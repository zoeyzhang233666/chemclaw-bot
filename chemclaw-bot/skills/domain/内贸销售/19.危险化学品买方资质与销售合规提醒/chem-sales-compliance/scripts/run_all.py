# -*- coding: utf-8 -*-
"""一键跑完：Excel + HTML + 校验。

用法:
    python scripts/run_all.py examples/01-纯碱-福莱特
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(argv):
    if len(argv) < 2:
        print("用法: python run_all.py <案例目录>")
        return 2
    case_dir = Path(argv[1]).resolve()
    case = case_dir / "case.json"
    out_dir = case_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = case_dir.name.split("-", 1)[-1]
    xlsx = out_dir / f"{stem}_合规提醒.xlsx"
    html = out_dir / f"{stem}_合规提醒.html"

    steps = [
        [sys.executable, str(HERE / "build_workbook.py"), str(case), str(xlsx)],
        [sys.executable, str(HERE / "build_html.py"), str(case), str(html)],
        [sys.executable, str(HERE / "verify.py"), str(case), "--html", str(html), "--xlsx", str(xlsx)],
    ]
    for cmd in steps:
        print(">", " ".join(cmd[1:]))
        rc = subprocess.call(cmd)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
