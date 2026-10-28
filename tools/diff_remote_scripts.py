# -*- coding: utf-8 -*-
"""对比客户端（0829）引擎脚本与本机基线的差异，输出 unified diff。"""
import difflib
import sys
from pathlib import Path

REMOTE = Path(r"C:\Users\Administrator\Desktop\关键词调研小程序R版\R_SellerSprite关键词调研-v1.0.0-win-x64-portable_0829_无源码\SellerSprite关键词调研-v1.0.0-win-x64-portable\_internal\app\engine\scripts")
LOCAL = Path(r"C:\Users\Administrator\Desktop\关键词调研小程序R版\关键词小程序R版\app\engine\scripts")

FILES = ["analyze_trends.py", "validate_analysis.py", "validate_report.py"]


def main() -> int:
    for name in FILES:
        r = (REMOTE / name).read_text(encoding="utf-8")
        l = (LOCAL / name).read_text(encoding="utf-8")
        if r == l:
            print(f"=== {name}: 无差异 ===")
            continue
        diff = list(difflib.unified_diff(
            l.splitlines(keepends=True), r.splitlines(keepends=True),
            fromfile=f"local/{name}", tofile=f"remote/{name}", n=2))
        print(f"=== {name}: {len(diff)} 行差异 ===")
        sys.stdout.writelines(diff[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
