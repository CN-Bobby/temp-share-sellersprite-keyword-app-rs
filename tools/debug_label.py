# -*- coding: utf-8 -*-
"""调试：真实 LLM 标注请求，检查 status/finish_reason 与输出长度。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.llm_client import LLMClient  # noqa: E402
from app.core.llm_label import SYSTEM_PROMPT, build_batch_prompt  # noqa: E402

if __name__ == "__main__":
    max_tokens = int(sys.argv[4]) if len(sys.argv) > 4 else 8192
    client = LLMClient(sys.argv[1], sys.argv[2], sys.argv[3], mode="auto",
                       temperature=0.2, max_tokens=max_tokens)
    kw = []
    if len(sys.argv) > 5:
        # 从真实 keyword_labeled.json 读前 N 词
        import json as _json

        data = _json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
        n = int(sys.argv[6]) if len(sys.argv) > 6 else 20
        for k in data["keywords"][:n]:
            kw.append({
                "keyword": k.get("keyword"),
                "keywordCn": k.get("keywordCn"),
                "searches": k.get("searches"),
                "family_guess": k.get("family_guess"),
                "is_brand_candidate": bool(k.get("is_brand_candidate")),
                "marketplace": "US",
            })
    else:
        kw = [
            {"keyword": "lunch box", "keywordCn": "午餐盒", "searches": 624525,
             "family_guess": "lunch box", "is_brand_candidate": False, "marketplace": "US"},
            {"keyword": "lunch box for women", "keywordCn": "女士午餐盒", "searches": 80000,
             "family_guess": "lunch box", "is_brand_candidate": False, "marketplace": "US"},
            {"keyword": "insulated lunch bags for women", "keywordCn": "女士保温午餐袋", "searches": 30000,
             "family_guess": "lunch bag", "is_brand_candidate": False, "marketplace": "US"},
            {"keyword": "kids lunch box", "keywordCn": "儿童午餐盒", "searches": 200000,
             "family_guess": "lunch box", "is_brand_candidate": False, "marketplace": "US"},
            {"keyword": "bentgo lunch box", "keywordCn": "Bentgo午餐盒", "searches": 50000,
             "family_guess": "lunch box", "is_brand_candidate": True, "marketplace": "US"},
        ]
        for i in range(15):
            extra = {
                "keyword": f"mock keyword {i} for testing", "keywordCn": f"模拟关键词{i}",
                "searches": 10000 + i, "family_guess": "mock", "is_brand_candidate": False,
                "marketplace": "US",
            }
            kw.append(extra)
    print(f"批次 {len(kw)} 词，max_tokens={max_tokens}", flush=True)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_batch_prompt(kw)},
    ]
    result = client.complete(messages, json_mode=True)
    print("mode:", result.mode)
    print("finish_reason:", result.finish_reason)
    print("model:", result.model)
    print("reasoning_tokens:", result.reasoning_tokens)
    print("text_len:", len(result.text))
    print("text_head:", result.text[:300])
    print("text_tail:", result.text[-200:])
    try:
        data = json.loads(result.text)
        print("parsed rows:", len(data))
    except Exception as exc:
        print("parse error:", exc)
