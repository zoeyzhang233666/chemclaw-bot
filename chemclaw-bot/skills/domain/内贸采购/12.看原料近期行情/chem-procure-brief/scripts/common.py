# -*- coding: utf-8 -*-
"""化学品行情简报 skill —— 公共库。

只依赖 Python 标准库 + openpyxl。不联网、不碰第三方 SaaS。
设计原则：任何“没拿到”的东西一律写成 缺口，不用估算值填充。
"""
import json
import os
import re
import sys
import datetime
import statistics

# ---------------------------------------------------------------- 品种注册表
# secid 前缀：113=上期所 114=大商所 115=郑商所 142=上海国际能源 225=广期所
MARKETS = {
    '115': '郑商所', '114': '大商所', '113': '上期所', '142': '上海国际能源交易中心', '225': '广期所',
}

# product -> (market_id, 主连代码, 交易所中文)
# 这是“场内合约代码查询表”，不是产业链知识：只用于 fetch_futures.py 拼接行情接口，
# 不参与任何产业链判断（链一律由 research.json 的 chain_proof 提供）。
# 新品种直接在这里加一行即可；没有场内合约的品种无需登记（把 research.json 的 futures 删掉）。
PRODUCT_LIB = {
    '纯碱': ('115', 'SAM', '郑商所'),
    '烧碱': ('115', 'SHM', '郑商所'),
    '尿素': ('115', 'URM', '郑商所'),
    '甲醇': ('115', 'MAM', '郑商所'),
    '玻璃': ('115', 'FGM', '郑商所'),
    'PTA': ('115', 'TAM', '郑商所'),
    '短纤': ('115', 'PFM', '郑商所'),
    '纯苯': ('115', 'BZM', '郑商所'),
    '丙烯': ('115', 'PLM', '郑商所'),
    'PVC': ('114', 'vm', '大商所'),
    '聚乙烯': ('114', 'lm', '大商所'),
    '聚丙烯': ('114', 'ppm', '大商所'),
    '乙二醇': ('114', 'egm', '大商所'),
    '苯乙烯': ('114', 'ebm', '大商所'),
    '液化石油气': ('114', 'pgm', '大商所'),
    '碳酸锂': ('225', 'lcm', '广期所'),
    '工业硅': ('225', 'sim', '广期所'),
    '多晶硅': ('225', 'psm', '广期所'),
    '天然橡胶': ('113', 'rum', '上期所'),
    '燃料油': ('113', 'fum', '上期所'),
    '沥青': ('113', 'bum', '上期所'),
    '原油': ('142', 'scm', '上海国际能源交易中心'),
}

# 产业链提示：只回答“这个品种该去查哪几个上下游”，不回答“它们的价格是多少”。
# 采购版刻意**不预置任何品种的链**（CHAIN_HINTS 为空）：链必须由研究稿按工艺路线自证，
# 写在 research.json 的 upstream / downstream / chain 里，工具只负责校验“有没有断点”。
# 想固化企业内名单，请改 research.json，而不是改这里——否则换品种时会把别人的链带进来。
CHAIN_HINTS = {}

# ---------------------------------------------------------------- 基础 IO
def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def dump_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def die(msg, code=2):
    print('[FATAL] ' + msg, file=sys.stderr)
    sys.exit(code)


def warn(msg):
    print('[WARN ] ' + msg)


def ok(msg):
    print('[ OK  ] ' + msg)


# ---------------------------------------------------------------- 数值工具
def num(v):
    """把 '1,150' / '1150元/吨' / 1150.0 统一成 float；拿不到返回 None。"""
    if v is None or v is True or v is False:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r'-?\d+(?:\.\d+)?', str(v).replace(',', ''))
    return float(m.group()) if m else None


def fmt(n, d=0):
    if n is None:
        return '—'
    return format(round(float(n), d), ',.%df' % d)


def fmt_trim(n, maxd=2):
    """按需保留小数：1150 -> '1,150'，-144.74 -> '-144.74'，-202.0 -> '-202'。
    用于毛利、成本这类既有整数也有两位小数的量。"""
    if n is None:
        return '—'
    f = float(n)
    for d in range(maxd + 1):
        if abs(round(f, d) - f) < 1e-9:
            return format(round(f, d), ',.%df' % d)
    return format(round(f, maxd), ',.%df' % maxd)


def pct(n, d=2):
    if n is None:
        return '—'
    return ('+' if n > 0 else '') + ('%.' + str(d) + 'f%%') % n


