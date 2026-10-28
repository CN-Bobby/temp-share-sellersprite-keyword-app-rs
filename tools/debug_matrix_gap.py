# -*- coding: utf-8 -*-
"""诊断：矩阵记录词与关键词总表的匹配情况（交集为空则矩阵空白）。"""
import json
import sys
from pathlib import Path

task = Path(sys.argv[1])
m = json.loads((task / "cache" / "asin_keyword_matrix.json").read_text(encoding="utf-8"))
km = json.loads((task / "cache" / "keyword_master.json").read_text(encoding="utf-8"))

master_raw = {k.get("keyword") for k in km.get("keywords", [])}
master_norm = {k.get("normalized_key") for k in km.get("keywords", [])}

recs = m.get("records", [])
rec_keywords = {r.get("keyword") for r in recs}
print(f"records={len(recs)} / 唯一词={len(rec_keywords)} / 总表词={len(master_raw)}")
print(f"交集(原始keyword): {len(rec_keywords & master_raw)}")
print(f"交集(normalized_key): {len(rec_keywords & master_norm)}")
print("未匹配的矩阵词:", sorted(rec_keywords - master_raw - master_norm)[:12])
print("keywords 空/None:", sum(1 for r in recs if not r.get("keyword")))
