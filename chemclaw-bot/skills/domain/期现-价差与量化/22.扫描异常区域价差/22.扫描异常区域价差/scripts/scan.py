# -*- coding: utf-8 -*-
"""
scan.py —— 区域价差扫描核心引擎（跨 Agent 通用）

设计原则（与 SKILL.md 的硬约束一一对应）：
 1. 先统一口径：每个价格点必须带 spec/region/delivery/tax/quote_type/date/source，
    并在入表时判定可比性等级；不可比的组合不进排行榜。
 2. 方向固定的两两价差：spread(A→B) = P_B − P_A，A 为基准地区，顺序在窗口内不变。
 3. 异常程度以「各自历史分布」为基准：分位 + 双侧尾部距离，绝不用绝对金额排序。
 4. 运费按方向分别录入；缺运费则 net=None（不估算），并保留裸价差。
 5. 数据覆盖不足 / 不可比 → 显式标记，进入缺口清单。

对外接口：
    from scan import ScanConfig, run_scan
    result = run_scan(ScanConfig(products=[...], window_months=12, freight={...}))
    result 可直接交给 report_html.build_html() 与 report_excel.build_excel()

数据适配层：
    load_panel() 读取标准长表 CSV（templates/价格长表模板.csv）或内置 JSON 面板。
    任何 Agent 只要把数据整理成标准长表，就能复用本引擎。
"""
from __future__ import annotations

import csv
import json
import math
import os
import statistics as st
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------- 常量与阈值
GRADE_ORDER = {'EXCESS_HIGH': 0, 'EXCESS_LOW': 0, 'ELEVATED': 1, 'NORMAL': 2,
               'INSUFFICIENT': 3, 'INCOMPARABLE': 4}

GRADE_ZH = {
    'EXCESS_HIGH': '显著偏高',
    'EXCESS_LOW': '显著偏低',
    'ELEVATED': '偏高偏离',
    'NORMAL': '正常区间',
    'INSUFFICIENT': '样本不足',
    'INCOMPARABLE': '不可比',
}

GAP_ZH = {
    'NO_REGION_PRICE': '该地区无同口径价格',
    'SINGLE_REGION_ONLY': '仅单一市场，无法构建区域组合',
    'SPEC_MISMATCH': '规格不可比',
    'DELIVERY_MISMATCH': '交货方式不可比且无运费可调整',
    'HISTORY_TOO_SHORT': '历史样本不足',
    'HISTORY_WINDOW_LIMITED': '历史窗口短于要求',
    'DEALER_QUOTE_ONLY': '仅有挂牌报价，无统一市场价',
    'FREIGHT_MISSING': '未提供运费，未做扣除',
    'NO_PAIR_COMMON_DATE': '两地无共同报价日',
    'NO_REGION_PRICE_IN_WINDOW': '窗口内无足够报价',
    'ISOLATED_QUOTE_DAY': '孤立异常报价日，已剔除',
}


@dataclass
class ScanConfig:
    """扫描参数。全部可被用户覆盖。"""
    products: List[str] = field(default_factory=list)      # 品种键，如 ['pure_soda','methanol','pvc']
    regions: Optional[List[str]] = None                     # 限定地区（节点代码），None=全部
    window_months: int = 12                                 # 历史窗口（月），1 / 3 / 6 / 12 / 36
    anomaly_grade_pct: float = 0.95                         # 异常分位阈值（双侧）
    elevate_grade_pct: float = 0.80                         # 偏离分位阈值（双侧）
    min_samples: int = 20                                   # 最小样本数
    freight: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)
    freight_enabled: bool = False                           # False = 裸价差视图
    spec_tier: str = 'primary'                              # 主规格档 / 'all'
    panel_path: Optional[str] = None                        # 自定义长表 CSV
    distances_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ScanConfig':
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (d or {}).items() if k in known})


