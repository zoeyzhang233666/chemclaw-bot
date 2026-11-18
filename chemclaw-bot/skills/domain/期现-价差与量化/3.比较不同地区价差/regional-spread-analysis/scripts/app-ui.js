/* app-ui.js — 渲染与交互（依赖 Core 与 ECharts） */
(function (G) {
  'use strict';
  var Core = G.Core;
  var isNum = Core.isNum, num = Core.num, pctf = Core.pct, sgn = Core.sgn;

  var P = null;                 // payload
  var S = {                     // 状态
    caliber: 'primary',
    regionOn: {},
    range: 'all',
    priceMode: 'price',
    pair: null,
    rollPair: null,
    regimePair: null,
    freightOn: false,
    freightSrc: 'default',
    freight: {},
    params: { loading_fee: 8, unloading_fee: 10, short_haul: 0, handler: 2 },
    eventFilter: '全部'
  };
  var CHARTS = {};

  var COLORS = {
    SD: '#4da3ff', HB: '#fbbf24', JS: '#7ee0c0',
    SD2: '#3b82f6', HB2: '#f59e0b', JS2: '#34d399'
  };
  function regionColor(id) { return COLORS[id] || '#8b9bb4'; }

  /* ---------------- 工具 ---------------- */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }
  function el(id) { return document.getElementById(id); }
  function html(id, s) { var e = el(id); if (e) e.innerHTML = s; }
  function cal(name) {
    var k = name === 'control' ? 'control' : 'primary';
    return P[k];
  }
  var cur = function () { return cal(S.caliber); };
  function names() { var n = {}; P.meta.regions.forEach(function (r) { n[r.id] = r.name; }); return n; }
  function regs() { return P.meta.regions.map(function (r) { return r.id; }); }
  function rr(id) { return (P.meta.regions.filter(function (r) { return r.id === id; })[0] || { name: id }); }
  function nowCal() { return cur(); }
  function series() { return nowCal().series; }
  function pairLabel(a, b) {
    var n = names();
    return (n[a] || a) + ' − ' + (n[b] || b);
  }
  function fmtMoney(v, d) { return isNum(v) ? (v >= 0 ? '' : '') + v.toFixed(d == null ? 1 : d) : '—'; }

  function chart(id) {
    var dom = el(id);
    if (!dom) return null;
    if (!CHARTS[id]) {
      CHARTS[id] = echarts.init(dom, null, { renderer: 'canvas' });
      window.addEventListener('resize', function () { CHARTS[id].resize(); });
    }
    return CHARTS[id];
  }
  var AXIS = {
    axisLine: { lineStyle: { color: '#2f3c4f' } },
    axisLabel: { color: '#8b9bb4', fontSize: 11 },
    splitLine: { lineStyle: { color: 'rgba(37,48,63,.7)' } }
  };
  var TIP = {
    backgroundColor: 'rgba(7,11,16,.95)', borderColor: '#2f3c4f', borderWidth: 1,
    textStyle: { color: '#e6ecf5', fontSize: 12 },
    extraCssText: 'border-radius:9px;box-shadow:0 10px 30px rgba(0,0,0,.5);'
  };

  /* ---------------- 页头 ---------------- */
  function renderHeader() {
    var m = P.meta;
    el('subline').innerHTML =
      esc(m.spec) + ' ｜ 单位 ' + esc(m.unit) + ' ｜ 频率 ' + esc(m.frequency === 'weekly' ? '周度' : m.frequency) +
      ' ｜ 样本 ' + esc(m.start) + ' ~ ' + esc(m.end) + '（' + m.n_observations + ' 期）';
    var b = [];
    if (m.data_status === 'DEMO') b.push('<span class="badge demo">⚠ DEMO 拟真数据 · 非真实报价</span>');
    else if (m.data_status === 'REAL') b.push('<span class="badge ok">真实市场数据</span>');
    else b.push('<span class="badge warn">客户提供数据（' + esc(m.data_status) + '）</span>');
    b.push('<span class="badge info">主口径：' + esc(P.meta.calibers[m.primary_caliber] ? P.meta.calibers[m.primary_caliber].label : m.primary_caliber) + '</span>');
    if (m.caliber_control) b.push('<span class="badge">对照：' + esc(P.meta.calibers[m.caliber_control].label) + '</span>');
    b.push('<span class="badge">' + m.regions.length + ' 个地区 · ' + (m.regions.length * (m.regions.length - 1)) + ' 个有序对</span>');
    b.push('<span class="badge">对齐：' + esc(m.align_method === 'weekly' ? 'ISO 周' : m.align_method) + '</span>');
    if (!m.hedge_online) b.push('<span class="badge">未接入期货 · 仅区域现货</span>');
    el('badges').innerHTML = b.join('');
    el('stamp').innerHTML = '生成日期<br><b class="mono">' + esc(m.as_run || '—') + '</b><br>数据截止 ' + esc(m.end);
  }

  function renderNav() {
    var items = [
      ['s-summary', '结论摘要'], ['s-caliber', '① 口径统一'], ['s-price', '② 价格与对齐'],
      ['s-spread', '③ 两两价差'], ['s-pct', '④ 历史分位'], ['s-freight', '⑤ 物流与运费'],
      ['s-regime', '⑥ 异常阶段'], ['s-map', '⑦ 区域地图'], ['s-notes', '⑧ 缺口与声明']
    ];
    html('nav', items.map(function (it, i) {
      return '<button data-t="' + it[0] + '"' + (i === 0 ? ' class="on"' : '') + '>' + it[1] + '</button>';
    }).join(''));
    Array.prototype.forEach.call(el('nav').querySelectorAll('button'), function (b) {
      b.addEventListener('click', function () {
        var t = el(b.dataset.t);
        if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' });
        Array.prototype.forEach.call(el('nav').querySelectorAll('button'), function (x) { x.classList.remove('on'); });
        b.classList.add('on');
      });
    });
  }

  /* ---------------- 0 摘要 ---------------- */
  function renderSummary() {
    var m = P.meta, pr = P.primary;
    el('summary-desc').innerHTML =
      '产品：' + esc(m.product) + '（' + esc(m.spec) + '）。比较 ' +
      m.regions.map(function (r) { return '<b>' + esc(r.full_name) + '</b>'; }).join('、') +
      ' 三个地区的现货价差，截止 ' + esc(m.end) + '。';

    if (m.data_status === 'DEMO') {
      el('demo-banner').innerHTML =
        '<div class="demobox"><b>⚠ 数据状态：DEMO 拟真数据。</b> 山东、河北、江苏的城市级独立日度序列在免费公开源中【未查到】，' +
        '本报告的价格序列以<b>已核实的真实价格骨架</b>（如 2023-09-01 华北重碱 3200 / 华东 3150、2024 年重碱终端均价 1953、' +
        '2025 年重碱区间 860—1450、沙河年均 1275、2025-12-31 生意社基准价 1225.71）为锚点构造，用于演示完整方法。' +
        '<b>金额与分位不可用于报价、交易或对外引用。</b> 替换真实数据：把 CSV 换成同结构文件后重跑 <code>init_analysis.py → analyze.py → build_html.py</code>。</div>';
    } else { el('demo-banner').innerHTML = ''; }

    // KPI
    var ls = pr.level_stats, order = pr.region_order;
    var k = [], n = names();
    order.forEach(function (r) {
      var st = ls[r];
      k.push('<div class="kpi"><div class="k">' + esc(n[r]) + '<span class="pill info">' + esc(rr(r).rep_market || '') + '</span></div>' +
        '<div class="v mono">' + num(st.current, 0) + '<small>元/吨</small></div>' +
        '<div class="s">1 年分位 ' + pctf(st.pct_1y) + '（' + esc(esc(rr(r).role || '')) + '）</div></div>');
    });
    // 主价差：取离散度最大的无序对
    var up = Core.unorderedPairs(order).map(function (p) {
      var s = Core.spreadSeries(series(), p[0], p[1]);
      if (!s.length) return null;
      var sdv = Core.sd(s.map(function (x) { return x.v; }));
      return { p: p, cur: s[s.length - 1].v, sd: sdv, n: s.length };
    }).filter(Boolean).sort(function (a, b) { return (b.sd || 0) - (a.sd || 0); });
    if (up.length) {
      var t = up[0];
      var rec = (pr.percentiles || []).filter(function (x) { return x.pair === Core.pairKey(t.p[0], t.p[1]); })[0];
      var w1 = rec && rec.windows ? rec.windows['1y'] : null, w3 = rec && rec.windows ? rec.windows['3y'] : null;
      k.push('<div class="kpi pos"><div class="k">波动最大价差<span class="pill">' + esc(pairLabel(t.p[0], t.p[1])) + '</span></div>' +
        '<div class="v mono">' + num(t.cur, 0) + '<small>元/吨</small></div>' +
        '<div class="s">1y 分位 ' + pctf(w1 && w1.pct) + ' ｜ 3y 分位 ' + pctf(w3 && w3.pct) + '</div></div>');
    }
    // 口径
    k.push('<div class="kpi violet"><div class="k">口径一致性</div><div class="v">' +
      (Object.keys(pr.normalize_report || {}).every(function (x) { return !(pr.normalize_report[x].missing || []).length; })
        ? '<span style="color:#3ddc97">✓ 可比</span>' : '<span style="color:#ffc857">⚠ 有缺失</span>') +
      '</div><div class="s">' + esc(m.calibers[m.primary_caliber].short || '') + ' ｜ 三地区同税基</div></div>');
    // 运费状态
    var fr = P.primary.freight.routes || [];
    var hasProvided = fr.some(function (x) { return x.freight_basis === 'provided'; });
    k.push('<div class="kpi warn"><div class="k">运费数据状态</div><div class="v" style="font-size:19px">' +
      (hasProvided ? '部分真实报价' : '仅默认参考值') + '</div>' +
      '<div class="s">' + (hasProvided ? '逐条标注来源' : '未提供真实运费 → 不做套利判断') + '</div></div>');
    el('kpis').innerHTML = k.join('');

    renderConclusion();
    renderReadme();

    var emb = pr.freight_embedded_in_price;
    el('caliber-warn').innerHTML = emb
      ? '<div class="warnbox"><b>⚠ 关键口径提醒：主口径为「送到价」，运费已内含在报价里。</b>' +
        esc(pr.freight_embedded_warning) + '</div>'
      : '<div class="okbox"><b>主口径为「出厂价」，不含运费。</b>区域价差必须叠加运费才能与「到货成本」比较，见第 ⑤ 节。</div>';
  }

  function renderConclusion() {
    var pr = P.primary, n = names(), order = pr.region_order;
    var lines = [];
    var ls = pr.level_stats;
    lines.push('<b>价格水平：</b>' + order.map(function (r) {
      return esc(n[r]) + ' ' + num(ls[r].current, 0) + '（1 年分位 ' + pctf(ls[r].pct_1y) + '）';
    }).join('，') + '。');
    var up = Core.unorderedPairs(order).map(function (p) {
      var s = Core.spreadSeries(series(), p[0], p[1]);
      if (!s.length) return null;
      var rec = (pr.percentiles || []).filter(function (x) { return x.pair === Core.pairKey(p[0], p[1]); })[0];
      return { p: p, cur: s[s.length - 1].v, w1: rec.windows['1y'], w3: rec.windows['3y'],
               mean: Core.mean(s.map(function (x) { return x.v; })) };
    }).filter(Boolean);
    lines.push('<b>价差现状：</b>' + up.map(function (t) {
      return esc(pairLabel(t.p[0], t.p[1])) + ' = <span class="mono">' + num(t.cur, 0) + '</span>（历史均值 ' +
        num(t.mean, 0) + '；1y 分位 ' + pctf(t.w1.pct) + '，3y 分位 ' + pctf(t.w3.pct) + '）';
    }).join('；') + '。');
    var hi = up.filter(function (t) { return isNum(t.w1.pct) && (t.w1.pct >= 90 || t.w1.pct <= 10); });
    if (hi.length) {
      lines.push('<b>处在历史边缘的价差：</b>' + hi.map(function (t) {
        return esc(pairLabel(t.p[0], t.p[1])) + '（' + (t.w1.pct >= 90 ? '1 年高位' : '1 年低位') +
          ' ' + pctf(t.w1.pct) + '）';
      }).join('、') + '。分位只说明「在这段历史里偏高/偏低」，<b>不预示回归</b>。');
    }
    var frows = pr.freight.routes || [];
    var pos = frows.filter(function (x) { return x.result && x.result.ok && x.result.covers_freight; });
    lines.push('<b>运费调整：</b>' + (pr.freight_embedded_in_price
      ? '主口径送到价已含运费，扣费对照仅用于核对「到货成本」，' : '') +
      (pos.length ? '在当前默认参数下有 ' + pos.length + ' 个方向价差覆盖了承运成本——' : '当前参数下所有方向的价差均未覆盖承运成本——') +
      '<b>这只是敏感性参考，不等于套利机会</b>（未计资金占用、损耗、账期、卸货短驳、仓储与开票）。');
    lines.push('<span style="color:#67768e">以上为历史统计描述与口径核对，不构成因果判断、投资建议或价格预测。</span>');
    el('conclusion').innerHTML = lines.join('<br><br>');
  }

  function renderReadme() {
    var m = P.meta, c = P.primary;
    var s = [];
    s.push('<b>减法方向</b>：价差 = 价(甲) − 价(乙)。正数表示<b>甲比乙贵</b>。矩阵是「行 − 列」；曲线与表格都写全「谁减谁」，不出现裸的「价差」。');
    s.push('<b>对齐</b>：' + (m.align_method === 'weekly' ? '按 ISO 周对齐（周五锚）' : '按日对齐（exact）') +
      '；三地同周都有报价才进入样本，缺失周剔除并计入「对齐质量」，不插值、不前向填充。');
    s.push('<b>分位</b>：经验分布（ECDF，并列取中秩），报告分位同时给出样本 N；N<30 标记为低置信。');
    s.push('<b>运费</b>：分「真实报价」与「默认参考值」。未提供真实运费时，任何"覆盖运费"的结论只能当敏感性参考。');
    s.push('<b>三项不混</b>：裸价差 / 运输成本 / 扣费后差异，永远分列显示。');
    s.push('<b>不认定套利</b>：价差覆盖运费 ≠ 机会，资金占用、损耗、账期、短驳、仓储、开票都未计。');
    el('readme').innerHTML = s.map(function (x) { return '· ' + x; }).join('<br>');
  }

  /* ---------------- ① 口径 ---------------- */
  function renderCaliber() {
    var m = P.meta, pr = P.primary, n = names();
    var rows = m.regions.map(function (r) {
      return '<tr><td class="l"><b>' + esc(r.name) + '</b><br><span style="color:#67768e;font-size:11.5px">' +
        esc(r.rep_market || '') + '</span></td>' +
        '<td class="l">' + esc(r.quote_basis || '—') + '</td>' +
        '<td class="l">' + esc(r.delivery || '') + ' / ' + esc(r.payment || '') + ' / ' + esc(r.tax || '') + '</td>' +
        '<td class="l">' + esc(r.source_org || '—') + '</td>' +
        '<td class="l"><span style="color:#8b9bb4;font-size:12px">' + esc(r.basis_risk || '') + '</span></td></tr>';
    }).join('');
    html('caliber-table',
      '<div class="scroll" style="max-height:none"><table><thead><tr>' +
      '<th class="l">地区</th><th class="l">报价口径</th><th class="l">交付/付款/税基</th>' +
      '<th class="l">来源与样本</th><th class="l">口径风险</th></tr></thead><tbody>' + rows + '</tbody></table></div>');

    var cl = m.caliber_checklist || [];
    if (!cl.length) {
      cl = [
        { item: '规格', status: '已统一', question: '是否同为重质纯碱（Na₂CO₃≥99.2%）？', action: '三地均取重质；轻质价差另计' },
        { item: '税率', status: '已统一', question: '是否同为含 13% 增值税？', action: '统一含税；不含税 = 含税 ÷ 1.13' },
        { item: '计量单位', status: '已统一', question: '是否同为元/吨、同一包装？', action: '统一元/吨，吨包/散装同价' },
        { item: '交付方式', status: '已统一', question: '厂提 / 送到 / 港口平仓是否一致？', action: '主口径统一为送到价（行业规范）' },
        { item: '付款方式', status: '已统一', question: '现汇 / 承兑贴息？', action: '统一现汇；承兑报价需扣贴息（该数值属已知缺口）' },
        { item: '报价时点', status: '已统一', question: '同一抓取时点？', action: '同一机构同一日度窗口；切换机构即口径断点' },
        { item: '样本企业', status: '已标注', question: '是否含已停产装置的历史价？', action: '连云港碱业老厂关停已入事件表' },
        { item: '时间对齐', status: '已对齐', question: '交易日是否一致？', action: '按 ISO 周对齐；缺一周即剔除并记录' }
      ];
    }
    html('caliber-checklist',
      '<div class="scroll" style="max-height:none"><table><thead><tr><th class="l">项</th><th class="l">检查问题</th>' +
      '<th class="l">状态</th><th class="l">处理动作</th></tr></thead><tbody>' +
      cl.map(function (c) {
        var cls = c.status && c.status.indexOf('统一') >= 0 ? 'ok' : (c.status && c.status.indexOf('标注') >= 0 ? 'mid' : 'info');
        return '<tr><td class="l">' + esc(c.item) + '</td><td class="l">' + esc(c.question) + '</td>' +
          '<td class="l"><span class="pill ' + cls + '">' + esc(c.status) + '</span></td><td class="l">' + esc(c.action) + '</td></tr>';
      }).join('') + '</tbody></table></div>');

    // 标准化日志
    var nr = pr.normalize_report || {};
    var logs = Object.keys(nr).map(function (k) {
      var r = nr[k];
      return '<tr><td class="l">' + esc(n[k] || k) + '</td><td>' + r.n + '</td><td>' + r.total_steps + '</td>' +
        '<td>' + num(r.sum_abs_adj, 1) + '</td><td>' + num(r.max_abs_adj, 1) + '</td>' +
        '<td class="l">' + ((r.warnings || []).length ? '<span class="pill mid">' + (r.warnings || []).length + ' 条提示</span> ' + esc((r.warnings || []).join('；')) : '<span class="pill ok">无</span>') + '</td>' +
        '<td class="l">' + ((r.missing || []).length ? '<span class="pill no">' + esc((r.missing || []).join('，')) + '</span>' : '<span class="pill ok">无缺失</span>') + '</td></tr>';
    }).join('');
    html('normalize-report',
      '<div class="scroll" style="max-height:none"><table><thead><tr><th class="l">地区</th><th>样本</th><th>换算步数</th>' +
      '<th>累计调整(元/吨)</th><th>单步最大</th><th class="l">提示</th><th class="l">缺失参数</th></tr></thead><tbody>' +
      logs + '</tbody></table></div>' +
      '<div class="hint">换算步数为 0 表示三地区报价已在同一口径上，无需调整——这正是「主口径选择正确」的证据。</div>');

    // 双口径对照
    if (!P.control) { html('caliber-compare', '<div class="empty">未提供对照口径数据</div>'); return; }
    var ctrl = P.control;
    var rows2 = Core.unorderedPairs(P.primary.region_order).map(function (p) {
      var s1 = Core.spreadSeries(P.primary.series, p[0], p[1]);
      var s2 = Core.spreadSeries(ctrl.series, p[0], p[1]);
      if (!s1.length || !s2.length) return '';
      var v1 = s1[s1.length - 1].v, v2 = s2[s2.length - 1].v;
      var diff = v1 - v2;
      return '<tr><td class="l">' + esc(pairLabel(p[0], p[1])) + '</td>' +
        '<td>' + num(v1, 0) + '</td><td>' + num(v2, 0) + '</td>' +
        '<td style="color:' + (diff >= 0 ? '#7ee0c0' : '#ff7a8a') + '">' + sgn(diff) + num(diff, 0) + '</td>' +
        '<td class="l" style="font-size:12px;color:#8b9bb4">' + esc('送到口径价差 = 出厂口径价差 + (乙内含运费 − 甲内含运费)') + '</td></tr>';
    }).join('');
    html('caliber-compare',
      '<div class="scroll" style="max-height:none"><table><thead><tr><th class="l">价差</th>' +
      '<th>' + esc(m.calibers[m.primary_caliber].label) + '</th><th>' + esc(m.calibers[m.caliber_control].label) + '</th>' +
      '<th>差额(元/吨)</th><th class="l">恒等关系</th></tr></thead><tbody>' + rows2 + '</tbody></table></div>' +
      '<div class="hint">对照口径的观测期不同（' + (m.n_observations_control || '—') + ' 期 vs 主口径 ' + m.n_observations + ' 期），' +
      '因为两套口径的停报缺口不同；这是<b>正确行为</b>——缺口没有被插值填平。</div>');
  }

  /* ---------------- ② 价格 ---------------- */
  function renderRegionChips() {
    var n = names();
    html('region-chips', regs().map(function (r) {
      return '<span class="chip' + (S.regionOn[r] ? ' on' : '') + '" data-r="' + r + '">' +
        '<span class="dot" style="background:' + regionColor(r) + '"></span>' + esc(n[r]) + '</span>';
    }).join(''));
    Array.prototype.forEach.call(el('region-chips').querySelectorAll('.chip'), function (c) {
      c.addEventListener('click', function () {
        var r = c.dataset.r;
        if (S.regionOn[r] && Object.keys(S.regionOn).filter(function (x) { return S.regionOn[x]; }).length <= 1) return;
        S.regionOn[r] = !S.regionOn[r];
        renderRegionChips(); drawPrice(); renderLevelTable(); renderMap();
      });
    });
  }

  function visibleData() {
    var payload = series(), rg = Core.rangeFilter(payload, S.range);
    var dates = payload.dates.slice(rg.from, rg.to + 1);
    var prices = {};
    regs().forEach(function (r) { prices[r] = payload.prices[r].slice(rg.from, rg.to + 1); });
    return { dates: dates, prices: prices, rg: rg, payload: payload };
  }

  function drawPrice() {
    var ch = chart('ch-price'); if (!ch) return;
    var d = visibleData(), on = regs().filter(function (r) { return S.regionOn[r]; });
    var n = names();
    var sc = [];
    on.forEach(function (r) {
      var arr = d.prices[r].slice();
      if (S.priceMode === 'index') {
        var base = null;
        for (var i = 0; i < arr.length; i++) if (isNum(arr[i])) { base = arr[i]; break; }
        arr = arr.map(function (v) { return isNum(v) && base ? v / base * 100 : null; });
      }
      sc.push({
        name: n[r], type: 'line', showSymbol: false, connectNulls: false, smooth: false,
        lineStyle: { width: 2, color: regionColor(r) },
        itemStyle: { color: regionColor(r) },
        emphasis: { focus: 'series' },
        data: arr
      });
    });
    ch.setOption({
      backgroundColor: 'transparent',
      animationDuration: 420,
      grid: { left: 62, right: 24, top: 40, bottom: 52 },
      tooltip: Object.assign({ trigger: 'axis', axisPointer: { type: 'cross', label: { backgroundColor: '#2f3c4f' } } }, TIP,
        { valueFormatter: function (v) { return isNum(v) ? v.toFixed(1) + (S.priceMode === 'index' ? '' : ' 元/吨') : '—（缺口）'; } }),
      legend: { top: 4, textStyle: { color: '#8b9bb4' }, icon: 'roundRect', itemWidth: 14, itemHeight: 3 },
      xAxis: Object.assign({ type: 'category', data: d.dates, boundaryGap: false,
        axisLabel: Object.assign({}, AXIS.axisLabel, { formatter: function (v) { return String(v).slice(2, 7); } }) }, AXIS),
      yAxis: Object.assign({ type: 'value', scale: true,
        name: S.priceMode === 'index' ? '指数（首期=100）' : '元/吨',
        nameTextStyle: { color: '#67768e', fontSize: 11, padding: [0, 0, 6, -30] },
        axisLabel: AXIS.axisLabel, axisLine: { show: false },
        splitLine: AXIS.splitLine }, {}),
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 10, borderColor: '#25303f',
        backgroundColor: '#111823', fillerColor: 'rgba(77,163,255,.14)',
        handleStyle: { color: '#4da3ff' }, textStyle: { color: '#67768e' } }],
      series: sc
    }, true);
    ch.off('click');
    ch.on('click', function (p) { showDayDetail(p.dataIndex); });
  }

  function showDayDetail(idx) {
    var d = visibleData(), n = names(), i = idx;
    var dt = d.dates[i];
    var box = el('price-detail');
    if (!box) return;
    var rows = regs().map(function (r) {
      var v = d.prices[r][i];
      return '<td>' + num(v, 0) + '</td>';
    }).join('');
    var sp = Core.unorderedPairs(regs()).map(function (p) {
      var a = d.prices[p[0]][i], b = d.prices[p[1]][i];
      return '<td>' + (isNum(a) && isNum(b) ? num(a - b, 0) : '—') + '</td>';
    }).join('');
    var evs = (P.events || []).filter(function (e) {
      var e1 = e.end || e.date;
      return e.date <= dt && e1 >= dt;
    });
    box.innerHTML = '<div style="border:1px solid #2f3c4f;border-radius:10px;padding:11px 14px;background:#1a2230;margin-top:12px">' +
      '<b>选中周：' + esc(dt) + '</b>' +
      '<table style="margin-top:8px"><thead><tr><th class="l">项目</th>' +
      regs().map(function (r) { return '<th>' + esc(n[r]) + ' 价</th>'; }).join('') +
      Core.unorderedPairs(regs()).map(function (p) { return '<th>' + esc(p[0] + '−' + p[1]) + '</th>'; }).join('') +
      '</tr></thead><tbody><tr><td class="l">元/吨</td>' + rows + sp + '</tr></tbody></table>' +
      (evs.length ? '<div class="hint" style="margin-top:8px">同期事件：' + evs.map(function (e) {
        return '<span class="pill info">' + esc(e.title) + '</span>';
      }).join(' ') + '</div>' : '<div class="hint" style="margin-top:8px">同期无已记录事件。</div>') +
      '</div>';
  }

  function renderLevelTable() {
    var payload = series(), n = names(), end = payload.dates[payload.dates.length - 1];
    var rows = regs().filter(function (r) { return S.regionOn[r]; }).map(function (r) {
      var all = payload.prices[r];
      var s = [];
      for (var i = 0; i < all.length; i++) if (isNum(all[i])) s.push({ d: payload.dates[i], v: all[i] });
      var cur = s.length ? s[s.length - 1].v : null;
      var y1 = s.filter(function (x) { return Core.WIN['1y'] >= Math.round((new Date(end) - new Date(x.d)) / 86400000); }).map(function (x) { return x.v; });
      var allv = s.map(function (x) { return x.v; });
      return '<tr><td class="l"><span class="dot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' +
        regionColor(r) + ';margin-right:7px"></span>' + esc(n[r]) + '</td>' +
        '<td><b>' + num(cur, 0) + '</b></td>' +
        '<td>' + num(Core.quantile(allv, .5), 0) + '</td>' +
        '<td>' + num(Math.min.apply(null, allv), 0) + ' ~ ' + num(Math.max.apply(null, allv), 0) + '</td>' +
        '<td>' + pctf(Core.percentileOf(cur, y1)) + '</td>' +
        '<td>' + pctf(Core.percentileOf(cur, allv)) + '</td>' +
        '<td>' + num(Core.sd(allv), 1) + '</td></tr>';
    }).join('');
    html('level-tbl', '<div class="scroll" style="max-height:none"><table><thead><tr><th class="l">地区</th><th>当前</th>' +
      '<th>全期中位数</th><th>全期区间</th><th>1y 分位</th><th>全期分位</th><th>标准差</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<div class="hint">样本期 ' + esc(payload.dates[0]) + ' ~ ' + esc(end) + '。分位基于实测经验分布。</div>');
  }

  function renderAlignTable() {
    var pr = P.primary, n = names();
    var rows = pr.region_order.map(function (r) {
      var st = pr.align.max_staleness[r];
      var gaps = (pr.align.dropped || []).filter(function (x) { return (x.missing || []).indexOf(r) >= 0; });
      return '<tr><td class="l">' + esc(n[r]) + '</td><td>' + pr.align.n_used + '</td>' +
        '<td>' + gaps.length + '</td>' +
        '<td>' + (st || 0) + ' 天</td>' +
        '<td class="l">' + (gaps.length ? gaps.map(function (g) { return esc(g.date); }).join('、') : '无') + '</td></tr>';
    }).join('');
    var ctrlRows = '';
    if (P.control) {
      ctrlRows = P.control.region_order.map(function (r) {
        var gaps = (P.control.align.dropped || []).filter(function (x) { return (x.missing || []).indexOf(r) >= 0; });
        return '<tr><td class="l">' + esc(n[r]) + '（对照）</td><td>' + P.control.align.n_used + '</td><td>' + gaps.length + '</td>' +
          '<td>' + (P.control.align.max_staleness[r] || 0) + ' 天</td><td class="l">' +
          (gaps.length ? gaps.map(function (g) { return esc(g.date); }).join('、') : '无') + '</td></tr>';
      }).join('');
    }
    html('align-tbl', '<div class="scroll" style="max-height:none"><table><thead><tr><th class="l">地区/口径</th>' +
      '<th>进入样本周数</th><th>缺失周</th><th>最大滞后</th><th class="l">缺失日期</th></tr></thead><tbody>' +
      rows + ctrlRows + '</tbody></table></div>' +
      '<div class="hint">主口径剔除 ' + pr.align.n_dropped + ' 周，对照口径剔除 ' + (P.control ? P.control.align.n_dropped : '—') +
      ' 周。缺口<b>未插值</b>，因此两个口径的可用周数不同——这是正确结果。</div>');
  }

  /* ---------------- ③ 价差 ---------------- */
  function renderMatrix() {
    var pr = series(), order = nowCal().region_order, n = names();
    var mx = nowCal().matrix;
    var last = function (r) { var a = pr.prices[r]; return a[a.length - 1]; };
    var vals = [];
    order.forEach(function (a) { order.forEach(function (b) { if (a !== b) { var v = mx.values[a + '|' + b]; if (isNum(v)) vals.push(v); } }); });
    var mxAbs = vals.length ? Math.max.apply(null, vals.map(Math.abs)) : 1;
    var head = '<tr><th class="l"></th>' + order.map(function (c) { return '<th>' + esc(n[c]) + '</th>'; }).join('') + '</tr>';
    var body = order.map(function (r) {
      return '<tr><th>' + esc(n[r]) + '<br><span style="font-size:10px;color:#67768e">' + esc(r) + ' ' + num(last(r), 0) + '</span></th>' +
        order.map(function (c) {
          if (r === c) return '<td class="diag">0</td>';
          var v = mx.values[r + '|' + c];
          if (!isNum(v)) return '<td class="diag">—</td>';
          var t = Math.min(1, Math.abs(v) / (mxAbs || 1));
          var bg = v >= 0 ? 'rgba(255,122,138,' + (0.08 + t * 0.34) + ')' : 'rgba(61,220,151,' + (0.08 + t * 0.34) + ')';
          var fg = v >= 0 ? '#ffb3bd' : '#8ff0c4';
          return '<td class="val" data-a="' + r + '" data-b="' + c + '" style="background:' + bg + ';color:' + fg + '">' +
            sgn(v) + v.toFixed(0) +
            '<span class="sm">' + esc(r) + '−' + esc(c) + '</span></td>';
        }).join('') + '</tr>';
    }).join('');
    el('matrix-box').innerHTML = '<table class="mx"><thead>' + head + '</thead><tbody>' + body + '</tbody></table>';
    Array.prototype.forEach.call(el('matrix-box').querySelectorAll('td.val'), function (td) {
      td.addEventListener('mouseenter', function (ev) {
        var a = td.dataset.a, b = td.dataset.b;
        var meta = mx.meta[a + '|' + b] || {};
        showTip(ev, '<b>' + esc(n[a]) + ' − ' + esc(n[b]) + ' = ' + num(mx.values[a + '|' + b], 1) + ' 元/吨</b><br>' +
          (mx.values[a + '|' + b] >= 0 ? esc(n[a]) + ' 比 ' + esc(n[b]) + ' 贵' : esc(n[b]) + ' 比 ' + esc(n[a]) + ' 贵') +
          '<br>样本 N = ' + (meta.n || 0) + '，日期 ' + esc(meta.date || ''));
      });
      td.addEventListener('mouseleave', hideTip);
    });
  }

  function showTip(ev, s) {
    var t = el('tip');
    t.innerHTML = s; t.style.display = 'block';
    var x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + 320 > window.innerWidth) x = ev.clientX - 330;
    if (y + 120 > window.innerHeight) y = ev.clientY - 120;
    t.style.left = x + 'px'; t.style.top = y + 'px';
  }
  function hideTip() { el('tip').style.display = 'none'; }

  function renderPairChips() {
    var up = Core.unorderedPairs(regs());
    if (!S.pair) S.pair = up[0].join('-');
    html('pair-chips', up.map(function (p) {
      var k = p.join('-');
      return '<span class="chip' + (S.pair === k ? ' on' : '') + '" data-k="' + k + '">' + esc(pairLabel(p[0], p[1])) +
        '<span style="color:#67768e;margin-left:6px">' + esc(k) + '</span></span>';
    }).join(''));
    Array.prototype.forEach.call(el('pair-chips').querySelectorAll('.chip'), function (c) {
      c.addEventListener('click', function () { S.pair = c.dataset.k; renderPairChips(); drawSpread(); });
    });
  }

  function drawSpread() {
    var ch = chart('ch-spread'); if (!ch) return;
    var p = S.pair.split('-');
    var s = Core.spreadSeries(series(), p[0], p[1]);
    var rg = Core.rangeFilter(series(), S.range);
    var d0 = series().dates[rg.from], d1 = series().dates[rg.to];
    s = s.filter(function (x) { return x.date >= d0 && x.date <= d1; });
    var vals = s.map(function (x) { return [x.date, x.v]; });
    var m = Core.mean(s.map(function (x) { return x.v; }));
    var sdv = Core.sd(s.map(function (x) { return x.v; }));
    ch.setOption({
      animationDuration: 380,
      grid: { left: 58, right: 20, top: 34, bottom: 44 },
      tooltip: Object.assign({ trigger: 'axis', valueFormatter: function (v) { return isNum(v) ? v.toFixed(1) + ' 元/吨' : '—'; } }, TIP),
      title: { text: pairLabel(p[0], p[1]) + '（' + p[0] + ' − ' + p[1] + '）', left: 4, top: 0,
        textStyle: { color: '#e6ecf5', fontSize: 13, fontWeight: 600 } },
      xAxis: Object.assign({ type: 'time', axisLabel: Object.assign({}, AXIS.axisLabel, { formatter: '{MM}-{dd}' }) }, AXIS),
      yAxis: Object.assign({ type: 'value', scale: true, name: '元/吨', nameTextStyle: { color: '#67768e', fontSize: 11 },
        axisLabel: AXIS.axisLabel, axisLine: { show: false }, splitLine: AXIS.splitLine }, {}),
      series: [{
        type: 'line', showSymbol: false, data: vals,
        lineStyle: { width: 2, color: COLORS.SD }, itemStyle: { color: COLORS.SD },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(77,163,255,.28)' }, { offset: 1, color: 'rgba(77,163,255,.01)' }]) },
        markLine: {
          symbol: 'none', silent: true,
          data: [
            { yAxis: 0, lineStyle: { color: '#8b9bb4', type: 'solid', width: 1 }, label: { formatter: '0', color: '#8b9bb4', fontSize: 10 } },
            { yAxis: m, lineStyle: { color: '#ffc857', type: 'dashed', width: 1 }, label: { formatter: '均值 ' + m.toFixed(0), color: '#ffc857', fontSize: 10, position: 'insideEndTop' } }
          ]
        }
      }]
    }, true);
  }

  function renderPairTable() {
    var pr = nowCal(), n = names();
    var rows = pr.pairs.map(function (p) {
      if (!p.n) return '';
      var d = p.desc;
      return '<tr><td class="l"><b>' + esc(p.label) + '</b></td><td class="l">' + esc(p.direction) + '</td>' +
        '<td><b>' + num(p.current, 1) + '</b></td><td>' + num(d.mean, 1) + '</td>' +
        '<td>' + num(Math.min.apply(null, [d.min]), 1) + ' ~ ' + num(d.max, 1) + '</td>' +
        '<td>' + num(d.sd, 1) + '</td><td>' + p.n + '</td><td class="l" style="font-size:11.5px;color:#67768e">' + esc(p.last_date) + '</td></tr>';
    }).join('');
    html('pair-tbl', '<div class="scroll" style="max-height:none"><table><thead><tr><th class="l">价差（方向）</th>' +
      '<th class="l">含义</th><th>当前</th><th>历史均值</th><th>区间</th><th>标准差</th><th>N</th><th class="l">最新日期</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<div class="hint">校验：山东−河北 与 河北−山东 互为相反数；N 一致。若某个有序对样本为 0，说明该方向在数据中始终无法对齐。</div>');
  }

  /* ---------------- ④ 分位 ---------------- */
  function renderPctTable() {
    var pr = nowCal(), n = names(), wins = P.meta.windows || ['1y', '3y'];
    var head = '<tr><th class="l">价差</th><th>当前</th>' + wins.map(function (w) {
      return '<th>' + w + ' 分位</th><th>' + w + ' 最小~最大</th><th>' + w + ' 中位</th><th>N</th>';
    }).join('') + '<th class="l">位置</th></tr>';
    var rows = pr.percentiles.map(function (r) {
      if (!r.n_total) return '';
      var cells = wins.map(function (w) {
        var x = r.windows[w] || {};
        var cls = isNum(x.pct) ? (x.pct >= 90 ? 'no' : (x.pct <= 10 ? 'ok' : 'mid')) : '';
        return '<td><span class="pill ' + cls + '" style="font-size:12px;padding:2px 9px">' + pctf(x.pct) + '</span></td>' +
          '<td style="font-size:12px;color:#8b9bb4">' + num(x.min, 0) + ' ~ ' + num(x.max, 0) + '</td>' +
          '<td style="font-size:12px;color:#8b9bb4">' + num(x.median, 0) + '</td>' +
          '<td style="font-size:12px;color:#67768e">' + (x.n || 0) + '</td>';
      }).join('');
      var first = r.windows[wins[wins.length - 1]] || r.windows[wins[0]] || {};
      return '<tr><td class="l"><b>' + esc(pairLabel(r.a, r.b)) + '</b></td><td><b>' + num(r.current, 1) + '</b></td>' +
        cells + '<td class="l"><span class="pill ' + (isNum(first.pct) && first.pct >= 90 ? 'no' : (isNum(first.pct) && first.pct <= 10 ? 'ok' : 'mid')) + '">' +
        esc(first.label || Core.percentileLabel(first.pct)) + '</span></td></tr>';
    }).join('');
    html('pct-tbl', '<div class="scroll" style="max-height:none"><table><thead>' + head + '</thead><tbody>' + rows + '</tbody></table></div>' +
      '<div class="hint">红色=历史高位（≥P90），绿色=历史低位（≤P10），黄色=中枢。' +
      '<b>分位高不代表会回落</b>；分位只回答「当前值在这段历史里排第几」。' +
      (wins.indexOf('1y') >= 0 ? ' 1y 样本约 52 期，3y 约 152 期。' : '') + '</div>');
  }

  function renderRollChips() {
    var up = Core.unorderedPairs(regs());
    if (!S.rollPair) S.rollPair = up[0].join('-');
    html('rollpair-chips', up.map(function (p) {
      var k = p.join('-');
      return '<span class="chip' + (S.rollPair === k ? ' on' : '') + '" data-k="' + k + '">' + esc(pairLabel(p[0], p[1])) + '</span>';
    }).join(''));
    Array.prototype.forEach.call(el('rollpair-chips').querySelectorAll('.chip'), function (c) {
      c.addEventListener('click', function () { S.rollPair = c.dataset.k; renderRollChips(); drawRolling(); drawHist(); });
    });
  }

  function drawRolling() {
    var ch = chart('ch-roll'); if (!ch) return;
    var p = S.rollPair.split('-');
    var s = Core.spreadSeries(series(), p[0], p[1]);
    var roll = Core.rollingPercentile(s, 365, 30);
    ch.setOption({
      grid: { left: 52, right: 18, top: 30, bottom: 34 },
      tooltip: Object.assign({ trigger: 'axis', valueFormatter: function (v) { return isNum(v) ? v.toFixed(1) + '%' : '样本不足'; } }, TIP),
      title: { text: pairLabel(p[0], p[1]) + ' · 滚动 1 年分位', left: 4, top: 0, textStyle: { color: '#e6ecf5', fontSize: 13, fontWeight: 600 } },
      xAxis: Object.assign({ type: 'category', boundaryGap: false, data: roll.map(function (x) { return x.date; }),
        axisLabel: Object.assign({}, AXIS.axisLabel, { formatter: function (v) { return String(v).slice(2, 7); } }) }, AXIS),
      yAxis: Object.assign({ type: 'value', min: 0, max: 100, name: '分位 %', nameTextStyle: { color: '#67768e', fontSize: 11 },
        axisLabel: AXIS.axisLabel, axisLine: { show: false }, splitLine: AXIS.splitLine }, {}),
      series: [{
        type: 'line', showSymbol: false, connectNulls: false,
        data: roll.map(function (x) { return isNum(x.v) ? x.v : null; }),
        lineStyle: { width: 1.8, color: '#a78bfa' }, itemStyle: { color: '#a78bfa' },
        areaStyle: { color: 'rgba(167,139,250,.14)' },
        markLine: { symbol: 'none', silent: true, data: [
          { yAxis: 90, lineStyle: { color: 'rgba(255,122,138,.55)', type: 'dashed' }, label: { formatter: 'P90', color: '#ff7a8a', fontSize: 10 } },
          { yAxis: 10, lineStyle: { color: 'rgba(61,220,151,.55)', type: 'dashed' }, label: { formatter: 'P10', color: '#3ddc97', fontSize: 10 } },
          { yAxis: 50, lineStyle: { color: 'rgba(139,155,180,.3)', type: 'dotted' }, label: { formatter: '', show: false } }
        ] }
      }]
    }, true);
  }

  function drawHist() {
    var ch = chart('ch-hist'); if (!ch) return;
    var p = S.rollPair.split('-');
    var s = Core.spreadSeries(series(), p[0], p[1]);
    var end = series().dates[series().dates.length - 1];
    var win = (P.meta.windows || ['1y'])[0];
    var samp = Core.windowSample(s, end, win);
    if (!samp.length) { ch.clear(); return; }
    var cur = s[s.length - 1].v;
    var lo = Math.min.apply(null, samp.concat([cur])), hi = Math.max.apply(null, samp.concat([cur]));
    var step = Math.max(5, Math.round((hi - lo + 1) / 14 / 5) * 5);
    var bins = [];
    for (var b = Math.floor(lo / step) * step; b <= hi + step; b += step) bins.push([b, 0]);
    samp.forEach(function (v) {
      for (var i = bins.length - 1; i >= 0; i--) { if (v >= bins[i][0]) { bins[i][1]++; break; } }
    });
    ch.setOption({
      grid: { left: 40, right: 18, top: 30, bottom: 34 },
      tooltip: Object.assign({ trigger: 'axis', axisPointer: { type: 'shadow' } }, TIP),
      title: { text: pairLabel(p[0], p[1]) + ' · 近 ' + win + ' 分布（N=' + samp.length + '）', left: 4, top: 0,
        textStyle: { color: '#e6ecf5', fontSize: 13, fontWeight: 600 } },
      xAxis: Object.assign({ type: 'category', data: bins.map(function (x) { return x[0].toFixed(0); }),
        axisLabel: Object.assign({}, AXIS.axisLabel, { fontSize: 10, interval: 1 }) }, AXIS),
      yAxis: Object.assign({ type: 'value', name: '周数', nameTextStyle: { color: '#67768e', fontSize: 11 },
        axisLabel: AXIS.axisLabel, axisLine: { show: false }, splitLine: AXIS.splitLine }, {}),
      series: [{
        type: 'bar', data: bins.map(function (x) { return x[1]; }),
        itemStyle: { color: '#4da3ff', opacity: .55, borderRadius: [3, 3, 0, 0] },
        markLine: { symbol: 'none', data: [{
          xAxis: bins.map(function (x) { return x[0].toFixed(0); }).indexOf((Math.floor(cur / step) * step).toFixed(0)),
          lineStyle: { color: '#ffc857', width: 2 }, label: { formatter: '当前 ' + cur.toFixed(0), color: '#ffc857', fontSize: 11, position: 'insideEndTop' }
        }] }
      }]
    }, true);
  }

  /* ---------------- ⑤ 运费 ---------------- */
  function initFreight() {
    S.freight = {};
    (P.primary.freight.routes || []).forEach(function (r) {
      S.freight[r.route] = { freight: r.freight, src: r.freight_basis === 'provided' ? 'manual' : 'default' };
    });
    var cp = P.primary.freight.params || {};
    S.params = {
      loading_fee: cp.loading_fee != null ? cp.loading_fee : 8,
      unloading_fee: cp.unloading_fee != null ? cp.unloading_fee : 10,
      short_haul: cp.short_haul != null ? cp.short_haul : 0,
      handler: cp.handler != null ? cp.handler : (cp.handling_fee != null ? cp.handling_fee : 2)
    };
    ['f-load', 'f-unload', 'f-short', 'f-handler'].forEach(function (id, i) {
      var key = ['loading_fee', 'unloading_fee', 'short_haul', 'handler'][i];
      var e = el(id); if (!e) return;
      e.value = S.params[key];
      e.addEventListener('input', function () {
        S.params[key] = e.value === '' ? null : parseFloat(e.value);
        drawFreight(); renderFreightResult();
      });
    });
  }

  function renderFreightWarn() {
    var pr = P.primary, rts = pr.freight.routes || [];
    var prov = rts.filter(function (r) { return r.freight_basis === 'provided'; }).length;
    var def = rts.filter(function (r) { return r.freight_basis === 'default_ref'; }).length;
    var na = rts.filter(function (r) { return r.freight_basis === 'not_available'; }).length;
    var s = '';
    if (pr.freight_embedded_in_price) {
      s += '<div class="warnbox" style="margin-bottom:12px"><b>主口径「送到价」已含运费。</b>本节的两项用途：' +
        '①在<b>出厂价口径</b>下把运费显性化，得到「到货成本」；②核对某个方向的价差是否足够覆盖承运成本。' +
        '<b>不要用整段运费从送到价里再扣一次</b>——那是重复扣减。</div>';
    }
    s += '<div class="' + (prov ? 'okbox' : 'gapbox') + '"><b>运费数据：</b>真实报价 ' + prov + ' 条 / 默认参考值 ' + def + ' 条 / 未获得 ' + na + ' 条。' +
      (prov ? '' : ' <b>尚未提供真实运费</b>——下面的「扣费后差异」全部基于默认参考值，只能作为敏感性参考，不能作为套利判断依据。') +
      '</div>';
    el('freight-warn').innerHTML = s;
  }

  function renderFreightInputs() {
    var rts = P.primary.freight.routes || [], n = names();
    var rows = rts.map(function (r) {
      var alt = (r.alternatives || []).map(function (a) {
        return '<span class="pill ' + (a.value == null ? 'no' : 'info') + '" title="' + esc(a.source || '') + '">' +
          esc(a.mode) + ' ' + (a.value == null ? '—' : a.value) + '</span>';
      }).join(' ');
      return '<tr><td class="l"><b>' + esc(r.flow) + '</b><br><span style="font-size:11px;color:#67768e">' + esc(r.route) + ' · ' + esc(r.main_mode) + '</span></td>' +
        '<td>' + esc(r.distance_km) + '<span style="color:#67768e;font-size:11px"> km</span><br>' +
        '<span class="pill ' + (r.distance_status === '已核实' ? 'ok' : 'mid') + '" style="font-size:10px">' + esc(r.distance_status || '估算') + '</span></td>' +
        '<td><input type="number" step="0.5" data-route="' + esc(r.route) + '" value="' + (r.freight == null ? '' : r.freight) + '" style="width:88px"' +
        (S.freightSrc === 'default' ? ' disabled' : '') + '></td>' +
        '<td><span class="pill ' + (r.freight_basis === 'provided' ? 'ok' : (r.freight_basis === 'not_available' ? 'no' : 'mid')) + '">' +
        (r.freight_basis === 'provided' ? '真实报价' : (r.freight_basis === 'not_available' ? '未获得' : '默认参考')) + '</span></td>' +
        '<td class="l"><span style="font-size:11.5px;color:#8b9bb4">' + esc(r.freight_source || '') + '</span></td>' +
        '<td class="l">' + alt + '</td></tr>';
    }).join('');
    html('freight-inputs', '<div class="scroll" style="max-height:none"><table><thead><tr><th class="l">路线方向</th>' +
      '<th>距离</th><th>主运费 元/吨</th><th>来源</th><th class="l">依据</th><th class="l">备选方式（运价）</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>');
    Array.prototype.forEach.call(el('freight-inputs').querySelectorAll('input[data-route]'), function (inp) {
      inp.addEventListener('input', function () {
        var k = inp.dataset.route;
        S.freight[k] = { freight: inp.value === '' ? null : parseFloat(inp.value), src: 'manual' };
        drawFreight(); renderFreightResult();
      });
    });
  }

  function routeParams(r) {
    var v = S.freight[r.route] || {};
    return {
      freight: S.freightOn ? (v.freight === undefined ? r.freight : v.freight) : null,
      loading_fee: S.params.loading_fee,
      unloading_fee: S.params.unloading_fee,
      short_haul: S.params.short_haul,
      handler: S.params.handler
    };
  }

  function currentPrices() {
    var pr = series(), out = {};
    regs().forEach(function (r) {
      var a = pr.prices[r];
      for (var i = a.length - 1; i >= 0; i--) if (isNum(a[i])) { out[r] = a[i]; break; }
    });
    return out;
  }

  function renderFreightResult() {
    var rts = P.primary.freight.routes || [], n = names(), px = currentPrices();
    if (!S.freightOn) {
      html('freight-result', '<div class="empty">运费调整未开启。<br><span style="font-size:12px">当前仅显示裸价差——这是默认状态，也是<b>不应被误读为套利</b>的状态。</span></div>');
      return;
    }
    var rows = rts.map(function (r) {
      var pf = px[r.from], pt = px[r.to];
      if (!isNum(pf) || !isNum(pt)) return '';
      var res = Core.freightAdjusted(pf, pt, r, routeParams(r));
      var srcPill = res.ok ? '<span class="pill ' + (S.freight[r.route] && S.freight[r.route].src === 'manual' ? 'info' : 'mid') + '">' +
        (S.freight[r.route] && S.freight[r.route].src === 'manual' ? '手输/真实' : '默认参考') + '</span>' : '<span class="pill no">未知</span>';
      if (!res.ok) {
        return '<tr><td class="l">' + esc(r.flow) + '</td><td>' + num(pf, 0) + '</td><td>' + num(pt, 0) + '</td>' +
          '<td>' + sgn(res.raw) + num(pt - pf, 0) + '</td><td>—</td><td>—</td><td class="l"><span class="pill no">运费未知，不计算</span></td></tr>';
      }
      var cls = res.covers_freight ? 'ok' : 'no';
      return '<tr><td class="l"><b>' + esc(r.flow) + '</b><br><span style="font-size:11px;color:#67768e">' + esc(r.distance_km) + ' km · ' + esc(r.main_mode) + '</span></td>' +
        '<td>' + num(pf, 0) + '</td><td>' + num(pt, 0) + '</td>' +
        '<td>' + sgn(res.raw) + num(res.raw, 0) + '</td>' +
        '<td>' + num(res.total, 0) + ' ' + srcPill + '</td>' +
        '<td style="color:' + (res.ref > 0 ? '#3ddc97' : '#ff7a8a') + ';font-weight:700">' + sgn(res.ref) + num(res.ref, 0) + '</td>' +
        '<td class="l"><span class="pill ' + cls + '">' + (res.covers_freight ? '价差覆盖运费' : '未覆盖运费') + '</span></td></tr>';
    }).join('');
    html('freight-result', '<div class="scroll" style="max-height:none"><table><thead><tr><th class="l">方向</th>' +
      '<th>产地价</th><th>目的地价</th><th>裸价差(目的地−产地)</th><th>综合运费</th><th>扣费后参考差异</th><th class="l">判定</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<div class="warnbox" style="margin-top:12px"><b>「价差覆盖运费」≠ 套利机会。</b>未计入：资金占用与利息、运输损耗、账期与承兑贴息、' +
      '卸货地短驳、仓储、开票与结算风险、可成交批量（沙河月用纯碱约 9 万吨量级，跨区大批量会改变本地产销平衡进而改变价格本身）。</div>');
  }

  function drawFreight() {
    var ch = chart('ch-freight'); if (!ch) return;
    var rts = P.primary.freight.routes || [], n = names(), px = currentPrices();
    var cats = [], raw = [], fr = [], ref = [];
    rts.forEach(function (r) {
      var pf = px[r.from], pt = px[r.to];
      if (!isNum(pf) || !isNum(pt)) return;
      cats.push(r.flow);
      raw.push(+(pt - pf).toFixed(1));
      if (S.freightOn) {
        var res = Core.freightAdjusted(pf, pt, r, routeParams(r));
        fr.push(res.ok ? res.total : null);
        ref.push(res.ok ? +res.ref.toFixed(1) : null);
      } else { fr.push(null); ref.push(null); }
    });
    ch.setOption({
      grid: { left: 56, right: 20, top: 36, bottom: 76 },
      tooltip: Object.assign({ trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: function (v) { return isNum(v) ? v.toFixed(1) + ' 元/吨' : '未开启'; } }, TIP),
      legend: { top: 0, textStyle: { color: '#8b9bb4' }, itemWidth: 12, itemHeight: 8 },
      xAxis: Object.assign({ type: 'category', data: cats, axisLabel: Object.assign({}, AXIS.axisLabel, { rotate: 28, fontSize: 10.5, interval: 0 }) }, AXIS),
      yAxis: Object.assign({ type: 'value', name: '元/吨', nameTextStyle: { color: '#67768e', fontSize: 11 },
        axisLabel: AXIS.axisLabel, axisLine: { show: false }, splitLine: AXIS.splitLine }, {}),
      series: [
        { name: '裸价差(目的−产地)', type: 'bar', data: raw, itemStyle: { color: '#4da3ff', opacity: .8, borderRadius: [3, 3, 0, 0] }, barGap: '12%' },
        { name: '综合运费', type: 'bar', data: fr, itemStyle: { color: '#ffc857', opacity: .8, borderRadius: [3, 3, 0, 0] } },
        { name: '扣费后参考差异', type: 'bar', data: ref, itemStyle: { color: '#7ee0c0', opacity: .85, borderRadius: [3, 3, 0, 0] } }
      ]
    }, true);
  }

  function renderRouteTable() {
    var rts = P.primary.freight.routes || [], n = names();
    var rows = rts.map(function (r) {
      var lanes = (r.lanes || []).map(function (l) {
        return '<span class="pill ' + (l.available ? 'ok' : 'no') + '" style="margin:1px 2px">' + esc(l.mode) +
          (l.available ? ' · ' + esc(l.distance_km) + 'km · ' + esc(l.transit_days) + '天' : ' · 不可用') + '</span>';
      }).join('');
      return '<tr><td class="l"><b>' + esc(r.flow) + '</b></td>' +
        '<td>' + esc(r.distance_km) + '<span style="color:#67768e;font-size:11px"> km</span>' +
        (r.distance_km_range ? '<br><span style="font-size:10.5px;color:#67768e">' + esc(r.distance_km_range[0] + '–' + r.distance_km_range[1]) + '</span>' : '') + '</td>' +
        '<td class="l"><span class="pill ' + (r.distance_status === '已核实' ? 'ok' : 'mid') + '">' + esc(r.distance_status || '估算') + '</span></td>' +
        '<td class="l">' + lanes + '</td>' +
        '<td>' + (r.freight == null ? '—' : num(r.freight, 0)) + '</td></tr>';
    }).join('');
    html('route-tbl', '<div class="scroll" style="max-height:none"><table><thead><tr><th class="l">方向</th><th>典型距离</th>' +
      '<th class="l">距离可信度</th><th class="l">可用运输方式</th><th>默认主运费</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<div class="hint">' + esc(P.meta.mode_rule || '') + '<br>' + esc(P.meta.tonkm_anchor || '') + '</div>');
  }

  /* ---------------- ⑥ 异常阶段 ---------------- */
  function renderRegimeChips() {
    var up = Core.unorderedPairs(regs());
    if (!S.regimePair) S.regimePair = up[0].join('-');
    html('regime-pair-chips', up.map(function (p) {
      return '<span class="chip' + (S.regimePair === p.join('-') ? ' on' : '') + '" data-k="' + p.join('-') + '">' +
        esc(pairLabel(p[0], p[1])) + '</span>';
    }).join(''));
    Array.prototype.forEach.call(el('regime-pair-chips').querySelectorAll('.chip'), function (c) {
      c.addEventListener('click', function () { S.regimePair = c.dataset.k; renderRegimeChips(); renderRegimeList(); });
    });
  }

  function renderRegimeList() {
    var list = (nowCal().regimes || {})[S.regimePair] || [];
    if (!list.length) { html('regime-list', '<div class="empty">该价差在样本期内没有识别出异常阶段（连续 ≥3 周 |z|≥1）</div>'); return; }
    html('regime-list', list.map(function (r, i) {
      return '<div class="ev" data-i="' + i + '"><div class="t">' + esc(r.start) + ' ~ ' + esc(r.end) +
        '<span class="kind ' + (r.direction === '走阔' ? '需求' : '物流') + '">' + esc(r.direction) + '</span>' +
        '<span class="pill">' + r.n + ' 周</span></div>' +
        '<div class="d">该阶段均值 ' + num(r.mean_spread, 0) + '，前一年均值 ' + num(r.base_mean, 0) +
        '，偏离 ' + sgn(r.deviation) + num(r.deviation, 0) + ' 元/吨</div>' +
        '<div class="n">' + (r.events && r.events.length ? r.events.length + ' 个同期事件：' + r.events.slice(0, 2).map(function (e) { return esc(e.title); }).join('；') : '无同期已记录事件') + '</div></div>';
    }).join(''));
    Array.prototype.forEach.call(el('regime-list').querySelectorAll('.ev'), function (d) {
      d.addEventListener('click', function () { showRegime(list[+d.dataset.i]); });
    });
    if (list.length) showRegime(list[0]);
  }

  function showRegime(r) {
    var n = names(), pr = nowCal();
    el('regime-detail-tag').innerHTML = '<span class="pill info">' + esc(r.start) + ' ~ ' + esc(r.end) + '</span>';
    var regsHtml = Object.keys(r.region_snapshots || {}).map(function (id) {
      var s = r.region_snapshots[id];
      return '<div class="regcard"><h4><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:' +
        regionColor(id) + '"></span>' + esc(s.name) + '</h4>' +
        '<div class="row"><span>阶段均价</span><b class="mono">' + num(s.mean, 0) + '</b></div>' +
        '<div class="row"><span>较前一年</span><b class="mono" style="color:' + (s.change_vs_prior_yr > 0 ? '#7ee0c0' : '#ff7a8a') + '">' +
        sgn(s.change_vs_prior_yr) + num(s.change_vs_prior_yr, 0) + '</b></div>' +
        '<div class="row"><span>阶段区间</span><b class="mono">' + num(s.min, 0) + '~' + num(s.max, 0) + '</b></div>' +
        ((r.fundamentals && r.fundamentals[id] && r.fundamentals[id].surplus) ? '<div class="row"><span>供需角色</span><span style="font-size:11.5px;color:#8b9bb4;text-align:right">' + esc(r.fundamentals[id].surplus) + '</span></div>' : '') +
        '</div>';
    }).join('');
    var evHtml = (r.events || []).length ? r.events.map(function (e) {
      return '<div class="ev" style="cursor:default;border-left-color:' + (e.price_effect === '收紧' ? '#3ddc97' : (e.price_effect === '宽松' ? '#ff7a8a' : '#ffc857')) + '">' +
        '<div class="t"><span class="kind ' + esc(e.kind) + '">' + esc(e.kind) + '</span>' + esc(e.title) +
        '<span class="pill">' + esc(e.price_effect) + '</span></div>' +
        '<div class="d">' + esc(e.overlap_from) + ' ~ ' + esc(e.overlap_to) + ' ｜ 影响区域：' + esc((e.regions || []).join('、')) + '</div>' +
        '<div class="n">' + esc(e.detail) + '</div>' +
        (e.economic_link ? '<div class="lk"><b>经济链条：</b>' + esc(e.economic_link) + '</div>' : '') + '</div>';
    }).join('') : '<div class="empty">该阶段没有已记录的事件。这本身是一个信息：价差变化可能来自未被记录的装置/需求变化，需要补充事件库。</div>';

    el('regime-detail').innerHTML =
      '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">' +
      '<span class="pill info">均值 ' + num(r.mean_spread, 0) + '</span>' +
      '<span class="pill info">偏离前一年 ' + sgn(r.deviation) + num(r.deviation, 0) + '</span>' +
      '<span class="pill ' + (r.direction === '走阔' ? 'no' : 'ok') + '">' + esc(r.direction) + '</span>' +
      '<span class="pill">' + r.n + ' 周</span></div>' +
      '<div class="grid g4" style="margin-bottom:14px">' + regsHtml + '</div>' +
      '<h4 style="font-size:13px;margin:4px 0 8px;color:#cbd6e6">同期事件与经济链条</h4>' + evHtml;
  }

  function renderEventFilter() {
    var kinds = ['全部'];
    (P.events || []).forEach(function (e) { if (kinds.indexOf(e.kind) < 0) kinds.push(e.kind); });
    html('event-filter', kinds.map(function (k) {
      return '<span class="chip' + (S.eventFilter === k ? ' on' : '') + '" data-k="' + esc(k) + '">' + esc(k) + '</span>';
    }).join(''));
    Array.prototype.forEach.call(el('event-filter').querySelectorAll('.chip'), function (c) {
      c.addEventListener('click', function () { S.eventFilter = c.dataset.k; renderEventFilter(); renderEventList(); });
    });
  }

  function renderEventList() {
    var evs = (P.events || []).filter(function (e) { return S.eventFilter === '全部' || e.kind === S.eventFilter; });
    evs = evs.slice().sort(function (a, b) { return a.date < b.date ? 1 : -1; });
    html('event-list', evs.map(function (e) {
      var col = e.price_effect === '收紧' ? '#3ddc97' : (e.price_effect === '宽松' ? '#ff7a8a' : '#ffc857');
      return '<div class="ev" style="cursor:default;border-left-color:' + col + '">' +
        '<div class="t"><span class="kind ' + esc(e.kind) + '">' + esc(e.kind) + '</span>' + esc(e.title) +
        '<span class="pill">' + esc(e.price_effect) + '</span>' +
        (e.verified ? '<span class="pill ok">已核实</span>' : '<span class="pill mid">待核实</span>') + '</div>' +
        '<div class="d">' + esc(e.date) + (e.end ? ' ~ ' + esc(e.end) : ' ~ 至今') + ' ｜ 影响：' + esc((e.regions || []).join('、')) + '</div>' +
        '<div class="n">' + esc(e.detail) + '</div>' +
        (e.economic_link ? '<div class="lk"><b>经济链条：</b>' + esc(e.economic_link) + '</div>' : '') + '</div>';
    }).join(''));
  }

  /* ---------------- ⑦ 地图与基本面 ---------------- */
  function drawMap() {
    var ch = chart('ch-map'); if (!ch) return;
    var px = currentPrices(), n = names();
    var fund = (P.fundamentals || {}).regions || {};
    var pts = [];
    P.meta.regions.forEach(function (r) {
      var cap = 0;
      (fund[r.id] && fund[r.id].producers || []).forEach(function (p) { cap += (p.capacity_mt || 0); });
      var v = px[r.id];
      pts.push({
        name: r.name + '（' + (r.rep_market || '') + '）', value: [r.lon, r.lat, v],
        symbolSize: 18 + Math.sqrt(Math.max(cap, 0)) * 2.2,
        itemStyle: { color: regionColor(r.id), opacity: .85, borderColor: '#0b0f15', borderWidth: 2 },
        label: { show: true, position: 'right', color: '#e6ecf5', fontSize: 12,
                 formatter: function () { return r.name + '\n' + (isNum(v) ? v.toFixed(0) + ' 元/吨' : '—'); },
                 lineHeight: 16 },
        _cap: cap, _role: r.role
      });
    });
    // 连线：距离 + 主运费
    var lines = [];
    var rts = P.primary.freight.routes || [];
    var seen = {};
    rts.forEach(function (r) {
      var k = [r.from, r.to].sort().join('-');
      if (seen[k]) return;
      seen[k] = 1;
      var A = P.meta.regions.filter(function (x) { return x.id === r.from; })[0];
      var B = P.meta.regions.filter(function (x) { return x.id === r.to; })[0];
      if (!A || !B) return;
      lines.push({
        coords: [[A.lon, A.lat], [B.lon, B.lat]],
        lineStyle: { color: r.distance_km > 600 ? 'rgba(255,200,87,.55)' : 'rgba(77,163,255,.55)',
                     width: Math.max(1.2, Math.min(4, r.distance_km / 220)), curveness: .08, type: 'solid' },
        label: { show: true, formatter: r.distance_km + ' km', color: '#8b9bb4', fontSize: 10, position: 'middle' }
      });
    });
    ch.setOption({
      backgroundColor: 'transparent',
      tooltip: Object.assign({ trigger: 'item' }, TIP, {
        formatter: function (p) {
          if (p.seriesType === 'effectScatter' || p.seriesType === 'scatter') {
            var d = p.data;
            return '<b>' + esc(p.name) + '</b><br>最新价：' + (isNum(d.value[2]) ? d.value[2].toFixed(0) + ' 元/吨' : '—') +
              '<br>可核实产能合计：' + d._cap + ' 万吨/年<br>供需角色：' + esc(d._role || '');
          }
          if (p.seriesType === 'lines') return esc(p.name || '');
          if (p.seriesType === 'scatter' && p.name === '中国轮廓（示意）') return '';
          return '';
        }
      }),
      geo: {
        map: 'china-shell', roam: true, zoom: 1.55, center: [116.6, 35.4],
        silent: true, aspectScale: .86,
        itemStyle: { areaColor: '#121a25', borderColor: '#2b3748', borderWidth: .8 },
        emphasis: { disabled: true }
      },
      series: [
        { type: 'lines', coordinateSystem: 'geo', data: lines, z: 2, silent: true,
          effect: { show: true, period: 4, trailLength: .12, symbol: 'arrow', symbolSize: 5, color: 'rgba(126,224,192,.9)' } },
        { type: 'effectScatter', coordinateSystem: 'geo', data: pts, z: 5,
          rippleEffect: { brushType: 'stroke', scale: 2.6 }, showEffectOn: 'render' }
      ]
    }, true);
    if (!G.__mapWarned) {
      G.__mapWarned = 1;
      var note = document.getElementById('map-note');
      if (note) note.style.display = 'block';
    }
  }

  function renderRegionCards() {
    var fund = (P.fundamentals || {}).regions || {}, ls = nowCal().level_stats, n = names();
    html('region-cards', P.meta.regions.map(function (r) {
      var f = fund[r.id] || {}, st = ls[r.id] || {};
      var prods = (f.producers || []).map(function (p) {
        return '<div class="prod"><span>' + esc(p.name) + ' <span style="color:#67768e;font-size:11px">' + esc(p.route || '') + '</span></span>' +
          '<b class="mono">' + (p.capacity_mt ? p.capacity_mt : '—') + '</b></div>';
      }).join('');
      return '<div class="regcard" style="margin-bottom:12px"><h4><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:' +
        regionColor(r.id) + '"></span>' + esc(r.full_name) +
        '<span class="pill ' + (r.role === '净调出' ? 'ok' : (r.role === '净调入' ? 'no' : 'mid')) + '">' + esc(r.role || '') + '</span>' +
        '<span class="pill info">' + num(st.current, 0) + ' 元/吨</span></h4>' +
        (prods ? '<div style="margin-bottom:8px">' + prods + '</div>' : '') +
        '<div class="row"><span>供需角色</span><span style="font-size:11.5px;color:#8b9bb4;text-align:right;max-width:60%">' + esc(f.surplus || '—') + '</span></div>' +
        '<div class="row"><span>产能说明</span><span style="font-size:11.5px;color:#8b9bb4;text-align:right;max-width:62%">' + esc(f.capacity_note || '—') + '</span></div>' +
        '<div class="row"><span>物流</span><span style="font-size:11.5px;color:#8b9bb4;text-align:right;max-width:62%">' + esc(f.logistics_note || '—') + '</span></div>' +
        '</div>';
    }).join(''));
  }

  function renderProducerTable() {
    var fund = (P.fundamentals || {}).regions || {}, n = names();
    var rows = '';
    P.meta.regions.forEach(function (r) {
      var f = fund[r.id] || {};
      (f.producers || []).forEach(function (p) {
        rows += '<tr><td class="l">' + esc(r.name) + '</td><td class="l"><b>' + esc(p.name) + '</b>' +
          (p.ticker ? ' <span class="pill">' + esc(p.ticker) + '</span>' : '') + '</td>' +
          '<td class="l">' + esc(p.city || '—') + '</td>' +
          '<td>' + (p.capacity_mt ? p.capacity_mt : '—') + '</td>' +
          '<td class="l"><span class="pill info">' + esc(p.route || '—') + '</span></td>' +
          '<td class="l" style="font-size:11.5px;color:#8b9bb4">' + esc(p.note || '') + '</td>' +
          '<td>' + (p.verified ? '<span class="pill ok">已核实</span>' : '<span class="pill mid">待核实</span>') + '</td></tr>';
      });
    });
    html('producer-tbl', '<div class="scroll" style="max-height:none"><table><thead><tr><th class="l">地区</th><th class="l">企业</th>' +
      '<th class="l">所在地</th><th>产能(万吨/年)</th><th class="l">工艺</th><th class="l">说明</th><th>核实</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<div class="hint">省级产能合计若【未查到】权威发布，本表不给出合计数字——宁缺不假。</div>');
  }

  function renderDownstream() {
    var fund = (P.fundamentals || {}).regions || {};
    var nat = (P.fundamentals || {}).national || {};
    var pm = nat.process_mix || [];
    var pmHtml = pm.map(function (p) {
      return '<div class="prod"><span>' + esc(p.route) + ' <span style="color:#67768e;font-size:11px">' + esc(p.cost_range || '') + '</span></span>' +
        '<b class="mono">' + pctf(p.share * 100, 1) + '</b></div>' +
        '<div class="bar"><i style="width:' + (p.share * 100) + '%"></i></div>';
    }).join('');
    var blocks = P.meta.regions.map(function (r) {
      var f = fund[r.id] || {};
      var ds = (f.downstream || []).map(function (d) {
        var v = d.share_2023 != null ? d.share_2023 * 100 : null;
        return '<div class="prod"><span>' + esc(d.industry) + '</span><b class="mono">' + pctf(v, 0) + '</b></div>' +
          '<div class="bar"><i style="width:' + (v || 0) + '%"></i></div>';
      }).join('');
      return '<div class="regcard"><h4>' + esc(r.name) + ' 下游结构</h4>' + ds +
        '<div class="hint" style="margin-top:8px">' + esc(f.downstream_caveat || '') + '</div></div>';
    }).join('');
    html('downstream',
      '<div class="grid two"><div class="regcard"><h4>全国工艺结构与成本梯次</h4>' + pmHtml +
      '<div class="hint" style="margin-top:8px">' + esc(nat.cost_tiers_note || '') + '</div></div>' +
      '<div class="regcard"><h4>全国产能（可核实）</h4>' +
      '<div class="row"><span>2024 年底产能</span><b class="mono">' + num(nat.capacity_mt_2024, 0) + ' 万吨</b></div>' +
      '<div class="row"><span>2025 年末产能</span><b class="mono">' + num(nat.capacity_mt_2025, 0) + ' 万吨</b></div>' +
      '<div class="row"><span>2024 年产量</span><b class="mono">' + num(nat.production_mt_2024, 0) + ' 万吨</b></div>' +
      '<div class="row"><span>CR4 集中度</span><b class="mono">' + pctf((nat.cr4_share || 0) * 100, 0) + '</b></div>' +
      '<div class="hint" style="margin-top:8px">' + esc(nat.capacity_note_2025 || '') + '</div></div></div>' +
      '<div class="grid g4" style="margin-top:16px">' + blocks + '</div>');
  }

  /* ---------------- ⑧ 缺口与来源 ---------------- */
  function renderNotes() {
    var g = P.meta.known_gaps || [];
    html('gaps', g.length ? g.map(function (x) {
      return '<div style="border:1px solid #25303f;border-radius:10px;padding:10px 13px;margin-bottom:9px;background:#1a2230">' +
        '<b>' + esc(x.id) + ' · ' + esc(x.item) + '</b>' +
        '<div class="note" style="margin-top:5px">影响：' + esc(x.impact) + '<br>处理方式：<span style="color:#7ee0c0">' + esc(x.handle) + '</span></div></div>';
    }).join('') : '<div class="empty">无</div>');
    var src = P.meta.sources || [];
    html('sources', src.map(function (s) {
      return '<div style="border-bottom:1px dashed #25303f;padding:8px 0">' +
        '<b>[' + esc(s.id) + '] ' + esc(s.name) + '</b> <span class="pill info">' + esc(s.status || '') + '</span>' +
        '<div class="note" style="margin-top:3px">' + esc(s.covers) + (s.date ? '（' + esc(s.date) + '）' : '') +
        (s.url ? '<br><a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.url) + '</a>' : '') + '</div></div>';
    }).join(''));
    var m = P.meta;
    html('disclaimer',
      '<b>1. 数据状态：</b>' + esc(m.data_status) + '。' +
      (m.data_status === 'DEMO' ? '本报告为<b>方法演示</b>，价格序列以已核实的真实骨架为锚构造，<b>金额与分位不得用于报价、交易或对外引用</b>。' : '') +
      '<br><b>2. 不构成交易建议：</b>本报告只做历史统计描述与口径核对，不给出交易建议、目标价或买卖方向。' +
      '<br><b>3. 不认定套利：</b>「价差覆盖运费」只是敏感性参考，未计入资金占用、损耗、账期、卸货短驳、仓储、开票与可成交批量。' +
      '<br><b>4. 不作因果判定：</b>事件与价差变化的对应只用于解释「可能为什么变化」，未做因果检验。' +
      '<br><b>5. 口径优先：</b>任何跨地区比较，先确认规格/税率/计量/交付/付款一致；缺一项就标注，不用 0 顶替。' +
      '<br><b>6. 缺口不补：</b>缺失周、缺失运费、缺失产能均明确标注，绝不插值、绝不估算。' +
      '<br><b>7. 期货：</b>' + esc(m.hedge_note || '') + '（本次是否接入期货：' + (m.hedge_online ? '是' : '否') + '）');
    html('footer',
      '区域价差研究 Skill · regional-spread-analysis ｜ 生成 ' + esc(m.as_run || '') + ' ｜ 数据截止 ' + esc(m.end) +
      ' ｜ 对齐 ' + esc(m.align_method) + ' ｜ 样本 ' + m.n_observations + ' 期' +
      '<br>本页自包含（零外部请求、可离线打开）。图表内核 ECharts 已内嵌。');
  }

  function renderPriceDetailSlot() {
    var box = document.querySelector('#ch-price');
    if (!box) return;
    var parent = box.parentNode.parentNode;
    if (!el('price-detail')) {
      var d = document.createElement('div');
      d.id = 'price-detail';
      parent.appendChild(d);
    }
  }

  function injectEcharts(cb) {
    var src = el('echarts-src').textContent;
    if (!src || src.indexOf('&lt;!--ECHARTS') >= 0 || src.indexOf('<!--ECHARTS') >= 0 || src.length < 1000) { cb(false); return; }
    // 用 Blob URL 注入：比 eval 更接近真实的 script 执行环境，且不引入外部请求
    var blobUrl = null;
    try {
      var blob = new Blob([src], { type: 'text/javascript' });
      blobUrl = URL.createObjectURL(blob);
    } catch (e) {
      try { (0, eval)(src); cb(typeof echarts !== 'undefined'); return; } catch (e2) { cb(false); return; }
    }
    var s = document.createElement('script');
    s.src = blobUrl;
    s.onload = function () { try { URL.revokeObjectURL(blobUrl); } catch (e) {} cb(typeof echarts !== 'undefined'); };
    s.onerror = function () { cb(false); };
    document.head.appendChild(s);
  }

  /* ---------------- 初始化 ---------------- */
  function boot() {
    var raw = el('payload').textContent;
    P = JSON.parse(raw);
    if (!P || !P.primary) { document.body.innerHTML = '<div style="padding:40px;color:#ff7a8a">数据未注入</div>'; return; }

    regs().forEach(function (r) { S.regionOn[r] = true; });
    renderHeader(); renderNav();
    renderSummary(); renderCaliber();
    renderRegionChips(); renderLevelTable(); renderAlignTable();
    renderMatrix(); renderPairChips(); renderPairTable();
    renderPctTable(); renderRollChips();
    initFreight(); renderFreightWarn(); renderFreightInputs(); renderFreightResult(); renderRouteTable();
    renderRegimeChips(); renderRegimeList(); renderEventFilter(); renderEventList();
    renderRegionCards(); renderProducerTable(); renderDownstream();
    renderNotes(); renderPriceDetailSlot();
    bindControls();

    G.__APP = { S: S, P: P, Core: Core, charts: CHARTS, ready: true };

    injectEcharts(function (ok) {
      G.__APP.chartsOk = !!ok;
      Array.prototype.forEach.call(document.querySelectorAll('[id^="ch-"]'), function (c) {
        if (!ok) c.innerHTML = '<div class="empty">图表内核未加载（ECharts 内嵌失败）。表格与数值不受影响。</div>';
      });
      if (ok) {
        try {
          echarts.registerMap('china-shell', GEO_SHELL || {});
        } catch (e) { console.warn('map register failed', e); }
        drawPrice(); drawSpread(); drawRolling(); drawHist(); drawFreight(); drawMap();
      }
    });
  }

  function bindControls() {
    Array.prototype.forEach.call(el('caliber-seg').querySelectorAll('button'), function (b) {
      b.addEventListener('click', function () {
        if (b.dataset.c === 'control' && !P.control) return;
        S.caliber = b.dataset.c;
        Array.prototype.forEach.call(el('caliber-seg').querySelectorAll('button'), function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        renderLevelTable(); renderMatrix(); renderPairTable(); renderPctTable();
        if (G.__APP && G.__APP.chartsOk) { drawPrice(); drawSpread(); drawRolling(); drawHist(); drawFreight(); }
      });
    });
    el('range-sel').addEventListener('change', function () {
      S.range = this.value;
      if (G.__APP && G.__APP.chartsOk) { drawPrice(); drawSpread(); }
    });
    el('price-mode').addEventListener('change', function () {
      S.priceMode = this.value;
      if (G.__APP && G.__APP.chartsOk) drawPrice();
    });
    el('freight-mode').addEventListener('click', function (ev) {
      var b = ev.target.closest('button'); if (!b) return;
      S.freightOn = b.dataset.m === 'on';
      Array.prototype.forEach.call(el('freight-mode').querySelectorAll('button'), function (x) { x.classList.remove('on'); });
      b.classList.add('on');
      renderFreightResult();
      if (G.__APP && G.__APP.chartsOk) drawFreight();
    });
    el('freight-src').addEventListener('click', function (ev) {
      var b = ev.target.closest('button'); if (!b) return;
      S.freightSrc = b.dataset.s;
      Array.prototype.forEach.call(el('freight-src').querySelectorAll('button'), function (x) { x.classList.remove('on'); });
      b.classList.add('on');
      renderFreightInputs();
    });
    el('f-reset').addEventListener('click', function () {
      initFreight(); renderFreightInputs();
      if (G.__APP && G.__APP.chartsOk) { drawFreight(); }
      renderFreightResult();
    });
  }

  G.bootUI = boot;
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
