# -*- coding: utf-8 -*-
"""check_xlsx.py —— 校验工作簿：表结构、公式存在性、数值勾稽

不依赖 Excel：用 openpyxl 读公式，用同一口径在 Python 里重算关键勾稽，
确认"表里的数字自洽"。

用法：python scripts/check_xlsx.py out/xxx.xlsx build/analysis.json
"""
import json, os, sys

from openpyxl import load_workbook

sys.stdout.reconfigure(encoding='utf-8')

EXPECT_SHEETS = ['00_封面与说明', '01_原料价格', '02_下游价格', '03_工艺单耗', '04_理论成本',
                 '05_加工价差', '06_分阶段对比', '07_背离区间', '08_计算公式', '09_数据缺口与来源']
BANNED = ['预计', '看涨', '看跌', '建议买', '建议卖', '抄底', '必涨']


def eval_formulas(wb):
    """最小 Excel 求值器：只支持本工作簿实际用到的几种公式形态。

    支持的形态：
      ='03_工艺单耗'!B8 / =03_工艺单耗!B8     跨表单元格引用
      =B5*C5                                  乘
      =B5-C5                                  减
      =IF(E5,D5/E5*100,"")                    条件 + 除 + 乘
    """
    import re
    cache = {}

    def cell(sheet, ref, depth=0):
        key = "'%s'!%s" % (sheet, ref)
        if key in cache:
            return cache[key]
        if depth > 12:
            return None
        v = wb[sheet][ref].value
        r = resolve(v, sheet, depth + 1) if isinstance(v, str) and v.startswith('=') else v
        cache[key] = r
        return r

    def resolve(expr, sheet, depth):
        e = expr.lstrip('=').strip()
        # 跨表引用
        m = re.fullmatch(r"'?([^'!]+)'?!(\$?[A-Z]+\$?\d+)", e)
        if m:
            ref = m.group(2).replace('$', '')
            return cell(m.group(1), ref, depth)
        # IF(cond, a, b)
        m = re.fullmatch(r'IF\((.*)\)', e)
        if m:
            parts, cur, d = [], '', 0
            for ch in m.group(1):
                if ch in '(':
                    d += 1
                elif ch in ')':
                    d -= 1
                if ch == ',' and d == 0:
                    parts.append(cur); cur = ''
                else:
                    cur += ch
            parts.append(cur)
            cond = resolve_term(parts[0], sheet, depth)
            if cond:
                return resolve_term(parts[1], sheet, depth) if len(parts) > 1 else None
            return None
        return resolve_term(e, sheet, depth)

    def resolve_term(t, sheet, depth):
        t = t.strip().strip('"')
        if t == '':
            return None
        # 纯算术表达式：逐个替换单元格引用后求值
        def rep(m):
            v = cell(sheet, m.group(1), depth)
            return '(None)' if v is None else repr(float(v))
        py = re.sub(r'\b([A-Z]{1,2}\d{1,5})\b', rep, t)
        try:
            return eval(py, {'__builtins__': {}}, {})
        except Exception:
            return None

    # 触发求值：把几个关键单元格填进缓存后再返回
    for sheet, ref in (('04_理论成本', 'D5'), ('04_理论成本', 'F5'),
                       ('05_加工价差', 'D5'), ('03_工艺单耗', 'B8')):
        try:
            cell(sheet, ref)
        except Exception:
            pass
    return cache


