#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_chain_html.py —— 通用化工产业链价格地图生成器

把一份 chain-data.json（见 references/data-contract.md）渲染成一个自包含的交互式 HTML：
悬停显示节点报价细节、点击锁定完整报价清单、下方可折叠完整明细、缺口与口径说明。

特点
- 只依赖 Python 标准库（3.8+），无需第三方包与网络。
- 输出单文件 HTML：内联 CSS/JS，无 CDN、无外部字体、无图片，可离线打开与转发。
- 布局自动计算（按 stage 分层、层内垂直居中、列宽按文本宽度自适应），不写死坐标，因此适用于任意化工品。
- 静态部分（结论、缺口、口径、来源）直接写进 HTML；交互部分（SVG 图、明细表）由内联 JS 渲染。

用法
  python build_chain_html.py chain-data.json
  python build_chain_html.py chain-data.json -o ./output/xxx.html
"""

import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chain_layout import PALETTE, PALETTE_ORDER, build_layout  # noqa: E402

# ---------------------------------------------------------------- 静态 HTML 片段

def esc(t):
    return html.escape(str(t), quote=True)


def bullet_list(items, cls=""):
    if not items:
        return ""
    lis = "".join("<li>%s</li>" % s for s in items)
    return '<ul class="%s">%s</ul>' % (cls, lis) if cls else "<ul>%s</ul>" % lis


def build_legend(data):
    out = []
    for st in data.get("stages", []):
        key = st.get("color") or ""
        style = None
        order = [s["key"] for s in data.get("stages", [])]
        idx = order.index(st["key"]) if st["key"] in order else 0
        style = PALETTE.get(st.get("color") or PALETTE_ORDER[idx % len(PALETTE_ORDER)],
                            PALETTE[PALETTE_ORDER[idx % len(PALETTE_ORDER)]])
        out.append(
            '<li><span class="dot" style="background:%s;border-color:%s"></span>%s</li>'
            % (style["fill"], style["stroke"], esc(st.get("label", st["key"]))))
    if any(lk.get("kind") == "dashed" for lk in data.get("links", [])):
        out.append("<li><span class=\"dash\"></span>虚线 = 溶剂 / 助剂投入</li>")
    return "".join(out)


def build_notes_section(notes, gaps):
    parts = []
    if gaps:
        parts.append("<h3>缺口清单（留空不估算）</h3><ul>")
        for g in gaps:
            ev = g.get("evidence")
            ev_html = '（依据：%s）' % esc(ev) if ev else ""
            parts.append('<li><span class="gap">%s</span>：%s%s</li>'
                         % (esc(g.get("scope", "")), esc(g.get("reason", "")), ev_html))
        parts.append("</ul>")
    blocks = [
        ("价格口径", "price_basis"),
        ("产业链关系", "chain_basis"),
        ("缺口处理原则", "gap_notes"),
        ("数据来源", "source_notes"),
    ]
    for title, key in blocks:
        items = notes.get(key) or []
        if items:
            parts.append("<h3>%s</h3>%s" % (esc(title), bullet_list(items)))
    return "".join(parts)


def build_gap_cards(gaps):
    if not gaps:
        return ""
    items = "".join(
        '<li><b>%s</b> —— %s</li>' % (esc(g.get("scope", "")), esc(g.get("reason", "")))
        for g in gaps)
    return ('<section class="gaps"><h2>本次未取到授权价格的环节</h2>'
            '<ul>%s</ul></section>' % items)


# ---------------------------------------------------------------- 应用端 JS

APP_JS = r"""
(function () {
  "use strict";
  var L = JSON.parse(document.getElementById('chain-data').textContent);
  var NS = 'http://www.w3.org/2000/svg';
  var svg = document.getElementById('chain');
  var tip = document.getElementById('tip');
  var stage = document.querySelector('.stage');
  var panel = document.getElementById('panel');
  var byId = {};
  L.nodes.forEach(function (n) { byId[n.id] = n; });

  function mk(tag, attrs, txt) {
    var e = document.createElementNS(NS, tag);
    if (attrs) { for (var k in attrs) { if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, attrs[k]); } }
    if (txt !== undefined && txt !== null) e.textContent = txt;
    return e;
  }

  var gLinks = mk('g'), gLabels = mk('g'), gNodes = mk('g');

  function defs() {
    var d = mk('defs');
    var m = mk('marker', { id: 'arw', viewBox: '0 0 10 10', refX: '9', refY: '5',
      markerWidth: '7', markerHeight: '7', orient: 'auto-start-reverse' });
    m.appendChild(mk('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: '#b7c2d2' }));
    d.appendChild(m);
    return d;
  }

  function render() {
    var c = L.canvas;
    svg.setAttribute('viewBox', '0 0 ' + c.w + ' ' + c.h);
    svg.style.minWidth = Math.min(c.w, 1100) + 'px';
    svg.appendChild(mk('rect', { x: 0, y: 0, width: c.w, height: c.h, fill: '#ffffff' }));

    L.columns.forEach(function (col) {
      svg.appendChild(mk('rect', { x: col.x, y: col.y, width: col.w, height: col.h,
        rx: 16, fill: col.band, opacity: 0.55 }));
      if (col.label) {
        svg.appendChild(mk('text', { x: col.labelX, y: col.labelY, 'text-anchor': 'middle',
          'font-size': 15, 'font-weight': 600, fill: '#5b6b80' }, col.label));
      }
    });

    svg.appendChild(defs());
    svg.appendChild(gLinks);
    svg.appendChild(gLabels);
    svg.appendChild(gNodes);

    L.links.forEach(function (lk, i) {
      var p = mk('path', { d: lk.d, fill: 'none', stroke: '#b7c2d2',
        'stroke-width': lk.dash ? 1.6 : 2,
        'stroke-dasharray': lk.dash ? '6 5' : 'none',
        'data-i': i, 'data-f': lk.from, 'data-t': lk.to });
      p.setAttribute('marker-end', 'url(#arw)');
      gLinks.appendChild(p);
      if (lk.label) {
        gLabels.appendChild(mk('text', { x: lk.lx, y: lk.ly, 'text-anchor': 'middle',
          'font-size': 12, fill: '#7b8a9e', 'data-lb': i,
          'paint-order': 'stroke', stroke: '#ffffff', 'stroke-width': 4 }, lk.label));
      }
    });

    L.nodes.forEach(function (n) {
      var g = mk('g', { 'class': 'node', style: 'cursor:pointer',
        transform: 'translate(' + n.x + ',' + n.y + ')' });
      g.appendChild(mk('rect', { x: 0, y: 0, width: n.w, height: n.h, rx: 13,
        fill: n.fill, stroke: n.stroke, 'stroke-width': 1.6 }));
      if (n.role === 'application') {
        g.appendChild(mk('text', { x: 16, y: 32, 'font-size': 16, 'font-weight': 700, fill: n.text }, n.name));
        g.appendChild(mk('text', { x: 16, y: 60, 'font-size': 12.5, fill: '#a1521c' }, n.gapLabel));
        n.short.forEach(function (s, i) {
          g.appendChild(mk('text', { x: 16, y: 88 + 22 * i, 'font-size': 12, fill: '#7d6a5c' }, s));
        });
      } else {
        var cxm = n.w / 2;
        g.appendChild(mk('text', { x: cxm, y: 28, 'text-anchor': 'middle', 'font-size': 17,
          'font-weight': 700, fill: n.text }, n.name));
        g.appendChild(mk('text', { x: cxm, y: 66, 'text-anchor': 'middle', 'font-size': 25,
          'font-weight': 700, fill: '#16202c' }, n.price));
        if (n.unit) {
          g.appendChild(mk('text', { x: cxm, y: 86, 'text-anchor': 'middle', 'font-size': 12.5,
            fill: '#66768c' }, n.unit));
        }
        if (n.basis) {
          g.appendChild(mk('text', { x: cxm, y: 104, 'text-anchor': 'middle', 'font-size': 11.5,
            fill: '#66768c' }, n.basis));
        }
      }
      g.addEventListener('mouseenter', function (ev) { hover(ev, n); });
      g.addEventListener('mousemove', function (ev) { moveTip(ev); });
      g.addEventListener('mouseleave', unhover);
      g.addEventListener('click', function () { select(n); });
      gNodes.appendChild(g);
    });
  }

  function highlight(id) {
    var ps = gLinks.querySelectorAll('path');
    for (var i = 0; i < ps.length; i++) {
      var p = ps[i];
      var on = id && (p.getAttribute('data-f') === id || p.getAttribute('data-t') === id);
      p.setAttribute('stroke', on ? '#5a7bc4' : (id ? '#dde3ec' : '#b7c2d2'));
      p.setAttribute('stroke-width', on ? 3 : (p.getAttribute('stroke-dasharray') === 'none' ? 2 : 1.6));
    }
    var ls = gLabels.querySelectorAll('text');
    for (var j = 0; j < ls.length; j++) {
      var t = ls[j], k = parseInt(t.getAttribute('data-lb'), 10), lk = L.links[k];
      t.setAttribute('opacity', (!id || lk.from === id || lk.to === id) ? '1' : '0.25');
    }
  }

  function rowsTable(rows, max) {
    var out = rows.slice(0, max);
    var h = '<table><tr><th>地区</th><th>牌号/规格</th><th class="r">价格</th></tr>';
    out.forEach(function (r) {
      h += '<tr><td>' + esc(r.region || '—') + '</td><td>' + esc(r.spec || '—') +
           '</td><td class="r">' + esc(r.price || '—') + '</td></tr>';
    });
    h += '</table>';
    if (rows.length > max) h += '<div class="more">另有 ' + (rows.length - max) + ' 条记录，见下方明细表</div>';
    return h;
  }

  function esc(s) {
    return String(s === undefined || s === null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function hover(ev, n) {
    highlight(n.id);
    var h = '<h4>' + esc(n.name) + '</h4>';
    if (n.role === 'application') {
      h += '<div class="tm">' + esc(n.gapLabel) + '</div><div>' + esc(n.desc) + '</div>';
    } else {
      h += '<div class="tp">' + esc(n.price) + (n.unit ? '<span>' + esc(n.unit) + '</span>' : '') + '</div>';
      h += '<div class="tm">' + esc(n.basis) + ' · 数据日 ' + esc(L.meta.data_date || '') + '</div>';
      if (n.rows.length) h += rowsTable(n.rows, 8);
    }
    tip.innerHTML = h;
    tip.style.display = 'block';
    moveTip(ev);
  }

  function moveTip(ev) {
    var r = stage.getBoundingClientRect();
    var x = ev.clientX - r.left + 16, y = ev.clientY - r.top + 14;
    tip.style.left = '0px'; tip.style.top = '0px';
    var tw = tip.offsetWidth, th = tip.offsetHeight;
    if (x + tw > r.width - 8) x = Math.max(8, ev.clientX - r.left - tw - 16);
    if (y + th > r.height + 40) y = Math.max(8, ev.clientY - r.top - th - 12);
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }

  function unhover() { tip.style.display = 'none'; highlight(null); }

  function panelDefault() {
    var rows = L.nodes.filter(function (n) { return n.role !== 'application'; });
    var h = '<h2>价格明细</h2><p class="pl">数据日 ' + esc(L.meta.data_date || '') +
            ' · 单位 ' + esc(L.meta.unit || '') + '</p>' +
            '<p style="font-size:13.5px;color:#42536b;margin:0 0 12px">把鼠标移到左侧图上任意环节可预览报价；点击环节后在这里列出该环节的完整原始记录。</p>' +
            '<table><tr><th>环节</th><th class="r">最新价</th><th>口径</th></tr>';
    rows.forEach(function (n) {
      h += '<tr><td><b>' + esc(n.name) + '</b></td><td class="num">' + esc(n.price) +
           '</td><td class="dim">' + esc(n.basis) + '</td></tr>';
    });
    h += '</table>';
    if (L.gaps.length) {
      h += '<p class="pl" style="margin-top:12px">下游应用环节本次未检索到授权价格，不以估算值填充。</p>';
    }
    panel.innerHTML = h;
  }

  function select(n) {
    var h = '<h2>' + esc(n.name) + '</h2>';
    h += '<p class="pl">' + (n.role === 'application' ? '下游应用环节'
      : ('数据日 ' + esc(L.meta.data_date || '') + ' · 单位 ' + esc(n.unit))) + '</p>';
    if (n.role === 'application') {
      h += '<p style="font-size:13.5px;color:#a1521c;font-weight:600;margin:4px 0 8px">' + esc(n.gapLabel) + '</p>';
      h += '<p style="font-size:13.5px;color:#42536b">' + esc(n.desc) + '</p>';
    } else {
      h += '<p class="pbig">' + esc(n.price) + (n.unit ? '<span>' + esc(n.unit) + '</span>' : '') + '</p>';
      h += '<p class="pmeta">' + esc(n.basis) + '</p>';
      if (n.desc) h += '<p style="font-size:13.5px;color:#42536b">' + esc(n.desc) + '</p>';
      if (n.rows.length) {
        h += '<div class="tblwrap"><table><tr><th>地区</th><th>牌号/规格</th><th class="r">价格</th><th>说明</th></tr>';
        n.rows.forEach(function (r) {
          h += '<tr><td>' + esc(r.region) + '</td><td>' + esc(r.spec) + '</td><td class="num">' +
               esc(r.price) + '</td><td class="dim">' + esc(r.note) +
               (r.date ? '<br>' + esc(r.date) : '') + (r.source ? ' · ' + esc(r.source) : '') + '</td></tr>';
        });
        h += '</table></div>';
      }
    }
    h += '<p style="margin:12px 0 0"><button id="pback">返回总览</button></p>';
    panel.innerHTML = h;
    document.getElementById('pback').addEventListener('click', panelDefault);
  }

  function fullTable(rows) {
    var h = '<div class="tblwrap"><table><tr><th>地区</th><th>牌号/规格</th><th class="r">价格</th>' +
            '<th>说明</th><th>日期</th><th>来源</th></tr>';
    rows.forEach(function (r) {
      h += '<tr><td>' + esc(r.region) + '</td><td>' + esc(r.spec) + '</td><td class="num">' +
           esc(r.price) + '</td><td class="dim">' + esc(r.note) + '</td><td class="dim">' +
           esc(r.date || '') + '</td><td class="dim">' + esc(r.source || '') + '</td></tr>';
    });
    return h + '</table></div>';
  }

  function renderTables() {
    var host = document.getElementById('tables');
    var groups = [];
    L.stages.forEach(function (st) {
      var ns = L.nodes.filter(function (n) { return n.stage === st.key && n.role !== 'application'; });
      if (ns.length) groups.push({ title: st.label || st.key, nodes: ns });
    });
    groups.forEach(function (g, i) {
      var cnt = g.nodes.reduce(function (a, n) { return a + n.rows.length; }, 0);
      var d = document.createElement('details');
      d.className = 'grp';
      if (i === groups.length - 1 || (groups.length === 1 && i === 0)) d.open = true;
      d.innerHTML = '<summary><span>' + esc(g.title) + '</span><span class="cnt">' + cnt +
        ' 条记录</span></summary><div class="body">' +
        g.nodes.map(function (n) {
          return '<p class="nhead"><b>' + esc(n.name) + '</b> — 图上标注 ' + esc(n.price) +
            (n.unit ? ' ' + esc(n.unit) : '') + (n.basis ? '（' + esc(n.basis) + '）' : '') + '</p>' +
            fullTable(n.rows);
        }).join('') + '</div>';
      host.appendChild(d);
    });
    (L.tables || []).forEach(function (g) {
      var d = document.createElement('details');
      d.className = 'grp';
      d.innerHTML = '<summary><span>' + esc(g.title) + '</span><span class="cnt">' +
        (g.rows || []).length + ' 条记录</span></summary><div class="body">' +
        (g.note ? '<p class="gnote">' + esc(g.note) + '</p>' : '') + fullTable(g.rows || []) + '</div>';
      host.appendChild(d);
    });
  }

  function renderFilter() {
    var box = document.getElementById('tableFilter');
    if (!box) return;
    box.addEventListener('input', function () {
      var q = box.value.trim().toLowerCase();
      var tbls = document.getElementById('tables').querySelectorAll('table');
      for (var i = 0; i < tbls.length; i++) {
        var rows = tbls[i].querySelectorAll('tr');
        var visible = 0;
        for (var j = 1; j < rows.length; j++) {
          var hit = !q || rows[j].textContent.toLowerCase().indexOf(q) >= 0;
          rows[j].style.display = hit ? '' : 'none';
          if (hit) visible++;
        }
        tbls[i].style.display = (visible || !q) ? '' : 'none';
      }
    });
  }

  render();
  panelDefault();
  renderTables();
  renderFilter();
})();
"""


# ---------------------------------------------------------------- 页面模板

PAGE = """<!DOCTYPE html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ · 数据日 __DATE__</title>
<style>
  :root{ --bg:#f3f5f9; --card:#fff; --tx:#16202c; --mut:#66768c; --line:#e3e9f1; }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{background:var(--bg);color:var(--tx);
    font:15px/1.65 "Segoe UI","Microsoft YaHei","PingFang SC",system-ui,sans-serif;}
  .wrap{max-width:1640px;margin:0 auto;padding:22px 20px 60px}
  h1{font-size:26px;margin:0 0 6px;letter-spacing:.4px}
  .sub{margin:0 0 4px;color:var(--mut);font-size:13.5px}
  .sub b{color:var(--tx)}
  .hint{margin:8px 0 0;font-size:13px;color:#3c5a86;background:#e9f1fd;border:1px solid #cfe0f8;
    border-radius:8px;padding:7px 12px;display:inline-block}
  .legend{list-style:none;display:flex;flex-wrap:wrap;gap:8px 18px;padding:0;margin:14px 0 16px;
    font-size:12.5px;color:var(--mut)}
  .legend li{display:flex;align-items:center;gap:6px}
  .dot{width:13px;height:13px;border-radius:4px;display:inline-block;border:1px solid}
  .dash{width:22px;height:0;border-top:2px dashed #b7c2d2;display:inline-block}
  .keyfinding{background:var(--card);border:1px solid var(--line);border-left:4px solid #5a7bc4;
    border-radius:10px;padding:12px 16px;margin:0 0 16px}
  .keyfinding h2{font-size:15px;margin:0 0 4px;color:#2c3e58}
  .keyfinding p{margin:0;font-size:14.5px}
  .stage{position:relative;display:grid;grid-template-columns:minmax(0,1fr) 372px;gap:16px;align-items:start}
  .chart-scroll{background:var(--card);border:1px solid var(--line);border-radius:14px;
    padding:6px;overflow:auto;box-shadow:0 1px 3px rgba(20,40,70,.05)}
  #chain{display:block;width:100%;height:auto}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 16px 18px;
    position:sticky;top:16px;max-height:calc(100vh - 40px);overflow:auto;
    box-shadow:0 1px 3px rgba(20,40,70,.05)}
  .panel h2{margin:0 0 4px;font-size:17px}
  .panel .pl{color:var(--mut);font-size:12.5px;margin:0 0 10px}
  .panel .pbig{font-size:30px;font-weight:700;letter-spacing:.5px;margin:2px 0 0}
  .panel .pbig span{font-size:14px;font-weight:500;color:var(--mut);margin-left:6px}
  .panel .pmeta{font-size:13px;color:var(--mut);margin:6px 0 12px}
  .panel button{font-size:12.5px;padding:5px 11px;border-radius:7px;border:1px solid #cfd8e5;
    background:#f7f9fc;cursor:pointer}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
  th{background:#f7f9fc;font-weight:600;color:#42536b;white-space:nowrap;font-size:12.5px}
  td.r,th.r{text-align:right}
  td.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
  td.dim{color:var(--mut);font-size:12.3px}
  .tblwrap{max-height:430px;overflow:auto;border:1px solid var(--line);border-radius:10px}
  .tblwrap table{border:0}
  .tblwrap th{position:sticky;top:0;z-index:1}
  .tables{margin-top:22px}
  .tables h2{font-size:19px;margin:0 0 4px}
  .tables .tnote{color:var(--mut);font-size:13px;margin:0 0 10px}
  .filterrow{margin:0 0 12px}
  .filterrow input{width:100%;max-width:420px;padding:8px 11px;border:1px solid #cfd8e5;
    border-radius:9px;font-size:13.5px;background:#fff}
  details.grp{background:var(--card);border:1px solid var(--line);border-radius:12px;
    margin-bottom:12px;overflow:hidden}
  details.grp>summary{cursor:pointer;padding:13px 16px;font-weight:600;font-size:15px;background:#fafcfe;
    display:flex;justify-content:space-between;align-items:center;gap:10px}
  details.grp>summary::-webkit-details-marker{display:none}
  details.grp>summary .cnt{font-weight:500;font-size:12.5px;color:var(--mut)}
  details.grp .body{padding:0 12px 12px}
  .nhead{font-size:13px;color:#42536b;margin:12px 0 6px}
  .gnote{font-size:12.8px;color:var(--mut);margin:10px 0 6px}
  .gaps{background:#fdf6ef;border:1px solid #f0dcc8;border-radius:12px;padding:14px 18px;margin-top:22px}
  .gaps h2{font-size:17px;margin:0 0 8px;color:#8a4a1e}
  .gaps ul{margin:0;padding-left:20px;font-size:13.5px}
  .gaps li{margin:4px 0}
  .notes{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;
    margin-top:22px;font-size:13.5px}
  .notes h2{font-size:18px;margin:0 0 8px}
  .notes h3{font-size:14.5px;margin:16px 0 6px}
  .notes ul{margin:6px 0;padding-left:20px}
  .notes li{margin:3px 0}
  .gap{color:#a1521c;font-weight:600}
  .tip{position:absolute;z-index:40;pointer-events:none;max-width:420px;background:#101a26;color:#eef3f9;
    border-radius:10px;padding:11px 13px;font-size:12.6px;line-height:1.5;
    box-shadow:0 8px 26px rgba(10,25,45,.28);display:none}
  .tip h4{margin:0 0 3px;font-size:14.5px}
  .tip .tp{font-size:19px;font-weight:700;margin:1px 0 4px}
  .tip .tp span{font-size:12px;font-weight:400;color:#a9bacd;margin-left:5px}
  .tip .tm{color:#a9bacd;font-size:11.8px;margin:0 0 7px}
  .tip table{font-size:12px}
  .tip th,.tip td{border-bottom:1px solid #25324399;padding:3px 6px;color:#dfe8f2}
  .tip th{background:transparent;color:#93a6bb;font-weight:500}
  .tip .more{margin-top:6px;color:#93a6bb;font-size:11.5px}
  @media (max-width:1080px){
    .stage{grid-template-columns:minmax(0,1fr)}
    .panel{position:static;max-height:none}
  }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>__TITLE__</h1>
  <p class="sub">数据日 <b>__DATE__</b> · 价格单位 <b>__UNIT__</b> · 检索时间 __RETRIEVED__ · 价格来源：__SOURCES__</p>
  <p class="hint">把鼠标移到任意环节即可预览该品种的最新报价细节；点击环节可在右侧锁定完整报价清单；下方为可检索的完整明细与缺口说明。</p>
  <ul class="legend">__LEGEND__</ul>
</header>

<section class="keyfinding">
  <h2>核心结论</h2>
  <p>__HEADLINE__</p>
</section>

<div class="stage">
  <div class="chart-scroll">
    <svg id="chain" viewBox="0 0 1200 700" preserveAspectRatio="xMidYMid meet" role="img"
         aria-label="__TITLE__：产业链各环节与最新报价"></svg>
  </div>
  <aside class="panel" id="panel"></aside>
  <div class="tip" id="tip"></div>
</div>

__GAPS__

<section class="tables" id="tables">
  <h2>完整报价明细</h2>
  <p class="tnote">__BASIS_NOTE__</p>
  <div class="filterrow"><input id="tableFilter" type="search" placeholder="在明细中检索：地区 / 牌号 / 价格 / 备注"></div>
</section>

<section class="notes">
  <h2>口径、方法与缺口说明</h2>
  __NOTES__
</section>

<div class="footerline" style="margin-top:18px;color:#66768c;font-size:12.5px">
  本页为单文件离线页面：图表与明细由内联脚本渲染，不含外部资源；价格逐条来自原始记录，未做第三方独立核验。
</div>
</div>

<script id="chain-data" type="application/json">__DATA__</script>
<script>__APP_JS__</script>
</body>
</html>
"""


def render_html(data, layout):
    meta = data.get("meta", {})
    sources = "、".join(s.get("name", "") for s in meta.get("sources", [])) or "见下方数据来源"
    out = PAGE
    repl = {
        "__LANG__": esc(meta.get("lang", "zh-CN")),
        "__TITLE__": esc(meta.get("title", "化工产业链价格地图")),
        "__DATE__": esc(meta.get("data_date", "")),
        "__UNIT__": esc(meta.get("unit", "")),
        "__RETRIEVED__": esc(meta.get("retrieved_at", "")),
        "__SOURCES__": esc(sources),
        "__HEADLINE__": esc(meta.get("headline", "")),
        "__LEGEND__": build_legend(data),
        "__GAPS__": build_gap_cards(data.get("gaps", [])),
        "__BASIS_NOTE__": esc(meta.get("basis_note", "")),
        "__NOTES__": build_notes_section(data.get("notes", {}), data.get("gaps", [])),
        "__APP_JS__": APP_JS,
    }
    for k, v in repl.items():
        out = out.replace(k, v)
    payload = json.dumps(layout, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    out = out.replace("__DATA__", payload)
    return out


def default_out_path(src):
    base = os.path.splitext(os.path.basename(src))[0]
    if base == "chain-data":
        base = os.path.basename(os.path.dirname(os.path.abspath(src))) or "chain"
    return os.path.join(os.path.dirname(os.path.abspath(src)), base + "-chain.html")


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成自包含交互式化工产业链价格地图 HTML")
    ap.add_argument("input", help="chain-data.json 路径")
    ap.add_argument("-o", "--out", help="输出 HTML 路径（默认与输入同目录）")
    args = ap.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    layout = build_layout(data)
    html_text = render_html(data, layout)

    out_path = args.out or default_out_path(args.input)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_text)

    print("已生成: %s" % out_path)
    print("  画布: %sx%s · 节点 %d 个 · 连线 %d 条 · 明细行 %d 条"
          % (layout["canvas"]["w"], layout["canvas"]["h"], len(layout["nodes"]),
             len(layout["links"]),
             sum(len(n["rows"]) for n in layout["nodes"]) +
             sum(len(t.get("rows", [])) for t in layout["tables"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
