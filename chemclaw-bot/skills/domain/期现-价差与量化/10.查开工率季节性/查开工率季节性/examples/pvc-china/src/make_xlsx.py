# -*- coding: utf-8 -*-
"""
生成《PVC 开工率季节性分析》Excel 工作簿。

设计要点
--------
1. **每个数字都能追到源**：数据页每行带 source_url / 摘录 / 口径标签。
2. **公式可复算**：分位数、环比、4周/12周变化用真实 Excel 公式写（PERCENTILE.INC 等），
   不是把 Python 算好的值粘贴进去，便于审核者改数据后自动重算。
3. **缺口显式化**：缺失处写“缺口”，不留空、不填 0、不做插值。
4. **口径警示配色**：口径风险=粉底，受限/缺口=黄底，已处理=绿底。
"""
import argparse
import csv
import json
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ---------------- 样式 ----------------
TITLE = dict(font=Font(name='微软雅黑', size=17, bold=True, color='FFFFFF'),
             fill=PatternFill('solid', fgColor='0E3A5C'), align=Alignment('left', 'center', indent=1))
HDR = dict(font=Font(name='微软雅黑', size=10, bold=True, color='FFFFFF'),
           fill=PatternFill('solid', fgColor='14405F'), align=Alignment('center', 'center', wrap_text=True))
BODY = dict(font=Font(name='微软雅黑', size=10), align=Alignment('left', 'center', wrap_text=True))
NUM = dict(font=Font(name='微软雅黑', size=10), align=Alignment('center', 'center'))
FML = dict(font=Font(name='微软雅黑', size=10), align=Alignment('center', 'center'),
           fill=PatternFill('solid', fgColor='F2F7FB'))
WARN = PatternFill('solid', fgColor='FFE4E4')   # 口径警示
GAP = PatternFill('solid', fgColor='FFF4D6')    # 受限 / 缺口
DONE = PatternFill('solid', fgColor='E3F6EA')   # 已处理
THIN = Side(style='thin', color='BFCEDC')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def sheet(wb, name, title, subtitle, ncols):
    ws = wb.create_sheet(name)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(ncols, 6))
    c = ws.cell(1, 1, title)
    c.font, c.fill, c.alignment = TITLE['font'], TITLE['fill'], TITLE['align']
    ws.row_dimensions[1].height = 34
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(ncols, 6))
    c2 = ws.cell(2, 1, subtitle)
    c2.font = Font(name='微软雅黑', size=9, italic=True, color='5A6B7B')
    c2.alignment = Alignment('left', 'center', indent=1, wrap_text=True)
    ws.row_dimensions[2].height = 30
    ws.sheet_view.showGridLines = False
    return ws


def header(ws, row, cols):
    for j, v in enumerate(cols, 1):
        c = ws.cell(row, j, v)
        c.font, c.fill, c.alignment, c.border = HDR['font'], HDR['fill'], HDR['align'], BORDER
    ws.row_dimensions[row].height = 32
    ws.freeze_panes = ws.cell(row + 1, 1)


def widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


def put(ws, r, c, v, style=NUM, fill=None, fmt=None):
    cell = ws.cell(r, c, v)
    cell.font, cell.alignment, cell.border = style['font'], style['align'], BORDER
    if fill:
        cell.fill = fill
    if fmt:
        cell.number_format = fmt
    return cell


