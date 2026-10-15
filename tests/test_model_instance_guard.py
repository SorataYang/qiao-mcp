"""Exercise MCP scopes through the real SDK transport without a desktop."""

import asyncio
import json
import threading
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import ready_model_state, tool_fns

from qiao_mcp.domain_server import DomainFastMCP
from qiao_mcp.providers.qtmodel_provider import QtModelProvider
from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.catalog import register_tool_catalog
from qiao_mcp.tools.envelope import ToolError, _wrap
from qiao_mcp.tools.group_management import register_group_tools
from qiao_mcp.tools.modifications import register_modification_tools


@pytest.fixture
def guarded_native(fake_provider, monkeypatch):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    if not all(callable(getattr(QtServer, name, None)) for name in (
        "require_model_instance", "require_model_revision",
    )):
        pytest.skip("Installed qtmodel lacks instance/revision contexts")
    snapshot = ready_model_state()
    snapshot["server"] = {"model_instance_guard": 1, "model_revision_schema": 1}
    snapshot["model_state"].update(
        model_instance_id="project-a", model_revision="state-a", history_revision="history-a",
        pending_command_count=0, model_revision_uncertain=False,
    )
    wire = SimpleNamespace(calls=[], response=lambda header, body: (200, "{}"))

    def post(cls, command, header, read_timeout):
        try:
            body = json.loads(command) if command else {}
        except ValueError:
            body = command  # Legacy file routes use a bare path.
        wire.calls.append((header, body))
        code, text = wire.response(header, body)
        return SimpleNamespace(status_code=code, text=text)

    monkeypatch.setattr(QtServer, "_ensure_connection", classmethod(lambda cls: None))
    monkeypatch.setattr(QtServer, "_post", classmethod(post))
    fake_provider._mdb, fake_provider._odb, fake_provider._cdb = qtmodel.mdb, qtmodel.odb, qtmodel.cdb
    fake_provider.get_model_state = lambda: deepcopy(snapshot)
    return fake_provider, snapshot, wire, QtServer


def assert_scope_cleared(server, wire):
    server.send_dict("UPDATE")
    assert wire.calls[-1] == ("UPDATE", {})
    assert QtModelProvider._bound_model_instance.get() is None


@pytest.mark.parametrize("layout", ["domains", "flat"])
def test_all_group_mutations_and_commits_keep_one_model(guarded_native, layout):
    provider, _, wire, sdk = guarded_native
    provider.get_model_state = Mock(side_effect=provider.get_model_state)
    server = DomainFastMCP("guard-test", catalog_layout=layout)
    register_tool_catalog(server, provider)
    fields = {"name": "girder", "element_ids": [2, 3]}
    if layout == "domains":
        result = asyncio.run(server.call_tool("edit_construction", {
            "request": {"operation": "create_structure_group", **fields},
        }))
    else:
        result = asyncio.run(server.call_tool("create_structure_group", fields))
    assert result[1]["status"] == "success"
    assert len(wire.calls) == 4
    assert [header for header, _ in wire.calls].count("UPDATE") == 2
    assert all(body["expected_model_instance_id"] == "project-a" for _, body in wire.calls)
    assert all("expected_model_revision" not in body for _, body in wire.calls)
    provider.get_model_state.assert_called_once_with()
    assert_scope_cleared(sdk, wire)


def test_real_sdk_handshake_supplies_instance_capability(guarded_native, monkeypatch):
    provider, snapshot, wire, sdk = guarded_native
    monkeypatch.setattr(provider, "get_model_state", QtModelProvider.get_model_state.__get__(provider))
    monkeypatch.setattr(sdk, "get_connection_status", classmethod(lambda cls: {
        "status": "connected", "connected": True, "compatible": True,
        "server": {**snapshot["server"], "model_state": snapshot["model_state"]},
    }))
    tool_fns(register_group_tools, provider)["create_structure_group"](name="girder")
    assert len(wire.calls) == 2
    assert all(body["expected_model_instance_id"] == "project-a" for _, body in wire.calls)
    assert_scope_cleared(sdk, wire)


