"""Durable analysis handles independent of an MCP connection's lifetime."""

import asyncio
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from qiao_mcp.jobs import JobStore, refresh_job, start_job
from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.schemas import PageLimit, PageOffset

RequestId = Annotated[str, Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
JobId = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]


class AnalysisJob(BaseModel):
    job_id: str
    request_id: str
    state: Literal["submitting", "running", "completed", "failed", "cancelled", "unknown"]
    parameters: dict[str, Any]
    model_instance_id: str
    submitted_model_revision: str | None
    created_at: float
    updated_at: float
    backend_started_at: str | float | None
    result: dict[str, Any] | None
    error: str | None


class JobResult(BaseModel):
    status: Literal["success"] = "success"
    job: AnalysisJob


class JobsResult(BaseModel):
    status: Literal["success"] = "success"
    jobs: list[AnalysisJob]
    next_offset: int | None


def register_job_tools(mcp: MCPServer, provider: BridgeProvider):
    store = JobStore()  # Lazy filesystem access; catalog inspection creates no DB.

    @mcp.tool()
    async def start_analysis_job(
        request_id: RequestId,
        kind: Literal["analysis", "concrete_check"] = "analysis",
        name: str = "",
        show_view: bool = False,
    ) -> JobResult:
        """Start a desktop solve and return a durable job handle without waiting for completion.

        Requires an instance-guard-capable SDK/desktop. For legacy backends use
        run_analysis/run_concrete_check. Writes/imports the requested check case
        or starts structural analysis; prepare settings and inspect model state first.
        Use a unique request_id for each intended run; reuse the SAME ID after a
        lost MCP reply to retrieve the existing job without submitting again.
        Poll get_analysis_job. Check job.state, not the outer success envelope.
        Disconnecting/closing an MCP client does not stop desktop execution.
        To cancel use QiaoTong's stop control, then poll for backend confirmation.
        (提交后返回任务号，断线不重复求解，完成计算不代表规范检算合格。)

        Args:
            request_id: Caller-generated unique token, e.g. UUID hex. Same token and
                parameters return the same job; changed parameters are rejected.
            kind: analysis for structural solve, concrete_check for a named check.
            name: Required check case name for concrete_check; empty for analysis.
            show_view: Show structural analysis progress window; false for checks.
        """
        if (kind == "analysis" and name) or (kind == "concrete_check" and (not name.strip() or show_view)):
            raise ToolError("analysis requires empty name; concrete_check requires name and show_view=false")
        try:
            job = await asyncio.to_thread(start_job, store, provider, request_id, {
                "kind": kind, "name": name, "show_view": show_view,
            })
            return JobResult(job=AnalysisJob.model_validate(job))
        except Exception as exc:
            raise ToolError(f"Job submission unavailable: {exc}") from exc

    @mcp.tool()
    async def get_analysis_job(job_id: JobId) -> JobResult:
        """Read a saved solve handle and reconcile the matching desktop task, without starting work.

        Poll every 2–5 seconds. Reconnect/restart with the same QIAO_MCP_JOB_DB.
        Completed results are the native solve status, not archived force/stress
        tables; use normal result tools against the matching solved model.
        A different model or unavailable connection returns unknown and can be
        queried again. A replaced task or lost start receipt cannot be attributed
        safely; inspect the desktop and never automatically resubmit.

        Args:
            job_id: Durable handle returned by start_analysis_job or list_analysis_jobs.
        """
        try:
            job = await asyncio.to_thread(refresh_job, store, provider, job_id)
            return JobResult(job=AnalysisJob.model_validate(job))
        except Exception as exc:
            raise ToolError(f"Cannot read job: {exc}") from exc

    @mcp.tool()
    async def list_analysis_jobs(limit: PageLimit = 20, offset: PageOffset = 0) -> JobsResult:
        """List locally saved solve handles without contacting QiaoTong.

        Entries are last-observed states; get_analysis_job refreshes one task.
        Records/request IDs persist until the user removes the job database.

        Args:
            limit: Number of saved jobs per page, at most 500.
            offset: Zero-based pagination offset, newest submissions first.
        """
        rows = await asyncio.to_thread(store.list, limit + 1, offset)
        return JobsResult(jobs=[AnalysisJob.model_validate(row) for row in rows[:limit]],
                          next_offset=offset + limit if len(rows) > limit else None)
