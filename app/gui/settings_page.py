# -*- coding: utf-8 -*-
"""设置页：SellerSprite MCP Key 与 LLM API 凭据单独登记（需求 4）。

密钥只进 Windows 凭据管理器，settings.json 不含密钥。
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from app.core.config import Settings


class _TestThread(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, fn) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._fn())
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc))


class SettingsPage(QWidget):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self._threads: list[_TestThread] = []

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        scroll.setWidget(body)
        root.addWidget(scroll)

        # ---------- SellerSprite MCP ----------
        mcp_box = QGroupBox("SellerSprite MCP 凭据")
        mcp_form = QFormLayout(mcp_box)
        self.mcp_url_edit = QLineEdit(self.settings.mcp_url)
        self.mcp_key_edit = QLineEdit(self.settings.mcp_secret_key)
        self.mcp_key_edit.setEchoMode(QLineEdit.Password)
        mcp_form.addRow("接入地址", self.mcp_url_edit)
        mcp_form.addRow("Secret Key", self.mcp_key_edit)
        mcp_row = QHBoxLayout()
        self.mcp_test_btn = QPushButton("测试连接（读取工具列表）")
        self.mcp_test_btn.clicked.connect(self._test_mcp)
        self.mcp_test_label = QLabel("")
        mcp_row.addWidget(self.mcp_test_btn)
        mcp_row.addWidget(self.mcp_test_label, 1)
        mcp_form.addRow(mcp_row)
        lay.addWidget(mcp_box)

        # ---------- 模型 ----------
        llm_box = QGroupBox("模型 API 凭据（OpenAI 兼容）")
        llm_form = QFormLayout(llm_box)
        self.llm_url_edit = QLineEdit(self.settings.llm_base_url)
        self.llm_key_edit = QLineEdit(self.settings.llm_api_key)
        self.llm_key_edit.setEchoMode(QLineEdit.Password)
        self.llm_model_edit = QLineEdit(self.settings.llm_model)
        self.llm_mode_combo = QComboBox()
        for text, value in (("自动识别", "auto"), ("Responses API", "responses"),
                            ("Chat Completions", "chat")):
            self.llm_mode_combo.addItem(text, value)
        idx = self.llm_mode_combo.findData(self.settings.llm_mode)
        self.llm_mode_combo.setCurrentIndex(max(0, idx))
        llm_form.addRow("Base URL", self.llm_url_edit)
        llm_form.addRow("API Key", self.llm_key_edit)
        llm_form.addRow("模型名", self.llm_model_edit)
        llm_form.addRow("兼容模式", self.llm_mode_combo)
        llm_row = QHBoxLayout()
        self.llm_test_btn = QPushButton("测试模型")
        self.llm_test_btn.clicked.connect(self._test_llm)
        self.llm_test_label = QLabel("")
        llm_row.addWidget(self.llm_test_btn)
        llm_row.addWidget(self.llm_test_label, 1)
        llm_form.addRow(llm_row)
        lay.addWidget(llm_box)

        # ---------- 保存 ----------
        save_row = QHBoxLayout()
        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self._save)
        status = QLabel("")
        self._status = status
        save_row.addWidget(self.save_btn)
        save_row.addWidget(status, 1)
        lay.addLayout(save_row)
        lay.addStretch(1)

    # ---------- 读写 ----------

    def _collect(self) -> None:
        self.settings.mcp_url = self.mcp_url_edit.text().strip()
        self.settings.mcp_secret_key = self.mcp_key_edit.text().strip()
        self.settings.llm_base_url = self.llm_url_edit.text().strip()
        self.settings.llm_api_key = self.llm_key_edit.text().strip()
        self.settings.llm_model = self.llm_model_edit.text().strip()
        self.settings.llm_mode = self.llm_mode_combo.currentData()

    def _save(self) -> None:
        try:
            self._collect()
            self.settings.save()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"保存失败：{str(exc)[:120]}")
            QMessageBox.warning(self, "保存失败", str(exc)[:400])
            return
        self._status.setText("已保存（密钥已写入 Windows 凭据管理器，不在 settings.json）")

    def _run(self, fn, ok_label: QLabel) -> None:
        self._collect()
        ok_label.setText("测试中…")
        thread = _TestThread(fn)
        self._threads = [t for t in self._threads if not t.isFinished()] + [thread]

        def on_ok(info: dict) -> None:
            # 测试通过即登记：输入框值写入 settings 与 Windows 凭据管理器，
            # 用户无需再单独点“保存设置”即可在任务列表执行
            try:
                self._collect()
                self.settings.save()
            except Exception as exc:  # noqa: BLE001
                ok_label.setText(f"凭据保存失败：{str(exc)[:120]}")
                QMessageBox.warning(self, "凭据保存失败", str(exc)[:400])
                return
            ok_label.setText(info.get("text", "连接正常") + "（已保存）")
            self._status.setText("凭据已登记")

        def on_err(err: str) -> None:
            ok_label.setText(f"失败：{err[:120]}")
            QMessageBox.warning(self, "测试失败", err[:400])

        thread.finished_ok.connect(on_ok)
        thread.finished_err.connect(on_err)
        thread.start()

    def _test_mcp(self) -> None:
        from urllib.parse import quote

        from app.core.mcp_client import test_mcp_connection

        # 测试直接读取输入框（不依赖已保存的凭据管理器值）；
        # 保存设置按钮才会把密钥写入凭据管理器
        key = self.mcp_key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "缺少凭据", "请先填写 SellerSprite Secret Key")
            return
        base = self.mcp_url_edit.text().strip().rstrip("/")
        sep = "&" if "?" in base else "?"
        endpoint = f"{base}{sep}secret-key={quote(key, safe='')}"

        def run() -> dict:
            info = test_mcp_connection(endpoint)
            if info.get("ok"):
                return {"text": f"连接正常，发现 {info['tools']} 个工具"}
            raise RuntimeError(info.get("error", "未知错误"))

        self._run(run, self.mcp_test_label)

    def _test_llm(self) -> None:
        from app.core.llm_client import LLMClient

        base = self.llm_url_edit.text().strip()
        key = self.llm_key_edit.text().strip()
        model = self.llm_model_edit.text().strip()
        if not (base and key and model):
            QMessageBox.warning(self, "缺少凭据", "请填写 Base URL、API Key 与模型名")
            return
        # 测试直接读取输入框（不依赖已保存的凭据管理器值）
        client = LLMClient(base, key, model,
                           mode=self.llm_mode_combo.currentData())

        def run() -> dict:
            info = client.test_connection()
            return {"text": f"模型正常（{info.get('mode')} / {info.get('model')}）：{info.get('sample')}"}

        self._run(run, self.llm_test_label)
