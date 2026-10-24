/* 供应商报价核验报告 —— 前端交互（由 build_html.py 内联）。数据来自 window.SQV */
(function () {
  var M = window.SQV;
  var fmt = function (n, d) { if (n === null || n === undefined || isNaN(n)) return '—'; return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: d === undefined ? 0 : d, maximumFractionDigits: d === undefined ? 0 : d }); };
  var sign = function (n, d) { if (n === null || n === undefined) return '—'; var s = fmt(Math.abs(n), d); return (n > 0 ? '+' : n < 0 ? '−' : '') + s; };
  var pct = function (n, d) { if (n === null || n === undefined) return '—'; var s = fmt(Math.abs(n), d === undefined ? 2 : d); return (n > 0 ? '+' : n < 0 ? '−' : '') + s + '%'; };
  var esc = function (s) { return String(s === null || s === undefined ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };

  // ---------------- 页签
  var TABS = [
    ['overview', '报价 vs 市场'],
    ['targets', '口径校验与偏离'],
    ['history', '历史位置'],
    ['events', '行情变化'],
    ['evidence', '证据与缺口'],
    ['method', '计算公式']
  ];
  var tabsEl = document.getElementById('tabs');
  TABS.forEach(function (t, i) {
    var b = document.createElement('button');
    b.textContent = t[1]; b.dataset.k = t[0];
    if (i === 0) b.className = 'on';
    b.onclick = function () {
      document.querySelectorAll('#tabs button').forEach(function (x) { x.className = ''; });
      b.className = 'on';
      document.querySelectorAll('main > section').forEach(function (s) { s.classList.remove('on'); });
      document.getElementById('sec-' + t[0]).classList.add('on');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      if (window.__charts) window.__charts.forEach(function (c) { try { c.resize(); } catch (e) {} });
      if (t[0] === 'history' && window.__drawAnchors) setTimeout(window.__drawAnchors, 60);
    };
    tabsEl.appendChild(b);
  });

  function locate(id) {
    var tab = id.split(':')[0];
    var btn = document.querySelector('#tabs button[data-k="' + tab + '"]');
    if (btn) btn.click();
    setTimeout(function () {
      var el = document.getElementById(id.split(':')[1]);
      if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.style.transition = 'background .4s'; var o = el.style.background; el.style.background = '#fff7ed'; setTimeout(function () { el.style.background = o; }, 1400); }
    }, 200);
  }
  window.locate = locate;

  window.__charts = [];

  // ---------------- 首屏：市场区间 + 报价标记
  function renderRange() {
    var el = document.getElementById('rangebar');
    if (!el) return;
    var t = (M.targets || []).filter(function (x) { return x.status === '可比'; })[0];
    if (!t || t.low === null) { el.innerHTML = '<div class="alert gap">未取得同口径参考区间</div>'; return; }
    var q = t.quote, lo = t.low, hi = t.high;
    var min = Math.min(lo, q) * 0.985, max = Math.max(hi, q) * 1.015;
    var pos = function (v) { return (v - min) / (max - min) * 100; };
    el.innerHTML =
      '<div class="cap">' + esc(t.target_label) + '口径（元/吨，含税）· 参考区间 ' + fmt(lo) + ' – ' + fmt(hi) + '</div>' +
      '<div class="track" style="left:' + pos(lo) + '%;right:' + (100 - pos(hi)) + '%"></div>' +
      '<div class="mid" style="left:' + pos(t.center) + '%"></div>' +
      '<div class="tick" style="left:' + pos(lo) + '%;top:44px">' + fmt(lo) + '<br><span class="small">区间下沿</span></div>' +
      '<div class="tick" style="left:' + pos(t.center) + '%;top:44px">' + fmt(t.center) + '<br><span class="small">参考中枢</span></div>' +
      '<div class="tick" style="left:' + pos(hi) + '%;top:44px">' + fmt(hi) + '<br><span class="small">区间上沿</span></div>' +
      '<div class="mk" style="left:' + pos(q) + '%"><b>供应商报价 ' + fmt(q) + '</b><i></i></div>';
  }

  // ---------------- KPI
  function renderKPI() {
    var el = document.getElementById('kpis');
    var t = (M.targets || []).filter(function (x) { return x.status === '可比'; })[0] || {};
    var p1y = (M.percentiles || []).filter(function (p) { return p.window === '1y'; })[0] || {};
    var cards = [
      { lab: '供应商报价（测试输入）', val: fmt(M.quote.value) + ' <small>元/吨</small>', meta: M.quote.grade_claimed + ' · ' + (M.quote.tax.text || '') + ' · 出厂', cls: 'bad' },
      { lab: '市场参考中枢（' + (t.target_label || '—') + '）', val: fmt(t.center) + ' <small>元/吨</small>', meta: '同日 ' + (M.primary_anchor ? M.primary_anchor.date + ' · ' + M.primary_anchor.source_name : ''), cls: 'brand' },
      { lab: '偏离金额 / 偏离比例', val: sign(t.dev_center) + ' <small>元/吨</small>', meta: '偏离参考中枢 ' + pct(t.dev_center_pct), cls: t.dev_center > 0 ? 'bad' : 'ok' },
      { lab: '1 年历史分位（指数口径）', val: (p1y.quote_pctile === null || p1y.quote_pctile === undefined ? '缺口' : p1y.quote_pctile.toFixed(1) + '%'), meta: p1y.n ? '生意社基准价日频 · n=' + p1y.n : '样本不足', cls: 'warn' }
    ];
    el.innerHTML = cards.map(function (c) {
      return '<div class="kpi ' + c.cls + '"><div class="lab">' + esc(c.lab) + '</div><div class="val">' + c.val + '</div><div class="meta">' + c.meta + '</div></div>';
    }).join('');
  }

  // ---------------- 走势图（可切换窗口/口径）
  var HIST = M.history || {};
  function drawTrend(kind) {
    var dom = document.getElementById('chart-trend');
    if (!dom || !window.echarts) return;
    var cfg = {
      ppi: { src: (HIST.ppi_1y || []), name: '生意社乙二醇基准价（元/吨，含税，日频）', color: '#2563eb' },
      fut1y: { src: (HIST.fut_1y || []), name: 'EG0 期货收盘（元/吨，不含税，交易日）', color: '#7c3aed' },
      fut3m: { src: (HIST.fut_3m || []), name: 'EG0 期货收盘近 3 个月（元/吨，不含税）', color: '#0d9488' },
      fut3y: { src: (HIST.fut_3y || []), name: 'EG0 期货收盘近 3 年（元/吨，不含税）', color: '#b45309' }
    }[kind];
    if (!cfg || !cfg.src.length) { dom.innerHTML = '<div class="alert gap"><b>数据缺口：</b>本次未取得该窗口的序列，故不绘制走势图，也不计算该窗口分位（不使用估算或插值）。</div>'; return; }
    var ch = echarts.getInstanceByDom(dom) || echarts.init(dom);
    var data = cfg.src.map(function (p) { return [p.d, p.v]; });
    var evs = (M.events || []).map(function (e) {
      var d = e.d.match(/\d{4}-\d{2}/) ? e.d.slice(0, 7) : null;
      return d ? { d: d, t: e.title, f: e.fact } : null;
    }).filter(Boolean);
    var marks = {};
    var series = [{
      name: cfg.name, type: 'line', showSymbol: kind === 'fut3y', symbolSize: 4,
      lineStyle: { width: 2, color: cfg.color }, itemStyle: { color: cfg.color },
      areaStyle: { opacity: .08, color: cfg.color }, data: data,
      markLine: {
        symbol: 'none', label: { formatter: function (p) { return p.name; }, fontSize: 11 },
        lineStyle: { type: 'dashed', color: '#dc2626', width: 1.4 },
        data: [{ yAxis: (M.targets[0] || {}).quote, name: '报价 ' + fmt((M.targets[0] || {}).quote) }]
      }
    }];
    if (kind !== 'fut1y' && kind !== 'fut3m' && kind !== 'fut3y') {
      var evDates = (M.events || []).map(function (e) { var m = e.d.match(/\d{4}-\d{2}-\d{2}/); return m ? m[0] : null; }).filter(Boolean);
      series[0].markPoint = {
        symbolSize: 9, itemStyle: { color: '#dc2626' },
        label: { show: false },
        data: evDates.filter(function (d) { return d >= data[0][0] && d <= data[data.length - 1][0]; }).map(function (d) {
          var p = data.filter(function (x) { return x[0] <= d; }).pop();
          return p ? { coord: [p[0], p[1]], name: d } : null;
        }).filter(Boolean)
      };
    }
    ch.setOption({
      backgroundColor: '#fff',
      grid: { left: 64, right: 26, top: 44, bottom: 64 },
      tooltip: { trigger: 'axis', valueFormatter: function (v) { return fmt(v) + ' 元/吨'; } },
      legend: { top: 6, left: 8, textStyle: { fontSize: 12 } },
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 10 }],
      xAxis: { type: 'category', boundaryGap: false, axisLabel: { fontSize: 11 }, axisLine: { lineStyle: { color: '#cbd5e1' } } },
      yAxis: { type: 'value', scale: true, name: '元/吨', nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 }, splitLine: { lineStyle: { color: '#eef2f7' } } },
      series: series
    }, true);
    window.__charts.push(ch);
  }
  window.__drawTrend = drawTrend;

  function bindTrend() {
    var box = document.getElementById('trend-chips');
    if (!box) return;
    box.querySelectorAll('.chip').forEach(function (c) {
      c.onclick = function () {
        box.querySelectorAll('.chip').forEach(function (x) { x.className = 'chip'; });
        c.className = 'chip on';
        drawTrend(c.dataset.k);
      };
    });
    drawTrend('ppi');
  }

  // ---------------- 分位图
  function drawPct() {
    var dom = document.getElementById('chart-pct');
    if (!dom || !window.echarts) return;
    var rows = (M.percentiles || []);
    if (!rows.length) { dom.innerHTML = '<div class="alert gap"><b>数据缺口：</b>本次未取得任何可用于计算分位的有效序列。</div>'; return; }
    var cats = [], vals = [], colors = [];
    rows.forEach(function (r) {
      var lab = { '1y': '1 年 · 生意社基准价', '1y_fut': '1 年 · EG0 期货', '3y': '3 年 · EG0 期货', '3m': '3 个月 · 逐日快照' }[r.window] || r.window;
      cats.push(lab);
      if (r.quote_pctile === null || r.quote_pctile === undefined) { vals.push(null); colors.push('#cbd5e1'); }
      else { vals.push(r.quote_pctile); colors.push(r.quote_pctile >= 80 ? '#dc2626' : r.quote_pctile >= 50 ? '#d97706' : '#0f9d76'); }
    });
    var ch = echarts.getInstanceByDom(dom) || echarts.init(dom);
    ch.setOption({
      grid: { left: 130, right: 60, top: 20, bottom: 20 },
      xAxis: { type: 'value', max: 100, min: 0, name: '分位 %', axisLabel: { formatter: '{value}%', fontSize: 11 } },
      yAxis: { type: 'category', data: cats, axisLabel: { fontSize: 12 } },
      tooltip: { trigger: 'axis', formatter: function (p) { var r = rows[p[0].dataIndex]; return cats[p[0].dataIndex] + '<br>报价: ' + fmt(r.compared_value) + '<br>分位: ' + (vals[p[0].dataIndex] === null ? '缺口' : vals[p[0].dataIndex] + '%') + (r.n ? '<br>样本: ' + r.n + '（' + r.start + ' ~ ' + r.end + '）' : ''); } },
      series: [{
        type: 'bar', data: vals.map(function (v, i) { return { value: v, itemStyle: { color: colors[i], borderRadius: [0, 6, 6, 0] } }; }),
        barWidth: 18,
        label: { show: true, position: 'right', formatter: function (p) { return p.value === null || p.value === undefined ? '缺口' : p.value + '%'; }, fontSize: 12, fontWeight: 700 },
        markLine: { silent: true, symbol: 'none', lineStyle: { color: '#94a3b8', type: 'dashed' }, data: [{ xAxis: 50, label: { formatter: '中位', fontSize: 11 } }] }
      }]
    }, true);
    window.__charts.push(ch);
  }

  function drawSpot() {
    var dom = document.getElementById('chart-spot');
    if (!dom || !window.echarts) return;
    var s = M.spot_series_3m || [];
    if (!s.length) { dom.innerHTML = '<div class="alert gap"><b>数据缺口：</b>本次未取得逐日现货快照（少于 8 个交易日点则不构成有效样本）。</div>'; return; }
    var ch = echarts.getInstanceByDom(dom) || echarts.init(dom);
    ch.setOption({
      grid: { left: 64, right: 30, top: 36, bottom: 40 },
      tooltip: { trigger: 'axis', valueFormatter: function (v) { return fmt(v) + ' 元/吨'; } },
      xAxis: { type: 'category', data: s.map(function (x) { return x.date.slice(5); }), axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', scale: true, name: '元/吨', axisLabel: { fontSize: 11 }, splitLine: { lineStyle: { color: '#eef2f7' } } },
      series: [{
        type: 'line', data: s.map(function (x) { return x.value; }), symbolSize: 8,
        lineStyle: { width: 2.5, color: '#0d9488' }, itemStyle: { color: '#0d9488' },
        label: { show: true, fontSize: 11, formatter: '{c}' },
        markLine: { symbol: 'none', lineStyle: { type: 'dashed', color: '#dc2626' }, data: [{ yAxis: (M.targets[0] || {}).quote, label: { formatter: '报价 ' + fmt((M.targets[0] || {}).quote), fontSize: 11 } }] }
      }]
    }, true);
    window.__charts.push(ch);
  }

  function drawAnchors() {
    var dom = document.getElementById('chart-anchors');
    if (!dom || !window.echarts) return;
    var a = (window.SQVCHART || {}).anchor || [];
    if (!a.length) { dom.innerHTML = '<div class="alert gap"><b>数据缺口：</b>本次未取得该品种的年度锚点（锚点≠序列，且不出分位）。</div>'; return; }
    if (!dom.clientWidth) return;          // 隐藏页签内不初始化，切页时再画
    var ch = echarts.getInstanceByDom(dom) || echarts.init(dom);
    var years = a.map(function (x) { return String(x.year); });
    var lows = a.map(function (x) { return x.low; });
    var deltas = a.map(function (x) { return (x.high !== null && x.low !== null) ? Math.max(0, x.high - x.low) : 0; });
    var q = (M.targets[0] || {}).quote;
    var mult = function (x) { return x.high !== x.low; };
    ch.setOption({
      grid: { left: 62, right: 26, top: 34, bottom: 34 },
      tooltip: {
        trigger: 'axis',
        formatter: function (ps) {
          var i = ps[0].dataIndex, x = a[i];
          return String(x.year) + ' · ' + x.nature + '<br>区间/水平：' + fmt(x.low) + (x.high !== x.low ? ' – ' + fmt(x.high) : '') + ' 元/吨';
        }
      },
      legend: { top: 2, left: 4, itemWidth: 12, itemHeight: 10, textStyle: { fontSize: 11.5 } },
      xAxis: { type: 'category', data: years, axisLabel: { fontSize: 12 } },
      yAxis: { type: 'value', scale: true, name: '元/吨', nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 }, splitLine: { lineStyle: { color: '#eef2f7' } } },
      series: [
        { name: '透明底（占位）', type: 'bar', stack: 'r', silent: true, itemStyle: { color: 'transparent' }, data: lows },
        { name: '年度区间', type: 'bar', stack: 'r', barWidth: 30, itemStyle: { color: '#93c5fd', borderRadius: [4, 4, 0, 0] }, data: deltas,
          label: { show: true, position: 'top', fontSize: 10.5, formatter: function (p) { var x = a[p.dataIndex]; return x.high !== x.low ? fmt(x.high) : fmt(x.high); } } },
        { name: '供应商报价', type: 'scatter', symbolSize: 13, itemStyle: { color: '#dc2626' }, data: a.map(function () { return q; }) }
      ]
    }, true);
    window.__charts.push(ch);
  }
  window.__drawAnchors = drawAnchors;

  window.addEventListener('resize', function () { (window.__charts || []).forEach(function (c) { c.resize(); }); });
  document.addEventListener('DOMContentLoaded', function () {
    renderKPI(); renderRange(); bindTrend(); drawPct(); drawSpot(); drawAnchors();
  });
  if (document.readyState !== 'loading') { renderKPI(); renderRange(); bindTrend(); drawPct(); drawSpot(); drawAnchors(); }
})();