@pytest.mark.parametrize("switch_at", ["first_write", "commit"])
def test_model_switch_rejection_stops_without_replay(guarded_native, switch_at):
    provider, _, wire, sdk = guarded_native
    current = {"instance": "project-b" if switch_at == "first_write" else "project-a"}

    def response(header, body):
        if body.get("expected_model_instance_id") != current["instance"]:
            return 400, "MODEL_INSTANCE_MISMATCH: active project changed"
        current["instance"] = "project-b"
        return 200, "{}"

    wire.response = response
    create = tool_fns(register_group_tools, provider)["create_structure_group"]
    with pytest.raises(ToolError, match="MODEL_INSTANCE_MISMATCH"):
        create(name="girder", element_ids=[2, 3])
    assert len(wire.calls) == (1 if switch_at == "first_write" else 2)
    assert all(body["expected_model_instance_id"] == "project-a" for _, body in wire.calls)
    wire.response = lambda header, body: (200, "{}")
    assert_scope_cleared(sdk, wire)


def test_unknown_write_outcome_keeps_error_and_clears_binding(guarded_native):
    provider, _, wire, sdk = guarded_native
    wire.response = lambda header, body: (504, "reply unavailable")
    create = tool_fns(register_group_tools, provider)["create_structure_group"]
    with pytest.raises(ToolError, match="OUTCOME UNKNOWN.*Do NOT retry"):
        create(name="girder")
    assert len(wire.calls) == 1 and wire.calls[0][0] != "UPDATE"
    wire.response = lambda header, body: (200, "{}")
    assert_scope_cleared(sdk, wire)


@pytest.mark.parametrize("instance", [None, "", "   ", 12, "x" * 129])
def test_advertised_guard_requires_valid_instance(guarded_native, instance):
    provider, snapshot, wire, sdk = guarded_native
    snapshot["model_state"]["model_instance_id"] = instance
    create = tool_fns(register_group_tools, provider)["create_structure_group"]
    with pytest.raises(ToolError, match="MODEL_IDENTITY_UNAVAILABLE"):
        create(name="girder")
    assert wire.calls == []
    assert_scope_cleared(sdk, wire)


@pytest.mark.parametrize("protocol", [True, "1", 2])
def test_invalid_instance_protocol_is_explicit(guarded_native, protocol):
    provider, snapshot, wire, _ = guarded_native
    snapshot["server"]["model_instance_guard"] = protocol
    with pytest.raises(RuntimeError, match="MODEL_IDENTITY_UNAVAILABLE"):
        with provider.operation_context("model_write"):
            pytest.fail("invalid protocol was accepted")
    assert wire.calls == []


@pytest.mark.parametrize("protocol", [None, 0])
def test_older_desktop_keeps_existing_write_contract(guarded_native, protocol):
    provider, snapshot, wire, _ = guarded_native
    snapshot["server"]["model_instance_guard"] = protocol
    tool_fns(register_group_tools, provider)["create_structure_group"](name="girder")
    assert len(wire.calls) == 2
    assert all("expected_model_instance_id" not in body for _, body in wire.calls)


def test_older_sdk_keeps_existing_state_guard(guarded_native, monkeypatch):
    provider, snapshot, wire, sdk = guarded_native
    monkeypatch.delattr(sdk, "require_model_instance")
    create = tool_fns(register_group_tools, provider)["create_structure_group"]
    create(name="girder")
    assert all("expected_model_instance_id" not in body for _, body in wire.calls)
    wire.calls.clear()
    snapshot["model_state"]["capabilities"]["modify_model"] = False
    with pytest.raises(ToolError, match="modify_model"):
        create(name="blocked")
    assert wire.calls == []


