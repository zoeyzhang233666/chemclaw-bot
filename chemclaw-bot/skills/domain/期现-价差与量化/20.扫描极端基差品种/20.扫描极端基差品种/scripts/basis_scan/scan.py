# -*- coding: utf-8 -*-
"""scan.py — 端到端扫描：对齐 -> 基差 -> 品种内分位 -> 极端筛选 -> 覆盖核验 -> 交付物

用法
----
  python -m basis_scan.scan --codes MA,SA,V,PP,L,TA,EG,UR,SH,EB,FG,PX \
      --window-years 3 --threshold 0.10 --min-obs 120 --out out

产出（out/）
  scan_result.json      全部结构化结果（HTML/Excel 的唯一数据源，保证可复现）
  basis_{code}.csv      每个品种的日度基差序列
  ranking.csv           排行榜（品种内分位降序）
  coverage.csv          数据覆盖核验表
  run_meta.json         运行参数、版本、数据指纹
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys

from .basis_engine import (DEFAULT_MIN_OBS, build_basis, build_monthly, percentile_bucket,
                           scan_product)
from .products import EXCLUDED, load_pool

def _find_root() -> str:
    """定位项目根（含 data/ 的那层）。

    先看模块所在位置往上找（开发布局 src/basis_scan/），找不到就退回到当前工作目录
    （这样 pkg 里的 scripts/basis_scan/ 被复制到任意目录后仍能直接运行）。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    for up in (here, os.path.dirname(here), os.path.dirname(os.path.dirname(here))):
        if os.path.isdir(os.path.join(up, 'data')):
            return up
    return os.getcwd()


ROOT = _find_root()


def _load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def _sha(path: str) -> str:
    if not os.path.exists(path):
        return ''
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:16]


