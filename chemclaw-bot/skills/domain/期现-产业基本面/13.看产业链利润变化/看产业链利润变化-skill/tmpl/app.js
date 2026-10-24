/* =========================================================================
 * PVC 电石法 产业链利润研究与成本计算器 —— 应用逻辑
 * 计算引擎与 Python scripts/engine.py 完全等价（同公式、同顺序、同单位换算）
 * ========================================================================= */
'use strict';
const D = PAYLOAD.data, H = PAYLOAD.history, ANCH = PAYLOAD.anchors;
const DEF = JSON.parse(JSON.stringify(PAYLOAD.defaults));
let P = JSON.parse(JSON.stringify(DEF));
P.manufacturing.enabled = true;
P.byproduct.enabled = false;

/* ---------------- 工具 ---------------- */
const nf = (v, d = 0) => (v === null || v === undefined || isNaN(v)) ? '—' : Number(v).toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmt = (v, d = 0) => nf(v, d);
const pct = (v, d = 1) => (v === null || v === undefined) ? '—' : (v >= 0 ? '+' : '') + Number(v).toFixed(d) + '%';
const cls = v => v > 0 ? 'pos' : (v < 0 ? 'neg' : '');
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const KINDNAME = { raw: '原料', energy: '能源', aux: '辅料', byproduct: '副产' };
const KINDCLS = { raw: 'raw', energy: 'energy', aux: 'aux', byproduct: 'byp' };

function unitFactor(it) {
  const u = (it.unit || '').toLowerCase();
  if (u.startsWith('kg')) return { k: 0.001, ay: true };
  if (u.startsWith('kwh')) return { k: 1, ay: false };
  return { k: 1, ay: (it.kind === 'raw' || it.kind === 'aux') };
}

/* ---------------- 计算引擎（与 engine.py 等价） ---------------- */
function compute(params, shock) {
  const p = params || P, sh = shock || {};
  const y = Math.max(p.yield || 1, 0.01);
  const rows = [];
  if (p.byproduct && p.byproduct.enabled) rows.push(p.byproduct);
  p.inputs.forEach(it => rows.push(it));

  let raw = 0, energy = 0, aux = 0, byp = 0;
  const breakdown = [];
  rows.forEach(it => {
    const price = it.price * (1 + (sh[it.id] || 0));
    const { k, ay } = unitFactor(it);
    let cost = 0;
    if (it.cons > 0) cost = it.cons * k * price / (ay ? y : 1);
    const rec = Object.assign({}, it, {
      price, cost, k, ay,
      cons_eff: (ay && it.cons) ? it.cons / y : it.cons
    });
    if (it.kind === 'raw') raw += cost;
    else if (it.kind === 'energy') energy += cost;
    else if (it.kind === 'aux') aux += cost;
    else if (it.kind === 'byproduct') byp += cost;
    breakdown.push(rec);
  });

  const m = p.manufacturing || {};
  const mfg = m.enabled ? (m.labor + m.depreciation + m.packaging + m.other) : 0;
  const price = p.product.price * (1 + (sh.product || 0));
  const netRaw = raw - byp;
  const spread = price - netRaw;
  const profit = spread - energy - aux - mfg;
  const totalCost = netRaw + energy + aux + mfg;
  const base = raw + energy + aux + mfg;
  const shares = {};
  breakdown.forEach(b => { shares[b.id] = base ? b.cost / base * 100 : 0; });
  return {
    price, y, raw, energy, aux, mfg, byp, netRaw, spread, profit, totalCost,
    margin: price ? profit / price * 100 : 0,
    breakdown, shares,
    shareRaw: base ? raw / base * 100 : 0, shareEnergy: base ? energy / base * 100 : 0,
    shareAux: base ? aux / base * 100 : 0, shareMfg: base ? mfg / base * 100 : 0,
    cac2Cost: (breakdown.find(b => b.id === 'cac2') || { cost: 0 }).cost
  };
}

/* ---------------- 图表主题 ---------------- */
const AX = { axisLine: { lineStyle: { color: '#2a405e' } }, axisLabel: { color: '#8fa3bd', fontSize: 11 }, splitLine: { lineStyle: { color: 'rgba(42,64,94,.45)' } } };
const TT = { backgroundColor: 'rgba(10,20,36,.96)', borderColor: '#2a405e', textStyle: { color: '#e6edf7', fontSize: 12 } };
const charts = {};
function ec(id, opt) {
  const el = document.getElementById(id);
  if (!el) return null;
  let c = charts[id];
  if (!c) { c = echarts.init(el, null, { renderer: 'canvas' }); charts[id] = c; }
  c.setOption(opt, true);
  return c;
}
window.addEventListener('resize', () => Object.values(charts).forEach(c => c.resize()));

/* ---------------- 导航 ---------------- */
document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => {
  document.querySelectorAll('#tabs button').forEach(x => x.classList.remove('on'));
  b.classList.add('on');
  document.querySelectorAll('section.view').forEach(s => s.classList.remove('on'));
  document.getElementById('v-' + b.dataset.v).classList.add('on');
  setTimeout(() => Object.values(charts).forEach(c => c.resize()), 30);
  renderView(b.dataset.v);
});

/* ---------------- KPI ---------------- */
function kpiCard(k, v, s, c) {
  return `<div class="kpi ${c || ''}"><div class="k">${k}</div><div class="v ${cls(v)}">${v}</div><div class="s">${s}</div></div>`;
}
function renderKpis() {
  const r = compute();
  const el = document.getElementById('kpis');
  const yoyS = (D.cross.pvc_spot_ppi / D.cross.pvc_spot_month_ago - 1) * 100;
  const caS = (D.cross.carbide_spot / D.cross.carbide_month_ago - 1) * 100;
  el.innerHTML =
    kpiCard('PVC 现货 (SG-5)', fmt(r.price), `${D.cross.date} · 生意社基准价`, 'b') +
    kpiCard('电石到厂价', fmt(caAt('carbide_spot')), `${D.cross.date} · 生意社`, 'a') +
    kpiCard('理论原料成本', fmt(r.raw), `电石占原料篮子 ${(r.raw ? r.cac2Cost / r.raw * 100 : 0).toFixed(1)}%`, 'a') +
    kpiCard('理论加工价差', fmt(r.spread), '售价 − 原料成本', 'b') +
    kpiCard('理论制造利润', fmt(r.profit), `已计入 ${fmt(r.energy + r.aux + r.mfg)} 元/吨成本`, 'c') +
    kpiCard('PVC 月内涨跌', pct(yoyS), `电石 ${pct(caS)}`, 'd');
}
function caAt(key) { return D.cross[key] || 0; }

