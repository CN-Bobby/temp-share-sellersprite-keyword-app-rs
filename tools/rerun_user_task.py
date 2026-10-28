# -*- coding: utf-8 -*-
"""重跑用户任务：queryType=2 修复验证。

用法: python tools/rerun_user_task.py --input <旧任务 input.json> --month 202606 --workdir tests/.tmp_rerun
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.core.llm_client import LLMClient  # noqa: E402
from app.core.pipeline import Pipeline  # noqa: E402
from app.core.task_store import TaskStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="旧任务目录（读 input.json 的 ASIN 清单）")
    ap.add_argument("--month", default="202606")
    ap.add_argument("--mcp-key", required=True)
    ap.add_argument("--llm-base", required=True)
    ap.add_argument("--llm-key", required=True)
    ap.add_argument("--llm-model", default="deepseek-v4-flash")
    ap.add_argument("--workdir", default="tests/.tmp_rerun")
    args = ap.parse_args()

    old_input = json.loads((Path(args.input) / "input.json").read_text(encoding="utf-8"))
    asins = old_input["groups"][0].get("asins", [])
    marketplace = old_input["groups"][0].get("marketplace", "US")
    print(f"重跑 {marketplace} {len(asins)} ASIN，month={args.month}（queryType=2 修复验证）", flush=True)

    root = Path(args.workdir)
    root.mkdir(parents=True, exist_ok=True)
    settings = Settings(app_dir=root / "app")
    settings.workspace_dir = str(root / "ws")
    settings.mcp_url = "https://mcp.sellersprite.com/mcp"
    settings.mcp_secret_key = args.mcp_key
    settings.llm_base_url = args.llm_base
    settings.llm_api_key = args.llm_key
    settings.llm_model = args.llm_model
    settings.llm_mode = "auto"
    settings.llm_max_tokens = 16384
    settings.save()

    store = TaskStore(settings.workspace_dir)
    task_dir = store.create(marketplace, len(asins))
    input_data = {
        "groups": [{"marketplace": marketplace, "asins": asins,
                    "node_ids": [], "node_top_n": 50}],
        "options": {"data_month": args.month, "keyword_pool_pages": 3,
                    "trend_months": 24, "core_trend_keywords": 5,
                    "longtail_trend_keywords": 5, "trend_keyword_cap": 20,
                    "current_ppc": True, "historical_ppc": False,
                    "report_language": "zh-CN"},
    }
    (task_dir / "input.json").write_text(
        json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8")
    (task_dir / "plan.json").write_text(json.dumps(
        {"planned_total": 30, "hard_cap": 35, "confirmed": True}),
        encoding="utf-8")

    t0 = time.time()

    def on_event(e: dict) -> None:
        kind = e.get("kind")
        if kind == "phase":
            print(f"[{time.time()-t0:6.0f}s] PHASE {e['phase']}: {e.get('message','')}", flush=True)
        elif kind == "log":
            print(f"[{time.time()-t0:6.0f}s]   {e.get('line','')[:110]}", flush=True)

    llm = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model,
                    mode="auto", temperature=0.2, max_tokens=settings.llm_max_tokens)
    pipeline = Pipeline(settings, task_dir, store, on_event=on_event, llm=llm)
    result = pipeline.run()
    print(f"RESULT {result}", flush=True)

    # 矩阵交集检查（修复验证核心）
    m = json.loads((task_dir / "cache" / "asin_keyword_matrix.json").read_text(encoding="utf-8"))
    km = json.loads((task_dir / "cache" / "keyword_master.json").read_text(encoding="utf-8"))
    master = {k.get("keyword") for k in km.get("keywords", [])}
    recs = m.get("records", [])
    rec_words = {r.get("keyword") for r in recs}
    print(f"矩阵 records={len(recs)} / 唯一词={len(rec_words)} / 词池={len(master)} / 交集={len(rec_words & master)}", flush=True)
    print(f"任务目录: {task_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
