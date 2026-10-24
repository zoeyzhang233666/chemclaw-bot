#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_workbook.py — 由 case_output.json 生成供应商寻源工作簿（12 个工作表）。

用法：
    python build_workbook.py <case_output.json> [输出.xlsx]

通用版：不依赖特定国家/产品，产能主值通过 cap_main() 从 capacity 字段自适应读取。
"""
import json, os, sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chart import BarChart, Reference

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(2)
SRC = sys.argv[1]
D = json.load(open(SRC, encoding='utf-8'))
BASE = os.path.dirname(os.path.abspath(SRC))
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, 'out', '海外供应商寻源工作簿.xlsx')
os.makedirs(os.path.dirname(OUT), exist_ok=True)

meta = D['meta']
S = {s['id']: s for s in D['sources']}
Q = {q['id']: q for q in D['questions']}
GNAME = {g['id']: g['name'] for g in D['groups']}
MANUF_TYPES = {'MANUFACTURER', 'JV_MANUFACTURER'}
GRADE_ORDER = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
companies = sorted(D['companies'], key=lambda c: (GRADE_ORDER.get(c['grade'], 9),
                                                  0 if c['entity_type'] in MANUF_TYPES else 1,
                                                  c.get('rank', 99)))
for i, c in enumerate(companies, 1):
    c['_rank'] = i


def cap_main(c):
    """通用产能主值：优先 capacity.expr，其次任意 *_mtpa / *_kta 键。"""
    cap = c.get('capacity') or {}
    if cap.get('expr'):
        return cap['expr']
    for k, v in cap.items():
        if k.endswith('_mtpa') or k.endswith('_kta') or k == 'main':
            return v
    return '—'


PROD_ZH = meta['product'].get('name_cn', '目标产品')
CTRY_ZH = meta.get('buyer_context', {}).get('origin', '目标国家')

# ---------- styles ----------
TEAL = '0F766E'
DARK = '0F172A'
LIGHT = 'F1F5F9'
HDR_FONT = Font(name='Microsoft YaHei', bold=True, color='FFFFFF', size=10)
HDR_FILL = PatternFill('solid', fgColor=TEAL)
SUB_FILL = PatternFill('solid', fgColor='CCFBF1')
BODY_FONT = Font(name='Microsoft YaHei', size=9.5)
BOLD = Font(name='Microsoft YaHei', size=9.5, bold=True)
TITLE_FONT = Font(name='Microsoft YaHei', size=15, bold=True, color=DARK)
NOTE_FONT = Font(name='Microsoft YaHei', size=9, italic=True, color='64748B')
THIN = Side(style='thin', color='CBD5E1')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical='top')
CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)
GRADE_FILL = {'A': PatternFill('solid', fgColor='D1FAE5'),
              'B': PatternFill('solid', fgColor='FEF3C7'),
              'C': PatternFill('solid', fgColor='E2E8F0'),
              'D': PatternFill('solid', fgColor='FEE2E2')}


def sheet_title(ws, title, subtitle, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=title)
    c.font = TITLE_FONT
    c.alignment = Alignment(vertical='center')
    ws.row_dimensions[1].height = 26
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c2 = ws.cell(row=2, column=1, value=subtitle)
    c2.font = NOTE_FONT
    c2.alignment = Alignment(vertical='center', wrap_text=True)
    ws.row_dimensions[2].height = 30


def table(ws, headers, rows, start_row=4, widths=None, grade_col=None, freeze=True):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=start_row, column=j, value=h)
        c.font = HDR_FONT
        c.fill = HDR_FILL
        c.alignment = CENTER
        c.border = BORDER
    ws.row_dimensions[start_row].height = 30
    for i, row in enumerate(rows, start_row + 1):
        for j, val in enumerate(row, 1):
            c = ws.cell(row=i, column=j, value=val)
            c.font = BODY_FONT
            c.alignment = WRAP
            c.border = BORDER
            if grade_col and j == grade_col:
                c.fill = GRADE_FILL.get(str(val), PatternFill())
                c.alignment = CENTER
                c.font = BOLD
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
    if freeze:
        ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    ws.auto_filter.ref = f"A{start_row}:{get_column_letter(len(headers))}{start_row + len(rows)}"
    return start_row + len(rows)


wb = Workbook()

# ===================== 1. 封面 =====================
ws = wb.active
ws.title = '00_封面与说明'
ws.sheet_properties.tabColor = TEAL
sheet_title(ws, '{CTRY_ZH} {PROD_ZH} 海外供应商寻源工作簿',
            '找海外候选生产商 · 制造证据分级 · 集团/生产/销售主体分离 | 报告编号 ' + meta['report_id'], 6)

rows = [
    ('报告编号', meta['report_id']),
    ('产品', f"{meta['product']['name_cn']} / {meta['product']['name_en']}"),
    ('CAS / HS', f"{meta['product']['cas']} / {meta['product']['hs_cn']}"),
    ('典型规格', meta['product']['spec_summary']),
    ('工艺路线', meta['product']['process_route']),
    ('目标国家/地区', meta['buyer_context']['origin']),
    ('目的国', meta['buyer_context']['destination']),
    ('采购批量', meta['buyer_context']['quantity']),
    ('是否仅接受实际生产厂家', meta['buyer_context']['only_actual_manufacturers']),
    ('需要的认证/包装', meta['buyer_context']['certifications_needed'] + ' / ' + meta['buyer_context']['packaging_needed']),
    ('调查日期', meta['research_date']),
    ('证据等级体系', 'A=有直接公开制造证据；B=有产品业务关联但制造身份待核验；C=仅存在行业相关性；D=贸易/代理/身份不明'),
]
r = 4
for k, v in rows:
    a = ws.cell(row=r, column=1, value=k); a.font = BOLD; a.fill = SUB_FILL; a.border = BORDER; a.alignment = WRAP
    b = ws.cell(row=r, column=2, value=v); b.font = BODY_FONT; b.border = BORDER; b.alignment = WRAP
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
    r += 1

r += 1
ws.cell(row=r, column=1, value='工作表导航').font = Font(name='Microsoft YaHei', size=11, bold=True, color=TEAL)
nav = [
    ('01_企业总表', '全部企业/主体：类型、等级、工厂、产品、产能、联系方式、待核验问题数'),
    ('02_生产商清单', 'A/B 级制造主体（生产商分栏）'),
    ('03_贸易与销售主体', '销售主体、非目标品、贸易商（贸易商分栏）'),
    ('04_制造证据台账', '逐条证据：编号、类型、置信度、原文摘要、来源 URL'),
    ('05_产能与规格对照', '公开产能口径、冲突说明、当前供货能力判断'),
    ('06_官方联系渠道', '官网、电话、邮箱与核验状态'),
    ('07_认证与质量文件', '认证名称与核验状态（未取得即标待核验）'),
    ('08_询证问题清单', '27 条待核实问题，可直接发询盘'),
    ('09_证据来源', '28 项公开来源与收录状态'),
    ('10_筛选漏斗', '从初始候选到可询盘的收敛过程'),
    ('11_新建候选_模板', '空白模板：录入新企业与证据（含下拉校验）'),
]
r += 1
for name, desc in nav:
    a = ws.cell(row=r, column=1, value=name); a.font = BOLD; a.border = BORDER
    b = ws.cell(row=r, column=2, value=desc); b.font = BODY_FONT; b.alignment = WRAP; b.border = BORDER
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
    r += 1

r += 1
ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
c = ws.cell(row=r, column=1, value='免责声明：' + meta['disclaimer'])
c.font = Font(name='Microsoft YaHei', size=9, color='9A3412')
c.fill = PatternFill('solid', fgColor='FFF7ED')
c.alignment = WRAP
ws.row_dimensions[r].height = 46
for j, w in enumerate([22, 30, 26, 26, 26], 1):
    ws.column_dimensions[get_column_letter(j)].width = w

# ===================== 2. 企业总表 =====================
ws = wb.create_sheet('01_企业总表')
sheet_title(ws, '企业总表（10 家主体）',
            '生产商与贸易商同表呈现，用『分栏』列区分；证据等级与主体类型是两条独立判断轴。', 18)

rows = []
for c in companies:
    cols = '生产商栏' if (c['entity_type'] in MANUF_TYPES and c['grade'] in ('A', 'B')) else '贸易/销售栏'
    qids = '、'.join(q for q in c.get('open_questions', []) if q in Q)
    rows.append([
        c['_rank'] if '_rank' in c else companies.index(c) + 1,
        c['legal_name'], c.get('cn_name', ''), c['entity_type_label'], cols, c['grade'],
        GNAME.get(c.get('group'), '—'), c.get('site', '—'),
        cap_main(c),
        '；'.join(p['product'] for p in c.get('products_specs', [])),
        '；'.join(e['id'] for e in c['evidence']),
        len(c['evidence']),
        (c.get('official_channels') or [{}])[0].get('value', '—'),
        c.get('export_info', '—'),
        len(c.get('open_questions', [])),
        qids,
        c['grade_reason'],
        '是' if c['grade'] == 'A' else '否',
    ])
hdr = ['序号', '企业名称（英文法定名）', '中文名', '企业类型', '分栏', '证据等级', '所属集团',
       '实际工厂所在地', '公开产能', '产品与规格（摘要）', '制造证据编号', '证据条数',
       '官方联系渠道（首项）', '出口业务信息', '待核验问题数', '待核验问题编号', '判定理由（摘要）', '是否已核验厂家']
table(ws, hdr, rows, widths=[6, 30, 18, 22, 16, 9, 22, 22, 26, 34, 18, 8, 36, 34, 9, 22, 62, 12], grade_col=6)
for i in range(5, 5 + len(rows)):
    ws.row_dimensions[i].height = 72
ws.column_dimensions['I'].width = 26

# ===================== 3. 生产商清单 =====================
ws = wb.create_sheet('02_生产商清单')
sheet_title(ws, '生产商分栏：确认或待确认拥有 MEG 装置的工厂主体',
            '本表仅收录 A/B 级制造主体。公开设计产能≠当前可供货量，供货能力必须另行书面确认。', 12)
manu = [c for c in companies if c['entity_type'] in MANUF_TYPES and c['grade'] in ('A', 'B')]
rows = []
for i, c in enumerate(manu, 1):
    ev = [e for e in c['evidence']][:2]
    rows.append([
        i, c['legal_name'], c.get('cn_name', ''), c['entity_type_label'], c['grade'],
        c.get('site', '—'), cap_main(c),
        (c.get('capacity') or {}).get('detail', '—'),
        (ev[0]['text'] if ev else '—'),
        (S.get(ev[0]['src'], {}).get('url') if ev else '—'),
        '；'.join(p['spec'][:60] + '…' for p in c.get('products_specs', [])[:1]),
        '待书面确认',
    ])
table(ws, ['序号', '企业名称', '中文名', '主体类型', '证据等级', '工厂所在地', '公开产能',
           '产能口径明细', '首要制造证据（原文摘要）', '证据来源URL', '规格（摘要）', '当前可供货量'],
      rows, widths=[6, 30, 18, 20, 9, 22, 16, 44, 60, 46, 40, 14], grade_col=5)
for i in range(5, 5 + len(rows)):
    ws.row_dimensions[i].height = 72

# ===================== 4. 贸易与销售主体 =====================
ws = wb.create_sheet('03_贸易与销售主体')
sheet_title(ws, '贸易/销售主体分栏：不要当作工厂',
            '包含：集团销售/营销主体、非目标产品但易混淆的石化企业、平台挂牌卖家。全部不作为制造证据。', 9)
trade = [c for c in companies if not (c['entity_type'] in MANUF_TYPES and c['grade'] in ('A', 'B'))]
rows = []
for i, c in enumerate(trade, 1):
    cat = {'AFFILIATE_SALES': '销售/营销主体（无自有装置）',
           'C': '非目标产品（易被关键词误判）'}.get(c['grade'] if c['grade'] == 'C' else c['entity_type'],
                                                c['entity_type_label'])
    if c['grade'] == 'C':
        cat = '非目标产品（易被关键词误判）'
    rows.append([i, c['legal_name'], c.get('cn_name', ''), c['entity_type_label'], cat, c['grade'],
                 c.get('site', '—'), c['grade_reason'], '需要澄清（见询证问题清单）'])
table(ws, ['序号', '企业名称', '中文名', '主体类型', '归类', '证据等级', '工厂所在地', '为什么不能当工厂', '处理建议'],
      rows, widths=[6, 32, 18, 22, 26, 9, 22, 78, 20], grade_col=6)
for i in range(5, 5 + len(rows)):
    ws.row_dimensions[i].height = 76

# ===================== 5. 制造证据台账 =====================
ws = wb.create_sheet('04_制造证据台账')
sheet_title(ws, '制造证据台账（逐条可回溯）',
            '每条证据记录：企业、证据类型、置信度、原文摘要与来源链接。『待下载』类证据不作为最终结论依据。', 9)
rows = []
for c in companies:
    for e in c['evidence']:
        src = S.get(e['src'], {})
        rows.append([c['legal_name'], c['grade'], e['id'], e['type'], e['grade'], e.get('conf', ''),
                     e['text'], e['src'], src.get('url', '')])
table(ws, ['企业', '企业证据等级', '证据编号', '证据类型', '证据性质', '置信度', '原文摘要', '来源ID', '来源URL'],
      rows, widths=[30, 10, 9, 20, 12, 8, 78, 9, 62])
for i in range(5, 5 + len(rows)):
    ws.row_dimensions[i].height = 54
    ws.cell(row=i, column=9).font = Font(name='Microsoft YaHei', size=9, color='0D9488', underline='single')

# ===================== 6. 产能与规格对照 =====================
ws = wb.create_sheet('05_产能与规格对照')
sheet_title(ws, '公开产能与规格口径对照',
            '公开设计产能 ≠ 当前实际供货能力；此处如实记录公开口径与冲突，不推算、不补数。', 8)
rows = []
for c in companies:
    cap = c.get('capacity', {})
    spec = c.get('products_specs', [{}])[0]
    rows.append([c['legal_name'], c['grade'], cap_main(c), cap.get('unit', '—'),
                 spec.get('product', '—'), spec.get('grade', '—'), cap.get('detail', '—'), cap.get('caveat', '—')])
table(ws, ['企业', '等级', '公开产能', '单位', '主要产品', '牌号/用途', '产能口径明细与冲突', '当前供货能力判断'],
      rows, widths=[30, 8, 16, 20, 14, 26, 64, 56], grade_col=2)
for i in range(5, 5 + len(rows)):
    ws.row_dimensions[i].height = 64

# 规格明细
start = 5 + len(rows) + 2
ws.cell(row=start, column=1, value='产品规格明细（企业公开值，仅 SHARQ 公布了完整典型指标）').font = Font(name='Microsoft YaHei', size=11, bold=True, color=TEAL)
srows = []
for c in companies:
    for p in c.get('products_specs', []):
        srows.append([c['legal_name'], p['product'], p.get('grade', ''), p.get('spec', ''), p.get('source', '')])
table(ws, ['企业', '产品', '牌号/用途', '公开规格', '来源'], srows, start_row=start + 1,
      widths=[30, 18, 30, 70, 12], freeze=False)

# ===================== 7. 官方联系渠道 =====================
ws = wb.create_sheet('06_官方联系渠道')
sheet_title(ws, '企业官网与官方公开联系渠道',
            '仅记录官网公开信息；未取得的部分标『待核验』，不臆造电话或邮箱。', 6)
rows = []
for c in companies:
    base = c.get('website', '')
    for ch in (c.get('official_channels') or [{'channel': '—', 'value': '—', 'status': '待核验'}]):
        rows.append([c['legal_name'], c.get('cn_name', ''), ch.get('channel'), ch.get('value'), ch.get('status'), base])
table(ws, ['企业', '中文名', '渠道类型', '公开信息', '核验状态', '企业官网'], rows, widths=[32, 18, 22, 56, 34, 52])
if rows:
    for i in range(5, 5 + len(rows)):
        ws.row_dimensions[i].height = 40

# ===================== 8. 认证与质量 =====================
ws = wb.create_sheet('07_认证与质量文件')
sheet_title(ws, '公开可得的认证与质量文件',
            '认证须对应到具体工厂；集团证书不能自动替代工厂证书。', 5)
rows = []
for c in companies:
    certs = c.get('certifications') or [{'cert': '未取得', 'status': '待核验'}]
    for ce in certs:
        rows.append([c['legal_name'], c['grade'], ce.get('cert'), ce.get('status'), '需向企业索取证书编号与有效期'])
table(ws, ['企业', '等级', '认证/文件', '公开状态', '下一步动作'], rows, widths=[34, 8, 32, 56, 40], grade_col=2)
for i in range(5, 5 + len(rows)):
    ws.row_dimensions[i].height = 34

# ===================== 9. 询证问题 =====================
ws = wb.create_sheet('08_询证问题清单')
sheet_title(ws, f"后续核验问题清单（{len(D['questions'])} 条）",
            '可直接复制发给对方；建议要求书面回复并附证书、COA 与提单样本（可脱敏）。', 6)
rows = []
for q in D['questions']:
    cname = next((c['legal_name'] for c in companies if c['id'] == q['company']), '通用')
    rows.append([q['id'], cname, q['q'], '未发出', '', ''])
table(ws, ['问题编号', '相关企业', '需核实的问题', '状态', '回复要点', '负责人'], rows,
      widths=[10, 34, 92, 12, 40, 12])
for i in range(5, 5 + len(rows)):
    ws.row_dimensions[i].height = 34
dv = DataValidation(type='list', formula1='"未发出,已发出,已回复,需跟进,已关闭"', allow_blank=True)
ws.add_data_validation(dv)
dv.add(f"D5:D{4 + len(rows)}")

# ===================== 10. 证据来源 =====================
ws = wb.create_sheet('09_证据来源')
sheet_title(ws, f"公开证据来源清单（{len(D['sources'])} 项）",
            '标注『待下载/直连失败』的来源仅作线索，不作为最终结论依据。', 6)
rows = []
for s in D['sources']:
    rows.append([s['id'], s['title'], s['url'], s['date'], s['status'], s['access']])
table(ws, ['来源ID', '标题', 'URL', '发布日期', '收录状态', '访问日期'], rows,
      widths=[9, 74, 62, 14, 30, 12])
for i in range(5, 5 + len(rows)):
    ws.row_dimensions[i].height = 38

# ===================== 11. 筛选漏斗 =====================
ws = wb.create_sheet('10_筛选漏斗')
sheet_title(ws, '筛选漏斗与统计', '可复现的收敛过程：从候选池到可询盘主体。', 5)
funnel = [
    ('Step 1 初始候选', 20, '沙特石化集团/附属 + 各方提及的名字（含 Sadara、Petrokemya、Sipchem、平台挂牌卖家）'),
    ('Step 2 取得产品级线索', 9, '出现 MEG 相关公开记载或明确为石化一体化企业'),
    ('Step 3 装置/产能级证据', sum(1 for c in companies if c['grade'] == 'A'), '官网产能表、EPC 项目页、官方投产公告、交易所文件、装置级运行数据（A 级企业数）'),
    ('Step 4 可询盘主体', len(manu), 'A/B 级生产主体，可直接发询盘（经 SABIC/自营渠道）'),
]
table(ws, ['阶段', '数量', '说明'], funnel, widths=[26, 10, 92])
r0 = 5
chart = BarChart()
chart.type = 'bar'
chart.style = 10
chart.title = '筛选漏斗：候选收敛'
chart.y_axis.title = '数量'
data = Reference(ws, min_col=2, min_row=4, max_row=4 + len(funnel))
cats = Reference(ws, min_col=1, min_row=5, max_row=4 + len(funnel))
chart.add_data(data, titles_from_data=True)
chart.set_categories(cats)
chart.height = 8
chart.width = 18
chart.legend = None
ws.add_chart(chart, 'E4')

# 等级统计
r1 = 4 + len(funnel) + 3
ws.cell(row=r1, column=1, value='按证据等级统计').font = Font(name='Microsoft YaHei', size=11, bold=True, color=TEAL)
grade_rows = [[g, sum(1 for c in companies if c['grade'] == g)] for g in 'ABCD']
table(ws, ['证据等级', '企业数'], grade_rows, start_row=r1 + 1, widths=[26, 10, 92], freeze=False)

# ===================== 12. 模板 =====================
ws = wb.create_sheet('11_新建候选_模板')
sheet_title(ws, '新建候选企业录入模板（空白）',
            '任何新增企业都必须沿同一字段链录入；未取得的字段填『待核验』，不得留空，更不得臆造。', 16)
hdr = ['序号', '企业法定名称', '中文名', '企业类型', '所属集团', '证据等级', '工厂所在地', '产品', '规格/牌号',
       '公开产能', '产能来源', '制造证据（原文摘要）', '证据来源URL', '官方联系渠道', '出口/认证信息', '待核验问题']
table(ws, hdr, [['' for _ in hdr] for _ in range(15)], widths=[6, 30, 18, 20, 20, 9, 22, 14, 26, 14, 22, 60, 44, 34, 30, 40])
last = 4 + 15
dv_type = DataValidation(type='list', formula1='"制造企业,合资制造企业,集团销售主体,附属公司销售主体,一般贸易商,代理/经销商,身份不明"', allow_blank=True)
dv_grade = DataValidation(type='list', formula1='"A,B,C,D"', allow_blank=True)
ws.add_data_validation(dv_type); ws.add_data_validation(dv_grade)
dv_type.add(f'D5:D{last}')
dv_grade.add(f'F5:F{last}')
for i in range(5, last + 1):
    ws.row_dimensions[i].height = 30

wb.save(OUT)
print('saved', OUT)
