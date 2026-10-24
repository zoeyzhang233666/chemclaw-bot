#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regions.json → 区域产业格局工作簿（13 表，顺序固定）。

用法:
  python build_xlsx.py regions.json --out out/山东-纯碱产业格局数据包.xlsx

规则（见 references/design-system.md）：
  · 每表第 1 行标题、第 2 行口径副标题、第 4 行表头，第 5 行起数据；
  · 冻结窗格 + 自动筛选 + 斑马纹 + 细边框；
  · 全部写静态值（不放公式），保证对方打开即是所见；
  · 空值写"—"或用浅灰单元格，含义在表底"说明"区统一交代。
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.formatting.rule import ColorScaleRule  # noqa: E402

C = {
    'deep': '0B3B4A', 'deep2': '12586A', 'teal': '0E7C6B', 'amber': 'B45309',
    'red': 'A1323A', 'line': 'D9DEE4', 'zebra': 'F5F8F9', 'head': 'EEF3F6',
    'grey': '6B7684', 'ok': 'E6F5F1', 'warn': 'FDF6E7',
}
THIN = Side(style='thin', color=C['line'])
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_TITLE = Font(name='Microsoft YaHei', size=15, bold=True, color=C['deep'])
F_SUB = Font(name='Microsoft YaHei', size=9.5, color=C['grey'])
F_HEAD = Font(name='Microsoft YaHei', size=10, bold=True, color='FFFFFF')
F_BODY = Font(name='Microsoft YaHei', size=10)
F_MONO = Font(name='Consolas', size=10)
F_SECTION = Font(name='Microsoft YaHei', size=11, bold=True, color=C['deep2'])


def _w(s):
    """CJK 宽度估算：汉字 2，其余 1。"""
    n = 0
    for ch in str(s):
        n += 2 if ord(ch) > 127 else 1
    return n


class Sheet:
    def __init__(self, wb, name, title, subtitle, cols, widths=None):
        self.ws = wb.create_sheet(name)
        self.cols = cols
        self.nrow = 4
        ws = self.ws
        ws.sheet_view.showGridLines = False
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(len(cols), 4))
        c = ws.cell(row=1, column=1, value=title)
        c.font = F_TITLE
        c.alignment = Alignment(vertical='center')
        ws.row_dimensions[1].height = 26
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(len(cols), 4))
        c2 = ws.cell(row=2, column=1, value=subtitle)
        c2.font = F_SUB
        c2.alignment = Alignment(vertical='center', wrap_text=True)
        ws.row_dimensions[2].height = 16 if len(subtitle) < 90 else 30
        # 表头
        for i, col in enumerate(cols, start=1):
            cell = ws.cell(row=4, column=i, value=col['t'])
            cell.font = F_HEAD
            cell.fill = PatternFill('solid', fgColor=C['deep'])
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.border = BORDER
            w = (widths[i - 1] if widths and i - 1 < len(widths) else 0) or col.get('w') or max(10, min(46, _w(col['t']) + 6))
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[4].height = 30
        ws.freeze_panes = 'A5'

    def write(self, rows):
        ws = self.ws
        for r, row in enumerate(rows):
            rw = 5 + r
            for i, col in enumerate(self.cols, start=1):
                v = row.get(col['k']) if isinstance(row, dict) else (row[i - 1] if i - 1 < len(row) else None)
                if v is None or v == '':
                    v = '—'
                cell = ws.cell(row=rw, column=i, value=v)
                cell.font = F_MONO if col.get('num') else F_BODY
                cell.border = BORDER
                if col.get('num'):
                    cell.alignment = Alignment(horizontal='right', vertical='top')
                else:
                    cell.alignment = Alignment(vertical='top', wrap_text=True)
                if r % 2 == 1:
                    cell.fill = PatternFill('solid', fgColor=C['zebra'])
            # 行高：按最长单元格估算
            mx = 1
            for i, col in enumerate(self.cols, start=1):
                val = row.get(col['k']) if isinstance(row, dict) else row[i - 1]
                if val is None:
                    continue
                w = (ws.column_dimensions[get_column_letter(i)].width or 12)
                lines = max(1, int(_w(val) / max(6, (w - 1) * 1.0)) + 1)
                mx = max(mx, min(6, lines))
            ws.row_dimensions[rw].height = 16 * mx
        self.nrow = 5 + len(rows) - 1
        if rows:
            ws.auto_filter.ref = 'A4:%s%d' % (get_column_letter(len(self.cols)), self.nrow)
        return self

    def scale(self, key, color=('FFFFFF', '0E7C6B')):
        ws = self.ws
        if self.nrow < 5:
            return self
        idx = [i for i, c in enumerate(self.cols, start=1) if c['k'] == key][0]
        rng = '%s5:%s%d' % (get_column_letter(idx), get_column_letter(idx), self.nrow)
        ws.conditional_formatting.add(rng, ColorScaleRule(start_type='min', start_color='FFFFFF',
                                                          end_type='max', end_color=color[1] if len(color) > 1 else '0E7C6B'))
        return self

    def notes(self, items, title='说明与口径'):
        ws = self.ws
        r = self.nrow + 2
        c = ws.cell(row=r, column=1, value=title)
        c.font = F_SECTION
        for i, t in enumerate(items, start=1):
            cell = ws.cell(row=r + i, column=1, value='· ' + t)
            cell.font = Font(name='Microsoft YaHei', size=9.5, color=C['grey'])
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            ws.merge_cells(start_row=r + i, start_column=1, end_row=r + i, end_column=max(4, len(self.cols)))
            ws.row_dimensions[r + i].height = max(15, 13 * (int(_w(t) / 150) + 1))
        return self


