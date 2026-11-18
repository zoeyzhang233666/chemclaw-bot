# -*- coding: utf-8 -*-
"""build_all.py — 一条命令跑完：校验 → HTML → Excel。

    python scripts/build_all.py examples/soda-ash/data.json
    python scripts/build_all.py mydata.json --out ./deliverables --name 尿素-某集团

输出文件名默认取 meta.export_base（没有则用 供应商准入尽调底稿_<target>_<product>）。
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def run(script, args):
    cmd = [sys.executable, os.path.join(HERE, script)] + args
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(p.stdout or "")
    if p.returncode != 0:
        sys.stderr.write(p.stderr or "")
        raise SystemExit(f"{script} 失败（退出码 {p.returncode}）")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", help="data.json 路径")
    ap.add_argument("--out", default=None, help="输出目录，默认与 data.json 同级 out/")
    ap.add_argument("--name", default=None, help="输出文件名前缀（不含扩展名）")
    ap.add_argument("--skip-validate", action="store_true")
    a = ap.parse_args()

    data = json.load(open(a.data, encoding="utf-8"))
    meta = data.get("meta", {})
    base = a.name or meta.get("export_base") or (
        f'供应商准入尽调底稿_{meta.get("target", "unknown")}_{meta.get("product", "")}'.rstrip("_"))
    out_dir = a.out or os.path.join(os.path.dirname(os.path.abspath(a.data)), "out")
    os.makedirs(out_dir, exist_ok=True)

    if not a.skip_validate:
        run("validate.py", [a.data])
    run("render_html.py", [a.data, os.path.join(out_dir, base + ".html")])
    try:
        run("render_xlsx.py", [a.data, os.path.join(out_dir, base + ".xlsx")])
    except SystemExit as e:
        print(f"[warn] Excel 未生成：{e}")
    print(f"\n完成：{out_dir}")


if __name__ == "__main__":
    main()
