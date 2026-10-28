# -*- coding: utf-8 -*-
"""调试：真实 market 段请求，测输出 token 与截断。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.llm_analysis import LLMAnalyzer  # noqa: E402
from app.core.llm_client import LLMClient  # noqa: E402

if __name__ == "__main__":
    base, key, model = sys.argv[1], sys.argv[2], sys.argv[3]
    task = Path(sys.argv[4])
    labeled = json.loads((task / "cache" / "keyword_labeled.json").read_text(encoding="utf-8"))
    trend = json.loads((task / "cache" / "trend_analysis.json").read_text(encoding="utf-8"))
    matrix = json.loads((task / "cache" / "asin_keyword_matrix.json").read_text(encoding="utf-8"))
    ctx = {
        "input": {"marketplace": "US", "options": {"data_month": "202606"}},
        "mode": "M2",
        "labeled": labeled,
        "trend_analysis": trend,
        "matrix": matrix,
    }
    client = LLMClient(base, key, model, mode=sys.argv[6] if len(sys.argv) > 6 else "auto",
                       temperature=0.2,
                       max_tokens=int(sys.argv[5]) if len(sys.argv) > 5 else 8192)
    analyzer = LLMAnalyzer(client)
    segment = sys.argv[7] if len(sys.argv) > 7 else "demand"
    messages = analyzer._segment_prompt(segment, ctx)
    print("输入 tokens 估算：", sum(len(m["content"]) for m in messages) // 3, flush=True)
    result = client.complete(messages, json_mode=True)
    print("finish_reason:", result.finish_reason, flush=True)
    print("text_len:", len(result.text), flush=True)
    try:
        data = result.json()
        print("demand_map:", len(data.get("demand_map", [])), flush=True)
        print("traffic_traps:", len(data.get("traffic_traps", [])), flush=True)
        print("quadrant items:", len((data.get("quadrant") or {}).get("items", [])), flush=True)
        print("opportunity_matrix:", len(data.get("opportunity_matrix", [])), flush=True)
    except Exception as exc:
        print("parse error:", exc, flush=True)
        print("tail:", result.text[-300:], flush=True)
