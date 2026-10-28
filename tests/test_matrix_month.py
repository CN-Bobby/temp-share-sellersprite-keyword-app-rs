# -*- coding: utf-8 -*-
"""v1.2.0：矩阵支持指定月份 + 当月快照防呆。

覆盖：
1. mcp_client.traffic_keyword 的 month 传参（有/无）
2. aggregate_asin_keyword_matrix 带月份 meta → month_yyyyMM_top100 口径
3. pipeline 矩阵步骤落盘带 month meta
4. 防呆：当月快照 total=0 → 明确报错"快照尚未归档"；历史月 total=0 → 明确报错
"""
import asyncio
import json
from datetime import datetime

import pytest

from app.core.config import Settings
from app.core.pipeline import Pipeline
from app.core.task_store import TaskStore
from tests.fake_llm import FakeLLM
from tests.fake_mcp import FakeMCP


@pytest.fixture()
def env(tmp_path):
    settings = Settings(app_dir=tmp_path / "app")
    settings.workspace_dir = str(tmp_path / "ws")
    settings.window_max_calls = 1000
    settings.min_call_interval = 0.0
    store = TaskStore(settings.workspace_dir)
    return settings, store, []


def _task(env, asins, month):
    settings, store, events = env
    task_dir = store.create("US", len(asins))
    input_data = {
        "groups": [{"marketplace": "US", "asins": asins,
                    "node_ids": [], "node_top_n": 50}],
        "options": {"data_month": month, "keyword_pool_pages": 3,
                    "trend_months": 24, "core_trend_keywords": 5,
                    "longtail_trend_keywords": 5, "trend_keyword_cap": 20,
                    "current_ppc": True, "historical_ppc": False,
                    "report_language": "zh-CN"},
    }
    (task_dir / "input.json").write_text(
        json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8")
    (task_dir / "plan.json").write_text(json.dumps({
        "planned_total": 32, "hard_cap": 35, "confirmed": True,
        "confirmed_at": "2026-08-29T00:00:00+08:00",
    }), encoding="utf-8")
    return task_dir, input_data


# ---------- 1. mcp_client.traffic_keyword month 传参 ----------

def test_traffic_keyword_with_month(monkeypatch, tmp_path):
    from app.core.mcp_client import CallLog, MCPClient, RateLimiter
    calls = {}

    async def fake_call(self, tool, arguments, scope):
        calls["arguments"] = arguments
        calls["scope"] = scope
        return {"code": "OK", "data": {"items": []}}

    monkeypatch.setattr(MCPClient, "call", fake_call)
    client = MCPClient("fake://e", RateLimiter(100, 60, 0),
                       CallLog(tmp_path / "cl.json"))
    asyncio.run(client.traffic_keyword("UK", "B0972DTRZR", page=1, size=100,
                                       month="202607"))
    assert calls["arguments"]["request"]["month"] == "202607"
    assert "month=202607" in calls["scope"]


def test_traffic_keyword_without_month(monkeypatch, tmp_path):
    from app.core.mcp_client import CallLog, MCPClient, RateLimiter
    calls = {}

    async def fake_call(self, tool, arguments, scope):
        calls["arguments"] = arguments
        calls["scope"] = scope
        return {"code": "OK", "data": {"items": []}}

    monkeypatch.setattr(MCPClient, "call", fake_call)
    client = MCPClient("fake://e", RateLimiter(100, 60, 0),
                       CallLog(tmp_path / "cl.json"))
    asyncio.run(client.traffic_keyword("UK", "B0972DTRZR"))
    assert "month" not in calls["arguments"]["request"]
    assert "month=" not in calls["scope"]


# ---------- 2. aggregate_asin_keyword_matrix 月份口径 ----------

def test_matrix_aggregate_month_scope(tmp_path, monkeypatch):
    import argparse
    import runpy
    from pathlib import Path

    src = Path("tests/fixtures/mcp_responses/traffic_keyword_current_B07BF5K374_p1.json")
    raw = json.loads(src.read_text(encoding="utf-8"))
    raw["_meta"] = {**raw.get("_meta", {}), "month": "202607",
                    "page": 1, "page_size": 100}
    task_dir = tmp_path / "t"
    (task_dir / "raw").mkdir(parents=True)
    (task_dir / "cache").mkdir()
    (task_dir / "raw" / "traffic_keyword_current_B07BF5K374_p1.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    (task_dir / "input.json").write_text(json.dumps({
        "groups": [{"marketplace": "US", "asins": ["B07BF5K374"],
                    "node_ids": [], "node_top_n": 50}],
        "options": {"data_month": "202607"},
    }, ensure_ascii=False), encoding="utf-8")

    script = Path("app/engine/scripts/aggregate_asin_keyword_matrix.py")
    ns = runpy.run_path(str(script))
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args",
                        lambda self: argparse.Namespace(workdir=str(task_dir)))
    ns["main"]()

    out = json.loads((task_dir / "cache" / "asin_keyword_matrix.json")
                     .read_text(encoding="utf-8"))
    assert out["snapshot_type"] == "month"
    assert out["month"] == "202607"
    assert out["scope"] == "month_202607_top100"
    assert out["records"], "历史月矩阵应有记录"


