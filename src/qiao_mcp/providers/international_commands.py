"""Serialize strict international DTOs without SDK-only version metadata."""

import inspect
import json
from typing import Any

_METHODS = {
    "add_international_vehicle",
    "update_international_vehicle",
    "add_international_live_load_case",
    "update_international_live_load_case",
}


def call_model_command(fn, method: str, kwargs: dict[str, Any]) -> Any:
    """Retain SDK defaults/validation and the guarded, non-replaying transport."""
    if method not in _METHODS or getattr(fn, "__module__", "") != "qtmodel.mdb.mdb_international_live_load":
        return fn(**kwargs)

    from qtmodel.core.qt_server import QtServer
    from qtmodel.mdb.mdb_international_live_load import MdbInternationalLiveLoad

    arguments = inspect.signature(fn).bind(**kwargs)
    arguments.apply_defaults()
    values = dict(arguments.arguments)
    new_name = values.pop("new_name", None)
    if method.endswith("_vehicle"):
        fields = (
            "name", "standard", "vehicle_type", "definition_mode", "parameters",
            "load_items", "index", "consider_point_load", "consider_displacement_bias",
        )
        definition = {key: values.pop(key) for key in fields}
        definition["parameters"] = MdbInternationalLiveLoad._merge_vehicle_parameters(
            definition["parameters"], values,
        )
        payload = MdbInternationalLiveLoad._international_vehicle_payload(**definition)
    else:
        payload = _case_payload(values, MdbInternationalLiveLoad)
    if new_name is not None:
        payload["new_name"] = MdbInternationalLiveLoad._international_name(new_name)
    result = QtServer.send_command(
        header=method.upper().replace("_", "-"),
        command=json.dumps(payload, ensure_ascii=False, allow_nan=False),
    )
    if result is None or result == "":
        return result
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return result


def _case_payload(values: dict[str, Any], api) -> dict[str, Any]:
    """Match qtmodel's complete-case payload, including native subcase defaults."""
    fields = {"name", "influence_plane", "sub_cases", "index", "span", "save_sub_case_result"}
    factors = {"highway_factor", "railway_factor", "light_rail_factor"}
    if values.keys() - fields - factors:
        raise ValueError("Unsupported international case payload fields")
    api._international_name(values["name"])
    api._international_name(values["influence_plane"])
    api._international_index(values["index"], True)
    if api._international_number(values["span"]) < 0 or not isinstance(values["save_sub_case_result"], bool):
        raise ValueError("span 必须为非负数，save_sub_case_result 必须为 bool")
    sub_cases = values["sub_cases"]
    if not isinstance(sub_cases, (list, tuple)) or not sub_cases:
        raise ValueError("sub_cases 必须为非空列表")
    cases = []
    for sub in sub_cases:
        if not isinstance(sub, dict) or sub.keys() - {"vehicle_name", "lane_names", "factor", "optimized", "lane_count", "hb_lane_names"}:
            raise ValueError("子工况包含未知字段")
        item = dict(sub)
        api._international_name(item.get("vehicle_name"))
        for key in ("lane_names", "hb_lane_names"):
            names = item.get(key, [] if key == "hb_lane_names" else None)
            if not isinstance(names, (list, tuple)) or (key == "lane_names" and not names):
                raise ValueError("车道必须为名称列表且 lane_names 不能为空")
            item[key] = [api._international_name(name) for name in names]
        if api._international_number(item.setdefault("factor", 1)) <= 0:
            raise ValueError("子工况系数必须为正数")
        if not isinstance(item.setdefault("optimized", False), bool):
            raise ValueError("optimized 必须为 bool")
        count = item.setdefault("lane_count", 0)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("lane_count 必须为非负整数")
        cases.append(item)
    payload = {key: values[key] for key in fields}
    payload["sub_cases"] = cases
    for key in factors:
        value = values[key]
        if value is not None:
            if not isinstance(value, dict):
                raise ValueError("系数必须为字典或 None")
            payload[key] = value
    return payload