def test_get_payload_is_not_changed_and_nested_scope_cannot_rebind(guarded_native):
    provider, snapshot, wire, sdk = guarded_native
    with provider.operation_context("model_write"):
        sdk.send_dict("GET-MODEL-DATA", {"ids": [1]})
        assert wire.calls == [("GET-MODEL-DATA", {"ids": [1], "version": sdk.QT_VERSION})]
        snapshot["model_state"]["model_instance_id"] = "project-b"
        with pytest.raises(RuntimeError, match="MODEL_INSTANCE_MISMATCH"):
            with provider.operation_context("model_write"):
                pytest.fail("nested scope changed the target model")
        sdk.send_dict("UPDATE")
        assert wire.calls[-1][1]["expected_model_instance_id"] == "project-a"
    assert_scope_cleared(sdk, wire)


def test_read_and_initialization_keep_their_payload_contracts(guarded_native):
    provider, _, wire, _ = guarded_native
    tool_fns(register_modification_tools, provider)["initialize_model"](confirm=True)
    assert wire.calls == [("INITIAL", {}), ("UPDATE", {})]
    wire.calls.clear()
    with provider.operation_context("model_read"):
        provider._mdb.get_model_edit_readiness()
    assert len(wire.calls) == 1
    assert wire.calls[0][0].startswith("GET-")
    assert wire.calls[0][1] == {}


def test_analysis_worker_receives_instance_context(guarded_native, monkeypatch):
    provider, _, wire, sdk = guarded_native
    server = DomainFastMCP("guard-solve")
    register_tool_catalog(server, provider)
    monkeypatch.setattr(server, "get_context", lambda: Mock(report_progress=AsyncMock()))
    threads = []

    def solve(**kwargs):
        threads.append(threading.get_ident())
        sdk.send_dict("DO-SOLVE")
        return {"state": "succeeded", "is_running": False}

    provider.run_analysis = solve
    result = asyncio.run(server.call_tool("analyze_model", {
        "request": {"operation": "run_analysis", "read_timeout": 60},
    }))
    assert result[1]["status"] == "success"
    assert threads and threads[0] != threading.get_ident()
    assert wire.calls == [("DO-SOLVE", {"expected_model_instance_id": "project-a"})]
    assert_scope_cleared(sdk, wire)


def test_concurrent_async_tools_do_not_share_instance_bindings(guarded_native):
    provider, snapshot, wire, sdk = guarded_native
    other = QtModelProvider.__new__(QtModelProvider)
    other_state = deepcopy(snapshot)
    other_state["model_state"]["model_instance_id"] = "project-b"
    other.get_model_state = lambda: other_state

    async def scenario():
        ready = asyncio.Event()

        async def first() -> str:
            ready.set()
            await asyncio.sleep(0.01)
            sdk.send_dict("UPDATE", {"caller": "a"})
            return "ok"

        async def second() -> str:
            await ready.wait()
            sdk.send_dict("UPDATE", {"caller": "b"})
            return "ok"

        await asyncio.gather(
            _wrap(first, provider, "model_write")(),
            _wrap(second, other, "model_write")(),
        )

    asyncio.run(scenario())
    assert {body["caller"]: body["expected_model_instance_id"] for _, body in wire.calls} == {
        "a": "project-a", "b": "project-b",
    }
    assert_scope_cleared(sdk, wire)


def test_cancelled_tool_clears_context(guarded_native):
    provider, _, wire, sdk = guarded_native

    async def cancelled() -> str:
        sdk.send_dict("UPDATE")
        raise asyncio.CancelledError

    async def scenario():
        with pytest.raises(asyncio.CancelledError):
            await _wrap(cancelled, provider, "model_write")()
        assert_scope_cleared(sdk, wire)

    asyncio.run(scenario())


