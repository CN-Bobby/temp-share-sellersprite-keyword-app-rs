# -*- coding: utf-8 -*-
"""确定性 FakeMCP：从 tests/fixtures/mcp_responses 读取历史真实响应，
复用 MCPClient 的限流/日志/重试逻辑，仅替换网络层。用于离线端到端测试。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.mcp_client import MCPClient


def _slug(keyword: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", keyword.lower()).strip("_")
    return s or "kw"


class FakeMCP(MCPClient):
    def __init__(self, fixtures_dir: str | Path, rate_limiter, call_log,
                 on_event=None) -> None:
        super().__init__("fake://endpoint", rate_limiter, call_log, on_event)
        self.fixtures = Path(fixtures_dir)

    def _read(self, name: str) -> dict:
        path = self.fixtures / name
        if not path.exists():
            raise FileNotFoundError(f"fixture 缺失: {name}（FakeMCP 无法离线应答）")
        return json.loads(path.read_text(encoding="utf-8"))

    async def _call_once(self, tool: str, arguments: dict) -> dict:
        if tool == "traffic_extend":
            req = arguments.get("request", {})
            page = req.get("page", 1)
            # 找到该批次：fixture 里按页码聚合（真实历史为 batch 1）
            return self._read(f"traffic_batch_1_p{page}.json")
        if tool == "traffic_keyword":
            req = arguments.get("request", {})
            asin = req.get("asin", "")
            return self._read(f"traffic_keyword_current_{asin}_p1.json")
        if tool == "aba_research_trend":
            keyword = arguments.get("keyword", "")
            name = f"trend_{_slug(keyword)}.json"
            if (self.fixtures / name).exists():
                return self._read(name)
            return self._synthetic_trend(keyword)
        if tool == "product_node":
            return {"code": "OK", "data": {"nodeIdPath": arguments.get("request", {}).get("nodeIdPath")}}
        if tool == "product_research":
            return {"code": "OK", "data": {"items": []}}
        raise NotImplementedError(f"FakeMCP 未实现工具: {tool}")

    @staticmethod
    def _synthetic_trend(keyword: str) -> dict:
        """生成 24 个月模拟趋势（analyze_trends.py 可解析的格式）。"""
        import datetime as dt

        items = []
        base = 50000 + (hash(keyword) % 900000)
        end = dt.date(2026, 7, 1)
        for i in range(36):
            m = end.month - i - 1
            y = end.year
            while m < 0:
                m += 12
                y -= 1
            month = dt.date(y, m + 1, 1)
            wave = 1 + 0.3 * ((m + 1) % 12 in (6, 7, 8))  # 夏季小高峰
            searches = int(base * wave * (1 + 0.05 * (i % 5)))
            items.append({
                "date": int(dt.datetime(y, m + 1, 1).timestamp() * 1000),
                "rank": max(1, 500 - i * 8),
                "searches": searches,
                "label": f"{y}{m + 1:02d}",
            })
        items.reverse()
        return {"code": "OK", "message": "成功", "data": items}
