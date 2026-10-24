# -*- coding: utf-8 -*-
"""生成供给事件台账 Excel 工作簿（多 Sheet，含公式与来源）。

Sheet 结构：
 00_说明            口径、公式、限制声明
 01_装置档案        装置主数据（unit_id 唯一）
 02_事件清单_已发生  已发生事件（含理论影响量、去重、来源）
 03_事件清单_未来    已披露未发生事项（严格分开）
 04_影响量计算       逐事件公式与参数（可审计）
 05_汇总_按企业
 06_汇总_按地区
 07_汇总_按事件类型
 08_汇总_按工艺路线
 09_事件时间线       甘特式起止（便于透视）
 10_来源与证据链     每条事件的来源链接与原文引用
 11_数据缺口与冲突   未知时间/未知负荷/口径冲突清单
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calc_impact as ci

try:
    import xlsxwriter
except ImportError:  # pragma: no cover
    xlsxwriter = None

FMT = {
    'title':  {'bold': True, 'font_size': 15, 'font_color': '#0F2E4C'},
    'h2':     {'bold': True, 'font_size': 11, 'font_color': '#1A5C8A'},
    'head':   {'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#1F4E79',
               'border': 1, 'border_color': '#9EB6CE', 'align': 'center',
               'valign': 'vcenter', 'text_wrap': True},
    'cell':   {'border': 1, 'border_color': '#D6E0EA', 'valign': 'top'},
    'wrap':   {'border': 1, 'border_color': '#D6E0EA', 'valign': 'top', 'text_wrap': True},
    'num':    {'border': 1, 'border_color': '#D6E0EA', 'num_format': '#,##0.0', 'valign': 'top'},
    'int':    {'border': 1, 'border_color': '#D6E0EA', 'num_format': '#,##0', 'valign': 'top'},
    'date':   {'border': 1, 'border_color': '#D6E0EA', 'num_format': 'yyyy-mm-dd', 'valign': 'top', 'align': 'center'},
    'pct':    {'border': 1, 'border_color': '#D6E0EA', 'num_format': '0.0%', 'valign': 'top'},
    'warn':   {'border': 1, 'border_color': '#E8B4B8', 'bg_color': '#FDEEEE', 'valign': 'top', 'text_wrap': True},
    'ok':     {'border': 1, 'border_color': '#B7D7B0', 'bg_color': '#EFF8ED', 'valign': 'top'},
    'oversea':{'border': 1, 'border_color': '#C9C2E8', 'bg_color': '#F2F0FB', 'valign': 'top'},
    'stock':  {'border': 1, 'border_color': '#D9D9D9', 'bg_color': '#F5F5F5', 'valign': 'top'},
}

BUCKET_FMT = {
    'domestic_confirmed': 'ok',
    'overseas': 'oversea',
    'unconfirmed': 'warn',
    'stock_stop': 'stock',
    'status_only': 'cell',
    'new_capacity': 'ok',
}

BUCKET_CN = {
    'domestic_confirmed': '国内·已确认',
    'overseas': '境外（不影响国产供给）',
    'unconfirmed': '未确认/待核（不计入）',
    'stock_stop': '存量停车（非窗口内边际）',
    'status_only': '状态确认（无产量影响）',
    'new_capacity': '新增产能',
}


def load_case(case_dir):
    def j(f):
        return json.load(open(os.path.join(case_dir, f), encoding='utf-8'))
    units_doc = j('units.json')
    return {
        'meta': j('datum.json')['meta'],
        'companies': j('companies.json')['companies'],
        'regions': j('companies.json')['regions'],
        'units': units_doc['units'],
        'events': j('status_events.json')['events'],
        'planned': j('planned_events.json')['planned_events'],
    }


def col_widths_from(header, rows, minw=10, maxw=46):
    out = []
    for i, h in enumerate(header):
        w = max([len(str(h)) * 2] + [len(str(r[i])) * 1.15 for r in rows if i < len(r) and r[i] is not None] or [minw])
        out.append(min(max(w, minw), maxw))
    return out


def build(case_dir, out_path, asset_eval=None):
    if xlsxwriter is None:
        raise SystemExit('需要 xlsxwriter')
    D = load_case(case_dir)
    meta = D['meta']
    ws_, we_ = ci.parse_date(meta['window_start']), ci.parse_date(meta['window_end'])
    S = ci.summarize(D['events'], ws_, we_, meta['national_capacity_wt'], meta['weekly_output_t'])
    rows = S['rows']

    wb = xlsxwriter.Workbook(out_path, {'nan_inf_to_errors': True})
    F = {k: wb.add_format(v) for k, v in FMT.items()}

    # ---------- 00 说明 ----------
    sh = wb.add_worksheet('00_说明')
    sh.set_column('A:A', 24); sh.set_column('B:B', 108)
    sh.write('A1', f"【看供给端最近发生了什么】{meta['product']} 供给事件台账", F['title'])
    sh.write('A2', f"统计窗口 {meta['window_start']} ~ {meta['window_end']}　基准日 {meta['as_of']}　单位：万吨/年、吨", F['h2'])
    lines = [
        ('本工作簿回答什么', '最近3个月国内甲醇生产装置发生了哪些停车/检修/复产/降负荷/投产事件；每件事影响多少产量；哪些还不确定。不输出供应预警与价格结论。'),
        ('数据可信度分级', 'official=企业公告/政府批文/交易所公告；industry=专业机构资讯（隆众、金联创、生意社、甲醇时代、化销网等）；rumor=未确认传闻，仅登记不计入确认影响量。'),
        ('影响量公式（停车/检修/故障）', 'L = 产能/365 × 窗口内停留天数 × (基准负荷 - 事件期负荷)；停车时事件期负荷=0，减产量系数=1。'),
        ('影响量公式（降负荷）', 'L = 产能/365 × 天数 × (基准负荷 - 实际负荷)。只有来源给出负荷数值（如45%）时才计入确认口径；仅写“低负荷”者按假设值计算并排除出确认口径。'),
        ('影响量公式（新增产能）', 'A = 产能/365 × 窗口内运行天数 × 爬坡负荷；与检修损失分列，绝不相互抵销。'),
        ('窗口裁剪规则', '跨窗口事件只计窗口内天数（含首尾）。存量停车（窗口前已停）单独标记，不计入窗口内边际变化。'),
        ('国产与境外分列', '境外装置（伊朗、马来、文莱等）只影响进口/到港，绝不并入国产供给合计。'),
        ('去重规则', '同一 unit_id + 同一事件家族 + 时间重叠 = 同一事件，合并并保留全部来源；source_count>=2 视为多源印证。'),
        ('无法计算的情形', '缺少停车起始日、缺少负荷数值、仅“传闻”来源、装置已长期停车/部分拆除 → 一律不进入确认影响量，并在“11_数据缺口与冲突”列示。'),
        ('关键局限', '①多数事件起止为“推定值”（依据“为期N天”倒推），误差±3~7天；②部分装置产能存在两种公开口径；③周产量/总产能分母为行业公开口径，用于量级参照而非精确核算。'),
    ]
    r = 3
    for k, v in lines:
        sh.write(r, 0, k, F['h2']); sh.write(r, 1, v, F['wrap']); r += 1
    r += 1
    sh.write(r, 0, '核心结果（国内口径）', F['h2']); r += 1
    kpi = [
        ('国内确认减产合计（万吨）', S['domestic_loss_wt']),
        ('占窗口内国内理论产能比例', f"{S['domestic_loss_pct_window_capacity']}%"),
        ('折合周产量倍数', f"{S['domestic_loss_weeks']} 周"),
        ('境外装置影响（万吨，仅进口端）', S['overseas_loss_wt']),
        ('未确认/待核（万吨，不计入）', S['unconfirmed_loss_wt']),
        ('窗口内新增产能贡献（万吨）', S['new_capacity_wt']),
        ('已确认事件数 / 境外 / 未确认', f"{S['totals']['n_domestic_confirmed']} / {S['totals']['n_overseas']} / {S['totals']['n_unconfirmed']}"),
    ]
    for k, v in kpi:
        sh.write(r, 0, k, F['cell']); sh.write(r, 1, v, F['cell']); r += 1

    # ---------- 01 装置档案 ----------
    sh = wb.add_worksheet('01_装置档案')
    hdr = ['unit_id', '企业ID', '企业', '生产基地', '省份', '大区', '装置名称', '产品', '产能(万吨/年)',
           '工艺路线', '基准状态', '产能口径说明', '消歧要点']
    sh.write_row(0, 0, hdr, F['head'])
    reg = {x['code']: x['name'] for x in D['regions']}
    route_cn = {'COAL': '煤制', 'NG': '天然气制', 'COKE_OVEN': '焦炉气制', 'CO2H2': '二氧化碳加氢制',
                'FURNACE_GAS': '矿热炉尾气制', 'UNKNOWN': '未披露'}
    body = []
    for u in D['units']:
        body.append([u['unit_id'], u['company_id'], u['company'], u['site'], u['province'],
                     reg.get(u['region_code'], u['region_code']), u['unit_name'], u['product'],
                     u['capacity_wt'], route_cn.get(u['route'], u['route']), u['status_base'],
                     u.get('capacity_note', ''), u.get('disambig', '')])
    for i, row in enumerate(body, start=1):
        for c, v in enumerate(row):
            f = F['int'] if c == 8 else F['wrap']
            sh.write(i, c, v, f)
    for i, w in enumerate(col_widths_from(hdr, body, maxw=40), start=0):
        sh.set_column(i, i, w)
    sh.freeze_panes(1, 0)
    sh.autofilter(0, 0, len(body), len(hdr) - 1)

    # ---------- 02 事件清单_已发生 ----------
    sh = wb.add_worksheet('02_事件清单_已发生')
    hdr = ['event_id', '归类', '事件类型', '企业', '生产基地', '装置', '省份', '大区', '工艺',
           '产能(万吨/年)', '起始日', '结束日', '窗口内天数', '事件期负荷', '减产量(吨)',
           '最新状态', '状态说明', '置信度', '来源数', '事件家族(去重键)']
    sh.write_row(0, 0, hdr, F['head'])
    body = []
    evmap = {e['event_id']: e for e in D['events']}
    for r0 in rows:
        e = evmap[r0['event_id']]
        dl = r0.get('downtime_load')
        body.append([r0['event_id'], BUCKET_CN.get(r0['bucket'], r0['bucket']), r0['event_type'],
                     r0['company'], e.get('site', ''), r0['unit_name'], r0['province'],
                     reg.get(r0['region_code'], r0['region_code']),
                     route_cn.get(r0['route'], r0['route']), r0['capacity_wt'],
                     r0['start_date'], r0['end_date'] or '', r0.get('days'),
                     dl if dl is not None else 'n/a',
                     r0.get('loss_t') if r0.get('loss_t') is not None else '不计',
                     r0['status_latest'], e.get('status_note', ''), r0['confidence'],
                     r0['source_count'], e.get('event_family', '')])
    for i, row in enumerate(body, start=1):
        bf = BUCKET_FMT.get(rows[i - 1]['bucket'], 'cell')
        for c, v in enumerate(row):
            if c == 9:
                f = wb.add_format({**FMT[bf], 'num_format': '#,##0'})
                sh.write(i, c, v, f)
            elif c == 14:
                f = wb.add_format({**FMT[bf], 'num_format': '#,##0'})
                sh.write(i, c, v, f)
            elif c in (10, 11):
                if v in ('', None):
                    sh.write(i, c, '', F[bf])
                else:
                    sh.write_datetime(i, c, ci.parse_date(v),
                                      wb.add_format({**FMT[bf], 'num_format': 'yyyy-mm-dd'}))
            elif c == 12:
                sh.write(i, c, v if v is not None else '', F[bf])
            else:
                sh.write(i, c, v, F[bf])
    for i, w in enumerate(col_widths_from(hdr, body, maxw=38)):
        sh.set_column(i, i, w)
    sh.freeze_panes(1, 3)
    sh.autofilter(0, 0, len(body), len(hdr) - 1)

    # ---------- 03 事件清单_未来 ----------
    sh = wb.add_worksheet('03_事件清单_未来已披露')
    hdr = ['plan_id', '类型', '企业', '装置', '省份', '产能(万吨/年)', '计划时点', '计划区间',
           '披露方式', '状态', '当前说明', '潜在供给影响(万吨/年)', '置信度', '来源数']
    sh.write_row(0, 0, hdr, F['head'])
    body = []
    for p in D['planned']:
        body.append([p['plan_id'], p['event_type'], p['company'], p['unit_name'], p['province'],
                     p['capacity_wt'], p['planned_date'], p.get('planned_window', ''),
                     p.get('disclosure_type', ''), p.get('status', ''), p.get('status_note', ''),
                     p.get('potential_supply_wt'), p.get('confidence'), p.get('source_count')])
    for i, row in enumerate(body, start=1):
        for c, v in enumerate(row):
            f = F['int'] if c in (5, 11, 13) else F['wrap']
            if c == 6 and v:
                sh.write_datetime(i, c, ci.parse_date(v),
                                  wb.add_format({**FMT['date']}))
            else:
                sh.write(i, c, v if v is not None else '', f)
    for i, w in enumerate(col_widths_from(hdr, body, maxw=44)):
        sh.set_column(i, i, w)
    sh.freeze_panes(1, 0)
    sh.autofilter(0, 0, len(body), len(hdr) - 1)
    sh.write(len(body) + 2, 0, '注意：本表事项与“02_事件清单_已发生”严格分开，不得相加或相互抵销。', F['warn'])

    # ---------- 04 影响量计算 ----------
    sh = wb.add_worksheet('04_影响量计算')
    hdr = ['event_id', '企业', '装置', '产能(万吨/年)', '日基准产能(吨/日)', '窗口内天数',
           '基准负荷', '事件期负荷', '减产系数', '计算公式', '减产(吨)', '全停上限(吨)',
           '是否用假设负荷', '是否计入确认口径']
    sh.write_row(0, 0, hdr, F['head'])
    body = []
    for r0 in rows:
        if r0.get('formula') is None:
            continue
        body.append([r0['event_id'], r0['company'], r0['unit_name'], r0['capacity_wt'],
                     r0.get('daily_t'), r0.get('days'), r0.get('baseline_load'),
                     r0.get('downtime_load'), r0.get('reduction_coef'), r0.get('formula'),
                     r0.get('loss_t'), r0.get('loss_upper_t'),
                     '是' if r0.get('assumed') else '否',
                     '是' if r0['bucket'] == 'domestic_confirmed' else '否'])
    for i, row in enumerate(body, start=1):
        for c, v in enumerate(row):
            if c in (4, 10, 11):
                sh.write(i, c, v, F['num'])
            elif c == 5:
                sh.write(i, c, v, F['int'])
            elif c in (6, 7, 8):
                sh.write(i, c, v, F['pct'] if v is not None else F['wrap'])
            elif c == 9:
                sh.write(i, c, v, F['wrap'])
            else:
                sh.write(i, c, v if v is not None else '', F['wrap'])
    for i, w in enumerate(col_widths_from(hdr, body, maxw=62)):
        sh.set_column(i, i, w)
    sh.freeze_panes(1, 0)

    # ---------- 05~08 汇总 ----------
    def pivot(keyfn, label, sheet, order=None):
        agg = defaultdict(lambda: {'loss': 0.0, 'cap': 0.0, 'n': 0})
        for r0 in rows:
            if r0['bucket'] != 'domestic_confirmed':
                continue
            k = keyfn(r0)
            agg[k]['loss'] += r0.get('loss_t') or 0.0
            agg[k]['cap'] += float(r0['capacity_wt'] or 0)
            agg[k]['n'] += 1
        items = sorted(agg.items(), key=lambda kv: -kv[1]['loss'])
        if order:
            items = sorted(items, key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)
        s2 = wb.add_worksheet(sheet)
        hdr = [label, '事件数', '涉及产能合计(万吨/年)', '确认减产(吨)', '确认减产(万吨)', '占确认减产比重']
        s2.write_row(0, 0, hdr, F['head'])
        total = sum(v['loss'] for _, v in items) or 1
        for i, (k, v) in enumerate(items, start=1):
            s2.write(i, 0, k, F['wrap'])
            s2.write(i, 1, v['n'], F['int'])
            s2.write(i, 2, v['cap'], F['num'])
            s2.write(i, 3, v['loss'], F['num'])
            s2.write(i, 4, v['loss'] / 10000.0, F['num'])
            s2.write(i, 5, v['loss'] / total, F['pct'])
        rr = len(items) + 1
        s2.write(rr, 0, '合计', F['h2'])
        s2.write(rr, 1, sum(v['n'] for _, v in items), F['int'])
        s2.write(rr, 2, '', F['cell'])
        s2.write(rr, 3, total, F['num'])
        s2.write(rr, 4, total / 10000.0, F['num'])
        s2.write(rr, 5, 1.0, F['pct'])
        for i, w in enumerate(col_widths_from(hdr, [[k, v['n'], v['cap'], v['loss'], v['loss'] / 1e4, '100%'] for k, v in items], maxw=40)):
            s2.set_column(i, i, w)
        s2.freeze_panes(1, 0)

    pivot(lambda r0: r0['company'], '企业', '05_汇总_按企业')
    pivot(lambda r0: reg.get(r0['region_code'], r0['region_code']), '大区', '06_汇总_按地区')
    pivot(lambda r0: r0['event_type'], '事件类型', '07_汇总_按事件类型',
          order=['计划检修', '实际停车', '意外故障', '降负荷', '复产', '新投产', '试车'])
    pivot(lambda r0: route_cn.get(r0['route'], r0['route']), '工艺路线', '08_汇总_按工艺路线',
          order=['煤制', '天然气制', '焦炉气制', '二氧化碳加氢制', '矿热炉尾气制'])

    # ---------- 09 时间线 ----------
    sh = wb.add_worksheet('09_事件时间线')
    hdr = ['event_id', '企业', '装置', '事件类型', '开始', '结束', '窗口内天数', '产能(万吨/年)',
           '减产(吨)', '归类', '状态']
    sh.write_row(0, 0, hdr, F['head'])
    tl = sorted(rows, key=lambda x: (x['start_date'] or '9999', x['company']))
    body = []
    for r0 in tl:
        body.append([r0['event_id'], r0['company'], r0['unit_name'], r0['event_type'],
                     r0['start_date'], r0['end_date'] or '', r0.get('days'),
                     r0['capacity_wt'], r0.get('loss_t'), BUCKET_CN.get(r0['bucket'], r0['bucket']),
                     r0['status_latest']])
    for i, row in enumerate(body, start=1):
        bf = BUCKET_FMT.get(tl[i - 1]['bucket'], 'cell')
        for c, v in enumerate(row):
            if c in (4, 5) and v:
                sh.write_datetime(i, c, ci.parse_date(v), wb.add_format({**FMT[bf], 'num_format': 'yyyy-mm-dd'}))
            elif c == 8:
                sh.write(i, c, v if v is not None else '', wb.add_format({**FMT[bf], 'num_format': '#,##0'}))
            else:
                sh.write(i, c, v if v is not None else '', F[bf])
    for i, w in enumerate(col_widths_from(hdr, body, maxw=34)):
        sh.set_column(i, i, w)
    sh.freeze_panes(1, 0)
    sh.autofilter(0, 0, len(body), len(hdr) - 1)

    # ---------- 10 来源与证据链 ----------
    sh = wb.add_worksheet('10_来源与证据链')
    hdr = ['event_id', '企业', '装置', '来源名称', '发布日期', '链接', '原文引用', '该事件来源总数']
    sh.write_row(0, 0, hdr, F['head'])
    body = []
    for e in D['events']:
        for s in e.get('sources', []):
            body.append([e['event_id'], e['company'], e['unit_name'], s.get('name', ''),
                         s.get('date', ''), s.get('url', ''), s.get('quote', ''),
                         e.get('source_count', len(e.get('sources', [])))])
    for p in D['planned']:
        for s in p.get('sources', []):
            body.append([p['plan_id'], p['company'], p['unit_name'], s.get('name', ''),
                         s.get('date', ''), s.get('url', ''), s.get('quote', ''),
                         p.get('source_count', len(p.get('sources', [])))])
    for i, row in enumerate(body, start=1):
        for c, v in enumerate(row):
            sh.write(i, c, v, F['wrap'])
        if row[5]:
            sh.write_url(i, 5, row[5], wb.add_format({**FMT['wrap'], 'font_color': '#0563C1', 'underline': 1}), row[5])
    for i, w in enumerate([10, 24, 28, 26, 12, 52, 70, 10]):
        sh.set_column(i, i, w)
    sh.freeze_panes(1, 0)
    sh.autofilter(0, 0, len(body), len(hdr) - 1)

    # ---------- 11 数据缺口与冲突 ----------
    sh = wb.add_worksheet('11_数据缺口与冲突')
    sh.write_row(0, 0, ['event_id/plan_id', '企业', '问题类型', '说明', '对计算结果的影响'], F['head'])
    gap = []
    for e in D['events']:
        if e.get('conflict'):
            gap.append([e['event_id'], e['company'], '口径冲突/推定', e['conflict'],
                        '已在事件中标注；影响量为区间性质' if e.get('exclude_from_confirmed') else '已按主口径处理并标注'])
        if e.get('exclude_from_confirmed'):
            gap.append([e['event_id'], e['company'], '未进入确认口径', e.get('status_note', '')[:120],
                        '不计入确认减产合计'])
        if any('推定' in str(s) or '假设' in str(e.get(k, '')) for k in ('load_note',)):
            pass
    for p in D['planned']:
        if p.get('conflict'):
            gap.append([p['plan_id'], p['company'], '未来事项时点不确定', p['conflict'], '不计入已发生影响量'])
    for i, row in enumerate(gap, start=1):
        for c, v in enumerate(row):
            sh.write(i, c, v, F['wrap'])
    for i, w in enumerate([14, 26, 20, 76, 40]):
        sh.set_column(i, i, w)

    wb.close()
    return S


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    case = os.environ.get('CASE_DIR') or os.path.join(root, 'case')
    out = os.environ.get('OUT_XLSX') or os.path.join(root, 'case', 'out', '甲醇供给事件台账.xlsx')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    s = build(case, out)
    print('written:', out)
    print('domestic_loss_wt =', s['domestic_loss_wt'], '| events =', s['totals']['n_domestic_confirmed'])
