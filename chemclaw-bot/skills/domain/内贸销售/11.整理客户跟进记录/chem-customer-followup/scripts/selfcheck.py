# -*- coding: utf-8 -*-
"""
selfcheck.py — 交付前自检（数据 + Excel + HTML 三项一起查）

用法：
    python selfcheck.py followup.json [--outdir examples/xxx]

检查：
  1. 数据：_common.validate + 停滞天数/逾期承诺自洽
  2. Excel：能被 openpyxl 打开、工作表数、每个表非空、行高是否够放文字
  3. HTML：标签闭合、id 唯一、时间线条数 = 数据条数、必需区块存在
无 openpyxl 时跳过第 2 项（只报 SKIP），不中断。
"""
import argparse
import json
import math
import os
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (
    validate, parse_as_of, compute_stall_days, promise_state, cjk_len,
)

VOID = {"meta", "link", "br", "hr", "img", "input", "source", "area",
        "base", "col", "embed", "param", "track", "wbr"}


class _Chk(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errs = [], []
        self.ids, self.dupes = set(), []
        self.tags = 0

    def handle_starttag(self, tag, attrs):
        self.tags += 1
        d = dict(attrs)
        if "id" in d:
            if d["id"] in self.ids:
                self.dupes.append(d["id"])
            self.ids.add(d["id"])
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errs.append(f"多余闭合 </{tag}>")
            return
        if self.stack[-1] == tag:
            self.stack.pop()
        else:
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i] == tag:
                    self.errs.append(f"未闭合 {self.stack[i+1:]} 于 </{tag}>")
                    del self.stack[i:]
                    break
            else:
                self.errs.append(f"孤立闭合 </{tag}>")


def check_html(path, data):
    errs, warns = [], []
    raw = open(path, encoding="utf-8").read()
    p = _Chk()
    p.feed(raw)
    if p.stack:
        errs.append(f"HTML 未闭合标签：{p.stack}")
    errs += p.errs[:5]
    if p.dupes:
        errs.append(f"HTML 重复 id：{set(p.dupes)}")
    n = len(data.get("timeline") or [])
    got = raw.count('class="tl-item"')
    if got != n:
        errs.append(f"HTML 时间线条数 {got} ≠ 数据 {n}")
    for need in ("客户明确需求", "客户异议", "我方承诺", "待确认", "AI 推断", "下一步动作"):
        if need not in raw:
            warns.append(f"HTML 缺少区块关键词：{need}")
    if "font-family" not in raw:
        warns.append("HTML 未设置字体栈，跨机器显示可能不一致")
    return errs, warns, {"tags": p.tags, "ids": len(p.ids), "bytes": len(raw.encode("utf-8"))}


def check_xlsx(path, data):
    try:
        from openpyxl import load_workbook
        from openpyxl.utils import get_column_letter
    except ImportError:
        return [], ["未安装 openpyxl，跳过 Excel 校验"], {}

    errs, warns = [], []
    wb = load_workbook(path)
    n_tl = len(data.get("timeline") or [])
    if len(wb.sheetnames) < 10:
        warns.append(f"工作表数 {len(wb.sheetnames)} < 10（预期 10 表）")
    for ws in wb.worksheets:
        if ws.max_row < 2:
            errs.append(f"工作表 {ws.title} 内容为空")

    # 时间线条数
    if "01_时间线" in wb.sheetnames:
        ws = wb["01_时间线"]
        got = ws.max_row - 4
        if got != n_tl:
            errs.append(f"Excel 时间线条数 {got} ≠ 数据 {n_tl}")

    # 行高是否够放文字（合并单元格感知）
    clipped = 0
    for ws in wb.worksheets:
        merged_w = {}
        for rng in ws.merged_cells.ranges:
            w = sum(ws.column_dimensions[get_column_letter(c)].width or 8.43
                    for c in range(rng.min_col, rng.max_col + 1))
            merged_w[(rng.min_row, rng.min_col)] = w
        for row in ws.iter_rows():
            r = row[0].row
            h = ws.row_dimensions[r].height
            if not h:
                continue
            need = 1
            for c in row:
                if c.value is None:
                    continue
                w = merged_w.get((c.row, c.column)) or \
                    (ws.column_dimensions[get_column_letter(c.column)].width or 8.43)
                sz = c.font.size or 10
                per = max(4, int(w * 0.94 * (10.0 / sz)))
                need = max(need, math.ceil(cjk_len(c.value) / per))
            if need * 15.6 + 5 > h + 2.5:
                clipped += 1
    if clipped:
        warns.append(f"{clipped} 行可能裁切文字（建议调大行高或列宽）")

    return errs, warns, {"sheets": len(wb.sheetnames), "rows": sum(ws.max_row for ws in wb.worksheets)}


def main():
    ap = argparse.ArgumentParser(description="跟进卡交付前自检")
    ap.add_argument("input", help="followup.json")
    ap.add_argument("--outdir", default=None, help="输出目录（默认 input.json 所在目录）")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8-sig") as f:
        data = json.load(f)

    outdir = args.outdir or os.path.dirname(os.path.abspath(args.input))
    slug = (data.get("meta") or {}).get("slug") or "followup_card"
    xlsx_path = os.path.join(outdir, f"{slug}.xlsx")
    html_path = os.path.join(outdir, f"{slug}.html")

    as_of = parse_as_of((data.get("meta") or {}).get("as_of_date"))
    errors, warnings = validate(data, as_of)
    days, last = compute_stall_days(data.get("timeline") or [], as_of)
    overdue = [p for p in (data.get("promises") or [])
               if promise_state(p, as_of)[1] == "risk"]

    print(f"数据：as_of={as_of}　停滞 {days if days is not None else '—'} 天　"
          f"逾期承诺 {len(overdue)} 项　记录 {len(data.get('timeline') or [])} 条")

    all_err = list(errors)
    all_warn = list(warnings)

    if os.path.exists(xlsx_path):
        e, w, info = check_xlsx(xlsx_path, data)
        all_err += e
        all_warn += w
        print(f"Excel：{info}")
    else:
        all_warn.append(f"未找到 {os.path.basename(xlsx_path)}（先运行 build_followup.py）")

    if os.path.exists(html_path):
        e, w, info = check_html(html_path, data)
        all_err += e
        all_warn += w
        print(f"HTML ：{info}")
    else:
        all_warn.append(f"未找到 {os.path.basename(html_path)}（先运行 build_followup.py）")

    print("\n── 结果 ──")
    if not all_err and not all_warn:
        print("  [pass] 全部检查通过")
    for e in all_err:
        print(f"  [error] {e}")
    for w in all_warn:
        print(f"  [warn ] {w}")
    sys.exit(1 if all_err else 0)


if __name__ == "__main__":
    main()