# ---------- 3. pipeline 落盘带 month meta + 端到端口径 ----------

def test_pipeline_saves_month_meta_and_scope(env):
    """矩阵月份未设置（matrix_month 缺省）= 近30天实时（不跟随汇总月）。"""
    settings, store, events = env
    asins = ["B0GSXBMPY6", "B0DJVXJL89"]
    task_dir, input_data = _task(env, asins, month="202606")
    llm = FakeLLM()
    p = Pipeline(settings, task_dir, store, on_event=events.append, llm=llm)
    fake = FakeMCP("tests/fixtures/mcp_responses", p.rate_limiter, p.call_log,
                   on_event=p.on_event)
    p.mcp = fake
    result = p.run()
    assert result["status"] == "done"

    # 落盘 meta.month 为空（近30天实时），不跟随汇总月 202606
    meta = json.loads((task_dir / "raw" / "traffic_keyword_current_B0GSXBMPY6_p1.json")
                      .read_text(encoding="utf-8"))["_meta"]
    assert meta.get("month") is None
    # 矩阵缓存口径：current_top100
    matrix = json.loads((task_dir / "cache" / "asin_keyword_matrix.json")
                        .read_text(encoding="utf-8"))
    assert matrix["snapshot_type"] == "current"
    assert matrix["scope"] == "current_top100"
    assert matrix.get("month") is None
    # 报告已生成且校验通过
    assert (task_dir / "output").exists()
    reports = list((task_dir / "output").glob("*.xlsx"))
    assert reports, "应生成 xlsx 报告"
    # 矩阵首列 = "近30天实时（截至 采集日）"（未设置矩阵月份）
    import openpyxl
    wb = openpyxl.load_workbook(reports[0], data_only=False)
    rank_ws = wb["08_ASIN自然广告位矩阵"]
    assert rank_ws.cell(1, 1).value == "快照月份"
    assert rank_ws.cell(2, 1).value.startswith("近30天实时（截至 ")
    assert "截至 2026-08" in rank_ws.cell(2, 1).value
    # 00 看板含采集时刻
    dash = wb["00_市场看板"]
    vals = [dash.cell(r, 1).value for r in range(1, dash.max_row + 1)]
    assert "ASIN矩阵采集时刻" in vals
    # 事件含成功
    assert any(e.get("kind") == "phase" and e.get("phase") == "done"
               for e in events)


# ---------- 4. 防呆：当月快照 total=0 ----------

class _EmptyTrafficMCP:
    """traffic_extend 恒返回 total=0 的假 MCP（其余方法不可达）。"""

    async def traffic_extend(self, marketplace, asins, page, size=50,
                             history_date=None, query_type=2):
        return {"code": "OK", "message": "成功",
                "data": {"items": [], "total": 0, "page": page, "size": size}}


def test_foolproof_current_month_raises(env):
    settings, store, events = env
    task_dir, input_data = _task(env, ["B0972DTRZR"], month=datetime.now().strftime("%Y%m"))
    p = Pipeline(settings, task_dir, store, on_event=events.append, llm=FakeLLM())
    p.mcp = _EmptyTrafficMCP()
    with pytest.raises(RuntimeError, match="快照尚未归档"):
        asyncio.run(p._step_traffic_extend(input_data, []))


