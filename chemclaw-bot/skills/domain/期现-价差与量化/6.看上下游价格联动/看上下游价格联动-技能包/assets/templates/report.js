/* report.js —— 交互式研究报告前端（数据由页面注入 window.__A__） */
(function () {
  'use strict';
  var A = window.__A__;
  var S = A.series, D = S.map(function (r) { return r.date; });
  var mode = 'level', coef = A.coef, otherCost = 0;
  var rollWin = A.windows[Math.min(1, A.windows.length - 1)], rollMode = 'level';
  var ccMode = 'level', maxLag = Math.min(20, A.maxlag || 20);

  function $(id) { return document.getElementById(id); }
  function fmt(v, nd) { if (v === null || v === undefined) return '—'; return Number(v).toLocaleString('en-US', { maximumFractionDigits: nd === undefined ? 0 : nd, minimumFractionDigits: nd === undefined ? 0 : nd }); }

  function fit(c, h) {
    var dpr = window.devicePixelRatio || 1;
    var w = c.clientWidth || c.parentNode.clientWidth;
    c.width = w * dpr; c.height = h * dpr; c.style.height = h + 'px';
    var ctx = c.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx: ctx, w: w, h: h };
  }

  function grid(o, pad, ymin, ymax, n, yticks, fmtY) {
    var ctx = o.ctx, w = o.w, h = o.h;
    ctx.clearRect(0, 0, w, h);
    ctx.font = '11px ui-monospace,Consolas,monospace';
    for (var i = 0; i <= yticks; i++) {
      var v = ymin + (ymax - ymin) * i / yticks;
      var y = pad.t + (h - pad.t - pad.b) * (1 - i / yticks);
      ctx.beginPath(); ctx.strokeStyle = 'rgba(143,160,181,.15)'; ctx.lineWidth = 1;
      ctx.moveTo(pad.l, y); ctx.lineTo(w - pad.r, y); ctx.stroke();
      ctx.fillStyle = '#8fa0b5'; ctx.fillText(fmtY(v), 4, y + 4);
    }
    var step = Math.max(1, Math.floor(n / 9));
    for (var k = 0; k < n; k += step) {
      var x = pad.l + (w - pad.l - pad.r) * (n <= 1 ? 0 : k / (n - 1));
      ctx.fillStyle = '#7c8ea3'; ctx.fillText((D[k] || '').slice(2), x - 20, h - pad.b + 15);
    }
  }

  function xAt(o, pad, i, n) { return pad.l + (o.w - pad.l - pad.r) * (n <= 1 ? 0 : i / (n - 1)); }
  function yAt(o, pad, v, ymin, ymax) { return pad.t + (o.h - pad.t - pad.b) * (1 - (v - ymin) / (ymax - ymin || 1)); }

  function polyline(o, pad, ys, color, width, ymin, ymax) {
    var ctx = o.ctx, started = false;
    ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineJoin = 'round';
    for (var i = 0; i < ys.length; i++) {
      if (ys[i] === null || ys[i] === undefined || isNaN(ys[i])) { started = false; continue; }
      var X = xAt(o, pad, i, ys.length), Y = yAt(o, pad, ys[i], ymin, ymax);
      if (!started) { ctx.moveTo(X, Y); started = true; } else ctx.lineTo(X, Y);
    }
    ctx.stroke();
  }

  /* ---------- 1. 价格曲线 ---------- */
  function seriesFor(m) {
    if (m === 'ret') return { px: S.map(function (r) { return r.px_ret === null ? null : r.px_ret * 100; }),
                              pta: S.map(function (r) { return r.pta_ret === null ? null : r.pta_ret * 100; }), unit: '%' };
    if (m === 'index') return { px: A.index.map(function (r) { return r.px_idx; }),
                                pta: A.index.map(function (r) { return r.pta_idx; }), unit: 'idx' };
    return { px: S.map(function (r) { return r.px; }), pta: S.map(function (r) { return r.pta; }), unit: 'cny' };
  }

  function drawPrice() {
    var c = $('cPrice'); var o = fit(c, 380); var pad = { l: 66, r: 16, t: 16, b: 28 };
    var s = seriesFor(mode);
    var sp = S.map(function (r) { return r.pta - coef * r.px - otherCost; });
    var all = s.px.concat(s.pta).filter(function (v) { return v !== null; });
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
    var ymin, ymax, fmtY;
    if (mode === 'ret') { ymin = Math.min(-3, lo); ymax = Math.max(3, hi); fmtY = function (v) { return v.toFixed(1) + '%'; }; }
    else if (mode === 'index') { ymin = lo - (hi - lo) * 0.06; ymax = hi + (hi - lo) * 0.06; fmtY = function (v) { return v.toFixed(0); }; }
    else { ymin = lo - (hi - lo) * 0.12; ymax = hi + (hi - lo) * 0.12; fmtY = function (v) { return v.toFixed(0); }; }
    grid(o, pad, ymin, ymax, S.length, 5, fmtY);
    polyline(o, pad, s.px, '#3f9dff', 2, ymin, ymax);
    polyline(o, pad, s.pta, '#39d3a0', 2, ymin, ymax);
    // 价差用独立缩放画成面积
    var slo = Math.min.apply(null, sp), shi = Math.max.apply(null, sp);
    var ctx = o.ctx;
    ctx.beginPath();
    for (var i = 0; i < sp.length; i++) {
      var X = xAt(o, pad, i, sp.length);
      var Y = pad.t + (o.h - pad.t - pad.b) * (1 - (sp[i] - slo) / ((shi - slo) || 1));
      if (i === 0) ctx.moveTo(X, Y); else ctx.lineTo(X, Y);
    }
    ctx.strokeStyle = 'rgba(255,200,87,.9)'; ctx.lineWidth = 1.4; ctx.stroke();
    ctx.lineTo(xAt(o, pad, sp.length - 1, sp.length), o.h - pad.b);
    ctx.lineTo(pad.l, o.h - pad.b); ctx.closePath();
    ctx.fillStyle = 'rgba(255,200,87,.08)'; ctx.fill();
    ctx.fillStyle = '#8fa0b5'; ctx.font = '11px sans-serif';
    ctx.fillText(s.unit === 'cny' ? '元/吨（价差单独缩放）' : s.unit, 4, 12);
    drawRanges();
  }

  function drawRanges() {
    var yr = {}; var order = [];
    S.forEach(function (r) { var y = r.date.slice(0, 4); if (!yr[y]) { yr[y] = []; order.push(y); } yr[y].push(r); });
    var html = '<table><thead><tr><th class="l">区间</th><th>起 PX</th><th>止 PX</th><th>PX 涨跌</th>'
             + '<th>起 PTA</th><th>止 PTA</th><th>PTA 涨跌</th><th>价差均值</th><th>价差变化</th></tr></thead><tbody>';
    order.sort().forEach(function (y) {
      var g = yr[y], a = g[0], b = g[g.length - 1];
      var sMean = g.reduce(function (s, r) { return s + r.pta - coef * r.px - otherCost; }, 0) / g.length;
      var pc = (b.px / a.px - 1) * 100, tc = (b.pta / a.pta - 1) * 100;
      var s0 = a.pta - coef * a.px - otherCost, s1 = b.pta - coef * b.px - otherCost;
      function tag(v) { return '<span class="tag ' + (v >= 0 ? 'pos' : 'neg') + '">' + v.toFixed(1) + '%</span>'; }
      html += '<tr><td class="l mono">' + y + ' <span class="dim">N=' + g.length + '</span></td>'
        + '<td class="mono">' + fmt(a.px, 0) + '</td><td class="mono">' + fmt(b.px, 0) + '</td><td>' + tag(pc) + '</td>'
        + '<td class="mono">' + fmt(a.pta, 0) + '</td><td class="mono">' + fmt(b.pta, 0) + '</td><td>' + tag(tc) + '</td>'
        + '<td class="mono">' + fmt(sMean, 0) + '</td><td class="mono">' + fmt(s1 - s0, 0) + '</td></tr>';
    });
    $('rangeTable').innerHTML = html + '</tbody></table>';
  }

  /* ---------- 2. 加工价差 ---------- */
  function spreadArr() { return S.map(function (r) { return r.pta - coef * r.px - otherCost; }); }
  function qSorted(a, q) {
    var n = a.length; if (!n) return null; if (n === 1) return a[0];
    var pos = (n - 1) * q, lo = Math.floor(pos), hi = Math.min(lo + 1, n - 1);
    return a[lo] + (a[hi] - a[lo]) * (pos - lo);
  }

  function drawSpread() {
    var c = $('cSpread'); var o = fit(c, 300); var pad = { l: 66, r: 54, t: 16, b: 28 };
    var sp = spreadArr(), sorted = sp.slice().sort(function (a, b) { return a - b; });
    var lo = Math.min.apply(null, sp), hi = Math.max.apply(null, sp);
    var ymin = lo - (hi - lo) * 0.08, ymax = hi + (hi - lo) * 0.08;
    grid(o, pad, ymin, ymax, sp.length, 5, function (v) { return v.toFixed(0); });
    // 分位参考线
    var ctx = o.ctx;
    [[0.1, 'P10'], [0.5, 'P50'], [0.9, 'P90']].forEach(function (p) {
      var v = qSorted(sorted, p[0]);
      var Y = yAt(o, pad, v, ymin, ymax);
      ctx.beginPath(); ctx.setLineDash([4, 4]); ctx.strokeStyle = 'rgba(143,160,181,.5)'; ctx.lineWidth = 1;
      ctx.moveTo(pad.l, Y); ctx.lineTo(o.w - pad.r, Y); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#7c8ea3'; ctx.font = '10.5px ui-monospace,monospace';
      ctx.fillText(p[1] + ' ' + v.toFixed(0), o.w - pad.r + 4, Y + 3);
    });
    // 面积（相对 0）
    var zeroY = yAt(o, pad, 0, ymin, ymax);
    ctx.beginPath();
    sp.forEach(function (v, i) {
      var X = xAt(o, pad, i, sp.length), Y = yAt(o, pad, v, ymin, ymax);
      if (i === 0) ctx.moveTo(X, Y); else ctx.lineTo(X, Y);
    });
    ctx.lineTo(xAt(o, pad, sp.length - 1, sp.length), zeroY); ctx.lineTo(pad.l, zeroY); ctx.closePath();
    ctx.fillStyle = 'rgba(255,200,87,.12)'; ctx.fill();
    polyline(o, pad, sp, '#ffc857', 1.9, ymin, ymax);

    var cur = sp[sp.length - 1];
    var pr = 100 * sorted.filter(function (v) { return v <= cur; }).length / sorted.length;
    var mean = sp.reduce(function (a, b) { return a + b; }, 0) / sp.length;
    var sd = Math.sqrt(sp.reduce(function (a, b) { return a + (b - mean) * (b - mean); }, 0) / sp.length);
    $('spreadKpis').innerHTML =
      card('最新加工价差', fmt(cur, 1), '历史分位 ' + pr.toFixed(1) + '%（λ=' + coef.toFixed(3) + '，其他成本 ' + otherCost + '）') +
      card('均值 / 标准差', fmt(mean, 0) + ' / ' + fmt(sd, 0), 'N=' + sp.length) +
      card('P5 / P10 / P50', fmt(qSorted(sorted, .05), 0) + ' / ' + fmt(qSorted(sorted, .1), 0) + ' / ' + fmt(qSorted(sorted, .5), 0), '历史分位带') +
      card('P90 / P95', fmt(qSorted(sorted, .9), 0) + ' / ' + fmt(qSorted(sorted, .95), 0), '高位区间');
  }
  function card(k, v, s) { return '<div class="kpi"><div class="k">' + k + '</div><div class="v mono">' + v + '</div><div class="s">' + s + '</div></div>'; }

  /* ---------- 3. 滚动相关 ---------- */
  function drawRoll() {
    var c = $('cRoll'); var o = fit(c, 300); var pad = { l: 56, r: 16, t: 16, b: 28 };
    var src = (A.rolling[String(rollWin)] || {})[rollMode] || [];
    var ys = src.map(function (v) { return v.r; });
    grid(o, pad, -1, 1, ys.length, 4, function (v) { return v.toFixed(2); });
    var ctx = o.ctx;
    [[0, false], [0.8, true], [-0.8, true]].forEach(function (p) {
      var Y = yAt(o, pad, p[0], -1, 1);
      ctx.beginPath(); ctx.setLineDash(p[1] ? [4, 4] : []);
      ctx.strokeStyle = p[1] ? 'rgba(255,107,129,.45)' : 'rgba(143,160,181,.45)';
      ctx.moveTo(pad.l, Y); ctx.lineTo(o.w - pad.r, Y); ctx.stroke(); ctx.setLineDash([]);
    });
    polyline(o, pad, ys, rollMode === 'level' ? '#3f9dff' : '#a78bfa', 1.9, -1, 1);
    var valid = ys.filter(function (v) { return v !== null && v !== undefined; });
    if (!valid.length) { $('rollKpis').innerHTML = card('样本不足', '不计算', '窗口 ' + rollWin + ' 观测'); return; }
    $('rollKpis').innerHTML =
      card('最新滚动 r', valid[valid.length - 1].toFixed(3), '窗口 ' + rollWin + ' 观测') +
      card('区间', Math.min.apply(null, valid).toFixed(2) + ' ~ ' + Math.max.apply(null, valid).toFixed(2), '有效窗口 ' + valid.length) +
      card('均值', (valid.reduce(function (a, b) { return a + b; }, 0) / valid.length).toFixed(3), rollMode === 'level' ? '水平口径' : '收益率口径') +
      card('稳定性', (100 * valid.filter(function (v) { return Math.abs(v) >= 0.8; }).length / valid.length).toFixed(0) + '%', '|r|≥0.8 窗口占比');
  }

  /* ---------- 4. 领先滞后 ---------- */
  function drawCC() {
    var c = $('cCC'); var o = fit(c, 300); var pad = { l: 56, r: 16, t: 16, b: 28 };
    var src = (ccMode === 'level' ? A.crosscorr_level : A.crosscorr_return).filter(function (x) { return Math.abs(x.lag) <= maxLag; });
    var vals = src.map(function (x) { return x.r; }).filter(function (v) { return v !== null; });
    if (!vals.length) return;
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var ymin = Math.min(-0.1, lo - 0.05), ymax = Math.max(0.1, hi + 0.05);
    grid(o, pad, ymin, ymax, src.length, 4, function (v) { return v.toFixed(2); });
    var ctx = o.ctx, bw = (o.w - pad.l - pad.r) / src.length * 0.6;
    var zeroY = yAt(o, pad, 0, ymin, ymax);
    src.forEach(function (it, i) {
      if (it.r === null) return;
      var X = pad.l + (o.w - pad.l - pad.r) * (i + 0.5) / src.length;
      var Y = yAt(o, pad, it.r, ymin, ymax);
      ctx.fillStyle = it.r >= 0 ? 'rgba(63,157,255,.85)' : 'rgba(255,107,129,.85)';
      ctx.fillRect(X - bw / 2, Math.min(Y, zeroY), bw, Math.abs(Y - zeroY));
      if (i % 2 === 0) { ctx.fillStyle = '#7c8ea3'; ctx.font = '10.5px ui-monospace,monospace'; ctx.fillText(String(it.lag), X - 6, o.h - pad.b + 15); }
    });
    ctx.beginPath(); ctx.strokeStyle = 'rgba(143,160,181,.5)'; ctx.moveTo(pad.l, zeroY); ctx.lineTo(o.w - pad.r, zeroY); ctx.stroke();
    ctx.fillStyle = '#8fa0b5'; ctx.font = '11px sans-serif';
    ctx.fillText('横轴：lag > 0 = PX 领先 PTA', pad.l, 12);
  }

  /* ---------- 绑定 ---------- */
  function bindChips(sel, attr, fn) {
    document.querySelectorAll(sel + ' .chip').forEach(function (ch) {
      ch.onclick = function () {
        document.querySelectorAll(sel + ' .chip').forEach(function (x) { x.classList.remove('on'); });
        ch.classList.add('on'); fn(ch.getAttribute(attr));
      };
    });
  }
  bindChips('#modeChips', 'data-mode', function (v) { mode = v; drawPrice(); });
  bindChips('#winChips', 'data-win', function (v) { rollWin = +v; drawRoll(); });
  bindChips('#rollMode', 'data-rm', function (v) { rollMode = v; drawRoll(); });
  bindChips('#ccMode', 'data-cc', function (v) { ccMode = v; drawCC(); });

  $('coefRange').oninput = function (e) { coef = +e.target.value; $('coefOut').textContent = coef.toFixed(3); drawPrice(); drawSpread(); };
  $('ocRange').oninput = function (e) { otherCost = +e.target.value; $('ocOut').textContent = otherCost; drawPrice(); drawSpread(); };
  $('resetCoef').onclick = function () {
    coef = A.coef; otherCost = 0;
    $('coefRange').value = A.coef; $('coefOut').textContent = A.coef.toFixed(3);
    $('ocRange').value = 0; $('ocOut').textContent = '0';
    drawPrice(); drawSpread();
  };
  $('lagRange').oninput = function (e) { maxLag = +e.target.value; $('lagOut').textContent = maxLag; drawCC(); };

  // 背离区间点击 → 高亮事件台账
  document.querySelectorAll('.diverge-row').forEach(function (tr) {
    tr.onclick = function () {
      var st = tr.getAttribute('data-start'), en = tr.getAttribute('data-end');
      document.querySelectorAll('.ev-row').forEach(function (ev) {
        var d = ev.getAttribute('data-date');
        ev.style.background = (d >= st && d <= en) ? 'rgba(255,107,129,.12)' : '';
      });
      document.querySelectorAll('.diverge-row').forEach(function (x) { x.classList.remove('sel'); });
      tr.classList.add('sel');
      document.getElementById('s8').scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
  });
  document.querySelectorAll('.ev-row').forEach(function (tr) { tr.onclick = function () { tr.classList.toggle('sel'); }; });

  window.addEventListener('resize', function () { drawPrice(); drawSpread(); drawRoll(); drawCC(); });
  drawPrice(); drawSpread(); drawRoll(); drawCC();
}());
