# -*- coding: utf-8 -*-
"""配置与凭据测试：settings 读写、密钥走凭据管理器不落盘。"""
import json

import pytest

from app.core.config import Settings

# 测试用独立 app_dir，不污染真实配置
TEST_APP_DIR = "tests/.tmp_settings"


@pytest.fixture()
def settings(tmp_path):
    s = Settings(app_dir=tmp_path / "app",
                 cred_prefix="SellerSpriteKeywordAppTest")  # 隔离前缀，防污染真实凭据
    yield s
    # 测试后清理防止串扰
    s.credentials.delete("mcp_secret_key")
    s.credentials.delete("llm_api_key")


def test_defaults(settings):
    assert settings.max_asins_per_group == 20
    assert settings.window_max_calls == 8
    assert settings.mcp_url == "https://mcp.sellersprite.com/mcp"
    assert settings.keyword_pool_pages == 3


def test_save_load_roundtrip(settings, tmp_path):
    settings.llm_model = "deepseek-chat-test"
    settings.workspace_dir = str(tmp_path / "ws")
    settings.save()

    s2 = Settings(app_dir=tmp_path / "app")
    assert s2.llm_model == "deepseek-chat-test"
    assert s2.workspace_dir == str(tmp_path / "ws")


def test_secrets_not_in_settings_file(settings, tmp_path):
    settings.mcp_secret_key = "SECRET_MCP_123"
    settings.llm_api_key = "SECRET_LLM_456"
    settings.save()

    raw = (tmp_path / "app" / "settings.json").read_text(encoding="utf-8")
    assert "SECRET_MCP_123" not in raw
    assert "SECRET_LLM_456" not in raw


def test_credential_roundtrip(settings):
    settings.mcp_secret_key = "KEY_A"
    settings.llm_api_key = "KEY_B"
    assert settings.mcp_secret_key == "KEY_A"
    assert settings.llm_api_key == "KEY_B"


def test_credential_delete(settings):
    settings.mcp_secret_key = "KEY_C"
    assert settings.mcp_secret_key == "KEY_C"
    settings.credentials.delete("mcp_secret_key")
    assert settings.mcp_secret_key == ""


def test_mcp_endpoint_build(settings):
    settings.mcp_url = "https://mcp.sellersprite.com/mcp"
    settings.mcp_secret_key = "abc123"
    assert settings.mcp_endpoint == "https://mcp.sellersprite.com/mcp?secret-key=abc123"


def test_mcp_endpoint_url_encoded(settings):
    """secret-key 含 URL 保留字符时必须编码（防破坏/截断）。"""
    settings.mcp_url = "https://mcp.sellersprite.com/mcp"
    settings.mcp_secret_key = "a&b#c+d/e"
    endpoint = settings.mcp_endpoint
    assert "a%26b%23c%2Bd%2Fe" in endpoint
    assert endpoint == "https://mcp.sellersprite.com/mcp?secret-key=a%26b%23c%2Bd%2Fe"


def test_has_credentials(settings):
    assert not settings.has_mcp_credentials()
    settings.mcp_secret_key = "x"
    assert settings.has_mcp_credentials()