def derive_factor(spot_norm, fut_rows, declared, sample=30):
    """确定「现货单位 → 期货单位」的换算系数（乘到现货上）。

    优先级：
      1) 源站文章自带换算式 `现货价格/0.32`（烧碱）、`现货/0.0125`（玻璃）：1/除数 即系数。
         这是最能自证的口径，逐日取中位数。
      2) 用 `基差=现货-期货` 反解 (基差+期货)/现货，再吸附到常见整系数。
      3) 品种池声明的 spot_to_fut_factor。
      4) 1.0。
    返回 (factor, 依据说明)。
    """
    divs, implied = [], []
    for s in spot_norm[:sample]:
        d = s.get('unit_divisor')
        try:
            if d not in ('', None) and float(d) > 0:
                divs.append(1.0 / float(d))
        except (TypeError, ValueError):
            pass
    for s in spot_norm[:sample]:
        f = {r['date']: r for r in fut_rows}.get(s['date'])
        if not f or s.get('src_basis') in ('', None) or not s.get('price'):
            continue
        try:
            implied.append((float(s['src_basis']) + float(f['close'])) / float(s['price']))
        except (TypeError, ValueError, ZeroDivisionError):
            continue

    def _snap(v):
        for c in (1.0, 20.0, 80.0, 100.0, 1000.0):
            if abs(v - c) / c < 0.02:
                return c
        return round(v, 6)

    if len(divs) >= 5:
        divs.sort()
        med = divs[len(divs) // 2]
        return _snap(med), ('由源站换算式 `现货/除数` 直接反解（中位数 %.6f，样本 %d 日）'
                            % (med, len(divs)))
    if len(implied) >= 5:
        implied.sort()
        med = implied[len(implied) // 2]
        return _snap(med), ('由源站基差公式反解 (基差+期货)/现货（中位数 %.4f，样本 %d 日）'
                            % (med, len(implied)))
    return float(declared or 1.0), ('品种池声明 spot_to_fut_factor=%s（源站未提供可反解的换算式）'
                                    % (declared or 1.0))


def cross_validate(basis_rows: list[dict], spot_rows: list[dict]) -> dict:
    """用生意社基差稿文末自带的公式，校验「我们算的基差 = 源站基差」。"""
    src = {r['date']: r for r in spot_rows if r.get('src_basis') not in ('', None)}
    n = ok = 0
    max_abs = 0.0
    bad = []
    for r in basis_rows:
        s = src.get(r['date'])
        if not s:
            continue
        n += 1
        try:
            sb = float(s['src_basis'])
        except (TypeError, ValueError):
            continue
        d = abs(r['basis'] - sb)
        max_abs = max(max_abs, d)
        if d <= 0.05:
            ok += 1
        else:
            bad.append(dict(date=r['date'], ours=r['basis'], theirs=sb))
    # 源站自身口径漂移识别：某日「标题基差」≠「正文公式计算值」，属源站前后不一致
    drift = []
    for r in spot_rows:
        if r.get('src_basis') in ('', None) or r.get('fut_close') in ('', None):
            continue
        try:
            title_b, fc, px = float(r['src_basis']), float(r['fut_close']), float(r['price'])
            dv = r.get('unit_divisor')
            fac = (1.0 / float(dv)) if dv not in ('', None) else 1.0
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(title_b - (px * fac - fc)) > 0.05:
            drift.append(dict(date=r['date'], title_basis=title_b,
                              body_basis=round(px * fac - fc, 4)))
    return dict(checked=n, matched=ok, match_rate=round(100 * ok / n, 2) if n else None,
                max_abs_diff=round(max_abs, 4), mismatches=bad[:10],
                src_drift=drift, n_src_drift=len(drift))


def src_rate(basis_rows, spot_rows):
    """现货文章里带「期货主力合约 + 收盘价」的占比，用于核对期货来源是否同源。"""
    src = {r['date']: r for r in spot_rows if r.get('fut_close') not in ('', None)}
    n = ok = 0
    for r in basis_rows:
        s = src.get(r['date'])
        if not s:
            continue
        n += 1
        try:
            if abs(float(s['fut_close']) - r['fut']) <= 0.5:
                ok += 1
        except (TypeError, ValueError):
            pass
    return n, ok


def main(argv=None):
    ap = argparse.ArgumentParser(description='跨品种基差扫描（品种内历史分位）')
    ap.add_argument('--codes', default='MA,SA,V,PP,L,TA,EG,UR,SH,EB,FG,PX')
    ap.add_argument('--window-years', type=int, default=3)
    ap.add_argument('--threshold', type=float, default=0.10)
    ap.add_argument('--min-obs', type=int, default=DEFAULT_MIN_OBS)
    ap.add_argument('--change-window', type=int, default=21, help='近一月变化所用交易日数')
    ap.add_argument('--roll-rule', default='main', choices=['main', 'near'])
    ap.add_argument('--anchor', default='', help='历史窗口锚点 ISO 日期，空=用数据最新日')
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--out', default='out')
    ap.add_argument('--pool', default='')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    root = a.root
    out = a.out if os.path.isabs(a.out) else os.path.join(root, a.out)
    os.makedirs(out, exist_ok=True)
    pool = load_pool(a.pool or None)
    codes = [c.strip().upper() for c in a.codes.split(',') if c.strip()]
    pool = [p for p in pool if p['code'] in codes]

    results, coverage, details = [], [], {}
    for prod in pool:
        code = prod['code']
        spot_path = os.path.join(root, 'data', 'raw', 'spot', '%s.csv' % code)
        fut_path = os.path.join(root, 'data', 'raw', 'fut', '%s_%s.csv' % (prod['futures_contract_prefix'], a.roll_rule))
        spot_rows = _load_csv(spot_path)
        fut_rows = _load_csv(fut_path)
        cov = dict(code=code, name=prod['name'], spot_file=os.path.relpath(spot_path, root),
                   fut_file=os.path.relpath(fut_path, root),
                   spot_days=len(spot_rows),
                   spot_first=spot_rows[0]['date'] if spot_rows else '',
                   spot_last=spot_rows[-1]['date'] if spot_rows else '',
                   fut_days=len(fut_rows),
                   fut_first=fut_rows[0]['date'] if fut_rows else '',
                   fut_last=fut_rows[-1]['date'] if fut_rows else '',
                   sha_spot=_sha(spot_path), sha_fut=_sha(fut_path))
        if not spot_rows or not fut_rows:
            status = '数据缺失'
            reason = []
            if not spot_rows:
                reason.append('无现货基准价序列')
            if not fut_rows:
                reason.append('无期货日线')
            res = dict(code=code, name=prod['name'], status=status, reason='；'.join(reason),
                       n_obs=0)
            results.append(res)
            cov.update(status=status, reason='；'.join(reason), matched=0)
            coverage.append(cov)
            details[code] = dict(daily=[], monthly=[])
            continue
        # 统一转换为 engine 需要的结构
        # ★ 单位换算：现货若与期货计价单位不同（如玻璃 元/平方米 vs 元/吨），
        #   必须在相减之前统一到期货单位；换算系数在品种池里显式声明，公式不因此改变。
        factor = float(prod.get('spot_to_fut_factor') or 1.0)
        fut_rows_p = fut_rows
        raw_pre = [dict(date=r['date'], price=float(r['price']), src_basis=r.get('src_basis', ''),
                        unit_divisor=r.get('unit_divisor', '')) for r in spot_rows]
        factor, factor_basis = derive_factor(raw_pre, fut_rows_p, prod.get('spot_to_fut_factor'))
        spot_norm = [dict(date=r['date'], price=float(r['price']) * factor, src_type=r.get('src_type', ''),
                          fut_contract=r.get('fut_contract', ''), fut_close=r.get('fut_close', ''),
                          src_basis=r.get('src_basis', ''), url=r.get('url', ''),
                          unit=prod['unit'], raw_price=float(r['price']),
                          raw_unit=prod.get('spot_unit') or prod['unit']) for r in spot_rows]
        fut_norm = [dict(date=r['date'], close=float(r['close']), symbol=r.get('symbol', ''),
                         oi=float(r.get('oi') or 0), is_roll=int(float(r.get('is_roll') or 0)))
                    for r in fut_rows]
        basis_rows, bcov = build_basis(spot_norm, fut_norm)
        res = scan_product(code, prod['name'], basis_rows, window_years=a.window_years,
                           threshold=a.threshold, min_obs=a.min_obs,
                           change_window=a.change_window, anchor=(a.anchor or None))
        xv = cross_validate(basis_rows, spot_norm)
        nfut, nfut_ok = src_rate(basis_rows, spot_norm)
        res.update(exchange=prod['exchange'], unit=prod['unit'],
                   spot_spec=prod['spot_spec'], spot_region=prod['spot_region'],
                   spot_tax=prod['spot_tax'], contract_spec=prod['contract_spec'],
                   futures_region=prod['futures_region'], last_trade_rule=prod['last_trade_rule'],
                   multiplier=prod['multiplier'], tick=prod['tick'], note=prod['note'],
                   spot_unit=prod.get('spot_unit') or prod['unit'],
                   spot_to_fut_factor=factor,
                   spot_unit_basis=factor_basis,
                   spot_unit_note=prod.get('spot_unit_note', ''),
                   spot_raw=(spot_norm[-1]['raw_price'] if spot_norm else ''),
                   roll_rule=('主力连续：每交易日取持仓量最大合约' if a.roll_rule == 'main'
                              else '近月连续：交割月≥当日的最近月份，持仓<主力5%则顺延'),
                   current_contract=basis_rows[-1]['symbol'] if basis_rows else '',
                   xcheck=xv)
        res['bucket'] = percentile_bucket(res.get('pct_used'))
        res['reason'] = ''
        res['n_total_basis_days'] = len(basis_rows)
        res['basis_first'] = basis_rows[0]['date'] if basis_rows else ''
        res['basis_last'] = basis_rows[-1]['date'] if basis_rows else ''
        res['chg_1m_per_trade_day'] = (
            round(res['chg_1m'] / max(1, a.change_window), 3)
            if res.get('chg_1m') not in ('', None) else '')
        results.append(res)
        cov.update(status=res['status'], reason=res.get('reason', ''), matched=len(basis_rows),
                   window_start=res.get('window_start', ''), window_end=res.get('window_end', ''),
                   n_obs=res.get('n_obs', 0), xcheck_rate=xv['match_rate'],
                   xcheck_n=xv['checked'], fut_src_check='%d/%d' % (nfut_ok, nfut),
                   bucket=res.get('bucket', ''))
        coverage.append(cov)
        details[code] = dict(
            daily=[dict(date=r['date'], spot=r['spot'], fut=r['fut'], basis=r['basis'],
                        symbol=r['symbol'], is_roll=r['is_roll']) for r in basis_rows],
            monthly=build_monthly(basis_rows))
        # 写出该品种日度基差
        with open(os.path.join(out, 'basis_%s.csv' % code), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['date', 'spot', 'futures', 'basis', 'contract', 'is_roll'])
            for r in basis_rows:
                w.writerow([r['date'], r['spot'], r['fut'], r['basis'], r['symbol'], r['is_roll']])
        print('  %-3s %-6s %s n=%s pct=%s flag=%s' % (
            code, prod['name'], res['status'], res.get('n_obs', 0), res.get('pct_used', ''),
            res.get('flag', '')), flush=True)

    # ---- 库存/仓单数据合并进结果（只补可获取的，取不到保留「未获取」）
    fund_path = os.path.join(out, 'fundamentals.json')
    fund = {}
    if os.path.exists(fund_path):
        with open(fund_path, encoding='utf-8') as f:
            fund = json.load(f)
    for r in results:
        f = fund.get(r['code'], {})
        lt, pv = f.get('inv_latest'), f.get('inv_prev')
        r['inventory'] = dict(
            status=f.get('inv_status', '未获取'), reason=f.get('inv_reason', ''),
            scope=f.get('inv_scope', ''), latest=lt, prev=pv,
            series=f.get('inv_series', [])[-40:], exchange=f.get('inv_exchange'))
        if lt and pv and pv.get('inventory'):
            r['inventory']['chg_20d'] = round(lt['inventory'] - pv['inventory'], 2)
            r['inventory']['chg_20d_pct'] = round(
                100 * (lt['inventory'] - pv['inventory']) / pv['inventory'], 2)
        r['events'] = f.get('events', [])
        r['events_scope'] = f.get('events_scope', '')


    # 排行榜：只在「OK」品种内按自身分位排序；不可比金额绝不跨品种比较
    ok_rows = [r for r in results if r['status'] == 'OK']
    flag_rank = {'低位极端': 0, '高位极端': 1, '常态': 2}
    ranked = sorted(ok_rows, key=lambda r: (flag_rank.get(r['flag'], 3),
                                            float(r['pct_used']) if r['flag'] == '低位极端'
                                            else -float(r['pct_used'])))
    for i, r in enumerate(ranked, 1):
        r['rank'] = i
    for r in results:
        r.setdefault('rank', '')

    excluded = [e for e in EXCLUDED]
    meta = dict(generated_at=dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                window_years=a.window_years, threshold=a.threshold, min_obs=a.min_obs,
                change_window=a.change_window, roll_rule=a.roll_rule, anchor=a.anchor or None,
                codes=codes, pool_size=len(codes),
                n_ok=len(ok_rows), n_extreme=sum(1 for r in ok_rows if r['extreme']),
                n_insufficient=sum(1 for r in results if r['status'] != 'OK'),
                basis_convention='基差 = 现货基准价 − 期货收盘价（品种内比较，禁止跨品种比较金额）',
                percentile_convention='经验分位=历史窗口内严格小于当日基差的比例；并列使用中位秩；'
                                      '极端判定用中位秩 ≤ 低阈值 或 ≥ 1−阈值',
                data_latest=max([r.get('basis_last') or '' for r in results] or ['']),
                version='1.0.0')
    # ---- 样本长度如实披露 ------------------------------------------------
    ok_obs = [r.get('n_obs', 0) for r in ok_rows]
    known = [r.get('n_obs', 0) for r in results if r.get('n_obs')]
    meta['sample_note'] = (
        '本次扫描的实际样本为「生意社逐日市场基差稿」在栏目窗口内可回溯的全部交易日'
        '（%d~%d 个，覆盖约 %.1f 个自然月），而非名义上的 %d 年窗口。'
        '名义窗口 %d 年只作为上界：数据更短时按实际样本计算并在覆盖核验表逐品种披露。'
        % (min(known) if known else 0, max(known) if known else 0,
           (max(known) if known else 0) / 20.5, a.window_years, a.window_years))
    meta['sample_warning'] = (
        '【重要边界】当前现货样本不足 1 个自然年，尚未覆盖完整的季节性周期与极端行情；'
        '因此分位只能说明"在近 %d 个交易日内处于什么位置"，不能外推为多年历史分位。'
        '长期历史需用 archive.py 按周增量归档逐步累积（100ppi 栏目仅保留最近约 10 页文章）。'
        % (max(known) if known else 0))
    meta['n_short_sample'] = sum(1 for r in ok_rows if r.get('n_obs', 0) < 250)
    meta['long_history_note'] = (
        '期货侧历史充足（逐合约日线可回溯至上市首日，主力连续 1600~1880 个交易日）；'
        '瓶颈在现货基准价的公开可回溯长度。')
    obj = dict(meta=meta, results=results, coverage=coverage, excluded=excluded,
               details=details, pool=pool, fundamentals=fund)
    with open(os.path.join(out, 'scan_result.json'), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)
    with open(os.path.join(out, 'ranking.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['rank', 'code', 'name', 'status', 'flag', 'pct_used', 'basis', 'n_obs',
                    'window_start', 'window_end', 'chg_1m', 'contract'])
        for r in results:
            w.writerow([r.get('rank', ''), r['code'], r['name'], r['status'],
                        r.get('flag', ''), r.get('pct_used', ''), r.get('basis_yuan', ''),
                        r.get('n_obs', ''), r.get('window_start', ''), r.get('window_end', ''),
                        r.get('chg_1m', ''), r.get('current_contract', '')])
    if coverage:
        keys = list(coverage[0].keys())
        for c in coverage:
            for k in c:
                if k not in keys:
                    keys.append(k)
        with open(os.path.join(out, 'coverage.csv'), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(coverage)
    with open(os.path.join(out, 'run_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print('\n[OK] %d 品种完成；可扫描 %d；极端 %d；不足 %d；结果 -> %s' % (
        len(results), len(ok_rows), meta['n_extreme'], meta['n_insufficient'],
        os.path.join(out, 'scan_result.json')))


if __name__ == '__main__':
    main()