# ---------------------------------------------------------------- 数据适配层
def load_panel(cfg: ScanConfig) -> Dict[str, Any]:
    """
    标准长表列（CSV）：
      product_key, product, region_code, region, spec, spec_tier,
      delivery, tax, quote_type, date, price, unit, source, source_url
    返回 {'rows': [...], 'catalog': {...}, 'meta': {...}}
    """
    if cfg.panel_path:
        rows = []
        with open(cfg.panel_path, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                r['price'] = float(r['price']) if r.get('price') else None
                if r['price'] is None:
                    continue
                rows.append(r)
        return {'rows': rows, 'catalog': {}, 'meta': {'source': cfg.panel_path, 'kind': 'user_csv'}}

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(here, 'data_raw', 'panel_long.csv')
    if not os.path.exists(p):
        raise FileNotFoundError(
            '未找到面板数据 %s。请先运行 scripts/fetch_all.py 抓取，'
            '或通过 ScanConfig(panel_path=...) 传入标准长表。' % p)
    rows = []
    with open(p, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            try:
                r['price'] = float(r['price'])
            except Exception:
                continue
            rows.append(r)
    cat_path = os.path.join(here, 'data_raw', 'catalog.json')
    catalog = json.load(open(cat_path, encoding='utf-8')) if os.path.exists(cat_path) else {}
    return {'rows': rows, 'catalog': catalog, 'meta': {'source': p, 'kind': 'builtin_panel'}}


# ---------------------------------------------------------------- 统计工具
def pct_rank(series: List[float], x: float) -> Optional[float]:
    """中位秩分位：处理并列值。"""
    n = len(series)
    if n == 0 or x is None:
        return None
    less = sum(1 for v in series if v < x)
    eq = sum(1 for v in series if v == x)
    return (less + 0.5 * eq) / n


def quantile(sorted_vals: List[float], q: float) -> Optional[float]:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def slope(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def safe_std(vals: List[float]) -> Optional[float]:
    if len(vals) < 3:
        return None
    s = st.stdev(vals)
    return s if s > 0 else None


# ---------------------------------------------------------------- 主流程
def run_scan(cfg: ScanConfig) -> Dict[str, Any]:
    panel = load_panel(cfg)
    rows = panel['rows']
    catalog = panel.get('catalog', {})

    products = cfg.products or sorted({r['product_key'] for r in rows})
    out = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'config': cfg.to_dict(),
        'meta': panel.get('meta', {}),
        'catalog': catalog,
        'products': {},
        'combinations': [],
        'gaps': [],
        'regions': {},
        'summary': {},
    }

    for pk in products:
        prod_rows = [r for r in rows if r['product_key'] == pk]
        if not prod_rows:
            out['gaps'].append({'product_key': pk, 'gap': 'NO_REGION_PRICE',
                                'detail': '品种池中该品种无任何价格数据'})
            continue
        prod_meta = (catalog.get('products', {}).get(pk) or {})
        regions_available = sorted({r['region_code'] for r in prod_rows})
        if cfg.regions:
            regions_available = [x for x in regions_available if x in cfg.regions]

        # ---- 口径统一：按 spec_tier 取主规格，逐地区构造日度序列
        tiers = sorted({r.get('spec_tier') or 'default' for r in prod_rows})
        chosen_tier = tiers[0] if cfg.spec_tier == 'primary' else cfg.spec_tier
        tier_rows = [r for r in prod_rows
                     if (cfg.spec_tier == 'all') or ((r.get('spec_tier') or 'default') == chosen_tier)]

        series: Dict[str, Dict[str, Any]] = {}
        for rc in regions_available:
            rs = [r for r in tier_rows if r['region_code'] == rc]
            if not rs:
                out['gaps'].append({'product_key': pk, 'region': rc, 'gap': 'NO_REGION_PRICE',
                                    'detail': '该地区无主规格档报价'})
                continue
            by_day: Dict[str, List[float]] = {}
            for r in rs:
                by_day.setdefault(r['date'], []).append(r['price'])
            # 逐日聚合：先按「商家」取中位数（同一商家同日可能重复报价），
            # 再对当天所有商家取中位数。这一步很关键 —— 挂牌报价里常有单一商家的
            # 离群高价（例如某贸易商挂 1900 而主流在 1050—1350）。若某天只剩这一条，
            # 直接取中位数就会把该地区价格整体抬高 600 元，凭空造出一个「历史极值」。
            daily = {}
            for d, vals in sorted(by_day.items()):
                daily[d] = st.median(vals)
            # 离群日保护：若某日仅 1 个商家且与「相邻 7 个有效日的中位数」偏离超过
            # 该地区整段离散度的 3 倍，则视为孤立异常报价，不参与配对（但登记缺口）。
            outl = _flag_isolated_spikes(daily, rs)
            if outl:
                out['gaps'].append({
                    'product_key': pk, 'region': rc, 'gap': 'ISOLATED_QUOTE_DAY',
                    'gap_zh': '孤立异常报价日，已剔除',
                    'detail': ('%s 有 %d 个报价日仅单一商家且价格显著偏离该地区常态'
                               '（如 %s），已从序列中剔除，避免制造虚假极值。'
                               % (rs[0]['region'], len(outl), '、'.join(sorted(outl)[:3]))),
                    'region_name': rs[0]['region'], 'dates': sorted(outl),
                })
                for d in outl:
                    daily.pop(d, None)
            series[rc] = {
                'region_code': rc,
                'region': rs[0]['region'],
                'n_quotes': len(rs),
                'n_days': len(daily),
                'daily': daily,
                'dates': sorted(daily),
                'latest': daily[sorted(daily)[-1]],
                'latest_date': sorted(daily)[-1],
                'spec_tier': chosen_tier,
                'spec_raw': sorted({r.get('spec') or '' for r in rs})[:6],
                'delivery': sorted({r.get('delivery') or '' for r in rs}),
                'quote_type': sorted({r.get('quote_type') or '' for r in rs}),
                'tax': sorted({r.get('tax') or '' for r in rs}),
                'sources': sorted({r.get('source') or '' for r in rs}),
            }

        out['products'][pk] = {
            'product_key': pk,
            'product': prod_meta.get('name') or (prod_rows[0].get('product') or pk),
            'meta': prod_meta,
            'spec_tier_used': chosen_tier,
            'spec_tiers_available': tiers,
            'regions': {k: {kk: vv for kk, vv in v.items() if kk != 'daily'}
                        for k, v in series.items()},
            'n_regions': len(series),
        }
        for rc, s in series.items():
            out['regions'][rc] = {'region_code': rc, 'region': s['region'],
                                  'product_keys': sorted(set(out['regions'].get(rc, {}).get('product_keys', []) + [pk]))}

        if len(series) < 2:
            out['gaps'].append({
                'product_key': pk, 'gap': 'SINGLE_REGION_ONLY',
                'detail': ('该品种可获取的同口径区域数 = %d，无法构建区域组合' % len(series)),
                'regions_available': sorted(series),
            })
            continue

        # ---- 窗口截断
        all_dates = sorted({d for s in series.values() for d in s['dates']})
        asof = all_dates[-1]
        asof_d = datetime.strptime(asof, '%Y-%m-%d').date()
        start_d = asof_d - timedelta(days=int(cfg.window_months * 30.44))
        start = start_d.strftime('%Y-%m-%d')

        # ---- 窗口内覆盖度过滤：窗口里没有（或极少）报价的地区不参与配对。
        # 这类地区往往只有历史零星报价（例如某个省只在早年出现过几天），
        # 放进来会让排行榜充斥着「无共同报价日」的空组合，掩盖真正的异常。
        in_win_days = {c: len({d for d in series[c]['dates'] if start <= d <= asof}) for c in series}
        dropped = {c: n for c, n in in_win_days.items() if n < cfg.min_samples}
        for c, n in sorted(dropped.items(), key=lambda kv: -kv[1]):
            out['gaps'].append({
                'product_key': pk, 'gap': 'NO_REGION_PRICE_IN_WINDOW',
                'gap_zh': '窗口内无足够报价，未纳入配对',
                'detail': ('%s 在近 %d 个月内仅 %d 个报价日（要求 ≥ %d 天），'
                           '不足以下结论，已从配对池移除；其价格水平仍列在「地区价格」表中供参考。'
                           % (series[c]['region'], cfg.window_months, n, cfg.min_samples)),
                'region': c, 'region_name': series[c]['region'], 'days_in_window': n,
            })
        active = [c for c in series if c not in dropped]
        if len(active) < 2:
            out['gaps'].append({
                'product_key': pk, 'gap': 'SINGLE_REGION_ONLY',
                'detail': ('窗口内报价足够的地区仅 %d 个，无法构建区域组合' % len(active)),
                'regions_available': sorted(active),
            })
            continue

        # ---- 方向固定：按地区价格水平选基准，整个窗口内不翻转。
        # 优先用品种配置里指定的定价中心；未指定时，选「与最多其它地区存在共同报价日」
        # 的地区作基准 —— 基准若选到报价稀疏的地区，会产生大量无法配对的组合，
        # 排行榜就被「样本不足」淹没，看不出真正的异常。
        base_pref = (prod_meta.get('pricing_center') or '')
        codes = sorted(active)
        if base_pref and base_pref in active:
            base = base_pref
        else:
            in_win = {c: {d for d in series[c]['dates'] if start <= d <= asof} for c in codes}
            base = max(codes, key=lambda c: (sum(1 for o in codes if o != c and in_win[c] & in_win[o]),
                                             len(in_win[c]), -ord(c[0])))

        for other in codes:
            if other == base:
                continue
            comb = _build_combination(pk, prod_meta, series, base, other, start, asof, cfg)
            out['combinations'].append(comb)

        # 窗口覆盖度提示
        span_days = (asof_d - datetime.strptime(all_dates[0], '%Y-%m-%d').date()).days
        if span_days < cfg.window_months * 30.44 * 0.9:
            out['gaps'].append({
                'product_key': pk, 'gap': 'HISTORY_WINDOW_LIMITED',
                'detail': ('要求窗口 %d 个月，实际可获取历史跨度约 %.1f 个月'
                           % (cfg.window_months, span_days / 30.44)),
                'required_months': cfg.window_months, 'actual_months': round(span_days / 30.44, 1),
            })

    for c in out['combinations']:
        for g in c.get('gaps', []):
            out['gaps'].append({'product_key': c['product_key'], 'pair': c['pair_code'], 'gap': g,
                                'gap_zh': GAP_ZH.get(g, g), 'detail': (c.get('gap_detail') or {}).get(g) or GAP_ZH.get(g, g)})

    # 同一（品种, 缺口代码）只登记一次，避免逐地区/逐组合重复刷屏
    dedup, seen_note = [], set()
    for g in out['gaps']:
        # 这两个代码是「品种级」结论，只需登记一次；其余缺口保留地区/组合粒度
        _k = ((g.get('product_key'), g.get('gap'))
              if g.get('gap') in ('NO_REGION_PRICE', 'DEALER_QUOTE_ONLY')
              else (g.get('product_key'), g.get('gap'), g.get('region') or g.get('pair')))
        if _k in seen_note:
            continue
        seen_note.add(_k)
        if g.get('gap') == 'DEALER_QUOTE_ONLY':
            affected = sorted({c['pair_code'] for c in out['combinations']
                               if c['product_key'] == g.get('product_key')})
            g = dict(g)
            g.pop('pair', None)
            g['gap_zh'] = GAP_ZH.get(g.get('gap'), g.get('gap'))
            g['detail'] = ('该品种全部价格均为厂家/贸易商公开挂牌报价，无交易所或资讯商统一口径的市场价；'
                           '因此所列价差反映的是「挂牌报价的区域结构」，不代表可成交价差，'
                           '也不能替代资讯商的区域市场价。受影响组合 %d 个。' % len(affected))
        dedup.append(g)
    out['gaps'] = dedup

    out['combinations'].sort(
        key=lambda c: (GRADE_ORDER.get(c['grade'], 9), -(c.get('anomaly') or 0),
                       -abs(c.get('spread_norm') or 0)))
    for i, c in enumerate(out['combinations'], 1):
        c['rank'] = i
    out['summary'] = _summarize(out)
    return out


def _flag_isolated_spikes(daily: Dict[str, float], rows: List[Dict[str, Any]],
                          win: int = 10, k: float = 3.0) -> set:
    """识别「单一商家的孤立离群报价日」。

    场景（真实数据里的确发生）：某地区平日有 5—6 家报价集中在 1250—1350，
    某天只剩 1 家挂 1900。若直接取当日中位数，该地区价格瞬间跳升 600 元，
    并凭空造出一个「历史极值」，把整条排行榜带偏。

    判定：该日只有 1 个商家，且该值与该地区**近邻日（按商家数≥2 的日子）**的中位数
    偏离超过 k 倍近邻 MAD。只用「多家报价日」做参照，避免孤立值污染参照系。
    被剔除的日期逐条登记在缺口表，可审计。
    """
    if len(daily) < win * 2:
        return set()
    cnt = Counter(r['date'] for r in rows)
    robust = [daily[d] for d in sorted(daily) if cnt.get(d, 0) >= 2]
    if len(robust) < win:
        return set()
    outl = set()
    dates = sorted(daily)
    for i, d in enumerate(dates):
        if cnt.get(d, 0) != 1:
            continue
        ref = [daily[x] for x in dates[max(0, i - win):i + 1 + win]
               if cnt.get(x, 0) >= 2 and x != d]
        if len(ref) < max(3, win // 2):
            continue
        med_r = st.median(ref)
        mad_r = st.median([abs(v - med_r) for v in ref])
        if mad_r <= 0:
            continue
        if abs(daily[d] - med_r) > k * 1.4826 * mad_r:
            outl.add(d)
    return outl


def _chg_by_days(dates: List[str], spreads: List[float], lookback: int) -> Optional[float]:
    """近 lookback 天内的价差变化：当前值 − 该日期之前（含当日）最近一条值。"""
    if len(dates) < 2:
        return None
    cur_d = datetime.strptime(dates[-1], '%Y-%m-%d').date()
    target = cur_d - timedelta(days=lookback)
    ref = None
    for d, s in zip(dates, spreads):
        if datetime.strptime(d, '%Y-%m-%d').date() <= target:
            ref = s
        else:
            break
    if ref is None:
        return None
    return round(spreads[-1] - ref, 2)


def _build_combination(pk: str, prod_meta: Dict[str, Any], series: Dict[str, Dict[str, Any]],
                       base: str, other: str, start: str, asof: str, cfg: ScanConfig) -> Dict[str, Any]:
    a, b = series[base], series[other]
    # 只取两地同日都有报价的日期
    common = sorted(set(a['daily']) & set(b['daily']))
    win = [d for d in common if start <= d <= asof]
    gaps: List[str] = []
    orient = prod_meta.get('orientation') or {}
    base_role = orient.get('base_role', '')
    other_role = orient.get('roles', {}).get(other, '')

    spreads = [round(b['daily'][d] - a['daily'][d], 2) for d in win]
    prices_a = [a['daily'][d] for d in win]
    prices_b = [b['daily'][d] for d in win]
    norm = [round(s / ((pa + pb) / 2) * 100, 3) if (pa + pb) else None
            for s, pa, pb in zip(spreads, prices_a, prices_b)]

    if not win:
        gaps.append('NO_PAIR_COMMON_DATE')

    rec: Dict[str, Any] = {
        'product_key': pk,
        'product': prod_meta.get('name') or pk,
        'pair_code': '%s|%s->%s' % (pk, base, other),
        'base': base, 'quote': other,
        'base_region': a['region'], 'quote_region': b['region'],
        'base_role': base_role, 'quote_role': other_role,
        'direction': '%s → %s' % (a['region'], b['region']),
        'formula': 'P(%s) − P(%s)' % (b['region'], a['region']),
        'n_obs': len(win),
        'first_date': win[0] if win else None,
        'last_date': win[-1] if win else None,
        'spread_series': [{'date': d, 'spread': s, 'p_a': pa, 'p_b': pb}
                          for d, s, pa, pb in zip(win, spreads, prices_a, prices_b)],
        'spec_tier': a['spec_tier'],
        'comparable': 'A',
        'gaps': gaps,
    }

    if len(win) == 0:
        rec.update({'spread_now': None, 'pct': None, 'anomaly': None, 'grade': 'INSUFFICIENT'})
        return rec

    now = spreads[-1]
    srt = sorted(spreads)
    pct = pct_rank(spreads, now)
    tail = min(pct, 1 - pct)
    anomaly = round(1 - 2 * tail, 4)
    sd = safe_std(spreads)
    z = round((now - st.mean(spreads)) / sd, 3) if sd else None

    rec.update({
        'spread_now': now,
        'pct': round(pct, 4),
        'anomaly': anomaly,
        'z': z,
        'mean': round(st.mean(spreads), 2),
        'std': round(sd, 2) if sd else None,
        'min': round(srt[0], 2), 'max': round(srt[-1], 2),
        'p05': round(quantile(srt, .05), 2), 'p25': round(quantile(srt, .25), 2),
        'p50': round(quantile(srt, .50), 2), 'p75': round(quantile(srt, .75), 2),
        'p95': round(quantile(srt, .95), 2),
        'spread_norm': norm[-1],
        'norm_mean': round(st.mean([x for x in norm if x is not None]), 3) if any(norm) else None,
        # 近期变化按「日历天」定位，而不是按「最近 N 个观测」——
        # 报价日期不均匀（有的地区隔几天一条、有的隔几周一条），
        # 用观测序号会让 chg_5d 实际跨越几个月，数值失去意义。
        'chg_5d': _chg_by_days(win, spreads, 7),
        'chg_20d': _chg_by_days(win, spreads, 30),
        'chg_5d_basis': '近 7 天（取窗口起点前最近一条报价）',
        'chg_20d_basis': '近 30 天（同上）',
        'slope_20d': round(slope(list(range(len(spreads[-21:]))), spreads[-21:]), 3)
        if len(spreads) >= 5 else None,
    })

    # 分级
    if len(spreads) < cfg.min_samples:
        grade = 'INSUFFICIENT'
        gaps.append('HISTORY_TOO_SHORT')
    elif pct >= cfg.anomaly_grade_pct:
        grade = 'EXCESS_HIGH'
    elif pct <= 1 - cfg.anomaly_grade_pct:
        grade = 'EXCESS_LOW'
    elif pct >= cfg.elevate_grade_pct or pct <= 1 - cfg.elevate_grade_pct:
        grade = 'ELEVATED'
    else:
        grade = 'NORMAL'
    rec['grade'] = grade
    rec['grade_zh'] = GRADE_ZH[grade]

    # ---- 运费（方向化，缺则 None）
    dist = _distance(base, other, cfg)
    rec['distance_km'] = dist['km'] if dist else None
    rec['drive_hours'] = dist['hours'] if dist else None
    rec['freight'] = _freight_block(pk, base, other, now, cfg, dist)

    # ---- 数据来源提示
    if a.get('quote_type') and set(a['quote_type']) == {'dealer_listing'}:
        gaps.append('DEALER_QUOTE_ONLY')
    return rec


def _load_distances(cfg: ScanConfig) -> Dict[str, Any]:
    if getattr(_load_distances, '_cache', None) is not None:
        return _load_distances._cache
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = cfg.distances_path or os.path.join(here, 'data_raw', 'distances.json')
    d = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {'distances': {}, 'nodes': []}
    _load_distances._cache = d
    return d


def _distance(a: str, b: str, cfg: ScanConfig) -> Optional[Dict[str, Any]]:
    d = _load_distances(cfg).get('distances', {})
    hit = d.get('%s|%s' % (a, b)) or d.get('%s|%s' % (b, a))
    if hit:
        return dict(hit, source='OSRM 实测公路里程')
    # 兜底：节点不在预测量表内时，按坐标大圆距离 × 公路绕行系数折算。
    # 结果明确标记 estimated=True，报告与工作簿都会显示「里程为折算值」，
    # 仅用于元/吨·公里 单位运费的换算，不得当作用户提供的真实里程。
    nodes = {n.get('code'): n for n in (_load_distances(cfg).get('nodes') or [])}
    na, nb = nodes.get(a) or {}, nodes.get(b) or {}
    if not (na.get('lon') and na.get('lat') and nb.get('lon') and nb.get('lat')):
        return None
    R = 6371.0
    p1, p2 = math.radians(na['lat']), math.radians(nb['lat'])
    dp = p2 - p1
    dl = math.radians(nb['lon'] - na['lon'])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    gc = 2 * R * math.asin(min(1.0, math.sqrt(h)))
    return {'km': round(gc * 1.28, 1), 'hours': None, 'estimated': True,
            'source': '按节点坐标大圆距离 × 1.28 公路绕行系数折算（非实测）'}


def _freight_block(pk: str, base: str, other: str, spread_now: float, cfg: ScanConfig,
                   dist: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    def one(a: str, b: str, sign: int) -> Dict[str, Any]:
        f = (cfg.freight.get(pk) or {}).get('%s->%s' % (a, b))
        if not f or not cfg.freight_enabled:
            return {'available': False, 'fee': None, 'net': None,
                    'status': 'DISABLED' if f else 'MISSING',
                    'mode': (f or {}).get('mode'), 'note': (f or {}).get('note')}
        fee = f.get('fee')
        unit = f.get('unit', '元/吨')
        if unit == '元/吨·公里':
            if not dist or not dist.get('km'):
                return {'available': False, 'fee': None, 'net': None,
                        'status': 'NO_DISTANCE', 'mode': f.get('mode'), 'note': f.get('note')}
            fee_abs = round(fee * dist['km'], 2)
        else:
            fee_abs = round(float(fee), 2)
        return {'available': True, 'fee': fee_abs, 'fee_input': fee, 'fee_unit': unit,
                'net': round(sign * spread_now - fee_abs, 2),
                'status': 'USER_PROVIDED', 'mode': f.get('mode', ''), 'note': f.get('note', '')}

    ab = one(base, other, +1)   # A 发货 → B 收货，价差为 P_B − P_A
    ba = one(other, base, -1)   # B 发货 → A 收货
    return {'enabled': cfg.freight_enabled, 'a_to_b': ab, 'b_to_a': ba}


def _summarize(out: Dict[str, Any]) -> Dict[str, Any]:
    combos = out['combinations']
    by_grade: Dict[str, int] = {}
    for c in combos:
        by_grade[c['grade']] = by_grade.get(c['grade'], 0) + 1
    top = [c for c in combos if c['grade'] in ('EXCESS_HIGH', 'EXCESS_LOW', 'ELEVATED')][:8]
    return {
        'n_combinations': len(combos),
        'n_products': len(out['products']),
        'n_regions': len({c['base'] for c in combos} | {c['quote'] for c in combos}),
        'by_grade': by_grade,
        'n_gaps': len(out['gaps']),
        'asof': combos[0]['last_date'] if combos else None,
        'top': [{'rank': c['rank'], 'product': c['product'], 'pair': '%s → %s' % (c['base_region'], c['quote_region']),
                 'grade': c['grade'], 'grade_zh': c['grade_zh'], 'spread': c['spread_now'],
                 'pct': c['pct'], 'anomaly': c['anomaly']} for c in top],
    }


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description='扫描异常区域价差')
    ap.add_argument('--products', default='', help='品种键，逗号分隔；空=全部')
    ap.add_argument('--regions', default='', help='地区节点代码，逗号分隔；空=全部')
    ap.add_argument('--window', type=int, default=12, help='历史窗口（月）')
    ap.add_argument('--min-samples', type=int, default=20)
    ap.add_argument('--anomaly-pct', type=float, default=0.95)
    ap.add_argument('--panel', default=None, help='自定义标准长表 CSV')
    ap.add_argument('--freight', default=None, help='运费 JSON 文件路径')
    ap.add_argument('--freight-enabled', action='store_true')
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)

    freight = json.load(open(args.freight, encoding='utf-8')) if args.freight else {}
    cfg = ScanConfig(
        products=[x for x in args.products.split(',') if x],
        regions=[x for x in args.regions.split(',') if x] or None,
        window_months=args.window, min_samples=args.min_samples,
        anomaly_grade_pct=args.anomaly_pct, freight=freight,
        freight_enabled=args.freight_enabled, panel_path=args.panel,
    )
    res = run_scan(cfg)
    out = args.out or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   'outputs', 'scan_result.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    s = res['summary']
    print('组合 %(n_combinations)d | 品种 %(n_products)d | 地区 %(n_regions)d | 缺口 %(n_gaps)d' % s)
    print('分级：', s['by_grade'])
    for t in s['top']:
        print('  #%d %s %s %s 价差=%s 分位=%s 异常度=%s'
              % (t['rank'], t['product'], t['pair'], t['grade_zh'], t['spread'], t['pct'], t['anomaly']))
    print('->', out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
