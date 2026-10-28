# -*- coding: utf-8 -*-
"""skill 引擎脚本执行器。

打包分发后没有独立 python 解释器，脚本改为 runpy 同进程执行
（sys.executable 是主程序 exe，不能跑 .py）。同进程执行顺带消除
Windows 子进程编码/乱码问题。依赖（openpyxl 等）已随主程序打包。
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import Callable, Optional


def _resolve_engine_root() -> Path:
    """定位引擎资产根目录。

    开发环境：app/core/engine.py → app/engine；
    打包环境（frozen）：PyInstaller add-data 把 assets/references/scripts
    放到 exe 同级（实测 onedir 的 add-data dest 相对 dist 根），从
    sys.executable 同级目录解析。
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 6.x onedir：add-data 落到 sys._MEIPASS（_internal）下
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        cand = meipass / "app" / "engine" / "scripts" / "aggregate_batches.py"
        if cand.exists():
            return meipass / "app" / "engine"
        # 兜底：部分版本把资产放到 exe 同级
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "scripts" / "aggregate_batches.py").exists():
            return exe_dir
    return Path(__file__).resolve().parents[1] / "engine"


ENGINE_ROOT = _resolve_engine_root()
SCRIPTS_DIR = ENGINE_ROOT / "scripts"
TEMPLATE_PATH = ENGINE_ROOT / "assets" / "keyword_market_report_template.xlsx"

OnOutput = Optional[Callable[[str], None]]


class EngineError(Exception):
    def __init__(self, script: str, workdir: Path, returncode: int,
                 detail: str) -> None:
        self.script = script
        self.workdir = workdir
        self.returncode = returncode
        self.detail = detail
        super().__init__(f"引擎脚本 {script} 失败（exit {returncode}）: {detail[-800:]}")


def engine_dir() -> Path:
    return ENGINE_ROOT


def run_script(name: str, workdir: Path | str, *extra_args: str,
               on_output: OnOutput = None, timeout: float = 600.0) -> str:
    """运行一个 skill 脚本（runpy 同进程），返回 stdout（当前为空串，输出走事件）。"""
    script = SCRIPTS_DIR / name
    if not script.exists():
        raise FileNotFoundError(f"引擎脚本不存在: {script}")
    old_argv = sys.argv
    old_path = list(sys.path)
    try:
        sys.argv = ["engine", "--workdir", str(workdir), *extra_args]
        # 脚本间互相 import（如 validate_labels import classify_keywords）
        sys.path.insert(0, str(SCRIPTS_DIR))
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:  # 脚本用 SystemExit 表达失败
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        if code != 0:
            raise EngineError(name, Path(workdir), code, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise EngineError(name, Path(workdir), 1, str(exc)) from exc
    finally:
        sys.argv = old_argv
        sys.path = old_path
    return ""


def engine_available() -> bool:
    """启动自检：引擎脚本与模板是否齐全。"""
    required = [
        "aggregate_batches.py", "normalize_keywords.py",
        "aggregate_asin_keyword_matrix.py", "classify_keywords.py",
        "validate_labels.py", "select_trend_keywords.py", "analyze_trends.py",
        "validate_analysis.py", "build_excel_report.py", "validate_report.py",
    ]
    missing = [n for n in required if not (SCRIPTS_DIR / n).exists()]
    return not missing and TEMPLATE_PATH.exists()
