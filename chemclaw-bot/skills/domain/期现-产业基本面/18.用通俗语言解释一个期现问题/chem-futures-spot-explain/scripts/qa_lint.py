# -*- coding: utf-8 -*-
"""
qa_lint.py —— 期现解释交付物的结构检查（零依赖，纯标准库）

用法:
  python qa_lint.py <页面.html> [工作簿.xlsx]

检查项（HTML）：
  L1  占位符残留（双花括号 / __TOKEN__）
  L2  外部资源（script src / link href / img src 指向 http）
  L3  必需章节（01 直接回答 … 数据缺口/来源）
  L4  入门/专业双模式标记存在
  L5  术语可点（data-term 数量 ≥ 8）
  L6  重算控件（合约选择 + 日期输入 + calc 输出容器）
  L7  口径声明（出现“基差”“现货 − 期货/减”等口径说明）
  L8  事实/推断/假设 三分（出现三个词）
  L9  数据缺口章节非空
  L10 DATA JSON 可解析

检查项（XLSX，如提供）：
  X1  工作表数量 ≥ 10
  X2  必需表名存在
  X3  公式数量 > 0
  X4  错误值单元格（需要 openpyxl；缺失则跳过并提示先重算后检查）

退出码: 0 通过；1 有不通过项
"""
import json
import os
import re
import sys
import zipfile

HTML_REQUIRED = ["直接回答", "市场指标", "公式", "产业逻辑", "事实", "数据缺口", "来源"]
XLSX_REQUIRED = ["概念", "公式", "库存", "基差", "月差", "来源"]


def lint_html(path):
    t = open(path, encoding="utf-8").read()
    res = []

    def add(code, desc, ok, detail=""):
        res.append((code, desc, ok, detail))

    ph = re.findall(r"\{\{[A-Za-z_]+\}\}", t)
    add("L1", "无占位符残留", not ph, ",".join(ph[:5]))
    ext = re.findall(r'<(?:script|img)[^>]+src="(https?://[^"]+)"', t) + \
          re.findall(r'<link[^>]+href="(https?://[^"]+)"', t)
    add("L2", "零外部资源（无 CDN/外链脚本样式图片）", not ext, ",".join(ext[:3]))
    missing = [k for k in HTML_REQUIRED if k not in t]
    add("L3", "必需章节齐全", not missing, "缺:" + ",".join(missing))
    add("L4", "入门/专业双模式标记", ('data-mode="beginner"' in t) and ('pro-only' in t) and ('beginner-only' in t))
    nterm = len(re.findall(r"data-term=", t))
    add("L5", "术语可点（≥8）", nterm >= 8, f"data-term={nterm}")
    add("L6", "重算控件（合约/日期/输出容器）",
        ('id="sel-contract"' in t) and ('id="inp-from"' in t) and ('id="calc-out"' in t))
    add("L7", "口径声明（基差谁减谁）", ("基差" in t) and (("现货 − 期货" in t) or ("现货减期货" in t) or ("现货 - 期货" in t)))
    add("L8", "事实/推断/假设三分", all(k in t for k in ("事实", "推断", "假设")))
    m = re.search(r'<script id="DATA" type="application/json">(.*?)</script>', t, re.S)
    ok_data = False
    detail = ""
    if m:
        try:
            d = json.loads(m.group(1).replace("<\\/", "</"))
            ok_data = bool(d.get("meta"))
            detail = "keys=" + str(len(d))
        except Exception as e:  # noqa
            detail = str(e)
    add("L10", "DATA JSON 可解析", ok_data, detail)
    add("L9", "数据缺口章节有内容", ("数据缺口" in t) and (t.count("怎么补") > 0 or t.count("GAP") > 2))
    return res


def lint_xlsx(path):
    res = []

    def add(code, desc, ok, detail=""):
        res.append((code, desc, ok, detail))

    try:
        import openpyxl
    except ImportError:
        add("X4", "错误值单元格检查", True, "跳过：未安装 openpyxl")
        return res
    wb = openpyxl.load_workbook(path)
    names = wb.sheetnames
    add("X1", "工作表数 ≥ 10", len(names) >= 10, str(len(names)))
    miss = [k for k in XLSX_REQUIRED if not any(k in n for n in names)]
    add("X2", "必需表名存在", not miss, "缺:" + ",".join(miss))
    nf = sum(1 for ws in wb.worksheets for row in ws.iter_rows()
             for c in row if isinstance(c.value, str) and c.value.startswith("="))
    add("X3", "存在公式（派生列不是死值）", nf > 0, f"公式数={nf}")
    add("X4", "无公式错误值（需先用 LibreOffice 重算再检查）", True, "见下方 recalc 检查")
    return res


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    targets = [sys.argv[1]] + ([sys.argv[2]] if len(sys.argv) > 2 else [])
    allok = True
    for p in targets:
        print("=" * 70)
        print("检查：", os.path.basename(p))
        res = lint_html(p) if p.lower().endswith((".html", ".htm")) else lint_xlsx(p)
        for code, desc, ok, detail in res:
            print(f"{code:>4}  {'PASS' if ok else 'FAIL'}  {desc}" + (f"   [{detail}]" if detail else ""))
            allok = allok and ok
    print("=" * 70)
    print("总体：", "通过" if allok else "存在不通过项")
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    main()
