# -*- coding: utf-8 -*-
"""一键：校验 → HTML → Excel → 体检。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable


def run(script: str, *args: str) -> int:
    cmd = [PY, str(HERE / script), *args]
    print("$", " ".join(cmd[1:]))
    return subprocess.call(cmd)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", default="out")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    data_path = Path(args.data).resolve()
    out = Path(args.out)

    if run("validate.py", str(data_path)) != 0:
        raise SystemExit("校验未通过，已停止")

    name = args.name
    if not name:
        import json
        with open(data_path, encoding="utf-8") as f:
            name = f'{json.load(f)["meta"]["product"]}多地区价格对比'

    if run("build_html.py", str(data_path), "--out", str(out), "--name", name) != 0:
        raise SystemExit("HTML 生成失败")
    if run("build_xlsx.py", str(data_path), "--out", str(out), "--name", name) != 0:
        raise SystemExit("Excel 生成失败")

    rc = run("qa.py", str(data_path), str(out / f"{name}.html"), str(out / f"{name}.xlsx"))
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
