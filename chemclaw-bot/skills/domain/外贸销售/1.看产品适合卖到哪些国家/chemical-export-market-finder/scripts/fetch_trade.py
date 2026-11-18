#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_trade.py - pull bilateral import data for one HS-6 code from UN Comtrade.

STEP 2 of the workflow. Produces the raw, cacheable dataset that every downstream
table is built from. No estimates, no interpolation: missing years stay missing.

Data source
-----------
UN Comtrade public preview API (no key required, rate limited):
    https://comtradeapi.un.org/public/v1/preview/C/A/HS
    flowCode=M (imports), classification HS, annual, customs basis.
    • partnerCode=0    -> reporter's total imports from the world
    • partnerCode=156  -> reporter's imports from China (CHN, M49=156)
    • omit partnerCode -> full partner breakdown for one reporter (<=500 rows)

Values are CIF in USD as-reported by the reporter. Quantity is netWgt in kg.

Usage
-----
    # total + China, all reporters, default years
    python fetch_trade.py --hs 283620 --years 2019-2025

    # also pull partner breakdowns for the top importers
    python fetch_trade.py --hs 283620 --years 2019-2025 --partners --top 15

    # different origin country (e.g. India exports -> study India as origin)
    python fetch_trade.py --hs 283620 --origin 699

    # exports instead of imports
    python fetch_trade.py --hs 283620 --flow X