def _block(ws, row, title, pairs):
    """封面式键值区块。"""
    c = ws.cell(row=row, column=1, value=title)
    c.font = F_SECTION
    r = row + 1
    for k, v in pairs:
        ws.cell(row=r, column=1, value=k).font = Font(name='Microsoft YaHei', size=10, bold=True, color=C['deep2'])
        ws.cell(row=r, column=1).border = BORDER
        ws.cell(row=r, column=1).fill = PatternFill('solid', fgColor=C['head'])
        cell = ws.cell(row=r, column=2, value=v)
        cell.font = F_BODY
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        cell.border = BORDER
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        ws.row_dimensions[r].height = max(16, 14 * (int(_w(v) / 120) + 1))
        r += 1
    return r + 1


def build(data_path, out_path):
    D = common.load(data_path)
    M, A, N = D['meta'], D['_agg'], D.get('narrative', {})
    U = M.get('capacity_unit', '万吨/年')
    S = common.summary_numbers(D)
    src = {s['id']: s for s in D.get('sources', [])}
    for i, s in enumerate(D.get('sources', []), start=1):
        s.setdefault('n', i)

    def src_txt(ids):
        out = []
        for i in (ids or []):
            s = src.get(i)
            out.append('S%d %s' % (s['n'], s.get('publisher', '')) if s else str(i))
        return '；'.join(out)

    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.title = M.get('title', '区域产业格局')
    wb.properties.creator = 'region-industry-map skill'
    wb.properties.description = '%s · %s · 截至 %s' % (M.get('product'), M.get('region'), M.get('asof'))

    ASOF = M.get('asof', '')

    # ---------------------------------------------------------------- 00 封面
    ws = wb.create_sheet('00_封面与目录')
    ws.sheet_view.showGridLines = False
    for i, w in enumerate([22, 26, 26, 18, 18, 16, 16, 16], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.merge_cells('A1:H2')
    c = ws['A1']
    c.value = '%s · %s 产业格局数据包' % (M.get('product'), M.get('region'))
    c.font = Font(name='Microsoft YaHei', size=20, bold=True, color='FFFFFF')
    c.fill = PatternFill('solid', fgColor=C['deep'])
    c.alignment = Alignment(vertical='center', horizontal='left', indent=1)
    ws.merge_cells('A3:H3')
    ws['A3'].value = M.get('subtitle', '')
    ws['A3'].font = Font(name='Microsoft YaHei', size=10, color=C['grey'])
    ws['A3'].alignment = Alignment(wrap_text=True, vertical='center', indent=1)
    ws.row_dimensions[3].height = 34
    r = _block(ws, 5, '研究口径', [
        ('品种', M.get('product', '')),
        ('区域', M.get('region', '')),
        ('数据截至', ASOF),
        ('产能单位', U),
        ('产能口径', M.get('capacity_basis', '名义/设计产能')),
        ('统计口径', M.get('scope_note', '已核实厂区 + 地区级记录')),
        ('点位规则', '仅"已公开精确坐标"的站点作为装置点位；注册地址一律不作点位'),
        ('配套 HTML', M.get('html_name', '同名 .html 文件（交互地图，可离线打开）')),
    ])
    r = _block(ws, r, '本工作簿的关键数字（均可回溯到 13_来源清单）', [
        ('已核实生产厂区', '%d 个' % S['plants_total']),
        ('样本产能合计', '%.2f %s' % (S['capacity_sample_total'], U)),
        ('注册相关企业（估算）', '%d 家' % S['registered_total']),
        ('化工园区 / 集聚区', '%d 个' % S['park_total']),
        ('在建 / 拟建项目', '%d 个，净增量 %.2f %s' % (S['projects'], S['net_capacity'], U)),
        ('CR3 / CR5 / HHI（样本）', '%s%% / %s%% / %s' % (S['cr3'], S['cr5'], S['hhi'])),
    ])
    c = ws.cell(row=r, column=1, value='工作表目录')
    c.font = F_SECTION
    toc = [
        ('01_核心结论', '带口径的结论与建议阅读顺序'),
        ('02_生产企业总表', '厂商 → 企业 → 厂区，含注册地址/生产地址/点位精度'),
        ('03_区域汇总', '城市 / 省份：企业数、样本产能、公开口径、覆盖度、缺口'),
        ('04_工厂点位核验', '坐标、精度、坐标来源、是否可作装置位置'),
        ('05_化工园区', '园区、主导产业、落位企业、产业配套'),
        ('06_产能与工艺', '厂区产能、工艺路线、原料、口径原文'),
        ('07_上下游关联', '上游原料、下游消费、物流节点、定性流向'),
        ('08_新增在建项目', '毛新增 / 退出 / 净增量 / 状态时点'),
        ('09_价格与供需', '价格观察（带日期与口径）与区域供需特征'),
        ('10_集中度与价差因素', 'CR/HHI 与可关联的客观因素'),
        ('11_数据缺口清单', '缺什么、影响什么、怎么补'),
        ('12_口径与核验记录', '门禁规则、命名与聚合规则、核验人/日期'),
        ('13_来源清单', '编号、发布方、标题、URL、日期、等级'),
    ]
    for i, (k, v) in enumerate(toc, start=1):
        rr = r + i
        ws.cell(row=rr, column=1, value=k).font = Font(name='Microsoft YaHei', size=10, bold=True, color=C['deep2'])
        ws.cell(row=rr, column=1).border = BORDER
        cell = ws.cell(row=rr, column=2, value=v)
        cell.font = F_BODY
        cell.border = BORDER
        ws.merge_cells(start_row=rr, start_column=2, end_row=rr, end_column=6)
    ws.cell(row=r + len(toc) + 2, column=1,
            value='本工作簿为产业研究底稿：所有数字均须能回到 13_来源清单中的某一条；“—”表示未取得公开数据，'
                  '不以估算替代。').font = Font(name='Microsoft YaHei', size=9.5, color=C['amber'])

    # ---------------------------------------------------------------- 01 结论
    sh = Sheet(wb, '01_核心结论', '核心结论（每条带口径与来源）',
               '%s · %s · 截至 %s　口径：样本产能 = 已核实厂区之和；注册企业数 ≠ 生产企业数' % (M.get('product'), M.get('region'), ASOF),
               [{'k': 'no', 't': '序号', 'w': 6}, {'k': 'text', 't': '结论', 'w': 78},
                {'k': 'method', 't': '口径 / 依据', 'w': 34}, {'k': 'src', 't': '来源', 'w': 26}])
    rows = []
    for i, c in enumerate(D.get('conclusions', []), start=1):
        if isinstance(c, str):
            rows.append({'no': i, 'text': c, 'method': '', 'src': ''})
        else:
            rows.append({'no': i, 'text': c.get('text', ''), 'method': c.get('method', ''), 'src': src_txt(c.get('sources'))})
    sh.write(rows).notes([
        '结论只描述"已核实的事实"与"由事实直接得出的结构判断"，不写预测；下一步看什么指标写在 09/08 表。',
        '凡涉及"产能合计"的结论，均标明是样本口径还是公开口径；两者不一致时并列展示，不取平均。',
        '建议阅读顺序：01 → 03（区域覆盖）→ 02（工厂与地址）→ 06（工艺）→ 08（项目）→ 11（缺口）。',
    ])

    # ---------------------------------------------------------------- 02 生产企业总表
    sites = D.get('sites', [])
    sh = Sheet(wb, '02_生产企业总表', '生产企业 / 贸易 / 下游据点总表（一行 = 一个厂区或据点）',
               '注册地址与实际生产地址分列；点位精度为"精确"才可作装置位置。产能为空表示未公开，不以估算替代。单位：%s' % U,
               [{'k': 'sid', 't': '站点ID', 'w': 12}, {'k': 'company', 't': '企业 / 集团', 'w': 30},
                {'k': 'site', 't': '厂区 / 基地', 'w': 24}, {'k': 'role', 't': '角色', 'w': 8},
                {'k': 'type', 't': '站点类型', 'w': 13}, {'k': 'prov', 't': '省', 'w': 8},
                {'k': 'city', 't': '市', 'w': 10}, {'k': 'district', 't': '县/区', 'w': 10},
                {'k': 'park', 't': '园区', 'w': 24}, {'k': 'route', 't': '工艺', 'w': 8},
                {'k': 'cap', 't': '公开产能(%s)' % U, 'w': 13, 'num': True},
                {'k': 'raw', 't': '产能原文', 'w': 26}, {'k': 'basis', 't': '产能口径', 'w': 18},
                {'k': 'status', 't': '状态', 'w': 8}, {'k': 'products', 't': '产品', 'w': 18},
                {'k': 'reg', 't': '注册地址', 'w': 32}, {'k': 'regt', 't': '注册地址类型', 'w': 12},
                {'k': 'plant', 't': '实际生产地址', 'w': 32}, {'k': 'plantt', 't': '生产地址类型', 'w': 12},
                {'k': 'prec', 't': '点位精度', 'w': 9}, {'k': 'csrc', 't': '坐标来源', 'w': 12},
                {'k': 'grade', 't': '证据等级', 'w': 8}, {'k': 'src', 't': '来源', 'w': 30},
                {'k': 'note', 't': '备注', 'w': 40}])
    ROLES = {'production': '生产', 'trader': '贸易/仓储', 'downstream': '下游用户'}
    sh.write([{
        'sid': s.get('site_id') or s.get('site_name'), 'company': s.get('company'),
        'site': s.get('site_name'), 'role': ROLES.get(s.get('role'), s.get('role')),
        'type': s.get('site_type', ''), 'prov': s.get('province'), 'city': s.get('city'),
        'district': s.get('district'), 'park': s.get('park') or '未核实',
        'route': s.get('route') or '未知', 'cap': s.get('capacity'),
        'raw': s.get('raw_capacity') or '未取得', 'basis': s.get('capacity_basis') or '未注明',
        'status': s.get('status'), 'products': ' / '.join(s.get('products') or []),
        'reg': s.get('reg_address') or '未核实', 'regt': s.get('reg_address_type') or '—',
        'plant': s.get('plant_address') or '未核实', 'plantt': s.get('address_type') or '—',
        'prec': s.get('precision'), 'csrc': s.get('coord_source') or '—',
        'grade': s.get('evidence_grade'), 'src': src_txt(s.get('source_ids')),
        'note': s.get('note') or '',
    } for s in sorted(sites, key=lambda x: (x.get('province') or '', x.get('city') or '', -(x.get('capacity') or 0)))]
    ).scale('cap').notes([
        '一行 = 一个厂区。同一企业的多个厂区分行列示；不要把集团总部当作一个厂区。',
        '注册地址只说明法人登记地，不能作为装置位置；"生产地址类型"为"园区地址/镇村地名"时，只能做园区级或县级落点。',
        '点位列：精确 = 可作装置位置；园区级 / 县级 / 市级 = 仅示意，不代表装置位置。',
        '贸易/仓储与下游用户不进入产能合计。',
    ])

    # ---------------------------------------------------------------- 03 区域汇总
    sh = Sheet(wb, '03_区域汇总', '区域汇总：城市与省份（企业数量 + 公开产能 + 覆盖度）',
               '“样本产能”= 表 02 中已核实生产厂区之和；“公开口径”= 城市/省级公开合计；“覆盖度”= 样本/公开；差额 = 尚未落到厂区的部分。',
               [{'k': 'level', 't': '层级', 'w': 8}, {'k': 'prov', 't': '省份', 'w': 10}, {'k': 'city', 't': '城市', 'w': 12},
                {'k': 'reg', 't': '注册企业(估算,家)', 'w': 15, 'num': True}, {'k': 'plants', 't': '已定位生产厂区(个)', 'w': 16, 'num': True},
                {'k': 'sample', 't': '样本产能(%s)' % U, 'w': 15, 'num': True}, {'k': 'decl', 't': '公开口径(%s)' % U, 'w': 14, 'num': True},
                {'k': 'cov', 't': '覆盖度(%)', 'w': 11, 'num': True}, {'k': 'gap', 't': '待落位差额', 'w': 12, 'num': True},
                {'k': 'trader', 't': '贸易据点(个)', 'w': 12, 'num': True}, {'k': 'down', 't': '下游据点(个)', 'w': 12, 'num': True},
                {'k': 'parks', 't': '园区(个)', 'w': 9, 'num': True}, {'k': 'net', 't': '在建净增(%s)' % U, 'w': 13, 'num': True},
                {'k': 'grade', 't': '数据等级', 'w': 9}, {'k': 'note', 't': '备注', 'w': 44}])
    rows = []
    for c in sorted(A['by_city'].values(), key=lambda x: -(x.get('capacity_sample') or 0)):
        rows.append({'level': '城市', 'prov': c['province'], 'city': c['city'], 'reg': c.get('registered'),
                     'plants': c.get('plants'), 'sample': c.get('capacity_sample'),
                     'decl': c.get('capacity_declared') if c.get('capacity_declared') is not None else c.get('capacity_covered'),
                     'cov': c.get('coverage'), 'gap': c.get('gap'), 'trader': c.get('trader_sites'),
                     'down': c.get('downstream_sites'), 'parks': len(c.get('parks') or []),
                     'net': c.get('net_capacity'), 'grade': c.get('data_grade') or '—', 'note': c.get('note') or ''})
    rows.append({'level': '—', 'prov': '—', 'city': '【城市合计】', 'reg': A['registered_total'],
                 'plants': A['plants_total'], 'sample': A['capacity_sample_total'],
                 'decl': sum((c.get('capacity_declared') or c.get('capacity_covered') or 0) for c in A['by_city'].values()),
                 'cov': A.get('coverage_total'), 'gap': None, 'trader': A['trader_sites_total'],
                 'down': A['downstream_sites_total'], 'parks': A['park_total'],
                 'net': A.get('net_capacity'), 'grade': '—', 'note': '城市合计含未列城市'})
    for p in sorted(A['by_prov'].values(), key=lambda x: -(x.get('capacity_sample') or 0)):
        rows.append({'level': '省份', 'prov': p['province'], 'city': '（%d 个城市）' % p['cities'],
                     'reg': p.get('registered'), 'plants': p.get('plants'), 'sample': p.get('capacity_sample'),
                     'decl': p.get('capacity_declared') or p.get('capacity_covered') or None,
                     'cov': p.get('coverage'), 'gap': None, 'trader': p.get('trader_sites'),
                     'down': p.get('downstream_sites'), 'parks': p.get('n_parks'),
                     'net': p.get('net_capacity'), 'grade': '—', 'note': p.get('cities_named', '')})
    sh.write(rows).scale('sample').notes([
        '注册企业数来自工商/名录类数据库的检索计数，是“与品种相关的注册主体”估算，含贸易、投资、已注销等，不能当作生产企业数。',
        '样本产能只统计“生产”角色且有公开产能数值的厂区；同一集团多厂区分别计入，但须与集团公开口径交叉核对（见 06 表）。',
        '覆盖度 < 100% 说明还有产能未落到厂区：该部分在 11_数据缺口 中列明，不做分摊。',
        '覆盖度为“—”表示公开口径未取得，只能给样本产能，不能给份额。',
    ])

    # ---------------------------------------------------------------- 04 点位核验
    sh = Sheet(wb, '04_工厂点位核验', '工厂点位核验：坐标、精度、来源与可用性',
               '只有“精度=精确 且 坐标可用=是”的点位，才允许在 HTML 地图上作为装置位置展示；其余只能作地区级记录。',
               [{'k': 'sid', 't': '站点ID', 'w': 12}, {'k': 'company', 't': '企业', 'w': 30}, {'k': 'site', 't': '厂区', 'w': 24},
                {'k': 'prov', 't': '省', 'w': 8}, {'k': 'city', 't': '市', 'w': 10}, {'k': 'lon', 't': '经度', 'w': 11, 'num': True},
                {'k': 'lat', 't': '纬度', 'w': 11, 'num': True}, {'k': 'prec', 't': '精度', 'w': 9},
                {'k': 'csrc', 't': '坐标来源', 'w': 14}, {'k': 'usable', 't': '可作装置位置', 'w': 12},
                {'k': 'addr', 't': '定位依据地址', 'w': 40}, {'k': 'note', 't': '核验备注 / 待办', 'w': 44}])
    sh.write([{
        'sid': s.get('site_id') or s.get('site_name'), 'company': s.get('company'), 'site': s.get('site_name'),
        'prov': s.get('province'), 'city': s.get('city'), 'lon': s.get('lon'), 'lat': s.get('lat'),
        'prec': s.get('precision'), 'csrc': s.get('coord_source'),
        'usable': '是' if s.get('coordinate_usable') else '否',
        'addr': s.get('plant_address') or s.get('reg_address') or '未核实',
        'note': ('待办：' + '；'.join(s.get('verify'))) if s.get('verify') else (s.get('note') or ''),
    } for s in sites]).notes([
        '精度分级：精确（厂区/园区内具体点位，来源可点击）；园区级（园区管委会公开位置）；县级（县级地名）；市级（城市中心）。',
        '坐标来源必须写明：企业官网 / 政府公示 / 园区公开资料 / 新闻报道 / 地图地名库 / 人工核对 / 未核实。',
        '禁止：用集团总部地址、写字楼地址、城市中心坐标冒充装置位置；同一坐标被 3 个以上站点共用时须说明原因。',
        '校验脚本 validate.py 会对“精确点位 + 总部类地址字样”“坐标越界”“同名重复站点”报警。',
    ])

    # ---------------------------------------------------------------- 05 园区
    sh = Sheet(wb, '05_化工园区', '化工园区与产业配套',
               '园区是企业的容器，不是企业本身：园区内企业数只统计表 02 中已核实落位的厂区；没有名单就写“未核实”。',
               [{'k': 'id', 't': '园区ID', 'w': 12}, {'k': 'name', 't': '园区名称', 'w': 34}, {'k': 'level', 't': '级别', 'w': 10},
                {'k': 'prov', 't': '省', 'w': 8}, {'k': 'city', 't': '市', 'w': 10}, {'k': 'dist', 't': '县/区', 'w': 10},
                {'k': 'lon', 't': '经度', 'w': 10, 'num': True}, {'k': 'lat', 't': '纬度', 'w': 10, 'num': True},
                {'k': 'cb', 't': '坐标依据', 'w': 24}, {'k': 'inds', 't': '主导产业', 'w': 26},
                {'k': 'rel', 't': '与本品种的关系', 'w': 34}, {'k': 'nsite', 't': '已核实落位厂区(个)', 'w': 14, 'num': True},
                {'k': 'cos', 't': '落位企业', 'w': 30}, {'k': 'sup', 't': '可查到的产业配套', 'w': 40},
                {'k': 'grade', 't': '证据等级', 'w': 9}, {'k': 'src', 't': '来源', 'w': 26}])
    sh.write([{
        'id': p.get('id'), 'name': p.get('name'), 'level': p.get('level'), 'prov': p.get('province'),
        'city': p.get('city'), 'dist': p.get('district'), 'lon': p.get('lon'), 'lat': p.get('lat'),
        'cb': p.get('coord_basis') or '未核实', 'inds': ' / '.join(p.get('main_industries') or []),
        'rel': p.get('soda_relevance') or '未核实',
        'nsite': sum(1 for s in sites if s.get('park_id') == p.get('id')),
        'cos': '、'.join(dict.fromkeys(s.get('company', '') for s in sites
                                      if s.get('park_id') == p.get('id') and s.get('company'))) or '未核实',
        'sup': '；'.join(p.get('supporting') or []) or '未核实',
        'grade': p.get('evidence_grade'), 'src': src_txt(p.get('source_ids')),
    } for p in D.get('parks', [])]).scale('nsite').notes([
        '园区名单以政府公示的化工园区名录（省级认定名单）为准；未列入名录的“化工集聚区”单独标注级别为市级/集聚区。',
        '“已核实落位厂区”只数表 02 中明确写了 park_id 的站点，不从园区宣传页倒推。',
    ])

    # ---------------------------------------------------------------- 06 产能与工艺
    prod = [s for s in sites if s.get('role') == 'production']
    sh = Sheet(wb, '06_产能与工艺', '厂区产能与工艺路线',
               '产能一律抄原文并注明口径（设计/名义/实际）；工艺路线只能从公开资料确认，未确认写“未知”，不从产品结构反推。',
               [{'k': 'company', 't': '企业', 'w': 28}, {'k': 'site', 't': '厂区', 'w': 22}, {'k': 'city', 't': '城市', 'w': 12},
                {'k': 'route', 't': '工艺', 'w': 9}, {'k': 'cap', 't': '产能(%s)' % U, 'w': 12, 'num': True},
                {'k': 'raw', 't': '原文', 'w': 24}, {'k': 'basis', 't': '口径', 'w': 16}, {'k': 'status', 't': '状态', 'w': 8},
                {'k': 'up', 't': '主要原料（已核实）', 'w': 28}, {'k': 'down', 't': '主要去向（已核实）', 'w': 28},
                {'k': 'grade', 't': '证据', 'w': 7}, {'k': 'src', 't': '来源', 'w': 26}])
    sh.write([{
        'company': s.get('company'), 'site': s.get('site_name'), 'city': s.get('city'),
        'route': s.get('route') or '未知', 'cap': s.get('capacity'), 'raw': s.get('raw_capacity') or '未取得',
        'basis': s.get('capacity_basis') or '未注明', 'status': s.get('status'),
        'up': ' / '.join(s.get('upstream') or []) or '未核实', 'down': ' / '.join(s.get('downstream') or []) or '未核实',
        'grade': s.get('evidence_grade'), 'src': src_txt(s.get('source_ids')),
    } for s in sorted(prod, key=lambda x: -(x.get('capacity') or 0))]).scale('cap').notes([
        '合计行请用 03_区域汇总 的“样本产能”，本表按厂区排序便于核对，不另设合计行以免与 03 表口径打架。',
        '工艺路线说明与原料单耗差异见 12_口径与核验记录；原料单耗若无公开来源，不在本表推算。',
    ])

    # ---------------------------------------------------------------- 07 上下游
    sh = Sheet(wb, '07_上下游关联', '上下游关联与物流节点',
               '上游 = 有公开证据的原料产地/供应商；下游 = 真正消耗本品的产业/企业；物流 = 港口、专用线、交割库、交易市场。数量缺失写“未取得”。',
               [{'k': 'kind', 't': '类型', 'w': 10}, {'k': 'name', 't': '名称', 'w': 30}, {'k': 'material', 't': '物料/环节', 'w': 16},
                {'k': 'prov', 't': '省', 'w': 8}, {'k': 'city', 't': '市', 'w': 10}, {'k': 'quant', 't': '公开数量/规模', 'w': 22},
                {'k': 'use', 't': '与本品的关系', 'w': 36}, {'k': 'node', 't': '节点类型', 'w': 12},
                {'k': 'grade', 't': '证据等级', 'w': 9}, {'k': 'src', 't': '来源', 'w': 26}])
    rows = []
    for u in D.get('upstream', []):
        rows.append({'kind': '上游原料', 'name': u.get('name', ''), 'material': u.get('material', ''),
                     'prov': u.get('province', ''), 'city': u.get('city', ''), 'quant': u.get('quant') or '未取得',
                     'use': u.get('note') or u.get('spec') or '', 'node': '', 'grade': u.get('evidence_grade'),
                     'src': src_txt(u.get('source_ids'))})
    for d in D.get('downstream', []):
        rows.append({'kind': '下游消费', 'name': d.get('company') or d.get('segment', ''), 'material': d.get('segment', ''),
                     'prov': d.get('province', ''), 'city': d.get('city', ''), 'quant': d.get('scale') or '未取得',
                     'use': d.get('note') or d.get('use') or '', 'node': '', 'grade': d.get('evidence_grade'),
                     'src': src_txt(d.get('source_ids'))})
    NODE_ROLE = {'port': '港口', 'rail': '铁路专用线', 'depot': '交割/仓储', 'market': '交易市场',
                 'road': '陆路通道', 'logistics_park': '物流园'}
    for n in D.get('nodes', []):
        rows.append({'kind': '物流节点', 'name': n.get('name', ''), 'material': n.get('role', ''),
                     'prov': n.get('province', ''), 'city': n.get('city', ''), 'quant': n.get('cap_note') or '未取得',
                     'use': n.get('evidence') or '', 'node': NODE_ROLE.get(n.get('role'), n.get('role')),
                     'grade': n.get('evidence_grade'), 'src': src_txt(n.get('source_ids'))})
    for f in D.get('flows', []):
        rows.append({'kind': '已证实流向', 'name': '%s → %s' % (f.get('from_site'), f.get('to_node') or f.get('to_site')),
                     'material': f.get('material', ''), 'prov': '', 'city': '',
                     'quant': f.get('volume') or '未取得', 'use': f.get('note') or '',
                     'node': '', 'grade': f.get('evidence_grade'), 'src': src_txt(f.get('source_ids'))})
    sh.write(rows).notes([
        '流向只在有公开来源（企业公告、环评运输量、园区介绍）时登记；“某厂可能买某矿”这类推断不写入。',
        '物流节点的吞吐量/库容若无公开数据写“未取得”，不按里程或产量推算。',
    ])

    # ---------------------------------------------------------------- 08 项目
    sh = Sheet(wb, '08_新增在建项目', '新增 / 在建 / 拟建项目（毛新增 vs 净增量）',
               '净增量 = 新增 − 退出；退出待确认的项目净增量留“待确认”且不计入合计。状态必须锁时点（status_asof）。',
               [{'k': 'id', 't': '项目ID', 'w': 10}, {'k': 'name', 't': '项目名称', 'w': 34}, {'k': 'co', 't': '企业', 'w': 24},
                {'k': 'prov', 't': '省', 'w': 8}, {'k': 'city', 't': '市', 'w': 10}, {'k': 'dist', 't': '县/区', 'w': 10},
                {'k': 'park', 't': '园区', 'w': 20}, {'k': 'type', 't': '类型', 'w': 10},
                {'k': 'cap', 't': '新增(%s)' % U, 'w': 11, 'num': True}, {'k': 'ret', 't': '退出(%s)' % U, 'w': 11, 'num': True},
                {'k': 'net', 't': '净增量(%s)' % U, 'w': 12, 'num': True}, {'k': 'status', 't': '状态', 'w': 10},
                {'k': 'asof', 't': '状态时点', 'w': 12}, {'k': 'online', 't': '预计投产', 'w': 12},
                {'k': 'prod', 't': '产品', 'w': 14}, {'k': 'impact', 't': '对区域供需的影响', 'w': 40},
                {'k': 'grade', 't': '证据', 'w': 7}, {'k': 'src', 't': '来源', 'w': 26}, {'k': 'todo', 't': '待核实', 'w': 30}])
    projs = D.get('projects', [])
    sh.write([{
        'id': p.get('id'), 'name': p.get('name'), 'co': p.get('company_id'), 'prov': p.get('province'),
        'city': p.get('city'), 'dist': p.get('district'), 'park': p.get('park'), 'type': p.get('type'),
        'cap': p.get('capacity'), 'ret': p.get('capacity_retired'), 'net': p.get('net') if p.get('net') is not None else '待确认',
        'status': p.get('status'), 'asof': p.get('status_asof'), 'online': p.get('online') or '未取得',
        'prod': ' / '.join(p.get('products') or []), 'impact': p.get('impact') or '',
        'grade': p.get('evidence_grade'), 'src': src_txt(p.get('source_ids')),
        'todo': '；'.join(p.get('verify') or []) or '—',
    } for p in projs]).notes([
        '毛新增 %.2f %s − 退出 %.2f %s = 净增量 %.2f %s（不含“待确认”项目）。' % (
            sum((p.get('capacity') or 0) for p in projs), U,
            sum((p.get('capacity_retired') or 0) for p in projs), U,
            sum((p.get('net') or 0) for p in projs if p.get('net') is not None), U),
        '置换/搬迁项目必须同时填“新增”与“退出”，否则会系统性高估新增产能。',
        '状态类型：已投产 / 在建 / 拟建 / 已备案 / 环评公示 / 退出。项目状态会变，交付时须写清时点。',
    ])

    # ---------------------------------------------------------------- 09 价格
    P = D.get('prices', {})
    sh = Sheet(wb, '09_价格与供需', '价格观察与区域供需特征',
               '价格必须有：日期、规格（重碱/轻碱等）、区域、口径（出厂含税/送到价/承兑）、来源。缺少任一项的观察不写入。',
               [{'k': 'asof', 't': '日期', 'w': 12}, {'k': 'spec', 't': '规格', 'w': 12}, {'k': 'region', 't': '区域', 'w': 14},
                {'k': 'value', 't': '价格', 'w': 10, 'num': True}, {'k': 'unit', 't': '单位', 'w': 10},
                {'k': 'basis', 't': '口径', 'w': 18}, {'k': 'note', 't': '原文/说明', 'w': 40}, {'k': 'src', 't': '来源', 'w': 26}])
    obs = P.get('observations', [])
    rows = [{'asof': o.get('asof'), 'spec': o.get('spec'), 'region': o.get('region'), 'value': o.get('value'),
             'unit': o.get('unit') or '元/吨', 'basis': o.get('basis'), 'note': o.get('note'),
             'src': src_txt(o.get('sources'))} for o in obs]
    if not rows:
        rows = [{'asof': '未取得', 'spec': '—', 'region': '—', 'value': None, 'unit': '—', 'basis': '—',
                 'note': '本次未取得可核实的价格序列（缺口，见 11 表）', 'src': '—'}]
    sh.write(rows).scale('value').notes([
        '价格是“观察值”，不是报价依据；同一日期不同口径的价格并列展示，不取平均。',
        '区域价差只做“客观因素”解释（运费、货源结构、合同形式），不做套利空间测算，除非有物流报价来源。',
    ] + ['区域供需特征｜%s：%s' % (f.get('region'), f.get('feature')) for f in P.get('regional_features', [])])

    # ---------------------------------------------------------------- 10 集中度
    sh = Sheet(wb, '10_集中度与价差', '集中度（样本口径）与区域价差客观因素',
               'CR3 / CR5 / HHI 基于表 06 的样本产能；样本覆盖率不足时不做“真实集中度”推断，只标注方向不确定。',
               [{'k': 'k', 't': '指标', 'w': 22}, {'k': 'v', 't': '数值', 'w': 16}, {'k': 'basis', 't': '口径', 'w': 46}])
    rows = [
        {'k': '样本产能合计', 'v': '%.2f %s' % (A['capacity_sample_total'], U), 'basis': '表 06 中“生产”角色且有公开数值的厂区之和'},
        {'k': 'CR1', 'v': A.get('cr1'), 'basis': '最大单一厂区占样本产能比例'},
        {'k': 'CR3', 'v': A.get('cr3'), 'basis': '前三大厂区合计占样本产能比例'},
        {'k': 'CR5', 'v': A.get('cr5'), 'basis': '前五大厂区合计占样本产能比例'},
        {'k': 'HHI', 'v': A.get('hhi'), 'basis': '平方和指数（0–10000），厂区口径'},
        {'k': '样本覆盖率', 'v': A.get('coverage_total'), 'basis': '样本产能 / 区域公开口径合计（%）'},
    ]
    for i, t in enumerate(A.get('top_share') or [], start=1):
        rows.append({'k': 'Top%d' % i, 'v': '%s %s %s%%' % (t.get('company'), t.get('capacity'), t.get('share')),
                     'basis': '厂区：%s' % (t.get('name') or '')})
    for f in N.get('price_diff_factors', []) or []:
        if isinstance(f, str):
            rows.append({'k': '价差因素', 'v': '—', 'basis': f})
        else:
            rows.append({'k': '价差因素', 'v': '—', 'basis': f.get('text', '')})
    sh.write(rows).notes([
        '集中度只能说明“已核实产能的集中程度”，不能直接推导价格走势或定价权。',
        '区域价差的客观因素包括：到厂运距与运费、货源结构（本地自产/区外调入）、下游集中度、合同形式（长约/散单）、交割库与库容、品质与包装差异。',
        N.get('concentration_note', '') or '',
    ])

    # ---------------------------------------------------------------- 11 缺口
    sh = Sheet(wb, '11_数据缺口', '数据缺口清单：缺什么、影响什么、怎么补',
               '缺口不是免责声明，是下一轮调研的作业单。缺失的地区/企业/产能明确标记，不以假设填补。',
               [{'k': 'no', 't': '序号', 'w': 6}, {'k': 'item', 't': '缺口事项', 'w': 40}, {'k': 'scope', 't': '涉及区域/对象', 'w': 24},
                {'k': 'why', 't': '为什么缺', 'w': 40}, {'k': 'impact', 't': '对结论的影响', 'w': 34},
                {'k': 'how', 't': '补齐方式', 'w': 40}, {'k': 'pri', 't': '优先级', 'w': 8}])
    gaps = N.get('gaps') or []
    sh.write([{'no': i, 'item': g.get('item') if isinstance(g, dict) else g,
               'scope': (g.get('scope') if isinstance(g, dict) else '') or '—',
               'why': (g.get('why') if isinstance(g, dict) else '') or '—',
               'impact': (g.get('impact') if isinstance(g, dict) else '') or '—',
               'how': (g.get('how') if isinstance(g, dict) else '') or '—',
               'pri': (g.get('priority') if isinstance(g, dict) else '') or 'P1'} for i, g in enumerate(gaps, start=1)]
           ).notes([
        '优先级：P0 = 影响供需判断或点位正确性，交付前必须确认；P1 = 影响份额与区划判断；P2 = 影响细节描述。',
        '涉及“某城市无数据”的，在 03 表中该城市行写“—”，并在本表登记原因。',
    ])

    # ---------------------------------------------------------------- 12 口径
    sh = Sheet(wb, '12_口径与核验', '口径、核验记录与聚合规则',
               '这一页写给下一个人：数字怎么来的、怎么算的、谁核的、哪一天核的。',
               [{'k': 'k', 't': '条目', 'w': 20}, {'k': 'v', 't': '内容', 'w': 110}])
    rows = [{'k': '编制说明', 'v': M.get('subtitle', '')},
            {'k': '数据截至', 'v': ASOF},
            {'k': '产能口径', 'v': M.get('capacity_basis', '')},
            {'k': '覆盖口径', 'v': N.get('coverage_note', '')},
            {'k': '地址规则', 'v': N.get('address_rule', '注册地址与生产地址分列；注册地址不作装置位置。')}]
    for m in N.get('method', []) or []:
        rows.append({'k': m.get('k'), 'v': m.get('v')})
    for u in N.get('usage', []) or []:
        rows.append({'k': '使用边界', 'v': u if isinstance(u, str) else u.get('text', '')})
    sh.write(rows).notes([
        '构建命令：python scripts/build_all.py regions.json --out out --name <品种-区域>',
        '校验命令：python scripts/validate.py regions.json --strict（error 阻断交付）',
        '体检命令：python scripts/qa.py "<产物.html>" "<产物.xlsx>"（真浏览器渲染 + 表格核对）',
    ])

    # ---------------------------------------------------------------- 13 来源
    sh = Sheet(wb, '13_来源清单', '来源清单',
               '等级：A 政府公示/交易所公告/企业年报；B 行业协会/主流媒体/上市公司信息平台；C 企业官网/行业资讯/地方媒体；D 未核实（仅线索）。',
               [{'k': 'n', 't': '编号', 'w': 8, 'num': True}, {'k': 'pub', 't': '发布方', 'w': 26}, {'k': 'title', 't': '标题', 'w': 46},
                {'k': 'type', 't': '类型', 'w': 14}, {'k': 'date', 't': '日期', 'w': 12}, {'k': 'grade', 't': '等级', 'w': 7},
                {'k': 'url', 't': 'URL', 'w': 60}, {'k': 'note', 't': '引用内容', 'w': 40}])
    sh.write([{'n': s.get('n'), 'pub': s.get('publisher'), 'title': s.get('title'), 'type': s.get('doc_type'),
               'date': s.get('date'), 'grade': s.get('grade'), 'url': s.get('url') or '（无公开链接）',
               'note': s.get('note') or ''} for s in sorted(D.get('sources', []), key=lambda x: x.get('n', 0))]
           ).notes([
        '每条来源都标注了引用的具体内容（note 列），便于复核时只核那一句。',
        '无公开链接的来源（内部访谈、线下材料）必须写明材料名称与取得时间，等级不得为 A。',
    ])

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    wb.save(out_path)
    print('XLSX →', out_path, '(%d 表)' % len(wb.sheetnames))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data')
    ap.add_argument('--out', default='out/区域产业格局数据包.xlsx')
    a = ap.parse_args()
    build(a.data, a.out)


if __name__ == '__main__':
    main()
