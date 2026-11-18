# -*- coding: utf-8 -*-
"""期现·产业基本面晨报 —— 公共库。

设计原则（与 SKILL.md 三条硬规矩一致）：
1. 只呈现已发生的事实，不做方向预测；方向词由 banned_hits() 拦截。
2. 每个数字都带「口径五件套」：数值 · 规格 · 区域 · 含税 · 数据日期 · 来源。
3. 拿不到就标缺口（gap），绝不用近似值、行业均值或插值填充。

只依赖 Python 标准库；openpyxl 仅在 build_xlsx 时需要。
"""
import datetime
import hashlib
import json
import os
import re
import statistics
import sys

# ---------------------------------------------------------------- 品种注册表
# 市场前缀：113=上期所 114=大商所 115=郑商所 142=上海国际能源 225=广期所
MARKETS = {'113': '上期所', '114': '大商所', '115': '郑商所',
           '142': '上海国际能源交易中心', '225': '广期所'}

# product -> dict(secid, 主连代码, 交易所)
PRODUCT_LIB = {
    '甲醇': ('115.MAM', 'MAM', '郑商所', 'MA'),
    'PP': ('114.ppm', 'ppm', '大商所', 'PP'),
    'PVC': ('114.vm', 'vm', '大商所', 'V'),
    'LLDPE': ('114.lm', 'lm', '大商所', 'L'),
    '乙二醇': ('114.egm', 'egm', '大商所', 'EG'),
    '苯乙烯': ('114.ebm', 'ebm', '大商所', 'EB'),
    '纯碱': ('115.SAM', 'SAM', '郑商所', 'SA'),
    '玻璃': ('115.FGM', 'FGM', '郑商所', 'FG'),
    '尿素': ('115.URM', 'URM', '郑商所', 'UR'),
    '烧碱': ('115.SHM', 'SHM', '郑商所', 'SH'),
    'PTA': ('115.TAM', 'TAM', '郑商所', 'TA'),
    '原油': ('142.scm', 'scm', '上海国际能源交易中心', 'SC'),
    '燃料油': ('113.fum', 'fum', '上期所', 'FU'),
    '沥青': ('113.bum', 'bum', '上期所', 'BU'),
    '焦煤': ('114.jmm', 'jmm', '大商所', 'JM'),
    '焦炭': ('114.jm', 'jm', '大商所', 'J'),
    '硅铁': ('115.SFM', 'SFM', '郑商所', 'SF'),
    '锰硅': ('115.SMM', 'SMM', '郑商所', 'SM'),
    '碳酸锂': ('225.lcm', 'lcm', '广期所', 'LC'),
    '工业硅': ('225.sim', 'sim', '广期所', 'SI'),
}

# 期货代码 -> 交易所（用于合约月份拼装，如 MA2701 / pp2701 / v2701）
EXCH_PREFIX = {'MA': '115', 'SA': '115', 'FG': '115', 'UR': '115', 'SH': '115',
               'TA': '115', 'SF': '115', 'SM': '115',
               'PP': '114', 'V': '114', 'L': '114', 'EG': '114', 'EB': '114',
               'JM': '114', 'J': '114',
               'SC': '142', 'FU': '113', 'BU': '113',
               'LC': '225', 'SI': '225'}

# 品种 -> 报告内代码（用于 DCE 小写代码）
DCE_CODES = {'PP': 'pp', 'V': 'v', 'L': 'l', 'EG': 'eg', 'EB': 'eb', 'JM': 'jm', 'J': 'j'}


def contract_secid(product, yymm):
    """MA + 2701 -> 115.MA701；PP + 2701 -> 114.pp2701（大商所小写）。"""
    code = PRODUCT_LIB.get(product, (None, None, None, product))[3]
    mkt = EXCH_PREFIX.get(code, '115')
    if code in DCE_CODES:
        return '%s.%s%s' % (mkt, DCE_CODES[code], yymm)
    return '%s.%s%s' % (mkt, code, yymm)


