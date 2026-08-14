"""端到端集成测试：建模 → 求解 → 查询结果。

需要桥通软件运行并设置 QIAOTONG_HTTP_URL 环境变量。
跳过条件：qtmodel 未安装或桥通软件未启动。
"""

import os

import pytest


@pytest.fixture
def skip_if_unavailable():
    """跳过测试，如果 qtmodel 不可用或桥通软件未运行。"""
    try:
        import qtmodel
    except ImportError:
        pytest.skip("qtmodel not installed")

    # 检查连接
    try:
        from qtmodel.core.qt_server import QtServer
        probe = getattr(QtServer, "get_connection_status", None)
        if probe:
            status = probe()
            if status.get("status") != "connected":
                pytest.skip(f"QiaoTong not connected: {status.get('message', 'unknown')}")
        else:
            # qtmodel < 2.6：尝试访问 mdb 触发连接
            _ = qtmodel.mdb
    except Exception as e:
        pytest.skip(f"QiaoTong connection failed: {e}")


def test_simple_beam_solve_and_query(skip_if_unavailable):
    """简支梁：创建节点/单元 → 设置边界/荷载 → 求解 → 查询位移和内力。"""
    import qtmodel

    # 1. 初始化
    qtmodel.mdb.initial()

    # 2. 创建节点（20m 跨，3个节点）
    qtmodel.mdb.add_nodes(
        node_data=[[0, 0, 0], [10, 0, 0], [20, 0, 0]],
        start_id=1,
        numbering_type=1
    )
    qtmodel.mdb.update_model()

    # 3. 创建材料和截面
    qtmodel.mdb.add_material(name='C50', database='C50')
    qtmodel.mdb.add_section(name='矩形1x1', sec_type='矩形', sec_info=[1.0, 1.0])
    qtmodel.mdb.update_model()

    # 4. 创建梁单元
    ele_data = [
        [1, 1, 1, 1, 0.0, 1, 2, 0, 0.0],  # 单元1: 节点1-2
        [2, 1, 1, 1, 0.0, 2, 3, 0, 0.0],  # 单元2: 节点2-3
    ]
    qtmodel.mdb.add_elements(ele_data=ele_data)
    qtmodel.mdb.update_model()

    # 5. 设置边界条件（节点1全固，节点3竖向铰支）
    qtmodel.mdb.add_general_support(node_id=1, boundary_info=[True] * 6)
    qtmodel.mdb.add_general_support(
        node_id=3,
        boundary_info=[False, True, False, False, False, False]
    )

    # 6. 创建荷载工况并施加均布荷载
    qtmodel.mdb.add_load_case(name='荷载1', case_type='恒载')
    qtmodel.mdb.add_beam_element_load(
        element_id=[1, 2],
        case_name='荷载1',
        load_type=1,  # 均布荷载
        coord_system=3,  # 整体坐标系
        list_x=[0.0, 1.0],  # 单元起点到终点
        list_load=[-100.0, -100.0]  # -100 kN/m（竖向向下）
    )
    qtmodel.mdb.update_model()

    # 7. 求解
    result = qtmodel.mdb.do_solve(wait=True, read_timeout=120, max_wait=300)
    assert result["ok"], f"求解失败: {result.get('message')}"
    assert result["state"] == "succeeded"

    # 8. 查询结果
    qtmodel.mdb.update_to_post()

    # 8.1 查询位移（节点2，跨中）
    # 注意：运营阶段荷载工况名是 "ST:" + 原工况名
    deform = qtmodel.odb.get_deformation(ids=2, stage_id=-1, case_name='ST:荷载1')
    assert len(deform) > 0, "应返回位移结果"
    d = deform[0]

    # 检查字段存在
    assert 'node_id' in d
    assert 'dz' in d, "应包含竖向位移 dz"

    # 简支梁跨中应有竖向位移
    dz = d['dz']
    assert dz < 0, f"跨中竖向位移应为负（向下），实际: {dz}"

    # 8.2 查询单元内力（单元1）
    force = qtmodel.odb.get_element_force(ids=1, stage_id=-1, case_name='ST:荷载1')
    assert len(force) > 0, "应返回内力结果"
    f = force[0]

    # 检查字段存在（qtmodel 返回嵌套的 force_i/force_j）
    assert 'element_id' in f
    assert 'force_i' in f
    assert 'force_j' in f

    # 简支梁均布荷载下，I端弯矩应大于J端（左端固支，右端铰支）
    my_i = abs(f['force_i'].get('My', 0))
    my_j = abs(f['force_j'].get('My', 0))
    assert my_i > 0, "I端弯矩应非零"
    assert my_j > 0, "J端弯矩应非零"

    print(f"✅ 测试通过")
    print(f"  跨中位移 dz = {dz:.6f} m")
    print(f"  单元1弯矩: I端 {my_i:.2f} kN·m, J端 {my_j:.2f} kN·m")
