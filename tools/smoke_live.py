# -*- coding: utf-8 -*-
"""真实冒烟脚本：20 个 US ASIN（历史任务合并），真实 MCP + 真实 LLM 全流程。

用法:
  python tools/smoke_live.py --mcp-key <KEY> --llm-base <URL> --llm-key <KEY> --llm-model <模型>
可选: --workdir <冒烟目录>（默认 tests/.tmp_smoke）--month 202606
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.core.engine import run_script  # noqa: E402
from app.core.llm_client import LLMClient  # noqa: E402
from app.core.pipeline import Pipeline  # noqa: E402
from app.core.task_store import TaskStore  # noqa: E402

# 历史任务合并的 20 个 US ASIN（f6ca2271 的 19 个 + ab57ceae 的 1 个）
SMOKE_ASINS = [
    "B0GSXBMPY6", "B0DJVXJL89", "B0D22TGD88", "B0DZPFGXYS", "B0DG8KFCTJ",
    "B0FC3T1K39", "B0BJJJ7B6J", "B0BBCBWLNP", "B07BF5K374", "B0CXF4NR2R",
    "B0FS1Q9T99", "B0FFSZ5DYG", "B0GJ7CCST9", "B0C15LVRG7", "B0CW1M9MKR",
    "B0F1MNW9PC", "B0BGPML441", "B09B1LRJ8F", "B0CC525JL2", "B0DHTTGH7G",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcp-key", required=True)
    ap.add_argument("--llm-base", required=True)
    ap.add_argument("--llm-key", required=True)
    ap.add_argument("--llm-model", required=True)
    ap.add_argument("--month", default="202606")
    ap.add_argument("--workdir", default="tests/.tmp_smoke")
    ap.add_argument("--resume", default=None,
                    help="复用已有任务目录续跑（不重复已完成的 MCP 调用）")
    args = ap.parse_args()

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
    settings.llm_max_tokens = 8192  # v4-flash 输出硬上限，超过会空输出
    settings.save()

    store = TaskStore(settings.workspace_dir)
    if args.resume:
        task_dir = Path(args.resume)
        if not (task_dir / "input.json").exists():
            print(f"续跑目录无效：{task_dir}", flush=True)
            return 1
        print(f"续跑任务：{task_dir.name}", flush=True)
    else:
        task_dir = store.create("US", len(SMOKE_ASINS))
        input_data = {
            "groups": [{"marketplace": "US", "asins": SMOKE_ASINS,
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
            {"planned_total": 33, "hard_cap": 35, "confirmed": True},
            ensure_ascii=False, indent=2), encoding="utf-8")

    t0 = time.time()
    phase_times: list[tuple[str, float]] = []
    last_phase = time.time()

    def on_event(e: dict) -> None:
        nonlocal last_phase
        kind = e.get("kind")
        if kind == "phase":
            now = time.time()
            phase_times.append((e.get("phase", ""), now - last_phase))
            last_phase = now
            print(f"[{now - t0:7.1f}s] PHASE {e['phase']}: {e.get('message', '')}", flush=True)
        elif kind == "log":
            print(f"[{time.time() - t0:7.1f}s]   {e.get('line', '')[:130]}", flush=True)
        elif kind == "rate_limit_wait":
            print(f"[{time.time() - t0:7.1f}s]   限流等待 {e.get('wait_seconds', 0):.0f}s…", flush=True)
        elif kind == "call_error":
            print(f"[{time.time() - t0:7.1f}s]   !! 调用失败 {e.get('tool')}: {e.get('error', '')[:150]}", flush=True)
        elif kind == "analysis_segment_degraded":
            print(f"[{time.time() - t0:7.1f}s]   !! 分析段降级 {e.get('segment')}: {e.get('error', '')[:150]}", flush=True)

    llm = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model,
                    mode="auto", temperature=0.2,
                    max_tokens=settings.llm_max_tokens)
    pipeline = Pipeline(settings, task_dir, store, on_event=on_event, llm=llm)
    print(f"冒烟开始：{len(SMOKE_ASINS)} ASIN，month={args.month}，预计 33 次调用（限流 8 次/分钟，约 4-5 分钟）", flush=True)
    result = pipeline.run()
    print(f"RESULT {result}", flush=True)
    print(f"总耗时 {time.time() - t0:.0f}s；各阶段耗时：{phase_times}", flush=True)

    if result.get("status") == "done":
        out = run_script("validate_report.py", task_dir)
        print("validate_report 输出：", flush=True)
        print(out[-2000:], flush=True)
        xlsx = list((task_dir / "output").glob("*.xlsx"))
        print(f"报告：{xlsx[0]}", flush=True)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