def parse_date(s):
    if not s:
        return None
    s = str(s).strip()[:10]
    for f in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y%m%d'):
        try:
            return datetime.datetime.strptime(s, f).date()
        except ValueError:
            continue
    m = re.match(r'(\d{4})-(\d{1,2})', s)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), 1)
        except ValueError:
            return None
    return None


def days_between(a, b):
    da, db = parse_date(a), parse_date(b)
    if not da or not db:
        return None
    return (db - da).days


# ---------------------------------------------------------------- 方向性表述检查
# 只抓“指向未来”的措辞。单独的“上涨/下跌/回落/跌破”是陈述已发生事实，必须放行，
# 所以这里用句式正则，不用裸词。
BANNED_WORDS = ['预计涨', '预计跌', '看涨', '看跌', '抄底', '必涨', '必跌', '稳赚',
                '保价上涨', '后市将', '即将上涨', '即将下跌', '一定会涨', '一定会跌']
BANNED_PATTERNS = [
    r'预计(会)?(也)?(上涨|下跌|上行|下行|走高|走低|反弹|回落)',
    r'(有望|将会|即将|料将|或将|仍将|还将|继续|持续)(上涨|下跌|上行|下行|走高|走低|反弹|回落|提价|涨价|跌价)',
    r'(后市|后期|未来|接下来|下周|下月|明年)(将|会|有望|或|可能|仍)',
    r'看(涨|跌)',
    r'(必|稳|一定|肯定|必然|无疑)(涨|跌|赚|赢)',
    r'抄底|逃顶|囤货待涨|追涨杀跌',
    r'(已经|基本|算是|就是)(见底|到底|触底|筑底)',
    r'(底部|顶部)(已现|已到|确认|形成|出现)',
    r'(上涨|下跌|上行|下行)空间(大|有限|打开)',
    r'(涨|跌)幅(有望|将)',
    r'建议[^。；\n]{0,10}(囤|备|压|建|抄|买|卖)(货|仓|库存)',
    r'不(会|可能)(再)?(跌|涨)',
]
_BANNED_RE = [re.compile(p) for p in BANNED_PATTERNS]


def banned_hits(text):
    """返回命中的方向性表述（去重）。"""
    if not isinstance(text, str):
        return []
    hits = [w for w in BANNED_WORDS if w in text]
    for pat in _BANNED_RE:
        m = pat.search(text)
        if m:
            hits.append(m.group(0))
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


# ---------------------------------------------------------------- 序列与统计
def load_series(path):
    """价格序列 JSON -> [{d,o,c,h,l,v,pct}]，按日期升序。
    兼容三种输入：[[date,o,c,l,h],...]（东财 klines 字符串）/ 对象数组 / {'klines':[...]}"""
    raw = load_json(path) if isinstance(path, str) else path
    if isinstance(raw, dict):
        raw = raw.get('rows') or raw.get('klines') or raw.get('daily') or raw.get('data') or []
    rows = []
    for x in raw:
        if isinstance(x, str):
            p = x.split(',')
            rows.append({'d': p[0], 'o': float(p[1]), 'c': float(p[2]), 'h': float(p[3]), 'l': float(p[4]),
                         'v': float(p[5]) if len(p) > 5 and p[5] else 0.0,
                         'pct': float(p[7]) if len(p) > 7 and p[7] else None})
        elif isinstance(x, (list, tuple)):
            d, o, c, l, h = x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4])
            rows.append({'d': d, 'o': o, 'c': c, 'h': h, 'l': l, 'v': 0.0, 'pct': None})
        else:
            rows.append({'d': x['d'], 'o': float(x.get('o', x['c'])), 'c': float(x['c']),
                         'h': float(x.get('h', x['c'])), 'l': float(x.get('l', x['c'])),
                         'v': float(x.get('v', 0)), 'pct': x.get('pct')})
    rows.sort(key=lambda r: r['d'])
    # 补日涨跌
    prev = None
    for r in rows:
        if r['pct'] is None:
            r['pct'] = 0.0 if prev is None else round((r['c'] / prev - 1) * 100, 2)
        prev = r['c']
    return rows


def find_le(rows, date_str):
    best = None
    for r in rows:
        if r['d'] <= date_str:
            best = r
        else:
            break
    return best


def window_stats(rows, last, days):
    cutoff = (parse_date(last['d']) - datetime.timedelta(days=days)).isoformat()
    w = [r for r in rows if r['d'] >= cutoff]
    if not w:
        return None
    hi = max(w, key=lambda x: x['h'])
    lo = min(w, key=lambda x: x['l'])
    closes = sorted(r['c'] for r in w)
    rank = sum(1 for c in closes if c <= last['c']) / len(closes) * 100
    rng = hi['h'] - lo['l']
    return {
        'days': days, 'start': w[0]['d'], 'n': len(w),
        'high': hi['h'], 'high_date': hi['d'], 'low': lo['l'], 'low_date': lo['d'],
        'mean': round(statistics.mean(closes), 1), 'median': round(statistics.median(closes), 1),
        'pct_rank': round(rank, 1),
        'pos_in_range': round((last['c'] - lo['l']) / rng * 100, 1) if rng else None,
    }


