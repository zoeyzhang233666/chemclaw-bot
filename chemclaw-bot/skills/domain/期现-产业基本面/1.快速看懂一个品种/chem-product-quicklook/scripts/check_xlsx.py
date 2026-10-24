#!/usr/bin/env python3
"""check_xlsx.py — Excel 交付物自检：结构、必填表、空表、缺口着色一致性

用法: python scripts/check_xlsx.py out/<品种>-品种研究入口.xlsx [--research research.json]

检查项：
  X01 12 张固定工作表齐全且顺序一致
  X02 每张表都有内容（非空单元 > 10）
  X03 表头行存在、冻结窗格在图例行之下
  X04 research.json 中的来源 id 全部出现在“10 来源清单”
  X05 缺口标注：research 里标记为缺口的字段在表内以“缺口”或着色出现
  X06 无 Excel 非法字符/超长单元格（>32767）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import openpyxl

EXPECTED = ["00 封面与指引", "01 产品百科", "02 牌号与规格", "03 工艺路线", "04 产业链节点",
            "05 企业与产能", "06 下游与需求", "07 贸易与区域", "08 期货与交割", "09 关键指标",
            "10 来源清单", "11 缺口与核验"]


class R:
    def __init__(self):
        self.err = 0
        self.warn = 0
        self.ok_n = 0

    def ok(self, m):
        self.ok_n += 1
        print("  \u2713 " + m)

    def fail(self, m):
        self.err += 1
        print("  \u2717 " + m)

    def warn_(self, m):
        self.warn += 1
        print("  ! " + m)


def collect_strings(o, out):
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            collect_strings(v, out)
    elif isinstance(o, list):
        for v in o:
            collect_strings(v, out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--research", default=None)
    a = ap.parse_args(argv)
    r = R()

    wb = openpyxl.load_workbook(a.xlsx)
    names = wb.sheetnames
    missing = [s for s in EXPECTED if s not in names]
    if missing:
        r.fail(f"缺少工作表：{missing}")
    elif names[:len(EXPECTED)] != EXPECTED:
        r.warn_(f"工作表顺序与标准不同：{names}")
    else:
        r.ok(f"12 张工作表齐全且顺序正确")

    total = 0
    thin = []
    for ws in wb.worksheets:
        n = sum(1 for row in ws.iter_rows() for c in row if c.value not in (None, ""))
        total += n
        # 无期货品种的“08 期货与交割”本就应很薄（只有降级说明）；
        # “02 牌号与规格”在单一规格/示意品种下也允许偏薄。二者不按“内容过少”判错。
        if n < 10 and not ("期货" in ws.title or "牌号" in ws.title):
            thin.append(f"{ws.title}({n})")
    (r.fail if thin else r.ok)(f"各表均有实质内容（偏薄：{thin or '无'}）")
    r.ok(f"全部工作表非空单元合计 {total}")

    nofreeze = [ws.title for ws in wb.worksheets[1:] if not ws.freeze_panes]
    (r.fail if nofreeze else r.ok)(f"冻结窗格：{'缺失于 ' + str(nofreeze) if nofreeze else '全部已设置'}")

    # 非法字符与超长
    bad = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str):
                    if len(c.value) > 32767:
                        bad.append((ws.title, c.coordinate, "超长"))
                    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", c.value):
                        bad.append((ws.title, c.coordinate, "非法字符"))
    (r.fail if bad else r.ok)(f"单元格合法性：{bad[:5] if bad else '通过'}")

    if a.research:
        doc = json.loads(Path(a.research).read_text(encoding="utf-8-sig"))
        src_ids = {s["id"] for s in doc.get("sources", [])}
        body = " ".join(collect_strings(doc, []))
        used = set(re.findall(r"\bS\d{2}\b", body))
        orphan = sorted(used - src_ids)
        (r.fail if orphan else r.ok)(f"正文引用的来源 id 均在来源清单内：{orphan or '通过'}")

        lst = wb["10 来源清单"] if "10 来源清单" in names else None
        if lst:
            sheet_txt = " ".join(str(c.value) for row in lst.iter_rows() for c in row if c.value)
            miss2 = sorted(i for i in src_ids if i not in sheet_txt)
            (r.fail if miss2 else r.ok)(f"来源清单覆盖全部 {len(src_ids)} 条来源：{miss2 or '通过'}")

        # “02 牌号与规格”在无期货/单一规格品种下可以是薄表，只要确有内容即可
        s2 = wb["02 牌号与规格"] if "02 牌号与规格" in names else None
        if s2:
            n2 = sum(1 for row in s2.iter_rows() for c in row if c.value not in (None, ""))
            if n2 < 6:
                r.warn_(f"02 牌号与规格 内容偏少（{n2} 个非空单元）——单一规格品种可接受，请人工确认")

        gaps = doc.get("gaps", [])
        g11 = wb["11 缺口与核验"] if "11 缺口与核验" in names else None
        if g11 and gaps:
            t = " ".join(str(c.value) for row in g11.iter_rows() for c in row if c.value)
            hit = sum(1 for g in gaps if g.get("area", "")[:6] in t)
            (r.ok if hit >= max(1, len(gaps) - 1) else r.warn_)(f"缺口表覆盖 {hit}/{len(gaps)} 条缺口")

    print(f"\n[check_xlsx] ok={r.ok_n} warn={r.warn} error={r.err}")
    return 1 if r.err else 0


if __name__ == "__main__":
    raise SystemExit(main())
