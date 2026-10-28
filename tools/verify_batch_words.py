# -*- coding: utf-8 -*-
"""抽样验证：两批 ASIN 的 指定月词池(qt=2) / 指定月矩阵 / 当前矩阵 词集交集。

用法: python tools/verify_batch_words.py --mcp-key <key>
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

SAMPLES = [
    ("任务A(202507批次)", "B0F8JKNNT7", "202507", "202606"),
    ("任务B(202606批次)", "B0D1DV9NHZ", "202606", "202606"),
    ("任务B(202606批次)", "B0CPSD21L4", "202606", "202606"),
]


async def main(key: str) -> None:
    url = f"https://mcp.sellersprite.com/mcp?secret-key={key}"
    rl = RateLimiter(max_calls=8, window_seconds=60.0, min_interval=7.5)
    client = MCPClient(url, rl, CallLog(Path("tests/.tmp_diag4_calllog.json")),
                       on_event=None)

    for label, asin, pool_month, kw_month in SAMPLES:
        print(f"\n===== {label} | ASIN {asin} =====", flush=True)
        # 1) 词池口径：traffic_extend queryType=2 + 指定月
        ext = await client.traffic_extend("US", [asin], page=1, size=100,
                                          history_date=pool_month, query_type=2)
        e = {i.get("keyword") for i in (ext.get("data") or {}).get("items") or []
             if isinstance(i, dict)}
        print(f"词池 qt=2 {pool_month}: {len(e)} 词", flush=True)
        # 2) 矩阵同月：traffic_keyword month=kw_month
        kw = await client.call(
            "traffic_keyword",
            {"request": {"marketplace": "US", "asin": asin, "page": 1, "size": 100,
                         "month": kw_month}},
            f"kw {kw_month} {asin}")
        k = {i.get("keyword") for i in (kw.get("data") or {}).get("items") or []
             if isinstance(i, dict)}
        print(f"矩阵 {kw_month}: {len(k)} 词", flush=True)
        # 3) 矩阵当前
        cur = await client.traffic_keyword("US", asin, page=1, size=100)
        c = {i.get("keyword") for i in (cur.get("data") or {}).get("items") or []
             if isinstance(i, dict)}
        print(f"矩阵当前: {len(c)} 词", flush=True)
        print(f"交集: 词池∩矩阵{kw_month}={len(e & k)} | 词池∩当前={len(e & c)} | 矩阵{kw_month}∩当前={len(k & c)}",
              flush=True)
        print(f"  词池样例: {sorted(e)[:6]}", flush=True)
        print(f"  矩阵{kw_month}样例: {sorted(k)[:6]}", flush=True)
        print(f"  当前样例: {sorted(c)[:6]}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcp-key", required=True)
    args = ap.parse_args()
    asyncio.run(main(args.mcp_key))
