# -*- coding: utf-8 -*-
"""交叉验证：traffic_extend 历史月 vs traffic_keyword 历史月，判定 month 支持性。

用法: python tools/verify_month_support.py --mcp-key <key>
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

ASIN = "B0F8JKNNT7"
MONTHS = ["202507", "202606"]


async def main(key: str) -> None:
    url = f"https://mcp.sellersprite.com/mcp?secret-key={key}"
    rl = RateLimiter(max_calls=8, window_seconds=60.0, min_interval=7.5)
    client = MCPClient(url, rl, CallLog(Path("tests/.tmp_diag2_calllog.json")),
                       on_event=None)
    for month in MONTHS:
        print(f"--- traffic_extend asinList=[{ASIN}] historyDate={month} ---", flush=True)
        ext = await client.traffic_extend("US", [ASIN], page=1, size=50,
                                          history_date=month, query_type=1)
        items = (ext.get("data") or {}).get("items") or []
        print(f"  返回 {len(items)} 词；样例: {[i.get('keyword') for i in items[:5]] if items else '(空)'}",
              flush=True)
        print(f"--- traffic_keyword month={month} {ASIN} ---", flush=True)
        kw = await client.call(
            "traffic_keyword",
            {"request": {"marketplace": "US", "asin": ASIN, "page": 1, "size": 100,
                         "month": month}},
            f"US snapshot {month} asin {ASIN} page=1")
        items2 = (kw.get("data") or {}).get("items") or []
        print(f"  返回 {len(items2)} 词；样例: {[i.get('keyword') for i in items2[:5]] if items2 else '(空)'}",
              flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcp-key", required=True)
    args = ap.parse_args()
    asyncio.run(main(args.mcp_key))
