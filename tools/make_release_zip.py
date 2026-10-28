# -*- coding: utf-8 -*-
"""规范打发布 zip（zipfile 真 zip + SHA256SUMS）。

注意：tar -a -c -f x.zip 生成的是 tar 数据（不可解压为 zip），
分发 zip 一律用本脚本。用法:
  python tools/make_release_zip.py --dir <便携目录> --out <输出zip路径> [--sha <SHA路径>]
"""
import argparse
import hashlib
import sys
import zipfile
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="便携目录（zip 根为目录名）")
    ap.add_argument("--out", required=True, help="输出 zip 路径")
    ap.add_argument("--sha", default=None, help="SHA256SUMS 输出路径")
    args = ap.parse_args()

    src = Path(args.dir)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file() and p.resolve() != out.resolve():
                z.write(p, p.relative_to(src.parent))

    digest = hashlib.sha256(out.read_bytes()).hexdigest().upper()
    print(f"OK {out}（{out.stat().st_size} 字节） SHA256={digest}")
    if args.sha:
        sha_path = Path(args.sha)
        sha_path.write_text(f"{digest}  {out.name}\n", encoding="utf-8")
        print(f"SHA 已写入 {sha_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
