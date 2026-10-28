# -*- coding: utf-8 -*-
"""合入客户端 0829 引擎修复的针对性回归：
1) 词族变体映射（normalize_hypothesis_keywords / validate_analysis 词族 WARN 通道）
2) validate_report 分页正则 \b 边界（ASIN 含 P4 不误判第 4 页）
"""
import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "app" / "engine" / "scripts"


def _load(name: str) -> dict:
    """runpy 加载引擎脚本（不触发 main），返回其全局命名空间。"""
    return runpy.run_path(str(SCRIPTS / name), run_name=f"_mod_{name[:-3]}")


def test_variant_mapping_functions():
    at = _load("analyze_trends.py")
    nk = at["normalize_key"]
    fg = at["family_guess"]
    assert nk("Girls Swimsuits  size 10-12") == "girls swimsuits size 10-12"
    assert fg(nk("girls swimsuit")) == fg(nk("girls swimsuits"))
    # 词族唯一最优映射：查询单数变体 → 命中词池复数精确词
    candidates = ["girls swimsuits size 10-12", "girls swimsuit cover up"]
    best = at["best_family_match"](nk("girls swimsuit size 10-12"), candidates)
    assert best == "girls swimsuits size 10-12"


def test_normalize_hypothesis_keywords_rewrites_analysis(tmp_path):
    """analyze_trends 的归一化：变体 source_keywords 写回词池精确词（幂等）。"""
    at = _load("analyze_trends.py")
    cache = tmp_path / "cache"
    cache.mkdir()
    labeled = {"keywords": [
        {"keyword": "girls swimsuits size 10-12"},
        {"keyword": "boys swim trunks"},
    ]}
    analysis = {"product_hypotheses": [
        {"source_keywords": ["girls swimsuit size 10-12", "boys swim trunks"],
         "evidence": {"searches": 100}, "confidence": "mid",
         "inference_level": "hypothesis",
         "product_response": "假设", "validation_needed": "x"},
    ]}
    (cache / "keyword_labeled.json").write_text(
        json.dumps(labeled, ensure_ascii=False), encoding="utf-8")
    (cache / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False), encoding="utf-8")

    at["normalize_hypothesis_keywords"](str(tmp_path))
    out = json.loads((cache / "analysis.json").read_text(encoding="utf-8"))
    sources = out["product_hypotheses"][0]["source_keywords"]
    assert sources[0] == "girls swimsuits size 10-12"  # 变体被替换
    assert sources[1] == "boys swim trunks"  # 精确词保持


def test_validate_analysis_family_warn_channel(tmp_path):
    """validate_analysis：变体经词族唯一匹配 [WARN] 通过，不误杀。"""
    cache = tmp_path / "cache"
    cache.mkdir()
    labeled = {"keywords": [{"keyword": "girls swimsuits size 10-12"}]}
    analysis = {"product_hypotheses": [
        {"source_keywords": ["girls swimsuit size 10-12"],
         "evidence": {"searches": 100}, "confidence": "mid",
         "inference_level": "hypothesis",
         "product_response": "（假设）", "validation_needed": "x"},
    ]}
    (cache / "keyword_labeled.json").write_text(
        json.dumps(labeled, ensure_ascii=False), encoding="utf-8")
    (cache / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate_analysis.py"),
         "--workdir", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8",
             "PYTHONUTF8": "1"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "[WARN]" in proc.stdout
    assert "OK" in proc.stdout  # 产品方向证据验收通过（中文输出按 UTF-8 环境）


def test_validate_analysis_unknown_word_fails_with_detail(tmp_path):
    """无法唯一映射的词保留并 FAIL，且消息带首条明细。"""
    cache = tmp_path / "cache"
    cache.mkdir()
    labeled = {"keywords": [{"keyword": "girls swimsuits size 10-12"}]}
    analysis = {"product_hypotheses": [
        {"source_keywords": ["totally unknown keyword"],
         "evidence": {"searches": 100}, "confidence": "mid",
         "inference_level": "hypothesis",
         "product_response": "（假设）", "validation_needed": "x"},
    ]}
    (cache / "keyword_labeled.json").write_text(
        json.dumps(labeled, ensure_ascii=False), encoding="utf-8")
    (cache / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate_analysis.py"),
         "--workdir", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8",
             "PYTHONUTF8": "1"})
    assert proc.returncode != 0
    assert "[FAIL]" in proc.stdout
    assert "totally unknown keyword" in proc.stdout


def test_validate_report_word_boundary_regexes_present():
    """validate_report 三处分页正则均带 \\b 词边界（合入完整性检查）。"""
    text = (SCRIPTS / "validate_report.py").read_text(encoding="utf-8")
    assert r"\b(?:page|p)\s*=?\s*[2-9]" in text
    assert r"\b(?:page|p)\s*=?\s*(\d+)" in text
    assert r"\b(?:page|p)\s*=?\s*1(?:\D|$)" in text


def test_word_boundary_no_false_positive_on_asin_p4():
    """ASIN 含 P4（B0FVD8TP4R）不再被误判为第 4 页调用。"""
    import re

    scope = "US current asin B0FVD8TP4R page=1"
    false_positive_old = re.search(r"(?:page|p)\s*=?\s*[2-9]", scope, re.I)
    assert false_positive_old is not None  # 旧正则确实误判（说明修复必要）
    fixed = re.search(r"\b(?:page|p)\s*=?\s*[2-9]", scope, re.I)
    assert fixed is None  # 新正则不再误判
