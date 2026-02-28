"""
High-level workflow tools for rapid bridge model creation.
高层工作流工具：快速桥梁建模

These tools combine multiple lower-level API calls to provide
one-step model generation for common bridge types.
"""

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider


def register_workflow_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register high-level workflow MCP tools."""

    @mcp.tool()
    def create_simple_beam_bridge(
        span: float = 20.0,
        num_elements: int = 10,
        material_name: str = "C50",
        section_name: str = "矩形梁",
        section_width: float = 1.0,
        section_height: float = 1.5,
        self_weight_case: str = "SW",
    ) -> str:
        """
        One-step creation of a simple beam bridge model (一键创建简支梁桥模型).

        Creates nodes, beam elements, supports, and a self-weight load case in
        a single step. The bridge lies along the X-axis.
        一键完成节点、梁单元、支承和自重工况的建立，桥梁沿X轴布置。

        Args:
            span: Span length in meters (跨径，单位m)
            num_elements: Number of beam elements (梁单元划分数量), min 2
            material_name: Material name (material must already exist) (材料名，须已创建)
            section_name: Section name (section must already exist) (截面名，须已创建)
            section_width: Section width in m for auto-creating a rectangle section
                           (矩形截面宽度，单位m，若截面不存在则自动创建)
            section_height: Section height in m (矩形截面高度，单位m)
            self_weight_case: Self-weight load case name (自重工况名)
        """
        try:
            log = []

            # 1. Create C50 concrete material if not present
            try:
                provider.add_material(
                    name=material_name, mat_type=1, standard=1, database=material_name
                )
                log.append(f"✓ Material '{material_name}' created")
            except Exception:
                log.append(f"ℹ Material '{material_name}' already exists or skipped")

            # 2. Create rectangular section if not present
            try:
                provider.add_section(
                    name=section_name,
                    sec_type="矩形",
                    sec_info=[section_width, section_height],
                )
                log.append(f"✓ Section '{section_name}' ({section_width}×{section_height}m) created")
            except Exception:
                log.append(f"ℹ Section '{section_name}' already exists or skipped")

            # 3. Create nodes along X-axis
            n = num_elements + 1
            dx = span / num_elements
            node_data = [[i + 1, i * dx, 0.0, 0.0] for i in range(n)]
            provider.add_nodes(node_data=node_data, is_merged=True)
            log.append(f"✓ {n} nodes created (x=0 to {span}m)")

            # 4. Get material and section IDs from model
            materials = provider.get_material_data()
            mat_id = next(
                (m.get("id", 1) for m in materials if m.get("name") == material_name), 1
            )
            sections = provider.get_section_names()
            sec_id = sections[0] if sections else 1

            # 5. Create beam elements
            ele_data = [
                [i + 1, 1, mat_id, sec_id, 0, i + 1, i + 2]
                for i in range(num_elements)
            ]
            provider.add_elements(ele_data=ele_data)
            log.append(f"✓ {num_elements} beam elements created")

            # 6. Set supports: pin at node 1, roller at last node
            provider.add_general_support(
                node_id=1, boundary_info=[True, True, True, False, False, False]
            )
            provider.add_general_support(
                node_id=n, boundary_info=[False, True, True, False, False, False]
            )
            log.append(f"✓ Pin support at node 1, roller at node {n}")

            # 7. Add self-weight load case automatically
            try:
                provider.add_self_weight(case_name=self_weight_case)
                log.append(f"✓ Self-weight case '{self_weight_case}' added")
            except Exception:
                log.append(f"ℹ Self-weight case skipped (add manually if needed)")

            return (
                f"✅ Simple beam bridge created successfully! (简支梁桥模型创建成功)\n"
                + "\n".join(log)
                + f"\n\nSpan: {span}m | Elements: {num_elements} | "
                f"Nodes: {n} | Material: {material_name} | Section: {section_name}\n"
                + "Next steps: apply_beam_distributed_load → configure_analysis → get_analysis_results"
            )
        except Exception as e:
            return f"Error creating simple beam bridge (创建简支梁桥失败): {e}"

    @mcp.tool()
    def create_continuous_beam_bridge(
        spans: list[float] = None,
        num_elements_per_span: int = 8,
        material_name: str = "C50",
        section_name: str = "箱梁截面",
        self_weight_case: str = "SW",
    ) -> str:
        """
        One-step creation of a continuous beam bridge model (一键创建连续梁桥模型).

        Creates a multi-span continuous beam with fixed supports at piers
        and appropriate end conditions.
        创建多跨连续梁桥，中间支座为固定支承，端部为活动支承。

        Args:
            spans: List of span lengths in meters (各跨跨径列表，单位m),
                   e.g. [30.0, 50.0, 30.0] means 3-span (3跨均匀布置)
            num_elements_per_span: Elements per span (每跨单元划分数)
            material_name: Material name (材料名，须已创建)
            section_name: Section name (截面名，须已创建)
            self_weight_case: Self-weight load case name (自重工况名)
        """
        if spans is None:
            spans = [30.0, 50.0, 30.0]

        try:
            log = []
            total_spans = len(spans)
            total_length = sum(spans)

            # 1. Materials and sections (attempt creation, skip if existing)
            try:
                provider.add_material(
                    name=material_name, mat_type=1, standard=1, database=material_name
                )
                log.append(f"✓ Material '{material_name}' created")
            except Exception:
                log.append(f"ℹ Material '{material_name}' skipped")

            # 2. Create nodes
            node_data = []
            x = 0.0
            node_id = 1
            for span_len in spans:
                dx = span_len / num_elements_per_span
                for j in range(num_elements_per_span):
                    node_data.append([node_id, round(x, 6), 0.0, 0.0])
                    x += dx
                    node_id += 1
            # Add final node
            node_data.append([node_id, round(total_length, 6), 0.0, 0.0])
            provider.add_nodes(node_data=node_data, is_merged=True)
            total_nodes = len(node_data)
            log.append(f"✓ {total_nodes} nodes created")

            # 3. Create elements
            materials = provider.get_material_data()
            mat_id = next(
                (m.get("id", 1) for m in materials if m.get("name") == material_name), 1
            )
            sections = provider.get_section_names()
            sec_id = sections[0] if sections else 1

            total_elements = total_spans * num_elements_per_span
            ele_data = [
                [i + 1, 1, mat_id, sec_id, 0, i + 1, i + 2]
                for i in range(total_elements)
            ]
            provider.add_elements(ele_data=ele_data)
            log.append(f"✓ {total_elements} beam elements created")

            # 4. Set supports at abutments and piers
            # Start abutment: roller (free X)
            provider.add_general_support(
                node_id=1, boundary_info=[False, True, True, False, False, False]
            )
            log.append("✓ Left abutment: roller support at node 1")

            # Pier nodes at span boundaries
            node_at_pier = 1
            for i, span_len in enumerate(spans[:-1]):
                node_at_pier += num_elements_per_span
                provider.add_general_support(
                    node_id=node_at_pier,
                    boundary_info=[True, True, True, False, False, False]
                )
                log.append(f"✓ Pier {i+1}: fixed support at node {node_at_pier}")

            # End abutment: roller
            provider.add_general_support(
                node_id=total_nodes,
                boundary_info=[False, True, True, False, False, False]
            )
            log.append(f"✓ Right abutment: roller support at node {total_nodes}")

            # 5. Self-weight
            try:
                provider.add_self_weight(case_name=self_weight_case)
                log.append(f"✓ Self-weight case '{self_weight_case}' added")
            except Exception:
                log.append("ℹ Self-weight case skipped")

            spans_str = "+".join(f"{s:.0f}" for s in spans)
            return (
                f"✅ Continuous beam bridge created! (连续梁桥模型创建成功)\n"
                + "\n".join(log)
                + f"\n\nSpans: {spans_str}m | Total: {total_length:.0f}m | "
                f"Nodes: {total_nodes} | Elements: {total_elements}\n"
                + "Next steps: apply loads → configure_analysis (enable creep) → get_analysis_results"
            )
        except Exception as e:
            return f"Error creating continuous beam bridge (创建连续梁桥失败): {e}"
