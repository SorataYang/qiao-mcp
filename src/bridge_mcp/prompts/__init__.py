"""
MCP Prompts for bridge design workflows.
桥梁设计工作流模板

Provides guided workflow templates for common bridge design scenarios.
"""

from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP):
    """Register all MCP prompts."""

    @mcp.prompt()
    def design_simple_beam(
        span_length: float = 20.0,
        beam_height: float = 1.5,
        material: str = "C50",
    ) -> str:
        """
        Guided workflow for designing a simple beam bridge (简支梁桥设计流程).

        Args:
            span_length: Span length in meters (跨径，单位m)
            beam_height: Beam height in meters (梁高，单位m)
            material: Concrete grade (混凝土等级)
        """
        return f"""You are a bridge structural engineer assistant. Please help design a simple beam bridge
with the following parameters:

## Design Parameters (设计参数)
- Span length (跨径): {span_length}m
- Beam height (梁高): {beam_height}m
- Material (材料): {material}

## Workflow Steps (工作流步骤)

1. **Create Material (创建材料)**: Use `create_material` tool to add concrete material {material}
2. **Create Section (创建截面)**: Use `create_section` tool to create the beam cross-section
3. **Create Nodes (创建节点)**: Use `create_nodes` tool to create support and midspan nodes
4. **Create Elements (创建单元)**: Use `create_elements` tool to connect nodes with beam elements
5. **Set Supports (设置支承)**: Use `set_support` tool to add boundary conditions
   - Left support: pin (铰接) - fix DX, DY, DZ
   - Right support: roller (滑动) - fix DY, DZ
6. **Apply Loads (施加荷载)**: Use `apply_nodal_force` or `apply_beam_distributed_load`
7. **Validate Model (验证模型)**: Use `validate_model` to check for issues
8. **Configure Analysis (配置分析)**: Use `configure_analysis` to set up the analysis
9. **Review Results (查看结果)**: Use `get_analysis_results` to check deformation and forces

Please proceed step by step, explaining each action and its engineering rationale.
请按步骤进行，解释每个操作及其工程依据。
"""

    @mcp.prompt()
    def design_continuous_beam(
        spans: str = "30+50+30",
        material: str = "C50",
    ) -> str:
        """
        Guided workflow for designing a continuous beam bridge (连续梁桥设计流程).

        Args:
            spans: Span arrangement, e.g. '30+50+30' in meters (跨径布置)
            material: Concrete grade (混凝土等级)
        """
        return f"""You are a bridge structural engineer assistant. Please help design a continuous beam bridge.

## Design Parameters (设计参数)
- Span arrangement (跨径布置): {spans}m
- Material (材料): {material}

## Workflow Steps (工作流步骤)

1. **Parse Span Info**: Parse span arrangement "{spans}" to determine support locations
2. **Create Material**: Add concrete material {material} with creep/shrinkage parameters
3. **Create Sections**: Create variable depth cross-sections (box girder typical for continuous beams)
4. **Create Nodes**: Create nodes at supports, quarter-points, and midspan
5. **Create Elements**: Connect with beam elements, assign tapered sections
6. **Set Supports**: Apply appropriate boundary conditions at each pier/abutment
7. **Define Construction Stages**: Set up cantilever construction stages if applicable
8. **Apply Dead/Live Loads**: Self-weight, secondary dead load, vehicle loads
9. **Add Prestressing**: Define tendon profiles and apply prestress forces
10. **Validate & Analyze**: Check model and run staged construction analysis
11. **Review Results**: Check stresses, deformations at critical sections

请注意连续梁的关键设计要点：跨中和支座处的弯矩分布、预应力筋布置、施工阶段分析。
"""

    @mcp.prompt()
    def check_structure(
        check_standard: str = "JTG3362-2018",
    ) -> str:
        """
        Guided workflow for structural code checking (结构检算工作流).

        Args:
            check_standard: Design code standard (检算规范),
                           e.g. 'JTG3362-2018' (公路), 'TB10092-2017' (铁路)
        """
        return f"""You are a bridge structural engineer assistant. Please help perform structural code checking.

## Check Standard (检算规范): {check_standard}

## Workflow Steps (工作流步骤)

1. **Review Model**: First use `get_model_info` to understand the current model
2. **Review Results**: Use `get_analysis_results` to check critical force/stress values
3. **Identify Critical Sections**: Determine governing sections based on force envelopes
4. **Set Up Load Combinations**: Define code-required load combinations
5. **Configure Check Cases**: Set up concrete/steel check cases per {check_standard}
6. **Add Reinforcement if needed**: Configure reinforcement for concrete members
7. **Run Check**: Execute structural verification
8. **Evaluate Results**: Review check results against allowable limits

请确保所有检算工况覆盖了规范 {check_standard} 要求的所有组合。
"""

    @mcp.prompt()
    def construction_stage_analysis() -> str:
        """
        Guided workflow for construction stage analysis (施工阶段分析工作流).
        """
        return """You are a bridge structural engineer assistant. Please help set up construction stage analysis.

## Workflow Steps (工作流步骤)

1. **Review Model Structure**: Use `get_model_info` to understand the model components
2. **Define Structure Groups**: Organize elements by construction sequence (按施工顺序组织结构组)
3. **Define Boundary Groups**: Group boundaries that change during construction
4. **Define Load Groups**: Group loads by application stage
5. **Create Construction Stages**: Use `add_construction_stage` to define each stage with:
   - Duration (时长)
   - Activated/deactivated structure groups (激活/钝化结构组)
   - Activated/deactivated boundary conditions (激活/钝化边界条件)
   - Applied loads (施加荷载)
   - Temporary loads (临时荷载)
6. **Configure Creep/Shrinkage**: Enable time-dependent analysis if concrete
7. **Set Analysis Parameters**: Configure construction stage analysis settings
8. **Validate**: Run `validate_model` before analysis
9. **Analyze**: Run the construction stage analysis
10. **Review Stage Results**: Check results at each critical stage

关键要点：确保施工顺序逻辑正确，龄期设置合理，安装方法选择正确（变形法/无应力法）。
"""
