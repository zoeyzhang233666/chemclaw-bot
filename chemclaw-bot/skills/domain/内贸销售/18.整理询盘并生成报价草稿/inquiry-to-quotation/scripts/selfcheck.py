# -*- coding: utf-8 -*-
"""交付前自检：字段 JSON、工作台 HTML、Excel 工作簿、报价草稿四条线一起过。

    python selfcheck.py <fields.json> [--html 工作台.html] [--xlsx 报价工作簿.xlsx] [--quote 报价草稿.md]

退出码 0 = 全绿；1 = 有 FAIL；2 = 文件缺失。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

OK, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "", level_when_bad: str = FAIL) -> None:
    results.append((OK if ok else level_when_bad, name, detail))


def check_doc(doc: dict) -> None:
    keys = set(doc["fields"].keys())
    check("字段齐 10 项", keys == set(C.FIELD_KEYS), f"多/少：{keys ^ set(C.FIELD_KEYS)}")
    for key in C.FIELD_KEYS:
        row = doc["fields"][key]
        check(f"分桶正确：{row['label']}", row["bucket"] == C.FIELD_BUCKET[key], row["bucket"])
        if row["bucket"] == "must":
            v = (row.get("value") or "").strip()
            if not v:
                check(f"缺失标记：{row['label']}", row["status"] in ("missing", "tbc"),
                      f"空值却是 {row['status']}")
            else:
                check(f"有值有出处：{row['label']}", bool((row.get("source") or "").strip()) or row["status"] == "tbc",
                      "缺出处", WARN)
    # 价格红线
    price = doc.get("price", {})
    if not str(price.get("ack") or "").strip():
        check("未确认时不得带价格", not price.get("unit_price"), f"未 ack 却有单价 {price.get('unit_price')}")
    check("字段表里没有价格字段", not any("price" in k or "单价" in C.FIELD_LABEL.get(k, "") for k in C.FIELD_KEYS),
          "", WARN)
    check("无占位符残留", "__DATA__" not in json.dumps(doc, ensure_ascii=False), "", WARN)
    bl = C.blockers(doc)
    check("闸门清单可计算", isinstance(bl, list), f"{len(bl)} 项")


def check_html(path: Path) -> None:
    html = path.read_text(encoding="utf-8", errors="replace")
    for needle, name in [
        ("上传询盘素材", "上传区"),
        ("必须补充后才能报价", "A 类分桶"),
        ("可先按假设准备", "B 类分桶"),
        ("生成报价草稿", "生成按钮"),
        ("我确认", "价格确认勾选"),
        ("待你填写", "单价留空提示"),
        ("不生成、不推荐、不调整任何商业价格", "价格红线文案"),
    ]:
        check(f"HTML 含「{name}」", needle in html)
    check("HTML 无未替换占位符", "__DATA__" not in html and "__TITLE__" not in html)
    data = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    if data:
        try:
            doc = json.loads(data.group(1))
            check("HTML 内嵌数据可解析", True, f"{len(doc['fields'])} 字段")
            price = doc.get("price", {})
            check("HTML 内嵌数据不含价格", not price.get("unit_price"), str(price.get("unit_price")))
        except json.JSONDecodeError as e:
            check("HTML 内嵌数据可解析", False, str(e))
    else:
        check("HTML 内嵌数据可解析", False, "找不到 <script id=data>")


def check_xlsx(path: Path) -> None:
    try:
        from openpyxl import load_workbook
    except ImportError:
        check("openpyxl 可用", False, "跳过 Excel 校验", WARN)
        return
    wb = load_workbook(path)
    want = ["01 询盘概要", "02 字段确认表", "03 缺失与假设", "04 价格与口径", "05 报价草稿",
            "06 口径与边界", "07 素材与证据"]
    check("Excel 7 个工作表", [s.title for s in wb.worksheets] == want, str([s.title for s in wb.worksheets]))
    s4 = wb["04 价格与口径"]
    check("04 单价单元格为空（价格不由系统填）", s4["C6"].value in (None, ""), str(s4["C6"].value))
    s5 = wb["05 报价草稿"]
    formulas = [str(c.value) for row in s5.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
    joined = " ".join(formulas)
    check("05 单价引用 04 表", "04 价格与口径" in joined and "$C$6" in joined, "", WARN)
    check("05 未确认时显示「待填单价」", any("待填单价" in f for f in formulas))
    check("05 有合计行公式", any("$C$22" in f for f in formulas), "", WARN)
    s2 = wb["02 字段确认表"]
    statuses = [s2.cell(row=r, column=8).value for r in range(4, 18)]
    check("02 状态列有下拉/值", any(statuses), f"{statuses[:6]}")
    s3 = wb["03 缺失与假设"]
    check("03 有 A/B 两类分桶", any("必须补充" in str(c.value or "") for row in s3.iter_rows() for c in row)
          and any("可先按假设" in str(c.value or "") for row in s3.iter_rows() for c in row))


def check_quote(path: Path) -> None:
    md = path.read_text(encoding="utf-8")
    for sec in ["一、商品明细", "二、价格与口径", "三、交付条件", "四、付款条件",
                "五、质量与验收", "六、报价有效期", "七、待客户确认事项", "八、备注"]:
        check(f"报价含「{sec}」", sec in md)
    check("报价写明单价", bool(re.search(r"\d[\d,]*\.\d{2}", md)))
    check("报价有生成说明", "生成说明" in md)
    check("报价未出现模板占位符", "{{" not in md)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="询盘→报价 交付前自检")
    ap.add_argument("fields")
    ap.add_argument("--html", default=None)
    ap.add_argument("--xlsx", default=None)
    ap.add_argument("--quote", default=None)
    args = ap.parse_args(argv)

    doc = C.load_doc(args.fields)
    check_doc(doc)
    for path, fn in [(args.html, check_html), (args.xlsx, check_xlsx), (args.quote, check_quote)]:
        if not path:
            continue
        p = Path(path)
        if p.exists():
            fn(p)
        else:
            check(f"文件存在：{p.name}", False, str(p), WARN)

    fails = [r for r in results if r[0] == FAIL]
    for status, name, detail in results:
        mark = {"PASS": "✔", "FAIL": "✖", "WARN": "!"}[status]
        show = detail if (detail and status != OK) else ""
        print(f"  {mark} {name}" + (f"　{show}" if show else ""))
    print(f"\n合计 {len(results)} 项：{len(results)-len(fails)} 通过，{len(fails)} 失败")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
