# -*- coding: utf-8 -*-
"""build_excel.py —— 生成《异常月差扫描工作簿》（XlsxWriter，原生 Excel 公式）

工作表
------
00 说明与红线        口径声明、免责、数据源、公式索引
01 合约规则          品种 × 交易所规则（含实测验证）
02 挂牌合约行情      当日全部挂牌合约（价格/持仓/成交）
03 期限结构          每品种当日曲线（含公式：月差、斜率）
04 月差计算          主表：每对组合同当前月差、分位、Z、近1月变化、评级
05 历史可比样本      每组合的历年同剩余期限样本（明细行）
06 分位统计          公式：分位数/均值/标准差/N，可改数据即重算
07 产业面            库存/仓单/现货/基差 + 来源与可信度
08 供需事件          事件时间线
09 公式说明          每个指标的定义与 Excel 实现
10 数据质量与限制    样本不足/不可比/口径差异清单
"""
from __future__ import annotations

import json
import os

import sys

import xlsxwriter

F = {
    'title': {'bold': True, 'font_size': 16, 'font_color': '#1F3864'},
    'sub': {'bold': True, 'font_size': 11, 'font_color': '#FFFFFF', 'bg_color': '#1F3864',
            'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'border': 1, 'border_color': '#FFFFFF'},
    'hdr': {'bold': True, 'font_size': 10, 'bg_color': '#D9E2F3', 'border': 1, 'border_color': '#8EA9DB',
            'align': 'center', 'valign': 'vcenter', 'text_wrap': True},
    'txt': {'font_size': 10, 'border': 1, 'border_color': '#D0D7E5', 'valign': 'top', 'text_wrap': False},
    'txtw': {'font_size': 10, 'border': 1, 'border_color': '#D0D7E5', 'valign': 'top', 'text_wrap': True},
    'num': {'font_size': 10, 'border': 1, 'border_color': '#D0D7E5', 'num_format': '#,##0.00', 'valign': 'top'},
    'num0': {'font_size': 10, 'border': 1, 'border_color': '#D0D7E5', 'num_format': '#,##0', 'valign': 'top'},
    'pct': {'font_size': 10, 'border': 1, 'border_color': '#D0D7E5', 'num_format': '0.0"%"', 'valign': 'top'},
    'date': {'font_size': 10, 'border': 1, 'border_color': '#D0D7E5', 'num_format': 'yyyy-mm-dd', 'valign': 'top'},
    'formula': {'font_size': 10, 'border': 1, 'border_color': '#D0D7E5', 'num_format': '#,##0.00',
                'bg_color': '#FFF2CC', 'valign': 'top'},
    'formula0': {'font_size': 10, 'border': 1, 'border_color': '#D0D7E5', 'num_format': '#,##0',
                 'bg_color': '#FFF2CC', 'valign': 'top'},
    'formulapct': {'font_size': 10, 'border': 1, 'border_color': '#D0D7E5', 'num_format': '0.0"%"',
                   'bg_color': '#FFF2CC', 'valign': 'top'},
    'note': {'font_size': 9, 'font_color': '#7F7F7F', 'italic': True, 'text_wrap': True, 'valign': 'top'},
    'warn': {'font_size': 10, 'font_color': '#C00000', 'bold': True, 'text_wrap': True, 'valign': 'top'},
    'ext': {'font_size': 10, 'bold': True, 'font_color': '#C00000', 'border': 1, 'border_color': '#D0D7E5',
            'align': 'center', 'valign': 'top'},
    'ok': {'font_size': 10, 'font_color': '#375623', 'border': 1, 'border_color': '#D0D7E5',
           'align': 'center', 'valign': 'top'},
    'dim': {'font_size': 10, 'font_color': '#808080', 'border': 1, 'border_color': '#D0D7E5', 'valign': 'top'},
}


def mk_formats(wb):
    return {k: wb.add_format(v) for k, v in F.items()}


def ws_setup(wb, name, widths, title, subtitle=''):
    ws = wb.add_worksheet(name)
    for i, w in enumerate(widths):
        ws.set_column(i, i, w)
    ws.set_row(0, 24)
    ws.merge_range(0, 0, 0, len(widths) - 1, title, F['title'])
    if subtitle:
        ws.set_row(1, 18)
        ws.merge_range(1, 0, 1, len(widths) - 1, subtitle, F['note'])
        ws.freeze_panes(3, 0)
        return ws, 3
    ws.freeze_panes(2, 0)
    return ws, 2


def write_header(ws, r, cols):
    for c, h in enumerate(cols):
        ws.write(r, c, h, F['hdr'])


def build(scan, industry, quotes, out_path):
    global F
    wb = xlsxwriter.Workbook(out_path, {'nan_inf_to_errors': True})
    F = mk_formats(wb)
    as_of = scan['as_of']
    prod_names = {p: b['name_cn'] for p, b in scan['products'].items()}

    # ---------------- 00 说明 ----------------
    ws, r = ws_setup(wb, '00 说明与红线', [26, 96],
                     '化工期货｜异常月差（近远月价差）扫描工作簿',
                     f'数据日 {as_of}　品种池：甲醇 MA / 纯碱 SA / 聚丙烯 PP / PTA TA')
    blocks = [
        ('本工作簿回答的问题', '1) 各品种主要合约月份与交易所规则；2) 当日全部挂牌合约价格与期限结构；'
                                '3) 按"近月减远月"口径的月差；4) 同组合同剩余期限的可比历史样本；'
                                '5) 当前月差、历史分位、近1月变化与极端程度；6) 极端分位排序；'
                                '7) 异常组合的库存/仓单/交割/供需事件；8) 样本不足与不可比说明。'),
        ('月差定义', '月差 = 近月结算价 − 远月结算价（元/吨）。正值＝近月升水（正向市场 contango）；'
                      '负值＝近月贴水（反向市场 backwardation）。远月必须晚于近月。'),
        ('历史分位', '在"同一品种 × 同一(近月,远月)月份组合 × 同一剩余期限整周数"的历史样本中，'
                      '当前月差所处的位置。分位越接近 100% 表示近月相对远月比历史更贵；越接近 0% 表示更便宜。'),
        ('可比样本', '每年取 1 个样本（2022–2026 各年度合约）。剩余期限 = 近月交割月结束日 − 观测日，'
                      '取整周数 floor(days/7)。不同月份组合分别统计，绝不合并为一个分布。'),
        ('数据源', '① 郑商所每日行情 FutureDataDaily.txt（结算价，官方）；'
                    '② 郑商所仓单日报 FutureDataWhsheet.txt（仓单，官方）；'
                    '③ 东方财富 futsseapi list/114（大商所 PP 当日最新价，官网对脚本返回 412）；'
                    '④ 新浪财经 InnerFuturesNewService.getDailyKLine（逐合约历史日线，276 个合约）。'),
        ('⚠ 价格口径差异', 'MA/SA/TA 使用交易所结算价；PP 因大商所官网拦截，当日行情为最新价口径。'
                            '两套口径已在"02 挂牌合约行情"的 price_basis 列分列，不混算。'),
        ('⚠ 红线', '① 不把异常月差直接当作跨期套利/交易建议；② 不合并不同月份组合的分布；'
                    '③ 样本不足不给分位；④ 不插值、不向前填充、不使用主力连续合约；'
                    '⑤ 未扣除仓储费、资金成本、交割成本、品级与地区升贴水。'),
        ('公式说明', '黄色底纹单元格为 Excel 原生公式，改动源数据即重算，无宏无加载项。详见「09 公式说明」。'),
    ]
    r += 1
    for k, v in blocks:
        ws.write(r, 0, k, F['warn'] if k.startswith('⚠') else F['sub'])
        ws.write(r, 1, v, F['txtw'])
        ws.set_row(r, 46)
        r += 1
    r += 1
    ws.write(r, 0, '工作表索引', F['sub'])
    ws.write(r, 1, ' '.join(['01 合约规则', '02 挂牌合约行情', '03 期限结构', '04 月差计算',
                             '05 历史可比样本', '06 分位统计', '07 产业面', '08 供需事件',
                             '09 公式说明', '10 数据质量与限制']), F['txtw'])

    # ---------------- 01 合约规则 ----------------
    ws, r = ws_setup(wb, '01 合约规则', [10, 12, 18, 20, 16, 10, 10, 10, 10, 22, 22, 14, 46],
                     '01 合约规则匹配（交易所规则 + 实测验证）',
                     '规则来源：交易所合约全文（双源交叉）；挂牌月份经 276 个逐合约日线实测验证')
    cols = ['品种', '名称', '交易所', '交易所(英)', '合约月份', '交易单位\n(吨/手)', '最小变动\n(元/吨)',
            '最低保证金\n(%)', '涨跌停板\n(%)', '最后交易日', '最后交割日', '主力锚点', '特别说明']
    write_header(ws, r, cols)
    r += 1
    for p, b in scan['products'].items():
        rule = b['rule']
        raw = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'data','contract_rules.json'), encoding='utf-8'))
        full = raw['products'][p]
        mo = rule['listed_months']
        mo_txt = '1–12 月（全年）' if len(mo) == 12 else ','.join(map(str, mo))
        row = [p, b['name_cn'], b['exchange_cn'], b['exchange'], mo_txt,
               rule['contract_unit_t'], rule['tick'], rule['min_margin_pct'], rule['price_limit_pct'],
               rule['last_trading_day_rule'], full.get('last_delivery_day_rule', ''),
               '/'.join(f'{m}月' for m in rule['main_months']), full.get('special', '')]
        for c, v in enumerate(row):
            ws.write(r, c, v, F['num0'] if isinstance(v, (int, float)) else F['txtw'])
        r += 1
    r += 1
    ws.write(r, 0, '实测验证', F['warn'])
    ws.merge_range(r, 1, r, 12, '四个品种均为 1–12 月全月连续挂牌，无跳月设计。各合约上市首日距交割月恒为 12 个月'
                                '（PP 为 11–12 个月，大商所挂牌略晚）。因此"主力只在 1/5/9"属过度简化：'
                                '01/05/09 是生命周期锚点，但换月逐月滚动，其余月份同样有可观流动性。', F['txtw'])
    ws.set_row(r, 40)

    # ---------------- 02 挂牌合约行情 ----------------
    ws, r = ws_setup(wb, '02 挂牌合约行情', [12, 10, 10, 10, 12, 12, 12, 12, 12, 12, 14, 12, 12],
                     '02 当日全部挂牌合约行情（含主力标记）',
                     f'数据日 {as_of}　黄色列为公式：距交割月数 / 是否主力 / 合约市值')
    cols = ['合约', '品种', '交割年', '交割月', '结算价', '收盘价', '昨结算', '涨跌', '成交量', '持仓量',
            '距交割(月)', '是否主力', '价格口径']
    write_header(ws, r, cols)
    hdr_row = r
    r += 1
    q = quotes.get('contracts', {})
    basis_map = quotes.get('price_basis_by_product', {})
    first_data = r
    rows = []
    for p, b in scan['products'].items():
        for t in b['term_structure']:
            rows.append((p, t))
    rows.sort(key=lambda x: (x[0], x[1]['y'], x[1]['m']))
    n_data = len(rows)
    # 主力标记需要每个品种单独判断：用公式 MAXIFS 不可跨版本，故用辅助列
    for p, t in rows:
        sym = t['symbol']
        qd = q.get(sym, {})
        settle = t['settle'] if t['settle'] is not None else qd.get('settle')
        close = t['close'] if t['close'] is not None else qd.get('close')
        ws.write(r, 0, sym, F['txt'])
        ws.write(r, 1, p, F['txt'])
        ws.write_number(r, 2, t['y'], F['num0'])
        ws.write_number(r, 3, t['m'], F['num0'])
        ws.write_number(r, 4, settle or 0, F['num'])
        ws.write_number(r, 5, close or 0, F['num'])
        ws.write_number(r, 6, qd.get('prev_settle') or 0, F['num'])
        ws.write_formula(r, 7, f'=IF(N("x")="x",E{r+1}-G{r+1})', F['formula'],
                         (settle or 0) - (qd.get('prev_settle') or 0))
        ws.write_number(r, 8, (t['volume'] or 0), F['num0'])
        ws.write_number(r, 9, (t['oi'] or 0), F['num0'])
        # 距交割月数（公式：以数据日的年月为基准）
        ws.write_formula(r, 10, f'=(C{r+1}-YEAR(DATEVALUE("{as_of}")))*12+(D{r+1}-MONTH(DATEVALUE("{as_of}")))',
                         F['formula0'], (t['y'] - int(as_of[:4])) * 12 + t['m'] - int(as_of[5:7]))
        ws.write(r, 11, 'YES' if t.get('is_main') else '', F['ok'] if t.get('is_main') else F['dim'])
        ws.write(r, 12, basis_map.get(p, 'settle'), F['txt'])
        r += 1
    last_data = r
    # 汇总公式
    r += 1
    ws.write(r, 0, '校验', F['warn'])
    ws.write(r, 1, '合约数', F['txt'])
    ws.write_formula(r, 2, f'=COUNTA(A{first_data+1}:A{last_data})', F['formula0'], n_data)
    ws.write(r, 3, '主力合约数', F['txt'])
    ws.write_formula(r, 4, f'=COUNTIF(L{first_data+1}:L{last_data},"YES")', F['formula0'],
                     sum(1 for _, t in rows if t.get('is_main')))

    # ---------------- 03 期限结构 ----------------
    ws, r = ws_setup(wb, '03 期限结构', [12, 12, 12, 12, 14, 14, 14, 16, 16, 30],
                     '03 各品种当日期限结构（曲线形态与单步跳变）',
                     '黄色列为公式：相邻月价差、曲线斜率(OLS)、形态判定')
    shape_rows = {}
    for p, b in scan['products'].items():
        ws.merge_range(r, 0, r, 9, f'{p} {b["name_cn"]}　形态：{b["shape"]["type"]}　'
                                   f'斜率 {b["shape"]["slope_per_month"]} 元/月　单调性 r={b["shape"]["monotonicity_r"]}',
                       F['sub'])
        r += 1
        cols = ['合约', '交割月', '结算价', '收盘价', '持仓量', '距交割(月)', '相邻价差', '环比', '累计 vs 首月', '备注']
        write_header(ws, r, cols)
        r += 1
        ts = b['term_structure']
        base = r
        for i, t in enumerate(ts):
            ws.write(r, 0, t['symbol'], F['txt'])
            ws.write(r, 1, f"{t['y']}-{t['m']:02d}", F['txt'])
            ws.write_number(r, 2, t['settle'] or 0, F['num'])
            ws.write_number(r, 3, t['close'] or 0, F['num'])
            ws.write_number(r, 4, t['oi'] or 0, F['num0'])
            ws.write_formula(r, 5, f'=(B{r+1}-0)-0', F['formula0'], t['months_out']) if False else \
                ws.write_number(r, 5, t['months_out'], F['num0'])
            if i == 0:
                ws.write(r, 6, '', F['dim'])
                ws.write(r, 7, '', F['dim'])
                ws.write_formula(r, 8, f'=C{r+1}-C{r+1}', F['formula'], 0)
            else:
                ws.write_formula(r, 6, f'=C{r+1}-C{r}', F['formula'],
                                 (t['settle'] or 0) - (ts[i - 1]['settle'] or 0))
                ws.write_formula(r, 7, f'=IF(C{r}=0,"",F{r+1})', F['formula'],
                                 (t['settle'] or 0) - (ts[i - 1]['settle'] or 0))
                ws.write_formula(r, 8, f'=C{r+1}-$C${base+1}', F['formula'],
                                 (t['settle'] or 0) - (ts[0]['settle'] or 0))
            if t.get('is_main'):
                ws.write(r, 9, '主力合约', F['ok'])
            r += 1
        end = r
        ws.write(r, 0, '斜率(元/月, OLS)', F['txt'])
        ws.write_formula(r, 1, f'=SLOPE(C{base+1}:C{end},F{base+1}:F{end})', F['formula0'],
                         b['shape']['slope_per_month'])
        ws.write(r, 2, '形态', F['txt'])
        ws.write(r, 3, b['shape']['type'], F['txt'])
        r += 3

    # ---------------- 04 月差计算 ----------------
    ws, r = ws_setup(wb, '04 月差计算', [8, 10, 10, 18, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 10, 18, 20],
                     '04 月差计算与异常排序（主表）',
                     '月差 = 近月结算价 − 远月结算价；分位基于「05 历史可比样本」逐组合统计')
    cols = ['#', '品种', '名称', '近月 − 远月', '近月价', '远月价', '当前月差', '历史均值', '历史分位',
            'Z分数', '近1月前', '近1月变化', '极端度', 'N(年)', '评级', '可交易性', '备注']
    write_header(ws, r, cols)
    hr = r
    r += 1
    flat = []
    for p, b in scan['products'].items():
        for pr in b['pairs']:
            if pr.get('computable'):
                flat.append(pr)
    flat.sort(key=lambda x: (-(x['extremeness'] if x['extremeness'] is not None else -1), x['product']))
    # 05 表位置映射（用于公式引用）
    sample_index = {}
    for i, pr in enumerate(flat, 1):
        pct = pr.get('percentile')
        grade = pr.get('grade', '')
        note = ''
        if pr.get('block_reasons'):
            note = '；'.join(pr['block_reasons'])
        if pr.get('n_history', 0) < 3:
            note = (note + '；' if note else '') + '历史样本不足，不给分位'
        ws.write_number(r, 0, i, F['num0'])
        ws.write(r, 1, pr['product'], F['txt'])
        ws.write(r, 2, prod_names.get(pr['product'], ''), F['txt'])
        ws.write(r, 3, pr['label'], F['txt'])
        ws.write_number(r, 4, pr['near_settle'] or 0, F['num'])
        ws.write_number(r, 5, pr['far_settle'] or 0, F['num'])
        ws.write_formula(r, 6, f'=E{r+1}-F{r+1}', F['formula'], pr['spread'])
        ws.write_number(r, 7, pr.get('mean_hist') if pr.get('mean_hist') is not None else 0, F['num'])
        if pct is None:
            ws.write(r, 8, '样本不足', F['dim'])
            ws.write(r, 9, '', F['dim'])
            ws.write(r, 12, '', F['dim'])
        else:
            ws.write_number(r, 8, pct, F['pct'])
            ws.write_number(r, 9, pr.get('z') or 0, F['num'])
            ws.write_number(r, 12, pr.get('extremeness') or 0, F['num'])
        ws.write_number(r, 10, pr.get('spread_1m_ago') if pr.get('spread_1m_ago') is not None else 0, F['num'])
        if pr.get('change_1m') is not None:
            ws.write_formula(r, 11, f'=G{r+1}-K{r+1}', F['formula'], pr['change_1m'])
        else:
            ws.write(r, 11, '', F['dim'])
        ws.write_number(r, 13, pr.get('n_history') or 0, F['num0'])
        is_ext = ('极端' in grade)
        ws.write(r, 14, grade, F['ext'] if is_ext else F['txt'])
        ws.write(r, 15, '可交易' if not pr.get('block_reasons') else '受限', F['ok'] if not pr.get('block_reasons') else F['txt'])
        ws.write(r, 16, note, F['txtw'])
        r += 1
    end4 = r
    r += 1
    ws.write(r, 0, '口径说明', F['warn'])
    ws.merge_range(r, 1, r, 16, 'Z 分数 = (当前月差 − 历史均值) / 历史标准差(样本)。极端度 = |分位 − 50| × 2，'
                                '0＝处于历史中位，100＝处于历史极限。可交易性受限的原因码见「10 数据质量与限制」。', F['txtw'])
    ws.set_row(r, 30)
    ws.autofilter(hr, 0, end4 - 1, 16)

    # ---------------- 05 历史可比样本 ----------------
    ws, r = ws_setup(wb, '05 历史可比样本', [4, 10, 18, 6, 12, 12, 12, 12, 14, 14, 14],
                     '05 历史可比样本明细（同品种 × 同月份组合 × 同剩余期限）',
                     '每行 = 某一历史年度合约在"同剩余期限周数"下的月差观测值')
    cols = ['#', '品种', '月份组合', '年度', '历史合约', '观测日', '月差', '近月价', '远月价',
            '剩余期限(周)', '对齐方式']
    write_header(ws, r, cols)
    r += 1
    idx = 0
    for pr in flat:
        for h in pr.get('history', []):
            idx += 1
            ws.write_number(r, 0, idx, F['num0'])
            ws.write(r, 1, pr['product'], F['txt'])
            ws.write(r, 2, pr['label'], F['txt'])
            ws.write_number(r, 3, h['year'], F['num0'])
            ws.write(r, 4, f"{h['near_sym']}/{h['far_sym']}", F['txt'])
            ws.write_datetime(r, 5, __import__('datetime').datetime.fromisoformat(str(h['date'])),
                              F['date'])
            ws.write_number(r, 6, h['spread'], F['num'])
            ws.write_number(r, 7, h['near'], F['num'])
            ws.write_number(r, 8, h['far'], F['num'])
            ws.write_number(r, 9, h['week_to_near'], F['num'])
            ws.write(r, 10, '整周精确' if h.get('week_aligned_exact', True) else '就近(±1周)', F['txt'])
            r += 1
    end5 = r
    r += 1
    ws.write(r, 0, '注意', F['warn'])
    ws.merge_range(r, 1, r, 10, '不同月份组合的样本分别统计，不在本表内合并。若某组合在某年度无同剩余期限的双边有效报价，'
                                '该年度即为空缺，不补数。', F['txtw'])
    ws.set_row(r, 28)
    ws.autofilter(3, 0, end5 - 1, 10)

    # ---------------- 06 分位统计（纯公式） ----------------
    ws, r = ws_setup(wb, '06 分位统计', [10, 18, 12, 12, 10, 10, 12, 12, 12, 12, 12, 12, 12, 14],
                     '06 分位统计（Excel 原生公式，改「05」数据即重算）',
                     '统计口径：AVEARGE/STDEV/MIN/MAX/PERCENTILE/COUNTIF，样本取自「05 历史可比样本」对应组合')
    cols = ['品种', '月份组合', '样本数N', '均值', '标准差', '最小值', 'P05', 'P25', '中位数P50',
            'P75', 'P95', '最大值', '当前分位(%)', '评级(公式)']
    write_header(ws, r, cols)
    r += 1
    for pr in flat:
        p = pr['product']
        # 在 05 表中按品种+组合定位行区间
        rows_in_05 = []
        for rr in range(3, end5):
            # 用 python 侧已知位置更稳妥：重建
            pass
        ws.write(r, 0, p, F['txt'])
        ws.write(r, 1, pr['label'], F['txt'])
        # 用 COUNTIFS / 数组不易跨表精确，改为引用本组合在 05 的连续区间（构建时已知）
        r += 1
    # 由于 05 行区间需精确，改为第二遍填充
    # 重新计算每个组合在 05 的区间
    start = 4  # 0-based data start row in 05 (header at row 3)
    ws6 = ws
    rrow = 4  # header row index in 06 is 3 (0-based) -> data starts 4
    for pr in flat:
        n = len(pr.get('history', []))
        r0 = start + 1  # 1-based excel row
        r1 = start + n
        col = 'G'  # 05 表的月差列
        rng = f"'05 历史可比样本'!$G${r0}:$G${r1}"
        cur = pr['spread']
        ws6.write(rrow, 0, pr['product'], F['txt'])
        ws6.write(rrow, 1, pr['label'], F['txt'])
        ws6.write_formula(rrow, 2, f'=COUNT({rng})', F['formula0'], n)
        if n > 0:
            ws6.write_formula(rrow, 3, f'=AVERAGE({rng})', F['formula'], pr.get('mean_hist'))
            ws6.write_formula(rrow, 4, f'=STDEV({rng})', F['formula'],
                              (pr.get('q95') - pr.get('q05')) / 3.29 if pr.get('q95') is not None else None)
            ws6.write_formula(rrow, 5, f'=MIN({rng})', F['formula'], pr.get('min_hist'))
            ws6.write_formula(rrow, 6, f'=PERCENTILE({rng},0.05)', F['formula'], pr.get('q05'))
            ws6.write_formula(rrow, 7, f'=PERCENTILE({rng},0.25)', F['formula'], pr.get('q25'))
            ws6.write_formula(rrow, 8, f'=PERCENTILE({rng},0.5)', F['formula'], pr.get('q50'))
            ws6.write_formula(rrow, 9, f'=PERCENTILE({rng},0.75)', F['formula'], pr.get('q75'))
            ws6.write_formula(rrow, 10, f'=PERCENTILE({rng},0.95)', F['formula'], pr.get('q95'))
            ws6.write_formula(rrow, 11, f'=MAX({rng})', F['formula'], pr.get('max_hist'))
            # 当前分位：((小于)+0.5*等于)/N*100
            ref = f"'04 月差计算'!$G${4 + [x['label'] for x in flat].index(pr['label'])}"
        if n > 0 and pr.get('percentile') is not None:
            ws6.write_formula(rrow, 12,
                              f'=IF(C{rrow+1}<3,"",(COUNTIF({rng},"<"&{cur})+0.5*COUNTIF({rng},{cur}))/C{rrow+1}*100)',
                              F['formulapct'], pr['percentile'])
            ws6.write_formula(rrow, 13,
                              f'=IF(C{rrow+1}<3,"样本不足",IF(L{rrow+1}="","",IF(OR(M{rrow+1}<=5,M{rrow+1}>=95),'
                              f'"极端","正常")))', F['txt'], pr.get('grade'))
        else:
            ws6.write(rrow, 12, '样本不足', F['dim'])
            ws6.write(rrow, 13, '样本不足', F['dim'])
        start += n
        rrow += 1

    # ---------------- 07 产业面 ----------------
    ws, r = ws_setup(wb, '07 产业面', [10, 12, 34, 12, 10, 12, 12, 12, 34, 8],
                     '07 产业面：库存 / 仓单 / 现货 / 基差',
                     '可信度：A=抓取正文+明确日期；B=研报/媒体转述；C=口径不明；D=未获取。缺数据一律留空，不估算。')
    cols = ['品种', '类别', '指标', '数值', '单位', '变化', '变化%', '日期', '来源', '可信度']
    write_header(ws, r, cols)
    r += 1
    for p, d in industry['products'].items():
        w = d.get('warrant')
        if w:
            ws.write(r, 0, p, F['txt'])
            ws.write(r, 1, '仓单', F['txt'])
            ws.write(r, 2, '注册仓单', F['txtw'])
            ws.write_number(r, 3, w.get('value') or 0, F['num0'])
            ws.write(r, 4, w.get('unit'), F['txt'])
            ws.write_number(r, 5, w.get('chg') if w.get('chg') is not None else 0, F['num0'])
            ws.write(r, 6, '', F['dim'])
            ws.write(r, 7, w.get('date'), F['txt'])
            ws.write(r, 8, w.get('source'), F['txtw'])
            ws.write(r, 9, w.get('confidence'), F['ok'] if w.get('confidence') == 'A' else F['txt'])
            r += 1
        for inv in d.get('inventory', []):
            ws.write(r, 0, p, F['txt'])
            ws.write(r, 1, '库存', F['txt'])
            ws.write(r, 2, inv['name'], F['txtw'])
            ws.write_number(r, 3, inv.get('value') if inv.get('value') is not None else 0, F['num'])
            ws.write(r, 4, inv.get('unit'), F['txt'])
            ws.write_number(r, 5, inv.get('chg') if inv.get('chg') is not None else 0, F['num'])
            ws.write_number(r, 6, inv.get('chg_pct') if inv.get('chg_pct') is not None else 0, F['pct'])
            ws.write(r, 7, inv.get('date'), F['txt'])
            ws.write(r, 8, (inv.get('source') or '') + ((' ' + inv['url']) if inv.get('url') else ''), F['txtw'])
            ws.write(r, 9, inv.get('confidence'), F['ok'] if inv.get('confidence') == 'A' else F['txt'])
            r += 1
        for key, cat in (('spot', '现货'), ('spot_alt', '现货'), ('basis', '基差')):
            s = d.get(key)
            if not s:
                continue
            ws.write(r, 0, p, F['txt'])
            ws.write(r, 1, cat, F['txt'])
            ws.write(r, 2, s.get('region') or s.get('note') or cat, F['txtw'])
            ws.write_number(r, 3, s.get('value') or 0, F['num'])
            ws.write(r, 4, s.get('unit'), F['txt'])
            ws.write(r, 5, '', F['dim'])
            ws.write(r, 6, '', F['dim'])
            ws.write(r, 7, s.get('date') or '', F['txt'])
            ws.write(r, 8, s.get('source') or '', F['txtw'])
            ws.write(r, 9, s.get('confidence'), F['ok'] if s.get('confidence') == 'A' else F['txt'])
            r += 1

    # ---------------- 08 供需事件 ----------------
    ws, r = ws_setup(wb, '08 供需事件', [10, 16, 70, 34, 16],
                     '08 供需事件时间线',
                     '事件仅用于解释期限结构为什么处在当前位置，不构成方向判断或交易建议')
    cols = ['品种', '日期', '事件', '影响', '方向标签']
    write_header(ws, r, cols)
    r += 1
    for p, d in industry['products'].items():
        for e in d.get('events', []):
            ws.write(r, 0, p, F['txt'])
            ws.write(r, 1, e.get('date'), F['txt'])
            ws.write(r, 2, e.get('event'), F['txtw'])
            ws.write(r, 3, e.get('impact') or '', F['txtw'])
            ws.write(r, 4, e.get('direction') or '', F['txt'])
            ws.set_row(r, 30)
            r += 1

    # ---------------- 09 公式说明 ----------------
    ws, r = ws_setup(wb, '09 公式说明', [26, 46, 60],
                     '09 指标定义与 Excel 公式实现')
    cols = ['指标', '定义', 'Excel 实现 / 说明']
    write_header(ws, r, cols)
    r += 1
    fx = [
        ('月差 Spread', '近月结算价 − 远月结算价（元/吨）', '=E-F（04 表 G 列）'),
        ('距交割月数', '(交割年 − 数据年) × 12 + (交割月 − 数据月)', '=(C-YEAR(DATEVALUE("2026-10-20")))*12+(D-MONTH(DATEVALUE("2026-10-20")))'),
        ('相邻月价差', '后一交割月结算价 − 前一交割月结算价', '=C(n)-C(n-1)（03 表）'),
        ('曲线斜率 OLS', '价格对距交割月数的最小二乘斜率', '=SLOPE(结算价区, 距交割月数区)；<-3 判正向市场，>3 判反向市场'),
        ('可比历史样本', '同品种 × 同(近月,远月)组合 × 同剩余期限整周数', '剩余期限 = floor((近月交割月结束日 − 观测日)/7天)；每年取 1 个'),
        ('历史分位', '当前月差在可比样本中的位置', '=(COUNTIF(区间,"<"&当前)+0.5*COUNTIF(区间,当前))/N*100'),
        ('历史均值', '可比样本算术平均', '=AVERAGE(区间)'),
        ('标准差', '可比样本样本标准差', '=STDEV(区间)（n−1 分母）'),
        ('Z 分数', '(当前 − 均值) / 标准差', '=(当前-AVERAGE(区间))/STDEV(区间)'),
        ('近1月变化', '当前月差 − 30 个自然日前最近交易日月差', '=G-K（04 表）'),
        ('极端度', '|分位 − 50| × 2', '0＝历史中位，100＝历史极限'),
        ('评级阈值', '≥95% 或 ≤5% 为极端；≥80% 或 ≤20% 为偏高', '可改「06」表公式中的 5/95 阈值'),
        ('样本不足', '可比历史年份 < 3（或 < 设定阈值）', '不给分位，写"样本不足"'),
    ]
    for a, b, c in fx:
        ws.write(r, 0, a, F['txt'])
        ws.write(r, 1, b, F['txtw'])
        ws.write(r, 2, c, F['txtw'])
        ws.set_row(r, 26)
        r += 1

    # ---------------- 10 数据质量与限制 ----------------
    ws, r = ws_setup(wb, '10 数据质量与限制', [12, 16, 60, 50],
                     '10 数据质量、样本不足与不可比说明')
    cols = ['品种', '组合/项目', '问题', '说明与处理']
    write_header(ws, r, cols)
    r += 1
    issues = []
    for p, b in scan['products'].items():
        issues.append((p, '—', '价格口径', f"{'最新价(东财)' if quotes.get('price_basis_by_product', {}).get(p)=='last' else '交易所结算价'}；与其他品种口径不同，不混算"))
        for pr in b['pairs']:
            if pr.get('n_history', 0) < 3:
                issues.append((p, pr['label'], '历史样本不足',
                               f"N={pr.get('n_history', 0)}，低于阈值，不给分位；跨年度（>12个月）组合天然无法构造同剩余期限样本"))
            for br in pr.get('block_reasons', []):
                issues.append((p, pr['label'], '可交易性受限', br))
    issues.append(('—', '大商所仓单', '数据未取得原始文件',
                   'DCE 官网对脚本返回 HTTP 412；PP 仓单采用媒体转述的 2026-10-19 数值（可信度 B）'))
    issues.append(('—', 'PTA 仓单跳升', '异常未解释',
                   '10-08 约1,002张 → 10-09 约36,187张，抓取页面均未说明原因，仅记录事实，不作累库结论'))
    issues.append(('—', '甲醇港口库存', '多口径并存', '隆众30.51(10-08) / 卓创37.41(10-08) / 金联创30.44(10-15)，不可混算环比'))
    issues.append(('—', '历史区间', '仅覆盖 2022–2026 年度合约', '更早年度合约在新浪接口不可取；样本 N 上限为 5（含当期）'))
    issues.append(('—', '成本项', '未扣除', '仓储费、资金成本、交割成本、品级/地区升贴水均未计入月差'))
    seen = set()
    for row in issues:
        key = (row[0], row[1], row[2])
        if key in seen:
            continue
        seen.add(key)
        for c, v in enumerate(row):
            ws.write(r, c, v, F['txtw'] if c >= 2 else F['txt'])
        ws.set_row(r, 26)
        r += 1

    wb.close()
    return out_path


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', default='out/scan_result.json')
    ap.add_argument('--industry', default='industry_data.json')
    ap.add_argument('--quotes', default=None)
    ap.add_argument('--out', default='out/异常月差扫描工作簿.xlsx')
    a = ap.parse_args()
    scan = json.load(open(a.scan, encoding='utf-8'))
    industry = json.load(open(a.industry, encoding='utf-8'))
    if not a.quotes:
        import glob as _glob
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        name = f'quotes_{scan["as_of"]}.json'
        cands = [os.path.join(root, name),
                 os.path.join(root, 'data', name),
                 os.path.join(os.path.dirname(a.scan) or '.', name)]
        cands += sorted(_glob.glob(os.path.join(root, 'examples', '*', name)))
        a.quotes = next((c for c in cands if os.path.exists(c)), None)
    if not a.quotes:
        print('!! 未找到 quotes_<as-of>.json，请先运行 fetch_quotes.py 或用 --quotes 指定')
        return 1
    quotes = json.load(open(a.quotes, encoding='utf-8'))
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    p = build(scan, industry, quotes, a.out)
    print('wrote', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
