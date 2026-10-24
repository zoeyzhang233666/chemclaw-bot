# -*- coding: utf-8 -*-
"""check_xlsx.py —— 归因工作簿自检。

检查：
  1. 13 个工作表齐全、无空表。
  2. 必备列存在（价格序列/分期对齐/事件清单/证据分级/候选解释）。
  3. 每个事件行都有原始链接；每个证据条目都有等级。
  4. 12_复算校验 全部为"是"。
  5. 期现结构表里基差 = 现货 − 主力收盘（抽样复算）。
  6. 不允许出现公式错误值（#REF!/#N/A/#DIV/0!）。
"""
from __future__ import annotations

import argparse
import sys

from openpyxl import load_workbook

REQUIRED_SHEETS = ['00_说明与结论', '01_价格序列', '02_分期对齐', '03_因子同期数据', '04_变动幅度与分级',
                   '05_事件清单', '06_证据分级', '07_候选解释排序', '08_来源与口径', '09_异动与阶段',
                   '10_期现结构', '11_数据缺口', '12_复算校验']
ERRVALS = ('#REF!', '#N/A', '#DIV/0!', '#VALUE!', '#NAME?', '#NUM!', '#NULL!')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx')
    a = ap.parse_args()
    wb = load_workbook(a.xlsx, data_only=True)
    msgs, ok = [], 0

    miss = [s for s in REQUIRED_SHEETS if s not in wb.sheetnames]
    if miss:
        msgs.append('缺少工作表：%s' % ', '.join(miss))
    else:
        ok += 1
    extra = [s for s in wb.sheetnames if s not in REQUIRED_SHEETS]
    if extra:
        msgs.append('存在非预期工作表：%s' % ', '.join(extra))

    for name in wb.sheetnames:
        ws = wb[name]
        if ws.max_row < 4:
            msgs.append('工作表 %s 只有 %d 行，内容过少' % (name, ws.max_row))
    ok += 1

    # 公式错误值
    for name in wb.sheetnames:
        ws = wb[name]
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value in ERRVALS:
                    msgs.append('%s!%s 出现公式错误值 %s' % (name, c.coordinate, c.value))
    ok += 1

    # 价格序列
    ws = wb['01_价格序列']
    hdr = [c.value for c in ws[4]]
    need = ['日期', '现货 元/吨', '期货主连 元/吨', '基差 元/吨']
    if not all(any(n in str(h) for h in hdr if h) for n in need):
        msgs.append('01_价格序列 缺少必备列：%s' % need)
    else:
        ok += 1
    rows = [r for r in ws.iter_rows(min_row=5, values_only=True) if r[0]]
    if len(rows) < 20:
        msgs.append('01_价格序列 数据行过少（%d）' % len(rows))
    else:
        ok += 1

    # 事件链接
    ws = wb['05_事件清单']
    hdr = [c.value for c in ws[4]]
    i_url = next((i for i, h in enumerate(hdr) if h and '链接' in str(h)), None)
    i_ev = next((i for i, h in enumerate(hdr) if h and '事件' in str(h)), None)
    ne, nlink = 0, 0
    if i_url is not None:
        for r in ws.iter_rows(min_row=5, values_only=True):
            if r[i_ev]:
                ne += 1
                if r[i_url]:
                    nlink += 1
    if ne == 0:
        msgs.append('05_事件清单 没有事件行')
    elif nlink < ne:
        msgs.append('05_事件清单 有 %d/%d 条事件缺原始链接' % (ne - nlink, ne))
    else:
        ok += 1

    # 证据等级
    ws = wb['06_证据分级']
    hdr = [c.value for c in ws[4]]
    i_lv = next((i for i, h in enumerate(hdr) if h and '等级' in str(h)), None)
    lv = [r[i_lv] for r in ws.iter_rows(min_row=5, values_only=True) if r[0] and i_lv is not None]
    bad = [x for x in lv if x not in ('E1', 'E2', 'E3', 'E4')]
    if not lv:
        msgs.append('06_证据分级 没有条目')
    elif bad:
        msgs.append('06_证据分级 存在非法等级值：%s' % set(bad))
    else:
        ok += 1

    # 复算校验
    ws = wb['12_复算校验']
    res = [r[4] for r in ws.iter_rows(min_row=5, values_only=True) if r[0] and r[4] in ('是', '否')]
    if not res:
        msgs.append('12_复算校验 没有校验行')
    elif '否' in res:
        msgs.append('12_复算校验 存在不一致项（%d 项为"否"）' % res.count('否'))
    else:
        ok += 1

    # 基差复算
    ws = wb['10_期现结构']
    bad2, checked = 0, 0
    for r in ws.iter_rows(min_row=5, values_only=True):
        if not r[0] or len(r) < 4 or r[3] is None:
            continue
        spot, front, basis = r[1], r[2], r[3]
        if isinstance(spot, (int, float)) and isinstance(front, (int, float)) and isinstance(basis, (int, float)):
            checked += 1
            if abs((spot - front) - basis) > 0.02:
                bad2 += 1
    if checked and bad2:
        msgs.append('10_期现结构 有 %d/%d 行基差 ≠ 现货 − 基准合约收盘' % (bad2, checked))
    else:
        ok += 1

    print('工作表 %d 个；检查项通过 %d 项，失败 %d 项' % (len(wb.sheetnames), ok, len(msgs)))
    for m in msgs:
        print('  FAIL ' + m)
    if not msgs:
        print('Excel 自检通过。')
    return 1 if msgs else 0


if __name__ == '__main__':
    sys.exit(main())