def change_stats(rows, last, days):
    b = find_le(rows, (parse_date(last['d']) - datetime.timedelta(days=days)).isoformat())
    if not b:
        return None
    return {'from_date': b['d'], 'from_close': b['c'], 'abs': round(last['c'] - b['c'], 1),
            'pct': round((last['c'] / b['c'] - 1) * 100, 2)}


def weekly(rows):
    out, key0 = [], None
    for r in rows:
        k = parse_date(r['d']).isocalendar()[:2]
        if k != key0:
            out.append([r['d'], r['o'], r['c'], r['l'], r['h']])
            key0 = k
        else:
            c = out[-1]
            c[2] = r['c']
            c[3] = min(c[3], r['l'])
            c[4] = max(c[4], r['h'])
    return out


def candles(rows):
    return [[r['d'], r['o'], r['c'], r['l'], r['h']] for r in rows]


# ---------------------------------------------------------------- 文本工具
def cjk_width(s):
    return sum(2 if ord(ch) > 127 else 1 for ch in str(s))


def clip(s, n=120):
    s = str(s or '').replace('\n', ' ')
    return s if len(s) <= n else s[:n - 1] + '…'


def sha_short(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()[:12]


# ================================================================ 采购侧扩展
# 以下四块只服务“我要买”的场景，和销售版的区别是：
#   1) 现货序列按“报价点位”分组，算区间涨跌与分位（销售版算期货序列）；
#   2) 区域价差用采购语言（到厂/送到 vs 出厂），并给出“为什么差”与“该不该买远端”；
#   3) 成本拆解把上游价格折算成“单耗 × 单价”，回答“成本还能不能托住报价”；
#   4) 事件按“对采购的影响”过滤（检修/复产/投产/库存/物流/政策），纯盘面新闻不进时间线。

ROUTE_UNITS = {'t': 1.0, 'ton': 1.0, '吨': 1.0, 'kt': 1000.0, '千吨': 1000.0,
               'normal_m3': 1 / 1000.0, 'nm3': 1 / 1000.0, '方': 1 / 1000.0,
               'kwh': 1 / 1000.0, '度': 1 / 1000.0}


def route_cost(route):
    """把一条工艺路线的单耗表折成“每吨原料成本”。

    route = {"name":"路线甲", "unit_price": {...可选...},
             "inputs":[{"item":"原料 X","qty":1.55,"unit":"吨","price":785,"date":"…"}, …]}
    qty 是“每生产 1 吨产品消耗多少单位原料”，必须来自公开工艺参数或企业披露；
    拿不到的就不写这条 inputs，绝不补默认值。
    """
    if not isinstance(route, dict):
        return None
    base = route.get('unit_price') or {}
    lines, total, ok = [], 0.0, True
    for x in route.get('inputs') or []:
        q = num(x.get('qty'))
        p = num(x.get('price'))
        if p is None and x.get('item') in base:
            p = num(base.get(x.get('item')))
        if q is None or p is None:
            ok = False
            lines.append({'item': x.get('item') or '未命名原料', 'qty': q, 'unit': x.get('unit') or '',
                          'price': p, 'unit_price_note': x.get('price_note') or '', 'cost': None,
                          'date': x.get('date'), 'src': x.get('src') or ''})
            continue
        f = ROUTE_UNITS.get(str(x.get('unit') or '吨').strip(), 1.0)
        cost = q * p * f
        total += cost
        lines.append({'item': x.get('item') or '未命名原料', 'qty': q, 'unit': x.get('unit') or '',
                      'price': p, 'unit_price_note': x.get('price_note') or '',
                      'cost': round(cost, 1), 'date': x.get('date'), 'src': x.get('src') or ''})
    return {'name': route.get('name') or '未命名路线', 'lines': lines,
            'total': round(total, 1) if ok and lines else None,
            'complete': bool(ok and lines),
            'co_product': route.get('co_product') or '',
            'note': route.get('note') or '', 'src': route.get('src') or '',
            'date': route.get('date')}


def series_from_quotes(quotes):
    """现货报价 -> 点位序列。

    quotes = [{"point":"采购点A","date":"2026-10-13","lo":3730,"hi":3960,
               "spec":"…","tax":"含税","basis":"…","src":"…"}, …]
    返回 {point: {'rows':[{d,lo,hi,mid}], 'meta':{spec,tax,basis}}}
    同一天同一批次的重复引用只保留第一条（不去重会让人误以为是两个数据点）。
    """
    out = {}
    for q in quotes or []:
        pt = (q.get('point') or q.get('region') or '').strip()
        d = str(q.get('date') or '')[:10]
        lo, hi = num(q.get('lo')), num(q.get('hi'))
        if lo is None and hi is None:
            lo = hi = num(q.get('value'))
        if not pt or not d or lo is None:
            continue
        if hi is None:
            hi = lo
        if lo > hi:
            lo, hi = hi, lo
        b = out.setdefault(pt, {'rows': [], 'meta': {}})
        b['rows'].append({'d': d, 'lo': lo, 'hi': hi, 'mid': round((lo + hi) / 2, 1),
                          'src': q.get('src') or '', 'note': q.get('note') or ''})
        for k in ('spec', 'tax', 'basis', 'unit'):
            if q.get(k) and not b['meta'].get(k):
                b['meta'][k] = q[k]
    for pt, b in out.items():
        seen, rows = set(), []
        for r in sorted(b['rows'], key=lambda x: x['d']):
            if r['d'] in seen:
                continue
            seen.add(r['d'])
            rows.append(r)
        b['rows'] = rows
    return out


def seq_stats(rows, windows=(7, 30, 90, 365, 1095)):
    """现货点位序列的区间统计。基准日取序列末值，**逐窗口按日历回溯**。

    现货是稀疏报价，因此每个窗口都返回基准日与样本数，让读者一眼看出这个
    “30 天涨跌幅”其实只有 6 个报价点——不做插值，也不假装是连续序列。
    """
    if not rows:
        return None
    last = rows[-1]
    out = {'last': last, 'n': len(rows), 'start': rows[0]['d']}
    chg = {}
    for w in windows:
        cut = (parse_date(last['d']) - datetime.timedelta(days=w)).isoformat()
        before = [r for r in rows if r['d'] <= cut]
        base = before[-1] if before else None
        if not base:
            continue
        chg[str(w)] = {'from_date': base['d'], 'from_mid': base['mid'], 'mid': last['mid'],
                       'abs': round(last['mid'] - base['mid'], 1),
                       'pct': round((last['mid'] / base['mid'] - 1) * 100, 2) if base['mid'] else None,
                       'n_between': len([r for r in rows if base['d'] < r['d'] <= last['d']]),
                       'exact_days': days_between(base['d'], last['d'])}
    win = {}
    for w in windows:
        cut = (parse_date(last['d']) - datetime.timedelta(days=w)).isoformat()
        seg = [r for r in rows if r['d'] >= cut]
        if len(seg) < 3:
            continue
        mids = sorted(r['mid'] for r in seg)
        hi = max(seg, key=lambda r: r['hi'])
        lo = min(seg, key=lambda r: r['lo'])
        rng = hi['hi'] - lo['lo']
        win[str(w)] = {'n': len(seg), 'start': seg[0]['d'],
                       'high': hi['hi'], 'high_date': hi['d'], 'low': lo['lo'], 'low_date': lo['d'],
                       'median': round(statistics.median(mids), 1),
                       'mean': round(statistics.mean(mids), 1),
                       'pct_rank': round(sum(1 for m in mids if m <= last['mid']) / len(mids) * 100, 1),
                       'pos_in_range': round((last['mid'] - lo['lo']) / rng * 100, 1) if rng else None}
    out['chg'] = {int(k): v for k, v in chg.items()}
    out['win'] = {int(k): v for k, v in win.items()}
    return out


def parse_ratio(text):
    """把 '270:1' / '1.55 吨' / '约 1.5' 里的系数取出来，取不到返回 None。"""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = re.search(r'(\d+(?:\.\d+)?)\s*[:：]\s*(\d+(?:\.\d+)?)', str(text))
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        return round(a / b, 4) if b else None
    return num(text)


def quote_position(value, stats):
    """当前价在区间里的相对位置，用文字表达（采购可以直接引用）。"""
    if value is None or not stats:
        return None
    w = stats['win'].get(365) or stats['win'].get(90) or stats['win'].get(30)
    if not w or w.get('pos_in_range') is None:
        return None
    p = w['pos_in_range']
    label = '区间下 1/3' if p < 33.3 else ('区间中段' if p < 66.7 else '区间上 1/3')
    return {'pos': p, 'label': label, 'n': w['n'], 'start': w['start']}