/* ---------------- 输入面板 ---------------- */
function renderInputs() {
  const box = document.getElementById('inputs');
  box.innerHTML = '';
  P.inputs.forEach((it, i) => {
    if (it.id === 'power_cac2' && P.route !== 'carbide_int') return;
    const div = document.createElement('div');
    div.className = 'card';
    div.style.cssText = 'padding:10px;background:#0b1729;box-shadow:none;margin-bottom:8px';
    const isEst = /未定值|估计/.test(it.source || '');
    div.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <div style="font-size:12.5px;font-weight:600">${it.name}
          <span class="tag ${KINDCLS[it.kind] || ''}">${KINDNAME[it.kind] || it.kind}</span>
          ${isEst ? '<span class="tag est">估算</span>' : ''}</div>
        <button class="btn" style="padding:2px 8px;font-size:11px" data-info="${it.id}">来源</button>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px">
        <div class="ctl"><label>单耗 ${it.unit.split('/')[0]}</label><input type="number" step="0.01" min="0" data-id="${it.id}" data-f="cons" value="${it.cons}"></div>
        <div class="ctl"><label>单价</label><input type="number" step="1" min="0" data-id="${it.id}" data-f="price" value="${it.price}"></div>
        <div class="ctl"><label>成本 元/吨</label><input type="text" disabled value="${fmt(compute().breakdown.find(b => b.id === it.id).cost, 1)}"></div>
      </div>`;
    box.appendChild(div);
  });
  box.querySelectorAll('button[data-info]').forEach(b => b.onclick = () => showInfo(b.dataset.info));
  box.querySelectorAll('input[data-id]').forEach(inp => {
    inp.oninput = () => {
      const it = P.inputs.find(x => x.id === inp.dataset.id);
      if (!it) return;
      it[inp.dataset.f] = parseFloat(inp.value) || 0;
      inp.classList.add('chg');
      renderAll(false);
    };
  });
  document.getElementById('ctlCount').textContent = P.inputs.filter(x => x.cons > 0 || x.id === 'power_cac2').length + ' 项';
}

/* ---------------- 结果区 ---------------- */
function renderResults() {
  const r = compute();
  const box = document.getElementById('results');
  const row = (label, f, v, hi, hl) => `<div class="resrow ${hi ? 'hi' : ''}">
      <div class="l"><b>${label}</b><span class="formula">${f}</span></div>
      <div class="v ${hl || cls(v)}">${fmt(v)}</div></div>`;
  box.innerHTML =
    row('产品售价（含税）', 'P', r.price, false, '') +
    row('① 原料成本（已按收率修正）', 'Σ 单耗ᵢ ÷ 收率 × 单价ᵢ', r.raw, false, '') +
    (r.byp > 0 ? row('①b 联产烧碱收益抵减', '0.75 × 烧碱价（一体化口径）', -r.byp, false, '') : '') +
    row('② 加工价差 = 售价 − 原料成本', 'P − ① (+①b)', r.spread, true, '') +
    row('③ 能源成本', '电耗 × 电价 + 汽耗 × 汽价', -r.energy, false, '') +
    row('④ 辅料成本', 'HCl + 触媒 + 助剂', -r.aux, false, '') +
    row('⑤ 制造费用', r.mfg > 0 ? '折旧 320 + 人工 260 + 包装 120 + 其他 80' : '（未勾选 → 不计入）', -r.mfg, false, '') +
    row('理论制造利润 = ② − ③④⑤', '价差 − 已核实成本', r.profit, true, '') +
    row('理论总制成成本（②之前的成本）', '① + ③ + ④ + ⑤', r.totalCost, false, '');

  let gapNote = '';
  if (r.byp === 0) gapNote = `<div class="note">当前为<b>外购电石口径</b>：不包含自产电石的电耗与联产烧碱收益，与隆众周报样本口径一致。`;
  else gapNote = `<div class="note info">当前为<b>氯碱一体化口径</b>：已计入联产烧碱收益抵减，不可与“外购电石口径”的数直接比较。`;
  gapNote += ` 利润率 ${r.margin.toFixed(1)}%。</div>`;
  box.insertAdjacentHTML('beforeend', gapNote);
}

/* ---------------- 成本占比 / 瀑布图 ---------------- */
const PALETTE = ['#f59e0b', '#4cc9f0', '#a78bfa', '#22c55e', '#f43f5e', '#14b8a6', '#eab308', '#8b5cf6', '#06b6d4', '#84cc16', '#fb7185'];
function renderCharts() {
  const r = compute();
  // 饼图
  const data = r.breakdown.filter(b => b.cost > 0.5).map((b, i) => ({
    name: b.name.replace(/\(.*?\)/g, '').trim(), value: +b.cost.toFixed(1),
    itemStyle: { color: b.kind === 'byproduct' ? '#22c55e' : PALETTE[i % PALETTE.length] }
  }));
  ec('ch_share', {
    tooltip: Object.assign({ trigger: 'item', formatter: p => `${p.name}<br/><b>${fmt(p.value, 1)}</b> 元/吨（${p.percent}%）` }, TT),
    series: [{
      type: 'pie', radius: ['46%', '72%'], center: ['50%', '52%'],
      itemStyle: { borderColor: '#0f172a', borderWidth: 2, borderRadius: 5 },
      label: { color: '#9fb0c8', fontSize: 10.5, formatter: '{b}\n{d}%' },
      labelLine: { lineStyle: { color: '#2a405e' }, length: 8, length2: 8 },
      data
    }]
  });

  // 瀑布
  const steps = [];
  let acc = 0;
  const push = (n, v, base) => steps.push({ name: n, value: v, base, isTotal: false });
  steps.push({ name: '售价', value: r.price, base: 0, isTotal: true });
  acc = r.price;
  const items = [
    ['原料(收率修正)', -r.raw], ['能源', -r.energy], ['辅料', -r.aux], ['制造费用', -r.mfg]
  ];
  if (r.byp > 0) items.splice(1, 0, ['烧碱抵减', r.byp]);
  items.forEach(([n, v]) => {
    if (Math.abs(v) < 0.5) return;
    const b = v >= 0 ? acc : acc + v;
    steps.push({ name: n, value: Math.abs(v), base: b, isTotal: false, isGain: v >= 0 });
    acc += v;
  });
  steps.push({ name: '理论利润', value: r.profit, base: 0, isTotal: true });
  ec('ch_waterfall', {
    tooltip: Object.assign({
      formatter: p => {
        const s = steps[p.dataIndex];
        return `${s.name}<br/><b>${s.isTotal ? fmt(s.value) : fmt(s.isGain ? s.value : -s.value)}</b> 元/吨`;
      }
    }, TT),
    grid: { left: 78, right: 16, top: 18, bottom: 42 },
    xAxis: Object.assign({ type: 'category', data: steps.map(s => s.name), axisLabel: { color: '#8fa3bd', fontSize: 10.5, interval: 0, rotate: 18 } }, { axisLine: AX.axisLine }),
    yAxis: Object.assign({ type: 'value' }, AX),
    series: [{
      type: 'bar', stack: 't', barWidth: '52%', silent: false,
      data: steps.map((s, i) => ({
        value: s.base, itemStyle: { color: 'transparent' }
      })).concat([]),
      label: { show: false }
    }, {
      type: 'bar', stack: 't', barWidth: '52%',
      data: steps.map(s => ({
        value: s.value,
        itemStyle: {
          color: s.isTotal ? (s.name === '理论利润' ? (s.value >= 0 ? '#10b981' : '#f43f5e') : '#4cc9f0')
            : (s.isGain ? '#22c55e' : '#fb923c'),
          borderRadius: 3
        }
      })),
      label: {
        show: true, position: 'top', color: '#cbd5e1', fontSize: 10,
        formatter: p => { const s = steps[p.dataIndex]; return s.isTotal ? fmt(s.value) : ''; }
      }
    }]
  });
}

/* ---------------- 明细表 ---------------- */
function renderBreakdown() {
  const r = compute();
  let h = `<thead><tr><th>物料 / 能源</th><th>类别</th><th>名义单耗</th><th>计费单耗</th><th>单位</th>
    <th>单价</th><th>成本 元/吨</th><th>占比</th></tr></thead><tbody>`;
  r.breakdown.forEach(b => {
    if (b.cons === 0) return;
    const est = /未定值|估计/.test(b.source || '');
    h += `<tr style="cursor:pointer" data-info="${b.id}">
      <td>${b.name}${est ? ' <span class="tag est">估算</span>' : ''}</td>
      <td style="text-align:right"><span class="tag ${KINDCLS[b.kind]}">${KINDNAME[b.kind]}</span></td>
      <td class="mono">${b.cons}</td>
      <td class="mono">${b.ay ? b.cons_eff.toFixed(4) : b.cons}</td>
      <td class="mut" style="font-size:11px">${b.unit}</td>
      <td class="mono">${fmt(b.price, 2)}</td>
      <td class="mono" style="font-weight:600">${b.kind === 'byproduct' ? '-' + fmt(b.cost, 2) : fmt(b.cost, 2)}</td>
      <td class="mono ${b.kind === 'byproduct' ? 'down' : ''}">${b.kind === 'byproduct' ? '抵减' : b.cost === 0 ? '—' : (r.raw + r.energy + r.aux + r.mfg ? (b.cost / (r.raw + r.energy + r.aux + r.mfg) * 100).toFixed(2) + '%' : '—')}</td>
    </tr>`;
  });
  h += `</tbody><tfoot>
    <tr><td colspan="6">原料合计 / 能源合计 / 辅料合计 / 制造费用</td>
      <td class="mono">${fmt(r.raw, 1)} / ${fmt(r.energy, 1)} / ${fmt(r.aux, 1)} / ${fmt(r.mfg, 1)}</td>
      <td class="mono">${fmt(r.totalCost, 1)}</td></tr></tfoot>`;
  document.getElementById('tbl_breakdown').innerHTML = h;
  document.querySelectorAll('#tbl_breakdown tr[data-info]').forEach(tr => tr.onclick = () => showInfo(tr.dataset.info));
}

function renderExcluded() {
  const ex = [
    '财务费用（利息/融资）', '销售费用与物流运费', '增值税进销项税额差',
    '电石渣/废水中和处理费', '装置检修与开停车损失', '企业所得税与地方附加',
    '地方电价/汽价差异', '自产电石的电耗（外购口径）', '联产烧碱收益（外购口径）'
  ];
  document.getElementById('excluded').innerHTML = ex.map(e => `<span class="pill">${e}</span>`).join('');
}

/* ---------------- 抽屉：参数与来源 ---------------- */
function showInfo(id) {
  const it = P.inputs.find(x => x.id === id) || (P.byproduct && P.byproduct.id === id ? P.byproduct : null);
  if (!it) return;
  const base = compute();
  const up = compute(null, { [id]: 0.05 }), dn = compute(null, { [id]: -0.05 });
  const body = document.getElementById('drawerBody');
  body.innerHTML = `
    <button class="x" onclick="closeDrawer()">×</button>
    <h4>${it.name}</h4>
    <div class="small">类别：${KINDNAME[it.kind]} · 计价单位：${it.unit}</div>
    <div class="kv">
      <div class="k">名义单耗</div><div class="mono">${it.cons} ${it.unit}</div>
      <div class="k">计费单耗</div><div class="mono">${(unitFactor(it).ay && it.cons ? (it.cons / base.y).toFixed(4) : it.cons)} ${it.unit}${unitFactor(it).ay ? '（÷ 收率 ' + base.y + '）' : '（能源不受收率影响）'}</div>
      <div class="k">当前单价</div><div class="mono">${fmt(it.price, 2)}</div>
      <div class="k">单位成本</div><div class="mono"><b>${fmt(base.breakdown.find(b => b.id === id).cost, 2)}</b> 元/吨 PVC</div>
      <div class="k">占原料成本</div><div class="mono">${it.kind === 'raw' && base.raw ? (base.breakdown.find(b => b.id === id).cost / base.raw * 100).toFixed(1) + '%' : '—'}</div>
      <div class="k">占总成本</div><div class="mono">${(base.raw + base.energy + base.aux + base.mfg) ? (base.breakdown.find(b => b.id === id).cost / (base.raw + base.energy + base.aux + base.mfg) * 100).toFixed(2) + '%' : '—'}</div>
      <div class="k">±5% 影响</div><div class="mono">利润 ${fmt(up.profit - base.profit, 1)} / ${fmt(dn.profit - base.profit, 1)} 元/吨</div>
    </div>
    <div class="note info" style="margin-bottom:10px"><b>核算口径：</b>${it.source || ''}</div>
    <div class="note">${it.note || ''}</div>
    <div class="hr"></div>
    <div class="small" style="color:var(--tx2);font-weight:600;margin-bottom:6px">计算展开</div>
    <div class="mono small" style="background:#0a1424;border:1px solid var(--line);border-radius:9px;padding:10px;line-height:1.9">
      ${it.cons} × ${unitFactor(it).k} × ${fmt(it.price, 2)}${unitFactor(it).ay ? ' ÷ ' + base.y : ''}
      = <b style="color:var(--accent)">${fmt(base.breakdown.find(b => b.id === id).cost, 2)}</b> 元/吨
    </div>`;
  document.getElementById('drawer').classList.add('on');
}
function closeDrawer() { document.getElementById('drawer').classList.remove('on'); }

/* ======================= 历史视图 ======================= */
function renderHistory() {
  const hs = H.history.filter(h => h.spread !== null);
  const mon = H.monthly;
  const v = H.validation, wv = H.week_validation;

  // KPIs
  const first = hs[0], last = hs[hs.length - 1];
  const spreads = hs.map(h => h.spread);
  const ku = H.week_validation.agg;
  document.getElementById('hkpis').innerHTML =
    kpiCard('区间理论加工价差', fmt(last.spread), `${first.date} → ${last.date}`, 'b') +
    kpiCard('区间均值', fmt(spreads.reduce((a, b) => a + b, 0) / spreads.length), `样本 ${hs.length} 个交易日`, 'b') +
    kpiCard('区间极值', `${fmt(Math.min(...spreads))} ~ ${fmt(Math.max(...spreads))}`, '低点 / 高点', 'a') +
    kpiCard('理论利润（最新）', fmt(last.profit), '扣能源/辅料/制造费用', 'c') +
    kpiCard('与隆众毛利同号率', (ku.sign_agree / ku.n_weeks * 100).toFixed(0) + '%', `${ku.n_weeks} 周中 ${ku.sign_agree} 周一致`, 'd');

  // 主图
  const dates = H.history.map(h => h.date);
  const pvcSpot = H.history.map(h => h.pvc_src === 'spot' ? h.pvc : null);
  const pvcProxy = H.history.map(h => h.pvc_src !== 'spot' ? h.pvc : null);
  const ca = H.history.map(h => h.carbide);
  const sp = H.history.map(h => h.spread);
  const startIdx = H.history.findIndex(h => h.spread !== null);
  ec('ch_hist', {
    tooltip: Object.assign({
      trigger: 'axis',
      formatter: ps => {
        let s = `<b>${ps[0].axisValue}</b>`;
        ps.forEach(p => { if (p.value !== null && p.value !== undefined) s += `<br/>${p.marker}${p.seriesName}：<b>${fmt(p.value, 1)}</b>`; });
        return s;
      }
    }, TT),
    legend: { data: ['PVC 现货价', 'PVC 期货代理', '电石到厂价', '理论加工价差'], textStyle: { color: '#9fb0c8', fontSize: 11 }, top: 0 },
    grid: { left: 62, right: 62, top: 38, bottom: 46 },
    xAxis: Object.assign({ type: 'category', data: dates, boundaryGap: false }, AX),
    yAxis: [
      Object.assign({ type: 'value', name: '元/吨', nameTextStyle: { color: '#64778f' }, min: 'dataMin' }, AX),
      Object.assign({ type: 'value', name: '价差', nameTextStyle: { color: '#64778f' }, splitLine: { show: false } }, { axisLine: AX.axisLine, axisLabel: AX.axisLabel })
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 8, borderColor: '#2a405e', fillerColor: 'rgba(76,201,240,.12)', textStyle: { color: '#64778f' } }],
    series: [
      { name: '理论加工价差', type: 'line', yAxisIndex: 1, data: sp, smooth: true, showSymbol: false, lineStyle: { width: 1.6, color: '#22c55e' }, itemStyle: { color: '#22c55e' },
        markArea: startIdx > 0 ? { silent: true, itemStyle: { color: 'rgba(100,116,139,.10)' }, data: [[{ xAxis: dates[0] }, { xAxis: dates[startIdx - 1] }]] } : undefined },
      { name: 'PVC 现货价', type: 'line', data: pvcSpot, smooth: true, showSymbol: false, connectNulls: false, lineStyle: { width: 2.2, color: '#4cc9f0' }, itemStyle: { color: '#4cc9f0' } },
      { name: 'PVC 期货代理', type: 'line', data: pvcProxy, smooth: true, showSymbol: false, connectNulls: false, lineStyle: { width: 1.6, color: '#64748b', type: 'dashed' }, itemStyle: { color: '#64748b' } },
      { name: '电石到厂价', type: 'line', data: ca, smooth: true, showSymbol: false, lineStyle: { width: 2, color: '#f59e0b' }, itemStyle: { color: '#f59e0b' } }
    ]
  });

  // 价差 vs 毛利对比（月度）
  const ms = mon;
  ec('ch_vs', {
    tooltip: Object.assign({ trigger: 'axis' }, TT),
    legend: { data: ['理论加工价差', '理论制造利润', '隆众毛利(全国电石法)'], textStyle: { color: '#9fb0c8', fontSize: 11 } },
    grid: { left: 58, right: 20, top: 36, bottom: 40 },
    xAxis: Object.assign({ type: 'category', data: ms.map(m => m.month) }, AX),
    yAxis: Object.assign({ type: 'value', name: '元/吨' }, AX),
    series: [
      { name: '理论加工价差', type: 'bar', data: ms.map(m => m.spread), itemStyle: { color: 'rgba(76,201,240,.75)', borderRadius: [3, 3, 0, 0] } },
      { name: '理论制造利润', type: 'line', data: ms.map(m => m.profit), smooth: true, symbolSize: 6, lineStyle: { color: '#f59e0b', width: 2 }, itemStyle: { color: '#f59e0b' } },
      { name: '隆众毛利(全国电石法)', type: 'line', data: ms.map(m => m.ms_profit_nat), smooth: true, symbol: 'diamond', symbolSize: 7, lineStyle: { color: '#f43f5e', width: 2, type: 'dashed' }, itemStyle: { color: '#f43f5e' } }
    ]
  });

  // 周度偏差
  const wk = wv.weeks;
  ec('ch_dev', {
    tooltip: Object.assign({ trigger: 'axis', formatter: ps => {
      const w = wk[ps[0].dataIndex];
      return `<b>${w.date}</b><br/>理论利润 ${fmt(w.theory, 1)}<br/>隆众毛利 ${fmt(w.mysteel, 1)}<br/>偏差 <b>${fmt(w.diff, 1)}</b>`;
    } }, TT),
    grid: { left: 58, right: 20, top: 30, bottom: 40 },
    xAxis: Object.assign({ type: 'category', data: wk.map(w => w.date.slice(4, 6) + '-' + w.date.slice(6)) }, AX),
    yAxis: Object.assign({ type: 'value', name: '偏差 元/吨' }, AX),
    series: [{
      type: 'bar', data: wk.map(w => ({ value: w.diff, itemStyle: { color: Math.abs(w.diff) > 300 ? '#f43f5e' : (w.diff > 0 ? '#22c55e' : '#fb923c'), borderRadius: [2, 2, 0, 0] } })),
      markLine: { silent: true, symbol: 'none', lineStyle: { color: '#a78bfa', type: 'dashed' }, data: [{ yAxis: wv.agg.mean_diff, label: { formatter: '均值 ' + wv.agg.mean_diff.toFixed(0), color: '#a78bfa', fontSize: 10 } }] }
    }]
  });

  // 月度总表
  let h = `<thead><tr><th>月份</th><th>PVC(现货)</th><th>PVC 代理</th><th>电石</th><th>理论原料成本</th>
    <th>理论加工价差</th><th>理论制造利润</th><th>隆众成本</th><th>隆众毛利</th><th>偏差</th><th>价格来源</th></tr></thead><tbody>`;
  mon.forEach(m => {
    const diff = (m.profit !== null && m.ms_profit_nat !== null) ? m.profit - m.ms_profit_nat : null;
    h += `<tr>
      <td>${m.month}</td>
      <td class="mono">${m.src && m.src.includes('spot') ? fmt(m.pvc) : '<span class="mut">—</span>'}</td>
      <td class="mono mut">${fmt(m.pvc_proxy)}</td>
      <td class="mono">${fmt(m.carbide)}</td>
      <td class="mono">${fmt(m.raw_cost)}</td>
      <td class="mono" style="font-weight:600;color:#9be3f7">${fmt(m.spread)}</td>
      <td class="mono ${cls(m.profit)}">${fmt(m.profit)}</td>
      <td class="mono mut">${fmt(m.ms_cost_nat)}</td>
      <td class="mono ${cls(m.ms_profit_nat)}">${fmt(m.ms_profit_nat)}</td>
      <td class="mono ${cls(diff)}">${diff === null ? '—' : fmt(diff)}</td>
      <td class="mut" style="font-size:10.5px">${m.src === 'spot' ? '现货' : m.src === 'proxy' ? '代理+锚点' : m.src === 'proxy+spot' ? '混合' : '无电石价'}</td>
    </tr>`;
  });
  h += `</tbody>`;
  document.getElementById('tbl_month').innerHTML = h;
}

/* ======================= 成本结构视图 ======================= */
const FLOW = [
  { t: '上游', n: '兰炭 + 石灰石', p: '电石', s: 'CaC₂ 发气量→乙炔' },
  { t: '① 乙炔发生', n: '电石 CaC₂', p: '1.45 t/t', s: '国标 1.45–1.5；隆众统计 1.35–1.42' },
  { t: '② 合成', n: '氯化氢 HCl', p: '0.72–0.85 t/t', s: '氯 + 氢燃烧合成' },
  { t: '③ 聚合', n: 'VCM → PVC', p: '收率 97%', s: '悬浮聚合 + 汽提 + 干燥' },
  { t: '④ 成品', n: 'PVC SG-5', p: '1 t', s: '包装入库' }
];
function renderCostView() {
  document.getElementById('flow').innerHTML = FLOW.map((f, i) =>
    `<div class="fnode"><div class="t">${f.t}</div><div class="n">${f.n}</div><div class="p">${f.p}</div>
     <div class="small" style="font-size:10.5px;line-height:1.5">${f.s}</div></div>` +
    (i < FLOW.length - 1 ? '<div class="farrow">→</div>' : '')).join('');

  const rows = [
    ['电石 CaC₂', '1.45–1.50 t/t', '国标口径（前瞻/新浪财经 2022-01-17 引国家标准）', '外购电石'],
    ['电石 CaC₂', '1.35–1.42 t/t', '隆众资讯行业统计标准（2024-12 文章）', '外购电石·行业统计'],
    ['电石 CaC₂', '1.40–1.60 t/t', '中国化工网（2026）', '外购电石·较宽区间'],
    ['氯化氢 HCl', '750–850 kg/t', '国标口径', '气体计价'],
    ['氯化氢 HCl', '630–650 kg/t', '隆众行业统计', '气体计价'],
    ['PVC 装置电耗', '450–500 kWh/t', '国标口径（装置本级）', '外购电石企业'],
    ['综合电耗', '≈8500 kWh/t', '中国化工报 2025-11-05（含电石环节）', '一体化全链'],
    ['电石电耗', '3400–3600 kWh/t', '联成化学 2020（台塑）', '电石厂'],
    ['汞触媒', '1.2 kg/t PVC', '专利 CN103408392A', '低汞/无汞'],
    ['乙烯（对照）', '0.5 t/t', '隆众（乙烯法）', '乙烯法'],
    ['氯气（乙烯法）', '0.6 t/t', '隆众（乙烯法）', '乙烯法'],
    ['VCM（乙烯法）', '1.002 t/t', '隆众（乙烯法）', '乙烯法']
  ];
  let h = `<thead><tr><th>指标</th><th>单耗</th><th>来源</th><th>适用范围</th></tr></thead><tbody>`;
  rows.forEach(r => h += `<tr><td>${r[0]}</td><td class="mono" style="font-weight:600">${r[1]}</td><td style="text-align:left;white-space:normal" class="mut">${r[2]}</td><td style="text-align:left" class="mut">${r[3]}</td></tr>`);
  h += `</tbody>`;
  document.getElementById('tbl_dose').innerHTML = h;

  // 结构对比
  const r = compute();
  const lit = { name: '文献口径', raw: 68, aux: 15, energy: 6, mfg: 6, other: 5 };
  ec('ch_struct', {
    tooltip: Object.assign({ trigger: 'axis', axisPointer: { type: 'shadow' } }, TT),
    legend: { data: ['本模型', '文献口径(前瞻/隆众)'], textStyle: { color: '#9fb0c8', fontSize: 11 } },
    grid: { left: 52, right: 18, top: 34, bottom: 30 },
    xAxis: Object.assign({ type: 'value', max: 100, axisLabel: { formatter: '{value}%', color: '#8fa3bd' } }, { splitLine: AX.splitLine }),
    yAxis: Object.assign({ type: 'category', data: ['其他', '制造费用', '能源', '辅料/HCl', '电石'] }, { axisLine: AX.axisLine, axisLabel: AX.axisLabel }),
    series: [
      { name: '本模型', type: 'bar', stack: 'a', data: [0, r.shareMfg, r.shareEnergy, r.shareAux, r.shareRaw].map(x => +x.toFixed(1)),
        itemStyle: { color: '#4cc9f0' }, label: { show: true, color: '#04101f', fontSize: 10, formatter: p => p.value > 4 ? p.value + '%' : '' } },
      { name: '文献口径(前瞻/隆众)', type: 'bar', stack: 'b', data: [5, lit.mfg, lit.energy, lit.aux, lit.raw],
        itemStyle: { color: 'rgba(167,139,250,.55)' }, label: { show: true, color: '#e6edf7', fontSize: 10, formatter: p => p.value > 4 ? p.value + '%' : '' } }
    ]
  });

  // 收率曲线
  const ys = [0.92, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 1.0];
  const costs = ys.map(y => {
    const p2 = JSON.parse(JSON.stringify(P)); p2.yield = y;
    return +compute(p2).raw.toFixed(0);
  });
  ec('ch_yield', {
    tooltip: Object.assign({ trigger: 'axis' }, TT),
    grid: { left: 66, right: 20, top: 26, bottom: 40 },
    xAxis: Object.assign({ type: 'category', data: ys.map(y => (y * 100).toFixed(0) + '%'), name: '综合收率' }, AX),
    yAxis: Object.assign({ type: 'value', name: '原料成本 元/吨' }, AX),
    series: [{
      type: 'line', data: costs, smooth: true, symbolSize: 7,
      lineStyle: { color: '#f59e0b', width: 2.5 }, itemStyle: { color: '#f59e0b' },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(245,158,11,.32)' }, { offset: 1, color: 'rgba(245,158,11,0)' }]) },
      markLine: { silent: true, symbol: 'none', data: [{ yAxis: costs[ys.indexOf(0.97)] || 0, lineStyle: { color: '#4cc9f0', type: 'dashed' }, label: { formatter: '当前 97%', color: '#4cc9f0' } }] }
    }]
  });
}

/* ======================= 敏感性 ======================= */
function fmtCell(v, good) {
  const t = v >= 0;
  const a = clamp(Math.abs(v) / 900, 0, 1);
  const col = t ? `rgba(16,185,129,${0.10 + a * 0.55})` : `rgba(244,63,94,${0.10 + a * 0.55})`;
  return `background:${col};color:#fff;font-weight:600`;
}
function renderSens() {
  const sm = H.sensitivity.matrix;
  const steps = sm.steps;
  const build = (data) => {
    let h = `<thead><tr><th>电石 \\ 产品</th>` + steps.map(s => `<th>${s > 0 ? '+' : ''}${(s * 100).toFixed(0)}%</th>`).join('') + `</tr></thead><tbody>`;
    data.forEach((row, i) => {
      h += `<tr><td style="font-weight:600">${steps[i] > 0 ? '+' : ''}${(steps[i] * 100).toFixed(0)}%</td>`;
      row.forEach(v => h += `<td class="mono" style="${fmtCell(v)}">${fmt(v)}</td>`);
      h += `</tr>`;
    });
    return h + `</tbody>`;
  };
  document.getElementById('tbl_sm_spread').innerHTML = build(sm.spread);
  document.getElementById('tbl_sm_profit').innerHTML = build(sm.profit);

  // 龙卷风
  const sf = H.sensitivity.single.filter(s => s.effect.some(e => Math.abs(e.d_profit) > 0.5));
  sf.sort((a, b) => Math.abs(b.effect[4].d_profit) - Math.abs(a.effect[4].d_profit));
  const names = sf.map(s => s.name.replace(/\(.*?\)/g, '').trim());
  ec('ch_tornado', {
    tooltip: Object.assign({ trigger: 'axis', axisPointer: { type: 'shadow' } }, TT),
    legend: { data: ['+10%', '+5%', '-5%', '-10%'], textStyle: { color: '#9fb0c8', fontSize: 11 } },
    grid: { left: 118, right: 22, top: 34, bottom: 26 },
    xAxis: Object.assign({ type: 'value', name: '利润变化 元/吨' }, AX),
    yAxis: Object.assign({ type: 'category', data: names }, { axisLine: AX.axisLine, axisLabel: AX.axisLabel }),
    series: [
      { name: '+10%', type: 'bar', data: sf.map(s => s.effect[4].d_profit), itemStyle: { color: '#f43f5e' }, barGap: '10%' },
      { name: '+5%', type: 'bar', data: sf.map(s => s.effect[3].d_profit), itemStyle: { color: '#fb7185' } },
      { name: '-5%', type: 'bar', data: sf.map(s => s.effect[1].d_profit), itemStyle: { color: '#86efac' } },
      { name: '-10%', type: 'bar', data: sf.map(s => s.effect[0].d_profit), itemStyle: { color: '#22c55e' } }
    ]
  });

  // 盈亏平衡价 = 使"理论制造利润=0"的产品售价 = 当期"总制成成本"
  const caShock = [-0.1, -0.05, 0, 0.05, 0.1];
  const be = caShock.map(s => {
    const r = compute(null, { cac2: s });
    return +r.totalCost.toFixed(0);
  });
  ec('ch_be', {
    tooltip: Object.assign({ trigger: 'axis' }, TT),
    grid: { left: 66, right: 20, top: 26, bottom: 40 },
    xAxis: Object.assign({ type: 'category', data: caShock.map(s => (s > 0 ? '+' : '') + (s * 100).toFixed(0) + '%'), name: '电石价格变动' }, AX),
    yAxis: Object.assign({ type: 'value', name: 'PVC 售价 元/吨' }, AX),
    series: [{
      type: 'line', data: be, smooth: true, symbolSize: 9,
      lineStyle: { color: '#a78bfa', width: 2.5 }, itemStyle: { color: '#a78bfa' },
      label: { show: true, position: 'top', color: '#c4b5fd', fontSize: 11, formatter: p => fmt(p.value) },
      areaStyle: { color: 'rgba(167,139,250,.14)' }
    }]
  });
}

/* ======================= 工艺对比 ======================= */
// 每条路线给出"每吨 PVC 的原料/能源分项"，全部可追溯到单耗 × 单价，不混用口径
function routeCosts() {
  const r = compute();
  const g = id => (P.inputs.find(x => x.id === id) || { cons: 0, price: 0 });
  return [
    {
      name: '电石乙炔法（外购电石）',
      idx: '原料成本 + 加工价差',
      cons: `电石 ${g('cac2').cons} t · HCl ${g('hcl').cons} t · 电 ${g('ele_pvc').cons} kWh · 汽 ${g('steam').cons} t`,
      parts: { 电石: r.cac2Cost, HCl: r.breakdown.find(b => b.id === 'hcl').cost, 能源: r.energy, 制造: r.mfg },
      note: '隆众周报样本主体。不含自产电石电耗、不含联产烧碱收益；氯由配套氯碱平衡供应。',
      total: r.raw + r.energy + r.aux + r.mfg
    },
    {
      name: '电石乙炔法（电力自给一体化）',
      idx: '电石内部成本 + 加工费',
      cons: '自产电石：综合电耗 ≈3400–3600 kWh/t 电石 × 1.45 t/t',
      parts: {
        电石: 4930 * 0.42, HCl: r.breakdown.find(b => b.id === 'hcl').cost,
        能源: r.energy, 制造: r.mfg
      },
      note: '成本优势来自煤电一体化而非电石本身；电力自给率与电价是核心变量，“以碱补氯”维持开工。',
      total: 4930 * 0.42 + r.breakdown.find(b => b.id === 'hcl').cost + r.energy + r.mfg
    },
    {
      name: '乙烯氧氯化法（对照）',
      idx: '乙烯 + 氯 + 加工费',
      cons: '乙烯 0.5 t · 氯 0.6 t · VCM 1.002 t',
      parts: { 乙烯: 0.5 * 7800, 氯: 0.6 * 1400, 能源: 275, 制造: r.mfg },
      note: '乙烯价格取 2026 上半年 CFR 高位区间（隆众）；华东乙烯法成本高于电石法 1200 元/吨以上。',
      total: 0.5 * 7800 + 0.6 * 1400 + 275 + r.mfg
    }
  ];
}
function renderRoute() {
  const routes = routeCosts();
  const baseTot = routes[0].total;
  let h = `<thead><tr><th>路线</th><th>适用成本指标</th><th>主要单耗</th><th>原料+能源+制造</th><th>相对电石法</th><th>口径要点</th></tr></thead><tbody>`;
  routes.forEach(rt => {
    h += `<tr><td style="text-align:left;font-weight:600">${rt.name}</td>
      <td style="text-align:left" class="mut">${rt.idx}</td>
      <td style="text-align:left;white-space:normal;font-size:11px" class="mut">${rt.cons}</td>
      <td class="mono" style="font-weight:600">${fmt(rt.total)}</td>
      <td class="mono ${rt.total > baseTot ? 'up' : 'down'}">${rt.name.indexOf('外购') >= 0 ? '基准' : (rt.total - baseTot >= 0 ? '+' : '') + fmt(rt.total - baseTot)}</td>
      <td style="text-align:left;white-space:normal;font-size:10.5px" class="mut">${rt.note}</td></tr>`;
  });
  document.getElementById('tbl_route').innerHTML = h + '</tbody>';

  const keys = ['电石', 'HCl', '乙烯', '氯', '能源', '制造'];
  const COL = { 电石: '#f59e0b', HCl: '#a78bfa', 乙烯: '#f43f5e', 氯: '#8b5cf6', 能源: '#4cc9f0', 制造: '#64748b' };
  ec('ch_route', {
    tooltip: Object.assign({ trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: ps => ps[0].axisValue + '<br/>' + ps.map(p => `${p.marker}${p.seriesName}：<b>${fmt(p.value, 0)}</b>`).join('<br/>') +
        `<br/><b>合计：${fmt(ps.reduce((a, b) => a + b.value, 0), 0)}</b> 元/吨` }, TT),
    legend: { textStyle: { color: '#9fb0c8', fontSize: 11 } },
    grid: { left: 148, right: 24, top: 44, bottom: 30 },
    xAxis: Object.assign({ type: 'value', name: '元/吨' }, AX),
    yAxis: Object.assign({ type: 'category', data: routes.map(x => x.name) },
      { axisLine: AX.axisLine, axisLabel: { color: '#8fa3bd', fontSize: 10.5, width: 140, overflow: 'break' } }),
    series: keys.map(k => ({
      name: k, type: 'bar', stack: 's',
      data: routes.map(rt => +(rt.parts[k] || 0).toFixed(0)),
      itemStyle: { color: COL[k] },
      label: { show: false }
    }))
  });

  const r = compute();
  const tot = r.raw + r.energy + r.aux + r.mfg;
  document.getElementById('routeNotes').innerHTML = `
    <div class="note info"><b>1. 先分清“谁的成本”：</b>电石法企业的成本曲线取决于<b>电石采购半径</b>——乌海/内蒙古与山东的到厂价差可达 400–600 元/吨，
      所以“全国均价”算出来的利润，对单个企业几乎没有指导意义。</div>
    <div class="note"><b>2. 电石占总成本 ${tot ? (r.cac2Cost / tot * 100).toFixed(1) : '—'}%：</b>行业统计为 65–75%，与本模型一致。
      电石每涨 100 元/吨，PVC 成本上升约 ${(1.45 * 100).toFixed(0)} 元/吨（除以收率后约 ${(1.45 * 100 / r.y).toFixed(0)}）。</div>
    <div class="note info"><b>3. 一体化≠低成本：</b>自产电石需承担约 ${(3400 * 1.45).toFixed(0)}–${(3600 * 1.45).toFixed(0)} kWh/吨 PVC 的电力，
      电价每上涨 0.05 元/度，成本增加约 ${(3500 * 1.45 * 0.05).toFixed(0)} 元/吨。西北企业靠低电价，而非电石本身便宜。</div>
    <div class="note bad"><b>4. 不要横比“毛利”：</b>电石法看“加工价差 + 区域价差”，乙烯法看“乙烯−PVC 价差”，
      两者原料篮子完全不同，用同一个“行业利润”口径比较会得出错误结论。</div>`;
}

/* ======================= 数据口径 ======================= */
function renderData() {
  const src = [
    ['PVC 现货（SG-5）', '生意社基准价', '中国·综合（基准规格）', '元/吨·含税', '日', '2026-07-20 → 2026-10-20', '近 93 天（免费源上限）'],
    ['电石', '生意社基准价', '宁夏/内蒙古（出厂折算）', '元/吨·含税', '日', '2026-07-20 → 2026-10-19', '近 93 天'],
    ['液碱 32%', '生意社基准价', '华东', '元/吨·含税', '日', '2026-07-20 → 2026-10-19', '近 93 天'],
    ['PVC 期货', '新浪财经 主力连续 V0', '大连商品交易所', '元/吨·含税', '日', '2025-10-20 → 2026-10-19', '242 个交易日'],
    ['电石（早于 93 天）', '文章披露锚点 + 线性插值', '乌海主流贸易价', '元/吨', '月/事件', '2026-01-01 → 2026-09-15', '6 个锚点'],
    ['第三方成本/毛利', '隆众资讯 周报', '全国 / 西北 / 山东', '元/吨', '周', '2026-01-09 → 2026-10-16', '40 期'],
    ['工艺单耗', '国标口径 + 隆众 + 前瞻 + 专利', '电石法', 't/t, kWh/t', '静态', '2022–2026', '多源交叉']
  ];
  let h = `<thead><tr><th>序列</th><th>来源</th><th>地区/规格</th><th>单位·税费</th><th>频率</th><th>区间</th><th>样本量</th></tr></thead><tbody>`;
  src.forEach(r => h += `<tr><td style="text-align:left;font-weight:600">${r[0]}</td><td style="text-align:left" class="mut">${r[1]}</td><td style="text-align:left" class="mut">${r[2]}</td><td style="text-align:left" class="mut">${r[3]}</td><td class="mut">${r[4]}</td><td class="mut" style="font-size:11px">${r[5]}</td><td class="mut">${r[6]}</td></tr>`);
  document.getElementById('tbl_sources').innerHTML = h + '</tbody>';

  let a = `<thead><tr><th>日期</th><th>乌海电石</th><th>原文表述</th><th>来源</th></tr></thead><tbody>`;
  ANCH.forEach(x => a += `<tr><td class="mono">${x.date}</td><td class="mono" style="font-weight:600;color:#fcd34d">${fmt(x.price)}</td>
    <td style="text-align:left;white-space:normal" class="mut">${x.quote}</td>
    <td style="text-align:left;white-space:normal;font-size:10.5px"><a href="${(x.source.match(/https?:\/\/\S+/) || [''])[0]}" target="_blank">${x.source.split(' ').slice(0, 2).join(' ')}</a></td></tr>`);
  document.getElementById('tbl_anchors').innerHTML = a + '</tbody>';

  const ku = H.week_validation.agg, v = H.validation;
  document.getElementById('val_ok').innerHTML = [
    `电石占总成本 ${compute().shareRaw ? (compute().cac2Cost / (compute().raw + compute().energy + compute().aux + compute().mfg) * 100).toFixed(1) : '—'}%（行业 65–75%）`,
    `40 周周度对比：方向一致 ${ku.sign_agree}/${ku.n_weeks} 周（${(ku.sign_agree / ku.n_weeks * 100).toFixed(0)}%）`,
    `周度偏差均值 ${ku.mean_diff.toFixed(0)} 元/吨，平均绝对偏差 ${ku.mean_abs_diff.toFixed(0)}`,
    `月度对比 ${v.n} 个月，同号 ${v.sign_agree} 个`,
    '收率、单位（kg/t）换算为显式公式，可逐项复核'
  ].map(x => `<li>${x}</li>`).join('');

  document.getElementById('val_lim').innerHTML = [
    '电石日价仅近 93 天：更早区间依赖锚点插值，标注为 interp',
    'PVC 现货早于 93 天用“期货主力 + 平均基差(-120)”代理，非现货实价',
    '能源价格（电价/汽价）取截面值，未随时间变动',
    '触媒、助剂单价为量级估计，可核实性低（已标 est）',
    '区域价差（乌海 vs 山东 400–600 元/吨）未在单一模型内体现'
  ].map(x => `<li>${x}</li>`).join('');

  document.getElementById('val_no').innerHTML = [
    '不把加工价差称为企业净利润',
    '不在缺价区间凭空外推价格',
    '不混用一体化与外购电石的单耗',
    '不把不同来源的单耗拼进同一口径',
    '不给出无来源的“企业实际盈利”数字'
  ].map(x => `<li>${x}</li>`).join('');
}

/* ======================= 总渲染 ======================= */
function renderAll(rebuildInputs) {
  renderKpis();
  if (rebuildInputs !== false) renderInputs();
  renderResults();
  renderCharts();
  renderBreakdown();
  renderExcluded();
}
function renderView(v) {
  if (v === 'history') renderHistory();
  else if (v === 'cost') renderCostView();
  else if (v === 'sens') renderSens();
  else if (v === 'route') renderRoute();
  else if (v === 'data') renderData();
}

/* ---------------- 事件绑定 ---------------- */
document.getElementById('in_prod').value = D.cross.pvc_spot_ppi;
document.getElementById('in_prod_date').value = D.cross.date;
document.getElementById('in_yield').value = P.yield;
document.getElementById('in_vat').value = 0.13;
document.getElementById('t_mfg').checked = true;
document.getElementById('t_byp').checked = false;

document.getElementById('in_prod').oninput = e => { P.product.price = parseFloat(e.target.value) || 0; renderAll(false); };
document.getElementById('in_yield').oninput = e => { P.yield = clamp(parseFloat(e.target.value) || 0.97, 0.5, 1); renderAll(false); };
document.getElementById('t_mfg').onchange = e => { P.manufacturing.enabled = e.target.checked; renderAll(false); };
document.getElementById('t_byp').onchange = e => { P.byproduct.enabled = e.target.checked; renderAll(); };
document.getElementById('btnReset').onclick = () => { P = JSON.parse(JSON.stringify(DEF)); P.manufacturing.enabled = true; P.byproduct.enabled = false; document.getElementById('in_prod').value = DEF.product.price; document.getElementById('in_yield').value = DEF.yield; document.getElementById('t_byp').checked = false; renderInputs(); renderAll(false); };
document.querySelectorAll('[data-preset]').forEach(b => b.onclick = () => {
  P.product.price = b.dataset.preset === 'spot' ? D.cross.pvc_spot_ppi : Math.round(D.series[D.series.length - 1].fut_close);
  document.getElementById('in_prod').value = P.product.price; renderAll(false);
});
document.getElementById('btnExport').onclick = () => {
  const blob = new Blob([JSON.stringify({ product: P.product, yield: P.yield, inputs: P.inputs, manufacturing: P.manufacturing, byproduct: P.byproduct, result: compute() }, null, 2)], { type: 'application/json' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'pvc-cost-params.json'; a.click();
};

renderAll(true);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
</script>
