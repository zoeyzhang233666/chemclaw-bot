# -*- coding: utf-8 -*-
"""增量变化检测：把「上一期基线 + 本期原始数据」算成可比的变动表。

用法：
  python assemble.py config.json --out build/data.json

核心规则（对应 SKILL.md「变化检测规则」）：
- R1 对齐：比较必须落在同一口径（品种/指标/规格/区域/含税）；
- R2 取数：本期默认取 ≤ 报告日的最后一个交易日；周五夜盘计入「下一交易日」口径；
- R3 变动：abs=本期-上期，pct=abs/上期；上期为 0 或缺时 pct 记 None，不写 0%；
- R4 新值优先：抓取价 > 派生价（现货-期货）；派生值必须写明算法；
- R5 陈旧标注：data_date < 报告日即标 stale_days，筛选阶段据此降级；
- R6 缺口：上期无记录的新指标标 is_new=True，不进入「变化」排行，单列「新增指标」。
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


# 事件类型中文名（正文与表格都用中文，英文枚举只留在原始数据里）
TYPE_CN = {
    'plant': '装置动态', 'maintenance': '检修', 'shutdown': '停车', 'restart': '复产',
    'capacity': '产能投放', 'project': '项目进度', 'policy': '政策',
    'regulation': '监管', 'tariff': '关税', 'trade': '进出口',
    'import': '进口', 'export': '出口', 'price': '报价调整', 'quote': '报价',
    'demand': '需求', 'inventory': '库存', 'stock': '库存',
    'cost': '成本', 'profit': '利润', 'geo': '地缘', 'shipping': '航运',
    'war': '冲突', 'sanction': '制裁', 'comment': '观点(噪声)', 'view': '观点(噪声)',
    'macro': '宏观', 'weather': '天气',
}


def type_cn(t):
    return TYPE_CN.get(t or '', t or '')


# ---------------------------------------------------------------- 读取原始
def load_raw(raw_dir):
    """raw/*.json -> {label: {rows,...}}，并汇总可用区间，供报告标注数据新鲜度。"""
    out = {}
    if not os.path.isdir(raw_dir):
        return out
    for fn in sorted(os.listdir(raw_dir)):
        if not fn.endswith('.json') or fn.startswith('_'):
            continue
        label = fn[:-5]
        try:
            d = common.load_json(os.path.join(raw_dir, fn))
        except Exception:
            continue
        # raw/ 下可能混放事件清单等非序列文件；只接受带 rows 的行情字典
        if isinstance(d, dict) and d.get('rows'):
            out[label] = d
    return out


def pick_close(raw, label, report_date):
    """取 ≤ 报告日的最后一根收盘，返回 (date, close, prev_row)。"""
    series = raw.get(label)
    if not series:
        return None
    rows = common.load_series(series)
    hit = common.find_le(rows, report_date)
    if not hit:
        return None
    i = rows.index(hit)
    prev = rows[i - 1] if i > 0 else None
    return hit, prev


# 主连换月识别阈值：相邻两日「前收 vs 昨收」偏离超过该比例，视为换月而非真实涨跌
ROLL_JUMP_PCT = 8.0


def main_contract_day_pct(rows, last, prev):
    """主连日涨跌。

    主连在换月日会「跳接」到下一个合约，若直接用相邻收盘相除会得到一天的假涨跌
    （本案例 10月20日：前一日 3,143 → 今日 3,117 看似 -0.83%，实际主力已从 MA2701
    切到新合约，真实主力 2701 当日仅 -0.50%）。

    规则：
    - 若 |last.open - prev.close| / prev.close 超过 ROLL_JUMP_PCT，判为换月，
      改用「今日收盘 / 今日开盘」得到的日内涨跌，并置 rolled=True 提示；
    - 否则用「今收 / 昨收 - 1」。
    """
    if not prev:
        return {'pct': None, 'method': '无上一交易日', 'rolled': False,
                'open_chg_pct': None}
    open_jump = (last['o'] / prev['c'] - 1) * 100 if prev['c'] else None
    rolled = abs(open_jump or 0) > ROLL_JUMP_PCT
    if rolled:
        pct = (last['c'] / last['o'] - 1) * 100 if last['o'] else None
        method = '换月跳接，改用日内（收盘/开盘）'
    else:
        pct = (last['c'] / prev['c'] - 1) * 100 if prev['c'] else None
        method = '收盘/昨收'
    return {'pct': round(pct, 2) if pct is not None else None,
            'method': method, 'rolled': rolled,
            'open_chg_pct': round(open_jump, 2) if open_jump is not None else None}


# ---------------------------------------------------------------- 变动计算
def delta(cur, base):
    if cur is None or base is None:
        return {'abs': None, 'pct': None}
    return {'abs': round(cur - base, 4),
            'pct': round((cur / base - 1) * 100, 2) if base else None}


def build_indicator(cfg, base_map):
    """单条指标：先取本期，再取上期，产出变动 + 新旧判定 + 陈旧天数。

    关键判定（R5）：上期本身是「空位」（None / "" / "-"）意味着该期未发布，
    这种情况本期数值不能与它相减（会把陈旧值误判成 0 变化），必须回退到
    cfg 里显式给出的 base（上上期/同口径来源），并在 note 里记明。
    """
    pid = cfg['id']
    rep = parse_report_date(cfg['_report_date'])
    cur_val = common.num(cfg.get('current'))
    cur_date = cfg.get('data_date')

    base = base_map.get(pid) or {}
    base_val = common.num(base.get('value'))
    base_date = base.get('date')
    base_src = '上一期报告'

    # 上一期为空位 → 回退到配置内的显式基线，绝不与陈旧值相减
    if base_val is None and cfg.get('base') is not None:
        base_val = common.num(cfg.get('base'))
        base_date = cfg.get('base_date')
        base_src = '配置指定（上一期该指标未发布）'
    # 上一期有值但数值与本期完全相同、且上一期数据日期早于今日 → 说明上一期沿用了源头
    if base_val is not None and cur_val is not None and abs(base_val - cur_val) < 1e-9 \
            and cfg.get('base') is not None and cfg.get('base_date') \
            and common.parse_date(cfg.get('base_date')) != common.parse_date(base_date):
        base_val = common.num(cfg.get('base'))
        base_date = cfg.get('base_date')
        base_src = '配置指定（上一期沿用了源头未更新）'

    d = delta(cur_val, base_val) if (base_val is not None) else {'abs': None, 'pct': None}
    # 上期日期兜底：基线里可能只有值没有日期（或日期在指标外），此时统一落到基线报告日，
    # 避免 Excel/HTML 出现「有上期值但没有上期日期」的空洞
    if base_val is not None and not base_date:
        base_date = (base.get('report_date')
                     or ((base.get('__report__') or {}).get('report_date'))
                     or cfg.get('base_date'))
    # 派生指标（基差/价差）的日期由构成项决定，等于报告日收盘日
    if not cur_date and cfg.get('freq') == 'daily':
        cur_date = cfg['_report_date']
    stale = common.days_between(cur_date, cfg['_report_date']) if cur_date else None
    row = {
        'id': pid,
        'product': cfg['product'],
        'module': cfg['module'],              # price | basis | spread | inventory | runrate | demand | cost
        'name': cfg['name'],
        'spec': cfg.get('spec', ''),
        'region': cfg.get('region', ''),
        'unit': cfg.get('unit', ''),
        'tax': cfg.get('tax', ''),
        'freq': cfg.get('freq', 'daily'),      # daily | weekly | monthly | event
        'current': cur_val,
        'current_date': cur_date,
        'base': base_val,
        'base_date': base_date,
        'base_source': base_src,
        'abs': d['abs'],
        'pct': d['pct'],
        'has_base': base_val is not None,
        'is_new': base_val is None,            # R6：上期无记录
        'stale_days': stale,
        'source': cfg.get('source', ''),
        'source_url': cfg.get('source_url', ''),
        'note': cfg.get('note', ''),
        'formula': cfg.get('formula', ''),
        # 每条信息的四件套，供 HTML 抽屉与 Excel 落表
        'what': cfg.get('what', ''),
        'why': cfg.get('why', ''),
        'verify': cfg.get('verify', ''),
        'tier': cfg.get('tier', 'B'),
        'history': cfg.get('history') or [],
        'report_date': cfg['_report_date'],
    }
    row['significance'] = significance(row, cfg)
    return row


def parse_report_date(s):
    d = common.parse_date(s)
    if not d:
        common.die('报告日期不合法：%s' % s)
    return d


# 每个指标族的「关注阈值」：超过即判为当日需要点名的变化
THRESHOLD = {
    'price_daily_pct': 1.0,       # 单日涨跌 ≥1%
    'basis_abs': 30,              # 基差变动 ≥30 元/吨
    'spread_abs': 20,             # 月差变动 ≥20 元/吨
    'inventory_pct': 3.0,         # 库存周环比 ≥3%
    'runrate_pp': 1.0,            # 开工率变化 ≥1 个百分点
    'generic_pct': 2.0,           # 其他百分数 ≥2%
}


def significance(row, cfg):
    """重要性：A=必须点名；B=值得记录；C=无变化/噪声（筛除）。"""
    if row['is_new']:
        return 'B'
    if row['abs'] is None:
        return 'C'
    a, p = abs(row['abs']), abs(row['pct'] or 0)
    if row['module'] in ('inventory', 'runrate', 'demand', 'cost'):
        if a >= THRESHOLD['runrate_pp'] * 2 or p >= THRESHOLD['inventory_pct']:
            return 'A'
        if a >= THRESHOLD['runrate_pp'] or p >= 1.0:
            return 'B'
        return 'C'
    if row['module'] == 'basis':
        return 'A' if a >= THRESHOLD['basis_abs'] * 2 else ('B' if a >= THRESHOLD['basis_abs'] else 'C')
    if row['module'] == 'spread':
        return 'A' if a >= THRESHOLD['spread_abs'] * 2 else ('B' if a >= THRESHOLD['spread_abs'] else 'C')
    # price / generic
    if p >= THRESHOLD['price_daily_pct'] * 2 or a >= 100:
        return 'A'
    if p >= THRESHOLD['price_daily_pct'] or a > 0:
        return 'B'
    return 'C'


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('config', help='本期配置 research.json')
    ap.add_argument('--out', default='build/data.json')
    ap.add_argument('--baseline', help='上一期 build/data.json（可选；缺省用配置内的 base 字段）')
    a = ap.parse_args()

    cfg = common.load_json(a.config)
    report_date = cfg['report']['report_date']
    rd = parse_report_date(report_date)
    prev_date = cfg['report'].get('prev_baseline_date') or \
        common.last_trading_day(rd).isoformat()

    # 上一期基线：优先读上一期的 build/data.json 或 research.json（两者字段命名不同，都要兼容）
    base_map = {}
    if a.baseline and os.path.exists(a.baseline):
        prev = common.load_json(a.baseline)
        prev_rep = (prev.get('report') or {}).get('report_date') or prev_date
        prev_date = prev_rep
        for r in prev.get('indicators', []):
            # build/data.json 用 current/current_date；research.json 用 current/data_date。上期不存在则退回 base/base_date
            val = r.get('current', r.get('base'))
            dt = r.get('current_date') or r.get('data_date') or r.get('base_date') or prev_rep
            base_map[r['id']] = {'value': val, 'date': dt, 'report_date': prev_rep}
        common.ok('基线来自上一期 %s（%d 条指标）' % (prev_date, len(base_map)))
    for ind in cfg.get('indicators', []):
        if ind.get('base') is not None and ind['id'] not in base_map:
            base_map[ind['id']] = {'value': ind.get('base'), 'date': ind.get('base_date')}

    # 期货序列：主连与合约
    raw = load_raw(cfg['paths']['raw'])
    futures = {}
    for p, spec in cfg.get('futures', {}).items():
        label = spec.get('series_label') or ('%s主连' % p)
        hit = pick_close(raw, label, report_date)
        if not hit:
            common.warn('%s 无 %s 及以前的行情' % (p, report_date))
            continue
        last, prev = hit
        rows = common.load_series(raw[label])
        dp = main_contract_day_pct(rows, last, prev)
        futures[p] = {
            'label': label,
            'name': spec.get('name', p),
            'secid': spec.get('secid', ''),
            'date': last['d'],
            'close': last['c'],
            'open': last['o'], 'high': last['h'], 'low': last['l'],
            'pct_day': dp['pct'],
            'pct_day_method': dp['method'],
            'rolled': dp['rolled'],
            'open_chg_pct': dp['open_chg_pct'],
            'prev_close': prev['c'] if prev else None,
            'prev_date': prev['d'] if prev else None,
            'chg_5d': common.change_stats(rows, last, 7),
            'chg_20d': common.change_stats(rows, last, 30),
            'chg_60d': common.change_stats(rows, last, 90),
            'year_pos': common.window_stats(rows, last, 365),
            'quarter_pos': common.window_stats(rows, last, 90),
            'candles_60': common.candles([r for r in rows if r['d'] >=
                                          (rd - datetime.timedelta(days=120)).isoformat()]),
            'candles_250': common.candles([r for r in rows if r['d'] >=
                                           (rd - datetime.timedelta(days=365)).isoformat()]),
            'first': rows[0]['d'], 'n': len(rows),
        }
        # 若配置指定了「主力实际合约」，用它给出可比的日涨跌与月差，避免主连跳接失真
        cm = spec.get('main_month_label')
        if cm:
            ch = pick_close(raw, cm, report_date)
            if ch:
                cl, cp = ch
                futures[p]['main_month'] = {
                    'label': cm, 'date': cl['d'], 'close': cl['c'],
                    'pct_day': round((cl['c'] / cp['c'] - 1) * 100, 2) if cp else None,
                    'prev_close': cp['c'] if cp else None,
                }

    # 指标
    inds = []
    for ind in cfg.get('indicators', []):
        ind = dict(ind)
        ind['_report_date'] = report_date
        inds.append(build_indicator(ind, base_map))

    # 事件：去重 + 重要性
    events = []
    for ev in cfg.get('events', []):
        e = dict(ev)
        e['report_date'] = report_date
        e['stale_days'] = common.days_between(e.get('event_date'), report_date)
        e['event_type_cn'] = type_cn(e.get('event_type'))
        e.setdefault('tier', 'B')
        events.append(e)

    summary = {
        'indicators_total': len(inds),
        'with_base': sum(1 for i in inds if i['has_base']),
        'is_new': sum(1 for i in inds if i['is_new']),
        'tier_A': sum(1 for i in inds if i['significance'] == 'A'),
        'tier_B': sum(1 for i in inds if i['significance'] == 'B'),
        'tier_C': sum(1 for i in inds if i['significance'] == 'C'),
        'events_total': len(events),
        'events_A': sum(1 for e in events if e.get('tier') == 'A'),
        'events_B': sum(1 for e in events if e.get('tier') == 'B'),
        'events_C': sum(1 for e in events if e.get('tier') == 'C'),
        'events_dup': sum(1 for e in events if e.get('dup_count')),
        'events_repeat': sum(1 for e in events if e.get('status') == 'repeat'),
        'events_excluded': sum(1 for e in events if e.get('tier') == 'C'),
    }

    data = {
        'meta': {
            'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
            'tool': 'industrial-morning-brief assemble.py',
            'offline': True,
        },
        'report': cfg['report'],
        'profile': cfg.get('profile', {}),
        'baseline': {'date': prev_date,
                     'label': cfg['report'].get('prev_label', '上一交易日收盘')},
        'futures': futures,
        'indicators': inds,
        'events': events,
        'excluded': cfg.get('excluded', []),
        'gaps': cfg.get('gaps', []),
        'sources': cfg.get('sources', []),
        'chain': cfg.get('chain', {}),
        'summary': summary,
    }
    common.dump_json(data, a.out)
    common.ok('已生成 %s' % a.out)
    common.ok('指标 %d 条（有基线 %d / 新指标 %d）；A级 %d B级 %d C级(噪声) %d' % (
        summary['indicators_total'], summary['with_base'], summary['is_new'],
        summary['tier_A'], summary['tier_B'], summary['tier_C']))
    stale = [i['name'] for i in inds if (i['stale_days'] or 0) > 1]
    if stale:
        common.warn('%d 条指标数据日期早于报告日 >1 天：%s' % (len(stale), '、'.join(stale[:6])))
    common.ok('事件 %d 条，去重 %d 条，筛除 %d 条' % (
        summary['events_total'], summary['events_dup'], summary['events_excluded']))


if __name__ == '__main__':
    main()
