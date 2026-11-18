#!/usr/bin/env python3
"""selftest.py — 端到端自检：用内置案例全流程跑一遍 build + validate + qa

用法:
    python scripts/selftest.py            # 跑全部（甲醇 + 无期货示例）
    python scripts/selftest.py --fast      # 跳过 playwright QA

退出码 0 = 全部通过。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
CASES = [
    ("甲醇案例", ROOT / "examples" / "methanol" / "data" / "research.json"),
    ("无期货示例", ROOT / "examples" / "no-futures-example" / "research.json"),
]


def run(desc, args):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = r.returncode == 0
    print(("  \u2713 " if ok else "  \u2717 ") + desc)
    if not ok:
        tail = (r.stdout or "")[-1200:] + (r.stderr or "")[-800:]
        print("    " + tail.replace("\n", "\n    "))
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="跳过 playwright QA")
    a = ap.parse_args(argv)

    fails = 0
    tmp = Path(tempfile.mkdtemp(prefix="cpq-selftest-"))
    try:
        for name, data in CASES:
            if not data.exists():
                print(f"  \u2717 {name}: 数据缺失 {data}")
                fails += 1
                continue
            print(f"\n=== {name} ===")
            doc = json.loads(data.read_text(encoding="utf-8-sig"))
            out = tmp / data.parent.name
            out.mkdir(parents=True, exist_ok=True)

            fails += 0 if run("validate.py", [PY, str(ROOT / "scripts" / "validate.py"), str(data)]) else 1
            fails += 0 if run("build_html.py", [PY, str(ROOT / "scripts" / "build_html.py"),
                                                str(data), "--out", str(out)]) else 1
            fails += 0 if run("build_xlsx.py", [PY, str(ROOT / "scripts" / "build_xlsx.py"),
                                                str(data), "--out", str(out)]) else 1

            xlsx = list(out.glob("*.xlsx"))
            if xlsx:
                fails += 0 if run("check_xlsx.py", [PY, str(ROOT / "scripts" / "check_xlsx.py"),
                                                    str(xlsx[0]), "--research", str(data)]) else 1

            html = list(out.glob("*.html"))
            if html and not a.fast:
                fails += 0 if run("qa_render.py", [PY, str(ROOT / "scripts" / "qa_render.py"),
                                                   str(html[0])]) else 1
            elif html and a.fast:
                print("  - 已跳过 qa_render（--fast）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n[selftest] {'全部通过' if fails == 0 else f'失败 {fails} 项'}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
