#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the 15-sheet Excel workbook from a case's src/*.json.

Usage:
    python build_xlsx.py <case_dir> [-o out.xlsx]

All values come from JSON — no numbers are typed here, so the workbook can never
drift from the HTML dashboard.
"""
import argparse
import json
import os
import sys

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    print('需要 openpyxl：pip install openpyxl')
    sys.exit(2)

NAVY, BLUE = '1F3864', '2E5C8A'
CONF_FILL = {'C1': 'D9EAD3', 'C2': 'FFF2CC', 'C3': 'FCE5CD', 'C4': 'F4CCCC'}
LEVEL_FILL = {'full': 'D9EAD3', 'partial': 'FFF2CC',
              'summary_only': 'FCE5CD', 'title_only': 'F4CCCC'}
THIN = Side(style='thin', color='D0D7E2')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


class Case:
    def __init__(self, d):
        self.dir = d
        s = os.path.join(d, 'src')

        def j(n):
            with open(os.path.join(s, n), encoding='utf-8') as f:
                return json.load(f)

        self.sources_doc = j('sources.json')
        self.sources = self.sources_doc.get('sources', [])
        self.meta = self.sources_doc.get('meta', {})
        self.limitations = self.sources_doc.get('limitations', [])
        self.news = j('news.json').get('items', [])
        self.events_doc = j('events.json')
        self.events = self.events_doc.get('events', [])
        self.ent = j('entities.json')
        self.chain = j('chain.json')
        self.dedupe = j('dedupe.json')
        self.questions = j('toverify.json').get('questions', [])

        self.src_by = {x['src_id']: x for x in self.sources}
        self.news_by = {x['news_id']: x for x in self.news}
        self.ent_by = {x['ent_id']: x for x in self.ent.get('companies', [])}
        self.plant_by = {x['plant_id']: x for x in self.ent.get('plants', [])}
        self.node_by = {x['node_id']: x for x in self.chain.get('nodes', [])}


def sheet(wb, title, widths, header, rows, freeze='A3', note=None, zebra=True, heights=None):
    ws = wb.create_sheet(title)
    ncol = max(len(header), 1)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=note or title)
    c.font = Font(size=10, color='5B6B80', italic=True)
    c.alignment = Alignment(vertical='center', wrap_text=False)
    ws.row_dimensions[1].height = 22

    for i, h in enumerate(header, 1):
        cell = ws.cell(row=2, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF', size=10)
        cell.fill = PatternFill('solid', fgColor=NAVY)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[2].height = 30

    for r, row in enumerate(rows, 3):
        for i, v in enumerate(row, 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.font = Font(size=10)
            cell.alignment = Alignment(vertical='top', wrap_text=True)
            cell.border = BORDER
            if zebra and r % 2 == 0:
                cell.fill = PatternFill('solid', fgColor='F7F9FC')

    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    if heights:
        for r, h in heights.items():
            ws.row_dimensions[r].height = h
    ws.freeze_panes = freeze
    if rows:
        ws.auto_filter.ref = f'A2:{get_column_letter(ncol)}{2 + len(rows)}'
    return ws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('case_dir')
    ap.add_argument('-o', '--out', default=None)
    a = ap.parse_args()

    C = Case(a.case_dir)
    out = a.out or os.path.join(C.dir, 'out',
                                f"产业资讯事件定位_{C.meta.get('case_id', 'case')}.xlsx")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    wb = Workbook()
    wb.remove(wb.active)

    # 00 overview
    rows = [
        ['case_id', C.meta.get('case_id', '')],
        ['品种', C.meta.get('product', '')],
        ['范围', C.meta.get('scope', '')],
        ['采集窗口', C.meta.get('window_label', '')],
        ['采集时点', C.meta.get('collect_time', '')],
        ['窗口选择理由', C.meta.get('window_selection_rationale', '')],
        ['', ''],
        ['信息源数', len(C.sources)],
        ['资讯条目数', len(C.news)],
        ['去重后事件数', len(C.events)],
        ['关联企业数', len(C.ent.get('companies', []))],
        ['装置数', len(C.ent.get('plants', []))],
        ['产业链节点数', len(C.chain.get('nodes', []))],
        ['待验证事项数', len(C.questions)],
        ['', ''],
    ]
    for c in ('C1', 'C2', 'C3', 'C4'):
        rows.append([f'事件确认度 {c}', sum(1 for e in C.events if e.get('verify_status') == c)])
    rows.append(['', ''])
    for lv in ('full', 'partial', 'summary_only', 'title_only'):
        rows.append([f'资讯内容深度 {lv}', sum(1 for n in C.news if n.get('content_level') == lv)])
    rows.append(['', ''])
    rows.append(['重要口径说明', '本表只做资讯聚合与事件定位，不提供价格涨跌结论；价格数字仅作事件背景并标注来源与日期。'])
    rows.append(['重要口径说明', '读不到正文的条目以“仅标题/摘要”标注，不推断内容；不访问即不判断存在与否。'])
    ws = sheet(wb, '00_案例概览', [22, 96], ['项目', '内容'],
               rows, note='案例概览 — 数据全部由 src/*.json 生成')
    for r in (2, 3, 4, 5, 6):
        ws.cell(row=r, column=1).font = Font(bold=True, size=10)

    # 01 sources
    sheet(wb, '01_信息源', [8, 30, 14, 6, 30, 10, 54, 6, 36, 10, 26, 34],
          ['源编号', '信息源', '类型', '层级', '站点', '可访问性', '访问限制说明',
           '窗口内条数', '价值', '可靠性', '栏目页', '工程注意'],
          [[s.get('src_id'), s.get('name'), s.get('type'), s.get('tier'), s.get('site'),
            s.get('access'), s.get('access_note'), s.get('in_window_items'),
            s.get('value'), s.get('reliability'),
            s.get('list_url') or '（无固定栏目页）', s.get('note')] for s in C.sources],
          note='信息源分层与访问限制 — 受限必须写具体现象，不得写“无法访问”')

    # 02 news
    def news_row(n):
        pts = '\n'.join('· ' + p for p in (n.get('core_points') or []))
        return [n.get('news_id'), n.get('src_id'), n.get('publisher'), n.get('title'),
                n.get('first_pub') or '（未取得）', n.get('first_pub_note'),
                n.get('list_ts'), n.get('repub_time'), n.get('content_level'),
                pts, n.get('event_hint') or '（未归入事件）',
                '是' if n.get('outside_window') else '',
                n.get('reliability_flag'), n.get('url'), n.get('note')]
    ws = sheet(wb, '02_原始资讯', [8, 7, 22, 60, 20, 40, 20, 20, 12, 78, 24, 7, 34, 60, 34],
               ['资讯编号', '源编号', '发布方', '标题', '首发时间', '时间说明', '列表时戳',
                '转载时间', '内容深度', '正文要点', '归属事件', '超窗', '可靠性提示', '链接', '备注'],
               [news_row(n) for n in C.news],
               note='原始资讯条目 — 首发时间与时间说明二选一必填；内容深度决定该条能支撑多强的结论')
    for r, n in enumerate(C.news, 3):
        f = LEVEL_FILL.get(n.get('content_level'))
        if f:
            ws.cell(row=r, column=9).fill = PatternFill('solid', fgColor=f)
    # put 链接 at H and 内容深度 at I per header order
    for r, n in enumerate(C.news, 3):
        cell = ws.cell(row=r, column=14)
        if isinstance(cell.value, str) and cell.value.startswith('http'):
            cell.hyperlink = cell.value
            cell.font = Font(size=10, color='1F4E79', underline='single')

    # 03 events
    def ev_row(e):
        node = C.node_by.get(e.get('chain_node') or '', {})
        return [e.get('event_id'), e.get('title'), e.get('type'), e.get('sub_type'),
                e.get('occur_date'), e.get('occur_date_note'),
                e.get('first_report'), e.get('last_update'),
                e.get('region'), e.get('province'), e.get('product'),
                f"{node.get('layer','')}→{node.get('name','')}" if node else '',
                '、'.join(C.ent_by[x]['short'] for x in e.get('companies', []) if x in C.ent_by),
                '、'.join(C.plant_by[x]['name'] for x in e.get('plants', []) if x in C.plant_by),
                e.get('capacity_desc'), e.get('scale_desc'),
                len(e.get('news_refs') or []), e.get('verify_status'),
                e.get('impact_hint')]
    ws = sheet(wb, '03_事件唯一编号', [22, 54, 12, 20, 12, 54, 20, 20, 20, 8, 24, 34, 34, 40, 44, 60, 8, 8, 40],
               ['事件编号', '事件标题', '类型', '细分类型', '发生日', '日期判定依据',
                '首发报道', '最后更新', '区域', '省', '产品', '产业链节点',
                '涉及企业', '涉及装置', '产能描述', '客观规模描述', '来源数', '确认度', '影响权重说明'],
               [ev_row(e) for e in C.events],
               note='事件唯一编号 — 一个事件一个编号；同一事件的多次报道在此合并，来源保留在 04 表')
    for r, e in enumerate(C.events, 3):
        f = CONF_FILL.get(e.get('verify_status'))
        if f:
            ws.cell(row=r, column=18).fill = PatternFill('solid', fgColor=f)

    # 04 dedupe
    sheet(wb, '04_去重关系', [22, 10, 22, 10, 12, 56, 34, 40],
          ['事件编号', '资讯编号', '关系', '发布方', '内容深度', '判定依据（可审计）', '对确认度的作用', '资讯标题'],
          [[l.get('event_id'), l.get('news_id'), l.get('relation'),
            C.news_by.get(l.get('news_id'), {}).get('publisher', ''),
            C.news_by.get(l.get('news_id'), {}).get('content_level', ''),
            l.get('basis'), l.get('conf_weight'),
            C.news_by.get(l.get('news_id'), {}).get('title', '')]
           for l in C.dedupe.get('links', [])],
          note='去重关系 — republish（同源转载）不增加确认度；conflict（冲突）并置保留，不做仲裁')

    # 05 unassigned
    sheet(wb, '05_未归入事件台账', [10, 62, 12, 66, 22],
          ['资讯编号', '资讯标题', '内容深度', '为什么不立事件（判定理由）', '关联事件（若有）'],
          [[u.get('news_id'), C.news_by.get(u.get('news_id'), {}).get('title', ''),
            C.news_by.get(u.get('news_id'), {}).get('content_level', ''),
            u.get('reason'), u.get('event_id') or '']
           for u in C.dedupe.get('unassigned', [])] or [['—', '本窗口全部资讯均已归入事件', '—', '—', '—']],
          note='未归入事件台账 — 不能让资讯静默丢失；每条须写明理由')

    # 06 entities
    rows = []
    for c in C.ent.get('companies', []):
        plants = [p for p in C.ent.get('plants', []) if p.get('ent_id') == c.get('ent_id')]
        for p in plants or [{}]:
            rows.append([c.get('ent_id'), c.get('name'), c.get('short'), c.get('group'),
                         c.get('province'), c.get('city'), c.get('region'), c.get('route'),
                         c.get('own_methanol'), c.get('role'), c.get('listed'),
                         p.get('plant_id', ''), p.get('name', ''),
                         p.get('capacity') if p.get('capacity') is not None else '未取得',
                         p.get('unit', ''), p.get('status', ''),
                         p.get('status_since') or '未取得', p.get('status_source', ''),
                         p.get('capacity_source', ''), p.get('note', '')])
    sheet(wb, '06_企业装置匹配', [12, 30, 14, 16, 8, 10, 8, 24, 14, 20, 18, 12, 30, 10, 18, 14, 12, 30, 30, 30],
          ['企业编号', '企业全称', '简称', '所属集团', '省', '市', '区域', '工艺路线',
           '是否自有甲醇', '产业角色', '证券代码', '装置编号', '装置名称', '产能', '单位',
           '装置状态', '状态起始日', '状态来源', '产能来源', '备注'],
          rows, note='企业装置匹配 — 产能为“未取得”时留空而非填 0；区分窗口内新发生与存量状态')

    # 07 verify status
    sheet(wb, '07_事实确认状态', [22, 44, 8, 58, 60, 60, 60],
          ['事件编号', '事件标题', '确认度', '判定依据', '已确认事实', '有数据支持的客观描述', '尚未确认的信息'],
          [[e.get('event_id'), e.get('title'), e.get('verify_status'), e.get('verify_basis'),
            '\n'.join('· ' + x for x in e.get('confirmed_facts') or []),
            '\n'.join('· ' + x for x in e.get('data_supported') or []),
            '\n'.join('· ' + x for x in e.get('unconfirmed') or [])]
           for e in C.events],
          note='事实确认状态 — 三层信息严格分开：已确认 / 有数据支持 / 未确认')
    for r, e in enumerate(C.events, 3):
        f = CONF_FILL.get(e.get('verify_status'))
        if f:
            ws.cell(row=r, column=3).fill = PatternFill('solid', fgColor=f)

    # 08 chain nodes
    sheet(wb, '08_产业链节点', [16, 40, 14, 24, 22, 34, 56, 24],
          ['节点编号', '节点名称', '所在层', '对应产品', '区域', '规模提示', '节点说明', '对应数据指标'],
          [[n.get('node_id'), n.get('name'), n.get('layer'), n.get('product'), n.get('region'),
            n.get('capacity_note') or '—', n.get('desc'), n.get('data_ref')]
           for n in C.chain.get('nodes', [])],
          note='产业链节点 — 事件须能挂到节点，才能回答“这条新闻在产业链哪一段”')

    # 09 chain edges
    sheet(wb, '09_产业链连接', [16, 40, 16, 40, 30],
          ['起点编号', '起点名称', '终点编号', '终点名称', '关系'],
          [[e.get('from'), C.node_by.get(e.get('from'), {}).get('name', ''),
            e.get('to'), C.node_by.get(e.get('to'), {}).get('name', ''), e.get('label')]
           for e in C.chain.get('edges', [])],
          note='产业链连接 — 节点间的物流/加工关系')

    # 10 indicators
    sheet(wb, '10_跟踪指标', [16, 40, 8, 30, 30, 24, 56],
          ['节点编号', '指标名称', '频率', '最新值', '上期值', '来源', '链接'],
          [[i.get('node_id'), i.get('name'), i.get('freq'), i.get('latest'), i.get('prev'),
            i.get('source'), i.get('link')] for i in C.chain.get('indicators', [])],
          note='跟踪指标 — 事件的定量背景；仅为背景，不构成价格判断')

    # 11 to verify
    ws = sheet(wb, '11_待验证事项', [8, 22, 52, 50, 50, 54, 14, 8, 40],
               ['编号', '关联事件', '待验证问题', '为什么重要', '需要什么证据', '去哪里取（可执行）',
                '当前状态', '优先级', '当前卡点'],
               [[q.get('q_id'), q.get('event_id'), q.get('question'), q.get('why_matters'),
                 q.get('evidence_needed'), q.get('where_to_get'), q.get('status'),
                 q.get('priority'), q.get('blocked_by')] for q in C.questions],
               note='待验证事项 — 必须是可执行的取证路径，不是“继续关注”')

    # 12 access limits
    sheet(wb, '12_访问限制日志', [8, 30, 12, 66, 44],
          ['源编号', '信息源', '可访问性', '具体限制现象', '对本案的影响'],
          [[s.get('src_id'), s.get('name'), s.get('access'), s.get('access_note'),
            s.get('note')] for s in C.sources if s.get('access') != '可读'] or
          [['—', '本案例所有源均可读', '—', '—', '—']],
          note='访问限制日志 — 受阻≠不存在；不得用“未发现”替代“未能访问”')

    # 13 method
    method = [
        ['硬约束 1', '不要把资讯聚合变成普通新闻摘要'],
        ['硬约束 2', '不要从新闻直接给出价格涨跌结论'],
        ['硬约束 3', '不要把搜索结果的标题当成已核实事实'],
        ['硬约束 4', '付费墙/不可访问来源必须披露为访问限制，不得用“未发现”替代“未能访问”'],
        ['硬约束 5', '不能编造资讯内容或事件'],
        ['硬约束 6', '两个来源冲突时并置保留，不做仲裁'],
        ['', ''],
        ['原理', '资讯条目 ≠ 产业事件。多条报道可能对应同一个事件；一个事件可能有后续更新。'],
        ['确认度 C1', '官方原文可读（政府/交易所/企业公告）'],
        ['确认度 C2', '≥2 家独立机构口径一致且正文可读；同源转载不计数'],
        ['确认度 C3', '单一来源，或仅标题级证据'],
        ['确认度 C4', '待核实，或来源之间存在冲突'],
        ['', ''],
        ['去重关系', 'primary 首发 / republish 转载 / followup 后续更新 / index_entry 索引形态 / selfmedia 自媒体 / conflict 来源冲突'],
        ['三层事实', '① 已确认事实 ② 有数据支持的客观描述 ③ 尚未确认的信息'],
        ['产能纪律', '产能必须有来源；无来源留空写“未取得”，禁止填估计值'],
    ]
    sheet(wb, '13_方法论与禁止事项', [18, 96], ['条目', '内容'], method,
          note='方法论与禁止事项 — 每份交付物都附带，便于复查口径')

    # 14 collect log
    log = []
    for s in C.sources:
        log.append([s.get('src_id'), s.get('name'), s.get('access'),
                    s.get('access_note') or s.get('note') or '正常可读'])
    global_lim = C.limitations or ['（无）']
    for i, t in enumerate(global_lim, 1):
        log.append([f'G{i:02d}', '全局限制', '—', t])
    sheet(wb, '14_采集与核验日志', [10, 34, 12, 90],
          ['编号', '来源/对象', '结果', '说明（含失败原因与排除项）'], log,
          note='采集与核验日志 — 失败与被排除的内容也要留痕')

    wb.save(out)
    print('saved', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())