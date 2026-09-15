"""Canonical tool registration, also usable for offline schema inspection."""

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.advanced_boundary import register_advanced_boundary_tools
from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.checking import register_checking_tools
from qiao_mcp.tools.envelope import register_tools_with_envelope
from qiao_mcp.tools.group_management import register_group_tools
from qiao_mcp.tools.modifications import register_modification_tools
from qiao_mcp.tools.moving_load import register_moving_load_tools
from qiao_mcp.tools.queries import register_query_tools
from qiao_mcp.tools.tendon import register_tendon_tools
from qiao_mcp.tools.visualization import register_visualization_tools
from qiao_mcp.tools.workflows import register_workflow_tools

TOOL_REGISTRARS = (
    register_modeling_tools,
    register_group_tools,
    register_tendon_tools,
    register_advanced_boundary_tools,
    register_visualization_tools,
    register_moving_load_tools,
    register_checking_tools,
    register_workflow_tools,
    register_query_tools,
    register_modification_tools,
    register_api_gateway_tools,
)


def register_tool_catalog(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register the same complete catalog for the server and offline validation."""
    for registrar in TOOL_REGISTRARS:
        register_tools_with_envelope(mcp, registrar, provider)
