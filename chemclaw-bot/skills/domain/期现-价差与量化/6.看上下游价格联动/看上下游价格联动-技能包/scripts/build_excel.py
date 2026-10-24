# -*- coding: utf-8 -*-
"""
build_excel.py —— 生成可审计的 Excel 工作簿（原生公式，非硬编码结果）

设计原则
  1. 每个计算单元格都是**活公式**，来源数据一改，全表自动重算；
  2. 参数集中放在「参数」表，用命名区域引用，改单耗不用改公式；
  3. 每个数字都能回溯到原始数据（原始数据表保留抓取 URL 与发布时间）；
  4. 无可靠单耗时，「加工价差」表拒绝出数并写明原因（防编造）。

表结构
  00_说明            研究问题、数据源、口径、限制、禁止事项
  01_口径与来源      逐项口径 + 数据来源 + 发布时间 + 校验方式
  02_参数            单耗λ、其他成本、窗口、阶段定义（全部命名区域）
  03_原始数据        date / PX / PTA / 价差 / 来源（公式区高亮）
  04_单耗台账        0.647~0.657 逐套装置与来源文献
  05_单耗敏感性      λ 从 0.60 到 0.72 的价差均值/P10/P50/P90（公式）
  06_加工价差        价差、分位、滚动分位、扩张分位
  07_历史分位        P0~P100 分位表 + 当前分位（PERCENTILE.INC / PERCENTRANK.INC）
  08_相关性          水平 vs 收益率（CORREL/RSQ/t/p/CI），周度复核
  09_滚动相关        20/60/120 窗口滚动相关系数（公式）
  10_领先滞后        交叉相关 lag -10..+10（公式）+ 峰值
  11_阶段与背离      分阶段统计 + 背离区间
  12_公式说明        每个公式的统计含义与陷阱
"""
import csv
import datetime as dt
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

HERE = os.path.dirname(os.path.abspath(__file__))

INK = 'FF1F2937'
HEAD = 'FF1F3A5F'
ACC = 'FF2563EB'
BAND = 'FFF1F5FB'
WARN = 'FFFFF3CD'
GREY = 'FFF3F4F6'

HDR_FONT = Font(bold=True, color='FFFFFFFF', size=10.5, name='微软雅黑')
BODY = Font(size=10.5, name='微软雅黑')
BOLD = Font(size=10.5, name='微软雅黑', bold=True)
THIN = Side(style='thin', color='FFD8DEE9')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def hdr(ws, row, labels, widths=None):
    for i, t in enumerate(labels, 1):
        c = ws.cell(row=row, column=i, value=t)
        c.font, c.fill = HDR_FONT, PatternFill('solid', fgColor=HEAD)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = BOX
    ws.row_dimensions[row].height = 26
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def title(ws, text, sub=None, span=8):
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(size=15, bold=True, color=INK, name='微软雅黑')
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    ws.row_dimensions[1].height = 30
    if sub:
        c2 = ws.cell(row=2, column=1, value=sub)
        c2.font = Font(size=10, color='FF6B7280', name='微软雅黑')
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
        ws.row_dimensions[2].height = 20


