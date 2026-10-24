# -*- coding: utf-8 -*-
"""由 model.json 生成 13 表 Excel 工作簿（与 HTML 同源同数）。"""
import argparse
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

INK = '1F2937'
BRAND = '1D4ED8'
HDR_FILL = PatternFill('solid', fgColor='1D4ED8')
HDR_FONT = Font(color='FFFFFF', bold=True, size=10.5, name='微软雅黑')
TITLE_FONT = Font(bold=True, size=14, color=INK, name='微软雅黑')
SUB_FONT = Font(size=9.5, color='64748B', name='微软雅黑')
BODY_FONT = Font(size=10, name='微软雅黑')
BOLD = Font(bold=True, size=10, name='微软雅黑')
THIN = Side(style='thin', color='E2E8F0')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical='top')
CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)
FILL_WARN = PatternFill('solid', fgColor='FEF3E2')
FILL_BAD = PatternFill('solid', fgColor='FDEAEA')
FILL_OK = PatternFill('solid', fgColor='E7F7F1')
FILL_MUTED = PatternFill('solid', fgColor='F1F5F9')


def sheet(wb, name, title, subtitle, headers, rows, widths=None, num_cols=(), heights=None,
          fills=None, freeze='A5'):
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    ws['A1'] = title
    ws['A1'].font = TITLE_FONT
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(len(headers), 2))
    ws['A2'] = subtitle
    ws['A2'].font = SUB_FONT
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(len(headers), 2))
    ws.row_dimensions[1].height = 24
    ws.row_dimensions[2].height = 18
    hr = 4
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=hr, column=j, value=h)
        c.fill = HDR_FILL
        c.font = HDR_FONT
        c.alignment = CENTER
        c.border = BORDER
    ws.row_dimensions[hr].height = 30
    for i, r in enumerate(rows, hr + 1):
        for j, v in enumerate(r, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = BODY_FONT
            c.border = BORDER
            c.alignment = CENTER if j in num_cols else WRAP
            if isinstance(v, (int, float)):
                c.number_format = '#,##0.00' if isinstance(v, float) else '#,##0'
            if fills:
                fv = fills.get(i - hr - 1) if isinstance(fills, dict) else (
                    fills[i - hr - 1] if i - hr - 1 < len(fills) else None)
                if fv:
                    c.fill = fv
        if heights:
            ws.row_dimensions[i].height = heights
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
    if freeze:
        ws.freeze_panes = freeze
    ws.auto_filter.ref = 'A%d:%s%d' % (hr, get_column_letter(len(headers)),
                                       hr + max(len(rows), 1))
    return ws


def build(model_path, out_path):
    m = common.load_json(model_path)
    q, meta = m['quote'], m['meta']
    wb = Workbook()
    wb.remove(wb.active)
    t0 = [x for x in m['targets'] if x['status'] == '可比']
    t0 = t0[0] if t0 else {}
    p1y = [p for p in m['percentiles'] if p['window'] == '1y']
    p1y = p1y[0] if p1y else {}

    def _pctcell(p):
        if p.get('quote_pctile') is None:
            return '缺口'
        return '%.1f%%' % p['quote_pctile']

    # ---------------- 00 封面与结论
    ws = wb.create_sheet('00 封面与结论')
    ws.sheet_view.showGridLines = False
    ws['A1'] = meta['title']
    ws['A1'].font = Font(bold=True, size=20, color=INK, name='微软雅黑')
    ws['A2'] = '报告编号 %s ｜ 数据基准日 %s ｜ 品种族 %s' % (meta['report_id'], meta['asof'], meta.get('product_family'))
    ws['A2'].font = SUB_FONT
    ws['A4'] = '⚠ 使用前必读'
    ws['A4'].font = Font(bold=True, size=12, color='B45309', name='微软雅黑')
    notes = [
        '1. 本工作簿中的供应商报价为【测试输入】（虚构数据，仅演示解析与核验流程），不是真实供应商报价。',
        '2. 市场价格均为可追溯的公开数据，「数据来源」表中逐条列明发布方、标题、日期与链接。',
        '3. 本工作簿只陈述已发生的价格事实与口径差异，不预测未来价格，也不给出应还价金额。',
        '4. 口径不一致（规格/税费/交付/数量/账期）的价格不计算偏离；缺口一律标注，不用行业均值或插值填补。',
    ]
    for i, n in enumerate(notes, 5):
        ws['A%d' % i] = n
        ws['A%d' % i].font = BODY_FONT
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=8)
        ws['A%d' % i].alignment = WRAP
    r = 11
    ws['A%d' % r] = '关键结论'
    ws['A%d' % r].font = Font(bold=True, size=12, color=INK, name='微软雅黑')
    cards = [
        ('供应商报价（测试输入）', '%.0f 元/吨' % q['value'], '%s，%s，%s' % (q['grade_claimed'], q['tax']['text'], q['delivery']['text'])),
        ('市场参考中枢（%s）' % t0.get('target_label', '—'), '%.0f 元/吨' % (t0.get('center') or 0),
         '同日 %s，%s' % (m['primary_anchor']['date'], m['primary_anchor']['source_name'])),
        ('偏离金额 / 比例', '%+.0f 元/吨' % (t0.get('dev_center') or 0), '偏离参考中枢 %+.2f%%' % (t0.get('dev_center_pct') or 0)),
        ('1 年历史分位（指数口径）', _pctcell(p1y),
         ('%s日频 n=%d' % (p1y.get('series_name') or '', p1y['n'])) if p1y.get('n') else
         ('未取得 1 年序列：%s' % (p1y.get('gap') or '缺口'))),
        ('数据缺口', '%d 项' % len(m.get('gaps') or []), '详见「10 数据缺口」'),
        ('待确认口径', '%d 项' % len([c for c in m['comparability'] if c['label'] == '待确认']), '详见「11 待确认问题」'),
    ]
    for i, (lab, val, sub) in enumerate(cards):
        rr = r + 1 + i
        ws.cell(row=rr, column=1, value=lab).font = SUB_FONT
        c = ws.cell(row=rr, column=2, value=val)
        c.font = Font(bold=True, size=15, color='B91C1C' if i in (0, 2) else BRAND, name='微软雅黑')
        ws.cell(row=rr, column=3, value=sub).font = SUB_FONT
        ws.merge_cells(start_row=rr, start_column=3, end_row=rr, end_column=8)
    ws['A19'] = meta.get('disclaimer', '')
    ws['A19'].font = SUB_FONT
    ws.merge_cells('A19:H19')
    ws['A19'].alignment = WRAP
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 18
    for col in 'CDEFGH':
        ws.column_dimensions[col].width = 14

    # ---------------- 01 供应商报价
    unknowns = q.get('unknowns') or []
    rows = [
        ['供应商', q['supplier_label'], '测试输入，非真实供应商'],
        ['供应商性质（自述）', q.get('supplier_type'), ''],
        ['品种', q['product_name'], '别名：' + '、'.join(q.get('product_aliases') or [])],
        ['规格/等级', q['spec_text'], '含量未在报价单载明 → 待确认'],
        ['报价值', q['value'], '单位：%s' % q['unit']],
        ['税费', q['tax']['text'], '增值税率 %.0f%%' % (q['tax']['vat_rate'] * 100)],
        ['交付方式', q['delivery']['text'], '发运地：%s' % q['delivery'].get('origin', '—')],
        ['到货地', q['destination'], ''],
        ['数量', '%s %s' % (q['quantity']['value'], q['quantity']['unit']), q['quantity'].get('basis', '')],
        ['付款方式/账期', q['payment']['terms'], '未做贴息折现'],
        ['包装', q['packing'], ''],
        ['计价公式', q['pricing_formula'], ''],
        ['报价日期', q['quote_date'], ''],
        ['报价有效期', q['validity'], '缺失 → 影响可比性'],
    ]
    for u in unknowns:
        rows.append(['未确认项', u, '需向供应商确认'])
    sheet(wb, '01 供应商报价', '供应商报价原始口径', '所有字段原样留档；「未确认项」进入「11 待确认问题」',
          ['字段', '内容', '备注'], rows, widths=[22, 52, 40])

    # ---------------- 02 报价标准化
    rows = []
    for t in m['targets']:
        rows.append([t['target_label'], t['quote_value'], t['quote_formula'],
                     t.get('quote_gap') or '可直接计算'])
    rows.append(['账期折算价', m['quote_meta'].get('credit_discounted_price'), m['quote_meta'].get('credit_formula'), ''])
    rows.append(['增值税率', m['quote_meta']['vat'], '参数（来自 specs）', '可在规格文件中调整'])
    rows.append(['运价（元/吨）', m['quote_meta'].get('freight'), '未提供', '缺运价导致到厂靶心为空'])
    sheet(wb, '02 报价标准化', '报价标准化为四个可比靶心', '靶心 = 税费口径 × 交付口径；每个靶心都可复算',
          ['靶心 / 参数', '结果（元/吨 或 比例）', '公式', '说明'], rows,
          widths=[22, 20, 56, 40], num_cols=(2,))

    # ---------------- 03 市场价格
    rows = []
    for a in m['anchors']:
        rows.append([a['id'], a['date'], a.get('time', ''), a['source_name'], a['source_title'],
                     a['spec'], a['region'], '含税' if a['tax_included'] else '不含税', a['delivery'],
                     a['value'], a.get('change'), a['price_type'], a.get('tier', ''), a['url'], a.get('note', '')])
    fills3 = []
    for a in m['anchors']:
        fills3.append(FILL_OK if a.get('role') == 'primary' else FILL_MUTED)
    sheet(wb, '03 市场价格', '市场参考价（六项口径齐全才录入）', '绿色＝主锚；灰色＝交叉核验/指数参考。企业挂牌价单列于下一表',
          ['ID', '日期', '时间', '发布方', '原文标题', '规格/等级', '地区', '税费', '交付方式', '价格(元/吨)',
           '涨跌', '价格性质', '层级', '来源 URL', '原文要点'],
          rows, widths=[20, 11, 8, 22, 42, 24, 12, 8, 20, 12, 9, 26, 16, 46, 46],
          num_cols=(10, 11), fills=fills3, heights=44)

    # ---------------- 04 偏离比较
    rows = []
    for t in m['targets']:
        if t['status'] == '可比':
            rows.append([t['target_label'], t['quote_value'], t['low'], t['high'], t['center'],
                         t['dev_center'], t['dev_center_pct'], t['dev_low'], t['dev_high'],
                         t.get('position_label'), '可比', ''])
        else:
            rows.append([t['target_label'], t['quote_value'], None, None, None, None, None, None, None, None,
                         t['status'], t.get('reason') or t.get('quote_gap') or ''])
    ws = sheet(wb, '04 偏离比较', '偏离计算', '偏离金额 = 报价 − 参考中枢；偏离比例 = 偏离金额 ÷ 参考中枢',
               ['口径（靶心）', '供应商报价', '区间下沿', '区间上沿', '参考中枢', '偏离金额', '偏离比例(%)',
                '较下沿差额', '较上沿差额', '区间位置', '状态', '说明'],
               rows, widths=[18, 13, 11, 11, 11, 12, 12, 12, 12, 13, 20, 44], num_cols=(2, 3, 4, 5, 6, 7, 8, 9, 10))
    # 补公式说明（在数据下方）
    r0 = 4 + len(rows) + 2
    t = t0
    if t:
        lines = [
            '偏离金额 = 报价 − 参考中枢 = %.2f − %.2f = %.2f' % (t['quote'], t['center'], t['dev_center']),
            '偏离比例 = 偏离金额 ÷ 参考中枢 = %.2f ÷ %.2f = %.2f%%' % (t['dev_center'], t['center'], t['dev_center_pct']),
        ]
        if t.get('position_in_range') is not None:
            lines.append('区间内位置 = (报价 − 下沿) ÷ (上沿 − 下沿) = (%.2f − %.2f) ÷ (%.2f − %.2f) = %.1f%%'
                         % (t['quote'], t['low'], t['high'], t['low'], t['position_in_range']))
        for i, ln in enumerate(lines):
            c = ws.cell(row=r0 + i, column=1, value=ln)
            c.font = BODY_FONT

    # ---------------- 05 历史分位
    rows = []
    for p in m['percentiles']:
        lab = {'3m': '3 个月', '1y': '1 年', '1y_fut': '1 年（期货）', '3y': '3 年（期货）'}.get(p['window'], p['window'])
        if p.get('ok'):
            rows.append([lab, p.get('series_name'), p.get('freq'), p.get('tax'), p.get('spec'), p.get('region'),
                         p['n'], p['start'], p['end'], p['low'], p['high'], p['median'],
                         p.get('compared_value'), p.get('quote_pctile'), p.get('method'), '已计算'])
        else:
            rows.append([lab, p.get('series_name'), p.get('freq'), p.get('tax'), p.get('spec'), p.get('region'),
                         p.get('n'), None, None, None, None, None, p.get('compared_value'), None,
                         p.get('gap') or '', '缺口'])
    sheet(wb, '05 历史分位', '历史分位（基于有效序列，不用最高最低价推断）',
          'P = (#<X + 0.5×#=X) ÷ N × 100%；期货序列与报价比较时，报价已折算为不含税',
          ['窗口', '序列', '频率', '税费口径', '规格', '地区', '样本数', '起始', '结束', '区间低点',
           '区间高点', '中位数', '比较值', '报价分位(%)', '方法/缺口原因', '状态'],
          rows, widths=[12, 30, 10, 10, 24, 16, 9, 12, 12, 11, 11, 11, 12, 13, 46, 10],
          num_cols=(7, 10, 11, 12, 13, 14))

    # ---------------- 06 价格历史
    rows = []
    for s in m.get('spot_series_3m') or []:
        rows.append(['现货快照', s['date'], s['region'], s['spec'], s['value'], '含税', s['delivery'],
                     s.get('change'), s['source'], s['url']])
    for p in (m.get('history') or {}).get('ppi_1y', []):
        rows.append(['生意社基准价', p['d'], '全国综合', '乙二醇基准（聚酯级综合）', p['v'], '含税', '基准价口径',
                     None, '生意社（100ppi）', 'https://www.100ppi.com/vane/detail-222.html'])
    for p in (m.get('history') or {}).get('fut_1y', []):
        rows.append(['EG0 期货收盘', p['d'], '交割库（盘面）', 'DCE 交割标准品', p['v'], '不含税', '盘面',
                     None, '新浪财经 EG0 日线', 'https://finance.sina.com.cn/futures/quotes/EG0.shtml'])
    sheet(wb, '06 价格历史', '价格历史（逐条可复核）', '每条记录都带来源；期货与现货口径分列，不可混算',
          ['序列类型', '日期', '地区', '规格', '价格(元/吨)', '税费', '交付/口径', '当日涨跌', '来源', 'URL'],
          rows, widths=[16, 12, 16, 24, 12, 8, 18, 10, 24, 50], num_cols=(5, 8))

    # ---------------- 07 事件与行情变化
    rows = [[e['d'], e['title'], e.get('phase', ''), e['fact'], e.get('price_effect', ''), e.get('source', '')]
            for e in m.get('events') or []]
    sheet(wb, '07 事件与行情变化', '近期已经发生的行情变化', '只记录已发生的事实、日期与来源；不含方向判断与预测',
          ['日期', '事件', '价格阶段', '已发生的事实', '对应价格表现', '来源'], rows,
          widths=[16, 34, 16, 70, 34, 34], heights=54)

    # ---------------- 08 口径矩阵
    rows = [[c['item'], c['quote'], c['market'], c['direction'], '可量化' if c['quantifiable'] else '不可量化',
             c['label'], c['evidence']] for c in m['comparability']]
    fills8 = [FILL_OK if r[5] in ('已对齐', '已有依据（方向）') else FILL_WARN if r[5] == '待确认' else FILL_BAD for r in rows]
    sheet(wb, '08 口径矩阵', '口径差异判定矩阵', '结论只有三种：已对齐/有依据、待确认、不可比',
          ['口径项', '供应商报价', '市场参考', '方向', '可量化性', '结论', '依据'], rows,
          widths=[18, 26, 26, 28, 12, 16, 60], fills=fills8, heights=44)

    # ---------------- 09 计算公式
    rows = [
        ['单位换算', '元/kg → 元/吨', '值 × 1000', ''],
        ['含税 → 不含税', '不含税价', '含税价 ÷ (1 + VAT)', 'VAT = %.0f%%' % (m['quote_meta']['vat'] * 100)],
        ['不含税 → 含税', '含税价', '不含税价 × (1 + VAT)', ''],
        ['到厂价', '到厂', '出厂 + 运费', '缺运价时留空，不用均价顶替'],
        ['账期折算', '现款价', '报价 × (1 − 年化资金成本 × 账期天数 ÷ 365)', m['quote_meta'].get('credit_formula', '')],
        ['偏离金额', '元/吨', '报价靶心 − 参考中枢', ''],
        ['偏离比例', '%', '偏离金额 ÷ 参考中枢 × 100%', ''],
        ['区间内位置', '%', '(报价 − 下沿) ÷ (上沿 − 下沿) × 100%', '单点区间不给该值'],
        ['历史分位', '%', '(#<X + 0.5×#=X) ÷ N × 100%', '禁止用最高/最低价推断'],
        ['窗口区间', '元/吨', 'low = min(样本)，high = max(样本)', '同序列同口径'],
        ['报价→期货可比', '不含税', '含税报价 ÷ (1+VAT)', '仅用于同屏位置比较，不作价差结论'],
        ['年度锚点对比', '差额', '报价 − 锚点值', '锚点≠序列，不出分位'],
    ]
    sheet(wb, '09 计算公式', '计算公式与参数', '每个数字都能按本表复算；参数集中在 specs 规格文件',
          ['项目', '输出', '公式', '参数/说明'], rows, widths=[20, 14, 58, 56])

    # ---------------- 10 数据缺口
    rows = [[g['id'], g['item'], g['impact'], g['tried'], g['why'], g['next']] for g in m.get('gaps') or []]
    sheet(wb, '10 数据缺口', '数据缺口清单', '缺口本身就是结论：写清缺什么、试过什么、为什么补不上、下一步怎么补',
          ['编号', '缺口项', '对报告的影响', '已尝试渠道', '为什么缺', '补数路径'], rows,
          widths=[8, 34, 34, 50, 30, 40], heights=48, fills=[FILL_WARN] * len(rows))

    # ---------------- 11 待确认问题
    pend = (m.get('evidence_summary') or {}).get('pending') or []
    rows = []
    for i, p in enumerate(pend, 1):
        rows.append([i, p, '供应商', '高' if i <= 3 else '中', '未答复前，该差异不视为已解释'])
    for c in m['comparability']:
        if c['label'] == '待确认':
            rows.append([len(rows) + 1, '请确认：%s（现状：%s；市场参考：%s）' % (c['item'], c['quote'], c['market']),
                         '供应商/采购', '中', c['evidence']])
    sheet(wb, '11 待确认问题', '待确认问题清单（可直接发给供应商）', '按优先级排序；答复后应在此表登记结论与依据',
          ['序号', '要确认的问题（建议原话）', '问谁', '优先级', '备注'], rows,
          widths=[7, 78, 12, 9, 46], num_cols=(1,), heights=40)

    # ---------------- 12 来源清单
    rows = []
    for a in m['anchors']:
        rows.append([a['source_name'], a['source_title'], a['date'], a.get('time', ''), a['url'],
                     a.get('note', ''), '市场价格'])
    for e in m.get('enterprise_prices') or []:
        rows.append([e['party'], '%s 挂牌/结算价' % e['month'], '', '', '', e.get('note', ''), '企业定价'])
    for e in m.get('events') or []:
        rows.append(['（见事件来源）', e['title'], e['d'], '', '', e.get('source', ''), '事件事实'])
    sheet(wb, '12 来源清单', '数据来源清单', '每条结论都能回溯到以下任一来源',
          ['发布方', '标题/内容', '日期', '时间', 'URL', '要点', '类别'], rows,
          widths=[24, 46, 12, 8, 50, 50, 12], heights=40)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    wb.save(out_path)
    return out_path


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('model')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    p = build(a.model, a.out)
    print('OK -> %s (%.1f KB)' % (p, os.path.getsize(p) / 1024))
