#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_xlsx.py — 把 research.json 渲染成多表 Excel 工作簿（默认 13 表）。

用法:
    python render_xlsx.py research.json -o workbook.xlsx

依赖：openpyxl（pip install openpyxl）
输出表：00 说明 / 01 下游结构 / 02 需求指标库 / 03 代理指标分级 / 04 历史比较 /
        05 景气打分 / 06 传导链条 / 07 政策与事件 / 08 价格与库存 / 09 缺口清单 /
        10 来源清单 / 11 证据明细 / 12 口径规范
"""
import argparse, json, os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule

NAVY, BLUE, GOLD, GREY = '0B1F2E', '1B3F5C', 'E6B45A', 'F2F5F8'
H_FILL = PatternFill('solid', fgColor=BLUE)
H_FONT = Font(color='FFFFFF', bold=True, size=10.5, name='微软雅黑')
T_FONT = Font(name='微软雅黑', size=10)
THIN = Side(style='thin', color='D5DEE6')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical='top')
CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)


def header_block(ws, title, subtitle, ncol):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(1, 1, title)
    c.font = Font(name='微软雅黑', size=15, bold=True, color='FFFFFF')
    c.fill = PatternFill('solid', fgColor=NAVY)
    c.alignment = Alignment(vertical='center', horizontal='left', indent=1)
    ws.row_dimensions[1].height = 34
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c2 = ws.cell(2, 1, subtitle)
    c2.font = Font(name='微软雅黑', size=10, color='D8E6F2')
    c2.fill = PatternFill('solid', fgColor=NAVY)
    c2.alignment = Alignment(vertical='center', horizontal='left', indent=1, wrap_text=True)
    ws.row_dimensions[2].height = 30


def table(ws, start_row, headers, rows, widths=None, freeze=True, numfmt=None, wrap_cols=None):
    for j, h in enumerate(headers, 1):
        c = ws.cell(start_row, j, h)
        c.font = H_FONT; c.fill = H_FILL; c.alignment = CENTER; c.border = BORDER
    ws.row_dimensions[start_row].height = 30
    for i, r in enumerate(rows, start_row + 1):
        for j in range(1, len(headers) + 1):
            v = r[j - 1] if j - 1 < len(r) else None
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            c = ws.cell(i, j, v)
            c.font = T_FONT; c.border = BORDER
            c.alignment = WRAP if (wrap_cols is None or j in wrap_cols) else Alignment(vertical='top')
            if i % 2 == 0:
                c.fill = PatternFill('solid', fgColor=GREY)
            if numfmt and j in numfmt and isinstance(v, (int, float)):
                c.number_format = numfmt[j]
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
    if freeze:
        ws.freeze_panes = ws.cell(start_row + 1, 1)
    if not rows:  # 空表时给出提示，避免条件格式/freeze 越界
        c = ws.cell(start_row + 1, 1, '（本次无数据：该项为空，请检查 research.json 对应字段）')
        c.font = Font(name='微软雅黑', size=10, color='8A4B08', italic=True)
        ws.merge_cells(start_row=start_row + 1, start_column=1,
                       end_row=start_row + 1, end_column=max(len(headers), 1))
    return start_row + len(rows)


def build(doc, out):
    meta = doc.get('meta', {})
    segs = doc.get('segments', [])
    segname = {s['key']: s['name'] for s in segs}
    wb = Workbook()

    def sheet(name, color=NAVY):
        ws = wb.create_sheet(name)
        ws.sheet_properties.tabColor = color
        return ws

    # 00 说明
    ws = wb.active; ws.title = '00_说明'; ws.sheet_properties.tabColor = GOLD
    header_block(ws, '%s 下游需求研究报告 · 数据工作簿' % meta.get('product', ''),
                 '研究区间：%s ｜ 数据截止：%s ｜ 所有数值均标注数据日期、口径、来源；缺口不估算。'
                 % (meta.get('window', ''), meta.get('asof', '')), 3)
    rows = [['01_下游结构', '多套消费占比口径（含统计年份/来源/差异原因）', '占比是权重，不是结论'],
            ['02_需求指标库', '价格/开工/产量/库存/利润/订单/消费（长表可透视）', '按“等级”筛 A 得到真实需求指标'],
            ['03_代理指标分级', 'A/B/C/D 分级与局限', '决定某指标能否代表消费'],
            ['04_历史比较', '区间初值→末值、环比、同比', '只做同口径相邻两期比较'],
            ['05_景气打分', '分项打分、分项指数、加权传导与敏感性', '禁止跨下游简单平均'],
            ['06_传导链条', '终端→采购的每一跳、滞后与强度', '价格→需求为弱相关'],
            ['07_政策与事件', '可核验政策/事件与方向判断', '附原始链接'],
            ['08_价格与库存', '价格/库存/利润明细序列', '注意万重箱与万吨单位'],
            ['09_缺口清单', '缺口、原因、补数路径、影响', '不用估计值顶替'],
            ['10_来源清单', '来源机构、类型、证据ID、链接', '逐条可核验'],
            ['11_证据明细', '全部原始证据记录', '与 HTML 同源'],
            ['12_口径规范', '指标单位/范围/频率/常见误用', '跨品种通用']]
    table(ws, 4, ['工作表', '内容', '使用要点'], rows, widths=[20, 62, 44])
    ws.freeze_panes = 'A5'
    for i, w in enumerate(['① 下游产品价格上涨 ≠ 原料消费增长。',
                           '② 不要对所有下游简单平均。',
                           '③ 不同机构口径数值不可直接相减。',
                           '④ 占比须标年份与来源，禁止跨口径相加。',
                           '⑤ 只陈述已发生事实，不预测价格。'], 19):
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=3)
        c = ws.cell(i, 1, w)
        c.font = Font(name='微软雅黑', size=10, color='8A4B08')
        c.fill = PatternFill('solid', fgColor='FFF6E5')
        c.alignment = Alignment(wrap_text=True, vertical='center', indent=1)
        ws.row_dimensions[i].height = 24

    # 01 结构
    ws = sheet('01_下游结构', BLUE)
    header_block(ws, '一、下游消费结构（多口径并列）',
                 '差异来自分母：内需 / 表观（含出口）/ 全部应用（含损耗）。使用时必须与统计年份绑定。', 7)
    rows = []
    for s in doc.get('structure', []):
        for it in s.get('items', []):
            rows.append([s.get('year'), s.get('org'), it[0], it[1], it[2] if len(it) > 2 else None,
                         s.get('basis'), s.get('note', '')])
    table(ws, 4, ['统计年份', '来源机构', '下游/应用', '占比(%)', '对应量(万吨)', '口径说明', '备注'],
          rows, widths=[10, 30, 34, 9, 12, 34, 44], numfmt={4: '0.0', 5: '#,##0'})

    # 02 指标库
    ws = sheet('02_需求指标库')
    header_block(ws, '二、需求指标库（长表，可透视）',
                 '等级：A=真实需求或其产量级代理；B=表观/库存/利润；C=价格与预期；D=调研定性。', 12)
    rows = [[e['id'], segname.get(e['seg'], e['seg']), e.get('kpi', ''), e.get('metric'), e.get('value'),
             e.get('unit'), e.get('date'), e.get('period', ''), e.get('caliber', ''),
             (doc.get('sources', {}).get(e.get('src'), [e.get('src')])[0]), e.get('grade', 'A'), e.get('url')]
            for e in sorted(doc.get('evidence', []), key=lambda x: (x['seg'], str(x['date'])))]
    r = table(ws, 4, ['证据ID', '下游', '大类', '指标', '数值', '单位', '数据日期', '时段', '口径',
                      '来源机构', '等级', '原文链接'],
              rows, widths=[9, 14, 8, 34, 11, 10, 12, 18, 40, 18, 7, 34], numfmt={5: '#,##0.00'})
    if rows and r > 4:
        ws.conditional_formatting.add('K5:K%d' % r, CellIsRule(operator='equal', formula=['"A"'],
                                     fill=PatternFill('solid', fgColor='D6F5E6')))
    if rows and r > 4:
        ws.conditional_formatting.add('K5:K%d' % r, CellIsRule(operator='equal', formula=['"C"'],
                                     fill=PatternFill('solid', fgColor='FDE8E4')))
    ws.auto_filter.ref = 'A4:L%d' % r

    # 03 分级
    ws = sheet('03_代理指标分级', BLUE)
    header_block(ws, '三、代理指标分级：什么能代表需求', '同一指标在不同品种可能等级不同，需按品种重判。', 7)
    r = table(ws, 4, ['指标', '等级', '类型', '为什么可用', '局限 / 误用风险', '频率', '来源'],
              [[p.get('ind'), p.get('grade'), p.get('type'), p.get('why'), p.get('limit'),
                p.get('freq'), p.get('src')] for p in doc.get('proxy', [])],
              widths=[26, 8, 26, 44, 56, 10, 20])
    if rows and r > 4:
        ws.conditional_formatting.add('B5:B%d' % r, CellIsRule(operator='equal', formula=['"A"'],
                                     fill=PatternFill('solid', fgColor='D6F5E6')))

    # 04 历史比较
    ws = sheet('04_历史比较')
    header_block(ws, '四、历史比较：区间初值 → 末值', '只在同一指标、同一口径的相邻两期之间计算变化。', 8)
    rows = []
    for grp, items in (doc.get('derived') or {}).items():
        if grp == 'transmission' or not isinstance(items, dict):
            continue
        for name, st in items.items():
            if not isinstance(st, dict) or 'span' not in st:
                continue
            sp = st['span']
            rows.append([grp, name, sp['from'], sp['v0'], sp['to'], sp['v1'],
                         sp['chg'], sp['chg_pct'], st.get('min'), st.get('max')])
    r = table(ws, 4, ['分组', '指标', '初值日期', '初值', '末值日期', '末值', '变化量', '变化率(%)', '区间最低', '区间最高'],
              rows, widths=[14, 30, 13, 12, 13, 12, 11, 11, 11, 11],
              numfmt={4: '#,##0.00', 6: '#,##0.00', 7: '#,##0.00', 8: '0.00'})
    if rows and r > 4:
        ws.conditional_formatting.add('H5:H%d' % r,
                                      CellIsRule(operator='lessThan', formula=['0'], font=Font(color='26B57E')))

    # 05 打分
    ws = sheet('05_景气打分', GOLD)
    header_block(ws, '五、下游景气打分与加权传导',
                 '打分 -2…+2；分项指数=下游内部加权；传导指数=Σ(分项×占比)。不是消费量增速。', 5)
    sent = doc.get('derived', {}).get('sentiment') or doc.get('sentiment') or []
    r = table(ws, 4, ['下游', '指标', '打分', '依据', '证据'],
              [[segname.get(x['seg'], x['seg']), x['indicator'], x['score'], x['basis'], ' / '.join(x.get('ev', []))]
               for x in sent], widths=[14, 26, 8, 70, 22])
    if rows and r > 4:
        ws.conditional_formatting.add('C5:C%d' % r,
                                      CellIsRule(operator='lessThan', formula=['0'],
                                                 fill=PatternFill('solid', fgColor='FDE8E4')))
    T = doc.get('derived', {}).get('transmission', {})
    if T:
        r += 2
        r = table(ws, r, ['分项', '景气指数', '消费占比(%)', '贡献', '说明'],
                  [[segname.get(k, k), v, T.get('weights_domestic', {}).get(k, ''),
                    T.get('contribution', {}).get(k, ''), ''] for k, v in T.get('seg_index', {}).items()]
                  + [['加权传导指数', T.get('weighted_total'), 100, T.get('weighted_total'), T.get('explain', '')]],
                  widths=[18, 16, 14, 16, 70], numfmt={2: '0.000', 4: '0.000'}, freeze=False)

    # 06 传导
    ws = sheet('06_传导链条')
    header_block(ws, '六、需求传导链条', '强度“弱”表示该跳不能作为需求判断依据。', 6)
    table(ws, 4, ['上游指标', '下游指标', '传导机制', '滞后', '强度', '可用证据'],
          [[x.get('from'), x.get('to'), x.get('chan'), x.get('lag'), x.get('strength'), x.get('evidence')]
           for x in doc.get('transmission', [])], widths=[24, 24, 40, 14, 18, 50])

    # 07 政策
    ws = sheet('07_政策与事件')
    header_block(ws, '七、产业政策与可验证事件', '只收录能核到原始公告或权威报道的事件。', 8)
    table(ws, 4, ['日期', '涉及下游', '事件', '内容', '对需求的影响', '证据ID', '可核验性', '链接'],
          [[p.get('date'), p.get('seg'), p.get('title'), p.get('what'), p.get('impact'),
            p.get('ev'), p.get('verify'), p.get('url')] for p in doc.get('policy', [])],
          widths=[14, 14, 32, 50, 50, 9, 24, 44])

    # 08 价格库存
    ws = sheet('08_价格与库存')
    header_block(ws, '八、价格、库存与利润明细序列', '注意单位：玻璃万重箱、纯碱万吨；利润为机构成本模型测算值。', 6)
    rows = []
    for grp, items in (doc.get('derived') or {}).items():
        if grp == 'transmission' or not isinstance(items, dict):
            continue
        for name, st in items.items():
            if not isinstance(st, dict) or 'points' not in st:
                continue
            for p in st['points']:
                rows.append([grp, name, p['date'], p['value'], p.get('mom'), p.get('ev')])
    r = table(ws, 4, ['分组', '指标', '日期', '数值', '环比', '证据ID'],
              rows, widths=[14, 30, 12, 14, 12, 10], numfmt={4: '#,##0.000', 5: '#,##0.000'})
    ws.auto_filter.ref = 'A4:F%d' % r

    # 09 缺口
    ws = sheet('09_缺口清单', 'C0504D')
    header_block(ws, '九、数据缺口与使用边界', '拿不到就写缺口，不用估计值顶替。', 5)
    table(ws, 4, ['#', '缺口', '原因', '补数路径', '对结论的影响'],
          [[i + 1, g.get('item'), g.get('why'), g.get('plan'), g.get('impact')]
           for i, g in enumerate(doc.get('gaps', []))], widths=[5, 34, 46, 40, 46])

    # 10 来源
    ws = sheet('10_来源清单')
    header_block(ws, '十、来源机构与链接', '来源类型决定可信度与口径。', 5)
    src = doc.get('sources', {})
    used = {}
    for e in doc.get('evidence', []):
        used.setdefault(e.get('src'), []).append(e['id'])
    rows = []
    for k, ids in used.items():
        nm = src.get(k, [k, ''])
        urls = sorted({e['url'] for e in doc['evidence'] if e.get('src') == k})
        rows.append([nm[0] if isinstance(nm, list) else nm, nm[1] if isinstance(nm, list) else '',
                     len(ids), ' '.join(ids), '\n'.join(urls)])
    table(ws, 4, ['来源机构', '来源类型', '证据条数', '证据ID', '链接'], rows,
          widths=[30, 26, 10, 46, 70])

    # 11 证据明细
    ws = sheet('11_证据明细')
    header_block(ws, '十一、证据明细（%d 条）' % len(doc.get('evidence', [])),
                 'HTML 与 Excel 使用同一份证据库，编号互通。', 10)
    rows = [[e['id'], segname.get(e['seg'], e['seg']), e.get('metric'), e.get('value'), e.get('unit'),
             e.get('date'), (src.get(e.get('src'), [e.get('src')]) or [''])[0], e.get('grade', 'A'),
             e.get('caliber', ''), e.get('quote', ''), e.get('url')]
            for e in sorted(doc.get('evidence', []), key=lambda x: x['id'])]
    r = table(ws, 4, ['证据ID', '下游', '指标', '数值', '单位', '数据日期', '来源机构', '等级', '口径', '原文摘录', '链接'],
              rows, widths=[9, 14, 32, 12, 10, 12, 18, 7, 36, 70, 40], numfmt={4: '#,##0.00'})
    ws.auto_filter.ref = 'A4:K%d' % r

    # 12 口径规范
    ws = sheet('12_口径规范', '7030A0')
    header_block(ws, '十二、需求指标口径规范（跨品种通用）', '定义单位、统计范围、频率与常见误用。', 6)
    spec = doc.get('caliber_spec') or [
        ['日熔量/日投料量', '万吨/日', '在产产线日熔化量，剔除僵尸产能', '日/周', '混淆在产/有效/实际运行三种口径', '玻璃等'],
        ['开工率', '%', '在产条数/总条数 或 运行产能/名义产能', '周', '条数口径受产线大小影响', '全行业'],
        ['产能利用率', '%', '实际产量/名义产能', '周/月', '分母定义各家不同', '全行业'],
        ['产量', '万吨/万重箱', '统计期实际产出', '周/月', '厚度不同换算系数不同', '全行业'],
        ['表观消费', '万吨', '产量+进口-出口(±库存变化)', '周/月', '不是终端消费；抢出口会扭曲', '全行业'],
        ['企业库存', '万吨/万重箱', '生产企业自有仓库', '周', '下降可能是减产或搬库', '全行业'],
        ['库存天数', '天', '库存量/日均产量或消耗', '周/月', '堵窑/停产时分母失真', '玻璃、纯碱'],
        ['利润', '元/吨', '机构成本模型测算单吨毛利', '周', '非报表利润；亏损到减产有 3-6 月滞后', '全行业'],
        ['订单天数', '天', '加工企业在手订单可支撑天数', '半月', '样本与区域差异大', '玻璃深加工等'],
        ['产销率', '%', '当期销量/当期产量', '日/周', '单日值波动极大，须看周均', '玻璃、水泥'],
        ['原料库存天数(下游)', '天', '下游持有的本产品库存可支撑天数', '周/月', '二次衰减项，常被忽略', '全行业'],
        ['期货价格/基差', '元/吨', '连续合约收盘；基差=现货-期货', '日', '不含税、含换月跳空、反映预期', '全品种'],
        ['物耗系数', '吨/吨', '生产1吨下游产品所耗本产品物量', '静态', '经验值有区间，须注明来源', '全品种'],
    ]
    table(ws, 4, ['指标', '单位', '统计范围', '频率', '常见误用', '适用品种'],
          spec, widths=[22, 20, 46, 10, 50, 22])

    for w in wb.worksheets:
        w.sheet_view.showGridLines = False
        w.sheet_view.zoomScale = 90
    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    wb.save(out)
    print('XLSX ->', out, '(%.1f KB)' % (os.path.getsize(out) / 1024))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('-o', '--out', default='workbook.xlsx')
    a = ap.parse_args()
    build(json.load(open(a.src, encoding='utf-8')), a.out)


if __name__ == '__main__':
    main()