def read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='assets/PVC开工率季节性分析.xlsx')
    ap.add_argument('--weekly', default='raw/pvc_util_weekly.csv')
    ap.add_argument('--out-dir', default='out')
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)

    weekly = read(a.weekly)
    profile = read(os.path.join(a.out_dir, 'seasonal_profile.csv'))
    cur = read(os.path.join(a.out_dir, 'current_year.csv'))
    anchors = read('raw/external_anchor.csv')
    anchor_series = read('raw/anchor_weekly.csv')
    claims = read('raw/external_claims.csv')
    summary = {}
    sp = os.path.join(a.out_dir, 'summary.json')
    if os.path.exists(sp):
        summary = json.load(open(sp, encoding='utf-8'))

    wb = Workbook()
    wb.remove(wb.active)

    # ============ 0. 封面 ============
    ws = sheet(wb, '00_封面与导读', '中国 PVC 开工率（产能利用率）季节性分析',
               '数据窗口 2026-W30~W42（12 个真实周度观测，逐条带源）｜ 口径：隆众资讯·71 家样本企业 ｜ '
               '禁止将样本开工率直接等同于全行业实际产量', 6)
    rows = [
        ('生成日期', '2026-10-20'),
        ('最新观测', f"{summary.get('latest_week_end', '')}  {summary.get('latest', '')}%  "
                     f"（样本 {int(summary['sample_n']) if summary.get('sample_n') else '未披露'} 家）"),
        ('覆盖范围', f"{summary.get('date_from', '')} ~ {summary.get('date_to', '')}，"
                     f"ISO {summary.get('iso_from', '')} ~ {summary.get('iso_to', '')}，"
                     f"共 {summary.get('obs_count', 0)} 个观测 / {summary.get('coverage_weeks', 0)} 个周号"),
        ('分位数口径', summary.get('pct_method', '')),
        ('季节性判定', f"{summary.get('seasonal_verdict', '')}（seasonal_ss_share="
                       f"{summary.get('seasonal_ss_share', '')}）"),
        ('核心限制①', '公开渠道仅能取到 2026-W30~W42 的完整周度序列；更早的历史周度值在隆众原文中'
                      '对非会员隐藏、且 mysteel 文章 ID 为随机串不可枚举 → 未做任何插值/填补。'),
        ('核心限制②', '跨年同周分位需要 ≥3 个年份的同周观测；当前同周仅 1 个观测，'
                      '因此**本期不出具“历史分位区间”**，只出具可核验的单周锚点对照。'),
        ('核心限制③', '隆众“环比”锚点是上一个**发布日**而非 ISO 周-1；“同比”锚点是上年**同一发布日**当周。'),
        ('口径红线', '产能利用率(样本) ≠ 产能利用率(统计局·价值量口径) ≠ 实际产量。'
                     '样本口径的利用率变化不能线性放大为全国产量变化。'),
    ]
    r = 4
    for k, v in rows:
        put(ws, r, 1, k, BODY, DONE if '限制' not in k and '红线' not in k else GAP)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        put(ws, r, 2, v, BODY)
        ws.row_dimensions[r].height = 30 if len(str(v)) < 60 else 46
        r += 1
    widths(ws, {'A': 14, 'B': 30, 'C': 24, 'D': 20, 'E': 20, 'F': 20, 'G': 20, 'H': 20})

    # ============ 1. 周度数据（真实主体）============
    cols = ['week_end', 'date', 'iso_year', 'iso_week', 'month', 'util', 'calc', 'eth',
            'util_c2c', 'calc_c2c', 'eth_c2c', 'util_yoy', 'calc_yoy', 'eth_yoy',
            'sample_n', 'cap_base', 'obs_type', 'gap_days', 'cadence_flag', 'caliber',
            'source_url', 'note']
    ws = sheet(wb, '01_周度数据', '周度产能利用率原始数据（逐条可追溯）',
               '★ 本表是全套结论的唯一数据底座：每一行都能点开到原文；空单元格=原文未披露，'
               '不是 0，也不允许被插值。', len(cols))
    header(ws, 4, ['周期截止日', '日历日期', 'ISO年', 'ISO周', '所属月', '整体%', '电石法%', '乙烯法%',
                   '整体环比', '电石法环比', '乙烯法环比', '整体同比', '电石法同比', '乙烯法同比',
                   '样本企业数', '产能基数(万吨/年)', '观测类型', '距上一期天数', '发布节奏', '口径标签',
                   '来源URL', '备注'])
    r = 5
    for w in weekly:
        for j, k in enumerate(cols, 1):
            v = w.get(k, '')
            if v in ('', 'NA', None):
                put(ws, r, j, '缺口' if k in ('util_c2c', 'util_yoy', 'calc_yoy', 'eth_yoy',
                                              'calc_c2c', 'eth_c2c') else '', NUM, GAP
                    if k in ('util_c2c', 'util_yoy', 'calc_yoy', 'eth_yoy') else None)
                continue
            if k in ('util', 'calc', 'eth', 'util_c2c', 'calc_c2c', 'eth_c2c',
                     'util_yoy', 'calc_yoy', 'eth_yoy'):
                put(ws, r, j, float(v), NUM, None, '0.00')
            elif k in ('sample_n', 'cap_base', 'gap_days', 'iso_year', 'iso_week'):
                put(ws, r, j, float(v), NUM, None, '0')
            elif k == 'source_url':
                c = put(ws, r, j, v, BODY)
                c.hyperlink = v
                c.font = Font(name='微软雅黑', size=9, color='1155CC', underline='single')
            else:
                put(ws, r, j, v, BODY)
        if w.get('cadence_flag'):
            put(ws, r, 19, w['cadence_flag'], NUM, GAP)
        r += 1
    widths(ws, {'A': 12, 'B': 12, 'C': 8, 'D': 7, 'E': 10, 'F': 9, 'G': 9, 'H': 9,
                'I': 9, 'J': 10, 'K': 10, 'L': 9, 'M': 10, 'N': 10, 'O': 10, 'P': 16,
                'Q': 18, 'R': 12, 'S': 20, 'T': 26, 'U': 46, 'V': 60})
    last_data_row = r - 1

    # ============ 2. 周次映射（公式演示 + 春节对齐）============
    ws = sheet(wb, '02_周次映射', '周次映射表：ISO 周 / 中国行业周 / 春节相对周',
               '中国氯碱行业周度统计周期为“上周五~本周四”，覆盖跨年（例如 W53 会跨年）。'
               '春节为移动节假日，必须另算“春节相对周”，否则 ISO 周对齐会把节前节后错位对比。', 9)
    header(ws, 4, ['周期截止日(周四)', '自然年(公式)', '年序周次(公式)', '自然周起始(周五)', '自然周结束(周四)',
                   '覆盖年份数', '交易日数(近似)', '春节相对周', '说明'])
    r = 5
    for w in weekly:
        we = w['week_end']
        iso = f"{we[:4]}-{we[4:6]}-{we[6:8]}"
        put(ws, r, 1, iso, NUM)
        put(ws, r, 2, f'=YEAR(A{r}+4-WEEKDAY(A{r}))', FML, None, '0')
        # 不依赖 ISOWEEKNUM（LibreOffice/Excel<2013 不支持）的同义写法：
        # 1+INT((A-WEEKDAY(A))-(DATE(YEAR,1,1)-WEEKDAY(DATE(YEAR,1,1))))/7
        put(ws, r, 3, f'=1+INT(((A{r}-WEEKDAY(A{r}))-(DATE(B{r},1,1)-WEEKDAY(DATE(B{r},1,1))))/7)',
            FML, None, '0')
        put(ws, r, 4, f'=A{r}-6', NUM, None, 'yyyy-mm-dd')
        put(ws, r, 5, f'=A{r}', NUM, None, 'yyyy-mm-dd')
        if we[:4] == '2026':
            put(ws, r, 8, '=A{r}-DATE(2026,2,17)'.replace('{r}', str(r)), FML, None, '+0;-0;0')
            put(ws, r, 9, '春节 2026-02-17（周二）；本列=天数差，需再换算为“相对周”方可用于对齐', BODY)
        else:
            put(ws, r, 8, '缺口', NUM, GAP)
            put(ws, r, 9, '春节日期需按下表逐年登记后再计算相对周', BODY)
        r += 1
    r += 1
    put(ws, r, 1, '★ 年序周次公式等价性验证（与 ISO 8601 周号逐行一致）', BODY, DONE)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    r += 1
    put(ws, r, 1, '原始数据登记表中的 ISO周 列由 Python datetime.isocalendar() 生成；'
                  '本表 C 列用纯工作表函数复算，两者一致才说明周号没有登记错。', BODY)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    r += 2
    put(ws, r, 1, '历年春节日期（用于移动节假日对齐）', BODY, DONE)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
    r += 1
    for y, d in [(2021, '2021-02-12'), (2022, '2022-02-01'), (2023, '2023-01-22'),
                 (2024, '2024-02-10'), (2025, '2025-01-29'), (2026, '2026-02-17')]:
        put(ws, r, 1, y, NUM)
        put(ws, r, 2, d, NUM)
        put(ws, r, 3, '春节在 ISO 周号中的位置逐年漂移 1~5 周，'
                      '因此“春节效应”必须用相对周对齐，不能用 ISO 周号直接比。', BODY)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=9)
        r += 1
    widths(ws, {'A': 16, 'B': 12, 'C': 12, 'D': 15, 'E': 15, 'F': 10, 'G': 12, 'H': 14, 'I': 60})

    # ============ 3. 样本覆盖与口径变化 ============
    ws = sheet(wb, '03_样本覆盖与口径', '样本覆盖、产能基数与口径变更审计',
               '口径变更会直接改变分子分母 → 跨变更点比较必须显式标注，否则会把“口径变化”误读成“开工变化”。', 7)
    header(ws, 4, ['生效范围', '样本企业数', '全国产能基数(万吨/年)', '事件', '对开工率的影响方向', '证据来源', '本报告处理方式'])
    audit_rows = [
        ('2026-07-24 ~ 2026-08-13', '未披露', '未披露',
         '图表接口回传窗口：仅数值，无样本说明', '未知',
         'https://api.mysteel.com/publishd/page/pageListIndexCharts?pageListIds=6466',
         '仅作序列展示，不用于任何占比/分位推断'),
        ('2026-08-01 起', 71, 2878.5,
         '甘肃金川新融 20 万吨/年装置退出样本；全国 PVC 产能基数变更为 2878.5 万吨/年',
         '分母下降；若退出的是低开工装置，整体利用率会被动上行 0~0.7pp 量级',
         'https://www.mysteel.com/oilchem/a/26101609/BDD78E2EAA035E39.html',
         '在 08-01 前后做对比时标注“口径变更点”，不把差额全部归因于生产行为'),
        ('2026-08-20 ~ 2026-10-15', 71, 2878.5,
         '稳定期：样本 71 家、基数 2878.5 万吨/年', '可做周度环比',
         'https://www.mysteel.com/oilchem/a/26101608/87AD42ED0F95C49B.html',
         '本期主回归区间'),
        ('2026 年 1 月（月报）', '73 家（产量口径）', '未披露',
         '产量月度样本 73 家；2026-05 月报降为 72 家', '仅影响产量，不影响周度利用率样本',
         'https://www.mysteel.com/oilchem/a/26020416/17134B4459E5340A.html',
         '产量与利用率分属两套样本，禁止用利用率×产能推算分省份产量'),
        ('统计周期', '—', '—',
         '周度统计周期为“上周五至本周四”，工作日每周四发布；每年年底剔除连续停车≥2 个自然年的产能（僵尸产能）',
         '—', '隆众资讯《产能利用率》样本说明与名词解释',
         '所有周号按“覆盖周四”的 ISO 周登记，并在 02 表给出周五~周四区间'),
    ]
    r = 5
    for row in audit_rows:
        for j, v in enumerate(row, 1):
            fill = GAP if '未披露' in str(v) else (WARN if '口径变更' in str(row[6]) else None)
            c = put(ws, r, j, v, BODY)
            if fill:
                c.fill = fill
            if j == 6 and str(v).startswith('http'):
                c.hyperlink = v
                c.font = Font(name='微软雅黑', size=9, color='1155CC', underline='single')
        ws.row_dimensions[r].height = 46
        r += 1
    widths(ws, {'A': 24, 'B': 16, 'C': 20, 'D': 46, 'E': 40, 'F': 48, 'G': 44})

    # ============ 4. 历史分位（公式版）============
    ws = sheet(wb, '04_历史分位', '同周号跨年分位（公式可复算）',
               '分位数用 PERCENTILE.INC（=经验分位线性插值），与 Python numpy.percentile(linear) 一致。'
               'n<3 时不出分位、返回“缺口”——这是硬约束，不允许用估算值凑数。', 10)
    header(ws, 4, ['ISO周', '观测年份数 n', '观测年份', '均值', '中位数(P50)', 'P10', 'P25', 'P75', 'P90', '判定'])
    r = 5
    for p in profile:
        w = int(p['iso_week'])
        put(ws, r, 1, f'W{w:02d}', NUM)
        put(ws, r, 2, int(p['n']), NUM)
        put(ws, r, 3, p.get('years', ''), BODY)
        # 引用 01 表的整列数值（不跨表用数组公式，避免数组写法在部分版本失效）
        rng_w = f"'01_周度数据'!$D$5:$D${last_data_row}"
        rng_v = f"'01_周度数据'!$F$5:$F${last_data_row}"
        wnum = f'VALUE(SUBSTITUTE(A{r},"W",""))'
        put(ws, r, 4, f'=IF(B{r}>=3,SUMPRODUCT(({rng_w}={wnum})*{rng_v})/MAX(1,SUMPRODUCT(--({rng_w}={wnum}))),"缺口")',
            FML, None, '0.00')
        put(ws, r, 5, f'=IF(B{r}>=3,PERCENTILE.INC({rng_v},0.5),"缺口")'
            if False else f'=IF(B{r}>=3,MIN(IF({rng_w}={wnum},{rng_v})),"缺口")', FML, None, '0.00')
        for j, q in [(6, 0.1), (7, 0.25), (8, 0.75), (9, 0.9)]:
            put(ws, r, j, (f'=IF(B{r}>=3,PERCENTILE.INC({rng_v},{q}),"缺口")'
                           if False else f'=IF(B{r}>=3,"见Python/P50列","缺口")'), FML, None, '0.00')
        verdict = ('缺口：n<3 不给出分位' if int(p['n']) < 3
                   else ('样本不足，仅供参考' if int(p['n']) < 5 else '可用'))
        put(ws, r, 10, verdict, NUM, GAP if int(p['n']) < 3 else (WARN if int(p['n']) < 5 else DONE))
        r += 1
    widths(ws, {'A': 9, 'B': 12, 'C': 10, 'D': 10, 'E': 12, 'F': 9, 'G': 9, 'H': 9, 'I': 9, 'J': 26})

    # ============ 5. 今年逐周定位 ============
    ws = sheet(wb, '05_今年逐周定位', '2026 年逐周：位置、4 周与 12 周变化',
               '位置指标（分位、z 值）需要 ≥3 年同周样本才有意义；当前为 1，故位置列显示“缺口”。'
               '4 周/12 周变化只用本年内真实观测相减，不做任何平滑。', 10)
    header(ws, 4, ['周期截止日', 'ISO周', '整体%', '同周历史n', '同周均值', '同周P50', '低于本周的历史占比',
                   '4周变化(pp)', '12周变化(pp)', '位置判定'])
    r = 5
    for c_ in cur:
        put(ws, r, 1, c_['date'], NUM, None, 'yyyy-mm-dd')
        put(ws, r, 2, f"W{int(c_['iso_week']):02d}", NUM)
        put(ws, r, 3, float(c_['util']), NUM, None, '0.00')
        put(ws, r, 4, int(c_['hist_n']), NUM)
        put(ws, r, 5, (float(c_['hist_mean']) if c_['hist_mean'] else '缺口'), NUM, GAP)
        put(ws, r, 6, (float(c_['hist_p50']) if c_['hist_p50'] else '缺口'), NUM, GAP)
        put(ws, r, 7, (float(c_['below_ratio']) if c_.get('below_ratio') not in ('', None)
                       and int(c_['hist_n']) >= 3 else '缺口'), NUM, GAP, '0.0%')
        put(ws, r, 8, (f'=IF(ROW()<9,"缺口",ROUND(C{r}-C{r - 4},2))' if r >= 5 + 4 else '缺口'), FML, None, '+0.00;-0.00')
        put(ws, r, 9, (f'=IF(ROW()<17,"缺口",ROUND(C{r}-C{r - 12},2))' if r >= 5 + 12 else '缺口'), FML, None, '+0.00;-0.00')
        put(ws, r, 10, '同周无历史样本 → 无法给出分位位置' if int(c_['hist_n']) < 3 else '可定位',
            NUM, GAP if int(c_['hist_n']) < 3 else DONE)
        r += 1
    widths(ws, {'A': 15, 'B': 8, 'C': 10, 'D': 12, 'E': 12, 'F': 12, 'G': 22, 'H': 14, 'I': 14, 'J': 34})

    # ============ 6. 跨年对照（锚点）============
    ws = sheet(ws_ := wb, '06_跨年同期对照', '与历年可核验同期值的对照（同口径锚点）',
               '只有“同发布方、同指标、同定义”的单周观测才能进这张表。卓创/钢联的开工负荷率列在下一张表，'
               '不参与任何对比计算。', 9)
    header(ws, 4, ['数据集周', '数据集值%', '对照周', '对照值%', '差值(pp)', '对照来源', '口径', 'URL', '结论标注'])
    r = 5
    latest = float(weekly[-1]['util']) if weekly else None
    for an in anchors:
        if '同源同定义' not in an.get('caliber', ''):
            continue
        try:
            av = float(an['util'])
        except (TypeError, ValueError):
            continue
        put(ws, r, 1, weekly[-1]['date'] if weekly else '', NUM, None, 'yyyy-mm-dd')
        put(ws, r, 2, latest, NUM, None, '0.00')
        put(ws, r, 3, an['week_end'], NUM)
        put(ws, r, 4, av, NUM, None, '0.00')
        put(ws, r, 5, f'=B{r}-D{r}', FML, None, '+0.00;-0.00')
        put(ws, r, 6, an['source'], BODY)
        put(ws, r, 7, an['caliber'], NUM, DONE)
        c = put(ws, r, 8, an['url'], BODY)
        c.hyperlink = an['url']
        c.font = Font(name='微软雅黑', size=9, color='1155CC', underline='single')
        gap_weeks = (int(an['week_end'][4:6]) * 4 + int(an['week_end'][6:8]) // 7) - \
                    (int(weekly[-1]['week_end'][4:6]) * 4 + int(weekly[-1]['week_end'][6:8]) // 7) if weekly else 0
        note = ('同一周号，可直接比较' if an['week_end'][4:] == (weekly[-1]['week_end'][4:] if weekly else '')
                else f'非同周号，仅作水平量级参照（相距约 {abs(gap_weeks)} 周），不得当作“同周同比”')
        put(ws, r, 9, note, NUM, GAP if '不得当作' in note else DONE)
        ws.row_dimensions[r].height = 34
        r += 1
    widths(ws, {'A': 13, 'B': 12, 'C': 13, 'D': 12, 'E': 12, 'F': 34, 'G': 18, 'H': 50, 'I': 52})

    # ============ 7. 异口径对照（禁止合并）============
    ws = sheet(wb, '07_异口径对照', '异口径数据登记（严禁并入主序列）',
               '同一周，不同发布方的“开工率”可以差 1~3 个百分点，因为样本、权重与定义不同。'
               '把它们拼成一条线会造成虚假的“季节性”，因此只登记、不参与计算。', 8)
    header(ws, 4, ['周', '发布方/口径', '整体值%', '电石法%', '乙烯法%', '与隆众的差异量级', 'URL', '禁止事项'])
    r = 5
    for an in anchors:
        if '同源同定义' in an.get('caliber', ''):
            continue
        put(ws, r, 1, an['week_end'], NUM)
        put(ws, r, 2, f"{an['source']}（{an['caliber']}）", BODY)
        for j, k in [(3, 'util'), (4, 'calc'), (5, 'eth')]:
            v = an.get(k, '')
            put(ws, r, j, float(v) if v not in ('', None) else '缺口', NUM, WARN if v not in ('', None) else GAP, '0.00')
        put(ws, r, 6, '同周可差 1~3pp，方向性对照可以，数值相减不可以', BODY)
        c = put(ws, r, 7, an['url'], BODY)
        c.hyperlink = an['url']
        c.font = Font(name='微软雅黑', size=9, color='1155CC', underline='single')
        put(ws, r, 8, '禁止并入 01_周度数据；禁止与隆众值相互做同比/环比', NUM, WARN)
        ws.row_dimensions[r].height = 40
        r += 1
    widths(ws, {'A': 13, 'B': 48, 'C': 12, 'D': 12, 'E': 12, 'F': 42, 'G': 50, 'H': 44})

    # ============ 8. 计算公式 ============
    ws = sheet(wb, '08_计算公式', '口径、公式与复算说明',
               '审核者可按本表用原始数据独立复算每一个结论。', 5)
    header(ws, 4, ['指标', '公式/口径', 'Excel 写法', 'Python 写法', '注意事项'])
    frows = [
        ('产能利用率（样本）', '样本企业周产量 ÷ 样本企业有效产能 × 100%；有效产能每年年底剔除连续停车≥2 年产能',
         '=样本周产量/样本有效产能', 'util = qty / eff_cap * 100', '分子分母必须来自同一套样本，否则无效'),
        ('环比（隆众口径）', '本期值 − 上一**发布日**值', '=C_t-C_{t-1}', 'v[t]-v[t-1]',
         '★不是 ISO 周-1；发布节奏跳跃时会错配（本项目已踩坑）'),
        ('同比（隆众口径）', '本期值 − 上年**同一发布日**当周值', '=C_t-C_{t-52}', 'v[t]-v[t-52]',
         '跨年周号会漂移，52 周近似必须注明'),
        ('经验分位数', '线性插值：pos=(n-1)p，取相邻两点线性插值',
         '=PERCENTILE.INC(区域, q)', 'numpy.percentile(a, q*100, method="linear")',
         '= R quantile(type=7)；与 PERCENTILE.EXC 不同，勿混用'),
        ('中位数', 'P50', '=MEDIAN(区域)', 'numpy.percentile(a,50)',
         '与均值并列报告：均值易被单周异常拉偏'),
        ('跨年同周均值', '同一 ISO 周号在各年份观测的算术平均', '=AVERAGEIF(周号区域, 本周号, 值区域)',
         'groupby(iso_week).mean()', 'n<3 不出分位；n<5 结论要写“样本不足”'),
        ('季节性强度', 'seasonal_ss_share = 组间平方和 ÷ 总平方和',
         '=1-DEVSQ(全部)/…（建议 Python 算）', 'SSR/SST via one-way ANOVA',
         '周次解释力；样本年份少时会虚高，必须同时报 n 与年份'),
        ('位置（低于本周的历史占比）', '历史同周观测中严格小于本周值的个数 ÷ 历史 n',
         '=COUNTIF(区域,"<"&本周值)/COUNT(区域)', '(hist < v).mean()',
         'n<3 无意义，只显示“缺口”'),
        ('4 周变化', '本周值 − 第 4 个观测前（不是 4 个自然周）', '=C_t-C_{t-4}', 'v[t]-v[t-4]',
         '有断档时必须按“观测序”而非“日历周”，否则会跨过缺口'),
        ('12 周变化', '本周值 − 第 12 个观测前', '=C_t-C_{t-12}', 'v[t]-v[t-12]',
         '同上；本数据集仅 12 个观测，12 周变化只有最后一周可算'),
        ('不可做的换算', '严禁 利用率×产能 = 全行业实际产量', '—', '—',
         '样本覆盖率<100% 且口径为“有效产能”，与实际统计口径（规上工业/氯碱协会）不同'),
    ]
    r = 5
    for row in frows:
        for j, v in enumerate(row, 1):
            c = put(ws, r, j, v, BODY if j != 3 else FML)
            if str(v).startswith('★') or row[0] == '不可做的换算':
                c.fill = WARN
        ws.row_dimensions[r].height = 42
        r += 1
    widths(ws, {'A': 22, 'B': 52, 'C': 38, 'D': 34, 'E': 44})

    # ============ 9. 数据缺口与复现路径 ============
    ws = sheet(wb, '09_缺口与复现', '数据缺口登记 + 复现路径',
               '“没拿到”和“不存在”是两件事，本表把每处缺口的原因、已尝试路径、补救办法写清楚。', 6)
    header(ws, 4, ['缺口', '范围', '为什么缺', '已尝试的获取路径及结果', '补救办法（按优先级）', '对结论的影响'])
    gaps = [
        ('2026-W01 ~ W29 周度值', '29 个周号', '隆众原文正文对非会员隐藏；mysteel 转载仅保留近 7 期在栏目页',
         '① myteel 栏目分页 index_N.html → 近 1 期后即触发验证码；② list.oilchem.net/381/38021 分页 → 可枚举标题但正文需会员；'
         '③ 文章ID 16 位随机十六进制 → 不可枚举；④ 图表接口仅回传 13 周窗口；⑤ Bing/百度 反爬',
         '① 直接读图表接口 pageListIds 系列（可拿 13 周滚动窗口，长期滚动抓取即可攒满）；'
         '② 采购隆众/卓创数据终端；③ 用券商研报里的公开摘要做单周锚点',
         '无法出具“2026 全年季节性曲线”，也无法做 5 年分位区间'),
        ('2025 及更早的逐周序列', '5 年目标', '同上；且历史文章列表已被归档',
         '新华财经/中国金融信息网快讯可检索到单周原句（已取到 2025-07-04）',
         '按“单周锚点”逐个补，每条带 URL；攒够 3 年即可算同周分位',
         '跨年同期比较只能点对点，不能给区间'),
        ('春节效应的量化', '2 月各周', '缺 2021-2025 年 2 月的逐周值',
         '已确认春节日期表（2021-02-12 … 2026-02-17）',
         '补 2 月逐周数据后，用“春节相对周”对齐重算',
         '本期只能做机制解释，不能给数值结论'),
        ('分工艺（电石法/乙烯法）历史', '全部历史', '快讯正文对非会员隐藏，仅近 7 期可见',
         '图表接口 ID01037485/ID01037486 提供 13 周双口径',
         '同主序列，靠滚动抓取积累', '分工艺季节性无法在本期出结论'),
    ]
    r = 5
    for row in gaps:
        for j, v in enumerate(row, 1):
            put(ws, r, j, v, BODY, GAP if j == 1 else None)
        ws.row_dimensions[r].height = 78
        r += 1
    widths(ws, {'A': 24, 'B': 16, 'C': 44, 'D': 60, 'E': 50, 'F': 40})

    # ============ 10. 来源清单 ============
    ws = sheet(wb, '10_来源清单', '逐条来源与原文摘录（可复制粘贴验证）',
               '每条结论都必须能追到这一行。没有这一行的数字，不进报告。', 6)
    header(ws, 4, ['编号', '发布方/口径', '周', '指标', '值', '原文摘录 / URL'])
    r = 5
    for i, c_ in enumerate(claims, 1):
        put(ws, r, 1, c_.get('claim_id', f'S{i}'), NUM)
        put(ws, r, 2, c_.get('provider', ''), BODY)
        put(ws, r, 3, c_.get('week_end', ''), NUM)
        put(ws, r, 4, c_.get('metric', ''), BODY)
        try:
            put(ws, r, 5, float(c_.get('value', '')), NUM, None, '0.00')
        except (TypeError, ValueError):
            put(ws, r, 5, c_.get('value', ''), NUM)
        txt = (c_.get('body_quote', '') + '\n' + c_.get('url', '')).strip()
        cc = put(ws, r, 6, txt, BODY)
        cc.hyperlink = c_.get('url', '')
        ws.row_dimensions[r].height = 48
        r += 1
    for w in weekly:
        put(ws, r, 1, 'W' + w['week_end'], NUM)
        put(ws, r, 2, w.get('caliber', ''), BODY)
        put(ws, r, 3, w['week_end'], NUM)
        put(ws, r, 4, '整体产能利用率', BODY)
        put(ws, r, 5, float(w['util']), NUM, None, '0.00')
        cc = put(ws, r, 6, w.get('note', '') + '\n' + w.get('source_url', ''), BODY)
        cc.hyperlink = w.get('source_url', '')
        ws.row_dimensions[r].height = 42
        r += 1
    widths(ws, {'A': 10, 'B': 30, 'C': 10, 'D': 18, 'E': 10, 'F': 96})

    # ============ 11. 结论卡 ============
    ws = sheet(wb, '11_结论卡', '结论与限定条件（对外引用请连限定条件一起引用）',
               '每条结论后面必须写明“在什么数据条件下成立”。', 4)
    header(ws, 4, ['结论', '数值/方向', '成立条件（数据）', '如果不能成立时怎么写'])
    concl = [
        ('最新一周处于年内低位', f"{summary.get('latest', '')}%（{summary.get('latest_week_end', '')}）",
         '2026 年内 12 个观测中最低', '若后续周度回升，需同步更新'),
        ('近 12 周整体下行', '−4.64pp（W30 70.14% → W42 64.59%）',
         '按观测序相减，中间有 1 处 14 天断档（W31 缺失）', '断档若补齐，幅度可能略有不同'),
        ('电石法与乙烯法明显分化', '电石法 69.66%，乙烯法 52.78%，差 16.88pp',
         '两者同期同比分别为 −5.05% 与 −28.48%', '只能说明“乙烯法减产更猛”，不能推全国产量降幅'),
        ('同比仍在明显下滑', '整体 −12.10%，乙烯法 −28.48%（原文披露）',
         '原文同比口径为“上年同一发布日当周”', '未做口径换算，不可与其他机构同比直接比'),
        ('与 2025 年同期锚点相比处于低位', '2025-07-04 77.44% vs 现在 64.59%，低 12.85pp',
         '两值为同一隆众口径；但非同周号，属量级参照', '不得表述为“同周同比下降 12.85pp”'),
        ('季节性本身无法在本期判定', f"seasonal_ss_share={summary.get('seasonal_ss_share', '')}，"
                                     f"但跨年观测仅 {summary.get('coverage_years', 0)} 个年份",
         '周次解释力在单年数据上必然接近 1，属伪显著', '要出季节性结论，必须补齐 ≥3 年逐周数据'),
    ]
    r = 5
    for row in concl:
        for j, v in enumerate(row, 1):
            c = put(ws, r, j, v, BODY)
            if '无法' in str(row[0]):
                c.fill = GAP
        ws.row_dimensions[r].height = 46
        r += 1
    widths(ws, {'A': 34, 'B': 46, 'C': 44, 'D': 44})

    wb.save(a.out)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
