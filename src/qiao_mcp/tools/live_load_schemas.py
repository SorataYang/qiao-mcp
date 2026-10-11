"""Explicit live-load definitions; units belong to each native load system."""

from typing import Annotated, Literal

from pydantic import Field

from qiao_mcp.tools.schemas import QueryName

LiveLoadSystem = Literal["china_longitudinal", "aashto", "china_transversal", "bs", "en1991"]
LiveLoadCaseNames = Annotated[list[QueryName], Field(max_length=500)]
