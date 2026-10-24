# -*- coding: utf-8 -*-
"""Build the SBS HS-code research workbook from case JSON."""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

def arg(flag, default=None):
    if flag in sys.argv:
        return sys.argv[sys.argv.index(flag) + 1]
    return default

CASE_PATH = arg('--case') or arg('--in') or (sys.argv[1] if len(sys.argv) > 1 else None)
if not CASE_PATH:
    sys.exit('usage: python build_workbook.py --case <case.json> --out <workbook.xlsx>')
case = json.load(open(CASE_PATH, encoding='utf-8'))

TITLE_FILL = PatternFill('solid', fgColor='1F3864')
HEAD_FILL = PatternFill('solid', fgColor='D9E2F3')
SUB_FILL = PatternFill('solid', fgColor='F2F2F2')
WARN_FILL = PatternFill('solid', fgColor='FFF2CC')
BAD_FILL = PatternFill('solid', fgColor='FCE4D6')
GOOD_FILL = PatternFill('solid', fgColor='E2EFDA')
THIN = Side(style='thin', color='BFBFBF')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical='top')
CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)

def sheet(wb, name, title, subtitle, headers, widths, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = name
    n = len(headers)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
    c = ws.cell(1, 1, title)
    c.font = Font(size=13, bold=True, color='FFFFFF')
    c.fill = TITLE_FILL
    c.alignment = Alignment(vertical='center')
    ws.row_dimensions[1].height = 26
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n)
    c2 = ws.cell(2, 1, subtitle)
    c2.font = Font(size=9, color='595959')
    c2.alignment = WRAP
    ws.row_dimensions[2].height = 30
    for i, h in enumerate(headers, 1):
        cell = ws.cell(4, i, h)
        cell.font = Font(bold=True, size=10)
        cell.fill = HEAD_FILL
        cell.alignment = CENTER
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    ws.freeze_panes = 'A5'
    return ws

def put(ws, r, values, fills=None, bold_first=False, height=None):
    for i, v in enumerate(values, 1):
        cell = ws.cell(r, i, v)
        cell.alignment = WRAP
        cell.border = BORDER
        cell.font = Font(size=10, bold=(bold_first and i == 1))
        if fills and i in fills:
            cell.fill = fills[i]
    if height:
        ws.row_dimensions[r].height = height

wb = Workbook()
M = case['meta']

# ---------- 00 封面 ----------
ws = sheet(wb, '00_封面与口径', '海关商品编码（HS）候选研究工作簿 —— ' + case['product']['name_cn'],
           '本工作簿与同名 HTML 报告数据同源；结论为"候选+条件+依据"，不构成单一申报结论，最终以海关认定为准。',
           ['项目', '内容', '来源/说明'], [26, 78, 46], first=True)
rows = [
    ('案例编号', case['meta']['case_id'], '本次任务生成'),
    ('查询日期', case['meta']['query_date'], '所有税率与法规的"截至时点"'),
    ('HS 版本', case['meta']['hs_version'], '国务院关税税则委员会 税委会公告2025年第12号'),
    ('退税文库版本', case['meta']['rebate_version'], '国家税务总局 税总货劳函〔2026〕214号'),
    ('产品名称', case['product']['name_cn'], '用户输入'),
    ('英文名称', case['product']['name_en'], 'SDS/合同常用英文品名'),
    ('CAS 号', case['product']['cas'], '族类登记号，不能单独锁定 10 位编码'),
    ('别名', '、'.join(case['product']['aliases']), '检索用'),
    ('外观形态', case['product']['appearance'], 'S9 供应商 SDS 第9节'),
    ('是否混合物', case['product']['is_mixture'], '基础聚合物 vs 复配 TPE'),
    ('主要用途', '、'.join(case['product']['use']), 'S9 第1节建议用途 + 行业通用'),
    ('是否零售包装', case['product']['retail'], '用户输入'),
    ('危险性', case['product']['hazard'], 'S9 第2、14节'),
    ('候选数量', str(len(case['candidates'])), '含首选、并列、兜底、条件性候选'),
    ('证据等级口径', 'A 官方原文 / B 二手或供应商原始文件并已交叉核对 / C 第三方数据库 / D 待核验', '贯穿全簿'),
    ('免责声明', case['not_advice'], '必须随交付物一起传阅'),
]
r = 5
for k, v, s in rows:
    put(ws, r, [k, v, s])
    ws.cell(r, 1).font = Font(size=10, bold=True)
    r += 1

