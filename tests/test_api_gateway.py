"""逃生舱工具行为测试：方法发现、签名先验校验、危险方法拦截。"""

import pytest
from conftest import ready_model_state, tool_fns, tool_text

from qiao_mcp.providers.qtmodel_provider import QtModelProvider
from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.envelope import ToolError


class RealSigMdb:
    """带真实签名的假 mdb，用于验证签名先验校验。"""

    def __init__(self):
        self.calls = []

    def add_tendon_group(self, name: str = ""):
        self.calls.append(("add_tendon_group", {"name": name}))

    def delete_model_object(self, object_type: str, index: int):
        self.calls.append(("delete_model_object", {"object_type": object_type, "index": index}))

    def get_node_data(self, ids=None):
        self.calls.append(("get_node_data", {"ids": ids}))
        return []

    def save_file(self, file_path: str = ""):
        self.calls.append(("save_file", {"file_path": file_path}))

    def update_model(self):
        self.calls.append(("update_model", {}))

    def initial(self):  # 危险方法
        self.calls.append(("initial", {}))

    def post_python_file(self, file_path: str, url: str = ""):  # 作用于 MCP 主机
        self.calls.append(("post_python_file", {"file_path": file_path, "url": url}))

    def prepare_model_edit(self, preparation_token: str):  # 可不可逆删除结果
        self.calls.append(("prepare_model_edit", {"preparation_token": preparation_token}))

    def wait_solve(self, poll_interval: float = 5, max_wait=None):  # 默认无限期轮询
        self.calls.append(("wait_solve", {"poll_interval": poll_interval, "max_wait": max_wait}))

    def export_api_help(self, file_path: str):  # 写 MCP 主机任意路径
        self.calls.append(("export_api_help", {"file_path": file_path}))

    def list_parameter_section_types(self):  # 纯本地计算
        self.calls.append(("list_parameter_section_types", {}))
        return ["矩形"]

    def resolve_node_selection(self, node_ids=None):  # 桥通内只读解析
        self.calls.append(("resolve_node_selection", {"node_ids": node_ids}))
        return {"node_ids": node_ids or []}


@pytest.fixture
def gateway_provider():
    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    p._mdb = RealSigMdb()
    p._odb = None
    p._cdb = None
    p.get_model_state = ready_model_state
    return p


def test_list_api_filters_by_pattern(gateway_provider):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    text = tool_text(fns["list_qtmodel_api"](api_object="mdb", pattern="tendon"))
    assert "add_tendon_group(name: str = '')" in text
    assert "update_model" not in text


def test_call_api_dispatches_and_refreshes(gateway_provider):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    result = fns["call_qtmodel_api"](
        api_object="mdb", method="add_tendon_group", kwargs={"name": "钢束组1"}
    )
    assert "successfully" in tool_text(result)
    calls = gateway_provider._mdb.calls
    assert ("add_tendon_group", {"name": "钢束组1"}) in calls
    assert ("update_model", {}) in calls, "mdb 的 add_* 调用后应刷新模型"


def test_call_api_rejects_wrong_kwargs_before_dispatch(gateway_provider):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    with pytest.raises(ToolError) as exc:
        fns["call_qtmodel_api"](
            api_object="mdb", method="add_tendon_group", kwargs={"nameX": "x"}
        )
    msg = str(exc.value)
    assert "参数不匹配" in msg
    assert "add_tendon_group(name: str = '')" in msg, "报错须回显真实签名"
    assert gateway_provider._mdb.calls == [], "校验失败不得下发"


def test_call_api_blocks_dangerous_methods(gateway_provider):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    with pytest.raises(ToolError) as exc:
        fns["call_qtmodel_api"](api_object="mdb", method="initial")
    msg = str(exc.value)
    assert "not callable via the gateway" in msg or "逃生舱" in msg
    assert gateway_provider._mdb.calls == []


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("post_python_file", {"file_path": "/etc/passwd", "url": "http://example.invalid/"}),
        ("prepare_model_edit", {"preparation_token": "t"}),
        ("wait_solve", {"max_wait": None}),
        ("export_api_help", {"file_path": "/Users/someone/.zshrc"}),
    ],
)
def test_call_api_blocks_host_and_irreversible_methods(gateway_provider, method, kwargs):
    """作用于主机、不可逆或长耗时的方法不得经逃生舱直呼，也不出现在检索结果中。"""
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    with pytest.raises(ToolError, match="not callable via the gateway"):
        fns["call_qtmodel_api"](api_object="mdb", method=method, kwargs=kwargs)
    assert gateway_provider._mdb.calls == []
    listed = tool_text(fns["list_qtmodel_api"](api_object="mdb", pattern=method))
    assert listed.startswith("No mdb methods found")


def test_call_api_commits_every_mdb_write(gateway_provider):
    """2.9 的写接口（如 delete_model_object）进入复合命令，须由 update_model 提交。"""
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    fns["call_qtmodel_api"](
        api_object="mdb", method="delete_model_object",
        kwargs={"object_type": "node", "index": 3},
    )
    assert gateway_provider._mdb.calls == [
        ("delete_model_object", {"object_type": "node", "index": 3}),
        ("update_model", {}),
    ]


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("get_node_data", {"ids": [1]}),
        ("list_parameter_section_types", {}),
        ("resolve_node_selection", {"node_ids": [1, 2]}),
        ("save_file", {"file_path": "C:/a.bfmd"}),
    ],
)
def test_call_api_skips_commit_for_reads_and_project_commands(gateway_provider, method, kwargs):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    fns["call_qtmodel_api"](api_object="mdb", method=method, kwargs=kwargs)
    assert [name for name, _ in gateway_provider._mdb.calls] == [method]


def test_call_api_guards_unprefixed_helpers_as_reads(gateway_provider):
    """不带 get_ 前缀却不改模型的方法按读守卫：模型不可写时仍可调用，写方法照拦。"""
    state = ready_model_state()
    state["model_state"]["capabilities"]["modify_model"] = False
    gateway_provider.get_model_state = lambda: state
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    fns["call_qtmodel_api"](
        api_object="mdb", method="resolve_node_selection", kwargs={"node_ids": [1]}
    )
    with pytest.raises(ToolError, match="modify_model"):
        fns["call_qtmodel_api"](
            api_object="mdb", method="delete_model_object",
            kwargs={"object_type": "node", "index": 3},
        )
    assert [name for name, _ in gateway_provider._mdb.calls] == ["resolve_node_selection"]


def test_call_api_unknown_method(gateway_provider):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    with pytest.raises(ToolError) as exc:
        fns["call_qtmodel_api"](api_object="mdb", method="no_such_method")
    assert "no method" in str(exc.value)
