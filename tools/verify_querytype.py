# -*- coding: utf-8 -*-
"""验证：traffic_extend queryType=2（当前榜单）与 traffic_keyword 同月词交集。

用法: python tools/verify_querytype.py --mcp-key <key>
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.call_log import CallLog  # noqa: E402
from app.core.mcp_client import MCPClient  # noqa: E402
from app.core.rate_limiter import RateLimiter  # noqa: E402

ASIN = "B0F8JKNNT7"
MONTH = "202606"


async def main(key: str) -> None:
    url = f"https://mcp.sellersprite.com/mcp?secret-key={key}"
    rl = RateLimiter(max_calls=8, window_seconds=60.0, min_interval=7.5)
    client = MCPClient(url, rl, CallLog(Path("tests/.tmp_diag3_calllog.json")),
                       on_event=None)

    kw = await client.call(
        "traffic_keyword",
        {"request": {"marketplace": "US", "asin": ASIN, "page": 1, "size": 100,
                     "month": MONTH}},
        f"US kw {MONTH} asin {ASIN} p1")
    kw_items = (kw.get("data") or {}).get("items") or []
    kw_words = {i.get("keyword") for i in kw_items if isinstance(i, dict)}
    print(f"traffic_keyword {MONTH}: {len(kw_words)} 词", flush=True)

    for qt in (2,):
        ext = await client.call(
            "traffic_extend",
            {"request": {"marketplace": "US", "asinList": [ASIN], "page": 1,
                         "size": 100, "historyDate": MONTH, "queryType": qt}},
            f"US extend qt={qt} {MONTH} asin {ASIN} p1")
        items = (ext.get("data") or {}).get("items") or []
        words = {i.get("keyword") for i in items if isinstance(i, dict)}
        inter = kw_words & words
        print(f"traffic_extend queryType={qt} {MONTH}: {len(words)} 词，与 keyword 交集 {len(inter)}",
              flush=True)
        for k in sorted(inter)[:10]:
            print("  交集:", k, flush=True)
        print("  extend 样例:", sorted(words)[:10], flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcp-key", required=True)
    args = ap.parse_args()
    asyncio.run(main(args.mcp_key))
