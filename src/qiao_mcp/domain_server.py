"""Expose domain requests while preserving the original operation handlers."""

from dataclasses import dataclass
from functools import reduce
from operator import or_
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.tools.base import Tool as RegisteredTool
from mcp.types import Tool, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, create_model

from qiao_mcp.tools.domains import TOOL_DOMAINS, ToolDomain
from qiao_mcp.tools.envelope import ToolInputError

CATALOG_LAYOUT_ENV = "QIAO_MCP_CATALOG_LAYOUT"
DEFAULT_CATALOG_LAYOUT = "domains"


def _model_name(name: str) -> str:
    return "".join(part.title() for part in name.split("_"))


@dataclass(frozen=True)
class BoundDomain:
    tool: Tool
    request_adapter: TypeAdapter


def _bind_domain(domain: ToolDomain, operations: dict[str, RegisteredTool]) -> BoundDomain:
    variants = []
    members = [operations[name] for name in domain.operations]
    for tool in members:
        if "operation" in tool.fn_metadata.arg_model.model_fields:
            raise ValueError(f"Operation {tool.name} reserves the domain selector field")
        variants.append(create_model(
            f"{_model_name(tool.name)}Operation",
            __base__=tool.fn_metadata.arg_model,
            __config__=ConfigDict(extra="forbid"),
            __doc__=tool.description,
            operation=(Literal[tool.name], Field(description="Operation to perform (操作名称).")),
        ))
    request_type = reduce(or_, variants)
    envelope = create_model(
        f"{_model_name(domain.name)}Request",
        __base__=BaseModel,
        __config__=ConfigDict(extra="forbid"),
        request=(request_type, Field(discriminator="operation", description=(
            "Choose operation and supply only its matching fields. Each branch retains "
            "its original defaults, units and validation; an operation's nested request "
            "stays nested (选择操作并按对应分支填写参数，保留原有嵌套 request)."
        ))),
    )

    # Reuse the actual response models. Image operations have no structured
    # output contract, so a domain containing them likewise omits outputSchema.
    output_models = list(dict.fromkeys(tool.fn_metadata.output_model for tool in members))
    output_schema = None
    if None not in output_models:
        output_type = reduce(or_, [model for model in output_models if model is not None])
        output_schema = TypeAdapter(output_type).json_schema()
        output_schema["type"] = "object"
    annotations = [tool.annotations or ToolAnnotations() for tool in members]
    combined = ToolAnnotations(
        readOnlyHint=all(a.readOnlyHint is True for a in annotations),
        destructiveHint=any(a.destructiveHint is not False for a in annotations),
        idempotentHint=all(a.idempotentHint is True for a in annotations),
        openWorldHint=any(a.openWorldHint is not False for a in annotations),
    )
    return BoundDomain(
        tool=Tool(
            name=domain.name,
            title=domain.title,
            description=domain.description,
            inputSchema=envelope.model_json_schema(),
            outputSchema=output_schema,
            annotations=combined,
        ),
        request_adapter=TypeAdapter(envelope),
    )


class DomainFastMCP(FastMCP):
    """List domain schemas and dispatch both domain and legacy tool calls.

    The registered operation catalog remains the single source of argument
    models, output contracts and execution guards. No operations are selected
    out for scoring, and no backend is contacted while building the catalog.
    """

    def __init__(
        self, name: str | None = None, *, catalog_layout: str = DEFAULT_CATALOG_LAYOUT,
        **kwargs: Any,
    ) -> None:
        if catalog_layout not in {"domains", "flat"}:
            raise ValueError(f"{CATALOG_LAYOUT_ENV} must be 'domains' or 'flat', got {catalog_layout!r}")
        self.catalog_layout = catalog_layout
        self._bound_domains: dict[str, BoundDomain] = {}
        self._catalog_key: tuple[int, ...] | None = None
        super().__init__(name, **kwargs)

    def _domains(self) -> dict[str, BoundDomain]:
        registered = self._tool_manager.list_tools()
        key = tuple(id(tool) for tool in registered)
        if key != self._catalog_key:
            operations = {tool.name: tool for tool in registered}
            assigned = [name for domain in TOOL_DOMAINS for name in domain.operations]
            if len(assigned) != len(set(assigned)):
                raise ValueError("An operation belongs to more than one domain")
            missing = set(operations) - set(assigned)
            unknown = set(assigned) - set(operations)
            if missing or unknown:
                raise ValueError(f"Incomplete domain catalog: unassigned={sorted(missing)}, unknown={sorted(unknown)}")
            names = [domain.name for domain in TOOL_DOMAINS]
            if len(names) != len(set(names)) or set(names) & set(operations):
                raise ValueError("Domain names must be unique and distinct from operation names")
            bound = {domain.name: _bind_domain(domain, operations) for domain in TOOL_DOMAINS}
            self._bound_domains = bound
            self._catalog_key = key
        return self._bound_domains

    async def list_tools(self) -> list[Tool]:
        if self.catalog_layout == "flat":
            return await super().list_tools()
        return [domain.tool for domain in self._domains().values()]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        # Legacy clients retain their exact entry points and response behavior.
        if self._tool_manager.get_tool(name) is not None:
            return await super().call_tool(name, arguments)
        domain = self._domains().get(name)
        if domain is None:
            raise ToolInputError(f"Unknown tool: {name}")
        try:
            domain.request_adapter.validate_python(arguments)
        except ValidationError as exc:
            raise ToolInputError(f"Invalid request for {name}: {exc}") from exc
        # Forward the original values and omission choices, not a model dump
        # filled with defaults. The existing handler performs its usual checks,
        # receives the same Context, and converts its own structured/image result.
        selected = arguments["request"]
        operation = selected["operation"]
        fields = {key: value for key, value in selected.items() if key != "operation"}
        return await super().call_tool(operation, fields)