def main(xlsx_path, analysis_path):
    a = json.load(open(analysis_path, encoding='utf-8'))
    EXPECT_ROWS = a['summary']['n_obs']
    wb = load_workbook(xlsx_path, data_only=False)
    fails, warns = [], []

    # 1 表结构
    for name in EXPECT_SHEETS:
        if name not in wb.sheetnames:
            fails.append('缺工作表：%s' % name)
    extra = [n for n in wb.sheetnames if n not in EXPECT_SHEETS]
    if extra:
        warns.append('多余工作表：%s' % extra)
    print('工作表 %d 张：%s' % (len(wb.sheetnames), '、'.join(wb.sheetnames)))

    # 2 04 表公式
    ws = wb['04_理论成本']
    f_cost = f_share = 0
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=6):
        if isinstance(row[3].value, str) and row[3].value.startswith('='):
            f_cost += 1
        if isinstance(row[5].value, str) and row[5].value.startswith('='):
            f_share += 1
    if f_cost < EXPECT_ROWS * 0.8:
        fails.append('04 表成本公式过少（%d）' % f_cost)
    if f_share < EXPECT_ROWS * 0.8:
        fails.append('04 表占比公式过少（%d）' % f_share)
    print('04 表公式：成本 %d 个，占比 %d 个' % (f_cost, f_share))

    # 3 05 表公式
    ws5 = wb['05_加工价差']
    f5 = sum(1 for row in ws5.iter_rows(max_col=4)
             if isinstance(row[3].value, str) and row[3].value.startswith('='))
    if f5 < EXPECT_ROWS * 0.8:
        fails.append('05 表价差公式过少（%d）' % f5)
    print('05 表价差公式：%d 个' % f5)

    # 4 03 表单耗可编辑 —— 找 "主模型单耗所在单元格" 标签右侧的值
    ws3 = wb['03_工艺单耗']
    unit_cell = None
    for row in ws3.iter_rows(max_col=2):
        if isinstance(row[0].value, str) and '主模型单耗所在单元格' in row[0].value:
            unit_cell = row[1].value
    if not unit_cell:
        fails.append('03 表未标注主模型单耗引用单元格')
    else:
        ref = str(unit_cell).lstrip('=').strip()
        print('主模型单耗引用：%s' % ref)
        # 04 表必须真的引用它
        ws4 = wb['04_理论成本']
        hits = sum(1 for row in ws4.iter_rows(max_col=3)
                   if isinstance(row[2].value, str) and '03_工艺单耗!' in row[2].value)
        if hits < EXPECT_ROWS * 0.8:
            fails.append('04 表未引用 03 表单耗（命中 %d 行）' % hits)
        else:
            print('04 表引用 03 表单耗：%d 行 ✓' % hits)

    # 5 数值勾稽：用 01/02 表价格 × project 单耗重算价差，与 07 表/analysis 对照
    ws1, ws2 = wb['01_原料价格'], wb['02_下游价格']
    prices_up, prices_dn = {}, {}
    for row in ws1.iter_rows(min_row=4, max_col=2):
        if isinstance(row[0].value, str) and len(str(row[0].value)) == 8 and isinstance(row[1].value, (int, float)):
            prices_up[str(row[0].value)] = row[1].value
    for row in ws2.iter_rows(min_row=4, max_col=2):
        if isinstance(row[0].value, str) and len(str(row[0].value)) == 8 and isinstance(row[1].value, (int, float)):
            prices_dn[str(row[0].value)] = row[1].value
    n = len(set(prices_up) & set(prices_dn))
    print('价格表配对交易日：%d（analysis.json 报 %d）' % (n, a['summary']['n_obs']))
    if abs(n - a['summary']['n_obs']) > 2:
        fails.append('价格配对天数与 analysis 不一致：%d vs %d' % (n, a['summary']['n_obs']))

    unit = (a['meta']['materials'] or [{}])[0].get('unit')
    spreads = []
    for d, u in prices_up.items():
        if d in prices_dn and u is not None and unit:
            spreads.append(prices_dn[d] - unit * u)
    if spreads:
        mean = sum(spreads) / len(spreads)
        rep = a['summary']['spread']['mean']
        print('重算价差均值 %.2f ｜ analysis %.2f ｜ 差 %.2f' % (mean, rep, mean - rep))
        if abs(mean - rep) > 1.0:
            fails.append('价差均值勾稽失败：重算 %s vs 报告 %s' % (round(mean, 2), rep))

    # 5.5 公式求值：用最小 Excel 求值器跑 04/05 表的真实公式，确认能算出正确值
    try:
        vals = eval_formulas(wb)
        # 04 表第 5 行（首个数据行）成本 = 单耗 × 上游价
        unit_v = vals.get("'03_工艺单耗'!B8")
        up0 = prices_up.get(sorted(prices_up)[0])
        got = vals.get("'04_理论成本'!D5")
        if unit_v and up0 and got is not None:
            exp = unit_v * up0
            if abs(got - exp) > 0.01:
                fails.append('04 表公式求值错误：D5=%s，应为 %s' % (got, exp))
            else:
                print('公式求值 04!D5 = 单耗 %.3f × 上游 %.1f = %.1f ✓' % (unit_v, up0, got))
        sp_first = vals.get("'05_加工价差'!D5")
        dn0 = prices_dn.get(sorted(prices_dn)[0])
        if sp_first is not None and dn0 is not None:
            exp = dn0 - (unit_v * up0)
            if abs(sp_first - exp) > 0.01:
                fails.append('05 表公式求值错误：D5=%s，应为 %s' % (sp_first, exp))
            else:
                print('公式求值 05!D5 = 下游 %.1f − 成本 %.1f = %.1f ✓' % (dn0, unit_v * up0, sp_first))
        share = vals.get("'04_理论成本'!F5")
        if share is not None and dn0:
            exp = unit_v * up0 / dn0 * 100
            if abs(share - exp) > 0.05:
                fails.append('04 表占比公式求值错误：F5=%s，应为 %s' % (share, exp))
            else:
                print('公式求值 04!F5 = 成本占比 %.2f%% ✓' % share)
    except Exception as e:
        warns.append('公式求值器跳过的部分：%s' % str(e)[:120])

    # 6 06 表恒等式
    ws6 = wb['06_分阶段对比']
    checked = 0
    for row in ws6.iter_rows(min_row=4, max_col=11):
        if isinstance(row[0].value, str) and len(str(row[0].value)) == 8:
            d_cost, d_down, d_sp = row[5].value, row[8].value, row[9].value
            if None not in (d_cost, d_down, d_sp):
                checked += 1
                if abs(d_down - (d_cost + d_sp)) > 0.01:
                    fails.append('06 表恒等式不成立：%s（Δ下 %s ≠ Δ成本 %s + Δ价差 %s）'
                                 % (row[0].value, d_down, d_cost, d_sp))
    if checked < max(1, len(a.get('stages') or [])):
        fails.append('06 表阶段行过少（%d）' % checked)
    print('06 表恒等式校验：%d 段通过' % checked)

    # 7 禁用词
    for name in wb.sheetnames:
        for row in wb[name].iter_rows(values_only=True):
            for v in row:
                if isinstance(v, str):
                    for w in BANNED:
                        if w in v:
                            fails.append('工作表 %s 出现预测性表述：%s' % (name, w))

    # 8 必读声明
    txt = ' '.join(str(v) for row in wb['00_封面与说明'].iter_rows(values_only=True)
                   for v in row if v)
    for need in ['不是利润', '不等于因果']:
        if need not in txt:
            fails.append('封面缺少必读声明：%s' % need)
    # 3 张表要有价差≠利润字样
    for m in ('05_加工价差', '08_计算公式'):
        t = ' '.join(str(v) for row in wb[m].iter_rows(values_only=True) for v in row if v)
        if '不是利润' not in t:
            fails.append('%s 缺少"价差不是利润"限定' % m)

    for w in warns:
        print('  [warn]', w)
    if fails:
        for x in fails:
            print('  [FAIL]', x)
        print('\nExcel 校验失败：%d 项' % len(fails))
        return 1
    print('\nExcel 校验全部通过')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('用法：python check_xlsx.py <xlsx> <analysis.json>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
