"""
MCP Tools for advanced boundary conditions.
高级边界条件工具

Provides tools for elastic links (弹性连接), master-slave links (主从约束),
and elastic supports (弹性支承).
"""

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider


def register_advanced_boundary_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register advanced boundary condition MCP tools."""

    @mcp.tool()
    def add_elastic_link(
        link_type: int,
        start_node_id: int,
        end_node_id: int,
        stiffness_values: list[float] | None = None,
        group_name: str = "",
    ) -> str:
        """
        Add an elastic link between two nodes (添加弹性连接).

        Elastic links model connections like bearings and rigid arms between members.
        弹性连接用于模拟支座、刚性臂等节点间的连接关系。

        Args:
            link_type: Link type (连接类型):
                1=Rigid (刚性连接), 2=Rigid arm (刚性臂), 3=General elastic (一般弹性),
                4=Fixed-end (固接), 5=Master-slave (主从约束)
            start_node_id: Start node ID (起始节点编号)
            end_node_id: End node ID (终止节点编号)
            stiffness_values: Stiffness values [kx, ky, kz, krx, kry, krz] for type=3
                              弹性刚度值 [平动x, 平动y, 平动z, 转动x, 转动y, 转动z]
            group_name: Boundary group name (边界组名)
        """
        try:
            kwargs = {}
            if stiffness_values:
                kwargs["stiffness"] = stiffness_values
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_elastic_link(
                link_type=link_type,
                start_id=start_node_id,
                end_id=end_node_id,
                **kwargs,
            )
            link_type_names = {
                1: "Rigid(刚性)", 2: "Rigid arm(刚性臂)",
                3: "General elastic(一般弹性)", 4: "Fixed-end(固接)", 5: "Master-slave(主从)"
            }
            type_name = link_type_names.get(link_type, str(link_type))
            return (
                f"Elastic link ({type_name}) added between nodes {start_node_id} "
                f"and {end_node_id} (弹性连接创建成功)"
            )
        except Exception as e:
            return f"Error adding elastic link (添加弹性连接失败): {e}"

    @mcp.tool()
    def add_master_slave_link(
        master_node_id: int,
        slave_node_ids: list[int] | str,
        dof_constraints: list[bool] | None = None,
        group_name: str = "",
    ) -> str:
        """
        Add master-slave constraint (rigid link) between nodes (添加主从约束/刚域).

        Used to model rigid connections where slave nodes follow the motion
        of the master node (typically for diaphragm rigid zones).
        用于模拟刚域，从节点跟随主节点运动（典型应用：隔板刚域）。

        Args:
            master_node_id: Master node ID (主节点编号)
            slave_node_ids: Slave node ID(s) (从节点编号，支持列表或范围字符串)
            dof_constraints: DOF constraint flags [dx, dy, dz, rx, ry, rz],
                             True=constrained (自由度约束标志，True=约束)
            group_name: Boundary group name (边界组名)
        """
        try:
            kwargs = {}
            if dof_constraints:
                kwargs["dof_constraints"] = dof_constraints
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_master_slave_link(
                master_id=master_node_id,
                slave_ids=slave_node_ids,
                **kwargs,
            )
            return (
                f"Master-slave link added: master={master_node_id}, "
                f"slaves={slave_node_ids} (主从约束创建成功)"
            )
        except Exception as e:
            return f"Error adding master-slave link (添加主从约束失败): {e}"

    @mcp.tool()
    def add_elastic_support(
        node_id: int | list[int] | str,
        spring_values: list[float],
        group_name: str = "",
    ) -> str:
        """
        Add elastic spring supports on nodes (添加弹性支承/弹簧支座).

        Models foundation flexibility, pile caps, or rubber bearing stiffness.
        用于模拟地基柔度、桩基础、橡胶支座刚度等。

        Args:
            node_id: Node ID(s) (节点编号)
            spring_values: Spring stiffness [kx, ky, kz, krx, kry, krz] in N/m or N·m/rad
                           弹簧刚度 [平动x, 平动y, 平动z, 转动x, 转动y, 转动z]，单位 N/m 或 N·m/rad
            group_name: Boundary group name (边界组名)
        """
        try:
            kwargs = {}
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_elastic_support(
                node_id=node_id, spring_values=spring_values, **kwargs
            )
            return (
                f"Elastic support added on node(s) {node_id} "
                f"with stiffness {spring_values} (弹性支承创建成功)"
            )
        except Exception as e:
            return f"Error adding elastic support (添加弹性支承失败): {e}"
