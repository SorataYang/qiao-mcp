"""Expose domain requests while preserving the original operation handlers."""

import re
from dataclasses import dataclass
from functools import reduce
from operator import or_
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.tools.base import Tool as RegisteredTool
from mcp.types import Tool, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, create_model

from qiao_mcp.tools.domains import TOOL_DOMAINS, ToolDomain
from qiao_mcp.tools.envelope import ToolInputError
from qiao_mcp.tools.schemas import ObjectResult

CATALOG_LAYOUT_ENV = "QIAO_MCP_CATALOG_LAYOUT"
DEFAULT_CATALOG_LAYOUT = "discovery"


class SearchResult(ObjectResult):
    items: list[dict[str, Any]] = Field(description="Operation summaries and effect annotations.")
    total: int = Field(description="Total matches before pagination.")
    next_offset: int | None = Field(description="Next page offset, null when complete.")


class OperationSchemaResult(ObjectResult):
    operation: str
    description: str
    inputSchema: dict[str, Any]
    outputSchema: dict[str, Any] | None
    annotations: dict[str, Any]


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
        if catalog_layout not in {"discovery", "domains", "flat"}:
            raise ValueError(f"{CATALOG_LAYOUT_ENV} must be 'discovery', 'domains' or 'flat', got {catalog_layout!r}")
        self.catalog_layout = catalog_layout
        self._bound_domains: dict[str, BoundDomain] = {}
        self._catalog_key: tuple[int, ...] | None = None
        super().__init__(name, **kwargs)
        self._discovery = FastMCP("operation-discovery")
        readonly = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

        @self._discovery.tool(annotations=readonly)
        def search_operations(
            query: str = Field(default="", description="Operation name or keywords, English or Chinese. Empty lists all operations (操作名/关键词，空值列出全部)."),
            domain: str = Field(default="", description="Optional exact domain name, e.g. edit_geometry, manage_checks (领域筛选)."),
            offset: int = Field(default=0, ge=0, description="Zero-based offset for the next page (分页偏移)."),
            limit: int = Field(default=10, ge=1, le=50, description="Maximum matches per page (每页条数)."),
        ) -> SearchResult:
            """Find engineering operations by name/keywords, then get_operation_schema before execution.

            Searches the complete local catalog without contacting QiaoTong. Returns
            short descriptions, domains and effect hints, not full parameter schemas.
            中文可用：节点、截面、荷载、检算、施工、预应力、结果；无匹配时缩短关键词。
            """
            domains = {op: item.name for item in TOOL_DOMAINS for op in item.operations}
            if domain and domain not in {item.name for item in TOOL_DOMAINS}:
                raise ToolInputError(f"Unknown domain: {domain}")
            terms = re.findall(r"[\w]+", query.casefold())
            matches = []
            for tool in self._tool_manager.list_tools():
                if domain and domains.get(tool.name) != domain:
                    continue
                searchable = f"{tool.name} {tool.description}".casefold()
                if not all(term in searchable for term in terms):
                    continue
                score = sum(10 if term in tool.name else 1 for term in terms)
                matches.append((score, tool))
            matches.sort(key=lambda item: (-item[0], item[1].name))
            items = [{
                "operation": tool.name, "domain": domains.get(tool.name),
                "description": tool.description.strip().split("\n\n")[0][:350],
                "annotations": tool.annotations.model_dump() if tool.annotations else {},
            } for _, tool in matches[offset:offset + limit]]
            return SearchResult(status="success", items=items, total=len(matches),
                                next_offset=offset + limit if offset + limit < len(matches) else None)

        @self._discovery.tool(annotations=readonly)
        def get_operation_schema(
            operation: str = Field(description="Exact operation name returned by search_operations (精确操作名)."),
        ) -> OperationSchemaResult:
            """Read one operation's complete input/output schemas, units, defaults and side effects.

            No backend access. Pass its input fields as execute_operation.arguments;
            preserve any nested request field. Schema availability is not desktop capability.
            """
            tool = self._tool_manager.get_tool(operation)
            if tool is None:
                raise ToolInputError(f"Unknown operation: {operation}")
            return OperationSchemaResult(status="success", operation=tool.name, description=tool.description,
                                inputSchema=tool.parameters, outputSchema=tool.output_schema,
                                annotations=tool.annotations.model_dump() if tool.annotations else {})

        @self._discovery.tool(structured_output=False, annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True,
        ))
        def execute_operation(
            operation: Annotated[str, Field(description="Exact operation name; read get_operation_schema first (先查操作定义).")],
            arguments: Annotated[dict[str, Any], Field(description="Original operation arguments, including nested request when present. No domain operation selector (原始参数).")],
        ):
            """Execute a discovered operation through its original validation and model-state guard.

            May modify/delete model data, start analysis or overwrite files. Inspect the
            operation's side effects first. Returns its original structured or image result.
            Lost-reply writes must not be retried automatically; read back affected objects.
            """
            raise RuntimeError("Execution is dispatched by the owning server")

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
        if self.catalog_layout == "discovery":
            return await self._discovery.list_tools()
        if self.catalog_layout == "flat":
            return await super().list_tools()
        return [domain.tool for domain in self._domains().values()]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        discovery = self._discovery._tool_manager.get_tool(name)
        if discovery is not None:
            try:
                if set(arguments) - set(discovery.parameters["properties"]):
                    raise ValueError("Unexpected discovery argument")
                parsed = discovery.fn_metadata.arg_model.model_validate(arguments).model_dump_one_level()
                if name != "execute_operation":
                    return await self._discovery.call_tool(name, arguments)
                selected = self._tool_manager.get_tool(parsed["operation"])
                if selected is None:
                    raise ValueError(f"Unknown operation: {parsed['operation']}")
                if set(parsed["arguments"]) - set(selected.parameters["properties"]):
                    raise ValueError("Unexpected operation argument")
                selected.fn_metadata.arg_model.model_validate(parsed["arguments"])
            except (ValueError, ValidationError) as exc:
                raise ToolInputError(f"Invalid request for {name}: {exc}") from exc
            return await super().call_tool(parsed["operation"], parsed["arguments"])
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
