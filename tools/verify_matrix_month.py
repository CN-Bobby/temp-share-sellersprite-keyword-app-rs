# -*- coding: utf-8 -*-
"""验证：traffic_keyword 传历史月（与词池同月）是否与词池交集。

用法: python tools/verify_matrix_month.py --mcp-key <key> <任务目录>
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.call_log import CallLog  # noqa: E402
from app.core.mcp_client import MCPClient  # noqa: E402
from app.core.rate_limiter import RateLimiter  # noqa: E402


async def main(key: str, task: Path) -> None:
    url = f"https://mcp.sellersprite.com/mcp?secret-key={key}"
    km = json.loads((task / "cache" / "keyword_master.json").read_text(encoding="utf-8"))
    master = {k.get("keyword") for k in km.get("keywords", [])}
    print(f"词池 {len(master)} 词", flush=True)
    rl = RateLimiter(max_calls=8, window_seconds=60.0, min_interval=7.5)
    client = MCPClient(url, rl, CallLog(Path("tests/.tmp_diag_calllog.json")),
                       on_event=None)
    asin = "B0F8JKNNT7"
    print(f"--- traffic_keyword 当前（不传 month）{asin} ---", flush=True)
    cur = await client.traffic_keyword("US", asin, page=1, size=100)
    items = (cur.get("data") or {}).get("items") or []
    cur_kws = {i.get("keyword") for i in items if isinstance(i, dict)}
    print(f"  返回 {len(items)} 词；与词池交集 {len(cur_kws & master)}", flush=True)

    print(f"--- traffic_keyword month=202507 {asin} ---", flush=True)
    hist = await client.call(
        "traffic_keyword",
        {"request": {"marketplace": "US", "asin": asin, "page": 1, "size": 100,
                     "month": "202507"}},
        f"US snapshot 202507 asin {asin} page=1")
    items2 = (hist.get("data") or {}).get("items") or []
    hist_kws = {i.get("keyword") for i in items2 if isinstance(i, dict)}
    print(f"  返回 {len(items2)} 词；与词池交集 {len(hist_kws & master)}", flush=True)
    for k in sorted(hist_kws & master)[:8]:
        print("  交集词:", k, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcp-key", required=True)
    ap.add_argument("task", help="任务目录（读 cache/keyword_master.json 词池）")
    args = ap.parse_args()
    asyncio.run(main(args.mcp_key, Path(args.task)))
