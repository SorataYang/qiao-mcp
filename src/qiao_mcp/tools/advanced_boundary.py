"""
MCP Tools for advanced boundary conditions.
高级边界条件工具

Provides tools for elastic links (弹性连接), master-slave links (主从约束),
and elastic supports (弹性支承).
"""

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider


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

    @mcp.tool()
    def add_beam_constraint(
        beam_id: int,
        release_i: list[bool] | None = None,
        release_j: list[bool] | None = None,
        group_name: str = "",
    ) -> str:
        """
        Set beam end releases / constraints (设置梁端约束/铰接释放).

        Controls which DOFs are released at each end of a beam element.
        True = released (free), False = fixed (constrained).
        用于控制梁单元两端的自由度释放，True=释放(铰接), False=固接。

        Common use: releasing rotation at one end to create a pin connection.
        常见用法：释放一端转动自由度以创建铰接。

        Args:
            beam_id: Beam element ID (梁单元编号)
            release_i: DOF releases at I-end [dx, dy, dz, rx, ry, rz]
                       (I端自由度释放，True=释放)
            release_j: DOF releases at J-end [dx, dy, dz, rx, ry, rz]
                       (J端自由度释放，True=释放)
            group_name: Boundary group name (边界组名)

        Example:
            add_beam_constraint(1, release_i=[False,False,False,False,True,False])
            # Release My rotation at I-end (I端释放绕Y轴转动=铰接)
        """
        try:
            provider.add_beam_constraint(
                beam_id=beam_id,
                info_i=release_i,
                info_j=release_j,
                group_name=group_name,
            )
            parts = []
            if release_i is not None:
                parts.append(f"I-end releases={release_i}")
            if release_j is not None:
                parts.append(f"J-end releases={release_j}")
            return (
                f"Beam constraint set on element {beam_id}: "
                f"{', '.join(parts)} (梁端约束设置成功)"
            )
        except Exception as e:
            return f"Error adding beam constraint (设置梁端约束失败): {e}"

    @mcp.tool()
    def add_constraint_equation(
        name: str,
        slave_node: int,
        slave_dof: int = 1,
        master_info: list[list] | None = None,
        group_name: str = "",
    ) -> str:
        """
        Add a constraint equation between node DOFs (添加约束方程).

        Establishes a linear relationship between a slave DOF and one or more
        master DOFs: slave_dof = Σ(coefficient × master_dof).
        建立从属自由度与主自由度之间的线性约束关系。

        Args:
            name: Constraint equation name (约束方程名称)
            slave_node: Slave node ID (从节点编号)
            slave_dof: Slave DOF index 1-6 (从节点自由度: 1=Dx,2=Dy,3=Dz,4=Rx,5=Ry,6=Rz)
            master_info: List of master DOF definitions [[node_id, dof, coefficient], ...]
                         (主自由度信息 [[节点号, 自由度号, 系数], ...])
            group_name: Boundary group name (边界组名)

        Example:
            add_constraint_equation("CE1", slave_node=5, slave_dof=3,
                                    master_info=[[1, 3, 1.0], [2, 3, 0.5]])
            # Node 5 Dz = 1.0 * Node1_Dz + 0.5 * Node2_Dz
        """
        try:
            kwargs = {"name": name, "sec_node": slave_node, "sec_dof": slave_dof}
            if master_info is not None:
                kwargs["master_info"] = [tuple(m) for m in master_info]
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_constraint_equation(**kwargs)
            return (
                f"Constraint equation '{name}' added on node {slave_node} DOF {slave_dof} "
                f"(约束方程 '{name}' 创建成功)"
            )
        except Exception as e:
            return f"Error adding constraint equation (添加约束方程失败): {e}"

    @mcp.tool()
    def remove_boundary(
        remove_id: int,
        kind: str,
        group_name: str = "",
        end: str = "I",
    ) -> str:
        """
        Remove a specific boundary condition (删除指定边界条件).

        Args:
            remove_id: Node or element ID to remove boundary from (节点或单元编号)
            kind: Boundary type to remove (边界类型):
                "support" (一般支承), "elastic_support" (弹性支承),
                "elastic_link" (弹性连接), "master_slave" (主从约束),
                "beam_constraint" (梁端约束), "constraint_equation" (约束方程)
            group_name: Boundary group name (边界组名)
            end: For beam constraints: "I" or "J" end (梁端约束时指定I端或J端)
        """
        try:
            kwargs = {"remove_id": remove_id, "kind": kind}
            if group_name:
                kwargs["group_name"] = group_name
            kwargs["extra_name"] = end
            provider.remove_boundary(**kwargs)
            return (
                f"Successfully removed {kind} boundary from ID {remove_id} "
                f"(成功删除 {kind} 边界条件)"
            )
        except Exception as e:
            return f"Error removing boundary (删除边界条件失败): {e}"
