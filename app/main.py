# -*- coding: utf-8 -*-
"""应用入口：SellerSprite 关键词调研小程序 v1.0.0。"""
from __future__ import annotations

import sys


def main() -> int:
    # 打包自检：不启动 GUI，验证引擎资产与脚本执行链
    if "--selfcheck" in sys.argv:
        return _selfcheck()
    from PySide6.QtWidgets import QApplication

    from app.gui.main_window import MainWindow
    from app.version import APP_DISPLAY_NAME
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setOrganizationName("SellerSpriteKeywordApp")
    from app.gui.theme import QSS

    app.setStyleSheet(QSS)
    window = MainWindow()
    window.show()
    return app.exec()


def _selfcheck() -> int:
    """打包自检：引擎资产定位 + runpy 执行链 + 凭据库读写 + 版本。"""
    import json
    import tempfile
    import time
    from pathlib import Path

    from app.core.config import CredentialStore, Settings
    from app.core.engine import (ENGINE_ROOT, TEMPLATE_PATH, engine_available,
                                 run_script)
    from app.version import APP_VERSION, DEV_CHAIN, ENGINE_VERSION

    result = {"ok": True, "checks": {}, "dev_chain": DEV_CHAIN,
              "app_version": APP_VERSION, "engine_version": ENGINE_VERSION}
    result["checks"]["engine_available"] = engine_available()
    result["checks"]["scripts_dir"] = str(ENGINE_ROOT / "scripts")
    result["checks"]["template_exists"] = TEMPLATE_PATH.exists()

    # 凭据库读写 roundtrip：裸 win32cred 调用（不吞异常），确认打包环境真实行为
    check_name = f"_selfcheck_{int(time.time())}"
    probe = "OK"
    try:
        import win32cred  # 裸调用绕过 CredentialStore 的异常吞噬

        cred = {
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": f"SellerSpriteKeywordApp/{check_name}",
            "UserName": "app",
            "CredentialBlob": probe,
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }
        write_ret = win32cred.CredWrite(cred, 0)
        try:
            read = win32cred.CredRead(
                f"SellerSpriteKeywordApp/{check_name}", win32cred.CRED_TYPE_GENERIC)
            blob = read.get("CredentialBlob")
            readback = blob.decode("utf-16-le") if isinstance(blob, bytes) else str(blob)
        finally:
            try:
                win32cred.CredDelete(
                    f"SellerSpriteKeywordApp/{check_name}",
                    win32cred.CRED_TYPE_GENERIC, 0)
            except Exception:  # noqa: BLE001
                pass
        result["checks"]["credential_store"] = (readback == probe)
        result["checks"]["credential_write_ret"] = str(write_ret)
        result["checks"]["credential_readback"] = repr(readback)
        result["checks"]["credential_backend"] = "win32cred"
    except Exception as exc:  # noqa: BLE001
        result["checks"]["credential_store"] = False
        result["checks"]["credential_backend"] = "win32cred"
        result["checks"]["credential_error"] = repr(exc)[:300]

    # settings.json 可写性（非敏感路径）
    try:
        settings = Settings(app_dir=Path(tempfile.mkdtemp()))
        settings.save()
        result["checks"]["settings_writable"] = True
    except Exception as exc:  # noqa: BLE001
        result["checks"]["settings_writable"] = False
        result["checks"]["settings_error"] = str(exc)[:200]
    # runpy 执行链：空任务上跑 aggregate_batches 应走到业务逻辑
    # （缺 traffic_batch 文件而失败），证明 import/argparse/路径解析全通
    try:
        tmp = Path(tempfile.mkdtemp())
        run_script("aggregate_batches.py", tmp)
        result["checks"]["runpy_engine"] = False
        result["checks"]["error"] = "空任务未按预期失败"
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "traffic_batch" in msg:
            result["checks"]["runpy_engine"] = True
        else:
            result["checks"]["runpy_engine"] = False
            result["checks"]["error"] = msg[:300]
    if not all(result["checks"].values()):
        result["ok"] = False
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
