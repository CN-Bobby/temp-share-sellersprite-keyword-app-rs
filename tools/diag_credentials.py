# -*- coding: utf-8 -*-
"""只读诊断：读取（掩码显示）本地凭据管理器中的应用凭据，与命令行提供的真实 key 对比。

用法: python tools/diag_credentials.py --llm-key <真实key> [--mcp-key <真实key>]
（key 仅从命令行参数读取，严禁硬编码进源码/git）
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import CredentialStore  # noqa: E402


def mask(v: str) -> str:
    if not v:
        return "(空)"
    return v[:5] + "…" + v[-4:] if len(v) > 10 else "…" + v[-3:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm-key", required=True)
    ap.add_argument("--mcp-key", default=None)
    args = ap.parse_args()

    creds = CredentialStore()
    print("win32cred 可用:", creds.available())
    pairs = [("llm_api_key", args.llm_key)]
    if args.mcp_key:
        pairs.append(("mcp_secret_key", args.mcp_key))
    for name, real in pairs:
        v = creds.load(name)
        ok = (v == real)
        print(f"{name}: 长度={len(v) if v else 0} 值={mask(v or '')} 匹配真实key={'是' if ok else '否'}",
              flush=True)
        if v and not ok:
            print(f"  → 差异: 期望长度{len(real)} 实际长度{len(v)}；前8字符: {v[:8]!r}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
