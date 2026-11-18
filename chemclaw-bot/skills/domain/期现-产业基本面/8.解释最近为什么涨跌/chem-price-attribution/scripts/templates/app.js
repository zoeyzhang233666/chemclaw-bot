/* ==========================================================================
   期现-产业基本面归因报告 · 前端应用
   数据全部来自内联的 window.__REPORT__，无外部请求。
   ========================================================================== */
(function () {
  'use strict';
  var D = window.__REPORT__ || {};
  var CH = {};           // 图表实例
  var GROUP_CN = { cost: '成本', supply: '供给', demand: '需求', inventory: '库存', trade: '贸易', policy: '政策/事件', structure: '期现结构' };
  var LV_TXT = (D.meta && D.meta.level_text) || { E1: '数据支持', E2: '数据+时间吻合', E3: '仅时间吻合', E4: '缺乏证据' };
  var COLORS = ['#4aa8ff', '#f2b23c', '#a67bff', '#22c08d', '#ff5c9d', '#3ad4c4', '#ff7a59', '#8fa6ff'];

  /* ---------------- 工具 ---------------- */
  function $(id) { return document.getElementById(id); }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function fmt(v, nd) {
    if (v === null || v === undefined || v === '' ) return '<span class="nd">—</span>';
    if (typeof v !== 'number') return esc(v);
    nd = nd === undefined ? 2 : nd;
    return v.toLocaleString('zh-CN', { minimumFractionDigits: nd, maximumFractionDigits: nd });
  }
  function pct(v, nd) {
    if (v === null || v === undefined) return '<span class="nd">无数据</span>';
    nd = nd === undefined ? 2 : nd;
    var c = v > 0 ? 'pos' : (v < 0 ? 'neg' : '');
    return '<span class="' + c + '">' + (v > 0 ? '+' : '') + v.toFixed(nd) + '%</span>';
  }
  function lvBadge(l) { return '<span class="badge b' + l + '">' + l + '</span>'; }
  function grpTag(g) { return '<span class="tag ' + g + '">' + (GROUP_CN[g] || g) + '</span>'; }
  function colorOf(g) { return ({ cost: '#f2b23c', supply: '#ff7a59', demand: '#a67bff', inventory: '#3ad4c4', trade: '#4aa8ff', policy: '#ff5c9d', structure: '#8fa6ff' })[g] || '#4aa8ff'; }

  var ECH = {
    textStyle: { color: '#9fb3c0', fontFamily: 'Inter, "PingFang SC", "Microsoft YaHei", sans-serif' },
    grid: { left: 58, right: 58, top: 42, bottom: 34 },
    backgroundColor: 'transparent'
  };
  function axisCommon(extra) {
    var o = {
      axisLine: { lineStyle: { color: '#33505f' } },
      axisLabel: { color: '#8fa3b0', fontSize: 11 },
      splitLine: { lineStyle: { color: '#1d2b38', type: 'dashed' } }
    };
    for (var k in (extra || {})) o[k] = extra[k];
    return o;
  }
  function mk(id) {
    var dom = $(id); if (!dom || !window.echarts) return null;
    if (CH[id]) { CH[id].dispose(); }
    var c = window.echarts.init(dom, null, { renderer: 'canvas' });
    CH[id] = c;
    return c;
  }
  function opt(c, o) { if (c) c.setOption(o, true); }

  /* ---------------- 0. 速览 ---------------- */
  function renderSummary() {
    var s = D.summary;
    $('k-spot').textContent = (s.spot_chg_pct > 0 ? '+' : '') + s.spot_chg_pct.toFixed(2) + '%';
    $('k-spot').className = 'val ' + (s.spot_chg_pct > 0 ? 'pos' : 'neg');
    $('k-spot-sub').innerHTML = fmt(s.spot_start, 2) + ' → ' + fmt(s.spot_end, 2) + ' 元/吨（' + (s.spot_abs > 0 ? '+' : '') + fmt(s.spot_abs, 2) + '）';
    $('k-fut').textContent = (s.fut_chg_pct > 0 ? '+' : '') + s.fut_chg_pct.toFixed(2) + '%';
    $('k-fut').className = 'val ' + (s.fut_chg_pct > 0 ? 'pos' : 'neg');
    $('k-fut-sub').innerHTML = fmt(s.fut_start, 0) + ' → ' + fmt(s.fut_end, 0) + ' 元/吨（主连，含 9/29 合约切换）';
    $('k-basis').innerHTML = fmt(s.basis_start, 0) + ' → ' + fmt(s.basis_end, 0);
    $('k-basis-sub').innerHTML = '峰值 ' + fmt(s.basis_max, 0) + '（' + s.basis_max_date + '）· 低点 ' + fmt(s.basis_min, 0) + '（' + s.basis_min_date + '）';
    $('k-ev').innerHTML = s.n_items + ' <span style="font-size:15px;color:#6a8392">/ ' + s.n_events + '</span>';
    $('k-ev-sub').innerHTML = 'E1 ' + s.level_counts.E1 + ' · E2 ' + s.level_counts.E2 + ' · E3 ' + s.level_counts.E3 + ' · E4 ' + s.level_counts.E4;

    $('one-liner').innerHTML = '<b>一句话：</b>' + esc(D.narrative.one_liner || '');

    // 主图
    var c = mk('chart-main'); if (!c) return;
    var dates = D.price.map(function (r) { return r.date; });
    var series = [
      { name: '现货（元/吨）', type: 'line', smooth: true, showSymbol: false, data: D.price.map(function (r) { return r.spot; }), lineStyle: { width: 2.4, color: '#4aa8ff' }, itemStyle: { color: '#4aa8ff' }, yAxisIndex: 0, connectNulls: false },
      { name: '期货主连（元/吨）', type: 'line', smooth: true, showSymbol: false, data: D.price.map(function (r) { return r.fut; }), lineStyle: { width: 2, color: '#f2b23c' }, itemStyle: { color: '#f2b23c' }, yAxisIndex: 0 },
      { name: '基差（元/吨）', type: 'line', smooth: true, showSymbol: false, data: D.price.map(function (r) { return r.basis; }), lineStyle: { width: 1.6, color: '#a67bff', type: 'dashed' }, itemStyle: { color: '#a67bff' }, yAxisIndex: 1, areaStyle: { color: 'rgba(166,123,255,.08)' } }
    ];
    // 异动日标注
    var spikes = D.price.filter(function (r) { return r.anomaly === 'spike'; });
    if (spikes.length) {
      series[1].markPoint = {
        symbol: 'pin', symbolSize: 34, itemStyle: { color: '#ff5c5c' },
        label: { color: '#fff', fontSize: 9 },
        data: spikes.map(function (r) { return { coord: [r.date, r.fut], value: (D.price.filter(function(x){return x.date===r.date;})[0].anomaly==='spike'?'⚡':'') }; })
      };
    }
    opt(c, Object.assign({}, ECH, {
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(16,26,35,.96)', borderColor: '#33505f', textStyle: { color: '#e6eef3', fontSize: 12 }, axisPointer: { type: 'cross', label: { backgroundColor: '#33505f' } } },
      legend: { data: series.map(function (x) { return x.name; }), textStyle: { color: '#9fb3c0', fontSize: 11 }, top: 4, itemWidth: 14, itemHeight: 8 },
      grid: { left: 56, right: 60, top: 40, bottom: 52 },
      xAxis: axisCommon({ type: 'category', data: dates, boundaryGap: false, axisLabel: { color: '#8fa3b0', fontSize: 10, interval: Math.max(0, Math.floor(dates.length / 8)) }, splitLine: { show: false } }),
      yAxis: [
        axisCommon({ type: 'value', name: '价格 元/吨', nameTextStyle: { color: '#6a8392', fontSize: 10 }, scale: true }),
        axisCommon({ type: 'value', name: '基差 元/吨', nameTextStyle: { color: '#6a8392', fontSize: 10 }, scale: true, splitLine: { show: false } })
      ],
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 8, borderColor: '#24333f', fillerColor: 'rgba(74,168,255,.14)', handleStyle: { color: '#4aa8ff' }, textStyle: { color: '#6a8392', fontSize: 10 } }],
      series: series
    }));

    // 分级分布
    var c2 = mk('chart-levels');
    var groups = ['cost', 'supply', 'demand', 'inventory', 'trade', 'policy', 'structure'];
    var levels = ['E1', 'E2', 'E3', 'E4'];
    var colmap = { E1: '#22c08d', E2: '#4aa8ff', E3: '#f2b23c', E4: '#7a8b96' };
    var data = levels.map(function (l) {
      return {
        name: l + ' ' + LV_TXT[l], type: 'bar', stack: 'x', barWidth: '58%',
        itemStyle: { color: colmap[l] },
        label: { show: true, color: '#04121e', fontSize: 10, fontWeight: 700, formatter: function (p) { return p.value > 0 ? p.value : ''; } },
        data: groups.map(function (g) {
          return D.tree.filter(function (t) { return t.group === g; }).reduce(function (a, t) { return a + (t.counts[l] || 0); }, 0);
        })
      };
    });
    opt(c2, Object.assign({}, ECH, {
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(16,26,35,.96)', borderColor: '#33505f', textStyle: { color: '#e6eef3', fontSize: 12 } },
      legend: { textStyle: { color: '#9fb3c0', fontSize: 11 }, top: 2, itemWidth: 12, itemHeight: 8 },
      grid: { left: 48, right: 20, top: 44, bottom: 30 },
      xAxis: axisCommon({ type: 'category', data: groups.map(function (g) { return GROUP_CN[g]; }), axisLabel: { color: '#8fa3b0', fontSize: 11, interval: 0 } }),
      yAxis: axisCommon({ type: 'value', name: '证据条目数', nameTextStyle: { color: '#6a8392', fontSize: 10 } }),
      series: data
    }));
  }

  /* ---------------- 1. 涨跌复核 ---------------- */
  function renderRehab() {
    var r = D.narrative.rehab || {};
    var box = $('rehab-body');
    box.innerHTML = (r.body || []).map(function (p) {
      return '<p>' + mdInline(p) + '</p>';
    }).join('');

    // 敏感性表
    var rows = D.sensitivity || [];
    var h = '<thead><tr><th>起点</th><th class="num">起点现货</th><th class="num">终点现货</th><th class="num">涨跌（元/吨）</th><th class="num">涨跌幅</th><th>说明</th></tr></thead><tbody>';
    rows.forEach(function (x) {
      h += '<tr><td><b>' + x.date + '</b></td><td class="num">' + fmt(x.start, 2) + '</td><td class="num">' + fmt(x.end, 2) + '</td><td class="num">' + (x.diff >= 0 ? '+' : '') + fmt(x.diff, 2) + '</td><td class="num">' + pct(x.pct) + '</td><td style="color:#9fb3c0">' + esc(x.note || '') + '</td></tr>';
    });
    h += '</tbody>';
    $('tbl-sens').innerHTML = h;
    $('rehab-caveat').innerHTML = '<b>口径提醒：</b>' + esc(D.narrative.rehab_caveat || '');
  }

  function mdInline(s) {
    return esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`(.+?)`/g, '<code>$1</code>');
  }

  /* ---------------- 2. 异动识别 ---------------- */
  function renderAnomalies() {
    var bars = (D.anomaly_bars || []);
    var rets = bars.map(function (b) { return b.ret; });
    var c = mk('chart-ret');
    if (c) {
      var sd = 1.0;
      var ups = bars.map(function (b) { return (b.z !== null && b.z >= 2) ? b.ret : null; });
      var dns = bars.map(function (b) { return (b.z !== null && b.z <= -2) ? b.ret : null; });
      opt(c, Object.assign({}, ECH, {
        tooltip: { trigger: 'axis', backgroundColor: 'rgba(16,26,35,.96)', borderColor: '#33505f', textStyle: { color: '#e6eef3', fontSize: 12 }, formatter: function (ps) { var p = ps[0]; var b = bars[p.dataIndex]; return b.date + '<br>日收益 <b>' + b.ret.toFixed(2) + '%</b><br>z = ' + (b.z === null ? '—' : b.z.toFixed(2)) + '<br>成交量 z = ' + (b.vol_z === null ? '—' : b.vol_z.toFixed(2)); } },
        grid: { left: 52, right: 20, top: 30, bottom: 46 },
        xAxis: axisCommon({ type: 'category', data: bars.map(function (b) { return b.date; }), axisLabel: { color: '#8fa3b0', fontSize: 10, interval: Math.max(0, Math.floor(bars.length / 7)) }, splitLine: { show: false } }),
        yAxis: axisCommon({ type: 'value', name: '日收益 %', nameTextStyle: { color: '#6a8392', fontSize: 10 } }),
        dataZoom: [{ type: 'inside' }],
        series: [
          { name: '日收益', type: 'bar', data: bars.map(function (b) { return { value: b.ret, itemStyle: { color: b.spike ? (b.ret > 0 ? '#ff5c5c' : '#22c08d') : 'rgba(120,140,155,.45)' } }; }) },
          { name: '±2σ 上界', type: 'line', data: bars.map(function (b) { return b.band_up; }), symbol: 'none', lineStyle: { color: 'rgba(242,178,60,.7)', type: 'dashed', width: 1 } },
          { name: '−2σ 下界', type: 'line', data: bars.map(function (b) { return b.band_dn; }), symbol: 'none', lineStyle: { color: 'rgba(242,178,60,.7)', type: 'dashed', width: 1 } },
          { name: '零轴', type: 'line', data: bars.map(function () { return 0; }), symbol: 'none', lineStyle: { color: '#33505f', width: 1 } }
        ]
      }));
    }

    var c2 = mk('chart-vol');
    if (c2) {
      opt(c2, Object.assign({}, ECH, {
        tooltip: { trigger: 'axis', backgroundColor: 'rgba(16,26,35,.96)', borderColor: '#33505f', textStyle: { color: '#e6eef3', fontSize: 12 } },
        legend: { textStyle: { color: '#9fb3c0', fontSize: 11 }, top: 2, itemWidth: 14, itemHeight: 8 },
        grid: { left: 58, right: 62, top: 40, bottom: 46 },
        xAxis: axisCommon({ type: 'category', data: bars.map(function (b) { return b.date; }), axisLabel: { color: '#8fa3b0', fontSize: 10, interval: Math.max(0, Math.floor(bars.length / 7)) }, splitLine: { show: false } }),
        yAxis: [
          axisCommon({ type: 'value', name: '成交量 手', nameTextStyle: { color: '#6a8392', fontSize: 10 } }),
          axisCommon({ type: 'value', name: '持仓量 手', nameTextStyle: { color: '#6a8392', fontSize: 10 }, splitLine: { show: false } })
        ],
        dataZoom: [{ type: 'inside' }],
        series: [
          { name: '成交量', type: 'bar', data: bars.map(function (b) { return b.volume; }), itemStyle: { color: 'rgba(74,168,255,.55)' } },
          { name: '持仓量', type: 'line', yAxisIndex: 1, data: bars.map(function (b) { return b.oi; }), symbol: 'none', lineStyle: { color: '#f2b23c', width: 2 } }
        ]
      }));
    }

    // 异动簇表
    var cl = D.anomaly_clusters || [];
    var h = '<thead><tr><th>起</th><th>止</th><th>方向</th><th class="num">幅度</th><th class="num">异动日数</th><th>异动日</th></tr></thead><tbody>';
    if (!cl.length) h += '<tr><td colspan="6" class="nd">窗口内未识别出同时满足「|z|≥2 且放量」的异动日</td></tr>';
    cl.forEach(function (x) {
      h += '<tr><td>' + x.start_date + '</td><td>' + x.end_date + '</td><td>' + (x.direction === 'up' ? '<span class="pos">上涨</span>' : '<span class="neg">下跌</span>') + '</td><td class="num">' + pct(x.chg_pct) + '</td><td class="num">' + x.n_spike_days + '</td><td style="font-family:var(--mono);font-size:11px;color:#9fb3c0">' + x.spike_dates.join(', ') + '</td></tr>';
    });
    h += '</tbody>';
    $('tbl-clusters').innerHTML = h;

    // 阶段表
    var ph = D.matrix || [];
    var h2 = '<thead><tr><th>阶段</th><th>起</th><th>止</th><th class="num">现货涨跌</th><th class="num">期货涨跌</th><th class="num">天数</th><th class="num">日波动率</th><th>收尾</th></tr></thead><tbody>';
    (D.phases || []).forEach(function (p) {
      h2 += '<tr><td><b>' + p.start_date + '</b></td><td>' + p.start_date + '</td><td>' + p.end_date + '</td><td class="num">' + pct(p.chg_pct) + '</td><td class="num">—</td><td class="num">' + (p.n_days || '—') + '</td><td class="num">' + (p.vol_daily_pct != null ? p.vol_daily_pct.toFixed(2) + '%' : '—') + '</td><td style="color:#9fb3c0">' + esc(p.end_kind || '') + '</td></tr>';
    });
    h2 += '</tbody>';
    $('tbl-phases').innerHTML = h2;
  }

  /* ---------------- 3. 归因树 ---------------- */
  var treeFilter = 'all';
  function renderTree() {
    var groups = ['cost', 'supply', 'demand', 'inventory', 'trade', 'policy', 'structure'];
    var fb = $('tree-filters');
    var counts = { all: 0 };
    D.tree.forEach(function (t) { counts[t.group] = (counts[t.group] || 0) + 1; counts.all++; });
    fb.innerHTML = '';
    fb.appendChild(chipBtn('全部因素', 'all', counts.all));
    groups.forEach(function (g) {
      if (counts[g]) fb.appendChild(chipBtn(GROUP_CN[g], g, counts[g]));
    });

    var list = $('tree-list');
    list.innerHTML = '';
    D.tree.forEach(function (t) {
      if (treeFilter !== 'all' && t.group !== treeFilter) return;
      var card = el('div', 'ev');
      card.innerHTML =
        '<div class="row1">' + lvBadge(t.level) + grpTag(t.group) +
        '<span class="ttl">' + esc(t.name) + '</span>' +
        '<span class="tag" style="font-family:var(--mono)">E1 ' + t.counts.E1 + ' · E2 ' + t.counts.E2 + ' · E3 ' + t.counts.E3 + ' · E4 ' + t.counts.E4 + '</span>' +
        '<span class="arrow">详情 ›</span></div>' +
        '<div class="rsn">' + esc((t.best && t.best.reason) || t.logic || '无可用数据') + '</div>' +
        '<div class="src">规则：' + esc(t.logic || '') + '</div>';
      card.onclick = function () { openDriver(t); };
      list.appendChild(card);
    });
    if (!list.children.length) list.innerHTML = '<div class="note">该分类下暂无因子。</div>';

    renderMatrix();
  }
  function chipBtn(label, key, n) {
    var b = el('div', 'chip' + (key !== 'all' ? ' ' + key : '') + (treeFilter === key ? ' on' : ''), label + '<span class="n">' + n + '</span>');
    b.onclick = function () { treeFilter = key; renderTree(); };
    return b;
  }

  function renderMatrix() {
    var cols = D.series_meta || [];
    var rows = D.matrix || [];
    var h = '<thead><tr><th style="min-width:130px">区间</th>';
    cols.forEach(function (c) { h += '<th class="num" style="min-width:74px;font-size:10px">' + esc(c.name) + '</th>'; });
    h += '</tr></thead><tbody>';
    rows.forEach(function (r) {
      h += '<tr><td style="font-size:11px;font-family:var(--mono)">' + r.start_date + '<br>→' + r.end_date + '</td>';
      cols.forEach(function (c) {
        var v = r.vals[c.id];
        if (v === null || v === undefined) { h += '<td class="c blank">—</td>'; return; }
        var bg = v > 0 ? 'rgba(255,92,92,' + Math.min(.55, Math.abs(v) / 60) + ')' : 'rgba(34,192,141,' + Math.min(.55, Math.abs(v) / 60) + ')';
        h += '<td class="c" style="background:' + bg + ';color:#fff">' + (v > 0 ? '+' : '') + v.toFixed(1) + '</td>';
      });
      h += '</tr>';
    });
    h += '</tbody>';
    $('tbl-matrix').innerHTML = h;
  }

  /* ---------------- 驱动详情抽屉 ---------------- */
  function openDriver(t) {
    var title = lvBadge(t.level) + ' ' + esc(t.name);
    $('drawer-title').innerHTML = title;
    var b = '';
    b += '<h4>周期规则与方向含义</h4><div class="note info">' + esc(t.logic || '—') + '</div>';

    b += '<h4>同期数据与变动幅度</h4>';
    if (t.series && t.series.length) {
      b += '<table><thead><tr><th>指标</th><th class="num">期初</th><th class="num">期末</th><th class="num">变动</th><th class="num">z</th><th class="num">末值分位</th></tr></thead><tbody>';
      t.series.forEach(function (s) {
        if (!s.ok) { b += '<tr><td>' + esc(s.name || s.id) + '</td><td colspan="5" class="nd">无可用数据</td></tr>'; return; }
        b += '<tr><td>' + esc(s.name) + '<div style="font-size:11px;color:#6a8392">' + esc(s.start_date) + ' → ' + esc(s.end_date) + ' ' + esc(s.unit || '') + '</div></td>' +
          '<td class="num">' + fmt(s.start_value) + '</td><td class="num">' + fmt(s.end_value) + '</td>' +
          '<td class="num">' + pct(s.pct_change) + '</td>' +
          '<td class="num">' + (s.z != null ? s.z.toFixed(2) : '—') + '</td>' +
          '<td class="num">' + (s.pctile_end != null ? s.pctile_end.toFixed(1) + '%' : '—') + '</td></tr>';
      });
      b += '</tbody></table>';
    }
    if (t.manual && t.manual.length) {
      b += '<table style="margin-top:12px"><thead><tr><th>指标</th><th>数值／表述</th><th>时间</th><th>等级</th></tr></thead><tbody>';
      t.manual.forEach(function (m) {
        b += '<tr><td>' + esc(m.k) + '</td><td>' + esc(m.v) + '</td><td style="font-size:11px">' + esc(m.date || '—') + '</td><td>' + lvBadge(m.grade || 'E3') + '</td></tr>';
      });
      b += '</tbody></table>';
    }

    // 图表
    var sid = (t.series || []).filter(function (s) { return D.series[s.id]; })[0];
    b += '<h4>走势图</h4><div id="drawer-chart" style="height:250px"></div>';
    b += '<div id="drawer-chart2" style="height:200px;margin-top:8px"></div>';

    b += '<h4>证据判断（逐条）</h4>';
    var items = t.items || [];
    items.sort(function (a, b2) { return a.rank - b2.rank; });
    items.forEach(function (it) {
      b += '<div style="border:1px solid #24333f;border-radius:8px;padding:10px 12px;margin-bottom:8px;background:#141e28">' +
        '<div style="display:flex;gap:8px;align-items:center;margin-bottom:4px">' + lvBadge(it.level) + '<b style="font-size:12.5px;color:#fff;flex:1">' + esc(it.series || '') + '</b>' +
        (it.date ? '<span class="tag" style="font-family:var(--mono)">' + it.date + '</span>' : '') + '</div>' +
        '<div style="font-size:12px;color:#9fb3c0">' + esc(it.reason || '') + '</div>' +
        (it.extra_note ? '<div style="font-size:11.5px;color:#6a8392;margin-top:4px">备注：' + esc(it.extra_note) + '</div>' : '') +
        (it.src ? '<div style="font-size:11px;color:#6a8392;margin-top:4px;font-family:var(--mono)">来源：' + esc(it.src) + '</div>' : '') +
        (it.src_url ? '<div style="font-size:11px;word-break:break-all;margin-top:2px"><a href="' + esc(it.src_url) + '" target="_blank" rel="noopener">' + esc(it.src_url) + '</a></div>' : '') +
        '</div>';
    });
    if (!items.length) b += '<div class="note">该因素暂无可用证据条目（记为 E4）。</div>';

    $('drawer-body').innerHTML = b;
    $('drawer-body').scrollTop = 0;
    openDrawer();

    setTimeout(function () {
      if (sid) {
        var c = mk('drawer-chart');
        var pts = D.series[sid.id].points;
        opt(c, Object.assign({}, ECH, {
          tooltip: { trigger: 'axis', backgroundColor: 'rgba(16,26,35,.96)', borderColor: '#33505f', textStyle: { color: '#e6eef3', fontSize: 12 } },
          grid: { left: 56, right: 24, top: 34, bottom: 30 },
          title: { text: sid.name + (sid.unit ? '（' + sid.unit + '）' : ''), textStyle: { color: '#9fb3c0', fontSize: 12, fontWeight: 400 }, left: 0, top: 0 },
          xAxis: axisCommon({ type: 'category', data: pts.map(function (p) { return p[0]; }), axisLabel: { color: '#8fa3b0', fontSize: 10, interval: Math.max(0, Math.floor(pts.length / 6)) }, splitLine: { show: false } }),
          yAxis: axisCommon({ type: 'value', scale: true }),
          series: [{ type: 'line', data: pts.map(function (p) { return p[1]; }), symbol: 'none', smooth: true, lineStyle: { color: colorOf(t.group), width: 2 }, areaStyle: { color: colorOf(t.group), opacity: .12 } }]
        }));
      }
      var c2 = mk('drawer-chart2');
      var pts = D.price;
      opt(c2, Object.assign({}, ECH, {
        tooltip: { trigger: 'axis', backgroundColor: 'rgba(16,26,35,.96)', borderColor: '#33505f', textStyle: { color: '#e6eef3', fontSize: 12 } },
        grid: { left: 56, right: 24, top: 18, bottom: 30 },
        title: { text: '对照：现货与期货主连', textStyle: { color: '#9fb3c0', fontSize: 12, fontWeight: 400 }, left: 0, top: 0 },
        legend: { top: 0, right: 0, textStyle: { color: '#9fb3c0', fontSize: 10 }, itemWidth: 12, itemHeight: 6 },
        xAxis: axisCommon({ type: 'category', data: pts.map(function (r) { return r.date; }), axisLabel: { color: '#8fa3b0', fontSize: 10, interval: Math.max(0, Math.floor(pts.length / 6)) }, splitLine: { show: false } }),
        yAxis: axisCommon({ type: 'value', scale: true }),
        series: [
          { name: '现货', type: 'line', data: pts.map(function (r) { return r.spot; }), symbol: 'none', lineStyle: { color: '#4aa8ff', width: 1.8 } },
          { name: '期货', type: 'line', data: pts.map(function (r) { return r.fut; }), symbol: 'none', lineStyle: { color: '#f2b23c', width: 1.8 } }
        ]
      }));
    }, 30);
  }

  /* ---------------- 4. 事件时间线 ---------------- */
  var evFilter = 'all';
  function renderEvents() {
    var groups = ['cost', 'supply', 'demand', 'inventory', 'trade', 'policy', 'structure'];
    var fb = $('event-filters');
    var cnt = { all: D.events.length };
    D.events.forEach(function (e) { cnt[e.group] = (cnt[e.group] || 0) + 1; });
    fb.innerHTML = '';
    fb.appendChild(evChip('全部事件', 'all', cnt.all));
    groups.forEach(function (g) { if (cnt[g]) fb.appendChild(evChip(GROUP_CN[g], g, cnt[g])); });

    var list = $('event-list');
    list.innerHTML = '';
    var evs = D.events.filter(function (e) { return evFilter === 'all' || e.group === evFilter; });
    if (!evs.length) list.innerHTML = '<div class="note">无事件</div>';
    evs.forEach(function (e) {
      var leadTxt = '';
      if (e.lead_days != null) {
        leadTxt = e.lead_days > 0 ? '<span class="tag" style="color:#22c08d;border-color:rgba(34,192,141,.4)">领先 ' + e.lead_days + ' 个交易日</span>'
          : '<span class="tag" style="color:#f2b23c;border-color:rgba(242,178,60,.4)">滞后 ' + Math.abs(e.lead_days) + ' 个交易日</span>';
      }
      var row = el('div', 'tl-row');
      row.innerHTML = '<div class="tl-date">' + e.date + '</div>' +
        '<div class="tl-body"><div class="t">' + esc(e.title) + '</div>' +
        '<div class="tl-lv">' + lvBadge(e.level) + grpTag(e.group) +
        (e.dir === 'up' ? '<span class="tag" style="color:#ff5c5c;border-color:rgba(255,92,92,.4)">利多</span>' : e.dir === 'down' ? '<span class="tag" style="color:#22c08d;border-color:rgba(34,192,141,.4)">利空</span>' : '') +
        leadTxt + '</div>' +
        '<div class="d" style="margin-top:4px">' + esc(e.magnitude || '') + '</div>' +
        (e.url ? '<div class="src"><a href="' + esc(e.url) + '" target="_blank" rel="noopener">' + esc(e.url) + '</a></div>' : '') +
        '</div>';
      list.appendChild(row);
    });

    // 事件散点图
    var c = mk('chart-events');
    if (!c) return;
    var pts = D.price.filter(function (r) { return r.spot; });
    var dates = pts.map(function (r) { return r.date; });
    var dmap = {}; dates.forEach(function (d, i) { dmap[d] = i; });
    var series = [{
      name: '现货', type: 'line', data: pts.map(function (r) { return r.spot; }), symbol: 'none',
      lineStyle: { color: 'rgba(74,168,255,.9)', width: 2 }, areaStyle: { color: 'rgba(74,168,255,.07)' }
    }];
    var show = D.events.filter(function (e) { return evFilter === 'all' || e.group === evFilter; });
    var data = show.map(function (e) {
      var idx = dmap[e.date];
      if (idx === undefined) { // 找最近的
        var best = -1, bd = 1e9;
        pts.forEach(function (r, i) { var dd = Math.abs(new Date(r.date) - new Date(e.date)); if (dd < bd) { bd = dd; best = i; } });
        idx = best;
      }
      return { value: [pts[idx].date, pts[idx].spot], ev: e, symbolSize: e.level === 'E1' ? 14 : e.level === 'E2' ? 11 : 8, itemStyle: { color: e.level === 'E1' ? '#22c08d' : e.level === 'E2' ? '#4aa8ff' : '#f2b23c' } };
    });
    series.push({
      name: '事件', type: 'scatter', data: data, symbol: 'pin',
      tooltip: { formatter: function (p) { var e = p.data.ev; return '<b>' + e.date + '</b><br>' + esc(e.title) + '<br>' + LV_TXT[e.level] + '（' + e.level + '）'; } },
      label: { show: false }
    });
    opt(c, Object.assign({}, ECH, {
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(16,26,35,.96)', borderColor: '#33505f', textStyle: { color: '#e6eef3', fontSize: 12 } },
      grid: { left: 56, right: 24, top: 30, bottom: 34 },
      xAxis: axisCommon({ type: 'category', data: dates, axisLabel: { color: '#8fa3b0', fontSize: 10, interval: Math.max(0, Math.floor(dates.length / 6)) }, splitLine: { show: false } }),
      yAxis: axisCommon({ type: 'value', scale: true, name: '现货 元/吨', nameTextStyle: { color: '#6a8392', fontSize: 10 } }),
      series: series
    }));
  }
  function evChip(label, key, n) {
    var b = el('div', 'chip' + (key !== 'all' ? ' ' + key : '') + (evFilter === key ? ' on' : ''), label + '<span class="n">' + n + '</span>');
    b.onclick = function () { evFilter = key; renderEvents(); };
    return b;
  }

  /* ---------------- 5. 候选解释 ---------------- */
  function renderHyp() {
    var box = $('hyp-list');
    box.innerHTML = '';
    (D.narrative.hypotheses || []).forEach(function (h) {
      var card = el('div', 'hyp');
      card.innerHTML = '<div class="hyp-hd"><div class="hyp-rank">' + h.rank + '</div>' +
        '<div class="hyp-claim">' + mdInline(h.claim) + '</div>' + lvBadge(h.level) +
        '<span style="color:#6a8392;font-size:18px;line-height:1">⌄</span></div>' +
        '<div class="hyp-bd">' +
        '<div class="sec">✓ 支持它的证据</div><ul>' + (h.supported_by || []).map(function (x) { return '<li>' + mdInline(x) + '</li>'; }).join('') + '</ul>' +
        '<div class="sec no">✗ 它不能证明什么 / 反证</div><ul>' + (h.not_proven || []).map(function (x) { return '<li>' + mdInline(x) + '</li>'; }).join('') + '</ul>' +
        '</div>';
      card.querySelector('.hyp-hd').onclick = function () { card.classList.toggle('open'); };
      box.appendChild(card);
    });
  }

  /* ---------------- 6. 分段归因 ---------------- */
  function renderPeriods() {
    var box = $('period-cards');
    box.innerHTML = '';
    (D.narrative.periods || []).forEach(function (p) {
      var card = el('div', 'card');
      card.style.background = '#16222e';
      card.style.padding = '16px 18px';
      var cands = (p.candidates || []).map(function (c) {
        return '<tr><td>' + lvBadge(c.level) + '</td><td><b>' + esc(c.factor) + '</b></td><td style="color:#9fb3c0">' + mdInline(c.note || '') + '</td></tr>';
      }).join('');
      card.innerHTML =
        '<div style="display:flex;gap:14px;align-items:baseline;flex-wrap:wrap;margin-bottom:8px">' +
        '<span class="badge bE2" style="background:#4aa8ff;color:#04121e;border:none">' + esc(p.id) + '</span>' +
        '<h3 style="margin:0;border:none;padding:0;font-size:15px">' + esc(p.name) + '</h3>' +
        '<span style="font-family:var(--mono);font-size:12px;color:#6a8392">' + p.start + ' → ' + p.end + '</span></div>' +
        '<div class="note info" style="margin-bottom:10px"><b>价格表现：</b>' + esc(p.price) + '</div>' +
        '<div class="prose">' + (Array.isArray(p.read) ? p.read : [p.read]).filter(Boolean).map(function (x) { return '<p>' + mdInline(x) + '</p>'; }).join('') + '</div>' +
        '<div class="heat"><table><thead><tr><th style="width:60px">等级</th><th style="width:190px">候选因素</th><th>证据说明</th></tr></thead><tbody>' + cands + '</tbody></table></div>';
      box.appendChild(card);
    });
  }

  /* ---------------- 7. 无法解释 ---------------- */
  function renderGaps() {
    var box = $('unexplained');
    box.innerHTML = '';
    (D.narrative.unexplained || []).forEach(function (u) {
      var d = el('div', 'ev');
      d.style.cursor = 'default';
      d.innerHTML = '<div class="row1"><span class="tag">' + esc(u.status) + '</span><span class="ttl">' + esc(u.item) + '</span></div>' +
        '<div class="rsn">' + mdInline(u.note || '') + '</div>';
      box.appendChild(d);
    });
    var g = D.narrative.data_gaps || [];
    var h = '<thead><tr><th>缺失项</th><th>为什么缺</th><th>影响</th></tr></thead><tbody>';
    g.forEach(function (x) {
      h += '<tr><td><b>' + esc(x.k) + '</b></td><td style="color:#9fb3c0;font-size:12px">' + esc(x.why) + '</td><td style="color:#f2b23c;font-size:12px">' + esc(x.impact) + '</td></tr>';
    });
    h += '</tbody>';
    $('tbl-gaps').innerHTML = h;
  }

  /* ---------------- 8. 方法 ---------------- */
  function renderMethod() {
    var h = '<thead><tr><th style="width:52px">等级</th><th>含义</th></tr></thead><tbody>';
    ['E1', 'E2', 'E3', 'E4'].forEach(function (l) {
      h += '<tr><td>' + lvBadge(l) + '</td><td>' + esc(LV_TXT[l]) + '</td></tr>';
    });
    h += '<tr><td colspan="2" style="color:#9fb3c0;font-size:11.5px;line-height:1.7">' +
      esc(D.meta.score_rule || '') + '<br><span style="color:#ff5c5c">' + esc(D.meta.disclaimer || '') + '</span></td></tr>';
    $('tbl-legend').innerHTML = h + '</tbody>';

    $('limitations').innerHTML = (D.narrative.limitations || []).map(function (x) {
      return '<div style="font-size:12.5px;color:#c4d4de;margin-bottom:8px;padding-left:14px;position:relative"><span style="position:absolute;left:0;color:#f2b23c">•</span>' + mdInline(x) + '</div>';
    }).join('');

    var sp = D.meta.spot_spec || {}, fu = D.meta.fut_spec || {};
    var rows = [
      ['现货价格', sp.name, '区域：' + (sp.region || '—') + '\n口径：' + (sp.spec || '') + '，' + (sp.tax || '') + '，' + (sp.basis || '') + '，' + (sp.unit || '')],
      ['期货价格', fu.name, '口径：' + (fu.tax || '不含税') + '，' + (fu.unit || '元/吨') + '\n切换说明：' + (fu.note || '')],
      ['煤炭价格', '秦皇岛港 5500 大卡动力煤现货', '来源：中国煤炭市场网 CCTD\n口径：港口现货价，含税，元/吨；非坑口价'],
      ['事件与月度数据', '生意社 PriceSeek／周评／月度统计', '来源：100ppi.com（每条原始 URL 见 Excel「05_事件清单」）\n口径：报告披露值，已逐条标注是否有数值'],
      ['下游产品', '大商所聚丙烯主连 PP0', '来源：新浪财经期货日线\n口径：期货结算前收盘价，不含税']
    ];
    var h2 = '';
    rows.forEach(function (r) {
      h2 += '<div style="border:1px solid #24333f;border-radius:8px;padding:10px 12px;margin-bottom:8px;background:#141e28">' +
        '<div style="font-size:11px;color:#6a8392;letter-spacing:.05em;text-transform:uppercase">' + esc(r[0]) + '</div>' +
        '<div style="font-size:13px;color:#fff;font-weight:600;margin:2px 0 4px">' + esc(r[1]) + '</div>' +
        '<div style="font-size:11.5px;color:#9fb3c0;white-space:pre-line;line-height:1.7">' + esc(r[2]) + '</div></div>';
    });
    $('sources').innerHTML = h2;
  }

  /* ---------------- 3+ 局部归因 ---------------- */
  var localRange = null;

  function localPct(a, b) { return a ? ((b / a - 1) * 100) : null; }

  function localRow(t, s, sid, start, end, dir) {
    var store = D.series[sid];
    if (!store || !store.points || !store.points.length) {
      return { driver: t.name, group: t.group, metric: s.name, level: 'E4', pct: null, dir: null,
               reason: '该指标无逐日序列（仅报告披露值）', unit: store && store.unit };
    }
    var seg = store.points.filter(function (p) { return p[0] >= start && p[0] <= end; });
    if (seg.length < 2) {
      return { driver: t.name, group: t.group, metric: s.name, level: 'E4', pct: null, dir: null,
               reason: '本区间内无观测', unit: store.unit };
    }
    var a = seg[0][1], b = seg[seg.length - 1][1];
    var p = (b / a - 1) * 100;
    var d2 = p > 0 ? 'up' : (p < 0 ? 'down' : 'flat');
    var rets = [];
    for (var i = 1; i < seg.length; i++) rets.push(seg[i][1] / seg[i - 1][1] - 1);
    var sd = 0;
    if (rets.length > 1) {
      var m = rets.reduce(function (x, y) { return x + y; }, 0) / rets.length;
      sd = Math.sqrt(rets.reduce(function (x, y) { return x + (y - m) * (y - m); }, 0) / rets.length);
    }
    var z = (sd > 0 && a > 0 && b > 0) ? (Math.log(b / a)) / (sd * Math.sqrt(rets.length)) : null;
    var sig = z !== null && Math.abs(z) >= 1.0;
    var lv, why;
    if (d2 === dir && sig) { lv = 'E1'; why = '区间内 ' + (p > 0 ? '+' : '') + p.toFixed(2) + '%（z=' + z.toFixed(2) + '），方向与现货一致且显著'; }
    else if (d2 !== dir && sig) { lv = 'E4'; why = '区间内 ' + (p > 0 ? '+' : '') + p.toFixed(2) + '%（z=' + z.toFixed(2) + '），方向与现货相反 → 不能解释本区间'; }
    else if (d2 === dir) { lv = 'E3'; why = '区间内 ' + (p > 0 ? '+' : '') + p.toFixed(2) + '%，方向一致但未达显著'; }
    else { lv = 'E4'; why = '区间内 ' + (p > 0 ? '+' : '') + p.toFixed(2) + '%，方向与现货相反'; }
    return { driver: t.name, group: t.group, metric: s.name, level: lv, pct: p, z: z, dir: d2, reason: why, unit: store.unit };
  }

  function computeLocal(start, end) {
    var pts = D.price.filter(function (r) { return r.date >= start && r.date <= end && r.spot; });
    if (pts.length < 2) return null;
    var spotA = pts[0].spot, spotB = pts[pts.length - 1].spot;
    var dir = spotB >= spotA ? 'up' : 'down';
    var rows = [];
    // 结构性指标（基差/月差/持仓量）也纳入局部归因，但不重复计入驱动树
    var EXTRA = ['basis_base', 'spread_base', 'oi'];
    var structureSrc = (D.tree || []).filter(function (t) { return t.group === 'structure'; })[0];
    var extraGroup = structureSrc ? structureSrc.group : 'structure';
    EXTRA.forEach(function (k) {
      var s = D.series[k];
      if (!s || !s.points || !s.points.length) return;
      rows.push(localRow({ name: (structureSrc ? structureSrc.name : '期现结构'), group: extraGroup },
                         s, k, start, end, dir));
    });
    (D.tree || []).forEach(function (t) {
      (t.series || []).forEach(function (s) {
        rows.push(localRow(t, s, s.id, start, end, dir));
      });
      // 只有报告披露值、没有逐日序列的因子，也要显式列出来（标为无逐日数据），
      // 绝不能让它们在局部归因里"消失"。
      (t.manual || []).forEach(function (m) {
        rows.push({ driver: t.name, group: t.group, metric: m.k, level: 'E3', pct: null, dir: m.dir || null,
                    reason: '仅有报告披露值（无逐日序列，无法做区间重算）：' + (m.v || ''), unit: '' });
      });
    });
    rows.sort(function (a, b) {
      var w = { E1: 4, E2: 3, E3: 2, E4: 1 };
      return w[b.level] - w[a.level];
    });
    var evs = (D.events || []).filter(function (e) { return e.date >= start && e.date <= end; });
    var counters = rows.filter(function (r) { return r.level === 'E4' && r.dir && r.dir !== 'off' && r.dir !== dir && r.pct !== null; });
    return { start: start, end: end, spotA: spotA, spotB: spotB, pct: localPct(spotA, spotB), dir: dir,
             rows: rows, events: evs, counters: counters, n: pts.length,
             futA: pts[0].fut, futB: pts[pts.length - 1].fut };
  }

  function renderLocal(start, end) {
    var res = computeLocal(start, end);
    localRange = res;
    var box = $('local-controls');
    var dates = D.price.filter(function (r) { return r.spot; }).map(function (r) { return r.date; });
    box.innerHTML = '';
    var lbl = function (txt) { var s = document.createElement('span'); s.style.cssText = 'font-size:12px;color:#9fb3c0'; s.textContent = txt; return s; };
    var mkSel = function (val, onChange) {
      var s = document.createElement('select');
      s.style.cssText = 'background:#101a23;color:#e6eef3;border:1px solid #33505f;border-radius:6px;padding:4px 8px;font-size:12px;font-family:var(--mono)';
      dates.forEach(function (d) { var o = document.createElement('option'); o.value = d; o.textContent = d; if (d === val) o.selected = true; s.appendChild(o); });
      s.onchange = function () { onChange(s.value); };
      return s;
    };
    var cur = res || { start: start, end: end };
    box.appendChild(lbl('起点'));
    box.appendChild(mkSel(cur.start, function (v) { renderLocal(v, cur.end > v ? cur.end : dates[dates.length - 1]); }));
    box.appendChild(lbl('终点'));
    box.appendChild(mkSel(cur.end, function (v) { renderLocal(cur.start < v ? cur.start : dates[0], v); }));
    // 快捷区间
    (D.phases || []).slice(-5).forEach(function (p) {
      var b = el('div', 'chip', p.start_date.slice(5) + '→' + p.end_date.slice(5));
      b.onclick = function () { renderLocal(p.start_date, p.end_date); };
      box.appendChild(b);
    });
    var all = el('div', 'chip', '全窗口');
    all.onclick = function () { renderLocal(dates[0], dates[dates.length - 1]); };
    box.appendChild(all);

    if (!res) {
      $('tbl-local').innerHTML = '<tbody><tr><td class="nd">所选区间不足 2 个观测，无法归因</td></tr></tbody>';
      $('local-events').innerHTML = '';
      $('local-counter').style.display = 'none';
      return;
    }

    var head = '<div style="font-size:13px;margin-bottom:8px;color:#cfdce4">' +
      '区间 <b style="font-family:var(--mono)">' + res.start + ' → ' + res.end + '</b>（' + res.n + ' 个交易日）｜' +
      '现货 <b style="font-family:var(--mono)">' + res.spotA.toFixed(2) + ' → ' + res.spotB.toFixed(2) + '</b>｜' +
      '<span class="' + (res.pct > 0 ? 'pos' : 'neg') + '" style="font-family:var(--mono);font-weight:700">' +
      (res.pct > 0 ? '+' : '') + res.pct.toFixed(2) + '%</span>' +
      (res.futA && res.futB ? '｜期货 ' + res.futA.toFixed(0) + ' → ' + res.futB.toFixed(0) : '') + '</div>';

    var h = '<thead><tr><th style="width:52px">等级</th><th>因子</th><th>指标</th><th class="num">区间变化</th><th>判断</th></tr></thead><tbody>';
    res.rows.forEach(function (r) {
      h += '<tr><td>' + lvBadge(r.level) + '</td><td>' + grpTag(r.group) + ' ' + esc(r.driver) + '</td><td>' + esc(r.metric) +
        '</td><td class="num">' + (r.pct === null ? '<span class="nd">无数据</span>' : pct(r.pct)) + '</td>' +
        '<td style="color:#9fb3c0;font-size:12px">' + esc(r.reason) + '</td></tr>';
    });
    $('tbl-local').innerHTML = head + h + '</tbody>';

    var eb = '';
    if (!res.events.length) eb = '<div class="note">本区间内没有已收录的带日期事件。</div>';
    res.events.forEach(function (e) {
      eb += '<div style="border-bottom:1px dashed #24333f;padding:9px 0">' +
        '<div style="font-family:var(--mono);font-size:11px;color:#6a8392">' + e.date + '</div>' +
        '<div style="font-size:12.5px;color:#fff">' + esc(e.title) + '</div>' +
        '<div style="margin-top:4px">' + lvBadge(e.level) + grpTag(e.group) + '</div>' +
        (e.url ? '<div style="font-size:10.5px;word-break:break-all;margin-top:3px"><a href="' + esc(e.url) + '" target="_blank" rel="noopener">' + esc(e.url) + '</a></div>' : '') +
        '</div>';
    });
    $('local-events').innerHTML = eb;

    var cb = $('local-counter');
    if (res.counters.length) {
      cb.style.display = 'block';
      cb.innerHTML = '<b>反证（在本区间内方向与价格相反，不能用来解释本区间）：</b><br>' +
        res.counters.map(function (r) {
          return '• ' + esc(r.driver) + '（' + esc(r.metric) + '）区间内 ' + (r.pct > 0 ? '+' : '') + r.pct.toFixed(2) + '%';
        }).join('<br>');
    } else { cb.style.display = 'none'; }

    drawLocalChart(dates);
  }

  function drawLocalChart(dates) {
    var c = mk('chart-local');
    if (!c) return;
    var pts = D.price.filter(function (r) { return r.spot; });
    var rng = localRange;
    var bg = [];
    if (rng) {
      var i0 = dates.indexOf(rng.start), i1 = dates.indexOf(rng.end);
      if (i0 >= 0 && i1 >= 0) bg.push([{ xAxis: rng.start }, { xAxis: rng.end }]);
    }
    opt(c, Object.assign({}, ECH, {
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(16,26,35,.96)', borderColor: '#33505f', textStyle: { color: '#e6eef3', fontSize: 12 } },
      grid: { left: 58, right: 24, top: 34, bottom: 30 },
      title: { text: '拖拽框选区间（左右拖动或用滚轮选中一段）', textStyle: { color: '#6a8392', fontSize: 11, fontWeight: 400 }, left: 0, top: 0 },
      xAxis: axisCommon({ type: 'category', data: pts.map(function (r) { return r.date; }), boundaryGap: false, axisLabel: { color: '#8fa3b0', fontSize: 10, interval: Math.max(0, Math.floor(pts.length / 10)) }, splitLine: { show: false } }),
      yAxis: axisCommon({ type: 'value', scale: true, name: '元/吨', nameTextStyle: { color: '#6a8392', fontSize: 10 } }),
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 6, borderColor: '#24333f', fillerColor: 'rgba(74,168,255,.14)', handleStyle: { color: '#4aa8ff' }, textStyle: { color: '#6a8392', fontSize: 10 } }],
      series: [{
        name: '现货', type: 'line', data: pts.map(function (r) { return r.spot; }), symbol: 'none', smooth: true,
        lineStyle: { color: '#4aa8ff', width: 2 }, areaStyle: { color: 'rgba(74,168,255,.10)' },
        markArea: bg.length ? { silent: true, itemStyle: { color: 'rgba(242,178,60,.16)' }, label: { show: true, color: '#f2b23c', fontSize: 10, position: 'insideTop' }, data: bg } : undefined
      }]
    }));
    // 框选事件：用带刷新开关的 brush，避免与内置的 dataZoom 拖拽冲突
    try {
      c.dispatchAction({ type: 'takeGlobalCursor', key: 'brush', brushOption: { brushType: 'lineX', brushMode: 'single' } });
      c.off('brushEnd');
      c.on('brushEnd', function (p) {
        if (!p.areas || !p.areas.length) return;
        var a = p.areas[0].coordRange;
        if (!a || a.length < 2) return;
        var s = pts[a[0]] && pts[a[0]].date, e = pts[a[1]] && pts[Math.min(a[1], pts.length - 1)].date;
        if (s && e && s !== e) setTimeout(function () { renderLocal(s, e); }, 30);
      });
    } catch (e) { /* 老版本 echarts 不支持 brush 时静默降级，下拉框仍可用 */ }
  }

  /* ---------------- 抽屉控制 ---------------- */
  function openDrawer() { $('drawer').classList.add('on'); $('mask').classList.add('on'); }
  function closeDrawer() { $('drawer').classList.remove('on'); $('mask').classList.remove('on'); }

  /* ---------------- 启动 ---------------- */
  function boot() {
    if (!window.echarts) {
      document.querySelectorAll('.chart').forEach(function (d) { d.innerHTML = '<div class="note danger">ECharts 未加载（报告生成异常），图表不可用，但所有表格与结论不受影响。</div>'; });
    }
    renderSummary();
    renderRehab();
    renderAnomalies();
    renderTree();
    renderLocal((D.phases && D.phases.length ? D.phases[D.phases.length - 1].start_date : D.price[0].date),
                D.price[D.price.length - 1].date);
    renderEvents();
    renderHyp();
    renderPeriods();
    renderGaps();
    renderMethod();
    $('drawer-close').onclick = closeDrawer;
    $('mask').onclick = closeDrawer;
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDrawer(); });
    var t;
    window.addEventListener('resize', function () {
      clearTimeout(t);
      t = setTimeout(function () { for (var k in CH) { try { CH[k].resize(); } catch (e) { } } }, 120);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
