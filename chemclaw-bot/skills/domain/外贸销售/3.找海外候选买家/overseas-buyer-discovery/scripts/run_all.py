# -*- coding: utf-8 -*-
"""run_all.py — 一键重建报告与工作簿。

用法:
    python run_all.py <工作目录> [报告名] [工作簿名]

工作目录下应包含:
    leads_merged.json        必填  归一化后的线索（见 references/data-contract.md）
    comtrade_series.json     可选  进口额/数量/均价序列
    comtrade_partners.json   可选  分来源国结构 {"2024":[...],"2025":[...]}
    peer_gate.json           可选  同行/竞品排除清单
    market_facts.json        可选  {"headline":{...},"facts":[...]}
    report.css               必填  HTML 样式（从 scripts/report.css 复制）

脚本会先做数据校验，再依次调用 build_html.py 与 build_xlsx.py。
校验失败会打印具体是哪个字段缺了，不会静默生成半成品。
"""
import json
import os
import subprocess
import sys

REQUIRED = ["company", "type", "evidence_tier", "region_short", "lane", "lane_label",
            "main_business", "why_related", "evidence_summary", "evidence_urls", "confidence"]
VALID_TIER = {"A", "B", "C"}
VALID_TYPE = {"终端生产企业", "直接进口商", "经销商", "待确认"}


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate(leads):
    problems = []
    if not leads:
        return ["leads_merged.json 为空或不存在"]
    for i, l in enumerate(leads, 1):
        name = l.get("company") or "#%d" % i
        for k in REQUIRED:
            if not l.get(k):
                problems.append("%s 缺少字段 %s" % (name, k))
        if l.get("evidence_tier") and l["evidence_tier"] not in VALID_TIER:
            problems.append("%s 证据等级非法: %s" % (name, l["evidence_tier"]))
        if l.get("type") and l["type"] not in VALID_TYPE:
            problems.append("%s 客户类型非法: %s" % (name, l["type"]))
        for ev in (l.get("evidence_list") or []):
            if not ev.get("url"):
                problems.append("%s 的证据缺链接（%s）" % (name, ev.get("type", "?")))
    # 本机号码/个人邮箱粗筛
    import re
    for l in leads:
        blob = json.dumps(l, ensure_ascii=False)
        for m in re.findall(r"\+?62\s?8\d{2}[\s-]?\d{3,4}[\s-]?\d{3,4}", blob):
            problems.append("%s 疑似个人手机号: %s" % (l.get("company"), m))
    return problems


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    work = os.path.abspath(sys.argv[1])
    html_name = sys.argv[2] if len(sys.argv) > 2 else "候选买家研究报告.html"
    xlsx_name = sys.argv[3] if len(sys.argv) > 3 else "候选买家清单.xlsx"
    here = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.join(work, "out")
    os.makedirs(outdir, exist_ok=True)

    leads = load(os.path.join(work, "leads_merged.json"), [])
    problems = validate(leads)

    if not os.path.exists(os.path.join(work, "report.css")):
        css_src = os.path.join(here, "report.css")
        if os.path.exists(css_src):
            import shutil
            shutil.copy(css_src, os.path.join(work, "report.css"))

    print("线索数: %d" % len(leads))
    if problems:
        print("\n[校验警告] 共 %d 条：" % len(problems))
        for p in problems[:40]:
            print("  -", p)
        if len(problems) > 40:
            print("  ...")
        if any("缺少字段" in p for p in problems):
            print("\n存在必填字段缺失，已中止。请补齐后重跑。")
            sys.exit(2)

    for script, out in (("build_html.py", html_name), ("build_xlsx.py", xlsx_name)):
        target = os.path.join(outdir, out)
        print("\n>> %s -> %s" % (script, target))
        r = subprocess.run([sys.executable, os.path.join(here, script), target], cwd=work)
        if r.returncode != 0:
            print("失败:", script)
            sys.exit(r.returncode)
    print("\n完成。输出目录:", outdir)


if __name__ == "__main__":
    main()
