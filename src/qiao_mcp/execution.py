"""Non-blocking waits for synchronous desktop operations."""

import asyncio
from collections.abc import Callable
from contextvars import copy_context
from typing import TypeVar

from mcp.server.mcpserver import Context

T = TypeVar("T")
HEARTBEAT_SECONDS = 5.0


async def wait_for_operation(
    operation: Callable[[], T], ctx: Context, *, label: str, total: float | None,
) -> T:
    """Keep SDK context in the worker; cancelling the wait does not stop the desktop."""
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(None, copy_context().run, operation)
    elapsed = 0.0
    try:
        while True:
            done, _ = await asyncio.wait({future}, timeout=HEARTBEAT_SECONDS)
            if done:
                return await future
            elapsed += HEARTBEAT_SECONDS
            try:
                await ctx.report_progress(
                    progress=elapsed, total=total,
                    message=f"{label}: {elapsed:g}s elapsed",
                )
            except Exception:
                # Losing progress delivery must not replay or interrupt a write.
                pass
    finally:
        # A cancelled MCP waiter cannot cancel a synchronous SDK call. Retrieve
        # a later exception to avoid an unobserved Future warning; never retry.
        if not future.done():
            future.add_done_callback(lambda result: result.exception() if not result.cancelled() else None)