# ---------- 01 产品属性 ----------
ws = sheet(wb, '01_产品属性', '产品属性表（归类所需的每一个特征）',
           '每一行是一个影响归类的产品特征：值、来源、对本例归类的意义、若缺失的处理方式。',
           ['特征', '本例取值/描述', '证据来源', '对归类的影响', '证据等级', '是否已确认'],
           [22, 46, 30, 44, 18, 12])
attrs = [
    ('化学身份', '苯乙烯-丁二烯-苯乙烯嵌段共聚物（SBS）', 'S9 SDS 第1节 / S10 CAS', '锁定 40.02 项下 SBR 系列', 'B', '是'),
    ('高分子结构', '线型/星型三嵌段，聚苯乙烯硬段 + 聚丁二烯软段', 'S9 + 行业通识', '决定"热塑性"，对应 4002.19 的热塑子目', 'B', '是'),
    ('是否氢化（SEBS）', '待确认（本表按未氢化 SBS）', '—', '氢化后常按 4002.99 申报', 'D', '否'),
    ('单体单元', '苯乙烯 + 丁二烯，无第三单体', 'S10', '排除 EPDM/BR/NBR 等其他胶种子目', 'B', '是'),
    ('苯乙烯含量', '待确认（典型 20%–40%）', '—', '影响美国 .20 号；影响 39 章与 40 章比较', 'D', '否'),
    ('是否充油', '待确认（本表给出充油/非充油两条路径）', '—', '决定 4002191300 与 4002191400', 'D', '否'),
    ('充油比例/油种', '待确认', '—', '注释五（二）允许充油的边界', 'D', '否'),
    ('是否含填料/助剂', '待确认（微量抗氧剂、隔离剂常见）', '—', '决定是否落入 4005 复合橡胶', 'D', '否'),
    ('物理形态', '白色/透明颗粒、碎屑状固体', 'S9 第9节', '满足第40章注释三"初级形状"', 'B', '是'),
    ('是否硫化', '否（热塑性，未硫化）', 'S9 + 产品定义', '排除 4006/4008', 'B', '是'),
    ('比重', '< 1', 'S9 第9节', '辅助识别，不改变归类', 'B', '是'),
    ('溶解性', '不溶于水；溶于特定溶解度参数溶剂', 'S9 第9节 / S10', '排除胶乳/分散体路径', 'B', '是'),
    ('是否混合物/制剂', '基础聚合物：否；复配 TPE 料：是', '用户输入', '决定 40.02 还是 40.05', 'C', '部分'),
    ('主要用途', '塑料改性、沥青改性、胶粘剂、鞋材、电线电缆', 'S9 第1节', '申报要素"用途"；成品化后编码改变', 'B', '是'),
    ('是否零售包装', '否（编织袋/吨包）', '用户输入', '不影响基础聚合物归类', 'C', '是'),
    ('危险性', '非危险化学品、非危险货物（无 UN 号）', 'S9 第2、14节', '运输与单证层面', 'B', '是'),
    ('CAS 适用性', '9003-55-8 为族类号，覆盖 SBS 与 SBR 多牌号', 'S10', '不能用 CAS 直接反查编码', 'C', '是'),
]
r = 5
for row in attrs:
    put(ws, r, list(row), fills={6: (BAD_FILL if row[5] == '否' else GOOD_FILL)})
    r += 1
ws.cell(r + 1, 1, '说明：标"否"的特征是本次无法从用户材料确认、且会改变编码的项目，已进入"04_缺失信息"表。').font = Font(size=9, italic=True, color='C00000')