# 产业链骨架：告诉研究阶段「该查什么」，不是数据本身
CHAIN_HINTS = {
    '甲醇': (['动力煤', '天然气（伊朗/中东）', '焦炉气'], ['MTO/MTP 烯烃', '甲醛', '醋酸', '二甲醚', 'MTBE']),
    'PP': (['原油', '石脑油', '丙烷（PDH）', '丙烯', '煤制烯烃'], ['塑编', 'BOPP 膜', '注塑', '无纺布']),
    'PVC': (['电石', '兰炭', '乙烯', '烧碱（联产）'], ['管材', '型材', '地板', '薄膜', '出口（印度/东南亚）']),
    'LLDPE': (['原油', '乙烯'], ['农膜', '包装膜', '管材']),
    '乙二醇': (['乙烯', '煤制乙二醇'], ['聚酯', '防冻液']),
    '纯碱': (['原盐', '动力煤', '合成氨'], ['浮法玻璃', '光伏玻璃', '洗涤日化']),
    '玻璃': (['纯碱', '天然气/石油焦'], ['房地产竣工', '汽车玻璃', '光伏组件']),
    '尿素': (['无烟煤', '天然气', '合成氨'], ['复合肥', '三聚氰胺', '车用尿素']),
}

# ---------------------------------------------------------------- 基础 IO
def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def dump_json(obj, path):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def ok(msg):
    print('[ OK  ] ' + msg)


def warn(msg):
    print('[WARN ] ' + msg)


