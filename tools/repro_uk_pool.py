# -*- coding: utf-8 -*-
"""复现 UK 2608 词池为空：采集层诊断。

只复现 采集层（反查 traffic_extend 3 页 + 逐 ASIN traffic_keyword 1 页），
落盘原始响应到 --workdir/raw，打印 code/items 统计，不跑 LLM。
用法: python tools/repro_uk_pool.py --marketplace UK --month 202608 --asins A1,A2,... [--workdir tests/.tmp_repro]
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.core.mcp_client import MCPClient  # noqa: E402


def load_input(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    groups = d.get("groups") or []
    for g in groups:
        mp = g.get("marketplace", "").upper()
        asins = [a.strip() for a in (g.get("asins") or []) if a.strip()]
        if asins:
            return mp, asins, g.get("month") or g.get("snapshot_month")
    raise SystemExit("input.json 无有效 groups")


def summarize(payload, label):
    """递归统计 items 与 code。"""
    code = payload.get("code") if isinstance(payload, dict) else None
    msg = payload.get("message") if isinstance(payload, dict) else None

    def find_items(obj):
        if isinstance(obj, dict):
            items = obj.get("items")
            if isinstance(items, list):
                return items
            for v in obj.values():
                r = find_items(v)
                if r is not None:
                    return r
        elif isinstance(obj, list):
            for v in obj:
                r = find_items(v)
                if r is not None:
                    return r
        return None

    items = find_items(payload)
    n = len(items) if items is not None else -1
    kw0 = ""
    if items:
        first = items[0]
        kw0 = first.get("keyword") or first.get("searchTerm") or ""
    print(f"  {label}: code={code} msg={msg} items={n} 首词={kw0[:40]}")
    return n


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--marketplace", default=None)
    ap.add_argument("--month", default=None)
    ap.add_argument("--asins", default=None)
    ap.add_argument("--workdir", default="tests/.tmp_repro")
    ap.add_argument("--mcp-key", default=None)
    args = ap.parse_args()

    settings = Settings(app_dir=Path("."))  # 非敏感默认；密钥走 CredentialStore
    workdir = Path(args.workdir)
    raw_dir = workdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    mcp_key = args.mcp_key or settings.credentials.load("mcp_secret_key")
    if not mcp_key:
        raise SystemExit("未找到 MCP key（--mcp-key 或凭据管理器 mcp_secret_key）")
    url = f"{settings.mcp_url}?secret-key={mcp_key}"

    mp = (args.marketplace or "UK").upper()
    month = args.month or "202608"
    asins = [a.strip() for a in (args.asins or "").split(",") if a.strip()]
    if not asins:
        # 优先从 input.json 读取
        inp = workdir / "input.json"
        if inp.exists():
            mp, asins, month = load_input(inp)
            print(f"从 input.json 读取: {mp} {month} {len(asins)} ASIN")
        else:
            raise SystemExit("--asins 或 workdir/input.json 必填")

    print(f"=== 复现 {mp} {month} {len(asins)} ASIN ===")
    from app.core.mcp_client import CallLog, MCPClient, RateLimiter
    rl = RateLimiter(settings.window_max_calls, settings.window_seconds,
                     settings.min_call_interval)
    call_log = CallLog(workdir / "call_log.json")
    mcp = MCPClient(url, rl, call_log,
                    request_timeout=settings.llm_request_timeout,
                    rate_limit_retry_wait=60.0)
    print("--- 反查 traffic_extend 3 页（多 ASIN 批次） ---")
    totals = []
    for page in range(1, 4):
        fname = f"traffic_batch_1_p{page}.json"
        data = await mcp.traffic_extend(mp, asins, page, size=50,
                                        history_date=month)
        meta = {"marketplace": mp, "batch": 1, "page": page,
                "asins": asins, "called_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        if isinstance(data, dict):
            data = {**data, "_meta": {**data.get("_meta", {}), **meta}}
        (raw_dir / fname).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
        totals.append(summarize(data, f"p{page}"))
        await asyncio.sleep(0)

    print("--- 逐 ASIN traffic_keyword 当前前100词 ---")
    for asin in asins:
        fname = f"traffic_keyword_current_{asin}_p1.json"
        data = await mcp.traffic_keyword(mp, asin, page=1, size=100)
        meta = {"asin": asin, "marketplace": mp, "page": 1, "page_size": 100,
                "snapshot_type": "current",
                "observed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        if isinstance(data, dict):
            data = {**data, "_meta": {**data.get("_meta", {}), **meta}}
        (raw_dir / fname).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
        summarize(data, f"{asin}")
        await asyncio.sleep(0)

    print(f"=== 完成：原始响应已落盘 {raw_dir} ===")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
