"""Structured query data alongside backward-compatible human-readable messages."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.schemas import DataResult, ResultPage, ResultSource


def _json_data(value: Any) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif callable(getattr(value, "to_dict", None)):
        value = value.to_dict()
    elif not isinstance(value, (Mapping, type)) and hasattr(value, "__dict__"):
        value = {key: item for key, item in vars(value).items() if not key.startswith("_")}
    if isinstance(value, Mapping):
        return {key: _json_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_data(item) for item in value]
    return value


def data_result(
    provider: BridgeProvider, operation: str, data: Any, message: str, *,
    selectors: dict[str, Any], limit: int | None = None, offset: int = 0,
    backend_page: bool = False,
) -> DataResult:
    """No extra backend calls, no fabricated units or result revision claims."""
    data = _json_data(data)
    json.dumps(data, allow_nan=False)  # Reject non-JSON/non-finite results instead of stringifying numbers.
    raw = data if isinstance(data, dict) else {}
    units = raw.get("units")
    coordinates = raw.get("coordinate_system")
    page = ResultPage(scope="none", offset=0, limit=None, returned=None, total=None, next_offset=None)
    if backend_page:
        items = raw.get("items", raw.get("data"))
        page = ResultPage(
            scope="backend", offset=raw.get("offset", offset), limit=raw.get("limit", limit),
            returned=len(items) if isinstance(items, list) else None,
            total=raw.get("total"),
            next_offset=raw.get("next_offset", offset + limit if raw.get("has_more") is True and limit else None),
        )
    elif isinstance(data, list):
        total = len(data)
        if limit is not None:
            limit, offset = max(1, min(limit, 500)), max(0, offset)
            data = data[offset:offset + limit]
        else:
            offset = 0
        page = ResultPage(scope="local" if limit is not None else "none", offset=offset,
                          limit=limit, returned=len(data), total=total,
                          next_offset=offset + len(data) if offset + len(data) < total else None)
    observed: dict[str, Any] = getattr(provider, "get_result_observation", lambda: {})()
    source = ResultSource(
        software=provider.get_software_name(), adapter_version=provider.version,
        operation=operation, selectors=selectors, read_at=datetime.now(UTC).isoformat(),
        observed_model_instance_id=observed.get("observed_model_instance_id"),
        observed_model_revision=observed.get("observed_model_revision"),
    )
    warnings = ["Observed model revision does not establish result freshness; verify the solved case/stage."]
    if units is None:
        warnings.append("Backend did not provide unit metadata; consult the operation and native schema before interpreting values.")
    if coordinates is None:
        warnings.append("Backend did not provide coordinate-system metadata.")
    if data is None or data == [] or data == {}:
        warnings.append("No data returned; this does not prove a zero response or a successful analysis.")
    return DataResult(status="success", message=message, data=data, source=source,
                      pagination=page, units=units, coordinate_system=coordinates, warnings=warnings)
