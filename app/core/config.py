# -*- coding: utf-8 -*-
"""应用配置：非敏感设置存 settings.json，密钥只进 Windows 凭据管理器。

分发版设计约束（需求 4）：程序单独登记 API 和 MCP Key；
settings.json 永不写入任何密钥，密钥仅存 Windows 凭据管理器。
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

APP_NAME = "SellerSprite关键词调研"
CRED_PREFIX = "SellerSpriteKeywordApp"

# 测试/诊断用前缀注入：GUI 测试不得写真实凭据管理器（防泄漏；实测 TMP key 污染过生产）
_DEFAULT_CRED_PREFIX = CRED_PREFIX

DEFAULT_MCP_URL = "https://mcp.sellersprite.com/mcp"
DEFAULT_LLM_BASE_URL = "https://api.deepseek.com"
# 当前 DeepSeek API 仅支持 V4 系列（/models 实测：deepseek-v4-flash / -pro / -vision-exp）；
# 旧别名 deepseek-chat 已停用，实名默认 `deepseek-v4-flash`（冒烟 73 项验收模型）
DEFAULT_LLM_MODEL = "deepseek-v4-flash"
DEFAULT_LLM_MODE = "auto"  # auto | responses | chat
# 官方输出上限 384K；关闭思考后输出预算全归正文，16384 留足余量
DEFAULT_LLM_MAX_TOKENS = 16384


def default_workspace_dir() -> str:
    docs = Path(os.environ.get("USERPROFILE") or Path.home())
    return str(docs / "Documents" / "SellerSprite关键词调研")


class CredentialStore:
    """Windows 凭据管理器封装（win32cred），不可用时降级为内存态（不落盘）。

    写入/读取失败时**不静默**：仅目标不存在（ERROR_NOT_FOUND，winerror 1168）
    返回 None；其他异常向上传播，由 GUI 通知用户凭据保存失败。
    cred_prefix 可注入（测试必须使用隔离前缀，避免污染真实凭据管理器）。
    """

    def __init__(self, cred_prefix: str | None = None) -> None:
        self._win32cred = None
        self._memory: dict[str, str] = {}
        self.cred_prefix = cred_prefix or _DEFAULT_CRED_PREFIX
        try:
            import win32cred  # type: ignore

            self._win32cred = win32cred
        except Exception:
            self._win32cred = None

    def _target(self, name: str) -> str:
        return f"{self.cred_prefix}/{name}"

    def save(self, name: str, value: str) -> None:
        if self._win32cred is None:
            self._memory[name] = value
            return
        cred = {
            "Type": self._win32cred.CRED_TYPE_GENERIC,
            "TargetName": self._target(name),
            "UserName": "app",
            "CredentialBlob": value,  # win32cred 期望 str（Unicode）
            "Persist": self._win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }
        self._win32cred.CredWrite(cred, 0)  # 失败抛错，不静默

    def load(self, name: str) -> str | None:
        if self._win32cred is None:
            return self._memory.get(name)
        try:
            cred = self._win32cred.CredRead(self._target(name),
                                            self._win32cred.CRED_TYPE_GENERIC)
        except Exception as exc:  # noqa: BLE001
            winerror = getattr(exc, "winerror", None)
            if winerror == 1168:  # ERROR_NOT_FOUND：目标不存在
                return None
            raise
        blob = cred.get("CredentialBlob")
        if blob is None:
            return None
        if isinstance(blob, bytes):
            # CredWrite 以 str 写入时按 UTF-16 宽字符存储
            return blob.decode("utf-16-le", errors="replace").rstrip("\x00")
        return str(blob)

    def delete(self, name: str) -> None:
        if self._win32cred is None:
            self._memory.pop(name, None)
            return
        try:
            self._win32cred.CredDelete(self._target(name), self._win32cred.CRED_TYPE_GENERIC, 0)
        except Exception:
            pass

    def available(self) -> bool:
        return self._win32cred is not None


class Settings:
    """设置：settings.json 只存非敏感字段；两个密钥走 CredentialStore。"""

    KEYS = ("mcp_secret_key", "llm_api_key")

    def __init__(self, app_dir: Path | None = None,
                 cred_prefix: str | None = None) -> None:
        self._lock = threading.Lock()
        self.app_dir = Path(app_dir) if app_dir else Path(__file__).resolve().parents[2]
        self.settings_path = self.app_dir / "settings.json"
        self.credentials = CredentialStore(cred_prefix=cred_prefix)
        # 非敏感字段
        self.workspace_dir: str = default_workspace_dir()
        self.mcp_url: str = DEFAULT_MCP_URL
        self.llm_base_url: str = DEFAULT_LLM_BASE_URL
        self.llm_model: str = DEFAULT_LLM_MODEL
        self.llm_mode: str = DEFAULT_LLM_MODE
        self.llm_temperature: float = 0.2
        self.llm_max_tokens: int = DEFAULT_LLM_MAX_TOKENS
        self.llm_request_timeout: float = 120.0
        self.window_max_calls: int = 8
        self.window_seconds: float = 60.0
        self.min_call_interval: float = 7.5
        self.max_asins_per_group: int = 20
        self.keyword_pool_pages: int = 3
        self.load()

    # ---------- 持久化 ----------
    def load(self) -> None:
        with self._lock:
            if not self.settings_path.exists():
                return
            try:
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            except Exception:
                return
            for key in (
                "workspace_dir", "mcp_url", "llm_base_url", "llm_model", "llm_mode",
                "llm_temperature", "llm_max_tokens", "llm_request_timeout",
                "window_max_calls", "window_seconds", "min_call_interval",
                "max_asins_per_group", "keyword_pool_pages",
            ):
                if key in data:
                    setattr(self, key, data[key])

    def save(self) -> None:
        with self._lock:
            data = {
                "workspace_dir": self.workspace_dir,
                "mcp_url": self.mcp_url,
                "llm_base_url": self.llm_base_url,
                "llm_model": self.llm_model,
                "llm_mode": self.llm_mode,
                "llm_temperature": self.llm_temperature,
                "llm_max_tokens": self.llm_max_tokens,
                "llm_request_timeout": self.llm_request_timeout,
                "window_max_calls": self.window_max_calls,
                "window_seconds": self.window_seconds,
                "min_call_interval": self.min_call_interval,
                "max_asins_per_group": self.max_asins_per_group,
                "keyword_pool_pages": self.keyword_pool_pages,
            }
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    # ---------- 密钥 ----------
    @property
    def mcp_secret_key(self) -> str:
        return self.credentials.load("mcp_secret_key") or ""

    @mcp_secret_key.setter
    def mcp_secret_key(self, value: str) -> None:
        self.credentials.save("mcp_secret_key", value)

    @property
    def llm_api_key(self) -> str:
        return self.credentials.load("llm_api_key") or ""

    @llm_api_key.setter
    def llm_api_key(self, value: str) -> None:
        self.credentials.save("llm_api_key", value)

    @property
    def mcp_endpoint(self) -> str:
        """完整 MCP 端点 URL：地址 + 经 URL 编码的 secret-key 查询参数。"""
        from urllib.parse import quote

        key = quote(self.mcp_secret_key, safe="")
        base = self.mcp_url.rstrip("/")
        if not key:
            return base
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}secret-key={key}"

    def has_mcp_credentials(self) -> bool:
        return bool(self.mcp_secret_key)

    def has_llm_credentials(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)