# ---------- 02 候选编码 ----------
ws = sheet(wb, '02_候选编码', '候选编码总表（中国出口 10 位）',
           '按优先级排序。同一产品特征组合只应命中其中一个；"条件"未满足时该候选不成立。',
           ['优先级', '编号', '申报编码(10位)', 'HS6', '品名（税则+数据库口径）', '定位', '置信度', '成立条件（摘要）',
            '不成立时的风险', '最惠国税率', '普通税率', '出口关税', '出口退税(数据源)', '增值税', '监管条件', '检验检疫'],
           [7, 6, 14, 9, 34, 16, 14, 52, 40, 10, 10, 9, 14, 9, 9, 9])
r = 5
for c in sorted(case['candidates'], key=lambda x: x['rank']):
    put(ws, r, [c['rank'], c['id'], c['code10'], c['hs6'], c['name'], c['verdict'], c['confidence'],
                '；'.join(c['conditions']), c['vuln'], c['mfn'], c['gen'], c['export_tax'], c['rebate'],
                c['vat'], c['reg'], c['ciq']],
        fills={1: GOOD_FILL if c['rank'] <= 2 else (WARN_FILL if c['rank'] <= 4 else SUB_FILL)})
    r += 1
zero = [c['code10'] for c in case['candidates'] if str(c['rebate']).startswith('0')]
top = [c['code10'] for c in sorted(case['candidates'], key=lambda x: x['rank'])[:2]]
if zero:
    ws.cell(r + 1, 1, '注：候选 %s 的出口退税率为 0%%，与首选候选 %s 的退税率存在量级差异，是本次归类最重要的商业风险点。' % ('、'.join(zero), '、'.join(top))).font = Font(size=9, bold=True, color='C00000')
ws.cell(r + 2, 1, '注：出口退税率为数据源快照（B级），须按 2026C 版文库在电子税务局或委托报关行二次核验。').font = Font(size=9, italic=True)

# ---------- 03 归类依据 ----------
ws = sheet(wb, '03_归类依据', '逐个候选的法律依据（条文 → 适用 → 结论）',
           '每条依据都引用到具体章注/税目/子目条文；税则条文可在 S1 官方 PDF 中按章节页码核对。',
           ['编号', '申报编码', '依据层级', '条文/规则原文（摘录）', '在本例中如何适用', '支撑的结论', '等级'],
           [6, 14, 16, 62, 56, 30, 10])
LAW = [
    ('总规则一', '具有法律效力的归类，应按税目条文和有关类注或章注确定', '先定章、再定税目，不按商品俗称或CAS直接给码'),
    ('第40章注释一', '本目录所称"橡胶"，是指……天然橡胶、合成橡胶、从油类提取的油膏以及上述物品的再生品', 'SBS 属合成橡胶，进入第40章考察'),
    ('第40章注释三', '"初级形状"只限于液体/糊状（含胶乳）及不规则块、团、包、粉、粒、碎屑等散装形状', 'SBS 粒料属初级形状；压片/成卷则不属于'),
    ('第40章注释四（一）', '不饱和合成物质，用硫磺硫化能使其不可逆地变为非热塑物质，且满足18–29℃下3倍拉伸不断、2倍拉伸5分钟内回复到1.5倍以内', 'SBS 含丁二烯不饱和双键，可硫化；需以技术数据举证'),
    ('第40章注释五（一）', '与硫化剂、促进剂、颜料（识别用除外）、增塑剂或增量剂（充油橡胶所加矿物油除外）、填料、增强剂等混合的橡胶不归入40.01/40.02', '含填料/助剂复配料应归 4005'),
    ('第40章注释五（二）', '含乳化剂、微量抗氧剂、稳定剂等特殊用途添加剂的橡胶，仍具有原料基本特性时保留在40.01/40.02', '微量抗氧剂不改变 40.02 归类'),
    ('第40章注释九', '"板""片""带"仅指未切割或仅切割成矩形的板片带及正几何形块', '配合注释三判定形态'),
    ('税目 40.02', '合成橡胶及从油类提取的油膏，初级形状或板、片、带；……', 'SBS 的税目层级'),
    ('子目 4002.19', '--其他（丁苯橡胶/SBR；羧基丁苯橡胶/XSBR 项下，非胶乳）', '固体粒料 SBS 的第一层落点'),
    ('本国子目 4002.1913', '----热塑丁苯橡胶', '与 SBS 化学身份+热塑特征直接对应，首选'),
    ('本国子目 4002.1914', '----充油热塑丁苯橡胶', '充油牌号的对应子目'),
    ('本国子目 4002.1919', '----其他', '兜底'),
    ('本国子目 4005.9900', '--其他（未硫化的复合橡胶，初级形状）', '复配料路径'),
    ('第39章注释二（十一）', '本章不包括：第四十章规定的合成橡胶及其制品', '排除 39.03 路径的法理依据'),
    ('第39章注释四', '共聚物按重量最大的单体单元归入相应税目', '若按第39章口径，苯乙烯/丁二烯比例决定 3903 还是 3902'),
    ('归类总规则六', '子目归类按子目条文及子目注释确定，比较只能在同一数级上进行', '10 位细分只能在 4002.19 同级内比较'),
]
r = 5
for c in sorted(case['candidates'], key=lambda x: x['rank']):
    for k in c['basis']:
        law = next((l for l in LAW if k.startswith(l[0].split('（')[0][:6])), None)
        text = law[1] if law else '（见税则对应条文）'
        how = law[2] if law else c['why']
        put(ws, r, [c['id'], c['code10'], k, text, how, c['title'], 'A' if '注释' in k or '子目' in k or '税目' in k or '规则' in k else 'B'])
        r += 1
    put(ws, r, [c['id'], c['code10'], '归类理由（综合）', c['why'], '—', c['title'], c['confidence']], fills={4: SUB_FILL})
    r += 1