Outputs (into --out, default ./trade_data)
------------------------------------------
    raw/*.json                      raw API responses (cache; re-runs are free)
    imports_by_reporter_year.csv    reporter x year: world value/qty + China value/qty
    partners_by_reporter_year.csv   reporter x year x partner (when --partners)
    reporters.json / partners.json  official code->name reference
    fetch_meta.json                 provenance: what was fetched, when, coverage per year
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://comtradeapi.un.org/public/v1/preview/C/A/HS?'
REF_REPORTERS = 'https://comtradeapi.un.org/files/v1/app/reference/Reporters.json'
REF_PARTNERS = 'https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json'
UA = {'User-Agent': 'chemical-export-market-finder/1.0 (research; contact: user)'}


def _get(url, timeout=120, tries=6, cache_path=None):
    """GET with backoff. Comtrade returns 429 (rate) and 403 'Quota Exceeded' under load."""
    if cache_path and os.path.exists(cache_path) and os.path.getsize(cache_path) > 50:
        try:
            return json.load(open(cache_path, encoding='utf-8'))
        except Exception:
            pass
    delay = 4
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            raw = urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8')
            j = json.loads(raw)
            if cache_path:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                json.dump(j, open(cache_path, 'w', encoding='utf-8'))
            return j
        except urllib.error.HTTPError as e:
            last = f'HTTP {e.code}'
            if e.code in (429, 403, 500, 502, 503, 504):
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            raise RuntimeError(f'{last} for {url}')
        except Exception as e:  # network hiccup
            last = str(e)
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise RuntimeError(f'gave up after {tries} tries: {last}')


def load_reference(url, cache_path):
    j = _get(url, cache_path=cache_path)
    key = next(k for k, v in j.items() if isinstance(v, list))
    return j[key]


def parse_years(spec):
    out = []
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-')
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return sorted(set(out))


def main():
    ap = argparse.ArgumentParser(description='Fetch UN Comtrade bilateral trade data for an HS-6 code.')
    ap.add_argument('--hs', required=True, help='HS-6 code, e.g. 283620')
    ap.add_argument('--years', default='2019-2025', help='e.g. 2019-2025 or 2020,2022,2024')
    ap.add_argument('--origin', default='156', help='origin/partner M49 code (default 156 = China)')
    ap.add_argument('--flow', default='M', choices=['M', 'X'], help='M=imports (default), X=exports')
    ap.add_argument('--out', default='trade_data')
    ap.add_argument('--partners', action='store_true', help='also fetch partner breakdown for top importers')
    ap.add_argument('--top', type=int, default=15, help='how many top importers to pull partner detail for')
    a = ap.parse_args()

    hs = a.hs.strip()
    if not (hs.isdigit() and len(hs) == 6):
        print(f'ERROR: --hs must be a 6-digit code, got {hs!r}', file=sys.stderr)
        return 2
    years = parse_years(a.years)
    out = a.out
    raw = os.path.join(out, 'raw')
    os.makedirs(raw, exist_ok=True)

    print(f'[1/4] reference lists ...', flush=True)
    reporters = load_reference(REF_REPORTERS, os.path.join(raw, 'reporters.json'))
    partners = load_reference(REF_PARTNERS, os.path.join(raw, 'partners.json'))
    reps = {int(r['id']): r for r in reporters}
    parts = {int(r['id']): r for r in partners}

    def nm(code):
        r = parts.get(int(code)) or reps.get(int(code))
        return r.get('text') if r else f'#{code}'

    print(f'[2/4] totals + origin({a.origin}) for HS {hs}, years {years} ...', flush=True)
    rows = []
    for y in years:
        for partner, tag in (('0', 'wld'), (a.origin, 'orig')):
            url = BASE + urllib.parse.urlencode({
                'period': y, 'cmdCode': hs, 'flowCode': a.flow, 'partnerCode': partner})
            try:
                j = _get(url, cache_path=os.path.join(raw, f'{a.flow}_{hs}_{y}_p{partner}.json'))
                print(f'   {y} partner={partner}: {j.get("count", 0)} reporters', flush=True)
                if tag == 'wld':
                    rows.append({'year': y, 'world': {d['reporterCode']: d for d in j.get('data', [])}})
                else:
                    if rows and rows[-1]['year'] == y:
                        rows[-1]['origin'] = {d['reporterCode']: d for d in j.get('data', [])}
                time.sleep(1.2)
            except Exception as e:
                print(f'   {y} partner={partner}: FAILED ({str(e)[:90]}) -> left as gap', flush=True)

    recs = []
    for blk in rows:
        y = blk['year']
        w = blk.get('world', {})
        o = blk.get('origin', {})
        for rep, d in w.items():
            od = o.get(rep, {})
            rr = reps.get(rep, {})
            recs.append({
                'year': y, 'reporterCode': rep, 'reporter': nm(rep),
                'iso3': rr.get('reporterCodeIsoAlpha3', ''),
                'import_usd': d.get('primaryValue') or 0,
                'netweight_kg': d.get('netWgt') or 0,
                'qty': d.get('qty') or 0,
                'origin_usd': od.get('primaryValue') or 0,
                'origin_kg': od.get('netWgt') or 0,
                'origin_reported': bool(od),
            })
    p1 = os.path.join(out, 'imports_by_reporter_year.csv')
    with open(p1, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0].keys()) if recs else ['year'])
        w.writeheader(); w.writerows(recs)
    print(f'   -> {p1} ({len(recs)} rows)', flush=True)

    # coverage per year (a real, reportable metric)
    cover = {}
    for y in years:
        sub = [r for r in recs if r['year'] == y]
        cover[y] = {'reporters_with_data': len(sub)}

    # optional partner breakdown
    if a.partners and recs:
        latest = {}
        for r in recs:
            if r['import_usd'] > 0:
                latest[r['reporterCode']] = max(latest.get(r['reporterCode'], 0), r['year'])
        ranked = sorted(latest.items(), key=lambda kv: -max(
            (r['import_usd'] for r in recs if r['reporterCode'] == kv[0] and r['year'] == kv[1]), default=0))
        targets = [rep for rep, _ in ranked[:a.top]]
        print(f'[3/4] partner breakdown for top {len(targets)} importers ...', flush=True)
        prow = []
        for rep in targets:
            for y in years:
                url = BASE + urllib.parse.urlencode({
                    'period': y, 'reporterCode': rep, 'cmdCode': hs, 'flowCode': a.flow})
                try:
                    j = _get(url, cache_path=os.path.join(raw, f'{a.flow}_{hs}_R{rep}_{y}_partners.json'))
                    n = 0
                    for d in j.get('data', []):
                        if d['partnerCode'] == 0:
                            continue
                        prow.append({'year': y, 'reporterCode': rep, 'reporter': nm(rep),
                                     'partnerCode': d['partnerCode'], 'partner': nm(d['partnerCode']),
                                     'value_usd': d.get('primaryValue') or 0,
                                     'netweight_kg': d.get('netWgt') or 0})
                        n += 1
                    print(f'   {nm(rep)} {y}: {n} partners', flush=True)
                    time.sleep(0.9)
                except Exception as e:
                    print(f'   {nm(rep)} {y}: FAILED ({str(e)[:70]})', flush=True)
        p2 = os.path.join(out, 'partners_by_reporter_year.csv')
        with open(p2, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=['year', 'reporterCode', 'reporter', 'partnerCode',
                                              'partner', 'value_usd', 'netweight_kg'])
            w.writeheader(); w.writerows(prow)
        print(f'   -> {p2} ({len(prow)} rows)', flush=True)
    else:
        print('[3/4] partner breakdown skipped (use --partners)', flush=True)

    meta = {
        'hs6': hs, 'flow': a.flow, 'origin_m49': a.origin, 'origin_name': nm(a.origin),
        'years_requested': years, 'coverage': cover, 'fetched_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'source': 'UN Comtrade public preview API (annual, HS, CIF, as-reported)',
        'currency': 'USD', 'quantity_unit': 'kg (netWgt)',
        'caveats': ['coverage falls in recent years; totals are sums over reporting countries only',
                    'blank year = not reported, never zero-filled'],
    }
    json.dump(meta, open(os.path.join(out, 'fetch_meta.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'[4/4] done -> {out}', flush=True)
    print('NEXT: python build_outputs.py --data ' + out + ' --product "..." --spec "..."', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
