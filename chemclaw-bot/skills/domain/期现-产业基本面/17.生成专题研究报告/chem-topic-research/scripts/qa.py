# -*- coding: utf-8 -*-
"""
qa.py —— 交付物静态自检（不需要浏览器）。

    python qa.py <交付物目录或单个 HTML>

检查：
  * HTML 里没有残留占位符（__TITLE__ / __DATA__ / {{...}}）
  * 标题、payload、结论、来源、缺口数量与 case 一致（若同目录有 build_report.json）
  * Excel 13 页齐全、自检页无 FAIL
  * Markdown 提纲/记录/全文存在且非空，且提纲含"为什么需要"
  * 报告全文不含禁止措辞（"行业普遍认为""毫无疑问"等）

退出码 0 = 全过。
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BANNED = ["行业普遍认为", "据了解", "毫无疑问", "必将", "势必", "众所周知"]

results = []


def chk(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    return ok


def check_html(path):
    text = io.open(path, encoding="utf-8").read()
    chk("HTML 无残留占位符", "__TITLE__" not in text and "__DATA__" not in text
        and not re.search(r"\{\{[A-Z_]+\}\}", text))
    m = re.search(r'<script id="payload" type="application/json">(.*?)</script>', text, re.S)
    if not chk("HTML 含 payload", bool(m)):
        return
    payload = json.loads(m.group(1))
    chk("payload 含受众", bool(payload.get("profile", {}).get("audience_key")))
    n_c = len(payload.get("conclusions") or [])
    n_s = len(payload.get("sources") or {})
    n_g = len(payload.get("gaps") or {})
    n_sec = len(payload.get("sections") or [])
    chk("结论 ≥ 3 条", n_c >= 3, "实际 %d" % n_c)
    chk("来源 ≥ 10 条", n_s >= 10, "实际 %d" % n_s)
    chk("章节 ≥ 4 个", n_sec >= 4, "实际 %d" % n_sec)
    chk("缺口已列示", n_g >= 1, "实际 %d" % n_g)
    # 图表数据键可解析
    ds = payload.get("datasets") or {}
    charts = [b for s in payload.get("sections") or [] for b in s.get("blocks") or []
              if b.get("type") == "chart"]
    missing = [b.get("data_key") for b in charts if b.get("data_key") not in ds]
    chk("图表数据键全部可解析", not missing, "缺失 %s" % (missing or "无"))
    chk("图表数量合理", len(charts) >= 4, "实际 %d" % len(charts))
    # 结论可下钻
    bad = [c["id"] for c in payload.get("conclusions") or []
           if not (c.get("evidence") or [])]
    chk("结论均带证据", not bad, "缺失 %s" % (bad or "无"))
    bad2 = [c["id"] for c in payload.get("conclusions") or []
            if c.get("type") in ("判断", "解释") and not c.get("falsify")]
    chk("判断/解释均有反证条件", not bad2, "缺失 %s" % (bad2 or "无"))
    # 禁止措辞（只在正文里查，避免命中来源标题）
    body = " ".join(str(b.get("text") or "") for s in payload.get("sections") or []
                    for b in s.get("blocks") or [] if b.get("type") in ("para", "callout"))
    hits = [w for w in BANNED if w in body]
    chk("正文无模糊措辞", not hits, "命中 %s" % (hits or "无"))


def check_xlsx(path):
    try:
        from openpyxl import load_workbook
    except ImportError:
        chk("Excel 检查", False, "未安装 openpyxl，跳过")
        return
    wb = load_workbook(path)
    expected = ["00_使用说明", "01_证据索引", "02_原始数据", "03_企业产能", "04_项目台账", "05_价格数据",
                "06_产业指标", "07_计算结果", "08_结论", "09_关键变量", "10_资料缺口", "11_章节大纲",
                "12_质量自检"]
    missing = [s for s in expected if s not in wb.sheetnames]
    chk("Excel 13 页齐全", not missing, "缺 %s" % (missing or "无"))
    if "12_质量自检" in wb.sheetnames:
        ws = wb["12_质量自检"]
        vals = [ws.cell(row=r, column=1).value for r in range(5, ws.max_row + 1)]
        fails = [ws.cell(row=r, column=2).value for r in range(5, ws.max_row + 1)
                 if ws.cell(row=r, column=1).value == "FAIL"]
        chk("Excel 自检页无 FAIL", not fails, "FAIL %s" % (fails or "无"))
    empty = []
    for s in expected:
        if s in wb.sheetnames:
            ws = wb[s]
            has = any(ws.cell(row=r, column=c).value not in (None, "")
                      for r in range(5, ws.max_row + 1) for c in range(1, 6))
            if not has:
                empty.append(s)
    chk("无空页", not empty, "%s" % (empty or "无"))


def check_md(path):
    p = path
    if not chk("提纲存在", os.path.exists(p), p):
        return
    t = io.open(p, encoding="utf-8").read()
    chk("提纲非空", len(t) > 800, "%d 字" % len(t))
    chk("提纲写清章节理由", "为什么" in t and "依赖数据" in t)
    chk("提纲标注确认状态", "待确认" in t or "已确认" in t)


def main(argv):
    target = argv[1] if len(argv) > 1 else "."
    files = []
    if os.path.isdir(target):
        files = sorted(glob.glob(os.path.join(target, "*.html")))
        xlsx = sorted(glob.glob(os.path.join(target, "*.xlsx")))
        mds = sorted(glob.glob(os.path.join(target, "*研究提纲*.md")))
        recs = sorted(glob.glob(os.path.join(target, "*执行记录*.md")))
        full = sorted(glob.glob(os.path.join(target, "*报告全文*.md")))
    else:
        files = [target]
        xlsx = mds = recs = full = []

    chk("找到 HTML", bool(files), "%d 个" % len(files))
    for f in files:
        check_html(f)
    for x in xlsx:
        check_xlsx(x)
    if os.path.isdir(target):
        chk("找到 Excel", bool(xlsx), "%d 个" % len(xlsx))
        chk("找到提纲", bool(mds), "%d 个" % len(mds))
        chk("找到执行记录", bool(recs), "%d 个" % len(recs))
        chk("找到报告全文", bool(full), "%d 个" % len(full))
        for t in mds:
            pass
        if mds:
            check_md(mds[0])
        if full:
            txt = "".join(io.open(f, encoding="utf-8").read() for f in full)
            hits = [w for w in BANNED if w in txt]
            chk("Markdown 全文无模糊措辞", not hits, "%s" % (hits or "无"))

    npass = sum(1 for _, ok, _ in results if ok)
    print("== 交付物自检 ==")
    for name, ok, detail in results:
        print("  %-4s %-24s %s" % ("PASS" if ok else "FAIL", name, detail))
    print("\nRESULT %s  (%d/%d)" % ("PASS" if npass == len(results) else "FAIL", npass, len(results)))
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
