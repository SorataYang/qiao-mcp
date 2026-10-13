"""Compare an installed candidate over stdio and local mcp-proxy (POSIX only).

Pass --python from a fresh environment containing the candidate wheel. No bridge
operation is called; both transports use an intentionally unused bridge endpoint.
This checks a local process, not Glama's Docker infrastructure.
"""

import argparse
import asyncio
import hashlib
import json
import os
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

PROXY_VERSION = "6.7.19"
BRIDGE_ENV = {
    "BRIDGE_PROVIDER": "qtmodel",
    "QIAOTONG_HTTP_URL": "http://localhost:1/pythonForQt/",
    "PYTHONPATH": "",
    "PYTHONNOUSERSITE": "1",
}


async def snapshot(session: ClientSession) -> dict:
    initialized = await session.initialize()
    return {
        "initialize": initialized.model_dump(mode="json", exclude_none=True),
        "tools": [t.model_dump(mode="json", exclude_none=True)
                  for t in (await session.list_tools()).tools],
        "resources": [r.model_dump(mode="json", exclude_none=True)
                      for r in (await session.list_resources()).resources],
        "prompts": [p.model_dump(mode="json", exclude_none=True)
                    for p in (await session.list_prompts()).prompts],
    }


async def compare(python: Path, cwd: str, port: int, version: str, catalog: Path) -> dict:
    params = StdioServerParameters(
        command=str(python), args=["-m", "qiao_mcp.server"], cwd=cwd, env=BRIDGE_ENV,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            direct = await snapshot(session)
    async with streamablehttp_client(
        f"http://127.0.0.1:{port}/mcp", timeout=15, sse_read_timeout=20,
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            proxy = await snapshot(session)

    expected = json.loads(catalog.read_text())
    assert direct["tools"] == proxy["tools"] == expected["tools"]
    assert direct["resources"] == proxy["resources"]
    assert direct["prompts"] == proxy["prompts"]
    initialized = proxy["initialize"]
    instructions = initialized["instructions"]
    assert instructions == direct["initialize"]["instructions"] == expected["initialize"]["instructions"]
    assert initialized["serverInfo"]["name"] == "qiao-mcp"
    assert initialized["serverInfo"]["version"] == version
    tools = proxy["tools"]
    fields = [p for t in tools for p in t["inputSchema"].get("properties", {}).values()]
    counts = {
        "tools": len(tools), "parameters": len(fields),
        "described_parameters": sum(bool(p.get("description")) for p in fields),
        "output_schemas": sum(bool(t.get("outputSchema")) for t in tools),
        "resources": len(proxy["resources"]), "prompts": len(proxy["prompts"]),
    }
    assert counts == {
        "tools": 153, "parameters": 596, "described_parameters": 596,
        "output_schemas": 151, "resources": 7, "prompts": 5,
    }
    return {
        "server_version": version, "proxy_version": PROXY_VERSION, **counts,
        "instructions_match_direct_stdio": True, "tools_match_candidate_catalog": True,
        "resources_and_prompts_match": True,
        "instructions_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
        "bridge_operations_called": False, "bridge_endpoint": BRIDGE_ENV["QIAOTONG_HTTP_URL"],
        "docker_build_tested": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("This local verification script requires POSIX process groups")
    # Keep the venv path itself; resolving its symlink would bypass the environment.
    python = args.python.absolute()
    output = args.output.absolute()
    env = {**os.environ, **BRIDGE_ENV}
    with tempfile.TemporaryDirectory(prefix="qiao-proxy-candidate-") as cwd:
        installed = json.loads(subprocess.check_output([
            str(python), "-c",
            "import importlib.metadata,json,qiao_mcp; "
            "print(json.dumps({'version':importlib.metadata.version('qiao-mcp'),"
            "'module':qiao_mcp.__file__}))",
        ], cwd=cwd, env=env, text=True))
        assert installed["version"] == args.version
        assert "site-packages" in installed["module"], "Use an installed wheel, not editable source"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        command = [
            "npm", "exec", "--yes", f"--package=mcp-proxy@{PROXY_VERSION}", "--",
            "mcp-proxy", "--host", "127.0.0.1", "--port", str(port), "--",
            str(python), "-m", "qiao_mcp.server",
        ]
        with output.with_suffix(".log").open("w") as log:
            process = subprocess.Popen(
                command, cwd=cwd, env=env, stdout=log, stderr=log, start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 20
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"Proxy exited with status {process.returncode}")
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                            break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Proxy did not listen within 20 seconds") from None
                        time.sleep(0.15)
                report = asyncio.run(asyncio.wait_for(compare(
                    python, cwd, port, args.version, args.catalog.absolute(),
                ), timeout=30))
            finally:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                raise AssertionError("Proxy is still listening after cleanup")
        except OSError:
            pass
        report.update(installed_package=installed, proxy_process_stopped=True, local_port_closed=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
