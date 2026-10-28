# -*- coding: utf-8 -*-
"""调用日志测试：in_progress → 原位补全。"""
import json

from app.core.call_log import CallLog


def test_start_and_finish(tmp_path):
    log = CallLog(tmp_path / "call_log.json")
    seq = log.start_call("traffic_extend", "US batch 1 (20 asins)",
                         planned_total=33, hard_cap=35)
    assert seq == 1
    data = json.loads((tmp_path / "call_log.json").read_text(encoding="utf-8"))
    assert data["calls"][0]["status"] == "in_progress"
    assert data["planned_total"] == 33

    log.finish_call(seq, success=True, returned=50, truncated=False)
    data = json.loads((tmp_path / "call_log.json").read_text(encoding="utf-8"))
    assert data["calls"][0]["status"] == "success"
    assert data["calls"][0]["returned"] == 50
    assert data["actual_total"] == 1


def test_multiple_calls_seq_increments(tmp_path):
    log = CallLog(tmp_path / "call_log.json")
    s1 = log.start_call("traffic_extend", "p1")
    s2 = log.start_call("traffic_extend", "p2")
    assert s1 == 1 and s2 == 2
    log.finish_call(s1, success=True)
    log.finish_call(s2, success=False, error="临时错误")
    summary = log.summary()
    assert summary["success_count"] == 1
    assert len(summary["failed"]) == 1


def test_failed_call_with_error(tmp_path):
    log = CallLog(tmp_path / "call_log.json")
    seq = log.start_call("traffic_keyword", "US asin B0X p1")
    log.finish_call(seq, success=False, error="ERROR_UNAUTHORIZED")
    data = json.loads((tmp_path / "call_log.json").read_text(encoding="utf-8"))
    assert data["calls"][0]["error"] == "ERROR_UNAUTHORIZED"
    assert data["calls"][0]["status"] == "failed"


def test_missing_file_returns_empty(tmp_path):
    log = CallLog(tmp_path / "nope.json")
    assert log.load() == {"calls": []}
    assert log.summary()["actual_total"] == 0
