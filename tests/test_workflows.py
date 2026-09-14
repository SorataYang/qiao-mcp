"""Exercise workflows against a model with existing entities and nonsequential IDs."""

import pytest
from conftest import FakeDb, tool_fns

from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.workflows import register_workflow_tools


class ModelDb(FakeDb):
    def __init__(self):
        super().__init__()
        self.nodes = [
            {"node_id": 1, "x": -10.0, "y": 0.0, "z": 0.0},
            {"node_id": 501, "x": 0.0, "y": 0.0, "z": 0.0},
        ]
        self.assigned_ids = iter([91, 17, 300, 51, 61, 27, 81, 45])
        self.materials = [{"index": 2, "name": "Other"}, {"index": 17, "name": "C50"}]
        self.sections = {"2": "Other", "29": "矩形梁", "31": "箱梁截面"}
        self.elements = [{"index": 40, "node_ids": [1, 501]}]
        self.load_groups = ["默认荷载组"]
        self.load_cases = ["SW"]

    def get_node_data(self, **kwargs):
        return list(reversed(self.nodes))

    def get_element_data(self, **kwargs):
        return self.elements

    def get_material_data(self):
        return self.materials

    def get_section_names(self):
        return self.sections

    def get_section_data(self, index, **kwargs):
        return {"name": self.sections[str(index)]}

    def get_load_group_names(self):
        return self.load_groups

    def get_load_case_names(self):
        return self.load_cases

    def add_nodes(self, node_data, **kwargs):
        self.calls.append(("add_nodes", (), {"node_data": node_data, **kwargs}))
        for x, y, z in node_data:
            if kwargs.get("is_merged") and any(
                (node["x"], node["y"], node["z"]) == (x, y, z) for node in self.nodes
            ):
                continue
            self.nodes.append({"node_id": next(self.assigned_ids), "x": x, "y": y, "z": z})

    def add_elements(self, ele_data):
        self.calls.append(("add_elements", (), {"ele_data": ele_data}))
        for row in ele_data:
            assert row[0] not in {element["index"] for element in self.elements}
            assert set(row[5:7]) <= {node["node_id"] for node in self.nodes}
            self.elements.append({"index": row[0], "node_ids": row[5:7]})

    def add_general_support(self, **kwargs):
        self.calls.append(("add_general_support", (), kwargs))

    def add_material(self, **kwargs):
        self.calls.append(("add_material", (), kwargs))
        self.materials.append({"index": 37, "name": kwargs["name"]})

    def add_section(self, **kwargs):
        self.calls.append(("add_section", (), kwargs))
        self.sections["47"] = kwargs["name"]

    def add_load_group(self, **kwargs):
        self.calls.append(("add_load_group", (), kwargs))
        self.load_groups.append(kwargs["name"])

    def add_load_case(self, **kwargs):
        self.calls.append(("add_load_case", (), kwargs))
        self.load_cases.append(kwargs["name"])


@pytest.fixture
def model(fake_provider):
    db = ModelDb()
    fake_provider._mdb = db
    return fake_provider, db, tool_fns(register_workflow_tools, fake_provider)


def test_simple_bridge_reuses_nodes_and_named_properties_without_overwriting_elements(model):
    _, db, functions = model
    result = functions["create_simple_beam_bridge"](span=20, num_elements=2)

    assert result["node_ids"] == [501, 91, 17]
    assert result["element_ids"] == [41, 42]
    assert result["material_id"] == 17
    assert result["section_id"] == 29
    elements = db.last("add_elements")[2]["ele_data"]
    assert [row[5:7] for row in elements] == [[501, 91], [91, 17]]
    assert all(row[2:4] == [17, 29] for row in elements)
    supports = [kwargs for method, _, kwargs in db.calls if method == "add_general_support"]
    assert [(s["node_id"], s["boundary_info"][0]) for s in supports] == [(501, True), (17, False)]
    assert db.elements[0] == {"index": 40, "node_ids": [1, 501]}
    for method in ("add_material", "add_section", "add_load_group", "add_load_case"):
        assert db.count(method) == 0


