# -*- coding: utf-8 -*-
"""
生成 Excel 工作簿（XlsxWriter）
包含：封面/口径、现货价格、合约日历、合约映射、换月记录、日度基差、
      周度/月度分布、经验分位、当前年位置、稳定性、固定交割月、数据缺口、来源与复现。
关键统计写入真实 Excel 公式（可复算）：基差=现货-期货、AVERAGE/MEDIAN/PERCENTILE/COUNT。
"""
import csv
import json
import os
import sys

import xlsxwriter

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'out')


def rcsv(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def f(v):
    try:
        return float(v)
    except Exception:
        return None


def main():
    dst = os.path.join(OUT, '甲醇_基差季节性_数据工作簿.xlsx')
    wb = xlsxwriter.Workbook(dst, {'nan_inf_to_errors': True})

    T = wb.add_format({'bold': True, 'font_size': 17, 'font_color': '#0e3a5c'})
    S = wb.add_format({'font_size': 10, 'font_color': '#5a6b80'})
    H = wb.add_format({'bold': True, 'bg_color': '#14405f', 'font_color': 'white', 'border': 1,
                       'border_color': '#9bb7cc', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
    TT = wb.add_format({'bold': True, 'font_size': 12, 'font_color': '#14405f', 'bottom': 1})
    TXT = wb.add_format({'text_wrap': True, 'valign': 'top'})
    LBL = wb.add_format({'bold': True, 'bg_color': '#eef4f8', 'border': 1, 'border_color': '#c9d8e3',
                         'text_wrap': True, 'valign': 'top'})
    N1 = wb.add_format({'num_format': '#,##0.00', 'border': 1, 'border_color': '#dde6ee'})
    N0 = wb.add_format({'num_format': '#,##0', 'border': 1, 'border_color': '#dde6ee'})
    PCT = wb.add_format({'num_format': '0.0%', 'border': 1, 'border_color': '#dde6ee'})
    D = wb.add_format({'border': 1, 'border_color': '#dde6ee', 'align': 'left'})
    WARN = wb.add_format({'bg_color': '#fff4d6', 'border': 1, 'border_color': '#e0c48a',
                          'text_wrap': True, 'valign': 'top'})
    BAD = wb.add_format({'bg_color': '#ffe4e4', 'border': 1, 'border_color': '#e8a7a7',
                         'text_wrap': True, 'valign': 'top'})
    OK = wb.add_format({'bg_color': '#e3f6ea', 'border': 1, 'border_color': '#a7d9bb',
                        'text_wrap': True, 'valign': 'top'})
    FM = wb.add_format({'num_format': '#,##0.00', 'bg_color': '#f2f7fb', 'border': 1,
                        'border_color': '#c9d8e3'})
    POS = wb.add_format({'num_format': '#,##0.00', 'border': 1, 'border_color': '#dde6ee',
                         'font_color': '#b42318'})

    def table(ws, r0, headers, rows, widths=None, fmts=None):
        ws.write_row(r0, 0, headers, H)
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                fm = fmts[j] if fmts else D
                if isinstance(v, (int, float)) and v is not None:
                    ws.write_number(r0 + 1 + i, j, v, fm)
                else:
                    ws.write(r0 + 1 + i, j, '' if v is None else str(v), D)
        if widths:
            for j, w in enumerate(widths):
                ws.set_column(j, j, w)
        ws.freeze_panes(r0 + 1, 0)
        return r0 + 1 + len(rows)

    # ================= 00 封面与口径 =================
    ws = wb.add_worksheet('00_封面与口径')
    ws.set_column(0, 0, 26)
    ws.set_column(1, 1, 100)
    ws.write(0, 0, '甲醇 期现基差季节性 数据工作簿', T)
    ws.write(1, 0, '生成日期 2026-10-20 · 样本 2022-08-17 ~ 2026-10-19 · 基差 = 现货 - 期货', S)
    rows = [
        ('研究标的', '郑州商品交易所 MA 甲醇期货 与 生意社甲醇基准价'),
        ('基差定义', '基差 = 现货价格 - 期货价格（严格此符号，元/吨）'),
        ('现货口径', '生意社甲醇基准价：全国口径、含税、元/吨。生意社定义为「基于价格大数据与价格模型产生的交易指导价」，公式 结算价=基准价*K+C。'),
        ('现货口径警示', '★ 非华东/太仓/江苏仓库报价。华东区域优等品5年历史在免费渠道不可得（隆众/卓创需登录且数值屏蔽；生意社区域图表仅93天且坐标标签有1天偏移）。本项目据此降级为全国基准价口径。'),
        ('现货来源', 'https://me.100ppi.com/news/list--1217-{page}.html 逐条抓取，原文链接见 01_现货价格 的 C 列'),
        ('期货来源', '新浪财经公开行情接口 InnerFuturesNewService.getDailyKLine，symbol=MA{YYMM}，共95个合约'),
        ('期货合约规则', '交割品级 GB/T 338-2011 工业用甲醇优等品；最后交易日=交割月第10个交易日；最后交割日=交割月第13个交易日；交割单位10吨'),
        ('映射规则1-近月连续', '持有「当月交割合约」至最后交易日；流动性门槛：临近交割20个交易日内且持仓<主力5%时视为不可交割报价，切换到下一合约'),
        ('映射规则2-主力连续', '每日取持仓量(OI)最大的合约'),
        ('映射规则3-固定交割月', '01/05/09合约各自独立成序列；同一交割月不同年份单列，不与连续合约混为同一统计样本'),
        ('频率与对齐', '以期货交易日为骨架；现货缺报日期不填补仅标记；周度取ISO周最后交易日，月度取月末最后交易日'),
        ('分位方法', '经验分位，线性插值（等价 Excel PERCENTILE），有效样本<3年标记样本不足'),
        ('缺失数据处理', '★ 未做任何插值、填补或估算；不可得数据一律标注为「数据缺口」'),
        ('数据缺口', '郑商所仓单/库存公开接口返回 HTTP 412，未取得可靠序列，故极值阶段库存/仓单背景不作为结论依据'),
        ('使用边界', '本工作簿展示历史已实现季节性，不构成对未来基差变化的预测'),
    ]
    for i, (k, v) in enumerate(rows):
        ws.write(3 + i, 0, k, LBL)
        ws.write(3 + i, 1, v, BAD if '★' in v else TXT)
        ws.set_row(3 + i, 34 if len(v) > 60 else 20)

    # ================= 01 现货价格 =================
    ws = wb.add_worksheet('01_现货价格')
    ws.write(0, 0, '生意社甲醇基准价（全国口径，含税，元/吨）', T)
    ws.write(1, 0, '逐条保留原文链接；未填补任何缺失交易日', S)
    spot = rcsv(os.path.join(OUT, 'spot_100ppi_meitan_benchmark.csv'))
    table(ws, 3, ['日期', '基准价(元/吨)', '原文链接'],
          [(r['date'], f(r['price']), r['source_url']) for r in spot],
          [12, 16, 80], [D, N1, D])

    # ================= 02 合约日历 =================
    ws = wb.add_worksheet('02_期货合约日历')
    ws.write(0, 0, 'MA 逐合约日历与「最后交易日=交割月第10个交易日」规则核验', T)
    cal = rcsv(os.path.join(OUT, 'contract_calendar.csv'))
    cols = ['合约', '交割年月', '挂牌首日(有K线)', '末个K线日', '交割月交易日数',
            '规则最后交易日(第10个交易日)', '规则核验', '数据天数']
    table(ws, 2, cols, [tuple(r.get(c, '') for c in cols) for r in cal],
          [12, 12, 16, 14, 14, 22, 26, 10],
          [D, D, D, D, N0, D, D, N0])

    # ================= 03/04 映射 =================
    for nm, fn, label in [('03_映射_近月连续', 'map_near.csv', '近月连续（含流动性门槛）'),
                          ('04_映射_主力连续', 'map_main.csv', '主力连续（持仓量最大）')]:
        ws = wb.add_worksheet(nm)
        ws.write(0, 0, '逐日合约映射：' + label, T)
        mp = rcsv(os.path.join(OUT, fn))
        table(ws, 2, ['日期', '合约', '期货收盘(元/吨)', '持仓量(手)'],
              [(r['date'], r['contract'], f(r['fut_price']), f(r['oi'])) for r in mp],
              [12, 12, 18, 16], [D, D, N1, N0])

    # ================= 05 换月记录 =================
    ws = wb.add_worksheet('05_换月记录')
    ws.write(0, 0, '换月记录：日期、移出/移入合约、跨日跳空', T)
    h1 = ['换月日', '移出合约', '移入合约', '移出前收盘', '移入日收盘', '换月跳空(元/吨)', '跳空占比%']
    w1 = [12, 12, 12, 14, 14, 18, 12]
    f1 = [D, D, D, N1, N1, POS, N1]
    rr = rcsv(os.path.join(OUT, 'roll_log_near.csv'))
    rr2 = rcsv(os.path.join(OUT, 'roll_log_main.csv'))
    ws.write(2, 0, 'A. 近月连续', TT)
    end1 = table(ws, 3, h1, [(r['换月日'], r['移出合约'], r['移入合约'], f(r['移出前收盘']),
                              f(r['移入日收盘']), f(r['换月跳空(元/吨)']), f(r['跳空占比%'])) for r in rr], w1, f1)
    ws.write(end1 + 2, 0, 'B. 主力连续', TT)
    end2 = table(ws, end1 + 3, h1, [(r['换月日'], r['移出合约'], r['移入合约'], f(r['移出前收盘']),
                                     f(r['移入日收盘']), f(r['换月跳空(元/吨)']), f(r['跳空占比%'])) for r in rr2], w1, f1)
    ws.write(end2 + 2, 0, 'C. 同日两合约价差（剥离换月影响的关键证据）', TT)
    sd = rcsv(os.path.join(OUT, 'roll_sameday_spread.csv'))
    table(ws, end2 + 3, ['换月日', '旧合约', '新合约', '旧收盘', '新收盘', '同日价差(元/吨)'],
          [(r['换月日'], r['旧合约'], r['新合约'], f(r['旧收盘']), f(r['新收盘']),
            f(r['两合约同日价差(元/吨)'])) for r in sd],
          [12, 12, 12, 12, 12, 18], [D, D, D, N1, N1, POS])

    # ================= 06 日度基差 =================
    ws = wb.add_worksheet('06_日度基差')
    ws.write(0, 0, '日度基差 = 现货 - 期货（近月连续）；F 列为真实 Excel 公式，可自行复算', T)
    daily = rcsv(os.path.join(OUT, 'seas_near', 'daily_basis.csv'))
    hr = 2
    ws.write_row(hr, 0, ['日期', '年', '月', '现货(元/吨)', '期货(元/吨)', '基差(元/吨)', '合约'], H)
    for i, r in enumerate(daily):
        row = hr + 1 + i
        ws.write(row, 0, r['date'], D)
        ws.write_number(row, 1, int(r['year']), N0)
        ws.write_number(row, 2, int(r['month']), N0)
        ws.write_number(row, 3, f(r['spot']), N1)
        ws.write_number(row, 4, f(r['fut']), N1)
        ws.write_formula(row, 5, '=D%d-E%d' % (row + 1, row + 1), FM)
        ws.write(row, 6, r['contract'], D)
    for j, w in enumerate([12, 7, 7, 14, 14, 14, 12]):
        ws.set_column(j, j, w)
    ws.freeze_panes(hr + 1, 0)
    n = len(daily)
    ws.write(n + 4, 0, '校验：基差均值（公式）', LBL)
    ws.write_formula(n + 4, 1, '=AVERAGE(F4:F%d)' % (n + 3), FM)
    ws.write(n + 5, 0, '校验：基差样本数（公式）', LBL)
    ws.write_formula(n + 5, 1, '=COUNT(F4:F%d)' % (n + 3), FM)

    # ================= 07 周度 =================
    ws = wb.add_worksheet('07_周度分布')
    ws.write(0, 0, '周度基差（ISO 周，取该周最后一个有配对数据的交易日）', T)
    wk = rcsv(os.path.join(OUT, 'seas_near', 'weekly_basis.csv'))
    table(ws, 2, ['ISO年', 'ISO周', '日期', '月份', '基差(元/吨)'],
          [(int(r['iso_year']), int(r['iso_week']), r['date'], int(r['month']), f(r['basis'])) for r in wk],
          [10, 10, 12, 8, 14], [N0, N0, D, N0, N1])

    # ================= 08 月度 =================
    ws = wb.add_worksheet('08_月度分布')
    ws.write(0, 0, '月度基差（月末最后交易日值 + 当月均值）', T)
    mo = rcsv(os.path.join(OUT, 'seas_near', 'monthly_basis.csv'))
    table(ws, 2, ['年', '月', '月末日期', '基差(月末)', '基差(月均)', '当月交易日数'],
          [(int(r['year']), int(r['month']), r['date'], f(r['basis_month_end']),
            f(r['basis_mean']), int(r['n_days'])) for r in mo],
          [8, 8, 12, 14, 14, 14], [N0, N0, D, N1, N1, N0])

    # ================= 09 经验分位 =================
    ws = wb.add_worksheet('09_经验分位')
    ws.set_column(0, 0, 34)
    ws.set_column(1, 5, 15)
    ws.set_column(6, 6, 22)
    ws.write(0, 0, '经验分位：同季节位置跨年份的 p10/p25/p50/p75/p90', T)
    ws.write(1, 0, '左表为预计算值；下方为 Excel 公式复算（PERCENTILE/AVERAGE/MEDIAN/COUNT），两者应一致', S)
    ws.write(3, 0, '一、月度分位（近月连续）', TT)
    sm = rcsv(os.path.join(OUT, 'seas_near', 'seasonal_month.csv'))
    heads = ['月份', '有效样本年数', '均值', '中位数', 'p10', 'p25', 'p75', 'p90', '最小', '最大']
    table(ws, 4, heads,
          [(r['month'] + '月', int(r['n_years']), f(r['mean']), f(r['median']), f(r['p10']),
            f(r['p25']), f(r['p75']), f(r['p90']), f(r['min']), f(r['max'])) for r in sm],
          [12, 12, 12, 12, 11, 11, 11, 11, 11, 11],
          [D, N0, N1, N1, N1, N1, N1, N1, N1, N1])

    jan_rows = [i for i, r in enumerate(mo) if int(r['month']) == 1]
    jan_vals = [f(mo[i]['basis_month_end']) for i in jan_rows]
    r0 = 4 + len(sm) + 3
    ws.write(r0, 0, '二、公式复算示例（1 月）', TT)
    ws.write(r0 + 1, 0, '指标', H)
    ws.write(r0 + 1, 1, 'Excel 公式结果', H)
    ws.write(r0 + 1, 6, '1月各年基差(辅助列)', H)
    for i, v in enumerate(jan_vals):
        ws.write_number(r0 + 2 + i, 6, v, N1)
    rng = 'G%d:G%d' % (r0 + 3, r0 + 2 + len(jan_vals))
    refs = ','.join('08_月度分布!D%d' % (4 + i) for i in jan_rows)
    items = [('均值', '=AVERAGE(%s)' % refs), ('中位数', '=MEDIAN(%s)' % refs),
             ('p10', '=PERCENTILE(%s,0.1)' % rng), ('p25', '=PERCENTILE(%s,0.25)' % rng),
             ('p75', '=PERCENTILE(%s,0.75)' % rng), ('p90', '=PERCENTILE(%s,0.9)' % rng),
             ('样本数', '=COUNT(%s)' % refs)]
    for i, (k, fm) in enumerate(items):
        ws.write(r0 + 2 + i, 0, k, LBL)
        ws.write_formula(r0 + 2 + i, 1, fm, FM)
    comp = r0 + 2 + len(items) + 1
    ws.write(comp, 0, '对照（预计算值）', LBL)
    jan = next((r for r in sm if r['month'] == '1'), None)
    if jan:
        for j, key in enumerate(['mean', 'median', 'p10', 'p25', 'p75', 'p90']):
            ws.write_number(comp, 1 + j, f(jan[key]), N1)
        ws.write_number(comp, 7, int(jan['n_years']), N0)

    r1 = comp + 3
    ws.write(r1, 0, '三、周度分位（仅列有样本的 ISO 周）', TT)
    sw = [r for r in rcsv(os.path.join(OUT, 'seas_near', 'seasonal_week.csv')) if int(r['n_years']) > 0]
    table(ws, r1 + 1, ['ISO周', '有效年数', '均值', '中位数', 'p10', 'p25', 'p75', 'p90'],
          [('W' + r['iso_week'], int(r['n_years']), f(r['mean']), f(r['median']),
            f(r['p10']), f(r['p25']), f(r['p75']), f(r['p90'])) for r in sw],
          None, [D, N0, N1, N1, N1, N1, N1, N1])

    # ================= 10 当前年位置 =================
    ws = wb.add_worksheet('10_当前年位置')
    ws.set_column(0, 0, 30)
    ws.set_column(1, 1, 16)
    ws.set_column(2, 4, 30)
    ws.write(0, 0, '当前基差相对往年同期的位置', T)
    mn = json.load(open(os.path.join(OUT, 'seas_near', 'meta_near.json'), encoding='utf-8'))
    mm = json.load(open(os.path.join(OUT, 'seas_main', 'meta_main.json'), encoding='utf-8'))
    r = 3
    for label, meta in [('近月连续', mn), ('主力连续', mm)]:
        ws.write(r, 0, label, TT)
        r += 1
        cp = meta['current_position']
        for scope, key in [('月度（10月）', 'month'),
                           ('周度（ISO第%s周）' % cp['week']['iso_week'], 'week')]:
            c = cp.get(key)
            if not c:
                continue
            ws.write(r, 0, scope, LBL)
            if c.get('value') is not None:
                ws.write_number(r, 1, c['value'], N1)
            ws.write(r, 2, '历史同期分位 %s%%' % c.get('below_ratio'), D)
            ws.write(r, 3, 'z=%s（样本%s年）' % (c.get('z'), c.get('n_hist')), D)
            ws.write(r, 4, '历史均值 %s / 标准差 %s' % (c.get('hist_mean'), c.get('hist_sd')), D)
            r += 1
        r += 1
    ws.write(r, 0, '重要提示', LBL)
    ws.merge_range(r, 1, r, 4,
                   '10月历史同期样本仅4年，100%分位与 z>5 属于小样本下的极端读数，'
                   '不能据此推断基差必然收敛；请结合现货口径限制一并解读。', WARN)
    ws.set_row(r, 46)

    # ================= 11 稳定性 =================
    ws = wb.add_worksheet('11_稳定性检验')
    ws.write(0, 0, '月度季节性稳定性（跨年变异系数、升水年份占比、分位极差）', T)
    st = rcsv(os.path.join(OUT, 'supp_stability_near.csv'))
    end = table(ws, 2, ['月份', '样本年数', '均值', '标准差', '变异系数', '升水年份占比', '最小值', '最大值', '分位极差'],
                [(r['月份'] + '月', int(r['样本年数']), f(r['均值']), f(r['标准差']), f(r['变异系数']),
                  f(r['升水年份占比']), f(r['最小值']), f(r['最大值']), f(r['分位极差(p90-p10)'])) for r in st],
                [10, 10, 12, 12, 12, 14, 12, 12, 14],
                [D, N0, N1, N1, N1, PCT, N1, N1, N1])
    ss = mn['stability']
    r = end + 2
    ws.write(r, 0, '季节性方差占比（月份间/总）', LBL)
    ws.write_number(r, 1, ss['seasonal_ss_share'], PCT)
    ws.write(r + 1, 0, '月份间平方和', LBL)
    ws.write_number(r + 1, 1, ss['between_month_ss'], N1)
    ws.write(r + 2, 0, '月份内平方和', LBL)
    ws.write_number(r + 2, 1, ss['within_month_ss'], N1)
    ws.merge_range(r + 3, 0, r + 3, 5,
                   '解读：月份仅解释约19%的基差总方差，多数月份跨年变异系数大于1，'
                   '说明历史季节性存在但强度偏弱，不可作为预测依据。', WARN)
    ws.set_row(r + 3, 34)

    # ================= 12 固定交割月 =================
    ws = wb.add_worksheet('12_固定交割月')
    ws.write(0, 0, '固定交割月（01/05/09）逐年基差：同一交割月不同年份单列', T)
    fs = rcsv(os.path.join(OUT, 'supp_fixed_month_summary.csv'))
    table(ws, 2, ['交割月', '合约', '样本日数', '起始', '结束', '基差均值', '基差中位', '最小', '最大', '说明'],
          [(r['交割月'], r['合约'], int(r['样本日数']), r['起始'], r['结束'], f(r['基差均值']),
            f(r['基差中位']), f(r['最小']), f(r['最大']), r['说明']) for r in fs],
          [9, 11, 10, 12, 12, 11, 11, 10, 10, 46],
          [D, D, N0, D, D, N1, N1, N1, N1, D])

    # ================= 13 数据缺口 =================
    ws = wb.add_worksheet('13_数据缺口与限制')
    ws.set_column(0, 0, 30)
    ws.set_column(1, 1, 62)
    ws.set_column(2, 2, 44)
    ws.write(0, 0, '数据缺口与可比性限制（未做任何填补）', T)
    gaps = [
        ('华东现货历史', '隆众/卓创需登录且数值屏蔽；生意社区域图表仅93天', '降级为全国基准价口径并显式标注', 'bad'),
        ('规格口径不对齐', '基准价未标明优等品分级，期货交割标准为优等品', '标注为口径限制，无法修正', 'bad'),
        ('地区口径不对齐', '基准价为全国口径，期货交割仓库集中于华东', '结论限于该口径，不可直接用于太仓套保定价', 'bad'),
        ('郑商所仓单/库存序列', '公开接口返回 HTTP 412，未取得可靠历史序列', '不做估算，极值阶段背景留空', 'bad'),
        ('流动性枯竭合约', 'MA2609 临近交割持仓降至1309手，收盘价被扭曲', '加流动性门槛，跳过901个伪近月报价日', 'ok'),
        ('最后交易日个别偏差', '2个合约提前1个交易日结束（流动性）', '已按规则核验并标注', 'ok'),
        ('报价时点错位', '现货08:30发布 vs 期货15:00收盘', '按同一日期配对，存在1日错位', 'warn'),
        ('季节位置样本年数', '各月仅4~5年', '分位统计置信度低，各表已列有效样本数', 'warn'),
    ]
    for j, hh in enumerate(['缺口/风险项', '说明', '处理方式']):
        ws.write(2, j, hh, H)
    for i, (a, b, c, s) in enumerate(gaps):
        ws.write(3 + i, 0, a, LBL)
        ws.write(3 + i, 1, b, BAD if s == 'bad' else (WARN if s == 'warn' else OK))
        ws.write(3 + i, 2, c, TXT)
        ws.set_row(3 + i, 32)

    # ================= 14 来源与复现 =================
    ws = wb.add_worksheet('14_数据来源与复现')
    for j, w in enumerate([16, 48, 48, 34]):
        ws.set_column(j, j, w)
    ws.write(0, 0, '数据来源与复现路径', T)
    src = [
        ('现货', '生意社甲醇基准价（me.100ppi.com 资讯频道，1083条，逐条含原文链接）',
         'scripts/fetch_spot_100ppi.py -> out/spot_100ppi_meitan_benchmark.csv', '2022-08-17 ~ 2026-10-20'),
        ('期货', '新浪财经公开行情接口 InnerFuturesNewService.getDailyKLine（95个MA合约）',
         'scripts/fetch_futures.py -> raw/MA_MA{YYMM}.json', '2019-05 ~ 2026-10-19'),
        ('合约规则', '郑商所《甲醇期货业务细则》：最后交易日=交割月第10个交易日；GB/T 338-2011 优等品',
         'scripts/build_contracts.py 逐合约核验', '91/95 精确吻合'),
        ('映射与基差', '近月连续 / 主力连续 / 固定交割月三套映射',
         'scripts/build_basis.py', '近月换月50次；主力换月14次'),
        ('季节性统计', '周度/月度对齐、均值中位数与经验分位',
         'scripts/basis_seasonality.py', '1003个日度基差'),
        ('补充分析', '稳定性、换月污染量化、固定交割月单列',
         'scripts/supp_analysis.py', '—'),
        ('报告渲染', '自包含交互式HTML + 本Excel工作簿',
         'scripts/make_report_data.py / make_html.py / make_xlsx.py', '—'),
    ]
    for j, hh in enumerate(['环节', '来源/方法', '复现脚本', '覆盖范围']):
        ws.write(2, j, hh, H)
    for i, row in enumerate(src):
        for j, v in enumerate(row):
            ws.write(3 + i, j, v, LBL if j == 0 else TXT)
        ws.set_row(3 + i, 34)

    wb.close()
    print('[OK]', dst, os.path.getsize(dst) // 1024, 'KB')


if __name__ == '__main__':
    main()
