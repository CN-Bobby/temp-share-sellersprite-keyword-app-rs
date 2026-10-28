# -*- coding: utf-8 -*-
"""开发工具：连接 SellerSprite MCP，dump 关键工具 schema 到 tests/fixtures/mcp_tools_schema.json。
用法: python tools/dump_mcp_schema.py <secret-key>
"""
import asyncio
import json
import sys
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

WANT = {"traffic_extend", "product_node", "product_research",
        "traffic_keyword", "aba_research_trend", "traffic_keyword_stat"}


async def main(secret_key: str) -> None:
    url = f"https://mcp.sellersprite.com/mcp?secret-key={secret_key}"
    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            out = {}
            for t in tools.tools:
                if t.name in WANT:
                    sch = t.input_schema or {}
                    req = (sch.get("properties") or {}).get("request", {})
                    out[t.name] = {
                        "top_required": sch.get("required"),
                        "description": t.description,
                        "request_required": req.get("required"),
                        "request_fields": {
                            k: v for k, v in (req.get("properties") or {}).items()
                        },
                    }
            with open("tests/fixtures/mcp_tools_schema.json", "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=1)
            for name, info in out.items():
                print("====", name, "| desc:", (info["description"] or "")[:80])
                print("  request required:", info["request_required"])
                for k, v in info["request_fields"].items():
                    d = (v.get("description") or "").replace("\n", " ")[:70]
                    print(f"    {k}: {v.get('type')} | {d}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
