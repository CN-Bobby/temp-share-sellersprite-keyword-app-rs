# -*- coding: utf-8 -*-
"""验证发布 zip 可分发性：解压、密钥扫描、selfcheck、GUI 启动。

用法:
  python tools/verify_dist_zip.py [--zip <zip路径>] [--root <解压根名>]
默认验证 发布/SellerSprite关键词调研-v1.1.0-win-x64-portable.zip。
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "发布"
KEYS = ["sk-820704137be2403083b51a48cdf968e7", "258b012c8bd840e0be125754aaaf7cb1"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default=str(
        BASE / "SellerSprite关键词调研-v1.1.0-win-x64-portable.zip"))
    ap.add_argument("--root", default="SellerSprite关键词调研-v1.1.0-win-x64-portable")
    args = ap.parse_args()
    zip_path = Path(args.zip)
    EXTRACT = Path(os.environ.get("TEMP", "/tmp")) / f"verify_{zip_path.stem[:12]}"

    print(f"验证: {zip_path}")
    print("1) ZIP 完整性：", end="", flush=True)
    z = zipfile.ZipFile(zip_path)
    bad = z.testzip()
    print("OK（条目", len(z.namelist()), "）" if bad is None else f"损坏: {bad}")
    if bad:
        return 1

    if EXTRACT.exists():
        shutil.rmtree(EXTRACT)
    z.extractall(EXTRACT)
    print("2) 解压目录：", EXTRACT)

    root = EXTRACT / args.root
    print("3) 密钥扫描：", end="", flush=True)
    leaks = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".py", ".json", ".md", ".txt", ".toml", ".yml", ".yaml", ".ini", ".cfg", ".log"):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                for k in KEYS:
                    if k in text:
                        leaks.append(str(p))
            except Exception:
                pass
    for exe in root.rglob("*.exe"):
        data = exe.read_bytes()
        for k in KEYS:
            if k.encode() in data:
                leaks.append(f"{exe} (binary)")
    print("无泄漏" if not leaks else f"泄漏: {leaks}")
    if leaks:
        return 1

    print("4) settings.json 残留：", end="", flush=True)
    res = list(root.rglob("settings.json"))
    print("无" if not res else f"存在: {res}")

    print("5) selfcheck：", end="", flush=True)
    exe = next(root.rglob("*.exe"))
    proc = subprocess.run([str(exe), "--selfcheck"], capture_output=True,
                          timeout=120)
    ok = proc.returncode == 0 and b'"ok": true' in proc.stdout
    print("PASS" if ok else f"FAIL rc={proc.returncode} out={proc.stdout[:200]}")
    if not ok:
        return 1

    print("6) GUI 启动：", end="", flush=True)
    proc = subprocess.Popen([str(exe)])
    import time

    time.sleep(6)
    alive = proc.poll() is None
    if alive:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    print("PASS" if alive else "FAIL（启动即退出）")
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