def test_foolproof_historical_month_raises(env):
    settings, store, events = env
    task_dir, input_data = _task(env, ["B0972DTRZR"], month="202607")
    p = Pipeline(settings, task_dir, store, on_event=events.append, llm=FakeLLM())
    p.mcp = _EmptyTrafficMCP()
    with pytest.raises(RuntimeError, match="total=0"):
        asyncio.run(p._step_traffic_extend(input_data, []))


# ---------- 5. v1.3.0：matrix_month 独立输入（方案 2） ----------

def test_prepare_task_input_matrix_month_independent(tmp_path):
    from app.core.pipeline import prepare_task_input
    groups = [{"marketplace": "UK", "asins": ["B0972DTRZR"],
               "node_ids": [], "node_top_n": 50}]
    ti = prepare_task_input(groups, "202512", matrix_month="202601")
    assert ti["options"]["data_month"] == "202512"
    assert ti["options"]["matrix_month"] == "202601"


def test_prepare_task_input_matrix_month_follows(tmp_path):
    from app.core.pipeline import prepare_task_input
    groups = [{"marketplace": "UK", "asins": ["B0972DTRZR"],
               "node_ids": [], "node_top_n": 50}]
    ti = prepare_task_input(groups, "202512")
    assert ti["options"]["data_month"] == "202512"
    assert "matrix_month" not in ti["options"]  # 跟随汇总月


def test_pipeline_x_neq_y_matrix_month(env):
    """X=202512 汇总、Y=202601 矩阵：词池按 X、矩阵按 Y、落盘 meta.month=Y。"""
    settings, store, events = env
    asins = ["B0GSXBMPY6", "B0DJVXJL89"]
    task_dir, input_data = _task(env, asins, month="202512")
    input_data["options"]["matrix_month"] = "202601"
    (task_dir / "input.json").write_text(
        json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8")
    llm = FakeLLM()
    p = Pipeline(settings, task_dir, store, on_event=events.append, llm=llm)
    fake = FakeMCP("tests/fixtures/mcp_responses", p.rate_limiter, p.call_log,
                   on_event=p.on_event)
    p.mcp = fake
    result = p.run()
    assert result["status"] == "done"
    # 反查词池按 X
    master = json.loads((task_dir / "cache" / "keyword_master.json")
                        .read_text(encoding="utf-8"))
    assert master["data_month"] == "202512"
    # 矩阵落盘 meta.month = Y
    meta = json.loads((task_dir / "raw" / "traffic_keyword_current_B0GSXBMPY6_p1.json")
                      .read_text(encoding="utf-8"))["_meta"]
    assert meta["month"] == "202601"
    # 矩阵缓存口径 Y
    matrix = json.loads((task_dir / "cache" / "asin_keyword_matrix.json")
                        .read_text(encoding="utf-8"))
    assert matrix["scope"] == "month_202601_top100"
    # 矩阵首列 = Y 月
    import openpyxl
    reports = list((task_dir / "output").glob("*.xlsx"))
    wb = openpyxl.load_workbook(reports[0], data_only=False)
    rank_ws = wb["08_ASIN自然广告位矩阵"]
    assert rank_ws.cell(1, 1).value == "快照月份"
    assert rank_ws.cell(2, 1).value == "202601"


class _EmptyMatrixMCP:
    """traffic_keyword 恒返回 total=0 的假 MCP（矩阵防呆用）。"""

    async def traffic_keyword(self, marketplace, asin, page=1, size=100,
                              month=None):
        return {"code": "OK", "message": "成功",
                "data": {"marketplace": marketplace, "asin": asin,
                         "total": 0, "items": []}}


def test_foolproof_matrix_month_current_raises(env):
    """Y=当月且所有矩阵 total=0 → 明确报错快照尚未归档。"""
    settings, store, events = env
    task_dir, input_data = _task(env, ["B0972DTRZR"],
                                 month=datetime.now().strftime("%Y%m"))
    input_data["options"]["matrix_month"] = datetime.now().strftime("%Y%m")
    p = Pipeline(settings, task_dir, store, on_event=events.append, llm=FakeLLM())
    p.mcp = _EmptyMatrixMCP()
    with pytest.raises(RuntimeError, match="快照尚未归档"):
        asyncio.run(p._step_traffic_keyword(input_data))
