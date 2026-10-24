/* app-core.js — 区域价差研究交互内核（纯计算，无 DOM 依赖，可在 Node/V8 中单测） */
(function (G) {
  'use strict';

  /* ---------- 通用 ---------- */
  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function num(x, d) { return isNum(x) ? x.toFixed(d == null ? 0 : d) : '—'; }
  function pct(x, d) { return isNum(x) ? x.toFixed(d == null ? 1 : d) + '%' : '—'; }
  function sgn(x) { return x > 0 ? '+' : ''; }
  function mean(a) { var s = 0, n = 0; for (var i = 0; i < a.length; i++) if (isNum(a[i])) { s += a[i]; n++; } return n ? s / n : null; }
  function sd(a) {
    var m = mean(a), n = 0, s = 0;
    if (m === null) return null;
    for (var i = 0; i < a.length; i++) if (isNum(a[i])) { s += (a[i] - m) * (a[i] - m); n++; }
    return n < 2 ? null : Math.sqrt(s / (n - 1));
  }
  function quantile(a, q) {
    var s = a.filter(isNum).slice().sort(function (x, y) { return x - y; });
    if (!s.length) return null;
    if (s.length === 1) return s[0];
    var pos = q * (s.length - 1), lo = Math.floor(pos), hi = Math.min(lo + 1, s.length - 1);
    return s[lo] * (1 - (pos - lo)) + s[hi] * (pos - lo);
  }
  /* ECDF 分位（并列取中秩），与 Python percentile_of 完全一致 */
  function percentileOf(v, sample) {
    if (!isNum(v)) return null;
    var less = 0, eq = 0, n = 0;
    for (var i = 0; i < sample.length; i++) {
      var x = sample[i];
      if (!isNum(x)) continue;
      n++;
      if (x < v - 1e-9) less++;
      else if (Math.abs(x - v) <= 1e-9) eq++;
    }
    if (!n) return null;
    return (less + 0.5 * eq) / n * 100;
  }
  function percentileLabel(p) {
    if (!isNum(p)) return '样本不足';
    if (p >= 90) return '历史高位（≥P90）';
    if (p >= 75) return '偏高（P75–P90）';
    if (p > 25) return '中枢区间（P25–P75）';
    if (p > 10) return '偏低（P10–P25）';
    return '历史低位（≤P10）';
  }
  function pearson(x, y) {
    var n = 0, sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
    for (var i = 0; i < x.length; i++) {
      if (!isNum(x[i]) || !isNum(y[i])) continue;
      n++; sx += x[i]; sy += y[i];
    }
    if (n < 3) return null;
    var mx = sx / n, my = sy / n;
    for (var j = 0; j < x.length; j++) {
      if (!isNum(x[j]) || !isNum(y[j])) continue;
      var dx = x[j] - mx, dy = y[j] - my;
      sxx += dx * dx; syy += dy * dy; sxy += dx * dy;
    }
    if (sxx < 1e-9 || syy < 1e-9) return null;
    return sxy / Math.sqrt(sxx * syy);
  }
  function daysBetween(a, b) { return Math.round((new Date(b) - new Date(a)) / 86400000); }

  /* ---------- 价差序列：spread(a,b) = p(a) - p(b) ---------- */
  function spreadSeries(payload, a, b) {
    var d = payload.dates, pa = payload.prices[a], pb = payload.prices[b], out = [];
    for (var i = 0; i < d.length; i++) {
      if (isNum(pa[i]) && isNum(pb[i])) out.push({ i: i, date: d[i], a: pa[i], b: pb[i], v: pa[i] - pb[i] });
    }
    return out;
  }
  function pairKey(a, b) { return a + '-' + b; }
  function unorderedPairs(regs) {
    var out = [];
    for (var i = 0; i < regs.length; i++) for (var j = i + 1; j < regs.length; j++) out.push([regs[i], regs[j]]);
    return out;
  }
  function orderedPairs(regs) {
    var out = [];
    for (var i = 0; i < regs.length; i++) for (var j = 0; j < regs.length; j++) if (i !== j) out.push([regs[i], regs[j]]);
    return out;
  }

  /* ---------- 窗口切片 ---------- */
  var WIN = { '1m': 30, '3m': 91, '6m': 182, '1y': 365, '2y': 730, '3y': 1095, '5y': 1825 };
  function windowSample(series, endDate, win) {
    if (!win || win === 'all') return series.map(function (x) { return x.v; });
    var days = WIN[win];
    if (days == null) return series.map(function (x) { return x.v; });
    var out = [];
    for (var i = 0; i < series.length; i++) {
      var dd = daysBetween(series[i].date, endDate);
      if (dd >= 0 && dd <= days) out.push(series[i].v);
    }
    return out;
  }
  function rangeFilter(payload, range) {
    if (!range || range === 'all') return { from: 0, to: payload.dates.length - 1 };
    var days = WIN[range] || 365;
    var end = payload.dates[payload.dates.length - 1];
    for (var i = 0; i < payload.dates.length; i++) {
      if (daysBetween(payload.dates[i], end) <= days) return { from: i, to: payload.dates.length - 1 };
    }
    return { from: 0, to: payload.dates.length - 1 };
  }

  /* ---------- 分位表（与 Python percentile_table 同口径） ---------- */
  function percentileTable(payload, pairs, windows, asOf) {
    var end = asOf || payload.dates[payload.dates.length - 1];
    return pairs.map(function (p) {
      var s = spreadSeries(payload, p[0], p[1]);
      if (!s.length) return { pair: pairKey(p[0], p[1]), a: p[0], b: p[1], n: 0 };
      var cur = s[s.length - 1].v, rec = {
        pair: pairKey(p[0], p[1]), a: p[0], b: p[1], current: cur,
        date: s[s.length - 1].date, n_total: s.length, windows: {}
      };
      windows.forEach(function (w) {
        var samp = windowSample(s, end, w);
        rec.windows[w] = {
          n: samp.length,
          pct: samp.length ? percentileOf(cur, samp) : null,
          min: samp.length ? Math.min.apply(null, samp) : null,
          max: samp.length ? Math.max.apply(null, samp) : null,
          median: samp.length ? quantile(samp, 0.5) : null,
          p10: samp.length ? quantile(samp, 0.10) : null,
          p90: samp.length ? quantile(samp, 0.90) : null,
          label: samp.length ? percentileLabel(percentileOf(cur, samp)) : '样本不足'
        };
      });
      return rec;
    });
  }

  /* ---------- 滚动 1 年分位（与 Python rolling_percentile 一致） ---------- */
  function rollingPercentile(series, windowDays, minN) {
    var out = [], wd = windowDays || 365, mn = minN || 30;
    for (var i = 0; i < series.length; i++) {
      var d0 = series[i].date, samp = [];
      for (var j = 0; j <= i; j++) {
        var dd = daysBetween(series[j].date, d0);
        if (dd >= 0 && dd <= wd) samp.push(series[j].v);
      }
      out.push({ date: d0, v: samp.length >= mn ? percentileOf(series[i].v, samp) : null, n: samp.length });
    }
    return out;
  }

  /* ---------- 运费 ---------- */
  function freightTotal(route, params) {
    var p = {};
    ['freight', 'loading_fee', 'unloading_fee', 'short_haul', 'handler'].forEach(function (k) {
      if (params && params[k] !== undefined) p[k] = params[k];
      else if (route && route[k] !== undefined) p[k] = route[k];
    });
    var f = p.freight;
    if (!isNum(f)) {
      return { known: false, total: null,
               comps: { freight: null, loading: p.loading_fee || 0, unloading: p.unloading_fee || 0,
                        short: p.short_haul || 0, handler: p.handler || 0 } };
    }
    var comps = {
      freight: f,
      loading: isNum(p.loading_fee) ? p.loading_fee : 0,
      unloading: isNum(p.unloading_fee) ? p.unloading_fee : 0,
      short: isNum(p.short_haul) ? p.short_haul : 0,
      handler: isNum(p.handler) ? p.handler : 0
    };
    var total = comps.freight + comps.loading + comps.unloading + comps.short + comps.handler;
    return { known: true, total: total, comps: comps };
  }

  function freightAdjusted(priceFrom, priceTo, route, params) {
    var ft = freightTotal(route, params);
    if (!ft.known) return { ok: false, reason: '主运费未知（不得按 0 计算）' };
    var landed = priceFrom + ft.total;
    return {
      ok: true,
      priceFrom: priceFrom, priceTo: priceTo,
      comps: ft.comps, total: ft.total,
      landed: landed,
      raw: priceTo - priceFrom,          // 与价差矩阵同向：to − from
      ref: priceTo - landed,             // 扣费后参考差异
      covers: priceTo - landed > 0
    };
  }

  /* ---------- 异常阶段：滚动 z（与 regime_scan 同口径的近似实现，仅用于前端提示） ---------- */
  function regimeScan(series, zThresh, minWeeks, win) {
    var z0 = zThresh == null ? 1.0 : zThresh, mw = minWeeks || 3, W = win || 52;
    var flags = [];
    for (var i = 0; i < series.length; i++) {
      var lo = Math.max(0, i - W + 1);
      var hist = [];
      for (var k = lo; k < i; k++) hist.push(series[k].v);
      if (hist.length < 8) { flags.push(false); continue; }
      var s = sd(hist), m = mean(hist);
      var z = (s && s > 1e-9) ? (series[i].v - m) / s : null;
      flags.push(z !== null && Math.abs(z) >= z0);
    }
    var out = [], i2 = 0;
    while (i2 < flags.length) {
      if (!flags[i2]) { i2++; continue; }
      var j = i2;
      while (j + 1 < flags.length && flags[j + 1]) j++;
      if (j - i2 + 1 >= mw) {
        var seg = series.slice(i2, j + 1).map(function (x) { return x.v; });
        var base = [];
        for (var k2 = Math.max(0, i2 - W); k2 < i2; k2++) base.push(series[k2].v);
        out.push({
          start: series[i2].date, end: series[j].date, n: seg.length,
          mean: mean(seg), maxAbs: seg.reduce(function (a, b) { return Math.abs(b) > Math.abs(a) ? b : a; }, seg[0]),
          base: mean(base), dev: mean(seg) - mean(base)
        });
      }
      i2 = j + 1;
    }
    return out;
  }

  /* ---------- 导出 ---------- */
  var API = {
    isNum: isNum, num: num, pct: pct, sgn: sgn, mean: mean, sd: sd, quantile: quantile,
    percentileOf: percentileOf, percentileLabel: percentileLabel, pearson: pearson,
    spreadSeries: spreadSeries, pairKey: pairKey, unorderedPairs: unorderedPairs, orderedPairs: orderedPairs,
    windowSample: windowSample, rangeFilter: rangeFilter, percentileTable: percentileTable,
    rollingPercentile: rollingPercentile, freightTotal: freightTotal, freightAdjusted: freightAdjusted,
    regimeScan: regimeScan, WIN: WIN
  };
  G.Core = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
