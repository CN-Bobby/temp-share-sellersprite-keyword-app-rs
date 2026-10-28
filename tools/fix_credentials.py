# -*- coding: utf-8 -*-
"""修复真实凭据管理器：删除测试残留假 llm_api_key，写回真实 key。

用法: python tools/fix_credentials.py --llm-key <真实key> [--mcp-key <真实key>]
（key 仅从命令行参数读取，严禁硬编码进源码/git）
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import CredentialStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm-key", required=True)
    ap.add_argument("--mcp-key", default=None)
    args = ap.parse_args()

    creds = CredentialStore()
    llm_cur = creds.load("llm_api_key") or ""
    print(f"修复前 llm_api_key: {llm_cur[:8]!r}（长度 {len(llm_cur)}）")
    if llm_cur != args.llm_key:
        creds.save("llm_api_key", args.llm_key)
        print("已写回真实 llm_api_key")
    if args.mcp_key:
        mcp_cur = creds.load("mcp_secret_key") or ""
        if mcp_cur != args.mcp_key:
            creds.save("mcp_secret_key", args.mcp_key)
            print("已写回真实 mcp_secret_key")
    print(f"修复后 llm_api_key 长度: {len(creds.load('llm_api_key') or '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
