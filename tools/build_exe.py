# -*- coding: utf-8 -*-
"""PyInstaller 打包脚本：onedir 便携分发版。

用法: python tools/build_exe.py
输出: 发布/SellerSprite关键词调研-v1.0.0-win-x64-portable/
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))
from app.version import APP_DISPLAY_NAME, APP_VERSION  # noqa: E402

EXE_NAME = APP_DISPLAY_NAME.replace(" ", "")  # exe/目录名不带空格
DIST_NAME = f"SellerSprite关键词调研-v{APP_VERSION}-win-x64-portable"
DIST_DIR = ROOT / "发布" / DIST_NAME
BUILD_DIR = ROOT / "build"

ENTRY = ROOT / "app" / "main.py"
ICON = ROOT / "app" / "gui" / "resources" / "app_icon.ico"

# 引擎资产（脚本/references/模板）作为数据文件随包分发
ENGINE_ASSETS = ["app/engine/scripts", "app/engine/references", "app/engine/assets"]


def main() -> int:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onedir",
        "--windowed",
        "--name", EXE_NAME,
        "--distpath", str(DIST_DIR.parent),
        "--workpath", str(BUILD_DIR / "work"),
        "--specpath", str(BUILD_DIR),
        "--version-file", str(ROOT / "tools" / "version_info.txt"),
        # 引擎脚本以数据文件随包分发、runpy 运行时 import，静态分析不可见，
        # 需显式声明其依赖
        "--hidden-import", "openpyxl",
        # pywin32 的 CredWrite/CredRead 依赖 win32timezone（动态导入，静态分析不可见），
        # 漏打包会导致凭据写入静默失败——实测坑点
        "--hidden-import", "win32timezone",
    ]
    if ICON.exists():
        cmd += ["--icon", str(ICON)]
    for asset in ENGINE_ASSETS:
        cmd += ["--add-data", f"{ROOT / asset};{asset}"]
    cmd.append(str(ENTRY))

    print("运行 PyInstaller：", " ".join(cmd[:8]), "...")
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        print("打包失败", flush=True)
        return proc.returncode

    # onedir 输出目录整理：PyInstaller 输出到 dist/<APP_NAME>，改名
    built = DIST_DIR.parent / EXE_NAME
    if built.exists():
        built.rename(DIST_DIR)

    # 打包后自动补齐交付文档（docs/ 为准，重打包不丢文档）
    import shutil as _shutil

    docs_src = ROOT / "docs"
    if docs_src.exists():
        for f in docs_src.iterdir():
            if f.is_file() and f.suffix.lower() in (".md", ".json"):
                _shutil.copy2(f, DIST_DIR / f.name)
    print(f"打包完成: {DIST_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