# ---------- 04 缺失信息 ----------
ws = sheet(wb, '04_缺失信息', '关键缺失信息与补证清单',
           '这些信息未确认前，不能把任一候选写成"确定编码"。按优先级（高→中）处理。',
           ['编号', '缺失信息', '影响哪个编码决策', '优先级', '如何补证（向谁要）', '补齐后的后果'],
           [7, 40, 36, 8, 48, 30])
r = 5
for m in case['missing']:
    put(ws, r, list(m), fills={4: (BAD_FILL if m[3] == '高' else WARN_FILL)})
    r += 1

# ---------- 05 歧义与误配 ----------
ws = sheet(wb, '05_歧义与误配', '容易混淆的编码对 / 常见误配（含已过期编码）',
           '上表是"同一产品可能落入的相邻编码"，下表是"检索时容易误命中的无关或过期编码"。',
           ['类型', '对象', '判断要点', '说明'], [16, 34, 34, 78])
r = 5
for a in case['ambiguity']:
    put(ws, r, ['歧义', a[0], a[1], a[2]], fills={1: WARN_FILL})
    r += 1
for a in case['ac']:
    fill = BAD_FILL if ('过期' in a[2] or '不适用' in a[2]) else SUB_FILL
    put(ws, r, ['误配/边界', a[0] + ' ' + a[1], a[2], a[3] + '（来源等级：' + a[4] + '）'], fills={3: fill})
    r += 1

# ---------- 06 层级对照 ----------
ws = sheet(wb, '06_编码层级对照', '国际 6 位 → 中国 8/10 位 → 目的国编码',
           'HS 前 6 位全球一致；第 7 位以后各国自定。给客户报价或让客户清关时，必须落到目的国自己的编码。',
           ['层级', '说明'], [26, 120])
r = 5
put(ws, r, ['国际 HS 6 位', '4002.19 —— 全球统一，任何国家报关都必须能对应到这一层'], fills={1: HEAD_FILL})
r += 1
for k, v in case['six_tree']:
    put(ws, r, [k, v])
    r += 1
ws.cell(r + 1, 1, '目的国编码（本次检索到的层级与结论）').font = Font(bold=True, size=11)
r += 2
hdr = ['国家/地区', '该国 HS6', '该国细分编码与层级', '税率（本次所得）', '说明', '证据等级', '来源 URL']
for i, h in enumerate(hdr, 1):
    c = ws.cell(r, i, h); c.font = Font(bold=True); c.fill = HEAD_FILL; c.alignment = CENTER; c.border = BORDER
