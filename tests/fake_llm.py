# -*- coding: utf-8 -*-
"""确定性 FakeLLM：不联网，按规则生成标注/分析输出，用于离线端到端测试。

对外接口与 app.core.llm_client.LLMClient 对齐（complete/test_connection）。
"""
from __future__ import annotations

import json
from typing import Any

from app.core.llm_client import LLMResult


class FakeLLM:
    """按规则响应的 mock。标注请求返回规则标注；分析请求返回固定骨架。"""

    def __init__(self, analysis_overrides: dict | None = None) -> None:
        self.detected_mode = "chat"
        self.calls: list[dict] = []
        self.analysis_overrides = analysis_overrides or {}

    # ---------- 标注 ----------

    def _label_response(self, keywords: list[dict]) -> list[dict]:
        rows = []
        for k in keywords:
            kw = k["keyword"]
            low = kw.lower()
            tags = []
            if any(w in low for w in ("for kids", "for boys", "for girls", " kids", " boys", " girls")):
                tags.append("audience:kids")
            elif any(w in low for w in ("for women", "for men", " womens", " mens", " women", " men")):
                tags.append("audience:adult")
            # 属性标签：保证长尾候选充足（validate_report 期望趋势词数达标）
            if any(w in low for w in ("steel", "plastic", "wood", "glass", "silicone")):
                tags.append("material:mock")
            else:
                tags.append("function:general")
            if not tags:
                # 校验规则：相关度 A 必须有需求标签
                tags.append(f"core_category:{(kw.split()[0] if kw.split() else kw)[:20]}")
            rows.append({
                "keyword": kw,
                "translation_fixed": k.get("keywordCn") or kw,
                "translation_reason": "确定性 mock 翻译",
                "translation_confidence": "high",
                "family": (kw.split()[0] if kw.split() else kw)[:12],
                "demand_tags": tags,
                "relevance": "A" if (k.get("searches") or 0) >= 10000 else "B",
                "relevance_reason": "确定性 mock 相关度",
                "purchase_intent": "高" if (k.get("purchaseRate") or 0) >= 0.03 else "中",
                "is_brand": bool(k.get("is_brand_candidate")),
                "is_noise": False,
                "local_context": "",
            })
        return rows

    # ---------- 分析 ----------

    def _analysis_response(self, keywords: list[dict]) -> dict:
        # 词池固定词（测试夹具 150 词中确定存在），不依赖请求携带的词表
        sample = ["lunch box", "lunch bag", "meal prep containers"]
        return {
            "category_label": "mock品类",
            "demand_map": [{
                "tag": "core_category:mock",
                "kw_count": len(keywords),
                "representative": sample,
                "searches_median": 10000,
                "purchase_rate_median": 0.02,
                "click_conc_median": None,
                "conv_conc_median": None,
                "ppc_median": None,
                "trend_direction": "flat",
                "product_implication": "确定性 mock 需求聚合。",
            }],
            "traffic_traps": [],
            "quadrant": {
                "click_median": 0.1,
                "conv_median": 0.05,
                "items": [
                    {"keyword": "lunch box", "click": 0.1414, "conv": 0.1128,
                     "quadrant": "high-high", "interpretation": "mock 双高"},
                    {"keyword": "lunch bag", "click": 0.082, "conv": 0.041,
                     "quadrant": "low-low", "interpretation": "mock 双低"},
                    {"keyword": "meal prep containers", "click": 0.122, "conv": 0.033,
                     "quadrant": "high-low", "interpretation": "mock 点击高转化低"},
                    {"keyword": "kids backpack", "click": 0.076, "conv": 0.061,
                     "quadrant": "low-high", "interpretation": "mock 转化高"},
                ],
            },
            "opportunity_matrix": [{
                "keyword": sample[0] if sample else "",
                "type": "core",
                "evidence": {"searches": 10000, "relevance": "A"},
                "confidence": "mid",
            }] if sample else [],
            "product_hypotheses": [{
                "demand": "mock 需求",
                "source_keywords": [sample[0]] if sample else [],
                "evidence": {"searches": 10000, "purchase_rate": 0.02},
                "user_problem": "mock 用户问题（推断）",
                "product_form": "mock 形态",
                "material": "",
                "function": "",
                "spec": "",
                "bundle_accessory": "",
                "product_response": "mock 产品响应（假设）",
                "confidence": "mid",
                "inference_level": "hypothesis",
                "validation_needed": "mock 待验证",
            }],
            "sku_structure": {"main_form": "mock", "bundle_demand": "",
                              "real_accessories": [], "fake_accessories": [],
                              "sku_hypothesis": "mock SKU（假设）"},
            "seasonality": {"growth_start_month": "", "peak_months": [],
                            "peak_duration": "", "off_duration": "",
                            "two_year_repeat": False, "timeline_advice": "mock"},
            "lifecycle": {"classification": "mature", "evidence": "mock"},
            "entry_conclusion": {
                "grade": "VALIDATE",
                "answers": {f"q{i}": f"mock 回答 {i}" for i in range(1, 8)},
                "evidence": "mock 证据",
                "limitations": "mock 限制",
            },
            "risk_checklist": {"cannot_prove": ["mock"], "next_validations": ["mock"]},
        }

    # ---------- 对外 ----------

    def complete(self, messages: list[dict], *, max_tokens: int | None = None,
                 json_mode: bool = True) -> LLMResult:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        self.calls.append({"mode": "label" if "关键词列表" in user else "analysis",
                           "chars": len(user)})
        if "关键词列表" in user:
            payload = json.loads(user)
            keywords = payload["关键词列表"]
            text = json.dumps(self._label_response(keywords), ensure_ascii=False)
        else:
            # 分析请求：user 消息 = JSON + 指令文本，截取 JSON 部分解析
            try:
                start = user.find("{")
                end = user.rfind("}")
                payload = json.loads(user[start:end + 1])
                keywords = payload.get("keywords", [])
            except Exception:
                keywords = []
            text = json.dumps(self._analysis_response(keywords), ensure_ascii=False)
        return LLMResult(text, finish_reason="stop", model="fake", mode="chat")

    def test_connection(self) -> dict:
        return {"ok": True, "mode": "chat", "model": "fake", "sample": "正常"}
