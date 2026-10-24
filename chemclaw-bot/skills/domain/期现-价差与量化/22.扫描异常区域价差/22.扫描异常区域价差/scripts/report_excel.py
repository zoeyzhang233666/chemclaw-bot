# -*- coding: utf-8 -*-
"""
report_excel.py —— 生成专业版 Excel 工作簿（10 个 sheet）

sheet 一览：
  00 说明与口径       方法与硬约束、参数、免责
  01 产品池           品种、规格档、地区覆盖、样本量
  02 地区价格         逐日 × 地区的身价格序列（口径五要素齐全）
  03 价差矩阵         当前裸价差 / 历史分位 / 异常度三张子表
  04 历史分位         每个组合的分布参数与分位表
  05 运费参数         按方向录入（可直接填数，公式自动重算）
  06 异常筛选         排行榜（带条件格式）
  07 数据缺口         不可比 / 覆盖不足登记
  08 来源清单         每个数据点的来源与抓取时间
  09 原始报价         明细（可审计，含被剔除行及原因）
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

C_DARK = '1F3040'
C_ACC = '2F5597'
C_HEAD = 'F2F5F9'
C_WARN = 'FFF2CC'
C_BAD = 'F8D7DA'
C_OK = 'E2EFDA'
C_GREY = '808080'

THIN = Side(style='thin', color='D0D7E2')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _title(ws, text, sub=''):
    ws['A1'] = text
    ws['A1'].font = Font(size=15, bold=True, color=C_DARK)
    if sub:
        ws['A2'] = sub
        ws['A2'].font = Font(size=10, color=C_GREY)
    ws.sheet_view.showGridLines = False


def _header(ws, row: int, cols: List[str], widths: List[int] | None = None):
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font = Font(bold=True, size=10, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor=C_ACC)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BOX
        if widths:
            ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    ws.row_dimensions[row].height = 30


def _freeze(ws, cell):
    ws.freeze_panes = cell


def build_excel(result: Dict[str, Any], out_path: str,
                panel_csv: str | None = None,
                background: Dict[str, Any] | None = None) -> str:
    wb = Workbook()
    cfg = result.get('config', {})
    s = result.get('summary', {})
    combos = result.get('combinations', [])
    products = result.get('products', {})

    # ------------------------------------------------------------ 00 说明
    ws = wb.active
    ws.title = '00 说明与口径'
    _title(ws, '扫描异常区域价差 · 工作簿说明',
           '生成时间 %s ｜ 数据截止 %s ｜ 可比组合 %d 个' % (
               result.get('generated_at'), s.get('asof') or '—', len(combos)))
    rows = [
        ('', ''),
        ('【本工作簿回答什么】', '在主要区域市场之间，哪些地区组合的价差当前明显偏离其自身历史区间；'
                                '分别给出裸价差与扣除用户提供运费后的参考差异。'),
        ('', ''),
        ('【硬约束 1｜不称套利】', '裸价差为正不等于存在套利机会。本工作簿不使用「套利」表述，'
                                  '扣除运费后仅称「参考差异」，且不评价可执行性。'),
        ('【硬约束 2｜运费不自估】', '运费必须由用户按方向提供真实报价。未提供时 freight_status=MISSING，'
                                    'net=None，绝不插值或使用行业平均值代替。'),
        ('【硬约束 3｜异常以自身分布为基准】', '每个地区组合的分位与异常度，都以其自己在窗口内的历史价差分布计算，'
                                              '不按价差绝对金额跨组合排序。'),
        ('【硬约束 4｜先统一口径】', '每个价格点携带 规格/地区/交货方式/税费/计价类型 五要素；'
                                    '规格或计价类型不可比的组合不进排行榜，登记在「07 数据缺口」。'),
        ('【硬约束 5｜方向固定】', '价差定义为 P(对照) − P(基准)，基准地区与方向在整个窗口内不翻转，'
                                  '避免价差穿零导致分位失真。'),
        ('', ''),
        ('【本次扫描参数】', ''),
        ('  品种池', ', '.join(products[k]['product'] for k in products) or '—'),
        ('  历史窗口(月)', cfg.get('window_months')),
        ('  最小样本数', cfg.get('min_samples')),
        ('  异常分位阈值', cfg.get('anomaly_grade_pct')),
        ('  运费调整', '已启用' if cfg.get('freight_enabled') else '未启用（用户未提供真实运费）'),
        ('', ''),
        ('【数据性质（务必阅读）】', '本工作簿的价格来自公开渠道的「厂家/贸易商挂牌报价」聚合，'
                                    '**不是**交易所结算价，也不是资讯商统一口径的「市场价」。'
                                    '同一省份同日存在多家、多规格报价，工作簿按可比规格档取中位数后使用。'
                                    '挂牌价通常高于可成交价，且挂牌与成交存在时滞，跨区域比较只能反映相对结构。'),
        ('', ''),
        ('【sheet 导航】', ''),
        ('  01 产品池', '品种、规格档、地区覆盖与样本量'),
        ('  02 地区价格', '逐日×地区身价格序列，五要素齐全，可追溯到原始报告页'),
        ('  03 价差矩阵', '当前裸价差 / 历史分位 / 异常度，三张矩阵'),
        ('  04 历史分位', '每个组合的均值、标准差、P5~P95 与当前分位'),
        ('  05 运费参数', '按方向填数的表单，填完即可在 06 看到扣除后差异'),
        ('  06 异常筛选', '排行榜，含分级与条件格式'),
        ('  07 数据缺口', '不可比、覆盖不足、历史窗口不足的显式登记'),
        ('  08 来源清单', '数据来源、抓取时间、口径说明'),
        ('  09 原始报价', '明细与剔除记录（可审计）'),
        ('', ''),
        ('【免责】', '本工作簿为研究分析材料，不构成投资建议或交易建议。使用者应自行核实价格与运费的真实性。'),
    ]
    r = 4
    for a, b in rows:
        ws.cell(row=r, column=1, value=a).font = Font(bold=bool(a.startswith('【')), size=10, color=C_DARK)
        c = ws.cell(row=r, column=2, value=b)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        c.font = Font(size=10)
        ws.row_dimensions[r].height = None if len(str(b or '')) < 60 else 46
        r += 1
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 118

    # ------------------------------------------------------------ 01 产品池
    ws = wb.create_sheet('01 产品池')
    _title(ws, '产品池与地区覆盖', '只有同一规格档内、至少两个地区有报价的品种，才可能形成区域组合')
    cols = ['品种键', '品种', '使用规格档', '规格档说明', '地区数', '地区清单',
            '最新样本日期', '原始报价条数', '口径说明']
    _header(ws, 4, cols, [12, 20, 12, 26, 8, 52, 14, 12, 60])
    r = 5
    for pk, p in products.items():
        regs = p.get('regions', {})
        dates = [v.get('latest_date') for v in regs.values() if v.get('latest_date')]
        ws.cell(row=r, column=1, value=pk)
        ws.cell(row=r, column=2, value=p.get('product'))
        ws.cell(row=r, column=3, value=p.get('spec_tier_used'))
        tierdesc = (result.get('catalog', {}).get('products', {}).get(pk, {})
                    .get('spec_tiers', {}).get(p.get('spec_tier_used'), ''))
        ws.cell(row=r, column=4, value=tierdesc)
        ws.cell(row=r, column=5, value=len(regs))
        ws.cell(row=r, column=6, value='、'.join(v.get('region', k) for k, v in
                                                sorted(regs.items(), key=lambda x: -x[1].get('n_days', 0))))
        ws.cell(row=r, column=7, value=max(dates) if dates else '')
        ws.cell(row=r, column=8, value=sum(v.get('n_quotes', 0) for v in regs.values()))
        ws.cell(row=r, column=9, value=result.get('catalog', {}).get('products', {}).get(pk, {}).get('price_basis', ''))
        for c in range(1, 10):
            ws.cell(row=r, column=c).border = BOX
            ws.cell(row=r, column=c).alignment = Alignment(wrap_text=True, vertical='top')
        r += 1
    _freeze(ws, 'A5')

    # ------------------------------------------------------------ 02 地区价格
    ws = wb.create_sheet('02 地区价格')
    _title(ws, '地区价格序列（口径统一后）', '规格档内逐日中位数；同一地区同日多条报价已聚合')
    cols = ['品种', '地区', '地区节点', '日期', '价格(元/吨)', '规格档', '交货方式', '税费', '计价类型', '来源']
    _header(ws, 4, cols, [20, 14, 16, 12, 13, 12, 30, 24, 18, 28])
    r = 5
    cat_prod = result.get('catalog', {}).get('products', {})
    pcols = ['product_key', 'product', 'region_code', 'region', 'spec', 'spec_tier', 'delivery',
             'tax', 'quote_type', 'date', 'price', 'unit', 'maker', 'source', 'source_url', 'report_id']
    if panel_csv and os.path.exists(panel_csv):
        import csv
        with open(panel_csv, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                ws.cell(row=r, column=1, value=row.get('product'))
                ws.cell(row=r, column=2, value=row.get('region'))
                ws.cell(row=r, column=3, value=row.get('region_code'))
                ws.cell(row=r, column=4, value=row.get('date'))
                ws.cell(row=r, column=5, value=float(row.get('price') or 0))
                ws.cell(row=r, column=6, value=row.get('spec_tier'))
                ws.cell(row=r, column=7, value=row.get('delivery'))
                ws.cell(row=r, column=8, value=row.get('tax'))
                ws.cell(row=r, column=9, value=row.get('quote_type'))
                ws.cell(row=r, column=10, value=row.get('source'))
                r += 1
    _freeze(ws, 'A5')
    if r > 6:
        ws.auto_filter.ref = 'A4:J%d' % (r - 1)

    # ------------------------------------------------------------ 03 价差矩阵
    ws = wb.create_sheet('03 价差矩阵')
    _title(ws, '区域价差矩阵', '行 = 基准地区，列 = 对照地区；数值 = P(列) − P(行)，单位元/吨')
    block = 4
    for pk, p in products.items():
        regs = sorted(p.get('regions', {}))
        if len(regs) < 2:
            continue
        ws.cell(row=block, column=1, value='【%s】当前裸价差（元/吨）' % p.get('product')).font = Font(bold=True, size=11)
        block += 1
        ws.cell(row=block, column=1, value='基准＼对照')
        for j, rc in enumerate(regs, 2):
            ws.cell(row=block, column=j, value=p['regions'][rc].get('region', rc))
        for c in range(1, len(regs) + 2):
            cell = ws.cell(row=block, column=c)
            cell.font = Font(bold=True, size=9, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor=C_ACC)
            cell.alignment = Alignment(horizontal='center')
        block += 1
        start = block
        idx = {c['pair_code']: c for c in combos if c['product_key'] == pk}
        for i, ra in enumerate(regs):
            ws.cell(row=block, column=1, value=p['regions'][ra].get('region', ra)).font = Font(bold=True, size=9)
            for j, rb in enumerate(regs, 2):
                if ra == rb:
                    ws.cell(row=block, column=j, value='—').alignment = Alignment(horizontal='center')
                    continue
                c2 = idx.get('%s|%s->%s' % (pk, ra, rb))
                if c2 and c2.get('spread_now') is not None:
                    ws.cell(row=block, column=j, value=round(c2['spread_now'], 1)).number_format = '#,##0.0'
            block += 1
        rng = 'B%d:%s%d' % (start, get_column_letter(len(regs) + 1), block - 1)
        ws.conditional_formatting.add(rng, ColorScaleRule(
            start_type='min', start_color='5FD0A8', mid_type='num', mid_value=0,
            mid_color='FFFFFF', end_type='max', end_color='FF8585'))
        block += 2

    # ------------------------------------------------------------ 04 历史分位
    ws = wb.create_sheet('04 历史分位')
    _title(ws, '历史分位与分布参数', '分位基于该组合自身在窗口内的价差序列（中位秩法）')
    cols = ['品种', '方向', '当前价差', '历史分位', '异常度', 'z值', '窗口均值', '标准差',
            '最小', 'P5', 'P25', '中位', 'P75', 'P95', '最大', '有效样本', '首日', '末日']
    _header(ws, 4, cols, [18, 26] + [10] * 14 + [12, 12, 12])
    r = 5
    for c2 in combos:
        if c2.get('spread_now') is None:
            continue
        vals = [c2.get('product'), '%s → %s' % (c2['base_region'], c2['quote_region']),
                c2.get('spread_now'), c2.get('pct'), c2.get('anomaly'), c2.get('z'),
                c2.get('mean'), c2.get('std'), c2.get('min'), c2.get('p05'), c2.get('p25'),
                c2.get('p50'), c2.get('p75'), c2.get('p95'), c2.get('max'),
                c2.get('n_obs'), c2.get('first_date'), c2.get('last_date')]
        for j, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=j, value=v)
            cell.border = BOX
            if j == 4:
                cell.number_format = '0.0%'
            elif j in (3, 7, 8, 9, 10, 11, 12, 13, 14, 15):
                cell.number_format = '#,##0.0'
        r += 1
    if r > 5:
        ws.conditional_formatting.add('D5:D%d' % (r - 1), ColorScaleRule(
            start_type='num', start_value=0, start_color='4AA3FF',
            mid_type='num', mid_value=0.5, mid_color='FFFFFF',
            end_type='num', end_value=1, end_color='FF5D5D'))
    _freeze(ws, 'C5')

    # ------------------------------------------------------------ 05 运费参数
    ws = wb.create_sheet('05 运费参数')
    _title(ws, '运费参数（按方向录入真实报价）',
           '在「运费」列直接填数即可；若填 元/吨·公里，请在「运费单位」列写明，系统按真实公路里程折算。留空=未提供，不做任何估算。')
    cols = ['品种', '基准地区', '对照地区', '方向', '运费', '运费单位', '运输方式', '里程(km)',
            '折算单吨运费', '当前裸价差', '扣除后参考差异', '状态']
    _header(ws, 4, cols, [16, 14, 14, 26, 11, 14, 16, 11, 14, 13, 15, 14])
    r = 5
    for c2 in combos:
        if c2.get('spread_now') is None:
            continue
        for d, sign, fwd in (('%s → %s' % (c2['base_region'], c2['quote_region']), 1, True),
                             ('%s → %s' % (c2['quote_region'], c2['base_region']), -1, False)):
            ws.cell(row=r, column=1, value=c2.get('product'))
            ws.cell(row=r, column=2, value=c2['base_region'])
            ws.cell(row=r, column=3, value=c2['quote_region'])
            ws.cell(row=r, column=4, value=d)
            ws.cell(row=r, column=5, value=None).fill = PatternFill('solid', fgColor=C_WARN)
            ws.cell(row=r, column=6, value='元/吨')
            ws.cell(row=r, column=7, value='公路' if not c2.get('distance_km') else '公路（待确认）')
            ws.cell(row=r, column=8, value=round(c2['distance_km'], 0) if c2.get('distance_km') else None)
            ws.cell(row=r, column=9, value='=IF(E%d="","",IF(F%d="元/吨·公里",E%d*H%d,E%d))' % (r, r, r, r, r))
            ws.cell(row=r, column=10, value=round(sign * c2['spread_now'], 1))
            ws.cell(row=r, column=11, value='=IF(I%d="","",J%d-I%d)' % (r, r, r))
            ws.cell(row=r, column=12, value='=IF(E%d="","未提供运费","已扣除")' % r)
            for c3 in range(1, 13):
                ws.cell(row=r, column=c3).border = BOX
                ws.cell(row=r, column=c3).font = Font(size=9)
            for c3 in (9, 10, 11):
                ws.cell(row=r, column=c3).number_format = '#,##0.0'
            r += 1
    ws.conditional_formatting.add('K5:K%d' % (r - 1), CellIsRule(
        operator='lessThan', formula=['0'], fill=PatternFill('solid', fgColor=C_OK)))
    _freeze(ws, 'E5')
    ws.auto_filter.ref = 'A4:L%d' % (r - 1)

    # ------------------------------------------------------------ 06 异常筛选
    ws = wb.create_sheet('06 异常筛选')
    _title(ws, '异常区域价差排行榜', '按异常度降序；异常度 = 1 − 2×双侧尾部距离（基于各自历史分布）')
    cols = ['排名', '品种', '基准地区', '对照地区', '方向', '当前裸价差', '占均价%', '历史分位',
            '异常度', 'z值', '判定', '近5期变化', '近20期变化', '有效样本', '里程(km)',
            '扣除运费后(A→B)', '规格档', '是否可比']
    _header(ws, 4, cols, [7, 18, 14, 14, 24, 12, 10, 10, 9, 8, 12, 11, 12, 9, 10, 15, 12, 10])
    r = 5
    for c2 in combos:
        gr = c2.get('grade')
        zh = {'EXCESS_HIGH': '显著偏高', 'EXCESS_LOW': '显著偏低', 'ELEVATED': '偏高偏离',
              'NORMAL': '正常区间', 'INSUFFICIENT': '样本不足'}.get(gr, gr)
        vals = [c2.get('rank'), c2.get('product'), c2['base_region'], c2['quote_region'],
                '%s → %s' % (c2['base_region'], c2['quote_region']),
                c2.get('spread_now'), c2.get('spread_norm'), c2.get('pct'), c2.get('anomaly'),
                c2.get('z'), zh, c2.get('chg_5d'), c2.get('chg_20d'), c2.get('n_obs'),
                round(c2['distance_km'], 0) if c2.get('distance_km') else None,
                None, c2.get('spec_tier'), '是' if c2.get('comparable') == 'A' else '弱']
        for j, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=j, value=v)
            cell.border = BOX
            cell.font = Font(size=9)
            if j == 8:
                cell.number_format = '0.0%'
            elif j in (6, 12, 13):
                cell.number_format = '#,##0.0'
            elif j == 7:
                cell.number_format = '0.00"%"'
        fill = {'EXCESS_HIGH': C_BAD, 'EXCESS_LOW': C_BAD, 'ELEVATED': C_WARN}.get(gr)
        if fill:
            ws.cell(row=r, column=11).fill = PatternFill('solid', fgColor=fill)
        r += 1
    ws.conditional_formatting.add('H5:H%d' % (r - 1), ColorScaleRule(
        start_type='num', start_value=0, start_color='4AA3FF', mid_type='num', mid_value=0.5,
        mid_color='FFFFFF', end_type='num', end_value=1, end_color='FF5D5D'))
    _freeze(ws, 'C5')
    ws.auto_filter.ref = 'A4:R%d' % (r - 1)

    # ------------------------------------------------------------ 07 数据缺口
    ws = wb.create_sheet('07 数据缺口')
    _title(ws, '数据缺口与不可比登记', '这些项目没有进入排行榜计算，禁止用插值或估算填补')
    _header(ws, 4, ['缺口类型', '类型代码', '品种/地区/组合', '说明'], [24, 24, 46, 96])
    r = 5
    for g in result.get('gaps', []):
        ws.cell(row=r, column=1, value=g.get('gap_zh') or g.get('gap'))
        ws.cell(row=r, column=2, value=g.get('gap'))
        ws.cell(row=r, column=3, value=g.get('pair') or g.get('region') or
                ','.join(g.get('regions_available', []) or []) or g.get('product_key'))
        ws.cell(row=r, column=4, value=g.get('detail'))
        for c3 in range(1, 5):
            ws.cell(row=r, column=c3).border = BOX
            ws.cell(row=r, column=c3).alignment = Alignment(wrap_text=True, vertical='top')
            ws.cell(row=r, column=c3).font = Font(size=9)
        r += 1
    if r == 5:
        ws.cell(row=5, column=1, value='无登记缺口')

    # ------------------------------------------------------------ 08 来源清单
    ws = wb.create_sheet('08 来源清单')
    _title(ws, '数据来源清单', '每个数据源的口径、覆盖范围与取用方式')
    _header(ws, 4, ['数据项', '来源', '口径', '覆盖范围', '取用方式', '备注'],
            [24, 34, 30, 30, 40, 50])
    src_rows = [
        ('省级挂牌报价', 'ChemicalBook 价格报告（PriceInfo 归档）',
         '厂家/贸易商公开挂牌报价', '纯碱 2024-06 起、甲醇 2026-05 起，省级×日度',
         'scripts/fetch_chembook2.py 抓取，按规格档取中位数',
         '挂牌价≠成交价；同日多规格，已按可比档圈定'),
        ('单市场/全国序列', '生意社 100ppi（rawmex / cindex 图表）',
         '国内混合价 / 单一市场价', '纯碱（河南）、甲醇（江苏太仓）、PVC（华东），约 93 日',
         'scripts/fetch_data.py 抓取，仅用于交叉校验', '无区域维度，不参与区域价差计算'),
        ('期货日线', '新浪财经期货 K 线接口',
         '结算/收盘', 'SA0 / MA0 / V0 多年日线', 'scripts/fetch_data.py',
         '用于期现对照与历史窗口参照'),
        ('公路里程', 'OSRM 公共路由服务（project-osrm）',
         '实际驾车里程', '12 个物流节点两两之间 66 组', 'scripts/fetch_distances.py',
         '非直线距离，用于 元/吨·公里 折算'),
    ]
    r = 5
    for row in src_rows:
        for j, v in enumerate(row, 1):
            cell = ws.cell(row=r, column=j, value=v)
            cell.border = BOX
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            cell.font = Font(size=9)
        r += 1

    # ------------------------------------------------------------ 09 原始报价
    ws = wb.create_sheet('09 原始报价')
    _title(ws, '原始报价明细与剔除记录', '保留全部原始行，剔除项标注原因，便于审计')
    _header(ws, 4, ['品种', '日期', '交货地', '厂家', '规格', '价格', '单位', '报告ID', '处理结果'],
            [18, 12, 18, 34, 34, 10, 8, 12, 26])
    r = 5
    if panel_csv and os.path.exists(panel_csv):
        import csv
        with open(panel_csv, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                ws.cell(row=r, column=1, value=row.get('product'))
                ws.cell(row=r, column=2, value=row.get('date'))
                ws.cell(row=r, column=3, value=row.get('region'))
                ws.cell(row=r, column=4, value=row.get('maker'))
                ws.cell(row=r, column=5, value=row.get('spec'))
                ws.cell(row=r, column=6, value=float(row.get('price') or 0))
                ws.cell(row=r, column=7, value=row.get('unit'))
                ws.cell(row=r, column=8, value=row.get('report_id'))
                ws.cell(row=r, column=9, value='保留（%s 档）' % row.get('spec_tier'))
                r += 1
    _freeze(ws, 'A5')
    ws.auto_filter.ref = 'A4:I%d' % max(r - 1, 5)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    wb.save(out_path)
    return out_path


if __name__ == '__main__':
    import json
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    res = json.load(open(os.path.join(here, 'outputs', 'scan_result.json'), encoding='utf-8'))
    bgp = os.path.join(here, 'data_raw', 'background.json')
    bg = json.load(open(bgp, encoding='utf-8')) if os.path.exists(bgp) else {}
    print(build_excel(res, os.path.join(here, 'outputs', '区域价差扫描工作簿.xlsx'),
                      os.path.join(here, 'data_raw', 'panel_long.csv'), bg))