ws.column_dimensions['C'].width = 46
ws.column_dimensions['G'].width = 46
r += 1
for f in case['foreign']:
    put(ws, r, [f['country'], f['hs6'], f['sub'], f['rate'], f['note'], f['level'], f['url']],
        fills={6: (BAD_FILL if '待核验' in f['level'] else GOOD_FILL)})
    r += 1

# ---------- 07 关税与税率 ----------
ws = sheet(wb, '07_关税税率', '中国进口口税率与协定税率（方向：出口时影响客户清关，进口时影响我方成本）',
           '数值来自 S1 官方税则 4002.1913 / 4002.1914 行。RCEP 与协定税率按具体国别列出。',
           ['编码', '品名', '最惠国', '普通', '出口关税', '出口退税', '增值税'] + ['协定-' + k for k in sorted(case['candidates'][0]['agreement_rates'])] + ['RCEP-' + k for k in sorted(case['candidates'][0]['rcep'])],
           [12, 26, 8, 8, 8, 10, 8] + [11] * 45)
r = 5
for c in case['candidates']:
    row = [c['code10'], c['name'], c['mfn'], c['gen'], c['export_tax'], c['rebate'], c['vat']]
    row += [c['agreement_rates'].get(k, '—') for k in sorted(c['agreement_rates'])]
    row += [c['rcep'].get(k, '—') for k in sorted(c['rcep'])]
    put(ws, r, row)
    r += 1
ws.cell(r + 1, 1, '说明：空白"—"表示该协定/安排对本国子目无特惠安排或未列明；出口退税以数据源为准，须按 2026C 版文库核验。').font = Font(size=9, italic=True)

# ---------- 08 出口监管 ----------
ws = sheet(wb, '08_出口监管条件', '各候选对应的中国出口监管条件与结论',
           '逐项给出"结论 + 依据 + 适用条件 + 仍需确认"，不允许只给结论。',
           ['编号', '监管主题', '结论', '依据', '等级', '适用条件', '仍需确认', '对业务的影响'],
           [6, 22, 46, 40, 20, 34, 40, 34])
r = 5
for g in case['regulatory']:
    put(ws, r, [g['id'], g['topic'], g['conclusion'], g['basis'], g['level'], g['condition'], g['todo'], g['effect']],
        fills={5: (BAD_FILL if ('D' in g['level'] or '待核验' in g['level']) else (WARN_FILL if 'B' in g['level'] else GOOD_FILL))})
    r += 1

# ---------- 09 申报要素 ----------
ws = sheet(wb, '09_申报要素填写', '首选候选的申报要素与填写建议',
           '申报要素取自 B 级数据源；报关前须在单一窗口按 4002191300 回填核对。',
           ['序号', '申报要素', '填写建议（本例）', '易错点'], [6, 34, 56, 50])
ws2 = next((c['decl_elems'] for c in sorted(case['candidates'], key=lambda x: x['rank']) if c.get('decl_elems')), ['以税则申报要素为准（本次未取得原文）'])
GUIDE = {
    '品牌类型': ('按实际：无品牌 / 境内自主品牌 / 境内收购品牌 / 境外品牌（贴牌）/ 境外品牌（其他）', '出口享惠情况填错同样退单'),
    '出口享惠情况': ('是否申请原产地证享惠要与报关单、合同一致', '与合同不一致'),
    '用途': ('如"塑料改性用""沥青改性用"，与客户实际用途一致', '写"工业用"过于笼统可能被质疑'),
    '外观(板、片、带等)': ('填"颗粒"或"碎屑"，务必与实物一致', '填"颗粒"实物为压片=申报不实'),
    '丁苯橡胶请注明是否充油、热塑': ('如"未充油、热塑"或"充油20%、热塑"（充油须给比例）', '本要素直接决定 4002191300 / 4002191400'),
    '成分含量': ('如"苯乙烯25%、丁二烯75%（不含油）"', '充油牌号须注明油的比例'),
    '签约日期': ('按合同签约日期填', '—'),
    '品牌(中文或外文名称)': ('有则填，无则填"无品牌"', '—'),
    '型号': ('填牌号（如 791H、1401E 等）', '—'),
    'GTIN': ('无则填"无"', '—'),
    'CAS': ('填 9003-55-8', '—'),
    '其他': ('按海关要求补充', '—'),
}
r = 5
for i, e in enumerate(ws2, 1):
    key = e.split('[')[0].strip()
    g = GUIDE.get(key, ('按实际情况填写', '—'))
    put(ws, r, [i, e, g[0], g[1]])
    r += 1

