#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the interactive basis dashboard (single self-contained HTML file).

No external assets, no CDN: charts are hand-drawn SVG, all JS is inline, so the
file opens offline and survives being zipped and moved.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, 'build')
OUT = os.path.join(ROOT, 'out', 'basis_report.html')

SURFACE = '#151b24'
BG = '#0d1117'
LINE = '#26303d'
DIM = '#8b98a5'
ACC = '#39d0d8'
ACC2 = '#f7b731'


def load(name):
    with open(os.path.join(BUILD, name), encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def loadj(name):
    with open(os.path.join(BUILD, name), encoding='utf-8') as f:
        return json.load(f)


CSS = """
:root{
 --bg:#0d1117;--panel:#151b24;--panel2:#1b2430;--line:#26303d;--ink:#e6edf3;--dim:#8b98a5;
 --acc:#39d0d8;--acc2:#f7b731;--up:#ff5f6d;--down:#2ea97d;--warn:#ffb020;--grid:#222c38;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 "Microsoft YaHei","PingFang SC",system-ui,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:22px 20px 60px}
header{border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:18px}
h1{font-size:22px;margin:0 0 6px;letter-spacing:.4px}
h1 small{font-size:13px;color:var(--dim);font-weight:400;margin-left:8px}
h2{font-size:16px;margin:30px 0 10px;padding-left:9px;border-left:3px solid var(--acc)}
h3{font-size:14px;margin:18px 0 8px;color:var(--ink)}
.sub{color:var(--dim);font-size:12.5px}
.row{display:flex;gap:14px;flex-wrap:wrap}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi{flex:1 1 200px;min-width:200px}
.kpi .lab{color:var(--dim);font-size:12px}
.kpi .val{font-size:27px;font-weight:700;letter-spacing:.5px;margin-top:2px}
.kpi .val small{font-size:13px;font-weight:400;color:var(--dim)}
.kpi .note{font-size:11.5px;color:var(--dim);margin-top:4px;line-height:1.45}
.up{color:var(--up)}.down{color:var(--down)}.warn{color:var(--warn)}.acc{color:var(--acc)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:600;background:var(--panel2)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:20px;border:1px solid var(--line);color:var(--dim);margin-right:4px}
.tag.y{color:var(--down);border-color:#25543f}
.tag.n{color:var(--up);border-color:#5a2b32}
.tag.u{color:var(--warn);border-color:#5b4a1d}
.banner{background:linear-gradient(90deg,#2a1d1d,#1a2330);border:1px solid #5a3b3b;border-radius:10px;padding:12px 16px;margin:16px 0}
.banner b{color:#ffb3b3}
.chart{width:100%;height:auto;display:block}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--dim);margin:6px 0 0}
.legend i{display:inline-block;width:16px;height:3px;vertical-align:middle;margin-right:5px}
.btns{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 10px}
.btn{background:var(--panel2);border:1px solid var(--line);color:var(--dim);padding:5px 12px;border-radius:7px;cursor:pointer;font-size:12.5px}
.btn.on{background:#12363a;border-color:var(--acc);color:var(--acc)}
code{background:#0b1017;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12px;color:#9fe8ec}
.foot{margin-top:34px;border-top:1px solid var(--line);padding-top:14px;color:var(--dim);font-size:11.5px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:900px){.grid2{grid-template-columns:1fr}}
"""


def svg_line(points, w=1180, h=300, pad=(46, 18, 30, 56), color='#39d0d8', fill='rgba(57,208,216,.13)',
             zero=None, dots=None):
    """points: list of (label, value). Returns inline SVG string."""
    pt, pr, pb, pl = pad
    xs = list(range(len(points)))
    vals = [p[1] for p in points]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    lo -= span * 0.12
    hi += span * 0.12
    if zero is not None:
        lo = min(lo, zero)
        hi = max(hi, zero)

    def X(i):
        return pl + (w - pl - pr) * (i / max(len(points) - 1, 1))

    def Y(v):
        return pt + (h - pt - pb) * (1 - (v - lo) / (hi - lo))

    path = ' '.join(('M' if i == 0 else 'L') + '%.1f,%.1f' % (X(i), Y(v)) for i, v in enumerate(vals))
    area = path + ' L%.1f,%.1f L%.1f,%.1f Z' % (X(len(vals) - 1), h - pb, X(0), h - pb)
    s = ['<svg viewBox="0 0 %d %d" class="chart" preserveAspectRatio="none">' % (w, h)]
    for g in range(5):
        v = lo + (hi - lo) * g / 4
        y = Y(v)
        s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#222c38"/>' % (pl, y, w - pr, y))
        s.append('<text x="%d" y="%.1f" fill="#8b98a5" font-size="10" text-anchor="end" '
                 'dominant-baseline="middle">%s</text>' % (pl - 6, y, ('%.2f' % v) if abs(v) < 10 else '%.0f' % v))
    if zero is not None and lo <= zero <= hi:
        s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#5a6b7d" stroke-dasharray="4 3"/>'
                 % (pl, Y(zero), w - pr, Y(zero)))
    s.append('<path d="%s" fill="%s" stroke="none"/>' % (area, fill))
    s.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (path, color))
    if dots:
        for i in dots:
            s.append('<circle cx="%.1f" cy="%.1f" r="3" fill="%s"/>' % (X(i), Y(vals[i]), color))
    step = max(1, len(points) // 7)
    for i in range(0, len(points), step):
        s.append('<text x="%.1f" y="%d" fill="#8b98a5" font-size="10" text-anchor="middle">%s</text>'
                 % (X(i), h - pb + 15, points[i][0][5:]))
    s.append('</svg>')
    return ''.join(s)


def svg_dual(dates, spot, fut, w=1180, h=330):
    """Two-series SVG with two y scales (spot vs futures)."""
    pt, pr, pb, pl = 20, 62, 32, 56
    allv = [v for v in spot + fut if v is not None]
    lo, hi = min(allv), max(allv)
    pad = (hi - lo) * 0.12 or 1
    lo, hi = lo - pad, hi + pad

    def Y(v):
        return pt + (h - pt - pb) * (1 - (v - lo) / (hi - lo))

    def X(i):
        return pl + (w - pl - pr) * (i / max(len(dates) - 1, 1))

    s = ['<svg viewBox="0 0 %d %d" class="chart">' % (w, h)]
    for g in range(6):
        v = lo + (hi - lo) * g / 5
        y = Y(v)
        s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#222c38"/>' % (pl, y, w - pr, y))
        s.append('<text x="%d" y="%.1f" fill="#8b98a5" font-size="10" text-anchor="end" '
                 'dominant-baseline="middle">%.0f</text>' % (pl - 6, y, v))
    for series, col in ((spot, '#f7b731'), (fut, '#39d0d8')):
        pts = [(i, v) for i, v in enumerate(series) if v is not None]
        if len(pts) > 1:
            d = ' '.join(('M' if k == 0 else 'L') + '%.1f,%.1f' % (X(i), Y(v)) for k, (i, v) in enumerate(pts))
            s.append('<path d="%s" fill="none" stroke="%s" stroke-width="2.2"/>' % (d, col))
        for i, v in pts:
            s.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="%s"/>' % (X(i), Y(v), col))
    step = max(1, len(dates) // 8)
    for i in range(0, len(dates), step):
        s.append('<text x="%.1f" y="%d" fill="#8b98a5" font-size="10" text-anchor="middle">%s</text>'
                 % (X(i), h - pb + 16, dates[i][5:]))
    s.append('</svg>')
    return ''.join(s)


def hist_bars(values, cur, w=560, h=200, bins=8):
    """Histogram of the (tiny) usable sample, with current value marked."""
    pt, pr, pb, pl = 16, 12, 26, 34
    lo, hi = min(values + [cur]), max(values + [cur])
    if hi == lo:
        hi = lo + 1
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        k = min(int((v - lo) / width), bins - 1)
        counts[k] += 1
    mx = max(counts) or 1
    s = ['<svg viewBox="0 0 %d %d" class="chart">' % (w, h)]
    bw = (w - pl - pr) / bins
    for k, c in enumerate(counts):
        bh = (h - pt - pb) * (c / mx)
        x = pl + k * bw + 2
        s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="#1f4b52" stroke="#2d6b74"/>'
                 % (x, h - pb - bh, bw - 4, max(bh, 1)))
        if c:
            s.append('<text x="%.1f" y="%.1f" fill="#8b98a5" font-size="9" text-anchor="middle">%d</text>'
                     % (x + (bw - 4) / 2, h - pb - bh - 3, c))
    for k in range(0, bins + 1, max(1, bins // 4)):
        v = lo + width * k
        s.append('<text x="%.1f" y="%d" fill="#8b98a5" font-size="9" text-anchor="middle">%.0f</text>'
                 % (pl + k * bw, h - pb + 14, v))
    cx = pl + (cur - lo) / (hi - lo) * (w - pl - pr)
    s.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#ff5f6d" stroke-width="2"/>'
             % (cx, pt, cx, h - pb))
    s.append('<text x="%.1f" y="%d" fill="#ff5f6d" font-size="10" text-anchor="middle">当前 %.0f</text>'
             % (cx, pt - 4, cur))
    s.append('</svg>')
    return ''.join(s)



JS_ENGINE = r"""
function fmt(n, d){ return (n>0?'+':'') + n.toLocaleString('zh-CN',{minimumFractionDigits:d||0,maximumFractionDigits:d||0}); }
function fmtU(n){ return n.toLocaleString('zh-CN'); }

/* 用与 Python 端 svg_line 相同的几何规则在前端重绘 */
function drawLine(pts, color, fill){
  const W=1180,H=300,pt=46,pr=18,pb=30,pl=56;
  const vals=pts.map(p=>p.v);
  let lo=Math.min(...vals,0), hi=Math.max(...vals,0);
  const span=(hi-lo)||1; lo-=span*0.12; hi+=span*0.12;
  const X=i=>pl+(W-pl-pr)*(i/Math.max(pts.length-1,1));
  const Y=v=>pt+(H-pt-pb)*(1-(v-lo)/(hi-lo));
  let s='<svg viewBox="0 0 '+W+' '+H+'" class="chart" preserveAspectRatio="none">';
  for(let g=0;g<5;g++){
    const v=lo+(hi-lo)*g/4, y=Y(v);
    s+='<line x1="'+pl+'" y1="'+y.toFixed(1)+'" x2="'+(W-pr)+'" y2="'+y.toFixed(1)+'" stroke="#222c38"/>';
    s+='<text x="'+(pl-6)+'" y="'+y.toFixed(1)+'" fill="#8b98a5" font-size="10" text-anchor="end" dominant-baseline="middle">'+v.toFixed(0)+'</text>';
  }
  if(lo<=0&&hi>=0){ s+='<line x1="'+pl+'" y1="'+Y(0).toFixed(1)+'" x2="'+(W-pr)+'" y2="'+Y(0).toFixed(1)+'" stroke="#5a6b7d" stroke-dasharray="4 3"/>'; }
  let d='';
  pts.forEach((p,i)=>{ d+=(i===0?'M':'L')+X(i).toFixed(1)+','+Y(p.v).toFixed(1); });
  s+='<path d="'+d+' L'+X(pts.length-1).toFixed(1)+','+(H-pb)+' L'+X(0).toFixed(1)+','+(H-pb)+' Z" fill="'+fill+'" stroke="none"/>';
  s+='<path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2"/>';
  [0,pts.length-1].forEach(i=>{ s+='<circle cx="'+X(i).toFixed(1)+'" cy="'+Y(pts[i].v).toFixed(1)+'" r="3" fill="'+color+'"/>'; });
  const step=Math.max(1,Math.floor(pts.length/7));
  for(let i=0;i<pts.length;i+=step){
    s+='<text x="'+X(i).toFixed(1)+'" y="'+(H-pb+15)+'" fill="#8b98a5" font-size="10" text-anchor="middle">'+pts[i].d.slice(5)+'</text>';
  }
  return s+'</svg>';
}

function selectContract(ct){
  document.querySelectorAll('#ctl-contract .btn').forEach(b=>{
    b.classList.toggle('on', b.dataset.ct===ct);
  });
  const bs=DATA.basisByContract[ct]||[];
  const cl=DATA.closeByContract[ct]||[];
  document.getElementById('basis-chart').innerHTML=drawLine(bs,'#39d0d8','rgba(57,208,216,.13)');
  // 同步首屏基差卡
  const lastB=bs.length?bs[bs.length-1].v:null;
  const lastC=cl.length?cl[cl.length-1].v:null;
  document.getElementById('kpi-ct').textContent=ct;
  if(lastB!==null){
    document.getElementById('kpi-basis').innerHTML=fmt(lastB)+'<small> 元/吨</small>';
    document.getElementById('kpi-basis-note').textContent=
      '现货 '+fmtU(DATA.spotNow)+' − 期货 '+fmtU(lastC)+'；基差率 '+(lastB/DATA.spotNow*100).toFixed(2)+'%';
  }
  const mn=Math.min(...bs.map(p=>p.v)), mx=Math.max(...bs.map(p=>p.v));
  document.getElementById('basis-readout').textContent=
    ct+' 口径：区间 '+fmt(mn)+' ~ '+fmt(mx)+' 元/吨；最新 '+fmt(lastB)+
    '；真实样本 '+bs.length+' 个（不足 20 个，不给历史分位）';
}

document.querySelectorAll('#ctl-contract .btn').forEach(b=>{
  b.addEventListener('click',()=>selectContract(b.dataset.ct));
});

/* 历史极值：点击展开当时的产业背景 */
document.querySelectorAll('tr[data-ex]').forEach(tr=>{
  tr.style.cursor='pointer';
  tr.addEventListener('click',()=>{
    const i=+tr.dataset.ex, e=DATA.extremes[i], box=document.getElementById('ex-detail');
    box.style.display='block';
    box.innerHTML='<b>'+e.date+'</b>（MA 主连收盘 '+fmtU(e.close)+'，来源 '+e.src+'）<br>'
      +'<b>当时背景：</b>'+e.bg+'<br><b>后续：</b>'+e.after;
  });
});
selectContract('MA2701');"""



def main():
    sys.stdout.reconfigure(encoding='utf-8')
    A = loadj('analysis.json')
    basis = load('raw_basis.csv')
    inv = load('raw_inventory.csv')
    ev = load('raw_events.csv')
    ex = load('raw_extremes.csv')
    src = load('raw_sources.csv')
    gaps = loadj('gaps.json')
    rec = load('raw_receipts.csv')
    adj = load('main_continuous_adj.csv')

    dates = [r['date'] for r in basis]
    spot = [float(r['spot_mid']) for r in basis]
    fut = [float(r['main_close']) for r in basis]
    series = [(p['date'], p['basis']) for p in A['series']]

    w1 = A['windows']['1Y']
    dec = A['decompose_30d']
    decp = A['decompose_peak']
    ct = A['contracts']

    port = [(r['date'], float(r['value_wan_ton'])) for r in inv
            if r['item'].startswith('\u6e2f\u53e3')]
    rec_pts = [(r['date'], float(r['receipt_total'])) for r in rec]

    rows_ct = ''.join('<tr><td>%s</td><td class="num">%.0f</td><td class="num">%+.0f</td>'
                      '<td class="num">%.2f%%</td></tr>'
                      % (k, v['close'], v['basis'], v['basis_rate']) for k, v in ct.items())
    rows_inv = ''.join('<tr><td>%s</td><td>%s</td><td class="num">%.2f</td><td class="num">%s</td>'
                       '<td>%s</td><td>%s</td></tr>'
                       % (r['date'], r['item'], float(r['value_wan_ton']),
                          ('%+.2f' % float(r['chg_wan_ton'])) if r['chg_wan_ton'] else '—',
                          r['note'], r['source_id']) for r in inv)
    rows_rec = ''.join('<tr><td>%s</td><td class="num">%.0f</td><td class="num">%s</td>'
                       '<td class="num">%.0f</td><td class="num">%.0f</td></tr>'
                       % (r['date'], float(r['receipt_total']),
                          ('%+.0f' % float(r['receipt_chg'])) if r['receipt_chg'] else '0',
                          float(r['warehouse_receipts']), float(r['factory_receipts']))
                       for r in rec)
    rows_ev = ''.join('<tr><td>%s</td><td><span class="tag">%s</span></td><td>%s</td><td>%s</td>'
                      '<td class="num">%s</td></tr>'
                      % (r['date'], r['category'], r['event'], r['bearing_on_basis'],
                         r['source_id']) for r in ev)
    rows_ex = ''.join('<tr data-ex="%d" title="点击查看当时产业背景"><td>%s</td>'
                      '<td class="num">%.0f</td><td>%s</td><td>%s</td><td class="num">%s</td></tr>'
                      % (i, r['date'], float(r['ma0_close']), r['background'],
                         r['aftermath'], r['source_id']) for i, r in enumerate(ex))
    rows_src = ''.join('<tr><td>%s</td><td>%s</td><td style="word-break:break-all">%s</td>'
                       '<td>%s</td><td>%s</td></tr>'
                       % (r['id'], r['title'], r['url'], r['publisher'], r['retrieved'])
                       for r in src)
    rows_gap = ''.join('<li><b>%s</b>：%s</li>' % (k, v) for k, v in gaps.items())

    rolls = [r for r in adj if r['switch']]
    rows_roll = ''.join('<tr><td>%s</td><td>%s</td><td class="num">%s</td><td class="num">%s</td></tr>'
                        % (r['date'], r['switch'],
                           ('%+.0f' % float(r['roll_gap'])) if r['roll_gap'] else '—',
                           ('%+.0f' % float(r['roll_shift'])) if r['roll_shift'] else '—')
                        for r in rolls)

    ct_series, ct_close = {}, {}
    for ck in ('MA2611', 'MA2612', 'MA2701'):
        pts = [{'d': r['date'], 'v': float(r['basis_' + ck])}
               for r in basis if r.get('basis_' + ck)]
        if pts:
            ct_series[ck] = pts
        pts2 = [{'d': r['date'], 'v': float(r['close_' + ck])}
                for r in basis if r.get('close_' + ck)]
        if pts2:
            ct_close[ck] = pts2
    payload = {
        'asof': A['asof'],
        'spotNow': A['spot_now'],
        'basisByContract': ct_series,
        'closeByContract': ct_close,
        'extremes': [{'date': r['date'], 'close': float(r['ma0_close']), 'bg': r['background'],
                      'after': r['aftermath'], 'src': r['source_id']} for r in ex],
    }

    basis_pts = series
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>\u592a\u4ed3\u7532\u9187\u57fa\u5dee\u7814\u7a76\u62a5\u544a \u00b7 {A['asof']}</title>
<style>{CSS}</style></head>
<body><div class="wrap">

<header>
  <h1>\u534e\u4e1c\u7532\u9187\uff08\u592a\u4ed3\uff09\u00b7 \u90d1\u5546\u6240 MA \u57fa\u5dee\u7814\u7a76<small>\u6570\u636e\u622a\u81f3 {A['asof']} \u6536\u76d8</small></h1>
  <div class="sub">
    \u57fa\u5dee\u53e3\u5f84\uff1a<b>\u57fa\u5dee = \u73b0\u8d27\u4ef7\u683c \u2212 \u671f\u8d27\u4ef7\u683c</b>\uff1b
    \u73b0\u8d27\uff1d\u9686\u4f17\u8d44\u8baf\u300c\u6c5f\u82cf\u592a\u4ed3 \u7532\u9187 \u51fa\u7f50 \u73b0\u6c47 \u542b\u7a0e\uff08GB/T 338-2011 \u4f18\u7b49\u54c1\uff09\u300d\uff1b
    \u671f\u8d27\uff1d\u90d1\u5546\u6240 MA \u5408\u7ea6\u6536\u76d8\u4ef7\u3002\u5355\u4f4d\uff1a\u5143/\u5428\u3002
  </div>
</header>

<div class="row">
  <div class="card kpi">
    <div class="lab">\u5f53\u524d\u57fa\u5dee\uff08<span id="kpi-ct">{A['main_contract']}</span>\uff09</div>
    <div class="val acc" id="kpi-basis">{A['basis_now']:+,.0f}<small> \u5143/\u5428</small></div>
    <div class="note" id="kpi-basis-note">\u73b0\u8d27 {A['spot_now']:,.0f} \u2212 \u671f\u8d27 {A['main_close']:,.0f}\uff1b\u57fa\u5dee\u7387 {A['basis_rate_now']:.2f}%</div>
  </div>
  <div class="card kpi">
    <div class="lab">\u8fd1 {dec['span_trading_days']} \u4e2a\u4ea4\u6613\u65e5\u53d8\u5316</div>
    <div class="val down">{dec['delta_basis']:+,.0f}<small> \u5143/\u5428</small></div>
    <div class="note">{dec['from_date']} \u2192 {dec['to_date']}\uff1b\u73b0\u8d27\u8d21\u732e {dec['share_spot']:+.0f}%\u3001\u671f\u8d27\u8d21\u732e {dec['share_fut']:+.0f}%</div>
  </div>
  <div class="card kpi">
    <div class="lab">\u53ef\u7528\u6837\u672c\u5206\u4f4d\uff08\u975e\u5386\u53f2\u5206\u4f4d\uff09</div>
    <div class="val warn">{w1['pct']:.0f}<small> % / n={w1['n']}</small></div>
    <div class="note">\u4ec5 {A['series'][0]['date']}~{A['asof']} \u7684\u771f\u5b9e\u6837\u672c\uff0c<b>\u4e0d\u53ef\u5f53\u4f5c 1/3/5 \u5e74\u5386\u53f2\u5206\u4f4d</b></div>
  </div>
  <div class="card kpi">
    <div class="lab">\u533a\u95f4\u5cf0\u503c\u57fa\u5dee</div>
    <div class="val up">+{A['peak_basis'][1]:,.0f}<small> \u5143/\u5428</small></div>
    <div class="note">{A['peak_basis'][0]}\uff1b\u8f83\u5cf0\u503c\u5df2\u56de\u843d {decp['delta_basis']:+,.0f}</div>
  </div>
</div>

<div class="banner">
  <b>\u5173\u4e8e\u300c\u6781\u7aef\u5206\u4f4d\u662f\u5426\u5fc5\u7136\u56de\u5f52\u300d</b>\u2014\u2014\u672c\u62a5\u544a\u4e0d\u4f5c\u6b64\u5224\u65ad\u3002\u5f53\u524d\u57fa\u5dee\u5904\u4e8e
  <b>\u6df1\u5ea6\u6b63\u57fa\u5dee\uff08\u73b0\u8d27\u5347\u6c34\uff09</b>\u72b6\u6001\uff0c\u4e14\u6709\u53ef\u6838\u67e5\u7684\u4ea7\u4e1a\u4e8b\u5b9e\u652f\u6491\uff08\u89c1\u7b2c 5 \u8282\uff09\u3002
  \u540c\u65f6\u5fc5\u987b\u63d0\u793a\uff1a{A['limits']['reason']}
</div>

<h2>1 \u00b7 \u73b0\u8d27\u4e0e\u671f\u8d27\u4ef7\u683c\u53cc\u8f74\u5bf9\u7167</h2>
<div class="card">
{svg_dual(dates, spot, fut)}
<div class="legend"><span><i style="background:{ACC2}"></i>\u592a\u4ed3\u73b0\u8d27\uff08\u9686\u4f17\uff0c\u51fa\u7f50\u542b\u7a0e\uff09</span>
<span><i style="background:{ACC}"></i>{A['main_contract']} \u6536\u76d8</span></div>
<div class="sub" style="margin-top:8px">
  10-08/10-09 \u53cc\u8282\u540e\u8df3\u6da8\uff08\u73b0\u8d27 4,725 \u2192 4,875\uff09\uff1b10-12 \u6cbf\u6d77 MTO \u96c6\u4e2d\u505c\u8f66\u5f15\u53d1\u8d1f\u53cd\u9988\uff0c
  \u73b0\u8d27 6 \u4e2a\u4ea4\u6613\u65e5\u56de\u843d\u7ea6 880 \u5143/\u5428\uff0c\u671f\u8d27\u540c\u671f\u4ec5\u56de\u843d\u7ea6 180 \u5143/\u5428\u3002
</div>
</div>

<h2>2 \u00b7 \u57fa\u5dee\u66f2\u7ebf\uff08\u53ef\u5207\u6362\u5408\u7ea6\u53e3\u5f84\uff09</h2>
<div class="card">
<div class="btns" id="ctl-contract">
  <span class="sub" style="align-self:center;margin-right:6px">\u671f\u8d27\u5408\u7ea6\uff1a</span>
  <button class="btn on" data-ct="MA2701">MA2701 \u4e3b\u529b</button>
  <button class="btn" data-ct="MA2612">MA2612</button>
  <button class="btn" data-ct="MA2611">MA2611 \u8fd1\u6708</button>
</div>
<div id="basis-chart">{svg_line(basis_pts, zero=0, dots=[0, len(basis_pts) - 1])}</div>
<div id="basis-readout" class="sub" style="margin-top:8px"></div>
<div class="sub" style="margin-top:4px">
  \u6ce8\uff1a\u9ed8\u8ba4\u66f2\u7ebf\u4e3a\u56fa\u5b9a\u5408\u7ea6 {A['main_contract']}\uff1b\u6362\u6708\u4ef7\u5dee\u5df2\u5728\u7b2c 4 \u8282\u5355\u72ec\u91cf\u5316\uff0c\u672a\u6df7\u5165\u672c\u66f2\u7ebf\u3002
  \u5207\u6362\u4e0a\u65b9\u5408\u7ea6\u4f1a\u540c\u6b65\u6539\u5199\u9996\u5c4f\u57fa\u5dee\u5361\u4e0e\u672c\u8282\u8bfb\u6570\u3002
</div>
</div>

<h2>3 \u00b7 \u57fa\u5dee\u53d8\u52a8\u5f52\u56e0</h2>
<div class="grid2">
  <div class="card">
    <h3>\u8fd1 {dec['span_trading_days']} \u4e2a\u4ea4\u6613\u65e5\uff08{dec['from_date']} \u2192 {dec['to_date']}\uff09</h3>
    <table>
      <tr><th>\u9879\u76ee</th><th class="num">\u53d8\u5316</th><th class="num">\u5360\u57fa\u5dee\u53d8\u5316</th></tr>
      <tr><td>\u73b0\u8d27</td><td class="num">{dec['delta_spot']:+,.0f}</td><td class="num">{dec['share_spot']:+.0f}%</td></tr>
      <tr><td>\u671f\u8d27</td><td class="num">{dec['delta_fut']:+,.0f}</td><td class="num">{dec['share_fut']:+.0f}%</td></tr>
      <tr><td><b>\u57fa\u5dee</b></td><td class="num"><b>{dec['delta_basis']:+,.0f}</b></td><td class="num">100%</td></tr>
    </table>
    <div class="sub" style="margin-top:8px">\u0394\u57fa\u5dee = \u0394\u73b0\u8d27 \u2212 \u0394\u671f\u8d27\uff1b\u8d21\u732e\u4ee5 \u0394\u57fa\u5dee \u4e3a\u5206\u6bcd\uff0c\u4e24\u8005\u4e4b\u548c\u6052\u4e3a 100%\u3002</div>
  </div>
  <div class="card">
    <h3>\u5cf0\u503c\u4ee5\u6765\uff08{decp['from_date']} \u2192 {decp['to_date']}\uff09</h3>
    <table>
      <tr><th>\u9879\u76ee</th><th class="num">\u53d8\u5316</th><th class="num">\u5360\u57fa\u5dee\u53d8\u5316</th></tr>
      <tr><td>\u73b0\u8d27</td><td class="num">{decp['delta_spot']:+,.0f}</td><td class="num">{decp['share_spot']:+.0f}%</td></tr>
      <tr><td>\u671f\u8d27</td><td class="num">{decp['delta_fut']:+,.0f}</td><td class="num">{decp['share_fut']:+.0f}%</td></tr>
      <tr><td><b>\u57fa\u5dee</b></td><td class="num"><b>{decp['delta_basis']:+,.0f}</b></td><td class="num">100%</td></tr>
    </table>
    <div class="sub" style="margin-top:8px">\u57fa\u5dee\u56de\u843d\u4e3b\u8981\u7531<b>\u73b0\u8d27\u8865\u8dcc</b>\u5b8c\u6210\uff0c\u800c\u975e\u671f\u8d27\u4e0a\u6da8\u3002</div>
  </div>
</div>

<h2>4 \u00b7 \u5408\u7ea6\u53e3\u5f84\uff1a\u56fa\u5b9a\u5408\u7ea6 vs \u4e3b\u529b\u8fde\u7eed</h2>
<div class="card">
  <table>
    <tr><th>\u5408\u7ea6</th><th class="num">\u6536\u76d8\u4ef7</th><th class="num">\u57fa\u5dee</th><th class="num">\u57fa\u5dee\u7387</th></tr>
    {rows_ct}
  </table>
  <div class="sub" style="margin-top:10px;line-height:1.75">
  <b>\u4e3a\u4ec0\u4e48\u540c\u4e00\u73b0\u8d27\u4f1a\u6709\u4e0d\u540c\u57fa\u5dee\uff1a</b>10-20 \u73b0\u8d27 3,980 \u540c\u65f6\u5bf9\u4e0a\u8fd1\u6708 MA2611\u3001MA2612 \u4e0e\u4e3b\u529b MA2701\uff0c
  \u66f2\u7ebf\u8fd1\u9ad8\u8fdc\u4f4e\uff08\u6df1\u5ea6 Back\uff09\uff0c\u8fd1\u6708\u57fa\u5dee {ct['MA2611']['basis']:+.0f}\u3001\u4e3b\u529b\u57fa\u5dee {A['basis_now']:+.0f}\uff0c
  \u76f8\u5dee {abs(A['basis_now'] - ct['MA2611']['basis']):.0f} \u5143/\u5428\u3002\u9686\u4f17 10-19 \u62a5\u300c\u73b0\u8d27\u5c0f\u5355\u57fa\u5dee +600\uff08\u5bf9 MA2611\uff09\u300d\uff0c
  \u4e0e\u672c\u8868 MA2611 \u53e3\u5f84 {ct['MA2611']['basis']:+.0f} \u76f8\u5dee {abs(ct['MA2611']['basis'] - 600):.0f} \u5143/\u5428\uff08\u65e5\u671f\u5dee\u4e00\u4e2a\u4ea4\u6613\u65e5\uff09\uff0c\u540c\u53e3\u5f84\u53ef\u6bd4\u3002
  \u5916\u90e8\u6838\u9a8c\uff1a\u56fd\u5185\u5546\u54c1\u57fa\u5dee\u62a5\u544a 10-20 \u62a5\u300c\u73b0\u8d27 3980 / \u4e3b\u529b 3157 / \u57fa\u5dee 823 / \u57fa\u5dee\u7387 20.68%\u300d\uff0c\u4e0e\u672c\u62a5\u544a\u5b8c\u5168\u4e00\u81f4\u3002
  </div>
</div>
<div class="card">
  <h3>\u4e3b\u529b\u6362\u6708\u8bb0\u5f55\uff08gap \u4e0e shift \u7684\u533a\u522b\u51b3\u5b9a\u4e86\u590d\u6743\u662f\u5426\u5e72\u51c0\uff09</h3>
  <table>
    <tr><th>\u6362\u6708\u65e5</th><th>\u5207\u6362</th><th class="num">gap\uff08\u5207\u6362\u65e5\u65b0\u65e7\u4e3b\u529b\u5dee\uff09</th>
    <th class="num">shift\uff08\u524d\u4e00\u65e5\u65b0\u65e7\u540c\u65e5\u5dee\uff09</th></tr>
    {rows_roll}
  </table>
  <div class="sub" style="margin-top:8px">
    <b>\u6362\u6708\u5904\u7406\uff1a</b>\u884c\u60c5\u5546\u53d1\u5e03\u7684 MA0 \u4e3b\u8fde\u5728\u6362\u6708\u5f53\u65e5\u4ecd\u6253\u5370<b>\u65e7\u5408\u7ea6</b>\u6536\u76ca\uff0c\u4ef7\u683c\u9636\u68af\u88ab\u63a8\u5230\u6b21\u65e5
    \uff082026-09-11 \u663e\u793a \u221212.07%\uff0c\u800c\u5404\u56fa\u5b9a\u5408\u7ea6\u5f53\u65e5\u5b9e\u9645\u53d8\u52a8\u4ec5 \u22121%~+1%\uff09\u3002\u56e0\u6b64\u590d\u6743\u5fc5\u987b\u6309
    <b>\u540c\u65e5\u4ef7\u5dee shift</b> \u5e73\u79fb\u6362\u6708\u65e5\u4e4b\u524d\u7684\u5168\u90e8\u4ef7\u683c\uff0c\u590d\u6743\u540e\u6362\u6708\u65e5\u6536\u76ca\u7387\u624d\u7b49\u4e8e\u65b0\u5408\u7ea6\u81ea\u8eab\u6536\u76ca\u7387\u3002
    \u672c\u62a5\u544a\u4e3b\u4f53\u66f2\u7ebf\u53ea\u4f7f\u7528\u56fa\u5b9a\u5408\u7ea6\u53e3\u5f84\uff0c\u4e0d\u505a\u8de8\u5408\u7ea6\u62fc\u63a5\u3002
  </div>
</div>

<h2>5 \u00b7 \u57fa\u672c\u9762\u8bc1\u636e\uff1a\u652f\u6301 / \u4e0d\u652f\u6301\u300c\u57fa\u5dee\u5f3a\u52bf\u300d</h2>
<div class="card">
<table>
  <tr><th style="width:70px">\u7ed3\u8bba</th><th>\u8bc1\u636e</th><th>\u65e5\u671f / \u6765\u6e90</th></tr>

  <tr><td><span class="tag y">\u652f\u6301</span></td>
      <td><b>\u6e2f\u53e3\u5e93\u5b58\u5904\u4e8e\u5386\u53f2\u6781\u4f4e\u4f4d\u7f6e\u3002</b>\u9686\u4f17\u53e3\u5f84\u6e2f\u53e3\u5e93\u5b58 2026-07-16 \u8c37\u503c 40.52 \u4e07\u5428\uff0c
          \u4e3a\u8fd1\u4e94\u5e74\u4f4e\u4f4d\uff1b2026-10-09 \u5e02\u573a\u53e3\u5f84\u8fdb\u4e00\u6b65\u964d\u81f3\u7ea6 30 \u4e07\u5428\uff0c\u521b\u5386\u53f2\u65b0\u4f4e\u3002
          \u4f4e\u5e93\u5b58 + \u53ef\u6d41\u901a\u8d27\u6e90\u96c6\u4e2d\uff0c\u662f\u73b0\u8d27\u5347\u6c34\uff08\u6b63\u57fa\u5dee\uff09\u7684\u76f4\u63a5\u539f\u56e0\u3002</td>
      <td>2026-07-16 / 10-09<br>S06 \u00b7 S07</td></tr>

  <tr><td><span class="tag y">\u652f\u6301</span></td>
      <td><b>\u8fdb\u53e3\u901a\u9053\u672a\u6062\u590d\u3002</b>\u4f0a\u6717\u5bf9\u534e\u76f4\u63a5\u8fdb\u53e3\u81ea 2025-11 \u8d77\u8fde\u7eed 9 \u4e2a\u6708\u62a5\u5173\u4e3a\u96f6\uff1b
          \u970d\u5c14\u6728\u5179\u6d77\u5ce1\u901a\u884c\u53d7\u9650\uff0c10 \u6708\u5230\u6e2f\u7ef4\u6301\u4f4e\u4f4d\uff0810-01~10-08 \u5230\u6e2f\u4ec5 6.88 \u4e07\u5428\uff09\u3002</td>
      <td>2026-09 / 10<br>S06 \u00b7 S03</td></tr>

  <tr><td><span class="tag y">\u652f\u6301</span></td>
      <td><b>\u53ef\u4ea4\u5272\u8d44\u6e90\u5168\u90e8\u96c6\u4e2d\u5728\u5382\u5e93\uff0c\u4ed3\u5e93\u4ed3\u5355\u4e3a 0\u3002</b>10-20 \u90d1\u5546\u6240\u7532\u9187\u4ed3\u5355\u603b\u8ba1 6,633 \u5f20\uff0c
          \u5176\u4e2d\u4ed3\u5e93\u53e3\u5f84 <b>0 \u5f20</b>\uff0c\u5168\u90e8\u767b\u8bb0\u5728\u5382\u5e93\uff08\u676d\u5b9e\u5316\u5de5 1,866\u3001\u5b89\u5fbd\u4e2d\u80fd 1,400\u3001\u56fd\u8d38\u77f3\u5316 1,000\u3001
          \u91d1\u6865\u5316\u5de5 900\u3001\u4e2d\u5316\u5316\u9500 600\u3001\u5b9a\u5dde\u5929\u9e6d 600\u3001\u6cb3\u5357\u5fc3\u8fde\u5fc3 267\u3001\u5b89\u5fbd\u660a\u6e90 200\uff09\u3002
          \u592a\u4ed3\u9633\u9e3f\u7b49\u6e2f\u53e3\u4ed3\u5e93\u4ed3\u5355\u4e3a 0\uff0c\u610f\u5473\u7740\u201c\u4e70\u671f\u8d27\u4ea4\u5272\u62ff\u8d27\u201d\u5728\u592a\u4ed3\u51e0\u4e4e\u4e0d\u53ef\u884c\uff0c\u73b0\u8d27\u7aef\u5fc5\u987b\u4ed8\u5347\u6c34\u3002</td>
      <td>2026-10-20<br>S01</td></tr>

  <tr><td><span class="tag y">\u652f\u6301</span></td>
      <td><b>\u592a\u4ed3\u4e3a\u57fa\u51c6\u4ea4\u5272\u5730\u3001\u5347\u8d34\u6c34 0\u3002</b>\u592a\u4ed3\u9633\u9e3f\u77f3\u5316\uff08\u4ed3\u5e93 0801\uff09\u671f\u8d27\u5347\u8d34\u6c34 0 \u5143/\u5428\uff0c
          \u6545\u592a\u4ed3\u73b0\u8d27\u4e0e\u671f\u8d27\u6807\u7684\u5728\u5730\u533a\u3001\u54c1\u8d28\u4e0a\u53ef\u76f4\u63a5\u5bf9\u6bd4\uff0c\u57fa\u5dee\u4e0d\u542b\u8de8\u533a\u8d34\u6c34\u4fee\u6b63\u3002</td>
      <td>2025-03-26<br>S16</td></tr>

  <tr><td><span class="tag n">\u4e0d\u652f\u6301</span></td>
      <td><b>\u53bb\u5e93\u5df2\u8f6c\u4e3a\u7d2f\u5e93\u3002</b>\u6e2f\u53e3\u5e93\u5b58\u81ea\u4f4e\u4f4d\u56de\u5347\uff1a10-14 \u4e3a 36.72 \u4e07\u5428\uff08+6.21\uff0c+20.35%\uff09\uff0c
          \u53e6\u7ec8\u7aef\u53e3\u5f84 10-15 \u4e3a 41.33 \u4e07\u5428\uff08+3.92\uff0c+10.48%\uff09\u3002\u53bb\u5e93\u53d9\u4e8b\u88ab\u6253\u7834\uff0c
          \u662f\u57fa\u5dee\u4ece 1,537 \u56de\u843d\u81f3 823 \u7684\u76f4\u63a5\u89e6\u53d1\u56e0\u7d20\u3002</td>
      <td>2026-10-14 / 10-15<br>S04 \u00b7 S07</td></tr>

  <tr><td><span class="tag n">\u4e0d\u652f\u6301</span></td>
      <td><b>\u9700\u6c42\u8d1f\u53cd\u9988\u6b63\u5728\u5b9e\u73b0\u3002</b>\u6cbf\u6d77 MTO \u56e0\u9ad8\u4ef7\u7532\u9187\u96c6\u4e2d\u505c\u8f66\uff08\u4e1a\u5185\u201c\u7f55\u89c1\u5168\u7ebf\u505c\u8f66\u201d\uff09\uff0c
          MTO \u884c\u4e1a\u5f00\u5de5\u7387\u7531 6 \u6708\u6708\u5747 82.05% \u964d\u81f3 10 \u6708\u9884\u671f 73.50%\u3002\u9700\u6c42\u7aef\u524a\u5f31\u4f1a\u540c\u65f6\u538b\u4f4e\u73b0\u8d27\u4e0e\u57fa\u5dee\u3002</td>
      <td>2026-10-12 / 10-18<br>S12 \u00b7 S04</td></tr>

  <tr><td><span class="tag n">\u4e0d\u652f\u6301</span></td>
      <td><b>\u4ed3\u5355\u5728\u589e\u52a0\u3002</b>\u4ed3\u5355\u7531 10-12 \u7684 5,216 \u5f20\u589e\u81f3 10-19 \u7684 7,083 \u5f20\uff08+1,867 \u5f20\uff0c\u7ea6 1.87 \u4e07\u5428\uff09\uff0c
          10-20 \u56de\u843d\u81f3 6,633 \u5f20\u3002\u4ed3\u5355\u56de\u5347\u610f\u5473\u7740\u53ef\u4ea4\u5272\u8d44\u6e90\u5728\u88ab\u751f\u4ea7\u51fa\u6765\uff0c\u5bf9\u8fd1\u6708\u5347\u6c34\u6784\u6210\u538b\u529b\u3002</td>
      <td>2026-10-12 ~ 10-20<br>S01</td></tr>

  <tr><td><span class="tag n">\u4e0d\u652f\u6301</span></td>
      <td><b>\u73b0\u8d27\u81ea\u8eab\u5728\u8865\u8dcc\u3002</b>\u8fd1 {dec['span_trading_days']} \u4e2a\u4ea4\u6613\u65e5\u57fa\u5dee {dec['delta_basis']:+.0f} \u5143/\u5428\u4e2d\uff0c
          \u73b0\u8d27\u8d21\u732e {dec['share_spot']:+.0f}%\uff08\u73b0\u8d27 {dec['delta_spot']:+.0f}\u3001\u671f\u8d27 {dec['delta_fut']:+.0f}\uff09\uff1b
          \u5cf0\u503c\u4ee5\u6765\u57fa\u5dee {decp['delta_basis']:+.0f} \u5143/\u5428\u4e2d\u73b0\u8d27\u8d21\u732e {decp['share_spot']:+.0f}%\u3002
          \u57fa\u5dee\u4fee\u590d\u4e3b\u8981\u7531\u73b0\u8d27\u4e0b\u8dcc\u5b8c\u6210\uff0c\u8bf4\u660e\u201c\u73b0\u8d27\u575a\u633a\u201d\u5728\u51cf\u5f31\u3002</td>
      <td>{dec['from_date']} ~ {dec['to_date']}<br>D03</td></tr>

  <tr><td><span class="tag u">\u5b58\u7591</span></td>
      <td><b>\u4e24\u5957\u6e2f\u53e3\u5e93\u5b58\u53e3\u5f84\u3001\u4e24\u4e2a\u66f4\u65b0\u65e5\u4e0d\u4e00\u81f4\u3002</b>10-14 \u7684 36.72 \u4e07\u5428\uff08+6.21\uff09\u4e0e 10-15 \u7684 41.33 \u4e07\u5428\uff08+3.92\uff09
          \u6765\u81ea\u4e0d\u540c\u7ec8\u7aef\u8f6c\u8ff0\uff0c\u6570\u503c\u4e0d\u53ef\u4e92\u6362\u3001\u4e5f\u4e0d\u53ef\u76f8\u51cf\u5f97\u51fa\u201c\u4e00\u65e5\u589e 4.6 \u4e07\u5428\u201d\u3002\u672c\u62a5\u544a\u5e76\u5217\u5448\u73b0\uff0c\u4e0d\u5408\u5e76\u3002</td>
      <td>2026-10-14 / 10-15<br>S04 \u00b7 S07</td></tr>

  <tr><td><span class="tag u">\u5b58\u7591</span></td>
      <td><b>\u5386\u53f2\u5206\u4f4d\u65e0\u6cd5\u53ef\u9760\u8ba1\u7b97\u3002</b>\u73b0\u8d27\u65e5\u5ea6\u5e8f\u5217\u4ec5 {w1['n']} \u4e2a\u771f\u5b9e\u6709\u4ef7\u65e5\uff08{A['series'][0]['date']} \u8d77\uff09\uff0c
          \u4e14\u5168\u90e8\u843d\u5728\u540c\u4e00\u6b21\u6781\u7aef\u884c\u60c5\u5185\u3002\u4efb\u4f55\u201c\u5904\u4e8e 1/3/5 \u5e74 X% \u5206\u4f4d\u201d\u7684\u8bf4\u6cd5\u76ee\u524d\u90fd\u4e0d\u53ef\u9a8c\u8bc1\u3002</td>
      <td>\u2014<br>D03</td></tr>
</table>
</div>

<h2>6 \u00b7 \u5e93\u5b58\u4e0e\u4ed3\u5355</h2>
<div class="grid2">
  <div class="card">
    <h3>\u6e2f\u53e3\u5e93\u5b58\uff08\u9686\u4f17\u53e3\u5f84\uff0c\u4e07\u5428\uff09</h3>
    {svg_line(port, w=560, h=220, color=ACC2, fill='rgba(247,183,49,.12)')}
    <div class="sub" style="margin-top:6px">\u4ec5\u5173\u952e\u65f6\u70b9\u503c\uff0c\u975e\u8fde\u7eed\u5468\u5ea6\u5e8f\u5217\u3002</div>
  </div>
  <div class="card">
    <h3>\u90d1\u5546\u6240\u7532\u9187\u4ed3\u5355\uff08\u5f20\uff09</h3>
    {svg_line(rec_pts, w=560, h=220, dots=[0, len(rec_pts) - 1])}
    <div class="sub" style="margin-top:6px">10-12 \u4f4e\u70b9 5,216 \u2192 10-19 \u9ad8\u70b9 7,083 \u2192 10-20 \u56de\u843d 6,633\u3002</div>
  </div>
</div>
<div class="card">
  <h3>\u5e93\u5b58\u660e\u7ec6</h3>
  <table><tr><th>\u65e5\u671f</th><th>\u9879\u76ee</th><th class="num">\u4e07\u5428</th><th class="num">\u53d8\u5316</th><th>\u5907\u6ce8</th><th>\u6765\u6e90</th></tr>
  {rows_inv}</table>
</div>
<div class="card">
  <h3>\u4ed3\u5355\u65e5\u62a5\uff08\u5f20\uff09</h3>
  <table><tr><th>\u65e5\u671f</th><th class="num">\u4ed3\u5355\u603b\u8ba1</th><th class="num">\u589e\u51cf</th>
  <th class="num">\u4ed3\u5e93\u53e3\u5f84</th><th class="num">\u5382\u5e93\u53e3\u5f84</th></tr>{rows_rec}</table>
  <div class="sub" style="margin-top:8px">
    \u201c\u4ed3\u5e93\u53e3\u5f84\u201d\u6c47\u603b\u592a\u4ed3\u9633\u9e3f\u3001\u5357\u901a\u5343\u7ea2\u3001\u6c5f\u82cf\u82cf\u8c6a\u3001\u5e38\u5dde\u5b8f\u5ddd\u7b49\u5b9e\u4f53\u4ed3\u5e93\uff1b\u201c\u5382\u5e93\u53e3\u5f84\u201d\u6c47\u603b\u676d\u5b9e\u5316\u5de5\u3001\u5b89\u5fbd\u4e2d\u80fd\u3001
    \u56fd\u8d38\u77f3\u5316\u7b49\u5382\u5e93\u3002\u672c\u671f\u6240\u6709\u6709\u6548\u4ed3\u5355\u5747\u5728\u5382\u5e93\uff0c\u5b9e\u4f53\u4ed3\u5e93\u4e3a 0\u3002
  </div>
</div>

<h2>7 \u00b7 \u5386\u53f2\u6781\u503c\u65f6\u671f\u7684\u57fa\u672c\u9762\u80cc\u666f</h2>
<div class="card">
  <table><tr><th>\u65e5\u671f</th><th class="num">MA \u4e3b\u8fde\u6536\u76d8</th><th>\u5f53\u65f6\u80cc\u666f</th><th>\u540e\u7eed</th><th>\u6765\u6e90</th></tr>
  {rows_ex}</table>
  <div id="ex-detail" style="display:none;margin-top:10px;padding:10px 12px;background:#0f1620;
       border:1px solid #2d6b74;border-radius:8px;font-size:12.5px;line-height:1.7"></div>
  <div class="sub" style="margin-top:6px">\u2191 \u70b9\u51fb\u4efb\u4e00\u5386\u53f2\u6781\u503c\u884c\uff0c\u5c55\u5f00\u5f53\u65f6\u7684\u4ea7\u4e1a\u80cc\u666f\u4e0e\u540e\u7eed\u8d70\u52bf\u3002</div>
  <div class="sub" style="margin-top:8px">
    \u6700\u63a5\u8fd1\u7684\u4e00\u6b21\uff1a<b>2021 \u5e74 10 \u6708</b>\uff0c\u52a8\u529b\u7164\u53cc\u63a7\u63a8\u5347\u6210\u672c\u3001\u4f9b\u5e94\u7d27\u5f20\uff0cMA \u4e3b\u8fde 2021-10-12 \u6536 4,054 \u5143/\u5428
    \u521b\u5386\u53f2\u6700\u9ad8\uff0c10 \u6708\u4e0b\u65ec\u5feb\u901f\u56de\u843d\u3002\u672c\u8f6e\uff082026 \u5e74 10 \u6708\uff09\u9a71\u52a8\u4e0d\u540c\u2014\u2014\u4e3b\u56e0\u662f<b>\u8fdb\u53e3\u65ad\u6863 + \u6e2f\u53e3\u6781\u4f4e\u5e93\u5b58</b>
    \u800c\u975e\u7164\u4ef7\uff0c\u4f46\u4e24\u8005\u90fd\u53e0\u52a0\u4e86\u201c\u4f4e\u5e93\u5b58 + \u5f3a\u73b0\u8d27\u201d\uff0c\u57fa\u5dee\u5f62\u6001\u53ef\u4ee5\u7c7b\u6bd4\u3002
  </div>
</div>

<h2>8 \u00b7 \u4ea7\u4e1a\u4e8b\u4ef6\u65f6\u95f4\u7ebf</h2>
<div class="card"><table><tr><th style="width:92px">\u65e5\u671f</th><th style="width:74px">\u7c7b\u522b</th>
<th>\u4e8b\u4ef6</th><th>\u5bf9\u57fa\u5dee\u7684\u542b\u4e49</th><th>\u6765\u6e90</th></tr>{rows_ev}</table></div>

<h2>9 \u00b7 \u6570\u636e\u7f3a\u53e3\u58f0\u660e</h2>
<div class="card"><ul style="margin:0;padding-left:18px;line-height:1.9">{rows_gap}</ul></div>

<h2>10 \u00b7 \u6570\u636e\u6765\u6e90</h2>
<div class="card"><table><tr><th>\u7f16\u53f7</th><th>\u6765\u6e90</th><th>\u94fe\u63a5</th><th>\u53d1\u5e03\u65b9</th><th>\u83b7\u53d6\u65e5</th></tr>
{rows_src}</table></div>

<div class="foot">
  \u8ba1\u7b97\u5f0f\uff1a\u57fa\u5dee\uff1d\u73b0\u8d27\u2212\u671f\u8d27\uff1b\u57fa\u5dee\u7387\uff1d\u57fa\u5dee/\u73b0\u8d27\uff1b\u7ecf\u9a8c\u5206\u4f4d\uff1d\u6837\u672c\u4e2d\u5c0f\u4e8e\u7b49\u4e8e\u5f53\u524d\u503c\u7684\u5360\u6bd4\uff1b
  \u0394\u57fa\u5dee\uff1d\u0394\u73b0\u8d27\u2212\u0394\u671f\u8d27\uff1b\u8d21\u732e\uff1d\u0394\u73b0\u8d27/\u0394\u57fa\u5dee \u4e0e \u2212\u0394\u671f\u8d27/\u0394\u57fa\u5dee\uff08\u548c\u4e3a 100%\uff09\u3002<br>
  \u672c\u6587\u4ef6\u4e3a\u7814\u7a76\u4ea4\u4ed8\u7269\uff0c\u6240\u6709\u6570\u5b57\u5747\u53ef\u56de\u6eaf\u81f3\u7b2c 10 \u8282\u6765\u6e90\u6216\u540c\u76ee\u5f55 Excel \u5de5\u4f5c\u7c3f\uff1b
  \u7f3a\u5931\u6570\u636e\u4e00\u5f8b\u7559\u7a7a\u5e76\u5728\u7b2c 9 \u8282\u58f0\u660e\uff0c\u672a\u4f7f\u7528\u63d2\u503c\u3001\u8fd1\u4f3c\u503c\u6216\u4e0d\u53ef\u6bd4\u62fc\u63a5\u3002
</div>
</div>
<script>
const DATA = {json.dumps(payload, ensure_ascii=False)};
{JS_ENGINE}
</script>
</body></html>"""

    html = html.replace('{JS_ENGINE}', JS_ENGINE)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print('HTML -> %s  (%.1f KB)' % (OUT, os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