def test_gateway_write_and_undo_use_their_own_contexts(guarded_native):
    provider, _, wire, sdk = guarded_native
    call = tool_fns(register_api_gateway_tools, provider)["call_qtmodel_api"]
    call(api_object="mdb", method="undo_model")
    assert wire.calls == [("UNDO", {
        "expected_model_instance_id": "project-a",
        "expected_model_revision": "state-a",
        "expected_history_revision": "history-a",
    })]
    wire.calls.clear()
    call(api_object="mdb", method="add_structure_group", kwargs={"name": "girder"})
    assert len(wire.calls) == 2
    assert all(body["expected_model_instance_id"] == "project-a" for _, body in wire.calls)
    assert all("expected_model_revision" not in body for _, body in wire.calls)
    assert_scope_cleared(sdk, wire)


def test_stale_undo_is_not_replayed(guarded_native):
    provider, _, wire, sdk = guarded_native
    wire.response = lambda header, body: (400, "MODEL_REVISION_MISMATCH")
    call = tool_fns(register_api_gateway_tools, provider)["call_qtmodel_api"]
    with pytest.raises(ToolError, match="MODEL_REVISION_MISMATCH"):
        call(api_object="mdb", method="undo_model")
    assert len(wire.calls) == 1 and wire.calls[0][0] == "UNDO"
    wire.response = lambda header, body: (200, "{}")
    assert_scope_cleared(sdk, wire)


@pytest.mark.parametrize("update,error", [
    ({"model_revision": ""}, "MODEL_REVISION_UNAVAILABLE"),
    ({"history_revision": None}, "MODEL_REVISION_UNAVAILABLE"),
    ({"pending_command_count": True}, "MODEL_REVISION_UNAVAILABLE"),
    ({"pending_command_count": -1}, "MODEL_REVISION_UNAVAILABLE"),
    ({"pending_command_count": 1}, "MODEL_REVISION_UNCERTAIN"),
    ({"model_revision_uncertain": "false"}, "MODEL_REVISION_UNAVAILABLE"),
    ({"model_revision_uncertain": True}, "MODEL_REVISION_UNCERTAIN"),
])
def test_undo_requires_valid_settled_revision(guarded_native, update, error):
    provider, snapshot, wire, sdk = guarded_native
    snapshot["model_state"].update(update)
    call = tool_fns(register_api_gateway_tools, provider)["call_qtmodel_api"]
    with pytest.raises(ToolError, match=error):
        call(api_object="mdb", method="undo_model")
    assert wire.calls == []
    assert_scope_cleared(sdk, wire)


@pytest.mark.parametrize("missing", ["sdk", "desktop"])
def test_undo_without_new_revision_protocol_keeps_existing_behavior(guarded_native, monkeypatch, missing):
    provider, snapshot, wire, sdk = guarded_native
    if missing == "sdk":
        monkeypatch.delattr(sdk, "require_model_revision")
    else:
        snapshot["server"].pop("model_revision_schema")
    call = tool_fns(register_api_gateway_tools, provider)["call_qtmodel_api"]
    call(api_object="mdb", method="undo_model")
    assert wire.calls == [("UNDO", {"expected_model_instance_id": "project-a"})]
    assert_scope_cleared(sdk, wire)


@pytest.mark.parametrize("method,path", [
    ("open_file", "C:/bridge test/model.bfmd"),
    ("save_file", "C:/bridge test/model.bfmd"),
    ("import_file", "C:/bridge test/model.mct"),
])
def test_native_file_routes_keep_bare_paths(guarded_native, method, path):
    provider, _, wire, sdk = guarded_native
    call = tool_fns(register_api_gateway_tools, provider)["call_qtmodel_api"]
    call(api_object="mdb", method=method, kwargs={"file_path": path})
    assert wire.calls[0][1] == path
    assert len(wire.calls) == (2 if method == "import_file" else 1)
    if method == "import_file":
        assert wire.calls[1] == ("UPDATE", {})
    assert_scope_cleared(sdk, wire)
