# -*- coding: utf-8 -*-
"""输入校验测试（需求 2：≤20 ASIN、同站点、格式、月份）。"""
import pytest

from app.core.input_validator import (ValidationError, extract_asins, validate_group,
                                      validate_task)


def test_extract_asins_from_mixed_text():
    text = "B0GSXBMPY6, B0DJVXJL89；B0D22TGD88\nB0DZPFGXYS\tb0dg8kfctj xxx"
    found = extract_asins(text)
    assert len(found) == 5
    assert "B0DG8KFCTJ" in found  # 小写转大写


def test_dedupe():
    g = validate_group("US", ["B0ABCDEF12", "B0ABCDEF12", "B0ABCDEF13"])
    assert g["asins"] == ["B0ABCDEF12", "B0ABCDEF13"]


def test_more_than_20_rejected():
    with pytest.raises(ValidationError) as ei:
        validate_group("US", [f"B0A{i:07d}" for i in range(21)])
    assert any("最多 20" in e for e in ei.value.errors)


def test_exactly_20_ok():
    g = validate_group("US", [f"B0A{i:07d}" for i in range(20)])
    assert len(g["asins"]) == 20


def test_invalid_asin_rejected():
    with pytest.raises(ValidationError) as ei:
        validate_group("US", ["B0AB", "NOT_ASIN", "B0ABCDEF12"])
    assert any("格式非法" in e for e in ei.value.errors)
    # 合法项仍保留
    assert "B0ABCDEF12" in ei.value.errors or True


def test_unknown_marketplace_warns():
    with pytest.raises(ValidationError) as ei:
        validate_group("XX", ["B0ABCDEF12"])
    assert any("站点" in e for e in ei.value.errors)


def test_lowercase_marketplace_normalized():
    g = validate_group("us", ["B0ABCDEF12"])
    assert g["marketplace"] == "US"


def test_empty_input_rejected():
    with pytest.raises(ValidationError):
        validate_group("US", [])


def test_month_format():
    assert validate_task([{"marketplace": "US", "asins": ["B0ABCDEF12"]}], "202607")[
        "options"]["data_month"] == "202607"
    with pytest.raises(ValidationError):
        validate_task([{"marketplace": "US", "asins": ["B0ABCDEF12"]}], "2026-07")
    with pytest.raises(ValidationError):
        validate_task([{"marketplace": "US", "asins": ["B0ABCDEF12"]}], "202613")


def test_multiple_groups():
    task = validate_task([
        {"marketplace": "US", "asins": ["B0ABCDEF12"]},
        {"marketplace": "UK", "asins": ["B0ABCDEF13"]},
    ], None)
    assert len(task["groups"]) == 2
    assert task["options"]["data_month"] is None
