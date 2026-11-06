"""Build the Claude Desktop MCP Bundle (.mcpb) from the working tree.

    uv run python scripts/build_mcpb.py             # validate, pack and smoke-test
    uv run python scripts/build_mcpb.py --no-smoke  # skip the stdio check

The manifest uses the uv server type: the bundle ships the source, pyproject.toml
and uv.lock, and the host installs the locked dependencies on first launch.
Requires Node (npx) for the pinned mcpb CLI. Output goes to dist/mcpb/.
"""

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "packaging" / "mcpb" / "manifest.json"
MCPB_CLI = "@anthropic-ai/mcpb@2.1.2"
BUNDLE_FILES = ["pyproject.toml", "uv.lock", "README.md", "LICENSE", "NOTICE"]
# uv run --frozen fails without the lock, and uv_build needs the readme and license files.
REQUIRED_ENTRIES = {"manifest.json", "uv.lock", "pyproject.toml", "src/qiao_mcp/server.py"}


def run(*command: str) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def npx() -> str:
    executable = shutil.which("npx")
    if executable is None:
        sys.exit("npx not found: install Node.js to run the mcpb CLI")
    return executable


def stage_bundle(stage: Path) -> None:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copy2(MANIFEST, stage / "manifest.json")
    for name in BUNDLE_FILES:
        shutil.copy2(ROOT / name, stage / name)
    shutil.copytree(ROOT / "src", stage / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


async def smoke_test(bundle: Path, workdir: Path, manifest: dict) -> None:
    if workdir.exists():
        shutil.rmtree(workdir)
    with zipfile.ZipFile(bundle) as archive:
        missing = REQUIRED_ENTRIES - set(archive.namelist())
        assert not missing, f"Bundle is missing {sorted(missing)}"
        archive.extractall(workdir)
    config = manifest["server"]["mcp_config"]
    args = [arg.replace("${__dirname}", str(workdir)) for arg in config["args"]]
    params = StdioServerParameters(
        command=shutil.which(config["command"]) or config["command"],
        args=args,
        # An explicit unused endpoint avoids discovering a real bridge session.
        env={"QIAOTONG_HTTP_URL": "http://localhost:1/pythonForQt/"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            tools = {tool.name for tool in (await session.list_tools()).tools}
            connection = await session.call_tool("execute_operation", {
                "operation": "check_qiaotong_connection", "arguments": {},
            })
    assert initialized.server_info.version == manifest["version"], initialized.server_info
    assert tools == {tool["name"] for tool in manifest["tools"]}, tools
    assert not connection.is_error, connection
    print(f"Smoke test passed: {sorted(tools)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-smoke", action="store_true", help="skip starting the packed server over stdio")
    options = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if manifest["version"] != version:
        sys.exit(f"{MANIFEST.relative_to(ROOT)} version {manifest['version']} != pyproject.toml {version}")

    run("uv", "lock", "--check")
    output = ROOT / "dist" / "mcpb"
    stage = output / "stage"
    bundle = output / f"qiao-mcp-{version}.mcpb"
    stage_bundle(stage)
    run(npx(), "-y", MCPB_CLI, "validate", str(stage / "manifest.json"))
    run(npx(), "-y", MCPB_CLI, "pack", str(stage), str(bundle))
    if not options.no_smoke:
        asyncio.run(smoke_test(bundle, output / "smoke", manifest))
    print(f"Built {bundle.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
