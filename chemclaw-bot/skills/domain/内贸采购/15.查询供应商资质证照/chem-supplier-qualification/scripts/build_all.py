# -*- coding: utf-8 -*-
"""
build_all.py — 一条命令：校验 -> 生成 HTML -> 生成 Excel

用法：
  python build_all.py data.json --out ./out
  python build_all.py data.json            # 默认输出到 data.json 同目录的 out/

产物：
  <out>/资质证照核验_<主体>_<产品>.html
  <out>/证照与监管要求核验台账_<主体>_<产品>.xlsx
  <out>/scans/  （若 data.json 同目录有 scans/，自动连同复制，保证 HTML 图片可点开）
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(args):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    print(out.strip())
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", default=None)
    ap.add_argument("--skip-validate", action="store_true")
    a = ap.parse_args()
    data = os.path.abspath(a.data)
    out = os.path.abspath(a.out or os.path.join(os.path.dirname(data), "out"))
    os.makedirs(out, exist_ok=True)

    rc = 0
    if not a.skip_validate:
        print("[1/3] 校验 ...")
        rc = run([os.path.join(HERE, "validate.py"), data])
        if rc != 0:
            print("校验未通过（存在 FAIL）。修正 data.json 后重试；如确属演示数据，可加 --skip-validate。")
            return rc
    print("[2/3] 生成 HTML ...")
    rc = run([os.path.join(HERE, "render_html.py"), data, "--out", out])
    if rc != 0:
        return rc
    # HTML 用相对路径 scans/ 引用扫描件；把源目录的 scans/ 一并复制到 out/
    src_scans = os.path.join(os.path.dirname(data), "scans")
    if os.path.isdir(src_scans):
        dst = os.path.join(out, "scans")
        if os.path.abspath(src_scans) != os.path.abspath(dst):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src_scans, dst)
        n = len([f for f in os.listdir(dst) if os.path.isfile(os.path.join(dst, f))])
        print("  scans -> %s (%d files)" % (dst, n))
    print("[3/3] 生成 Excel ...")
    rc = run([os.path.join(HERE, "render_xlsx.py"), data, "--out", out])
    if rc == 0:
        print("完成。输出目录：%s" % out)
    return rc


if __name__ == "__main__":
    sys.exit(main())
