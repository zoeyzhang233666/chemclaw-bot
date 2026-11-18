/* chem-cost-model dashboard app
 * 公式与 scripts/cost_engine.py 一一对应（改公式必须两边同时改）：
 *   c_i = q_i * p_i
 *   C   = Σ c_i
 *   w_i = c_i / C
 *   Δc_i(r) = q_i * p_i * r
 *   C'(r_1..r_n) = Σ q_i * p_i * (1 + r_i)
 *   C_t = Σ q_i * p_i(t)
 */
(function () {
  'use strict';
  const RAW = window.__DATA__;
  const D = JSON.parse(JSON.stringify(RAW));      // 可变的运行态
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.prototype.slice.call((r || document).querySelectorAll(s));

  // ------------------------------------------------------------------ 工具
  const nf = (v, d) => (v === null || v === undefined || isNaN(v)) ? '—'
    : Number(v).toLocaleString('zh-CN', { minimumFractionDigits: d === undefined ? 2 : d, maximumFractionDigits: d === undefined ? 2 : d });
  const pct = (v, d) => (v === null || v === undefined || isNaN(v)) ? '—' : (v * 1).toFixed(d === undefined ? 1 : d) + '%';
  const sgn = v => (v > 0 ? '+' : '');
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const PALETTE = ['#2f6db3', '#e07a3f', '#2f9e6e', '#9b59b6', '#c9567a', '#3aa6b9', '#b0943a', '#6b7b8f'];

  const state = {
    q: {},            // id -> 单耗 t/t
    p: {},            // id -> 价格 元/t（当前口径）
    rates: [],        // [{label, ratio}]
    taxBasis: (D.price_basis && D.price_basis.target) || 'tax_included',
    proc: (D.meta && D.meta.process_id) || 'default',
    histQ: null,      // id -> 单耗（历史用的固定单耗）
    dirty: {},
  };

  function initState(from) {
    const S = from || D;
    state.q = {}; state.p = {}; state.dirty = {};
    (S.materials || []).forEach(m => {
      state.q[m.id] = (m.dosage !== null && m.dosage !== undefined) ? m.dosage : null;
      state.p[m.id] = (m.price !== null && m.price !== undefined) ? m.price : null;
    });
    state.rates = (S.rates || []).map(r => ({ label: r.label, ratio: r.ratio }));
    state.taxBasis = (S.price_basis && S.price_basis.target) || 'tax_included';
    state.proc = (S.meta && S.meta.process_id) || 'default';
    // 历史固定单耗：以"原始"值为基准（历史序列建在原始单耗上）
    state.histQ = {};
    (RAW.materials || []).forEach(m => { state.histQ[m.id] = m.dosage; });
  }

  // ------------------------------------------------------------------ 重算
  function compute() {
    const mats = (D.materials || []).map(m => {
      const q = state.q[m.id], p = state.p[m.id];
      const hasQ = (q !== null && q !== undefined && q !== '' && !isNaN(+q));
      const hasP = (p !== null && p !== undefined && p !== '' && !isNaN(+p));
      return Object.assign({}, m, {
        q: hasQ ? +q : null, p: hasP ? +p : null,
        cost: (hasQ && hasP) ? (+q) * (+p) : null,
        price_missing: !hasP, dosage_missing: !hasQ
      });
    });
    const comp = mats.filter(m => m.cost !== null);
    const total = comp.reduce((s, m) => s + m.cost, 0);
    comp.forEach(m => { m.share = total ? m.cost / total * 100 : null; });
    const main = comp.filter(m => m.role !== 'aux');
    const aux = comp.filter(m => m.role === 'aux');

    // 敏感性
    const sens = comp.map(m => ({
      id: m.id, name: m.name, q: m.q, p: m.p, cost: m.cost, share: m.share,
      cells: state.rates.map(r => {
        const dc = m.q * m.p * r.ratio;
        return { label: r.label, ratio: r.ratio, dc: dc, newCost: m.cost + dc,
          newTotal: total + dc, dp: m.p * r.ratio };
      })
    }));
    // 单原料新成本（含基准列）
    const single = comp.map(m => ({
      id: m.id, name: m.name,
      newCosts: [m.cost].concat(state.rates.map(r => m.cost * (1 + r.ratio)))
    }));

    // 组合情景：从输入读
    const combos = (D.combos || []).map(c => {
      let neu = 0; const by = [];
      comp.forEach(m => {
        const rr = (c.changes && c.changes[m.id] !== undefined ? +c.changes[m.id] : 0) / 100;
        neu += m.q * m.p * (1 + rr);
        by.push({ id: m.id, name: m.name, ratio: rr * 100, old: m.cost, neu: m.cost * (1 + rr), d: m.cost * rr });
      });
      return { id: c.id, name: c.name, changes: c.changes || {}, old: total, neu: neu,
        d: neu - total, pct: total ? (neu - total) / total * 100 : null, by: by };
    });

    // 全部同步
    const sync = state.rates.map(r => {
      const neu = comp.reduce((s, m) => s + m.cost * (1 + r.ratio), 0);
      return { label: r.label, ratio: r.ratio, d: neu - total, pct: total ? (neu - total) / total * 100 : null };
    });

    return { mats, comp, total, main, aux, sens, single, combos, sync,
      mainTotal: main.reduce((s, m) => s + m.cost, 0),
      auxTotal: aux.reduce((s, m) => s + m.cost, 0) };
  }

  // 历史成本：固定 (state.histQ) × 当天价格
  function histSeries() {
    const H = D.history || {};
    const hs = H.materials || [];
    const map = {};
    hs.forEach(h => { map[h.material_id] = {}; (h.rows || []).forEach(r => { map[h.material_id][r.date] = r.value; }); });
    const mats = (D.materials || []).filter(m => map[m.id]);
    const dates = (hs[0] && hs[0].rows) ? hs[0].rows.map(r => r.date) : [];
    const out = [];
    dates.forEach(dt => {
      const items = {}; let ok = true;
      mats.forEach(m => {
        const v = map[m.id][dt];
        const q = state.histQ[m.id];
        if (v === null || v === undefined || q === null || q === undefined) { ok = false; items[m.id] = null; }
        else items[m.id] = q * v;
      });
      out.push({ date: dt, items: items, cost: ok && mats.length ? Object.values(items).reduce((a, b) => a + b, 0) : null, ok: ok });
    });
    return { rows: out, mats: mats, ref: (H.reference_series || [])[0] || null };
  }

  function daysBetween(a, b) { return Math.round((new Date(b) - new Date(a)) / 86400000); }

  function windowStats(rows) {
    const val = rows.filter(r => r.cost !== null);
    const out = [];
    [['30天', 30], ['3个月', 91], ['1年', 365], ['3年', 1095]].forEach(([lab, n]) => {
      if (!val.length) { out.push({ lab, status: 'gap', why: '无历史数据' }); return; }
      const end = val[val.length - 1];
      const endD = new Date(end.date);
      const startTarget = new Date(endD.getTime() - n * 86400000);
      let st = null;
      for (let i = val.length - 1; i >= 0; i--) {
        if (new Date(val[i].date) <= startTarget) { st = val[i]; break; }
      }
      if (!st) {
        out.push({ lab, status: 'gap', end: end, why: '起点早于可得数据（' + val[0].date + ' 起），未插值' });
      } else {
        out.push({ lab, status: 'ok', start: st, end: end, d: end.cost - st.cost,
          pct: st.cost ? (end.cost - st.cost) / st.cost * 100 : null,
          contrib: Object.keys(end.items).map(id => ({ id: id, d: end.items[id] - st.items[id] })) });
      }
    });
    return out;
  }

  // ------------------------------------------------------------------ 渲染：头部
  function renderHeader() {
    const M = D.meta || {};
    $('#hTitle').textContent = (M.product || '') + ' · 理论原料成本分析';
    $('#hSub').innerHTML = (M.process_name ? '<b style="color:#dce9f7">' + esc(M.process_name) + '</b> · ' : '') +
      '数据截止 <b style="color:#dce9f7">' + esc(M.as_of || '') + '</b> · ' +
      (M.formula_prod || '') + ' · 价格口径：' + (state.taxBasis === 'tax_included' ? '含税' : '不含税') +
      ' · 单位：元/吨产品';
    const bc = $('#hBadges'); bc.innerHTML = '';
    const R = compute();
    bc.innerHTML += '<span class="badge ok">已计价 ' + R.comp.length + '/' + R.mats.length + ' 条原料</span>';
    if (R.comp.length < R.mats.length) bc.innerHTML += '<span class="badge warn">' + (R.mats.length - R.comp.length) + ' 条原料缺价格（未计入，不是 0）</span>';
    const gp = (D.periods || []).filter(p => p.status === 'gap').map(p => p.label);
    if (gp.length) bc.innerHTML += '<span class="badge warn">' + gp.join(' / ') + ' 历史缺口</span>';
    bc.innerHTML += '<span class="badge">理论原料成本 ≠ 生产成本 ≠ 利润</span>';
    $('#fAsof').textContent = M.as_of || '';
  }

  // ------------------------------------------------------------------ 渲染：KPI
  function renderKPI() {
    const R = compute();
    const W = windowStats(histSeries().rows);
    const w30 = W[0], w3 = W[1];
    const biggest = R.sens.slice().sort((a, b) => b.cost - a.cost)[0];
    const deltaHtml = (w) => {
      if (!w || w.status !== 'ok') return '<span style="opacity:.75">历史窗口缺口</span>';
      const cls = w.d > 0 ? 'delta-up' : (w.d < 0 ? 'delta-down' : '');
      return '近' + w.lab + ' <b class="' + cls + '">' + sgn(w.d) + nf(w.d, 0) + '</b> 元 (' + sgn(w.pct) + pct(w.pct) + ')';
    };
    const el = $('#kpis');
    el.innerHTML = `
      <div class="kpi hero">
        <div class="lab">单位产品理论原料成本 <span class="tick">C = Σ q×p</span></div>
        <div class="val">${nf(R.total, 0)}<span class="unit">元 / 吨 ${esc((D.meta||{}).product_short || '产品')}</span></div>
        <div class="foot">${deltaHtml(w3 || w30)}</div>
      </div>
      <div class="kpi">
        <div class="lab">主料成本合计</div>
        <div class="val num">${nf(R.mainTotal, 0)}<span class="unit">元/吨</span></div>
        <div class="foot">占已计价总额 ${R.total ? nf(R.mainTotal / R.total * 100, 1) : '—'}%${R.auxTotal ? ' ｜ 辅料 ' + nf(R.auxTotal, 0) + ' 元' : ''}</div>
      </div>
      <div class="kpi">
        <div class="lab">成本占比最高</div>
        <div class="val" style="font-size:22px">${esc(biggest ? biggest.name.split('（')[0] : '—')}</div>
        <div class="foot">${biggest ? nf(biggest.share, 1) + '% ｜ ' + nf(biggest.cost, 0) + ' 元/吨' : '—'}</div>
      </div>
      <div class="kpi">
        <div class="lab">最近 30 天走势</div>
        <div class="val" style="font-size:26px;color:${w30 && w30.status === 'ok' ? (w30.d > 0 ? 'var(--up)' : 'var(--down)') : 'var(--ink3)'}">
          ${w30 && w30.status === 'ok' ? sgn(w30.d) + nf(w30.d, 0) : '缺口'}</div>
        <div class="foot">${w30 && w30.status === 'ok' ? '元/吨 (' + sgn(w30.pct) + nf(w30.pct, 2) + '%)' : (w30 ? w30.why : '')}</div>
      </div>`;
    // 图例
    const cs = $('#chipset'); cs.innerHTML = '';
    R.comp.forEach((m, i) => {
      cs.innerHTML += `<span class="chip"><i class="dot" style="background:${PALETTE[i % PALETTE.length]}"></i>${esc(m.name.split('（')[0])} ${nf(m.share, 1)}%</span>`;
    });
  }

  // ------------------------------------------------------------------ 渲染：控制台
  function renderControls() {
    // 工艺 tabs
    const tabs = D.process_alternatives || [];
    const tb = $('#tabs'); tb.innerHTML = '';
    if (tabs.length) {
      tabs.forEach(t => {
        const on = t.id === state.proc ? ' on' : '';
        tb.innerHTML += `<button class="tab${on}" data-pid="${t.id}">${esc(t.name)}<small>${esc(t.short || '')}</small></button>`;
      });
      $$('.tab', tb).forEach(b => b.onclick = () => switchProcess(b.dataset.pid));
    } else {
      tb.innerHTML = '<div style="font-size:12px;color:var(--ink3)">本模型为单一工艺口径：' + esc((D.meta || {}).process_name || '') + '</div>';
    }

    // 原料编辑器
    const me = $('#mateditor'); me.innerHTML = '';
    (D.materials || []).forEach(m => {
      const srcLabel = m.dosage_source_label || '';
      const sim = m.dosage_source === 'simulated' ? ' sim' : '';
      me.innerHTML += `<div class="matbox">
        <div class="mt">${esc(m.name)}<span class="tagd${sim}">${esc(srcLabel)}</span>${m.role === 'aux' ? '<span class="tagd">辅料</span>' : ''}</div>
        <div class="row"><label>单耗 t/t</label><input type="number" step="0.0001" min="0" data-id="${m.id}" data-k="q" value="${state.q[m.id] === null ? '' : state.q[m.id]}"></div>
        <div class="row"><label>价格 元/t</label><input type="number" step="0.01" min="0" data-id="${m.id}" data-k="p" value="${state.p[m.id] === null || state.p[m.id] === undefined ? '' : (+state.p[m.id]).toFixed(2)}" ${m.price_missing ? 'placeholder="缺价格"' : ''}></div>
      </div>`;
    });
    $$('#mateditor input').forEach(inp => {
      inp.onchange = () => {
        const id = inp.dataset.id, k = inp.dataset.k;
        const v = inp.value === '' ? null : +inp.value;
        if (v !== null && (isNaN(v) || v < 0)) { toast('请输入非负数'); return; }
        if (k === 'q') state.q[id] = v; else state.p[id] = v;
        state.dirty[id + k] = true; inp.classList.add('dirty');
        renderAll();
      };
    });

    // 幅度
    const rr = $('#ratesRow'); rr.innerHTML = '';
    state.rates.forEach((r, i) => {
      rr.innerHTML += `<div style="flex:1"><input type="number" step="0.5" data-ri="${i}" value="${(r.ratio * 100).toFixed(2)}" title="${r.label}"></div>`;
    });
    $$('#ratesRow input').forEach(inp => {
      inp.onchange = () => {
        const v = +inp.value;
        if (isNaN(v)) { toast('幅度需为数字'); return; }
        state.rates[+inp.dataset.ri].ratio = v / 100;
        renderAll();
      };
    });
    const st = $('#selTax');
    st.value = state.taxBasis;
    st.onchange = () => { toast('切换税口径需要按税率换算所有价格——请先确认税率，本页不擅自换算'); st.value = state.taxBasis; };
  }

  function switchProcess(pid) {
    const t = (D.process_alternatives || []).find(x => x.id === pid);
    if (!t) return;
    state.proc = pid;
    // 套用该工艺对应的单耗
    Object.keys(t.dosage || {}).forEach(id => { if (state.q[id] !== undefined) state.q[id] = t.dosage[id]; });
    toast('已切换到：' + t.name + '（单耗已按该工艺套用）');
    renderAll();
  }

  // ------------------------------------------------------------------ 渲染：成本构成
  function renderComp() {
    const R = compute();
    const tb = $('#tblComp tbody'); tb.innerHTML = '';
    R.mats.forEach((m, i) => {
      const cls = m.cost === null ? '' : '';
      const srcPill = `<span class="pill ${m.dosage_source === 'simulated' ? 'simulated' : (m.dosage_source || 'none')}">${esc(m.dosage_source_label || '无来源')}</span>`;
      if (m.cost === null) {
        tb.innerHTML += `<tr class="${cls}"><td class="nm">${esc(m.name)}</td>
          <td>${m.q === null ? '<span class="gapcell">缺单耗</span>' : nf(m.q, 4)}</td>
          <td>${m.p === null ? '<span class="gapcell">缺价格</span>' : nf(m.p, 2)}</td>
          <td><span class="gapcell">未计入</span></td><td>—</td><td>${srcPill}</td></tr>`;
      } else {        tb.innerHTML += `<tr data-id="${m.id}"><td class="nm"><span class="linky" data-open="${m.id}">${esc(m.name)}</span></td>
          <td class="num">${nf(m.q, 4)}</td><td class="num">${nf(m.p, 2)}</td>
          <td class="num"><b>${nf(m.cost, 2)}</b></td>
          <td class="num"><span class="bar"><i style="width:${clamp(m.share, 0, 100)}%;background:${PALETTE[i % PALETTE.length]}"></i></span> ${nf(m.share, 2)}%</td>
          <td>${srcPill}</td></tr>`;
      }
    });
    $('#tblComp tfoot').innerHTML = `<tr><td>合计（有价格部分）</td><td class="num">${nf(R.comp.reduce((s, m) => s + m.q, 0), 4)}</td>
      <td>—</td><td class="num">${nf(R.total, 2)}</td><td class="num">${R.total ? '100.00%' : '—'}</td><td></td></tr>`;
    $('#compHint').textContent = '理论原料成本，不含加工费';
    const missing = R.mats.filter(m => m.cost === null);
    $('#compNote').innerHTML = missing.length
      ? '尚未计价：' + missing.map(m => esc(m.name.split('（')[0])).join('、') + '（缺价格，未按 0 计入）。合计口径为"部分覆盖"。'
      : '所有原料均已计价，成本覆盖完整（仍不含能源/人工/折旧等）。';
    $$('#tblComp .linky').forEach(a => a.onclick = () => openDrawer(a.dataset.open));
    drawPie(R);
  }

  // ------------------------------------------------------------------ 渲染：历史
  function renderHist() {
    const H = histSeries();
    const W = windowStats(H.rows);
    const wc = $('#winCards'); wc.innerHTML = '';
    W.forEach(w => {
      if (w.status === 'ok') {
        wc.innerHTML += `<div class="winc"><div class="l"><span>近${w.lab}</span><span>${w.start.date}→${w.end.date}</span></div>
          <div class="v ${w.d > 0 ? 'delta-up' : 'delta-down'}">${sgn(w.d)}${nf(w.d, 0)}</div>
          <div class="d">成本 ${nf(w.start.cost, 0)} → ${nf(w.end.cost, 0)} ｜ ${sgn(w.pct)}${nf(w.pct, 2)}%</div></div>`;
      } else {
        wc.innerHTML += `<div class="winc gap"><div class="l"><span>近${w.lab}</span><span>缺口</span></div>
          <div class="v">无法计算</div><div class="d">${esc(w.why || '')}</div></div>`;
      }
    });
    const H0 = H.rows.find(r => r.cost !== null);
    const hl = H.rows.filter(r => r.cost !== null).length;
    $('#histHint').textContent = H.rows.length ? (H.rows[0].date + ' ~ ' + H.rows[H.rows.length - 1].date + '（' + H.rows.length + ' 天，' + hl + ' 天可算）') : '';
    $('#histNote').innerHTML = '口径：固定净单耗 × 同日真实基准价（含税、元/吨）。周末/节假日为平台承袭值，仅作展示，不做统计。'
      + ' 缺失月份未插值、未生成。';
    drawHist(H);
  }

  // ------------------------------------------------------------------ 渲染：热力图
  function renderHeat() {
    const R = compute();
    let h = '<thead><tr><th>原料</th><th>基准成本</th>' + state.rates.map(r => '<th>' + esc(r.label) + '</th>').join('') + '</tr></thead><tbody>';
    const allv = [];
    R.sens.forEach(s => s.cells.forEach(c => allv.push(c.dc)));
    const mx = Math.max.apply(null, allv.map(Math.abs).concat([1]));
    const col = v => {
      const t = clamp(v / mx, -1, 1);
      if (t >= 0) { const a = .10 + .55 * t; return 'rgba(192,57,43,' + a.toFixed(3) + ')'; }
      const a = .10 + .55 * (-t); return 'rgba(31,122,77,' + a.toFixed(3) + ')';
    };
    R.sens.forEach(s => {
      h += `<tr data-id="${s.id}"><td class="nm"><span class="linky" data-open="${s.id}">${esc(s.name.split('（')[0])}</span>
        <div style="font-size:11px;color:var(--ink3)">${nf(s.q, 4)} t/t × ${nf(s.p, 0)} 元/t</div></td>
        <td class="num">${nf(s.cost, 0)}</td>`;
      s.cells.forEach(c => {
        h += `<td class="num" style="background:${col(c.dc)};font-weight:600">${sgn(c.dc)}${nf(c.dc, 1)}</td>`;
      });
      h += '</tr>';
    });
    h += '</tbody><tfoot><tr><td>全部同步</td><td class="num">' + nf(R.total, 0) + '</td>' +
      R.sync.map(x => '<td class="num" style="background:' + col(x.d) + '">' + sgn(x.d) + nf(x.d, 0) + '</td>').join('') +
      '</tr></tfoot>';
    const t = $('#tblHeat'); t.innerHTML = h;
    $$('#tblHeat .linky').forEach(a => a.onclick = () => openDrawer(a.dataset.open));
    $$('#tblHeat tbody tr').forEach(tr => tr.onclick = (e) => { if (!e.target.classList.contains('linky')) openDrawer(tr.dataset.id); });
  }

  // ------------------------------------------------------------------ 渲染：贡献
  function renderContrib() {
    const H = histSeries();
    const W = windowStats(H.rows);
    const okW = W.filter(w => w.status === 'ok');
    if (!okW.length) { $('#contribText').textContent = '历史数据不足，无法计算贡献分解。'; drawContrib(null); return; }
    // 取最长的可用窗口做文字结论
    const w = okW[okW.length - 1];
    const items = w.contrib.slice().sort((a, b) => Math.abs(b.d) - Math.abs(a.d));
    const tot = w.d;
    const nm = id => ((D.materials.find(m => m.id === id) || {}).name || id).split('（')[0];
    let txt = `<b>近${w.lab}</b>（${w.start.date} → ${w.end.date}）：理论原料成本 ${sgn(tot)}${nf(tot, 0)} 元/吨`;
    if (Math.abs(tot) > 1) {
      txt += '，其中 ' + items.map(i => `${nm(i.id)} ${sgn(i.d)}${nf(i.d, 0)} 元（占变化 ${nf(i.d / tot * 100, 0)}%）`).join('；') + '。';
    } else {
      txt += '，各原料涨跌基本抵消，不给"谁贡献大"的比例（分母接近 0 时比例无意义）。';
    }
    $('#contribText').innerHTML = txt;
    drawContrib({ w: w, items: items, nm: nm });
  }

  // ------------------------------------------------------------------ 渲染：情景
  function renderScen() {
    const R = compute();
    const sc = $('#scenCards'); sc.innerHTML = '';
    R.sync.forEach(s => {
      const cls = s.d > 0 ? 'up' : (s.d < 0 ? 'down' : 'mid');
      sc.innerHTML += `<div class="sc ${cls}"><div class="n">全部原料同步 ${esc(s.label)}</div>
        <div class="v ${s.d > 0 ? 'delta-up' : 'delta-down'}">${sgn(s.d)}${nf(s.d, 0)}</div>
        <div class="u">元/吨产品 ｜ ${sgn(s.pct)}${nf(s.pct, 2)}%</div></div>`;
    });
    // 组合表
    const th = $('#tblCombo thead'), tb = $('#tblCombo tbody');
    th.innerHTML = '<tr><th>情景（右侧涨跌幅 % 可直接改）</th>' +
      R.comp.map(m => '<th>' + esc(m.name.split('（')[0]) + ' 涨跌%' + '</th>').join('') +
      '<th>基准 C</th><th>情景 C′</th><th>Δ成本</th><th>Δ%</th></tr>';
    tb.innerHTML = '';
    R.combos.forEach((c, ci) => {
      tb.innerHTML += `<tr><td class="nm"><b>${esc(c.name)}</b></td>` +
        R.comp.map(m => `<td><input type="number" step="1" style="width:62px;text-align:right" data-ci="${ci}" data-mid="${m.id}" value="${c.changes[m.id] === undefined ? 0 : (+c.changes[m.id]).toFixed(2)}"></td>`).join('') +
        `<td class="num">${nf(c.old, 0)}</td><td class="num"><b>${nf(c.neu, 0)}</b></td>
         <td class="num ${c.d > 0 ? 'delta-up' : 'delta-down'}">${sgn(c.d)}${nf(c.d, 0)}</td>
         <td class="num">${sgn(c.pct)}${nf(c.pct, 2)}%</td></tr>`;
    });
    $$('#tblCombo input').forEach(inp => {
      inp.onchange = () => {
        const ci = +inp.dataset.ci, mid = inp.dataset.mid, v = +inp.value;
        if (isNaN(v)) { toast('请输入数字'); return; }
        D.combos[ci].changes[mid] = v;
        renderScen();
      };
    });
  }

  // ------------------------------------------------------------------ 渲染：近期变化
  function renderRecent() {
    const H = histSeries();
    const box = $('#recentBox');
    const hs = (D.history || {}).materials || [];
    const rows = [];
    hs.forEach(h => {
      const r = h.rows || []; if (!r.length) return;
      const last = r[r.length - 1];
      const get = n => {
        const t = new Date(last.date).getTime() - n * 86400000;
        let v = null;
        for (let i = r.length - 1; i >= 0; i--) { if (new Date(r[i].date).getTime() <= t) { v = r[i]; break; } }
        return v;
      };
      const a = get(30), b = get(91);
      rows.push({ mid: h.material_id, name: h.name, last: last.value,
        d30: a ? last.value - a.value : null, p30: a ? (last.value - a.value) / a.value * 100 : null,
        d3: b ? last.value - b.value : null, p3: b ? (last.value - b.value) / b.value * 100 : null,
        src: h.source, spec: h.spec, region: h.region });
    });
    rows.sort((x, y) => Math.abs(y.p30 || 0) - Math.abs(x.p30 || 0));
    let h = `<table><thead><tr><th>原料</th><th>最新价</th><th>近30天</th><th>近3个月</th><th>对当前成本影响</th></tr></thead><tbody>`;
    rows.forEach(r => {
      const qNow = state.q[r.mid];
      const imp = (r.p30 !== null && qNow !== null && qNow !== undefined && qNow !== '') ? r.d30 * (+qNow) : null;   // q × Δp，与敏感性同一公式
      h += `<tr><td class="nm">${esc(r.name)}<div style="font-size:11px;color:var(--ink3)">${esc(r.spec || '')}｜${esc(r.region || '')}</div></td>
        <td class="num">${nf(r.last, 0)}</td>
        <td class="num ${r.d30 > 0 ? 'delta-up' : 'delta-down'}">${r.p30 === null ? '—' : sgn(r.p30) + nf(r.p30, 2) + '%'}</td>
        <td class="num ${r.d3 > 0 ? 'delta-up' : 'delta-down'}">${r.p3 === null ? '<span class="gapcell">缺口</span>' : sgn(r.p3) + nf(r.p3, 2) + '%'}</td>
        <td class="num">${imp === null ? '—' : sgn(imp) + nf(imp, 0) + ' 元/吨'}</td></tr>`;
    });
    h += '</tbody></table><div style="font-size:11.5px;color:var(--ink3);margin-top:8px">"对当前成本影响"= 该原料单耗 × 近30天实际价格变动金额（Δc = q × Δp），与敏感性矩阵同一公式，不是预测。</div>';
    box.innerHTML = h;
  }

  // ------------------------------------------------------------------ 渲染：价差
  function renderSpread() {
    const H = histSeries();
    const note = $('#spreadNote');
    if (!H.ref) { $('#chSpread').innerHTML = '<div style="padding:40px;color:var(--ink3);text-align:center">未提供产品价格序列</div>'; note.textContent = '未用估算值代替。'; return; }
    const pmap = {}; (H.ref.rows || []).forEach(r => { pmap[r.date] = r.value; });
    const dates = [], prod = [], cost = [], spread = [];
    H.rows.forEach(r => {
      const p = pmap[r.date];
      if (p === undefined || r.cost === null) return;
      dates.push(r.date); prod.push(p); cost.push(+r.cost.toFixed(2)); spread.push(+(p - r.cost).toFixed(2));
    });
    note.innerHTML = '产品价：' + esc(H.ref.spec || '') + ' · ' + esc(H.ref.region || '') + ' · ' + esc(H.ref.source || '') +
      '。价差 = 产品价 − 理论原料成本，<b>未扣能源/人工/折旧/运费</b>，所以不等于利润。';
    const ch = echarts.init($('#chSpread'));
    ch.setOption({
      grid: { left: 56, right: 56, top: 30, bottom: 46 },
      tooltip: { trigger: 'axis', valueFormatter: v => nf(v, 0) + ' 元' },
      legend: { top: 0, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 11 } },
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, hideOverlap: true } },
      yAxis: [{ type: 'value', scale: true, axisLabel: { fontSize: 10 } },
        { type: 'value', scale: true, axisLabel: { fontSize: 10 }, splitLine: { show: false } }],
      series: [
        { name: '产品现货价', type: 'line', data: prod, smooth: true, symbol: 'none', lineStyle: { width: 2, color: '#12365c' } },
        { name: '理论原料成本', type: 'line', data: cost, smooth: true, symbol: 'none', lineStyle: { width: 2, color: '#c0392b' } },
        { name: '价差(右轴)', type: 'bar', yAxisIndex: 1, data: spread, itemStyle: { color: 'rgba(47,109,179,.35)' } }
      ]
    });
    charts.push(ch);
  }

  // ------------------------------------------------------------------ 渲染：缺口
  function renderGaps() {
    const gl = $('#gapList'); gl.innerHTML = '';
    const tn = { price: '价格缺口', dosage: '单耗来源', history: '历史序列', history_window: '历史窗口' };
    (D.gaps || []).forEach(g => {
      gl.innerHTML += `<li><b>[${tn[g.type] || g.type}] ${esc(g.item)}</b><br>${esc(g.detail || '')}
        ${g.impact ? '<br><span style="color:var(--ink3)">影响：' + esc(g.impact) + '</span>' : ''}</li>`;
    });
    if (!(D.gaps || []).length) gl.innerHTML = '<li style="border-color:#a7d7b8">无缺口</li>';
    const nl = $('#niList'); nl.innerHTML = '';
    (D.not_included || []).forEach(x => {
      nl.innerHTML += `<div class="ni"><b>${esc(x.item)}</b><span>${esc(x.reason || '')}</span></div>`;
    });
  }

  // ------------------------------------------------------------------ 渲染：公式/来源
  function renderDocs() {
    const R = compute();
    let h = '';
    (D.formula_doc || []).forEach(f => {
      h += `<tr><td class="nm">${esc(f.name)}</td><td style="text-align:left;font-family:Consolas,monospace;font-size:12px">${esc(f.f)}</td>
        <td style="text-align:left;white-space:normal">${esc(f.v || '')}</td></tr>`;
    });
    // 追加两条"本例实测"
    h += `<tr><td class="nm">本例合计</td><td style="text-align:left;font-family:Consolas,monospace;font-size:12px">C = Σ q_i×p_i</td>
      <td style="text-align:left;white-space:normal">${R.comp.map(m => nf(m.q, 4) + '×' + nf(m.p, 2)).join(' + ')} = <b>${nf(R.total, 2)}</b> 元/吨</td></tr>`;
    $('#tblFormula tbody').innerHTML = h;

    let u = '';
    (D.materials || []).forEach(m => {
      const qs = (m.dosage_steps || []).map(s => esc(s.calc)).join('；') || '—';
      const ps = (m.price_steps || []).map(s => esc(s.calc)).join(' → ') || '—';
      u += `<tr><td class="nm">${esc(m.name)}</td><td style="text-align:left">${qs}</td>
        <td style="text-align:left;white-space:normal">${ps}</td><td style="text-align:left">${esc(m.price_tax_in || '—')} → ${esc(m.tax_label || '')}</td></tr>`;
    });
    $('#tblUnits tbody').innerHTML = u;

    let s = '';
    (D.data_sources || []).forEach(x => {
      s += `<tr><td>${esc(x.id || '')}</td><td style="text-align:left;white-space:normal">${esc(x.type || '')}</td>
        <td style="text-align:left;white-space:normal">${x.url ? '<a href="' + esc(x.url) + '" target="_blank" rel="noopener">' + esc(x.title) + '</a>' : esc(x.title || '')}</td>
        <td style="text-align:left;white-space:normal">${esc(x.used_for || '')}</td></tr>`;
    });
    $('#tblSrc tbody').innerHTML = s;
  }

  // ------------------------------------------------------------------ 抽屉
  function openDrawer(mid) {
    const m = (D.materials || []).find(x => x.id === mid); if (!m) return;
    $('#dTitle').textContent = m.name;
    const H = histSeries();
    const series = ((D.history || {}).materials || []).find(x => x.material_id === mid);
    const R = compute();
    const mc = R.mats.find(x => x.id === mid) || {};
    let body = `<dl class="kv">
      <dt>CAS</dt><dd>${esc(m.cas || '—')}</dd>
      <dt>单耗</dt><dd><b>${state.q[mid] === null ? '—' : nf(state.q[mid], 4)}</b> t/t 产品 <span class="pill ${m.dosage_source === 'simulated' ? 'simulated' : (m.dosage_source || 'none')}">${esc(m.dosage_source_label || '无来源')}</span></dd>
      <dt>单耗依据</dt><dd>${esc(m.dosage_ref || '—')}${m.dosage_scope ? '<br><span style="color:var(--ink3)">适用工艺：' + esc(m.dosage_scope) + '</span>' : ''}</dd>
      <dt>当前价格</dt><dd><b>${state.p[mid] === null ? '缺口' : nf(state.p[mid], 2) + ' 元/t（' + (state.taxBasis === 'tax_included' ? '含税' : '不含税') + '）'}</b></dd>
      <dt>规格 / 地区</dt><dd>${esc(m.price_spec || m.spec || '—')} ｜ ${esc(m.price_region || m.region || '—')}</dd>
      <dt>交货 / 日期</dt><dd>${esc(m.price_delivery || m.delivery || '—')} ｜ ${esc(m.price_date || '—')}</dd>
      <dt>价格来源</dt><dd>${esc(m.price_source || '—')}</dd>
      <dt>单项成本</dt><dd>${mc.cost === undefined || mc.cost === null ? '未计入（缺价格）' : '<b>' + nf(mc.cost, 2) + '</b> 元/吨 ，占比 <b>' + nf(mc.share, 2) + '%</b>'}</dd>
    </dl>`;
    if (m.price_steps && m.price_steps.length) {
      body += `<div class="sec-t">价格口径换算过程</div>`;
      m.price_steps.forEach(s => {
        body += `<div class="step"><b>${esc(s.label)}</b><div class="f">${esc(s.calc || '')} → ${nf(s.value, 2)} ${esc(s.unit || '')}</div></div>`;
      });
    }
    if (m.dosage_steps && m.dosage_steps.length) {
      body += `<div class="sec-t">单耗单位换算</div>`;
      m.dosage_steps.forEach(s => {
        body += `<div class="step"><b>${esc(s.label)}</b><div class="f">${esc(s.calc)} → ${nf(s.value, 6)} t/t</div></div>`;
      });
    }
    if (series) {
      body += `<div class="sec-t">历史价格（${esc(series.spec || '')}｜${esc(series.region || '')}｜${esc(series.source || '')}）</div>
        <div id="dChart" style="height:220px"></div>
        <div style="font-size:11.5px;color:var(--ink3);margin-top:6px">${esc(series.rows[0] ? series.rows[0].date : '')} ~ ${esc(series.rows[series.rows.length - 1] ? series.rows[series.rows.length - 1].date : '')}，
        共 ${(series.rows || []).length} 个日历日。${series.source_url ? '<a href="' + esc(series.source_url) + '" target="_blank">来源链接</a>' : ''}</div>`;
      // 该原料对总成本的贡献（历史窗口）
      const W = windowStats(H.rows).filter(w => w.status === 'ok');
      if (W.length) {
        const w = W[W.length - 1];
        const it = w.contrib.find(c => c.id === mid);
        if (it) body += `<div class="step" style="margin-top:10px"><b>近${w.lab}对总成本变化的贡献</b><div class="f">Δ = ${sgn(it.d)}${nf(it.d, 0)} 元/吨；占总变化 ${nf(it.d / w.d * 100, 0)}%</div></div>`;
      }
    } else {
      body += `<div class="sec-t">历史价格</div><div style="color:var(--gap);background:var(--gapbg);padding:10px;border-radius:8px">该原料未采集历史序列——缺口未用估算补齐。</div>`;
    }
    const sens = R.sens.find(x => x.id === mid);
    if (sens) {
      body += `<div class="sec-t">价格变动对该原料成本的影响</div><table><thead><tr><th>幅度</th><th>Δ价格</th><th>Δ成本</th><th>新单位总成本</th></tr></thead><tbody>` +
        sens.cells.map(c => `<tr><td>${esc(c.label)}</td><td class="num">${sgn(c.dp)}${nf(c.dp, 2)}</td>
          <td class="num ${c.dc > 0 ? 'delta-up' : 'delta-down'}">${sgn(c.dc)}${nf(c.dc, 2)}</td><td class="num">${nf(c.newTotal, 2)}</td></tr>`).join('') +
        '</tbody></table>';
    }
    $('#dBody').innerHTML = body;
    $('#drawer').classList.add('on'); $('#scrim').classList.add('on');
    if (series) {
      const rows = series.rows || [];
      const ch = echarts.init($('#dChart'));
      ch.setOption({
        grid: { left: 52, right: 12, top: 16, bottom: 30 },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: rows.map(r => r.date), axisLabel: { fontSize: 9, hideOverlap: true } },
        yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 9 } },
        series: [{ type: 'line', data: rows.map(r => r.value), smooth: true, symbol: 'none',
          lineStyle: { width: 2, color: '#2f6db3' }, areaStyle: { color: 'rgba(47,109,179,.10)' } }]
      });
      charts.push(ch);
    }
  }
  function closeDrawer() { $('#drawer').classList.remove('on'); $('#scrim').classList.remove('on'); }

  // ------------------------------------------------------------------ 图表
  const charts = [];
  function disposeCharts() { charts.forEach(c => { try { c.dispose(); } catch (e) {} }); charts.length = 0; }

  function drawPie(R) {
    const el = $('#chPie'); if (!el) return;
    const ch = echarts.init(el);
    charts.push(ch);
    const data = R.comp.map((m, i) => ({ name: m.name.split('（')[0], value: +m.cost.toFixed(2), itemStyle: { color: PALETTE[i % PALETTE.length] } }));
    const missing = R.mats.filter(m => m.cost === null).map(m => m.name.split('（')[0]);
    if (missing.length) data.push({ name: '未计价(缺口)', value: 0, itemStyle: { color: '#d9dee6' }, label: { show: true } });
    ch.setOption({
      tooltip: { trigger: 'item', formatter: p => p.name + '<br>' + nf(p.value, 2) + ' 元/吨 (' + p.percent + '%)' },
      legend: { bottom: 0, itemWidth: 10, itemHeight: 8, textStyle: { fontSize: 11 } },
      series: [{
        type: 'pie', radius: ['46%', '72%'], center: ['50%', '44%'], avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 4 },
        label: { formatter: p => p.percent > 4 ? p.name + '\n' + nf(p.percent, 1) + '%' : '', fontSize: 11, color: '#3c4f66' },
        data: data
      }]
    });
  }

  function drawHist(H) {
    const el = $('#chHist'); const ch = echarts.init(el); charts.push(ch);
    const rows = H.rows;
    const dates = rows.map(r => r.date);
    const cost = rows.map(r => r.cost === null ? null : +r.cost.toFixed(2));
    const colors = {};
    H.mats.forEach((m, i) => { colors[m.id] = PALETTE[i % PALETTE.length]; });
    const series = H.mats.map(m => ({
      name: m.name.split('（')[0], type: 'line', stack: 'c', symbol: 'none', smooth: true,
      lineStyle: { width: 0 }, areaStyle: { opacity: .85, color: colors[m.id] },
      data: rows.map(r => r.items[m.id] === null ? null : +r.items[m.id].toFixed(2))
    }));
    series.push({ name: '理论原料成本', type: 'line', data: cost, symbol: 'none', smooth: true,
      lineStyle: { width: 2.4, color: '#0f2540' }, z: 5 });
    ch.setOption({
      color: PALETTE,
      grid: { left: 64, right: 20, top: 34, bottom: 56 },
      tooltip: { trigger: 'axis', valueFormatter: v => (v === null ? '缺口' : nf(v, 0) + ' 元') },
      legend: { top: 0, itemWidth: 10, itemHeight: 8, textStyle: { fontSize: 11 } },
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 8, borderColor: '#e2e8f0' }],
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, hideOverlap: true }, boundaryGap: false },
      yAxis: { type: 'value', scale: true, name: '元/吨', nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10 } },
      series: series
    });
  }

  function drawContrib(obj) {
    const el = $('#chContrib'); const ch = echarts.init(el); charts.push(ch);
    if (!obj) { ch.dispose(); return; }
    const nm = obj.nm;
    const data = obj.items.map(i => ({ name: nm(i.id), value: +i.d.toFixed(1), share: i.d / (obj.w.d || 1) * 100 }));
    ch.setOption({
      grid: { left: 74, right: 46, top: 14, bottom: 30 },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: ps => ps[0].name + '<br>Δ成本 ' + nf(ps[0].value, 0) + ' 元/吨<br>占总变化 ' + nf(ps[0].data.share, 0) + '%' },
      xAxis: { type: 'value', axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: '#eef2f7' } } },
      yAxis: { type: 'category', data: data.map(d => d.name), axisLabel: { fontSize: 11 } },
      series: [{ type: 'bar', data: data.map(d => ({ value: d.value, itemStyle: { color: d.value > 0 ? '#c0392b' : '#1f7a4d', borderRadius: 3 } })),
        barWidth: '52%', label: { show: true, position: 'right', fontSize: 11, formatter: p => sgn(p.value) + nf(p.value, 0) } }]
    });
  }

  function renderAll() {
    disposeCharts();
    renderHeader(); renderKPI(); renderControls();
    renderComp(); renderHist(); renderHeat(); renderContrib(); renderScen(); renderRecent(); renderSpread();
    renderGaps(); renderDocs();
  }

  // ------------------------------------------------------------------ 本地保存
  const LS = 'chem_cost_models_v1';
  function loadLS() { try { return JSON.parse(localStorage.getItem(LS) || '{}'); } catch (e) { return {}; } }
  function saveLS(o) { try { localStorage.setItem(LS, JSON.stringify(o)); } catch (e) { toast('本机存储不可用'); } }

  function openModal() {
    renderModelList();
    $('#modal').classList.add('on');
    $('#mName').value = ((D.meta || {}).product || '').split('（')[0] + '-' + ((D.meta || {}).region || '') + '-' + new Date().toISOString().slice(0, 10);
  }
  function renderModelList() {
    const all = loadLS(); const box = $('#mList');
    const ks = Object.keys(all);
    if (!ks.length) { box.innerHTML = '<div style="font-size:12px;color:var(--ink3)">还没有保存的模型。</div>'; return; }
    box.innerHTML = ks.map(k => `<div class="mitem"><div class="t">${esc(k)}<small>${all[k].savedAt || ''} ｜ ${all[k].product || ''}</small></div>
      <button class="btn" data-load="${esc(k)}">载入</button><button class="btn" data-del="${esc(k)}">删除</button></div>`).join('');
    $$('#mList [data-load]').forEach(b => b.onclick = () => { loadModel(all[b.dataset.load]); $('#modal').classList.remove('on'); });
    $$('#mList [data-del]').forEach(b => b.onclick = () => { delete all[b.dataset.del]; saveLS(all); renderModelList(); });
  }
  function loadModel(m) {
    if (!m) return;
    state.q = Object.assign({}, m.q); state.p = Object.assign({}, m.p);
    state.rates = (m.rates || state.rates).map(r => ({ label: r.label, ratio: r.ratio }));
    if (m.combos) m.combos.forEach((c, i) => { if (D.combos[i]) D.combos[i].changes = c; });
    toast('已载入模型：' + m.name);
    renderAll();
  }

  // ------------------------------------------------------------------ 刷新价格
  async function refreshPrices() {
    // 浏览器端无法直接跨域抓取行情；这里把"刷新"做成"重新读取生成时的市场价"，
    // 并提示在支持的运行环境（Python/Node）中用 scripts/refresh_prices.py 拉最新序列后重建。
    const orig = {};
    (RAW.materials || []).forEach(m => { if (m.price !== null && m.price !== undefined) orig[m.id] = m.price; });
    Object.keys(orig).forEach(id => { state.p[id] = orig[id]; });
    toast('已重置为本次生成时的市场价（' + ((RAW.meta || {}).as_of || '') + '）。浏览器内无法直连行情源，最新价请用 scripts/refresh_prices.py 重建。');
    renderAll();
  }

  // ------------------------------------------------------------------ 杂项
  function esc(s) { return String(s === undefined || s === null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
  let tmr;
  function toast(msg) {
    const t = $('#toast'); t.textContent = msg; t.classList.add('on');
    clearTimeout(tmr); tmr = setTimeout(() => t.classList.remove('on'), 3200);
  }

  window.addEventListener('resize', () => charts.forEach(c => { try { c.resize(); } catch (e) {} }));

  // ------------------------------------------------------------------ 启动
  function boot() {
    D.process_alternatives = D.process_alternatives || [];
    D.combos = D.combos || [];
    initState();
    renderAll();
    $('#dClose').onclick = closeDrawer;
    $('#scrim').onclick = closeDrawer;
    document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeDrawer(); $('#modal').classList.remove('on'); } });
    $('#btnPrint').onclick = () => window.print();
    $('#btnReset').onclick = () => { initState(); toast('已回到生成时的原始参数'); renderAll(); };
    $('#btnSave').onclick = openModal;
    $('#mCancel').onclick = () => $('#modal').classList.remove('on');
    $('#mSave').onclick = () => {
      const name = ($('#mName').value || '').trim();
      if (!name) { toast('请填写模型名'); return; }
      const all = loadLS();
      all[name] = { name: name, savedAt: new Date().toLocaleString('zh-CN'), product: (D.meta || {}).product,
        q: state.q, p: state.p, rates: state.rates, combos: D.combos.map(c => c.changes) };
      saveLS(all); renderModelList(); toast('已保存到本机：' + name);
    };
    $('#btnAuto').onclick = refreshPrices;
    $('#btnRate5').onclick = () => {
      state.rates = [{ label: '-10%', ratio: -0.10 }, { label: '-5%', ratio: -0.05 }, { label: '0%', ratio: 0 },
                     { label: '+5%', ratio: 0.05 }, { label: '+10%', ratio: 0.10 }];
      renderAll();
    };
    $('#btnAllUp').onclick = () => { $$('#tblCombo tbody tr').forEach((tr, i) => {
      $$('input', tr).forEach(inp => { const v = 5; inp.value = v; D.combos[i].changes[inp.dataset.mid] = v; }); }); renderScen(); };
    $('#btnAllDown').onclick = () => { $$('#tblCombo tbody tr').forEach((tr, i) => {
      $$('input', tr).forEach(inp => { const v = -5; inp.value = v; D.combos[i].changes[inp.dataset.mid] = v; }); }); renderScen(); };
    $('#btnZero').onclick = () => { $$('#tblCombo tbody tr').forEach((tr, i) => {
      $$('input', tr).forEach(inp => { inp.value = 0; D.combos[i].changes[inp.dataset.mid] = 0; }); }); renderScen(); };
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