def test_continuous_bridge_places_piers_by_coordinate_order(model):
    _, db, functions = model
    result = functions["create_continuous_beam_bridge"](
        spans=[10, 20], num_elements_per_span=2,
    )
    assert result["node_ids"] == [501, 91, 17, 300, 51]
    assert result["support_node_ids"] == [501, 17, 51]
    assert result["section_id"] == 31
    coords = {node["node_id"]: node["x"] for node in db.nodes}
    rows = db.last("add_elements")[2]["ele_data"]
    assert [coords[row[6]] - coords[row[5]] for row in rows] == [5, 5, 10, 10]
    supports = [kwargs for method, _, kwargs in db.calls if method == "add_general_support"]
    assert [(s["node_id"], s["boundary_info"][0]) for s in supports] == [
        (501, False), (17, True), (51, False),
    ]


def test_missing_continuous_section_fails_before_any_write(model):
    _, db, functions = model
    with pytest.raises(ToolInputError, match="must already exist"):
        functions["create_continuous_beam_bridge"](section_name="Missing")
    assert db.calls == []


def test_simple_bridge_resolves_new_properties_after_creation(model):
    _, db, functions = model
    db.load_groups = []
    db.load_cases = []
    result = functions["create_simple_beam_bridge"](
        num_elements=2, material_name="C60", section_name="New rectangle",
    )
    assert result["material_id"] == 37
    assert result["section_id"] == 47
    assert db.last("add_section")[2]["sec_info"] == [1.0, 1.5]
    assert db.load_groups == ["默认荷载组"]
    assert db.load_cases == ["SW"]


@pytest.mark.parametrize("shape", ["ids", "records"])
def test_legacy_section_queries_resolve_the_requested_name(model, monkeypatch, shape):
    provider, _, functions = model
    data = [2, 29, 31] if shape == "ids" else [
        {"id": 2, "name": "Other"}, {"id": 29, "name": "矩形梁"},
    ]
    monkeypatch.setattr(provider, "get_section_names", lambda: data)
    result = functions["create_simple_beam_bridge"](num_elements=2)
    assert result["section_id"] == 29


def test_unresolved_node_ids_stop_before_elements_and_supports(model, monkeypatch):
    _, db, functions = model
    monkeypatch.setattr(db, "get_node_data", lambda **kwargs: [])
    with pytest.raises(ToolError, match="one distinct node ID"):
        functions["create_simple_beam_bridge"](num_elements=2)
    assert db.count("add_nodes") == 1
    assert db.count("add_elements") == 0
    assert db.count("add_general_support") == 0


@pytest.mark.parametrize("geometry", [
    {"ok": False, "reason": "chain folds back"},
    {"ok": True, "reason": "coordinates unavailable, check skipped"},
])
def test_unverified_geometry_stops_before_elements_and_supports(model, monkeypatch, geometry):
    provider, db, functions = model
    monkeypatch.setattr(provider, "check_node_chain_geometry", lambda ids: geometry)
    with pytest.raises(ToolError, match="geometry could not be verified"):
        functions["create_simple_beam_bridge"](num_elements=2)
    assert db.count("add_elements") == 0
    assert db.count("add_general_support") == 0


def test_property_creation_failure_is_not_mistaken_for_existing_property(model, monkeypatch):
    _, db, functions = model

    def fail(**kwargs):
        raise RuntimeError("material database unavailable")

    monkeypatch.setattr(db, "add_material", fail)
    with pytest.raises(ToolError, match="material database unavailable"):
        functions["create_simple_beam_bridge"](material_name="C60", num_elements=2)
    assert db.count("add_nodes") == 0
    assert db.count("add_elements") == 0


@pytest.mark.parametrize("tool, arguments", [
    ("create_simple_beam_bridge", {"span": 0}),
    ("create_simple_beam_bridge", {"span": float("nan")}),
    ("create_simple_beam_bridge", {"num_elements": 1}),
    ("create_simple_beam_bridge", {"section_width": -1}),
    ("create_simple_beam_bridge", {"material_name": " "}),
    ("create_continuous_beam_bridge", {"spans": []}),
    ("create_continuous_beam_bridge", {"spans": [10, -1]}),
    ("create_continuous_beam_bridge", {"spans": [float("inf")]}),
    ("create_continuous_beam_bridge", {"num_elements_per_span": 0}),
])
def test_invalid_geometry_is_rejected_before_any_write(model, tool, arguments):
    _, db, functions = model
    with pytest.raises(ToolInputError):
        functions[tool](**arguments)
    assert db.calls == []
