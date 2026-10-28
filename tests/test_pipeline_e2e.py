# -*- coding: utf-8 -*-
"""端到端流水线测试：FakeMCP（历史真实响应 fixture）+ FakeLLM（确定性）离线全流程。"""
import json

import pytest

from app.core.config import Settings
from app.core.pipeline import Pipeline
from app.core.task_store import TaskStore
from tests.fake_llm import FakeLLM
from tests.fake_mcp import FakeMCP

# 历史任务 19 个 US ASIN（fixtures 完整覆盖）
HIST_ASINS = [
    "B0GSXBMPY6", "B0DJVXJL89", "B0D22TGD88", "B0DZPFGXYS", "B0DG8KFCTJ",
    "B0FC3T1K39", "B0BJJJ7B6J", "B0BBCBWLNP", "B07BF5K374", "B0CXF4NR2R",
    "B0FS1Q9T99", "B0FFSZ5DYG", "B0GJ7CCST9", "B0C15LVRG7", "B0CW1M9MKR",
    "B0F1MNW9PC", "B0BGPML441", "B09B1LRJ8F", "B0CC525JL2",
]

FIXTURES = "tests/fixtures/mcp_responses"


@pytest.fixture()
def env(tmp_path):
    settings = Settings(app_dir=tmp_path / "app")
    settings.workspace_dir = str(tmp_path / "ws")
    # E2E 放开限流（限流行为由 test_rate_limiter.py 单独覆盖），避免 32 次调用真实等待 4 分钟
    settings.window_max_calls = 1000
    settings.min_call_interval = 0.0
    store = TaskStore(settings.workspace_dir)
    events: list[dict] = []
    return settings, store, events


def _prepare_task(env, asins: list[str] | None = None) -> tuple:
    settings, store, events = env
    asins = asins or HIST_ASINS
    task_dir = store.create("US", len(asins))
    input_data = {
        "groups": [{"marketplace": "US", "asins": asins,
                    "node_ids": [], "node_top_n": 50}],
        "options": {"data_month": "202606", "keyword_pool_pages": 3,
                    "trend_months": 24, "core_trend_keywords": 5,
                    "longtail_trend_keywords": 5, "trend_keyword_cap": 20,
                    "current_ppc": True, "historical_ppc": False,
                    "report_language": "zh-CN"},
    }
    (task_dir / "input.json").write_text(json.dumps(input_data, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    (task_dir / "plan.json").write_text(json.dumps({
        "planned_total": 32, "hard_cap": 35, "confirmed": True,
        "confirmed_at": "2026-08-29T00:00:00+08:00",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return task_dir


def _make_pipeline(env, task_dir):
    settings, store, events = env
    llm = FakeLLM()
    p = Pipeline(settings, task_dir, store, on_event=events.append, llm=llm)
    # FakeMCP 复用 pipeline 的限流器与 call_log，只替换网络层
    fake = FakeMCP(FIXTURES, p.rate_limiter, p.call_log, on_event=p.on_event)
    p.mcp = fake
    return p, events


def test_full_pipeline_offline(env):
    task_dir = _prepare_task(env)
    p, events = _make_pipeline(env, task_dir)
    result = p.run()
    assert result["status"] == "done"

    # 事件链完整性
    kinds = [e.get("kind") for e in events]
    assert "phase" in kinds
    phases = [e["phase"] for e in events if e.get("kind") == "phase"]
    assert "done" in phases

    # 产物完整性
    assert (task_dir / "cache" / "keyword_master.json").exists()
    assert (task_dir / "cache" / "keyword_labeled.json").exists()
    assert (task_dir / "cache" / "trend_analysis.json").exists()
    assert (task_dir / "cache" / "analysis.json").exists()
    xlsx = list((task_dir / "output").glob("*.xlsx"))
    assert len(xlsx) == 1

    # call_log：3 反查页 + 19 矩阵 + 实际趋势词数（动态），须等于 plan 更新后的计划
    plan = json.loads((task_dir / "plan.json").read_text(encoding="utf-8"))
    log = json.loads((task_dir / "cache" / "call_log.json").read_text(encoding="utf-8"))
    assert log["actual_total"] == plan["planned_total"]
    assert plan["actual_trend_keywords"] > 0
    assert all(c["status"] == "success" for c in log["calls"])


def test_pipeline_uses_cache_on_rerun(env):
    """断点续跑：二次运行不新增调用（raw/cache 全命中）。"""
    task_dir = _prepare_task(env)
    p, events = _make_pipeline(env, task_dir)
    assert p.run()["status"] == "done"

    # 记录第一次调用数
    log1 = json.loads((task_dir / "cache" / "call_log.json").read_text(encoding="utf-8"))
    n1 = log1["actual_total"]

    # 第二次运行：全部缓存命中
    p2, events2 = _make_pipeline(env, task_dir)
    assert p2.run()["status"] == "done"
    log2 = json.loads((task_dir / "cache" / "call_log.json").read_text(encoding="utf-8"))
    assert log2["actual_total"] == n1


def test_pipeline_over_20_asins_blocked_by_validator(env):
    """21 个 ASIN 应被校验层拒绝（不能进入 pipeline）。"""
    from app.core.input_validator import ValidationError, validate_task

    asins = HIST_ASINS + ["B0ABCDEF12", "B0ABCDEF13"]
    with pytest.raises(ValidationError):
        validate_task([{"marketplace": "US", "asins": asins}], None)
