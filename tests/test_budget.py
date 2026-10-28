# -*- coding: utf-8 -*-
"""预算计算测试（skill v1.6.2 公式）。"""
from app.core.budget import plan_budget


def test_standard_m2_20_asins():
    """20 个同站点 ASIN、无 Node、默认 10 趋势词 = ceil(20/20)*3 + 20 + 10 = 33。"""
    b = plan_budget([{"marketplace": "US", "asins": [f"B0A{i:07d}" for i in range(20)],
                      "node_ids": [], "node_top_n": 50}])
    assert b.planned_total == 33
    assert b.groups[0].pool_batches == 1
    assert b.groups[0].matrix_calls == 20
    assert b.groups[0].trend_calls == 10
    assert b.effective_hard_cap == 35


def test_20_plus_1_split_batches():
    """21 个 ASIN 拆 2 批：2*3 + 21 + 10 = 37。"""
    b = plan_budget([{"marketplace": "US", "asins": [f"B0A{i:07d}" for i in range(21)],
                      "node_ids": [], "node_top_n": 50}])
    assert b.groups[0].pool_batches == 2
    assert b.planned_total == 37


def test_m1_single_asin_plus_node():
    """M1（1 ASIN + 1 Node）：直接 ASIN 单独批 + 榜单余量批。
    u_est=51：pool_batches=1+ceil(50/20)=4 → 4*3=12 反查 + 矩阵 1 + 趋势 10
    + Node 校验 1 + 榜单 1 = 25（修复前低估为 17）。"""
    b = plan_budget([{"marketplace": "DE", "asins": ["B0ABCDEF12"],
                      "node_ids": ["12345"], "node_top_n": 50}])
    g = b.groups[0]
    assert g.extra_m1 == 1
    assert g.pool_batches == 4
    assert g.node_pages == 1
    assert g.total == 12 + 1 + 10 + 1 + 1


def test_hybrid_multi_asin_plus_node():
    """混合模式（2 ASIN + 1 Node）：反查池 = 2 + 50 = 52 → ceil(52/20)=3 批。
    3*3=9 + 矩阵 2 + 趋势 10 + Node 校验 1 + 榜单 1 = 23。"""
    b = plan_budget([{"marketplace": "US", "asins": ["B0ABCDEF12", "B0ABCDEF13"],
                      "node_ids": ["12345"], "node_top_n": 50}])
    g = b.groups[0]
    assert g.pool_batches == 3
    assert g.total == 9 + 2 + 10 + 1 + 1


def test_multi_site_groups():
    """多站点：US 20 ASIN + UK 5 ASIN，两组分别计算。"""
    b = plan_budget([
        {"marketplace": "US", "asins": [f"B0A{i:07d}" for i in range(20)], "node_ids": [], "node_top_n": 50},
        {"marketplace": "UK", "asins": [f"B0B{i:07d}" for i in range(5)], "node_ids": [], "node_top_n": 50},
    ])
    assert len(b.groups) == 2
    assert b.groups[0].marketplace == "US"
    assert b.groups[0].total == 33
    assert b.groups[1].total == 3 + 5 + 10


def test_pure_node_mode():
    """纯 Node：N + ΣP + ceil(U/20)*3 + T（U 按上限估算）。"""
    b = plan_budget([{"marketplace": "US", "asins": [], "node_ids": ["1", "2"],
                      "node_top_n": 50}])
    g = b.groups[0]
    # 2 node 校验 + 2 页榜单 + ceil(100/20)*3=15 + 10 趋势 = 29
    assert g.total == 2 + 2 + 15 + 10


def test_trend_cap():
    b = plan_budget([{"marketplace": "US", "asins": ["B0ABCDEF12"], "node_ids": [],
                      "node_top_n": 50}],
                    options={"core_trend_keywords": 15, "longtail_trend_keywords": 15,
                             "trend_keyword_cap": 20})
    assert b.groups[0].trend_calls == 20


def test_plan_dict_serializable():
    b = plan_budget([{"marketplace": "US", "asins": ["B0ABCDEF12"], "node_ids": [],
                      "node_top_n": 50}])
    d = b.as_dict()
    assert d["planned_total"] == 14  # 3 + 1 + 10
    assert isinstance(d["hard_cap"], int)