# ---------- 10 待确认问题 ----------
ws = sheet(wb, '10_待确认问题', '需报关行 / 预裁定 / 税务确认的问题清单',
           '每条都有责任方与解除条件；未解除前不得对客户承诺"确定编码"或"确定退税率"。',
           ['编号', '问题', '影响哪项结论', '找谁确认', '提出方', '状态'],
           [6, 46, 36, 46, 16, 12])
r = 5
for q in case['confirm']:
    put(ws, r, [q[0], q[1], q[2], q[3], q[4], '待确认'], fills={6: WARN_FILL})
    r += 1
ws.cell(r + 1, 1, '预裁定提示：按《海关预裁定管理暂行办法》（海关总署令第273号）第七条，应在货物拟进出口3个月前向备案地直属海关提出；第十一条60日内制发决定书；第十三条有效期3年，依据变化自动失效。').font = Font(size=9, color='C00000')

# ---------- 11 来源链接 ----------
ws = sheet(wb, '11_来源链接', '来源清单（每条都可点击核验）',
           'A=官方原文；B=二手/供应商原始文件但已与官方交叉核对；C=第三方数据库；D=待核验（不得作为承诺依据）。',
           ['编号', '来源名称', '发布单位', '文号', '日期', 'URL', '等级', '用于', '核验情况', '备注'],
           [6, 44, 22, 30, 24, 54, 22, 40, 40, 36])
r = 5
for s in case['sources']:
    put(ws, r, [s['id'], s['name'], s['publisher'], s['docno'], s['date'], s['url'], s['level'], s['used_for'], s['verified'], s['note']],
        fills={7: (BAD_FILL if s['level'].startswith('D') else (WARN_FILL if s['level'].startswith('C') else GOOD_FILL))})
    cell = ws.cell(r, 6)
    cell.hyperlink = s['url']
    cell.font = Font(size=9, color='0563C1', underline='single')
    r += 1

# ---------- 12 校验与统计 ----------
ws = sheet(wb, '12_校验与统计', '数据自检',
           '由脚本自动统计，用于交付前确认没有空表、没有遗漏来源。',
           ['检查项', '结果', '说明'], [36, 16, 80])
stats = [
    ('候选编码数量', len(case['candidates']), '含首选、并列、兜底、条件性与形态分岔候选'),
    ('首选/并列候选', sum(1 for c in case['candidates'] if c['rank'] <= 2), '、'.join(c['code10'] for c in sorted(case['candidates'], key=lambda x: x['rank'])[:2])),
    ('A 级来源数量', sum(1 for s in case['sources'] if s['level'].startswith('A')), '官方原文'),
    ('D 级待核验来源', sum(1 for s in case['sources'] if s['level'].startswith('D')), '目的国税则或需专业判断的项目，不得作为承诺依据'),
    ('缺失信息条数', len(case['missing']), '全部进入补证清单'),
    ('监管条件条目', len(case['regulatory']), '出口证件、退税、危化、危货、检验检疫等'),
    ('待确认问题', len(case['confirm']), '含报关行、税务、目的国代理'),
    ('已过期/不可用编码', sum(1 for a in case['ac'] if ('过期' in a[2] or '不适用' in a[2])), '见 05_歧义与误配 表下半部分'),
]
r = 5
for k, v, n in stats:
    put(ws, r, [k, v, n])
    r += 1

for name in wb.sheetnames:
    w = wb[name]
    w.sheet_view.zoomScale = 90

import re
default_name = 'HS归类候选研究工作簿_%s_%s.xlsx' % (
    re.sub(r'[\\/:*?"<>|\s]+', '', case['product']['name_cn'][:24]), case['meta']['case_id'])
out = arg('--out') or os.path.join(os.path.dirname(os.path.abspath(CASE_PATH)), default_name)
wb.save(out)
print('saved', out, os.path.getsize(out))