def write_rows(ws, start, rows, numfmt=None, band=True):
    for j, row in enumerate(rows):
        r = start + j
        for i, v in enumerate(row, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.font = BODY
            c.border = BOX
            if isinstance(v, str) and v.startswith('='):
                c.font = Font(size=10.5, name='微软雅黑', color='FF0B5FFF')
                c.alignment = Alignment(horizontal='right')
            if numfmt and i in numfmt:
                c.number_format = numfmt[i]
            if band and j % 2 == 1:
                c.fill = PatternFill('solid', fgColor='FFFAFCFF')
        ws.row_dimensions[r].height = 17


def load_csv(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def build(data_csv, analysis_json, out_xlsx):
    A = json.load(open(analysis_json, encoding='utf-8'))
    rows = load_csv(data_csv)
    n = len(rows)
    meta = A['meta']

    wb = Workbook()

    # ---------- 00_说明 ----------
    ws = wb.active
    ws.title = '00_说明'
    ws.sheet_view.showGridLines = False
    title(ws, 'PX × PTA 上下游价格联动研究 · 数据与计算工作簿',
          '所有结果均为活公式；改动「02_参数」的 λ 或「03_原始数据」的价格，其余各表自动重算。', 6)
    ws.column_dimensions['A'].width = 4
    ws.column_dimensions['B'].width = 22
    ws.column_dimensions['C'].width = 104
    blocks = [
        ('研究问题', 'PX（上游）与 PTA（下游）之间价格传导是否明显？哪些阶段出现背离？理论加工价差处于历史什么位置？是否存在可识别的领先/滞后？'),
        ('产业关系', 'PTA 由 PX 液相空气氧化制得（醋酸为溶剂、Co-Mn-Br 催化），PX 是唯一主要原料，不存在第二条主要原料路线 → 允许做单耗折算加工价差。'),
        ('数据源', '100ppi 生意社 PX/PTA 基准价（中文，2025-05-22 起）；SunSirs 日度现货价（英文站，可回溯 2023-01）。两源在重叠期逐日一致（差异 0 元/吨）。'),
        ('价格口径', '元/吨，含增值税，华东现货基准价；同一机构同一口径，避免跨源拼接。'),
        ('频率与样本', f"日频；成对有效样本 N={n}；区间 {meta['first']} ~ {meta['last']}。缺失日不插值，统计一律用成对有效样本。"),
        ('发布时点', '生意社基准价于当日 08:30 发布，反映当日市场水平（发布滞后 0 天）；SunSirs 英文站页面日期为报道日，价格对应链接日期（滞后 1 天），已校正。'),
        ('单耗来源', '0.655 t PX/t PTA：长江期货 2023-12-18；0.653：SCI99 2026-08-20；0.647~0.657：天风证券 2019-12-14 表 4 逐套装置。见「04_单耗台账」。'),
        ('加工价差定义', 'Δ = PTA − λ×PX − 其他成本。λ 默认 0.655；「其他成本」= 醋酸贡献(≈0.032 t/t×醋酸价) + 动力 + 折旧的简化项，默认为 0，含义为「不含折旧与能源的收入型加工费」。'),
        ('禁止事项', '① 不得把相关性表述为成本传导的因果证据；② 加工价差不等同企业利润；③ 不得给出交易建议/目标价；④ 单耗无出处时不得自造系数；⑤ 缺失不插值。'),
        ('待补缺口', '醋酸价格序列未纳入（未取得可靠日频公开序列），故「其他成本」以参数形式暴露，默认 0 并在敏感性中说明；一体化装置的内部结算价与物流成本未剔除。'),
    ]
    r = 4
    for k, v in blocks:
        a = ws.cell(row=r, column=2, value=k)
        a.font = BOLD
        a.fill = PatternFill('solid', fgColor=BAND)
        a.alignment = Alignment(vertical='top', horizontal='left')
        a.border = BOX
        b = ws.cell(row=r, column=3, value=v)
        b.font = BODY
        b.alignment = Alignment(wrap_text=True, vertical='top')
        b.border = BOX
        ws.row_dimensions[r].height = max(20, 16 * (len(v) // 60 + 1))
        r += 1

    # ---------- 01_口径与来源 ----------
    ws = wb.create_sheet('01_口径与来源')
    ws.sheet_view.showGridLines = False
    title(ws, '口径与来源台账', '每一条价格数据都必须能回答：什么品种/规格、哪个地区、含不含税、哪天发布、来自哪里。', 9)
    hdr(ws, 4, ['序号', '口径项', '上游 PX', '下游 PTA', '是否一致', '处理方式', '数据来源', '发布时点', '备注'],
        [6, 16, 26, 26, 10, 30, 34, 18, 30])
    kou = [
        (1, '品种/规格', '对二甲苯 PX，优等品', '精对苯二甲酸 PTA，优等品', '是', '按品种标准品取值', '生意社/ SunSirs', '每日', ''),
        (2, '地区', '华东综合现货', '华东现货', '近似一致', '统一用华东口径，不做跨区拼价', '生意社/ SunSirs', '每日', '跨区升贴水未剔除'),
        (3, '计量单位', '元/吨', '元/吨', '是', '无需换算', '—', '—', ''),
        (4, '税费', '含增值税', '含增值税', '是', '税基相同，无需价税分离', '—', '—', '若一含税一不含税须先×1.13/1.09'),
        (5, '价格性质', '现货基准价', '现货基准价', '是', '不使用期货价格，避免基差混入', '生意社/ SunSirs', '每日 08:30', '期货仅用于交叉验证'),
        (6, '频率', '日度', '日度', '是', '成对有效样本', '—', '—', '缺失不插值'),
        (7, '日期对齐', '价格口径日', '价格口径日', '是', '英文站滞后一天已校正', '—', '—', '错位会导致价差约 80 元/吨的系统偏差'),
        (8, '交叉校验', '两源重叠期逐日一致', '两源重叠期逐日一致', '是', '差异 0 元/吨，误差 0.00%', '100ppi vs SunSirs', '—', '见 12_公式说明 的校验方法'),
    ]
    write_rows(ws, 5, kou, numfmt={1: '0'})

    # ---------- 02_参数 ----------
    ws = wb.create_sheet('02_参数')
    ws.sheet_view.showGridLines = False
    title(ws, '参数与命名区域', '改这里，全表重算。λ 只有一个出处，禁止在各表重复写死。', 6)
    hdr(ws, 4, ['参数', '名称', '取值', '单位', '来源/说明'], [24, 18, 14, 12, 60])
    params = [
        ('单耗系数 λ', 'Lambda', meta['coef'], 't PX/t PTA', '长江期货 2023-12-18（行业通用 0.655）'),
        ('单耗下限', 'LambdaLo', 0.647, 't PX/t PTA', '天风证券 2019-12-14 表4：新凤鸣独山'),
        ('单耗上限', 'LambdaHi', 0.657, 't PX/t PTA', '天风证券 2019-12-14 表4：汉邦一期/桐昆嘉兴一期'),
        ('其他成本', 'OtherCost', 0.0, '元/吨', '醋酸+动力+折旧简化项；默认 0 = 仅收入型加工费'),
        ('醋酸单耗', 'AceticCoef', 0.032, 't/t', '天风证券表4（0.029~0.040）；SCI99 0.030~0.039'),
        ('滚动窗口A', 'WinA', 20, '观测', '短期'),
        ('滚动窗口B', 'WinB', 60, '观测', '主口径（报告 §5 默认）'),
        ('滚动窗口C', 'WinC', 120, '观测', '中期'),
        ('最小有效样本比', 'MinObs', 0.8, '比例', '窗口内有效样本 < 80% 时不出数'),
        ('显著水平', 'Alpha', 0.05, '—', '双尾'),
    ]
    write_rows(ws, 5, params)
    for i, row in enumerate(params):
        name = row[1]
        cell = ws.cell(row=5 + i, column=3)
        wb.defined_names.add(__import__('openpyxl').workbook.defined_name.DefinedName(
            name, attr_text=f"'02_参数'!$C${5 + i}"))
        cell.fill = PatternFill('solid', fgColor=WARN)
        cell.font = Font(size=10.5, name='微软雅黑', bold=True, color='FF92400E')

    r0 = 5 + len(params) + 2
    ws.cell(row=r0, column=1, value='阶段定义').font = Font(size=12, bold=True, name='微软雅黑', color=INK)
    hdr(ws, r0 + 1, ['阶段', '起始日', '结束日', '名称'], [24, 14, 14, 64])
    seg = [(s['code'], s['start'], s['end'], s['name']) for s in meta.get('segments') or []]
    if not seg:
        seg = [(p['code'], p['start'], p['end'], p['name']) for p in A['phases']]
    write_rows(ws, r0 + 2, seg)

    # ---------- 03_原始数据 ----------
    ws = wb.create_sheet('03_原始数据')
    ws.sheet_view.showGridLines = False
    title(ws, '原始价格数据与派生列', 'E/F/G/H 列为公式，改 PX/PTA 两列即全表联动。', 8)
    hdr(ws, 4, ['日期', 'PX 元/吨', 'PTA 元/吨', '区间涨跌 PX%', '理论价差', 'PTA/PX', 'PX 日收益', 'PTA 日收益'],
        [14, 13, 13, 14, 13, 11, 13, 13])
    first = 5
    data_rows = []
    for i, rr in enumerate(rows):
        r = first + i
        px = float(rr['px'])
        pta = float(rr['pta'])
        data_rows.append([
            rr['date'], px, pta,
            None,
            f'=C{r}-Lambda*B{r}-OtherCost',
            f'=C{r}/B{r}',
            None if i == 0 else f'=B{r}/B{r-1}-1',
            None if i == 0 else f'=C{r}/C{r-1}-1',
        ])
    write_rows(ws, first, data_rows, numfmt={1: 'yyyy-mm-dd', 2: '#,##0.00', 3: '#,##0.00',
                                             4: '0.00%', 5: '#,##0.00', 6: '0.0000', 7: '0.00%', 8: '0.00%'})
    last = first + n - 1
    ws.freeze_panes = 'A5'
    tb = Table(displayName='PriceData', ref=f'A4:H{last}')
    tb.tableStyleInfo = TableStyleInfo(name='TableStyleLight9', showRowStripes=True)
    ws.add_table(tb)

    # ---------- 04_单耗台账 ----------
    ws = wb.create_sheet('04_单耗台账')
    ws.sheet_view.showGridLines = False
    title(ws, '单耗台账：0.647~0.657 的出处', '单耗是加工价差的唯一乘数，必须逐条可追溯；无出处不得使用。', 7)
    hdr(ws, 4, ['序号', '装置/口径', 'PX 单耗 t/t', '醋酸 t/t', '高压蒸汽 t/t', '电力 kWh/t', '来源'],
        [6, 26, 13, 12, 14, 13, 54])
    units = [
        (1, '汉邦石化一期', 0.657, 0.036, 1.15, 26.4, '天风证券 2019-12-14 表4'),
        (2, '华彬石化', 0.654, 0.040, 1.04, 68.6, '同上'),
        (3, '恒力石化 1-3#', 0.655, 0.036, 0.67, -17.8, '同上（电力为负＝副产外送）'),
        (4, '桐昆嘉兴一期', 0.657, 0.038, 0.76, 0.0, '同上'),
        (5, '汉邦石化二期', 0.654, 0.035, 0.60, 92.4, '同上'),
        (6, '桐昆嘉兴二期', 0.651, 0.033, 0.52, 0.0, '同上'),
        (7, '新凤鸣独山', 0.647, 0.032, 0.65, -25.1, '同上'),
        (8, '恒力石化 4-5#（P8+）', 0.649, 0.029, 0.48, -100.0, '同上'),
        (9, '行业通用（估值口径）', 0.655, 0.032, None, None, '长江期货 2023-12-18'),
        (10, 'SCI99 调研口径', 0.653, 0.035, None, None, 'SCI99 2026-08-20（醋酸 0.030~0.039）'),
        (11, '均值（1-8 行）', '=AVERAGE(C5:C12)', '=AVERAGE(D5:D12)', '=AVERAGE(E5:E12)', '=AVERAGE(F5:F12)', '逐套装置算术平均'),
        (12, '极差（1-8 行）', '=MAX(C5:C12)-MIN(C5:C12)', '=MAX(D5:D12)-MIN(D5:D12)', '=MAX(E5:E12)-MIN(E5:E12)', None,
         '单耗离散度：PX 仅 ±0.8%，说明单耗稳定'),
    ]
    write_rows(ws, 5, units, numfmt={3: '0.000', 4: '0.000', 5: '0.00', 6: '0.0'})

    # ---------- 05_单耗敏感性 ----------
    ws = wb.create_sheet('05_单耗敏感性')
    ws.sheet_view.showGridLines = False
    title(ws, '单耗敏感性', 'λ 每变动 0.001 t/t，价差水平整体平移约 PX 价格×0.001（元/吨）。', 8)
    hdr(ws, 4, ['λ', '价差均值', '价差中位', 'P10', 'P50', 'P90', '价差标准差', '与 λ=0.655 之差'],
        [10, 13, 13, 12, 12, 12, 13, 16])
    # 用辅助列把「每个 λ 下的价差序列」落到 M~AH 列，再用普通统计函数汇总。
    # 这样既保留敏感性对比（每列一个 λ），又避免数组公式在部分读取器上返回 #DIV/0!。
    lam_list = [round(0.600 + 0.005 * k, 3) for k in range(21)]
    ws.cell(row=3, column=13, value='辅助：各 λ 下的价差序列（列＝λ，行＝日期观测）').font = Font(
        size=9, color='FF9CA3AF', name='微软雅黑')
    for k, lam in enumerate(lam_list):
        col = 13 + k  # M 起
        ws.cell(row=4, column=col, value=lam).font = Font(size=8.5, color='FF9CA3AF', name='微软雅黑')
        ws.cell(row=4, column=col).number_format = '0.000'
        for i in range(n):
            cell = ws.cell(row=first + i, column=col,
                           value=f"='03_原始数据'!C{first + i}-{lam}*'03_原始数据'!B{first + i}-OtherCost")
            cell.font = Font(size=8, name='微软雅黑', color='FF9CA3AF')
            cell.number_format = '#,##0.00'
    lam_rows = []
    for k, lam in enumerate(lam_list):
        r = 5 + k
        L = get_column_letter(13 + k)
        rng = f'${L}${first}:${L}${last}'
        lam_rows.append([
            lam,
            f'=AVERAGE({rng})',
            f'=MEDIAN({rng})',
            f'=PERCENTILE.INC({rng},0.1)',
            f'=PERCENTILE.INC({rng},0.5)',
            f'=PERCENTILE.INC({rng},0.9)',
            f'=STDEV({rng})',
            f'=B{r}-$B$16',  # 与默认 λ=0.655 那一行（第 16 行）的均值相比
        ])
    write_rows(ws, 5, lam_rows, numfmt={1: '0.000', 2: '#,##0.00', 3: '#,##0.00', 4: '#,##0.00',
                                        5: '#,##0.00', 6: '#,##0.00', 7: '#,##0.00', 8: '#,##0.00'})
    ws.cell(row=8, column=10, value='注：PERCENTILE.INC 与报告和 Python 的线性插值分位一致；PERCENTILE.EXC 会给出不同结果，勿混用。').font = Font(
        size=10, name='微软雅黑', color='FF6B7280')

    # ---------- 06_加工价差 ----------
    ws = wb.create_sheet('06_加工价差')
    ws.sheet_view.showGridLines = False
    title(ws, '理论加工价差与分位', '价差 = PTA − λ×PX − 其他成本。分位用 PERCENTRANK.INC（与报告一致）。', 7)
    hdr(ws, 4, ['日期', 'PX', 'PTA', '加工价差', '历史分位（全样本）', '滚动60日均值', '滚动60日标准差'],
        [14, 12, 12, 13, 18, 15, 16])
    rows2 = []
    for i, rr in enumerate(rows):
        r = 5 + i
        s_row = max(first, first + i - 59)
        ok = (first + i - s_row + 1) >= 60
        rows2.append([
            f"='03_原始数据'!A{first + i}",
            f"='03_原始数据'!B{first + i}",
            f"='03_原始数据'!C{first + i}",
            f"='03_原始数据'!E{first + i}",
            f"=PERCENTRANK.INC('03_原始数据'!$E${first}:$E${last},'03_原始数据'!E{first + i})",
            f'=IF({ok},AVERAGE(\'03_原始数据\'!$E${s_row}:$E${first + i}),"")',
            f'=IF({ok},STDEV(\'03_原始数据\'!$E${s_row}:$E${first + i}),"")',
        ])
    write_rows(ws, 5, rows2, numfmt={1: 'yyyy-mm-dd', 2: '#,##0.00', 3: '#,##0.00', 4: '#,##0.00',
                                     5: '0.0%', 6: '#,##0.00', 7: '#,##0.00'})
    ws.freeze_panes = 'A5'

    # ---------- 07_历史分位 ----------
    ws = wb.create_sheet('07_历史分位')
    ws.sheet_view.showGridLines = False
    title(ws, '历史分位表', '同一张表同时给出「价差处于什么位置」和「对应多少钱」，便于业务直接引用。', 6)
    hdr(ws, 4, ['分位', '加工价差 元/吨', '含义', '分位', '加工价差 元/吨', '含义'],
        [10, 16, 30, 10, 16, 30])
    qs = [('0%', 0), ('1%', 0.01), ('5%', 0.05), ('10%', 0.1), ('25%', 0.25), ('50%', 0.5),
          ('75%', 0.75), ('90%', 0.9), ('95%', 0.95), ('100%', 1)]
    meaning = {'0%': '历史最低', '5%': '极低（历史 5% 以下）', '10%': '偏低', '25%': '下四分位',
               '50%': '中位', '75%': '上四分位', '90%': '偏高', '95%': '极高', '100%': '历史最高', '1%': '极低'}
    prow = []
    for i in range(5):
        left = qs[i]
        right = qs[i + 5] if i + 5 < len(qs) else None
        prow.append([
            left[0], f"=PERCENTILE.INC('03_原始数据'!$E${first}:$E${last},{left[1]})", meaning.get(left[0], ''),
            right[0] if right else '',
            f"=PERCENTILE.INC('03_原始数据'!$E${first}:$E${last},{right[1]})" if right else '',
            meaning.get(right[0], '') if right else '',
        ])
    # 左列 5 行、右列 5 行，共 10 个分位；write_rows 会按行写入，两列各自独立
    while len(prow) < len(qs) // 2:
        prow.append(['', '', '', '', '', ''])
    write_rows(ws, 5, prow, numfmt={1: '@', 2: '#,##0.00', 4: '@', 5: '#,##0.00'})
    rr = 11
    ws.cell(row=rr, column=1, value='定位').font = Font(size=12, bold=True, name='微软雅黑')
    hdr(ws, rr + 1, ['指标', '数值', '公式说明'], [22, 18, 70])
    stat = [
        ('最新价差', "='03_原始数据'!E" + str(last), '直接引用最后一行'),
        ('最新分位', f"=PERCENTRANK.INC('03_原始数据'!$E${first}:$E${last},'03_原始数据'!E{last})",
         'PERCENTRANK.INC：与 Python 的 pct_rank 定义一致'),
        ('均值', f"=AVERAGE('03_原始数据'!E{first}:E{last})", '全样本算术均值'),
        ('标准差(样本)', f"=STDEV('03_原始数据'!E{first}:E{last})", 'STDEV = 样本标准差；STDEV.P 为总体'),
        ('偏度', f"=SKEW('03_原始数据'!E{first}:E{last})", '>0 右偏，说明高位出现过极端值'),
        ('峰度', f"=KURT('03_原始数据'!E{first}:E{last})", '超额峰度，>0 厚尾'),
        ('样本数 N', f"=COUNT('03_原始数据'!E{first}:E{last})", '成对有效价格数'),
        ('IQR', f"=PERCENTILE.INC('03_原始数据'!E{first}:E{last},0.75)-PERCENTILE.INC('03_原始数据'!E{first}:E{last},0.25)",
         '四分位距，抗极端值'),
        ('当前价差／P50 比值', f"='03_原始数据'!E{last}/PERCENTILE.INC('03_原始数据'!E${first}:E${last},0.5)",
         '相对中位水平的位置'),
    ]
    write_rows(ws, rr + 2, stat, numfmt={2: '#,##0.0000'})

    # ---------- 08_相关性 ----------
    ws = wb.create_sheet('08_相关性')
    ws.sheet_view.showGridLines = False
    title(ws, '水平相关 vs 收益率相关', '这两个数字不可互相替代：水平高相关多半来自共同趋势，收益率才反映逐期传导。', 8)
    hdr(ws, 4, ['口径', 'Pearson r', 'R²', 'N', 't 统计量', 'p 值（双尾）', '95%CI 下限', '95%CI 上限'],
        [30, 13, 11, 8, 12, 14, 13, 13])
    rng_px = f"'03_原始数据'!$B${first}:$B${last}"
    rng_pta = f"'03_原始数据'!$C${first}:$C${last}"
    rng_rp = f"'03_原始数据'!$G${first + 1}:$G${last}"
    rng_rt = f"'03_原始数据'!$H${first + 1}:$H${last}"
    rng_sp = f"'03_原始数据'!$E${first}:$E${last}"
    def corr_block(row, label, x, y, nformula):
        return [label,
                f'=CORREL({x},{y})',
                f'=RSQ({y},{x})',
                nformula,
                f'=B{row}*SQRT((D{row}-2)/(1-B{row}^2))',
                f'=IF(D{row}>2,T.DIST.2T(ABS(E{row}),D{row}-2),"NA")',
                f'=TANH(ATANH(B{row})-NORM.S.INV(1-Alpha/2)/SQRT(D{row}-3))',
                f'=TANH(ATANH(B{row})+NORM.S.INV(1-Alpha/2)/SQRT(D{row}-3))']
    # 显式覆盖 H5:H7：write_rows 只在 str 值以 '=' 开头时写公式，
    # 但 H 列第 5~7 行落在表头宽度之外时可能被后续 hdr() 覆盖，这里统一重写一次，确保是公式。
    cb = [corr_block(5, '价格水平（PX vs PTA）', rng_px, rng_pta, f'=COUNT({rng_px})'),
          corr_block(6, '日收益率（Δ%PX vs Δ%PTA）', rng_rp, rng_rt, f'=COUNT({rng_rp})'),
          corr_block(7, '价差 vs PX 水平', rng_px, rng_sp, f'=COUNT({rng_px})')]
    write_rows(ws, 5, cb, numfmt={2: '0.0000', 3: '0.0000', 4: '0', 5: '0.0000', 6: '0.00E+00',
                                  7: '0.0000', 8: '0.0000'})
    # 强制重写 CI 两列（write_rows 只在值以 '=' 开头时按公式处理，H 列曾残留数值）
    for row in (5, 6, 7):
        ws.cell(row=row, column=7,
                value=f'=TANH(ATANH(B{row})-NORM.S.INV(1-Alpha/2)/SQRT(D{row}-3))')
        ws.cell(row=row, column=8,
                value=f'=TANH(ATANH(B{row})+NORM.S.INV(1-Alpha/2)/SQRT(D{row}-3))')
        for col in (7, 8):
            cell = ws.cell(row=row, column=col)
            cell.number_format = '0.0000'
            cell.font = Font(size=10.5, name='微软雅黑', color='FF0B5FFF')
            cell.alignment = Alignment(horizontal='right')
    ws.cell(row=8, column=1, value='Spearman 秩相关（抗异常值）').font = BOLD
    hdr(ws, 9, ['口径', 'Spearman ρ', 'N', '说明'], [30, 14, 8, 60])
    # 辅助列法：Python 侧直接给出每个观测的「平均秩」（秩是数据的确定性属性，
    # 不是统计结果，放在辅助列并标灰说明来源），随后 Spearman 用 CORREL 计算 —— 全程是活公式，
    # 且避开 SUMPRODUCT/COUNTIF 的数组比较在不同读取器上的兼容问题。

    def avg_rank(vals):
        """平均秩（并列取平均），与 Excel RANK.AVG / Python scipy rankdata 一致"""
        order = sorted(range(len(vals)), key=lambda k: vals[k])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    px_vals = [float(rr['px']) for rr in rows]
    pta_vals = [float(rr['pta']) for rr in rows]
    rpx = avg_rank(px_vals)
    rpta = avg_rank(pta_vals)
    rrp = avg_rank([float(rows[i]['px']) for i in range(1, n)])
    rrt = avg_rank([float(rows[i]['pta']) for i in range(1, n)])
    # 辅助秩放 N~Q 列（远离 A:K 主表区），避免与 CI 列 H 冲突出错。
    for col, name in [(14, 'PX 秩'), (15, 'PTA 秩'), (16, 'Δ%PX 秩'), (17, 'Δ%PTA 秩')]:
        c = ws.cell(row=3, column=col, value='辅助：' + name)
        c.font = Font(size=9, color='FF9CA3AF', name='微软雅黑')
    for i in range(n):
        r = first + i
        ws.cell(row=r, column=14, value=rpx[i])
        ws.cell(row=r, column=15, value=rpta[i])
        if i > 0:
            ws.cell(row=r, column=16, value=rrp[i - 1])
            ws.cell(row=r, column=17, value=rrt[i - 1])
        for cidx in (14, 15, 16, 17):
            cell = ws.cell(row=r, column=cidx)
            cell.number_format = '0.0'
            cell.font = Font(size=9, name='微软雅黑', color='FF9CA3AF')
    write_rows(ws, 10, [
        ('价格水平', f'=CORREL($N${first}:$N${last},$O${first}:$O${last})', f'=COUNT({rng_px})',
         '秩为数据属性（并列取平均秩），放在灰字辅助列 N/O；本格仍为活公式'),
        ('日收益率', f'=CORREL($P${first + 1}:$P${last},$Q${first + 1}:$Q${last})', f'=COUNT({rng_rp})',
         '同上；收益率的辅助秩在 P/Q。替换数据后请同步重算辅助秩'),
    ], numfmt={2: '0.0000', 3: '0'})

    ws.cell(row=14, column=1, value='有效样本量校正（Pyper & Peterman）').font = BOLD
    hdr(ws, 15, ['口径', '原始 N', 'ρ(PX)', 'ρ(PTA)', '有效 N', '说明'], [30, 10, 12, 12, 10, 46])
    write_rows(ws, 16, [
        ('价格水平', f'=COUNT({rng_px})',
         f'=CORREL({rng_px},ROW({rng_px}))', f'=CORREL({rng_pta},ROW({rng_pta}))',
         '=B16*(1-C16*D16)/(1+C16*D16)', '自相关越高，有效样本越少，显著性容易被高估'),
        ('日收益率', f'=COUNT({rng_rp})',
         f'=CORREL({rng_rp},ROW({rng_rp}))', f'=CORREL({rng_rt},ROW({rng_rt}))',
         '=B17*(1-C17*D17)/(1+C17*D17)', '自相关越高，有效样本越少，显著性容易被高估'),
    ], numfmt={2: '0', 3: '0.000', 4: '0.000', 5: '0.0'})

    # ---------- 09_滚动相关 ----------
    ws = wb.create_sheet('09_滚动相关')
    ws.sheet_view.showGridLines = False
    title(ws, '滚动相关系数（活公式）', '窗口内有效样本不足 80% 时返回空，避免小样本噪声；数据源用绝对引用，整块可安全拖动。',
          6)
    hdr(ws, 4, ['日期', '滚动20 水平', '滚动60 水平', '滚动120 水平', '滚动60 收益率', '有效窗口?'],
        [14, 14, 14, 14, 15, 12])
    DP = "'03_原始数据'!"
    roll = []
    for i in range(n):
        r = 5 + i
        # 输出第 r 行 <=> 原始数据第 (first+i) 行；s 行起算，必须 >= first
        def win(col, w):
            s_row = max(first, first + i - w + 1)
            e_row = first + i
            return f'CORREL({DP}${col}${s_row}:${col}${e_row},'
        row_vals = [f"={DP}A{first + i}"]
        for w, col in ((20, 'B'), (60, 'B'), (120, 'B')):
            s_row = max(first, first + i - w + 1)
            ok = '1' if (first + i - s_row + 1) >= w * 0.8 else '0'
            # 窗口内某一序列为常数时 CORREL 会返回 #DIV/0!（真实数据里存在连续平盘），
            # 用 IFERROR 转成空，避免整表出现错误值。
            row_vals.append(
                f'=IF({ok}=1,IFERROR({win(col, w)}{DP}$C${s_row}:$C${first + i}),""),"")')
        # 收益率：G/H 列从 first+1 行才有值
        w = 60
        s_row = max(first + 1, first + i - w + 1)
        cnt = first + i - s_row + 1
        okr = '1' if cnt >= w * 0.8 else '0'
        row_vals.append(
            f'=IF({okr}=1,IFERROR(CORREL({DP}$G${s_row}:$G${first + i},{DP}$H${s_row}:$H${first + i}),""),"")')
        # 用 IF(B52="",...) 的判断在部分读取器上不可靠，改为数值判断
        row_vals.append(f'=IF(N(B{r})=0,"不足","有效")')
        roll.append(row_vals)
    write_rows(ws, 5, roll, numfmt={1: 'yyyy-mm-dd', 2: '0.000', 3: '0.000', 4: '0.000', 5: '0.000'})
    ws.freeze_panes = 'A5'

    # ---------- 10_领先滞后 ----------
    ws = wb.create_sheet('10_领先滞后')
    ws.sheet_view.showGridLines = False
    title(ws, '交叉相关（领先/滞后）', '正 lag = PX 领先 PTA；水平与收益率两套口径分别看，结论以后者为准。', 8)
    hdr(ws, 4, ['lag', '水平 r', '水平 N', '收益率 r', '收益率 N', '方向'],
        [8, 12, 10, 12, 10, 26])
    cc = []
    for lag in range(-10, 11):
        if lag >= 0:
            xs = f"{DP}$B${first}:$B${last - lag}"
            ys = f"{DP}$C${first + lag}:$C${last}"
            xr = f"{DP}$G${first + 1}:$G${last - lag}"
            yr = f"{DP}$H${first + 1 + lag}:$H${last}"
        else:
            k = -lag
            xs = f"{DP}$B${first + k}:$B${last}"
            ys = f"{DP}$C${first}:$C${last - k}"
            xr = f"{DP}$G${first + 1 + k}:$G${last}"
            yr = f"{DP}$H${first + 1}:$H${last - k}"
        direction = '同步' if lag == 0 else ('PX 领先' if lag > 0 else 'PTA 领先')
        cc.append([lag, f'=CORREL({xs},{ys})', f'=COUNT({xs})', f'=CORREL({xr},{yr})',
                   f'=COUNT({xr})', direction])
    write_rows(ws, 5, cc, numfmt={1: '+0;-0;0', 2: '0.0000', 3: '0', 4: '0.0000', 5: '0'})
    # 峰值区必须放在 lag 表（第 5~25 行）之下，否则会落进被统计的区域里自我引用
    ws.cell(row=27, column=1, value='峰值（最大正相关所在 lag）').font = BOLD
    hdr(ws, 28, ['口径', '峰值 lag', '峰值 r', '说明'], [18, 12, 12, 60])
    peaks = []
    for lbl, col_letter in (('价格水平', 'B'), ('日收益率', 'D')):
        rng = f'${col_letter}$5:${col_letter}$25'
        lag_rng = '$A$5:$A$25'
        peaks.append((lbl,
                      f'=INDEX({lag_rng},MATCH(MAX({rng}),{rng},0))',
                      f'=MAX({rng})',
                      'MAX 找最大正相关所在 lag；若要看反向领先需另看 MIN'
                      if lbl == '价格水平' else '收益率口径噪声更大，峰值也更不稳定'))
    write_rows(ws, 29, peaks, numfmt={2: '+0;-0;0', 3: '0.0000'})

    # ---------- 11_阶段与背离 ----------
    ws = wb.create_sheet('11_阶段与背离')
    ws.sheet_view.showGridLines = False
    title(ws, '分阶段统计与背离区间', '阶段按产业逻辑预定义（不按结果反复切）；背离区间由方向冲突规则识别。', 9)
    hdr(ws, 4, ['阶段', '名称', '起', '止', 'N', 'PX 涨跌', 'PTA 涨跌', '价差均值', '区段水平相关 r'],
        [8, 40, 12, 12, 7, 12, 12, 12, 16])

    # 为每个阶段登记起止行号（放在 03_原始数据 的 N/O 列，避开表格 A4:H 与 H/K 辅助区），
    # 用 INDEX 取区间，避免对日期文本做 >=/<= 比较（那样在部分读取器里会返回 0）。
    raw = wb['03_原始数据']
    raw.cell(row=3, column=14, value='阶段起点行').font = Font(size=9, color='FF9CA3AF', name='微软雅黑')
    raw.cell(row=3, column=15, value='阶段终点行').font = Font(size=9, color='FF9CA3AF', name='微软雅黑')
    date_idx = {rr['date']: first + i for i, rr in enumerate(rows)}
    all_dates = [rr['date'] for rr in rows]

    def row_at_or_after(d):
        """返回第一个 >= d 的观测所在行；没有则返回 None（阶段边界可能落在非交易日）"""
        for i, dd in enumerate(all_dates):
            if dd >= d:
                return first + i
        return None

    def row_at_or_before(d):
        for i in range(len(all_dates) - 1, -1, -1):
            if all_dates[i] <= d:
                return first + i
        return None

    seg_rows = []
    for j, p in enumerate(A['phases']):
        srow = date_idx.get(p['start']) or row_at_or_after(p['start'])
        erow = date_idx.get(p['end']) or row_at_or_before(p['end'])
        if srow is None or erow is None:
            continue
        reg = 5 + j
        raw.cell(row=reg, column=14, value=srow)
        raw.cell(row=reg, column=15, value=erow)
        r = 5 + len(seg_rows)
        # 起止价格：单单元格 INDEX 用「字面行号」定位（字面量比单元格引用更稳定）
        px_s = f"INDEX({DP}$B${first}:$B${last},{srow - first + 1})"
        px_e = f"INDEX({DP}$B${first}:$B${last},{erow - first + 1})"
        pta_s = f"INDEX({DP}$C${first}:$C${last},{srow - first + 1})"
        pta_e = f"INDEX({DP}$C${first}:$C${last},{erow - first + 1})"
        nrow = f"{DP}$O${reg}-{DP}$N${reg}+1"

        def seg_rng(col):
            return f"OFFSET({DP}${col}${first},{DP}$N${reg}-{first},0,{nrow},1)"
        px_seg, pta_seg, sp_seg = seg_rng('B'), seg_rng('C'), seg_rng('E')
        seg_rows.append([
            p['code'], p['name'], p['start'], p['end'],
            f"={nrow}",
            f"={px_e}/{px_s}-1",
            f"={pta_e}/{pta_s}-1",
            f"=AVERAGE({sp_seg})",
            f"=CORREL({px_seg},{pta_seg})",
        ])
    write_rows(ws, 5, seg_rows, numfmt={5: '0', 6: '0.00%', 7: '0.00%', 8: '#,##0.00', 9: '0.000'})

    r2 = 5 + len(seg_rows) + 2
    ws.cell(row=r2, column=1, value='背离区间（|20 观测 ΔPX| ≥ 3% 且 PTA 方向相反）').font = Font(size=12, bold=True, name='微软雅黑')
    hdr(ws, r2 + 1, ['起点', '终点', '天数', 'PX 涨跌', 'PTA 涨跌', '价差变化'], [8, 14, 14, 8, 12, 12])
    drows = [[d['start'], d['end'], d['n_days'], d['px_chg'] / 100, d['pta_chg'] / 100, d['spread_chg']]
             for d in A['divergence']['runs']]
    if drows:
        write_rows(ws, r2 + 2, drows, numfmt={4: '0.00%', 5: '0.00%', 6: '#,##0.00'})
    else:
        c = ws.cell(row=r2 + 2, column=1,
                    value='当前样本内未识别出持续背离区间（方向基本一致，价差波动主要来自幅度差异而非方向冲突）')
        c.font = Font(size=10.5, name='微软雅黑', italic=True, color='FF6B7280')
        ws.merge_cells(start_row=r2 + 2, start_column=1, end_row=r2 + 2, end_column=6)
    note = ws.cell(row=r2 + 4, column=1,
                   value='注：区段相关用 INDEX 取区间（而非 AVERAGEIFS 比较日期文本），'
                         '起止日期改到区间外时会自动跟随；若某阶段边界在数据中不存在，该行会被跳过。')
    note.font = Font(size=10, name='微软雅黑', color='FF6B7280')
    ws.merge_cells(start_row=r2 + 4, start_column=1, end_row=r2 + 4, end_column=9)

    # ---------- 12_公式说明 ----------
    ws = wb.create_sheet('12_公式说明')
    ws.sheet_view.showGridLines = False
    title(ws, '公式说明与使用陷阱', '照抄公式前先看这一页：每个函数的口径差异都会改变结论。', 5)
    hdr(ws, 4, ['用途', '公式', '口径说明', '陷阱'], [20, 34, 52, 52])
    formulas = [
        ('加工价差', '=PTA − Lambda*PX − OtherCost', '收入型加工费，不含折旧、能源、物流',
         'λ 必须来自台账；不同代际 0.647~0.657，差 0.008 ≈ 价差平移 60~80 元/吨'),
        ('Pearson r', '=CORREL(x,y)', '线性相关，对异常值敏感',
         '水平序列都有趋势 → r 虚高；必须同时报收益率口径'),
        ('决定系数', '=RSQ(y,x)', 'r 的平方，解释方差比例', '不能解释为「因果解释力」'),
        ('t 统计量', '=r*SQRT((n-2)/(1-r^2))', 'H0: ρ=0', 'n 是有效样本，不是自然日数'),
        ('p 值', '=T.DIST.2T(ABS(t),df)', '双尾', '自相关序列需用 Newey-West 或有效样本量校正'),
        ('Fisher 置信区间', '=TANH(ATANH(r)±NORMSINV(1-α/2)/SQRT(n-3))', 'Fisher z 变换', 'n<10 时不可靠'),
        ('有效样本量', '=n(1-ρxρy)/(1+ρxρy)', 'Pyper & Peterman 校正', '水平序列有效 N 常只有原始 N 的 10~30%'),
        ('分位', '=PERCENTILE.INC(range,p)', '线性插值（含端点）',
         'PERCENTILE.EXC 差距可达数十元/吨，两者不可混用；报告统一用 INC'),
        ('分位rank', '=PERCENTRANK.INC(range,x)', '当前值在历史中的位置',
         '与 PERCENTILE.INC 配对；结并列时取平均位置'),
        ('滚动相关', '=CORREL(offset range)', '窗口不足 80% 不出数', '窗口越长越平滑，会掩盖拐点'),
        ('交叉相关', '=CORREL(x[0:n-lag], y[lag:n])', '正 lag = x 领先 y', '只看 Pearson，无法排除共同趋势'),
        ('Granger F', '受限/非受限 RSS 比较', '检验是否含增量预测信息', 'Granger 不是因果，只说明时序上「先动」有价值'),
        ('中位数', '=MEDIAN(range)', '抗异常值', '与均值差距大说明分布偏斜，报告须同时给'),
        ('条件均值', '=AVERAGEIFS(val,date,">="&a,date,"<="&b)', '分阶段统计', '日期必须是文本可比格式或真日期'),
    ]
    write_rows(ws, 5, formulas)

    for s in wb.worksheets:
        s.sheet_properties.tabColor = '2563EB' if s.title.startswith(('0', '1')) else '64748B'
    wb.save(out_xlsx)
    print('written', out_xlsx)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'processed', 'px_pta_daily.csv'),
          sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'build', 'analysis.json'),
          sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, 'build', 'px_pta_workbook.xlsx'))
