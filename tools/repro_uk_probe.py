# -*- coding: utf-8 -*-
"""对照实验：定位 UK 反查 items=0 的参数根因（month / ASIN 数 / 站点）。
方案 A: 8 ASIN 无 month；B: 单 ASIN + month=202608；C: 单 ASIN 无 month；D: 8 ASIN + month=202607。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.core.mcp_client import CallLog, MCPClient, RateLimiter  # noqa: E402

ASINS = ["B0972DTRZR", "B0D1V795HP", "B0F4QWVZFY", "B09MKGPRW3",
         "B08WR8TSDP", "B0F2H6K2B2", "B0GG9LSPS1", "B0CLY46NRY"]


def n_items(payload):
    d = payload.get("data") or {}
    items = d.get("items") or []
    return len(items), d.get("total"), (items[0].get("keyword") if items else "")


async def main() -> int:
    settings = Settings(app_dir=Path("."))
    key = settings.credentials.load("mcp_secret_key")
    url = f"{settings.mcp_url}?secret-key={key}"
    rl = RateLimiter(settings.window_max_calls, settings.window_seconds,
                     settings.min_call_interval)
    mcp = MCPClient(url, rl, CallLog(Path("tests/.tmp_repro/call_log2.json")),
                    request_timeout=settings.llm_request_timeout,
                    rate_limit_retry_wait=60.0)

    cases = [
        ("A 8ASIN 无month", lambda: mcp.traffic_extend("UK", ASINS, 1, size=50)),
        ("B 1ASIN +month2608", lambda: mcp.traffic_extend("UK", [ASINS[0]], 1, size=50, history_date="202608")),
        ("C 1ASIN 无month", lambda: mcp.traffic_extend("UK", [ASINS[0]], 1, size=50)),
        ("D 8ASIN +month2607", lambda: mcp.traffic_extend("UK", ASINS, 1, size=50, history_date="202607")),
    ]
    for label, fn in cases:
        payload = await fn()
        n, total, kw = n_items(payload)
        print(f"{label}: items={n} total={total} 首词={kw[:30]}")
        await asyncio.sleep(0)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
