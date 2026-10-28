# -*- coding: utf-8 -*-
"""开发工具：验证 LLM 凭据与协议模式（Responses / Chat Completions）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.llm_client import LLMClient  # noqa: E402

if __name__ == "__main__":
    client = LLMClient(sys.argv[1], sys.argv[2], sys.argv[3], mode="auto",
                       temperature=0.2, max_tokens=4096)
    info = client.test_connection()
    print(info)
