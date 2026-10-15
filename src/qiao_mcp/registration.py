"""Capture operation metadata at registration without accessing SDK managers.

MCPServer exposes protocol schemas but not the argument models needed to build
our discriminated domain requests. Keep that SDK metadata dependency here;
listing and execution continue to use the public server API.
"""

import functools
import inspect
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.tools.base import Tool as RegisteredTool


class OperationServer(MCPServer):
    """Own the registered catalog and preserve 1.x synchronous execution order."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.registered_tools: dict[str, RegisteredTool] = {}
        super().__init__(*args, **kwargs)

    def add_tool(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        # Bind against the public signature so positional registration works too.
        options = inspect.signature(MCPServer.add_tool).bind(self, fn, *args, **kwargs)
        options.apply_defaults()
        metadata = dict(options.arguments)
        metadata.pop("self")
        tool = RegisteredTool.from_function(**metadata)
        if tool.name in self.registered_tools:
            return  # Match the SDK's first-registration-wins behavior.
        handler = fn
        if not inspect.iscoroutinefunction(fn):
            # 2.x sends synchronous handlers to a worker pool. Our shared desktop
            # provider previously ran these calls atomically on the event loop.
            # Keep that behavior; long-running analysis already offloads explicitly
            # with copy_context and retains its existing task deduplication.
            @functools.wraps(fn)
            async def handler(*call_args: Any, **call_kwargs: Any) -> Any:
                return fn(*call_args, **call_kwargs)

        super().add_tool(handler, *args, **kwargs)
        self.registered_tools[tool.name] = tool

    def remove_tool(self, name: str) -> None:
        super().remove_tool(name)
        self.registered_tools.pop(name)
