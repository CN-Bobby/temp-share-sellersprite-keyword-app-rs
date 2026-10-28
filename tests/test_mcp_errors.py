# -*- coding: utf-8 -*-
"""MCP 业务错误识别与限流重试测试（实测：限流 message 曾被当作成功落盘，导致误导性失败）。"""
import asyncio

import pytest

from app.core.call_log import CallLog
from app.core.mcp_client import MCPClient, MCPError
from app.core.rate_limiter import RateLimiter

_raise_business_error = MCPClient._raise_business_error


def _client(with_limiter=True, wait=0.0) -> MCPClient:
    limiter = RateLimiter(max_calls=1000, window_seconds=60.0, min_interval=0.0)
    return MCPClient("fake://endpoint", limiter, CallLog("tests/.tmp_mcp_err_calllog.json"),
                     rate_limit_retry_wait=wait, max_temp_retries=1)


class _NoLogCallLog:
    def start_call(self, *a, **k):
        return 1

    def finish_call(self, *a, **k):
        pass


def test_business_error_raises_rate_limited():
    """code=OK + message=接口访问次数已达上限 → 拦截为 rate_limited 错误。"""
    with pytest.raises(MCPError) as ei:
        _raise_business_error({"code": "OK", "message": "接口访问次数已达上限",
                               "data": {"items": []}})
    assert ei.value.rate_limited is True
    assert ei.value.retryable is True


def test_business_error_unauthorized():
    with pytest.raises(MCPError) as ei:
        _raise_business_error({"code": "ERROR_UNAUTHORIZED", "message": "授权或额度拒绝"})
    assert ei.value.unauthorized is True


def test_normal_response_passes():
    data = {"code": "OK", "message": "成功", "data": {"items": [{"keyword": "x"}]}}
    _raise_business_error(data)  # 不应抛


def test_rate_limited_call_retries_then_succeeds():
    """限流错误自动重试：第一次限流、第二次成功，重试等待参数可控。"""

    class FakeMCP(MCPClient):
        def __init__(self):
            super().__init__("fake://endpoint",
                             RateLimiter(1000, 60.0, 0.0),
                             _NoLogCallLog(), rate_limit_retry_wait=0.0)
            self.calls = 0

        async def _call_once(self, tool, arguments):
            self.calls += 1
            if self.calls == 1:
                # 模拟"服务端限流"被 _raise_business_error 拦截后的结果
                raise MCPError("服务端限流: 接口访问次数已达上限",
                               retryable=True, rate_limited=True)
            return {"code": "OK", "message": "成功",
                    "data": {"items": [{"keyword": "泳衣", "trafficPercentage": 0.1}]}}

    client = FakeMCP()
    events = []
    client.on_event = events.append
    result = asyncio.run(client.call("traffic_extend", {"request": {}}, "scope"))
    assert client.calls == 2
    assert result["data"]["items"][0]["keyword"] == "泳衣"
    wait_events = [e for e in events if e.get("kind") == "rate_limit_wait"
                   and e.get("source") == "server"]
    assert len(wait_events) == 1
