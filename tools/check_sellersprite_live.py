# -*- coding: utf-8 -*-
"""单独验证 SellerSprite MCP 工具可用性：连接/list_tools + 最小业务调用。

用法: python tools/check_sellersprite_live.py --mcp-key <key> [--asin <测试ASIN>]
（key 仅从命令行参数读取，严禁硬编码进源码/git）
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamable_http_client  # noqa: E402

from app.core.call_log import CallLog  # noqa: E402
from app.core.mcp_client import MCPClient  # noqa: E402
from app.core.rate_limiter import RateLimiter  # noqa: E402


async def _list_tools(url: str) -> int:
    async with streamable_http_client(url, terminate_on_close=False) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return len(tools.tools)


async def main(url: str, asin: str) -> None:
    print("1) 连接与授权（list_tools）…", flush=True)
    try:
        count = await _list_tools(url)
        print(f"   结果: 成功！发现 {count} 个工具", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"   失败: {exc}", flush=True)
        return

    print("2) 最小业务调用 traffic_extend（1 ASIN, size=5, 当前月）…", flush=True)
    rl = RateLimiter(max_calls=8, window_seconds=60.0, min_interval=7.5)
    client = MCPClient(url, rl, CallLog(Path("tests/.tmp_mcp_check_calllog.json")),
                       on_event=None, rate_limit_retry_wait=0.0)
    try:
        data = await client.traffic_extend("US", [asin], page=1, size=5,
                                           query_type=2)
        items = (data.get("data") or {}).get("items") or []
        total = (data.get("data") or {}).get("total")
        print(f"   结果: 成功！message={data.get('message')} total={total} 返回词数={len(items)}",
              flush=True)
        print(f"   样例: {[i.get('keyword') for i in items[:5]]}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"   失败: {exc}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcp-key", required=True)
    ap.add_argument("--asin", default="B0F8JKNNT7")
    args = ap.parse_args()
    url = f"https://mcp.sellersprite.com/mcp?secret-key={args.mcp_key}"
    asyncio.run(main(url, args.asin))
