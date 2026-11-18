# -*- coding: utf-8 -*-
"""build_all.py — 一键全流程：校验 → Excel → HTML → 页面验证 → 汇总

用法
----
python scripts/build_all.py examples/01-过氧化氢-越南-海运/case.json [--no-verify] [--as-of 2026-10-19]

产物（写在 case.json 所在目录）
------------------------------
出口合规准备工作簿_<产品>_<目的国>_<编号>.xlsx
出口合规准备页_<产品>_<目的国>_<编号>.html
checks.json / office_checks.json
preview/（截图，若验证开启）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import validators  # noqa: E402
import build_workbook  # noqa: E402
import build_html  # noqa: E402

NODE_CANDIDATES = [
    os.environ.get("NODE_BIN", ""),
    shutil.which("node") or "",
    (__import__('shutil').which('node') or 'node'),
]
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_node() -> str | None:
    for c in NODE_CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


def find_chrome() -> str | None:
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    return None


def slug(case: dict) -> str:
    import re
    p = case["inputs"]["product"]
    # 去掉括号内的别名/说明，只留主名称，避免文件名冗长
    name = re.sub(r"[（(][^）)]*[）)]", "", p["name_cn"]).replace("溶液", "").strip()
    dest = re.sub(r"[（(][^）)]*[）)]", "", p["destination"]).strip()
    return f"{name}_{dest}_{case['meta']['case_id']}"


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def parse_allpass(out: str) -> bool:
    """从验证脚本的 JSON 输出里稳健判断 allPass（允许前后有其它文本/缩进）。"""
    import re
    m = re.search(r'"allPass"\s*:\s*(true|false)', out)
    return bool(m and m.group(1) == "true")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="一键生成出口合规 HTML + Excel")
    ap.add_argument("case")
    ap.add_argument("--no-verify", action="store_true", help="跳过浏览器验证")
    ap.add_argument("--as-of", default=None)
    a = ap.parse_args(argv)

    case_path = Path(a.case).resolve()
    base = case_path.parent
    case = json.loads(case_path.read_text(encoding="utf-8"))
    s = slug(case)
    steps: list[tuple[str, bool, str]] = []

    # ---- 1) 校验 ----
    checks_path = base / "checks.json"
    chk = validators.run(str(case_path), str(checks_path), a.as_of)
    steps.append(("数据校验 validators.py", chk["ok"],
                  f"{chk['entries']} 条目 / {chk['regs']} 法规 / {chk['open_questions']} 待确认；"
                  f"error={len(chk['errors'])} warn={len(chk['warnings'])}"))
    if not chk["ok"]:
        for e in chk["errors"]:
            print("  ERROR", e)
        print("\n校验未通过，停止生成。")
        return 1

    # ---- 2) Excel ----
    xlsx_path = base / f"出口合规准备工作簿_{s}.xlsx"
    build_workbook.build(str(case_path), str(xlsx_path), str(checks_path))
    steps.append(("生成 Excel", xlsx_path.exists() and xlsx_path.stat().st_size > 20000,
                  f"{xlsx_path.name} ({xlsx_path.stat().st_size // 1024} KB)"))

    # ---- 3) HTML ----
    html_path = base / f"出口合规准备页_{s}.html"
    html_path.write_text(build_html.build(case, chk), encoding="utf-8")
    steps.append(("生成 HTML", html_path.stat().st_size > 40000,
                  f"{html_path.name} ({html_path.stat().st_size // 1024} KB)"))

    # ---- 4) 浏览器验证 ----
    if not a.no_verify:
        node, chrome = find_node(), find_chrome()
        if not node or not chrome:
            steps.append(("浏览器验证", True, "跳过（未找到 node 或 Chrome）"))
        else:
            rc, out = run([node, str(HERE / "verify_page.cjs"), str(html_path), str(base / "preview")])
            ok = rc == 0 and parse_allpass(out)
            steps.append(("页面结构与截图", ok, "见 preview/" if ok else out[-400:]))
            rc2, out2 = run([node, str(HERE / "verify_interaction.cjs"), str(html_path)])
            ok2 = rc2 == 0 and parse_allpass(out2)
            pv = base / "preview"
            if pv.exists():
                (pv / "interaction.json").write_text(out2, encoding="utf-8")
            steps.append(("交互功能验证", ok2, "展开/筛选/搜索/键盘/布局" if ok2 else out2[-400:]))

    # ---- 汇总 ----
    print("\n" + "=" * 72)
    print(f"案例：{case['meta']['case_id']}  {case['meta']['title']}")
    print("=" * 72)
    for name, ok, detail in steps:
        print(f"{'✔' if ok else '✘'} {name:<24} {detail}")
    print("=" * 72)
    allok = all(x[1] for x in steps)
    print("总体：", "全部通过" if allok else "有未通过项")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
