"""
Configuration management for bridge-mcp.
配置管理
"""

from dataclasses import dataclass, field


@dataclass
class BridgeMCPConfig:
    """Configuration for the bridge-mcp server."""

    # Provider settings
    provider: str = "qtmodel"
    """The backend provider to use (桥梁分析软件后端)"""

    # Server settings
    server_name: str = "bridge-mcp"
    """MCP server display name"""

    transport: str = "stdio"
    """Transport mode: 'stdio' or 'sse'"""

    # Logging
    log_level: str = "INFO"
    """Logging level"""

    # Result image settings
    result_image_dir: str = ""
    """Directory to store result images (结果图片保存目录)"""

    # Provider-specific settings
    provider_config: dict = field(default_factory=dict)
    """Provider-specific configuration options"""
