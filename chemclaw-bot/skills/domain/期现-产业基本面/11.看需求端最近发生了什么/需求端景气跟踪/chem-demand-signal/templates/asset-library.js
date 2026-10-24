/* asset-library.js — chem-demand-signal 的 SVG 图表库（零依赖、离线可用）
 * 用法：<script src="asset-library.js"></script> 后调用 DDS.spark(...) / DDS.donut(...)
 * 全部返回 SVG 字符串，可直接 innerHTML。字体沿用宿主页面。
 */
(function (root) {
  'use strict';
  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  /** 迷你折线：points 形如 [{value:1},{value:2}] */
  function spark(points, color, w, h) {
    w = w || 200; h = h || 26;
    const vals = points.map(p => p.value).filter(v => typeof v === 'number');
    if (!vals.length) return '';
    const mn = Math.min(...vals), mx = Math.max(...vals), rng = (mx - mn) || 1;
    const step = w / Math.max(points.length - 1, 1);
    const xy = points.map((p, i) => [i * step, h - 2 - (((p.value ?? mn) - mn) / rng) * (h - 4)]);
    const d = xy.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
    const last = xy[xy.length - 1];
    return '<svg viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none" style="width:100%;height:' + h + 'px">'
      + '<path d="' + d + ' L' + w + ' ' + h + ' L0 ' + h + ' Z" fill="' + color + '" opacity=".10"/>'
      + '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="1.7"/>'
      + '<circle cx="' + last[0].toFixed(1) + '" cy="' + last[1].toFixed(1) + '" r="3" fill="' + color + '"/></svg>';
  }

  /** 环形占比图：items 形如 [{name,share,color}] */
  function donut(items, size) {
    size = size || 260;
    const R = size / 2 - 6, r = R * 0.6, cx = size / 2, cy = size / 2;
    const tot = items.reduce((a, b) => a + (b.share || 0), 0) || 1;
    let acc = 0, out = '';
    items.forEach(it => {
      const a0 = acc / tot * Math.PI * 2, a1 = (acc + (it.share || 0)) / tot * Math.PI * 2;
      acc += (it.share || 0);
      const large = (a1 - a0) > Math.PI ? 1 : 0;
      const pt = (a, rad) => [cx + Math.cos(a) * rad, cy + Math.sin(a) * rad];
      const [x0, y0] = pt(a0, R), [x1, y1] = pt(a1, R), [x2, y2] = pt(a1, r), [x3, y3] = pt(a0, r);
      out += '<path d="M' + x0 + ' ' + y0 + ' A' + R + ' ' + R + ' 0 ' + large + ' 1 ' + x1 + ' ' + y1
        + ' L' + x2 + ' ' + y2 + ' A' + r + ' ' + r + ' 0 ' + large + ' 0 ' + x3 + ' ' + y3 + ' Z" fill="'
        + (it.color || '#4cc3e8') + '" opacity=".88"><title>' + esc(it.name) + ' ' + it.share + '%</title></path>';
    });
    return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '" style="transform:rotate(-90deg)">' + out + '</svg>';
  }

  /** 环形进度：deg 0-360 */
  function ring(deg, size, color) {
    const r = (size - 6) / 2, c = 2 * Math.PI * r, on = c * Math.min(deg / 360, 1);
    return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '" style="transform:rotate(-90deg)">'
      + '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="rgba(255,255,255,.07)" stroke-width="5"/>'
      + '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="' + color
      + '" stroke-width="5" stroke-dasharray="' + on + ' ' + c + '" stroke-linecap="round"/></svg>';
  }

  /** 面积折线：series 形如 [{d:'2026-01-01',c:1000}]，marks 为竖线标记日期数组 */
  function area(series, color, w, h, marks) {
    w = w || 1080; h = h || 250;
    if (!series || series.length < 2) return '<div style="font-size:12px;opacity:.6">无序列数据</div>';
    const vals = series.map(p => p.c ?? p.value);
    let mn = Math.min(...vals), mx = Math.max(...vals);
    const pad = (mx - mn) * 0.12 || 10; mn -= pad; mx += pad;
    const L = 54, R = 12, T = 14, B = 26, iw = w - L - R, ih = h - T - B;
    const X = i => L + i / (series.length - 1) * iw, Y = v => T + (1 - (v - mn) / (mx - mn)) * ih;
    const line = series.map((p, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(p.c ?? p.value).toFixed(1)).join(' ');
    let grid = '', ylab = '';
    for (let k = 0; k <= 4; k++) {
      const v = mn + (mx - mn) * k / 4, y = Y(v);
      grid += '<line x1="' + L + '" y1="' + y + '" x2="' + (w - R) + '" y2="' + y + '" stroke="rgba(120,170,210,.10)"/>';
      ylab += '<text x="' + (L - 8) + '" y="' + (y + 4) + '" text-anchor="end" fill="#5f7890" font-size="10.5">' + v.toFixed(0) + '</text>';
    }
    let xlab = '', last = null;
    series.forEach((p, i) => {
      const m = (p.d || '').slice(0, 7);
      if (m !== last && i % 22 === 0) {
        xlab += '<text x="' + X(i) + '" y="' + (h - 8) + '" fill="#5f7890" font-size="10.5" text-anchor="middle">' + m + '</text>';
        last = m;
      }
    });
    let mk = '';
    (marks || []).forEach(t => {
      const i = series.findIndex(p => (p.d || '') >= t);
      if (i >= 0) mk += '<line x1="' + X(i) + '" y1="' + T + '" x2="' + X(i) + '" y2="' + (T + ih) + '" stroke="#e6b45a" stroke-dasharray="3 4" opacity=".65"/>'
        + '<text x="' + (X(i) + 4) + '" y="' + (T + 12) + '" fill="#e6b45a" font-size="10">' + t + '</text>';
    });
    const gid = 'g' + Math.random().toString(36).slice(2, 8);
    return '<svg viewBox="0 0 ' + w + ' ' + h + '" style="width:100%;height:' + h + 'px">'
      + '<defs><linearGradient id="' + gid + '" x1="0" x2="0" y1="0" y2="1">'
      + '<stop offset="0" stop-color="' + color + '" stop-opacity=".30"/><stop offset="1" stop-color="' + color + '" stop-opacity="0"/></linearGradient></defs>'
      + grid + ylab + xlab + mk
      + '<path d="' + line + ' L' + X(series.length - 1) + ' ' + (T + ih) + ' L' + L + ' ' + (T + ih) + ' Z" fill="url(#' + gid + ')"/>'
      + '<path d="' + line + '" fill="none" stroke="' + color + '" stroke-width="1.9"/>'
      + '<circle cx="' + X(series.length - 1) + '" cy="' + Y(vals[vals.length - 1]) + '" r="3.6" fill="' + color + '"/></svg>';
  }

  /** 正负柱状：items 形如 [{v:0.4,l1:'浮法',l2:'权重46%'}] */
  function bars(items, w, h) {
    w = w || 760; h = h || 210;
    const L = 48, R = 10, T = 16, B = 54, iw = w - L - R, ih = h - T - B;
    const mx = Math.max(...items.map(x => Math.abs(x.v))) || 1;
    const zero = T + ih * 0.5, bw = iw / items.length * 0.52;
    let out = '';
    items.forEach((it, i) => {
      const cx = L + (i + 0.5) * iw / items.length, hh = Math.abs(it.v) / mx * (ih * 0.46);
      const col = it.v > 0 ? '#f0553f' : (it.v < 0 ? '#26b57e' : '#8fa3b8');
      out += '<rect x="' + (cx - bw / 2) + '" y="' + (it.v >= 0 ? zero - hh : zero) + '" width="' + bw
        + '" height="' + (hh || 1) + '" rx="4" fill="' + col + '" opacity=".85"/>'
        + '<text x="' + cx + '" y="' + (it.v >= 0 ? zero - hh - 7 : zero + hh + 15) + '" text-anchor="middle" fill="' + col
        + '" font-size="11.5" font-weight="700">' + (it.v > 0 ? '+' : '') + it.v.toFixed(2) + '</text>'
        + '<text x="' + cx + '" y="' + (h - 30) + '" text-anchor="middle" fill="#8ea6bb" font-size="10.5">' + esc(it.l1) + '</text>'
        + '<text x="' + cx + '" y="' + (h - 15) + '" text-anchor="middle" fill="#5f7890" font-size="9.5">' + esc(it.l2 || '') + '</text>';
    });
    return '<svg viewBox="0 0 ' + w + ' ' + h + '" style="width:100%;height:' + h + 'px">'
      + '<line x1="' + L + '" y1="' + zero + '" x2="' + (w - R) + '" y2="' + zero + '" stroke="rgba(120,170,210,.30)"/>'
      + out + '</svg>';
  }

  /** 历史分位条：p 0-100 */
  function percentile(p, color) {
    return '<div style="height:8px;border-radius:5px;background:rgba(255,255,255,.07);position:relative;margin-top:4px">'
      + '<div style="position:absolute;left:calc(' + p + '% - 5px);top:-3px;width:10px;height:14px;border-radius:3px;background:'
      + (color || '#e6b45a') + '"></div></div>';
  }

  root.DDS = { spark, donut, ring, area, bars, percentile, esc };
})(window);