def die(msg, code=2):
    print('[FATAL] ' + msg, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- 数值与日期
def num(v):
    """'1,150' / '1150元/吨' / 1150.0 -> float；拿不到返回 None。"""
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
    return None


def days_between(a, b):
    da, db = parse_date(a), parse_date(b)
    if not da or not db:
        return None
    return (db - da).days


def last_trading_day(d):
    """粗略交易日：跳过周末（不含法定节假日，节假日需人工核对）。"""
    d = d - datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


# ---------------------------------------------------------------- 方向性表述检查
# 只拦「指向未来」的句式；「下跌 3.2%」是已发生事实，必须放行。
BANNED_WORDS = ['预计涨', '预计跌', '看涨', '看跌', '抄底', '必涨', '必跌', '稳赚',
                '多单持有', '空单持有', '买入评级']
BANNED_PATTERNS = [
    # 「预计甲醇将进一步下跌」这类把预测当结论的句式：预计 … （中间可夹名词）… 将/会/继续 + 涨跌
    r'预计[^。；，\n]{0,14}(将|会|继续|仍|有望|或)(进一步)?(上涨|下跌|上行|下行|走高|走低|反弹|回落|抬升|下滑)',
    r'预计(会)?(也)?(上涨|下跌|上行|下行|走高|走低|反弹|回落)',
    r'(有望|将会|即将|料将|或将|仍将|还将|继续)(上涨|下跌|上行|下行|走高|走低|反弹|回落|提价|涨价|跌价)',
    r'(后市|后期|未来|接下来|下周|下月|明年)[^。；\n]{0,12}(将|会|有望|或|可能|仍)',
    r'看(涨|跌)',
    r'(必|稳|一定|肯定|必然|无疑)(涨|跌|赚|赢)',
    r'抄底|逃顶|囤货待涨|追涨杀跌',
    r'(已经|基本|算是|就是)(见底|到底|触底|筑底)',
    r'(底部|顶部)(已现|已到|确认|形成|出现)',
    r'(上涨|下跌|上行|下行)空间(大|有限|打开)',
    r'建议[^。；\n]{0,10}(囤|备|压|建|抄|买|卖)(货|仓|库存)',
    r'不(会|可能)(再)?(跌|涨)',
]
_BANNED_RE = [re.compile(p) for p in BANNED_PATTERNS]


def banned_hits(text):
    """返回命中的方向性表述片段。

    允许「条件句」：『若…则…』『如果…将…』是在描述假设情景下的传导逻辑，
    不是对未来的预测；只有把预测当结论的句子才算违规。因此先剔除条件子句再匹配。
    """
    if not isinstance(text, str):
        return []
    hits = [w for w in BANNED_WORDS if w in text]
    # 去掉条件分句（若/如果/假如/一旦 … 至分句结束），避免把假设当预测
    cleaned = re.sub(r'(若|如果|假如|一旦|倘若)[^。；\n]{0,40}', '', text)
    for pat in _BANNED_RE:
        m = pat.search(cleaned)
        if m:
            hits.append(m.group(0))
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


# ---------------------------------------------------------------- 序列工具
def load_series(path):
    """读取 fetch_futures.py 产出的序列；返回按日期升序的 [{d,o,c,h,l,v,pct}]。"""
    raw = load_json(path) if isinstance(path, str) else path
    if isinstance(raw, dict):
        raw = raw.get('rows') or raw.get('klines') or raw.get('data') or []
    rows = []
    for x in raw:
        if isinstance(x, str):
            p = x.split(',')
            rows.append({'d': p[0], 'o': float(p[1]), 'c': float(p[2]), 'h': float(p[3]),
                         'l': float(p[4]), 'v': float(p[5] or 0),
                         'pct': float(p[7]) if len(p) > 7 and p[7] else None})
        else:
            rows.append({'d': x['d'], 'o': float(x.get('o', x['c'])), 'c': float(x['c']),
                         'h': float(x.get('h', x['c'])), 'l': float(x.get('l', x['c'])),
                         'v': float(x.get('v', 0)), 'pct': x.get('pct')})
    rows.sort(key=lambda r: r['d'])
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


def change_stats(rows, last, days):
    b = find_le(rows, (parse_date(last['d']) - datetime.timedelta(days=days)).isoformat())
    if not b:
        return None
    return {'from_date': b['d'], 'from_close': b['c'],
            'abs': round(last['c'] - b['c'], 2),
            'pct': round((last['c'] / b['c'] - 1) * 100, 2)}


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
    return {'days': days, 'start': w[0]['d'], 'n': len(w),
            'high': hi['h'], 'high_date': hi['d'], 'low': lo['l'], 'low_date': lo['d'],
            'mean': round(statistics.mean(closes), 1), 'pct_rank': round(rank, 1),
            'pos_in_range': round((last['c'] - lo['l']) / rng * 100, 1) if rng else None}


def oi_vol_change(rows, last, prev):
    """持仓/成交变化：prev 为空时返回 None（不猜）。"""
    if not prev or not last:
        return None
    return {'v': last.get('v', 0) - prev.get('v', 0),
            'v_pct': round((last['v'] / prev['v'] - 1) * 100, 2) if prev.get('v') else None}


def candles(rows):
    return [[r['d'], r['o'], r['c'], r['l'], r['h']] for r in rows]


def weekly(rows):
    out, key0 = [], None
    for r in rows:
        k = parse_date(r['d']).isocalendar()[:2]
        if k != key0:
            out.append([r['d'], r['o'], r['c'], r['l'], r['h']])
            key0 = k
        else:
            out[-1][2] = r['c']
            out[-1][3] = min(out[-1][3], r['l'])
            out[-1][4] = max(out[-1][4], r['h'])
    return out


# ---------------------------------------------------------------- 文本
def clip(s, n=120):
    s = str(s or '').replace('\n', ' ')
    return s if len(s) <= n else s[:n - 1] + '…'


def sha_short(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()[:12]


def jaccard(a, b):
    """中文按 2-gram 集合计算相似度，用于事件去重。"""
    def grams(s):
        s = re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9]', '', str(s or ''))
        return set(s[i:i + 2] for i in range(max(0, len(s) - 1)))
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)
