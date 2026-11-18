# -*- coding: utf-8 -*-
"""build_all.py —— 一条命令跑完整条流水线。

    python build_all.py                          # 跑内置样例（乙二醇模拟数据）
    python build_all.py --data my.json --outdir out --name 某产品核对
    python build_all.py --no-samples             # 不重新生成模拟原始文件

流水线：
  1) （可选）重新生成模拟原始文件 samples/*.html
  2) validate.py（结构 + 语义 + 合规）
  3) render_html.py  → 单文件交互报告
  4) render_xlsx.py  → 多页签工作簿
  5) 成品复查（HTML/Excel 是否含 None/NaN/占位符、计数是否一致）

任何一步返回非零，整条流水线停止并给出原因——**不要带着未通过的校验去交付**。
"""
import argparse
import json
import os
import runpy
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def step(no, title):
    print(f"\n{'=' * 68}\n[{no}] {title}\n{'=' * 68}")


def run(args, **kw):
    t0 = time.time()
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    dt = time.time() - t0
    out = (r.stdout or "") + (r.stderr or "")
    print(out.rstrip())
    print(f"    ⏱ {dt:.1f}s · exit={r.returncode}")
    return r.returncode, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "examples", "mdeg", "data.json"))
    ap.add_argument("--outdir", default=os.path.join(ROOT, "examples", "mdeg", "out"))
    ap.add_argument("--name", default="", help="输出文件名前缀，默认取 data.meta.title")
    ap.add_argument("--no-samples", action="store_true")
    ap.add_argument("--strict", action="store_true", help="警告也视为失败")
    a = ap.parse_args()

    data_path = os.path.abspath(a.data)
    if not os.path.exists(data_path):
        print(f"[错误] 找不到 {data_path}")
        return 2
    data = json.load(open(data_path, encoding="utf-8"))
    os.makedirs(a.outdir, exist_ok=True)
    name = a.name or data.get("meta", {}).get("export_base") or "coa-check"
    html_path = os.path.join(a.outdir, f"{name}-核对报告.html")
    xlsx_path = os.path.join(a.outdir, f"{name}-核对工作簿.xlsx")
    only_example = os.path.basename(os.path.dirname(data_path)) == "mdeg"

    fails = []
    if only_example and not a.no_samples:
        step(1, "生成模拟原始文件（规格书 / COA / 历史台账）")
        rc, _ = run([os.path.join(HERE, "build_example_data.py")])
        if rc:
            fails.append("build_example_data")

    step(2, "校验输入（结构 / 语义 / 合规）")
    rc, out = run([os.path.join(HERE, "validate.py"), data_path] + (["--strict"] if a.strict else []))
    if rc:
        fails.append("validate")
        print("\n[中止] 输入未通过校验，未生成任何交付物。请先修正上表问题。")
        return 1

    step(3, "生成 HTML 交互报告")
    rc, _ = run([os.path.join(HERE, "render_html.py"), data_path, html_path])
    if rc:
        fails.append("render_html")

    step(4, "生成 Excel 工作簿")
    rc, _ = run([os.path.join(HERE, "render_xlsx.py"), data_path, xlsx_path])
    if rc:
        fails.append("render_xlsx")

    step(5, "成品复查")
    rc, out5 = run([os.path.join(HERE, "validate.py"), data_path, "--render", html_path, xlsx_path])
    if rc:
        fails.append("post-validate")

    print(f"\n{'=' * 68}")
    if fails:
        print("[失败] " + "、".join(fails))
        return 1
    print("[完成] 交付物：")
    for p in (html_path, xlsx_path):
        size = os.path.getsize(p) / 1024
        print(f"  · {p}  ({size:.0f} KB)")
    print("\n提醒：报告只呈现事实与判断，不作收货/退货决定；"
          "所有模拟数据均已标注 SIMULATED。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
