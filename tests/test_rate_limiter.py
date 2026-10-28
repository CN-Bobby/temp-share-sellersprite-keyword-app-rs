# -*- coding: utf-8 -*-
"""限流器测试：8 次/滚动 60 秒，相邻 ≥7.5 秒。"""
import time

import pytest

from app.core.rate_limiter import RateLimiter


def test_allows_up_to_max_calls_immediately():
    rl = RateLimiter(max_calls=8, window_seconds=60.0, min_interval=0)
    for _ in range(8):
        assert rl.next_available_in() == 0
        rl.record_call()


def test_ninth_call_must_wait():
    rl = RateLimiter(max_calls=8, window_seconds=60.0, min_interval=0)
    for _ in range(8):
        rl.record_call()
    wait = rl.next_available_in()
    assert wait > 0
    # 窗口是 60 秒：最早一次在 ~0s，8 次后 now≈0，需等 ~60s
    assert wait <= 60.0 + 1e-6


def test_window_slides():
    rl = RateLimiter(max_calls=2, window_seconds=0.2, min_interval=0)
    rl.record_call()
    rl.record_call()
    assert rl.next_available_in() > 0
    time.sleep(0.25)
    assert rl.next_available_in() == 0


def test_min_interval_enforced():
    rl = RateLimiter(max_calls=100, window_seconds=60.0, min_interval=7.5)
    rl.record_call()
    wait = rl.next_available_in()
    assert 7.4 <= wait <= 7.6


def test_calls_in_window():
    rl = RateLimiter(max_calls=8, window_seconds=60.0, min_interval=0)
    assert rl.calls_in_window == 0
    rl.record_call()
    rl.record_call()
    assert rl.calls_in_window == 2


def test_wait_until_allowed_blocks_and_reports():
    rl = RateLimiter(max_calls=1, window_seconds=0.15, min_interval=0)
    rl.record_call()
    waits = []
    rl.wait_until_allowed(on_wait=lambda w: waits.append(w))
    assert len(waits) >= 1
    assert waits[0] > 0


def test_invalid_params():
    with pytest.raises(ValueError):
        RateLimiter(max_calls=0)
    with pytest.raises(ValueError):
        RateLimiter(min_interval=-1)
