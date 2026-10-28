# -*- coding: utf-8 -*-
"""手动端到端调试入口：离线跑完整 pipeline，打印事件与耗时。"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.core.pipeline import Pipeline  # noqa: E402
from app.core.task_store import TaskStore  # noqa: E402
from tests.fake_llm import FakeLLM  # noqa: E402
from tests.fake_mcp import FakeMCP  # noqa: E402

HIST_ASINS = [
    "B0GSXBMPY6", "B0DJVXJL89", "B0D22TGD88", "B0DZPFGXYS", "B0DG8KFCTJ",
    "B0FC3T1K39", "B0BJJJ7B6J", "B0BBCBWLNP", "B07BF5K374", "B0CXF4NR2R",
    "B0FS1Q9T99", "B0FFSZ5DYG", "B0GJ7CCST9", "B0C15LVRG7", "B0CW1M9MKR",
    "B0F1MNW9PC", "B0BGPML441", "B09B1LRJ8F", "B0CC525JL2",
]

FIXTURES = "tests/fixtures/mcp_responses"

if __name__ == "__main__":
    workdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/.tmp_debug")
    workdir.mkdir(parents=True, exist_ok=True)
    ws = workdir / "ws"
    settings = Settings(app_dir=workdir / "app")
    settings.workspace_dir = str(ws)
    settings.window_max_calls = 1000
    settings.min_call_interval = 0.0
    store = TaskStore(ws)
    task_dir = store.create("US", len(HIST_ASINS))
    input_data = {
        "groups": [{"marketplace": "US", "asins": HIST_ASINS,
                    "node_ids": [], "node_top_n": 50}],
        "options": {"data_month": "202606", "keyword_pool_pages": 3,
                    "trend_months": 24, "core_trend_keywords": 5,
                    "longtail_trend_keywords": 5, "trend_keyword_cap": 20,
                    "current_ppc": True, "historical_ppc": False,
                    "report_language": "zh-CN"},
    }
    (task_dir / "input.json").write_text(
        json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8")
    (task_dir / "plan.json").write_text(json.dumps(
        {"planned_total": 32, "hard_cap": 35, "confirmed": True}), encoding="utf-8")

    t0 = time.time()

    def on_event(e):
        kind = e.get("kind")
        if kind == "phase":
            print(f"[{time.time()-t0:6.1f}s] PHASE {e['phase']}: {e.get('message','')}", flush=True)
        elif kind == "log":
            print(f"[{time.time()-t0:6.1f}s] LOG {e.get('line','')[:120]}", flush=True)
        elif kind in ("call_start", "call_success", "call_error"):
            print(f"[{time.time()-t0:6.1f}s] CALL {kind} {e.get('tool','')} {e.get('scope','')[:60]}", flush=True)
        elif kind == "label_batch_start":
            print(f"[{time.time()-t0:6.1f}s] LABEL batch {e.get('batch_index')}/{e.get('total_batches')} size={e.get('size')}", flush=True)
        elif kind == "analysis_segment_start":
            print(f"[{time.time()-t0:6.1f}s] ANALYSIS segment {e.get('segment')}", flush=True)

    llm = FakeLLM()
    p = Pipeline(settings, task_dir, store, on_event=on_event, llm=llm)
    p.mcp = FakeMCP(FIXTURES, p.rate_limiter, p.call_log, on_event=p.on_event)
    result = p.run()
    print(f"RESULT {result}", flush=True)
    print(f"TOTAL {time.time()-t0:.1f}s", flush=True)
