# -*- coding: utf-8 -*-
"""build_html.py —— 把 report_data.json 渲染成单文件离线 HTML。

特性：
  * 零外部依赖：ECharts 与数据全部内联，断网可看，可直接发给客户。
  * 交互：归因树点开抽屉、事件按成本/供给/需求/库存/政策/期现结构筛选、
    分期热力矩阵、证据分级分布、异动日标注。
  * 不预测：页面固定出现免责声明，所有"归因"只到证据分级为止。

用法：
  python build_html.py --data build/report_data.json --out out/report.html \
      --template-dir templates --assets assets/echarts.min.js
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def build_sensitivity(data, case):
    """不同起点下的同一波行情 —— 用来证明"涨多少"取决于起点选择。"""
    spot = {r['date']: r['spot'] for r in data['price'] if r['spot']}
    if not spot:
        return []
    ks = sorted(spot)
    end = ks[-1]
    out = []
    cands = []
    win_start = data['meta']['window']['start']
    cands.append((win_start, '研究窗口起点：两个来源共同确认的局部低点'))
    # 区间内最低点
    lo = min(spot.items(), key=lambda kv: kv[1])
    if lo[0] != win_start:
        cands.append((lo[0], '窗口内现货最低点（若以此为起点，即为"从底到底"的最大涨幅）'))
    # 月初首个交易日
    months = sorted({k[:7] for k in ks})
    for m in months[:6]:
        d = next((k for k in ks if k.startswith(m)), None)
        if d and d not in [c[0] for c in cands]:
            cands.append((d, '%s 月首个有报价日' % m))
    seen = set()
    for d, note in cands:
        if d in seen or d not in spot:
            continue
        seen.add(d)
        out.append({'date': d, 'start': spot[d], 'end': spot[end],
                    'diff': spot[end] - spot[d],
                    'pct': (spot[end] / spot[d] - 1) * 100, 'note': note})
    out.sort(key=lambda x: -x['pct'])
    return out


def build_anomaly_bars(anom, price_rows):
    bars = []
    for b in (anom or {}).get('bars_in_window', []):
        if b['date'] < price_rows[0]['date'] if price_rows else False:
            continue
        bars.append(b)
    return bars


def compute_bands(bars, n=60):
    """给异动图配 ±2σ 带：滚动 n 日收益标准差。"""
    rets = [b['ret'] for b in bars]
    for i, b in enumerate(bars):
        lo = max(0, i - n)
        seg = rets[lo:i]
        if len(seg) < 10:
            b['band_up'] = None
            b['band_dn'] = None
            continue
        sd = (sum((x - sum(seg) / len(seg)) ** 2 for x in seg) / len(seg)) ** 0.5
        b['band_up'] = 2 * sd
        b['band_dn'] = -2 * sd
    return bars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--template-dir', default=os.path.join(HERE, 'templates'))
    ap.add_argument('--assets', default=os.path.join(HERE, 'assets', 'echarts.min.js'))
    ap.add_argument('--anomalies', default=None)
    ap.add_argument('--case', default=None)
    a = ap.parse_args()

    data = C.jload(a.data)
    case = C.jload(a.case) if a.case else {}
    anom = C.jload(a.anomalies) if a.anomalies and os.path.exists(a.anomalies) else {}

    data['sensitivity'] = build_sensitivity(data, case)
    bars = build_anomaly_bars(anom, data['price'])
    data['anomaly_bars'] = compute_bands(bars)
    # 异动簇是在全历史上聚类得到的，只保留落在研究窗口内的
    w0 = data['meta']['window']['start']
    w1 = data['meta']['window']['end']
    data['anomaly_clusters'] = [c for c in anom.get('clusters', []) if w0 <= c['start_date'] <= w1]
    data['phases'] = anom.get('phases', [])
    data['narrative']['rehab_caveat'] = (
        '现货为生意社甲醇指数口径（含税、现汇参考价），不是太仓单一库区出罐价；'
        '期货为主连口径，9/29—9/30 由 MA2610 切换至 MA2701，跨切换日比较主连会失真。'
        '若要对外报价，必须改用当日实际库区成交价并注明批量与付款方式。')

    tpl = os.path.join(a.template_dir)
    css = open(os.path.join(tpl, 'style.css'), encoding='utf-8').read()
    body = open(os.path.join(tpl, 'body.html'), encoding='utf-8').read()
    js = open(os.path.join(tpl, 'app.js'), encoding='utf-8').read()
    ech = open(a.assets, encoding='utf-8').read() if os.path.exists(a.assets) else ''
    if not ech:
        print('!! 未找到 echarts.min.js，图表将不可用：', a.assets)

    meta = data['meta']
    case_meta = meta.get('case', {})
    title = case_meta.get('title') or ('%s 行情归因' % case_meta.get('product', ''))
    body = (body.replace('__TITLE__', esc(title))
                .replace('__SUBTITLE__', esc(data['narrative'].get('subtitle', '')))
                .replace('__PRODUCT__', esc(case_meta.get('product', '')))
                .replace('__SPEC__', esc(case_meta.get('spec', '')))
                .replace('__MARKET__', esc(case_meta.get('market', '')))
                .replace('__D0__', esc(meta['window']['start']))
                .replace('__D1__', esc(meta['window']['end']))
                .replace('__ASOF__', esc(meta['window'].get('asof', meta['window']['end'])))
                .replace('__GENERATED__', esc(meta['generated'])))

    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    html = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>%s</title>\n'
        '<style>\n%s\n</style>\n</head>\n<body>\n%s\n'
        '<script>%s</script>\n'
        '<script>window.__REPORT__=%s;</script>\n'
        '<script>%s</script>\n</body>\n</html>\n'
    ) % (esc(title), css, body, ech, payload, js)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(html)
    kb = len(html.encode('utf-8')) / 1024.0
    print('HTML 已生成 -> %s （%.0f KB，ECharts %s）' % (a.out, kb, '已内联' if ech else '缺失'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
