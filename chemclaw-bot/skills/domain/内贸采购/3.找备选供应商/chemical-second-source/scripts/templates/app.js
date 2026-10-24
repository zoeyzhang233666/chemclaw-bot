/* Chemical Second Source Workbench — generic renderer.
   All product-specific language comes from DATA.meta; no hard-coded chemical names. */
const DATA = window.__DSH_DATA__;
const M = Object.assign({
  product: '目标化工品',
  product_short: '目标品',
  unit: '万吨/年',
  asof: '',
  buyer_site: '',
  buyer_short: '',
  volume: '',
  volume_t: 0,
  volume_period: '月',
  spec: '',
  use_case: '',
  scenario: '',
  qualification_label: '准入/资质',
  qualification_short: '准入',
  grade_label: '等级 / 品牌',
  near_km: 500,
  distance_bands: [],
  processes: [],
  risk_categories: ['财务', '装置', '资质', '同源', '行业'],
  same_source_note: '',
  spec_note: '',
  disclaimer: '',
  action_window: '90 天',
  price_assumption: null,
  fin_year: '',
  output_year: '',
  method_steps: [],
  key_judgements: [],
  stamp_note: '公开信息研究 · 非报价 · 非决策建议'
}, DATA.meta || {});
const base = DATA.baseline || {};
const suppliers = DATA.candidates || [];
const sources = DATA.sources || [];
const specItems = DATA.spec_items || [];
const specStatus = DATA.spec_status || {};
const sameGroups = DATA.same_source || [];
const risks = DATA.risks || [];
const actions = DATA.actions || [];

if (!Array.isArray(M.processes) || !M.processes.length) {
  M.processes = [...new Set([base.process, ...suppliers.map(s => s.process)].filter(Boolean))].map((name, i) => ({
    name, color: ['#b45309', '#1f5eff', '#067647', '#6d28d9', '#0e7490', '#be123c'][i % 6], cost_score: 60
  }));
}

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => new Intl.NumberFormat('zh-CN').format(Number(n) || 0);
const num = n => Number(n) || 0;
const state = { selected: new Set(), filter: 'all', q: '', sort: 'distance', view: 'card', riskFilter: '全部' };

const PROC_LIST = (M.processes || []).map(p => typeof p === 'string' ? { name: p } : p);
const PROC_COLOR = {};
const PROC_COST = {};
const FALLBACK_COLORS = ['#b45309', '#1f5eff', '#067647', '#6d28d9', '#0e7490', '#be123c'];
PROC_LIST.forEach((p, i) => {
  PROC_COLOR[p.name] = p.color || FALLBACK_COLORS[i % FALLBACK_COLORS.length];
  PROC_COST[p.name] = Number(p.cost_score) || 60;
});
const procColor = p => PROC_COLOR[p] || '#64748b';
const procCost = p => PROC_COST[p] || 60;
const buyerShort = M.buyer_short || String(M.buyer_site || '').replace(/[（(].*$/, '').replace(/市$/, '') || '收货地';
const FY = M.fin_year ? String(M.fin_year) + ' ' : '';
const OY = M.output_year ? String(M.output_year) + ' ' : '';
const sourceMap = {};
sources.forEach(s => { if (s.id) sourceMap[s.id] = s; });
const sourceOf = id => sourceMap[id] || null;
const sourceLink = (id, fallbackName, fallbackUrl) => {
  const s = sourceOf(id);
  const name = s ? s.name : (fallbackName || '来源待补');
  const url = s ? s.url : fallbackUrl;
  const grade = s ? s.grade : '';
  return url ? `<a class="ev" href="${esc(url)}" target="_blank" rel="noopener">${esc(name)}${grade ? `<span class="grade">${esc(grade)}</span>` : ''}</a>` : `<span class="ev">${esc(name)}</span>`;
};

/* ---------- Hero / KPI ---------- */
function renderHero() {
  $('#heroTitle').innerHTML = `${esc(M.product)}<span>备选池</span>`;
  $('#stampDate').textContent = M.asof ? `数据截止 ${M.asof}` : '数据截止日待填';
  $('#stampNote').textContent = M.stamp_note;
  $('#heroSub').innerHTML = `现有供应商：<b>${esc(base.short || base.name || '待填')}（${esc(base.process || '')} ${fmt(base.capacity)} ${esc(M.unit)}）</b> · 收货地：<b>${esc(M.buyer_site || '待填')}</b> · 采购量：<b>${esc(M.volume || '待填')}</b> · 规格：<b>${esc(M.spec || '待填')}</b><br>目标：建立可验证的第二供应源，而不是把“备选”直接变成“替换”。`;
  $('#heroScenario').textContent = M.scenario || '示例场景：参数可按实际项目替换；研究结构与证据要求保持不变。';
  const near = suppliers.filter(s => num(s.distance) <= num(M.near_km)).length;
  const qual = suppliers.filter(s => s.qualified).length;
  const fresh = suppliers.filter(s => s.new_plant).length;
  $('#heroBadges').innerHTML = `
    <span class="hbadge"><b>${suppliers.length}</b> 家备选</span>
    <span class="hbadge"><b>${near}</b> 家 ≤${fmt(M.near_km)} km</span>
    <span class="hbadge"><b>${qual}</b> 家${esc(M.qualification_short)}</span>
    <span class="hbadge"><b>${fresh}</b> 家新装置</span>
    <span class="hbadge"><b>${sameGroups.length}</b> 组股权关系</span>
    <span class="hbadge hbadge--warn">排序 ≠ 建议 · 决策权在采购</span>`;
}

function renderKpis() {
  const provinces = [...new Set(suppliers.map(s => s.province).filter(Boolean))];
  const near = suppliers.filter(s => num(s.distance) <= num(M.near_km));
  const qual = suppliers.filter(s => s.qualified);
  const needSample = suppliers.filter(s => s.sample === '必须' || (specStatus[s.id] && Object.values(specStatus[s.id]).some(v => v !== 'COA')));
  $('#kpis').innerHTML = `
    <div class="kpi"><span>备选池</span><b>${suppliers.length}<small>家</small></b><p>${esc(provinces.join('、') || '—')}</p></div>
    <div class="kpi"><span>近场（≤${fmt(M.near_km)} km）</span><b>${near.length}<small>家</small></b><p>${esc(near.map(s => s.city).filter(Boolean).slice(0, 6).join('、') || '—')}</p></div>
    <div class="kpi"><span>${esc(M.qualification_label)}</span><b>${qual.length}<small>家</small></b><p>${esc(qual.map(s => s.short).slice(0, 6).join('、') || '—')}</p></div>
    <div class="kpi"><span>需要首样验证</span><b>${needSample.length}<small>家</small></b><p>新装置 / 新工艺 / 非准入为必验项</p></div>`;
}

/* ---------- Baseline / params ---------- */
function renderBaseline() {
  const b = base;
  const rev = b.revenue == null || b.revenue === '' ? '—' : b.revenue;
  const profit = b.profit == null || b.profit === '' ? '—' : b.profit;
  const loss = String(profit).trim().startsWith('-');
  $('#baselineCard').innerHTML = `
    <div class="baseline-top">
      <div>
        <div class="blabel">BASELINE / 现有供应商</div>
        <h3>${esc(b.name || b.short || '待填')}</h3>
        <div class="code">${esc(b.listed || '')} ${esc(b.code && b.code !== '—' ? b.code : '')} · ${esc(b.group || '')} · 实控人 ${esc(b.controller || '待核')}</div>
      </div>
      <span class="pill">${esc(b.process || '')} · ${b.qualified ? esc(M.qualification_short) : '非' + esc(M.qualification_short)} ${esc(b.brand || '')}</span>
    </div>
    <div class="bmetrics">
      <div class="bmetric"><span>${esc(M.product_short)}产能</span><b>${fmt(b.capacity)}<small>${esc(M.unit)}</small></b></div>
      <div class="bmetric"><span>到${esc(buyerShort)}运距</span><b>${fmt(b.distance)}<small>km</small></b></div>
      <div class="bmetric"><span>${FY}营收</span><b>${esc(rev)}<small>亿元</small></b></div>
      <div class="bmetric"><span>${FY}归母净利</span><b style="color:${loss ? '#ffb4a8' : '#d9fbe8'}">${esc(profit)}<small>亿元</small></b></div>
    </div>
    <div class="bwarn"><span>⚠</span><div><b>基准风险：</b>${esc(b.warn || b.risk_summary || '待补公开风险事实')} 这是“建第二源”的背景，不等于应立即更换。</div></div>`;
}

function renderParams() {
  const P = DATA.params || {};
  $('#pSpec').textContent = P.spec || M.spec || '待填';
  $('#pRecv').textContent = P.receiver || M.buyer_site || '待填';
  $('#qty').value = P.monthly || M.volume_t || 800;
  $('#rate').value = P.freight_rate || 0.45;
  $('#pMode').textContent = `汽运 ${P.freight_rate || 0.45}；水运 ${P.water_rate || 0.12}（估算）`;
  $('#paramNote').innerHTML = `运费区间为公开地理距离 × 行业常见费率的结构化估算，<strong>不是承运商报价</strong>；铁路/水运需另询。到厂成本还取决于出厂价、账期、返利、包装与卸货条件，本页不合成“唯一到厂价”。`;
  updateCalc();
  $('#qty').addEventListener('input', updateCalc);
  $('#rate').addEventListener('input', updateCalc);
}

function updateCalc() {
  const P = DATA.params || {};
  const qty = Math.max(1, Number($('#qty').value) || P.monthly || 800);
  const rate = Math.max(0.05, Number($('#rate').value) || P.freight_rate || 0.45);
  const truck = Number(P.truck_load_t) || 30;
  const trucks = Math.ceil(qty / truck);
  const months = M.volume_period === '年' ? 1 : 12;
  const annual = qty * months;
  const baseFreight = Math.round(num(base.distance) * rate);
  const price = Number(P.price_assumption || M.price_assumption || 0);
  $('#calcLine').innerHTML = `
    <span><i class="dot"></i>年需求 <b>${fmt(annual)}</b> 吨</span>
    <span><i class="dot"></i>月车次（${truck} 吨/车）<b>${trucks}</b> 车</span>
    <span><i class="dot"></i>现有供应商单吨汽运估算 <b>${fmt(baseFreight)}</b> 元/吨</span>
    ${price > 0 ? `<span><i class="dot"></i>运费占货值（按 ${fmt(price)} 元/吨） <b>${(baseFreight / price * 100).toFixed(1)}%</b></span>` : ''}`;
}

/* ---------- Filters / pool ---------- */
function buildFilters() {
  const f = [
    ['all', '全部'],
    ['near', `≤${fmt(M.near_km)} km`],
    ['qual', M.qualification_short],
    ['new', '新装置'],
    ['same', '同源/同集团']
  ];
  PROC_LIST.forEach(p => f.push(['proc:' + p.name, p.name]));
  return f;
}
const FILTERS = buildFilters();

function countFilter(k) {
  if (k === 'all') return suppliers.length;
  if (k === 'near') return suppliers.filter(s => num(s.distance) <= num(M.near_km)).length;
  if (k === 'qual') return suppliers.filter(s => s.qualified).length;
  if (k === 'new') return suppliers.filter(s => s.new_plant).length;
  if (k === 'same') return suppliers.filter(s => s.same_source && s.same_source !== '无').length;
  if (k.startsWith('proc:')) return suppliers.filter(s => s.process === k.slice(5)).length;
  return 0;
}

function renderChips() {
  $('#chips').innerHTML = FILTERS.map(([k, label]) => {
    const on = state.filter === k ? 'on' : '';
    return `<button class="chip ${on}" data-f="${esc(k)}">${esc(label)}<b>${countFilter(k)}</b></button>`;
  }).join('');
  $$('#chips .chip').forEach(b => b.addEventListener('click', () => {
    state.filter = b.dataset.f;
    renderChips();
    renderPool();
  }));
}

function filtered() {
  let list = suppliers.slice();
  const q = state.q.trim().toLowerCase();
  if (q) list = list.filter(s => [s.name, s.short, s.group, s.city, s.site, s.products, s.controller, s.brand, s.grade].filter(Boolean).join(' ').toLowerCase().includes(q));
  if (state.filter === 'near') list = list.filter(s => num(s.distance) <= num(M.near_km));
  if (state.filter === 'qual') list = list.filter(s => s.qualified);
  if (state.filter === 'new') list = list.filter(s => s.new_plant);
  if (state.filter === 'same') list = list.filter(s => s.same_source && s.same_source !== '无');
  if (state.filter.startsWith('proc:')) list = list.filter(s => s.process === state.filter.slice(5));
  if (state.sort === 'distance') list.sort((a, b) => num(a.distance) - num(b.distance));
  if (state.sort === 'capacity') list.sort((a, b) => num(b.capacity) - num(a.capacity));
  if (state.sort === 'risk') list.sort((a, b) => num(a.risk_score) - num(b.risk_score) || num(a.distance) - num(b.distance));
  if (state.sort === 'name') list.sort((a, b) => String(a.name).localeCompare(String(b.name), 'zh-CN'));
  return list;
}

function tagClass(t) {
  const s = String(t || '');
  if (/同源|不独立|亏损|装置老化|高风险|非准入|非资质/.test(s)) return 'red';
  if (/新装置|规模偏小|远距|纵向|待核|外资/.test(s)) return 'amber';
  if (/近场|同工艺|低成本|规模|准入|资质|区域|水运|央企|上市|国企|龙头|一体化/.test(s)) return 'green';
  return '';
}

function riskDots(n) {
  const v = Math.max(1, Math.min(5, Number(n) || 3));
  return `<span class="dots lv${v}">${[1, 2, 3, 4, 5].map(i => `<i class="${i <= v ? 'on' : ''}"></i>`).join('')}</span>`;
}

function cardHTML(s, idx) {
  const sel = state.selected.has(s.id);
  const tags = (s.tags || s.highlights || []);
  const ev = (s.evidence || []).map(id => sourceOf(id)).filter(Boolean);
  return `<article class="card ${sel ? 'sel' : ''}" data-id="${esc(s.id)}">
    <div class="card-top">
      <div class="idx">${String(idx).padStart(2, '0')}</div>
      <div class="card-title">
        <h3>${esc(s.name)}</h3>
        <p>${esc(s.group || '')} · ${esc(s.listed || '')}${s.code && s.code !== '—' ? ' ' + esc(s.code) : ''}</p>
      </div>
      <label class="checkbox" title="加入对比">
        <input type="checkbox" data-sel="${esc(s.id)}" ${sel ? 'checked' : ''} aria-label="选择 ${esc(s.name)}">
        <span></span>
      </label>
    </div>
    <div class="card-diff">${esc(s.diff || '')}</div>
    <div class="card-metrics">
      <div class="m"><span>产能 ${esc(M.unit)}</span><b>${fmt(s.capacity)}</b></div>
      <div class="m"><span>运距 km</span><b>${fmt(s.distance)}</b></div>
      <div class="m"><span>运费 元/吨</span><b>${fmt(s.freight_low)}–${fmt(s.freight_high)}</b></div>
      <div class="m"><span>风险等级</span><b style="font-size:12px">${esc(s.risk_level || '待核')} ${riskDots(s.risk_score)}</b></div>
    </div>
    <div class="tags">
      <span class="tag" style="background:${procColor(s.process)}18;border-color:${procColor(s.process)}55;color:${procColor(s.process)}">${esc(s.process)}</span>
      <span class="tag ${s.qualified ? 'green' : 'amber'}">${s.qualified ? esc(M.qualification_short) : '非' + esc(M.qualification_short)}</span>
      <span class="tag">${esc(s.spec_fit || '待核')}兼容</span>
      ${tags.map(h => `<span class="tag ${(s.tag_tones || {})[h] || tagClass(h)}">${esc(h)}</span>`).join('')}
    </div>
    <details>
      <summary>证据、风险与待核实项</summary>
      <div class="detail-grid">
        <div class="detail-block"><h4>身份 / 证据</h4>
          <div>${esc(s.site)} · ${esc(s.ownership)} · ${esc(s.employees)}</div>
          ${ev.length ? ev.map(e => sourceLink(e.id)).join('') : '<div class="sub">证据待补</div>'}
        </div>
        <div class="detail-block"><h4>产能 / 产品</h4>
          <div>${esc(s.capacity_note || '')}</div>
          <div>${esc(s.products || '')}</div>
          <div class="sub">${FY}营收/净利：${esc(s.revenue == null ? '—' : s.revenue)} / ${esc(s.profit == null ? '—' : s.profit)} 亿元</div>
        </div>
        <div class="detail-block"><h4>风险摘要</h4><div>${esc(s.risk_summary || '')}</div></div>
        <div class="detail-block"><h4>同源判断</h4><div>${esc(s.same_note || '')}</div></div>
        <div class="detail-block"><h4>需人工核实</h4><ul>${(s.verify || []).map(v => `<li>${esc(v)}</li>`).join('')}</ul></div>
      </div>
    </details>
  </article>`;
}

function renderPool() {
  const list = filtered();
  const wrap = $('#pool');
  if (state.view === 'card') {
    wrap.classList.remove('hide');
    $('#poolTableWrap').classList.add('hide');
    wrap.innerHTML = list.length ? list.map((s, i) => cardHTML(s, i + 1)).join('') : `<div class="panel">没有匹配的供应商，试试清空搜索或切换筛选。</div>`;
    $$('#pool .checkbox input').forEach(cb => cb.addEventListener('change', () => toggle(cb.dataset.sel)));
    $$('#pool .card').forEach(c => c.addEventListener('click', e => {
      if (e.target.closest('a') || e.target.closest('label') || e.target.closest('summary') || e.target.closest('details')) return;
      const cb = c.querySelector('input[data-sel]');
      if (cb) cb.click();
    }));
  } else {
    wrap.classList.add('hide');
    const tw = $('#poolTableWrap');
    tw.classList.remove('hide');
    tw.innerHTML = `<table class="pooltable"><thead><tr>
      <th>选</th><th>企业</th><th>工艺</th><th>产能</th><th>运距</th><th>运费</th><th>${esc(M.qualification_short)}</th><th>风险</th><th>同源</th><th>兼容/试样</th>
    </tr></thead><tbody>${list.map(s => `<tr>
      <td><input type="checkbox" data-sel="${esc(s.id)}" ${state.selected.has(s.id) ? 'checked' : ''} aria-label="选择 ${esc(s.name)}"></td>
      <td><div class="name">${esc(s.name)}</div><div class="tiny">${esc(s.group || '')}</div></td>
      <td>${esc(s.process)}</td>
      <td class="num">${fmt(s.capacity)} ${esc(M.unit)}</td>
      <td class="num">${fmt(s.distance)} km</td>
      <td class="num">${fmt(s.freight_low)}–${fmt(s.freight_high)}</td>
      <td>${s.qualified ? '是' : '否'}</td>
      <td>${esc(s.risk_level || '')}</td>
      <td>${esc(s.same_source || '无')}</td>
      <td>${esc(s.spec_fit || '')} / ${esc(s.sample || '')}</td>
    </tr>`).join('')}</tbody></table>`;
    $$('#poolTableWrap input[data-sel]').forEach(cb => cb.addEventListener('change', () => toggle(cb.dataset.sel)));
  }
}

/* ---------- Selection ---------- */
function toggle(id) {
  if (state.selected.has(id)) state.selected.delete(id);
  else {
    if (state.selected.size >= 5) { toast('最多选择 5 家；请先移除一家'); renderPool(); return; }
    state.selected.add(id);
  }
  syncSelection();
}
function syncSelection() {
  $$('input[data-sel]').forEach(cb => { cb.checked = state.selected.has(cb.dataset.sel); });
  $$('#pool .card').forEach(c => c.classList.toggle('sel', state.selected.has(c.dataset.id)));
  $('#selCount').textContent = state.selected.size;
  const names = [...state.selected].map(id => suppliers.find(s => s.id === id)).filter(Boolean);
  $('#selNames').innerHTML = names.map(s => `<span class="nm">${esc(s.short)}<button data-rm="${esc(s.id)}" aria-label="移除">×</button></span>`).join('');
  $$('#selNames button').forEach(b => b.addEventListener('click', () => { state.selected.delete(b.dataset.rm); syncSelection(); }));
  $('#tray').classList.toggle('show', state.selected.size > 0);
  $('#compareBtn').disabled = state.selected.size < 2;
  if (state.view === 'table') renderPool();
}
let toastTimer;
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 2400);
}

/* ---------- Scatter ---------- */
function drawScatter() {
  const svg = $('#scatter'); if (!svg) return;
  const W = 760, H = 400, pad = { l: 58, r: 22, t: 22, b: 48 };
  const maxD = Math.max(500, num(M.near_km), Math.ceil(Math.max(...suppliers.map(s => num(s.distance)), 1) / 500) * 500);
  const maxC = Math.max(100, Math.ceil(Math.max(...suppliers.map(s => num(s.capacity)), num(base.capacity), 1) * 1.15 / 100) * 100);
  const x = d => pad.l + Math.min(num(d), maxD) / maxD * (W - pad.l - pad.r);
  const y = c => H - pad.b - (Math.log10(Math.max(num(c), 10)) - 1) / (Math.log10(maxC) - 1) * (H - pad.t - pad.b);
  const near = num(M.near_km);
  let out = '';
  out += `<rect x="${x(0)}" y="${y(maxC)}" width="${x(near) - x(0)}" height="${y(100) - y(maxC)}" fill="#e8f7f0" opacity=".65"/>`;
  const yTicks = [50, 100, 200, 500, 1000, 2000, 5000].filter(v => v <= maxC);
  if (!yTicks.length) yTicks.push(maxC);
  yTicks.forEach(v => {
    out += `<line x1="${pad.l}" y1="${y(v)}" x2="${W - pad.r}" y2="${y(v)}" stroke="#e6edf4"/>`;
    out += `<text x="${pad.l - 8}" y="${y(v) + 3}" text-anchor="end" font-size="10" fill="#7a8b9d">${fmt(v)}</text>`;
  });
  const xStep = maxD / 5;
  for (let v = 0; v <= maxD; v += xStep) {
    out += `<line x1="${x(v)}" y1="${pad.t}" x2="${x(v)}" y2="${H - pad.b}" stroke="#eef3f8"/>`;
    out += `<text x="${x(v)}" y="${H - pad.b + 16}" text-anchor="middle" font-size="10" fill="#7a8b9d">${fmt(Math.round(v))}</text>`;
  }
  out += `<line x1="${x(near)}" y1="${pad.t}" x2="${x(near)}" y2="${H - pad.b}" stroke="#9ec9b4" stroke-dasharray="4 4"/>`;
  out += `<line x1="${pad.l}" y1="${y(100)}" x2="${W - pad.r}" y2="${y(100)}" stroke="#b9c9d9" stroke-dasharray="2 5"/>`;
  out += `<text x="${pad.l + 4}" y="${pad.t + 12}" font-size="10" fill="#5a6b7d">${esc(M.unit)}（对数）</text>`;
  out += `<text x="${W - pad.r}" y="${H - pad.b + 34}" text-anchor="end" font-size="10" fill="#5a6b7d">到${esc(buyerShort)}运距 km</text>`;
  out += `<text x="${x(near) - 6}" y="${pad.t + 12}" text-anchor="end" font-size="10" fill="#067647">${fmt(near)} km 近场</text>`;
  suppliers.forEach(s => {
    const cx = x(s.distance), cy = y(s.capacity);
    out += `<circle cx="${cx}" cy="${cy}" r="7" fill="${procColor(s.process)}" stroke="#fff" stroke-width="2" opacity=".92"><title>${esc(s.name)} · ${fmt(s.capacity)} ${esc(M.unit)} · ${fmt(s.distance)} km</title></circle>`;
    out += `<text x="${cx + 9}" y="${cy + 3.5}" font-size="9.5" fill="#33475c">${esc(s.short)}</text>`;
  });
  const bx = x(base.distance), by = y(base.capacity);
  out += `<path d="M${bx} ${by - 8} L${bx + 8} ${by} L${bx} ${by + 8} L${bx - 8} ${by} Z" fill="#b42318" stroke="#fff" stroke-width="2"><title>${esc(base.name)} · ${fmt(base.capacity)} ${esc(M.unit)} · ${fmt(base.distance)} km</title></path>`;
  out += `<text x="${bx + 11}" y="${by + 3}" font-size="9.5" fill="#b42318" font-weight="700">现有 ${esc(base.short)}</text>`;
  svg.innerHTML = out;
  const q = suppliers.filter(s => s.qualified).length;
  $('#scatterTitle').textContent = `${M.product_short}产能 vs 到${buyerShort}运距`;
  $('#scatterNote').textContent = `纵轴为对数刻度；虚线为 ${fmt(near)} km 近场边界与 100 ${M.unit} 规模线`;
  $('#scatterLegend').innerHTML = PROC_LIST.map(p => `<span><i style="background:${procColor(p.name)}"></i>${esc(p.name)}</span>`).join('') +
    `<span><i style="background:#b42318;border-radius:50%"></i>现有供应商（${esc(base.short)}）</span>` +
    `<span><i style="background:#e8f7f0;border:1px solid #bfe6d2"></i>近场 + 规模 ≥100 ${esc(M.unit)}</span>` +
    `<span>${q} 家具备${esc(M.qualification_short)}</span>`;
}

/* ---------- Stack ---------- */
function drawStack() {
  const groups = PROC_LIST.map(p => [p.name, procColor(p.name)]);
  const all = [base, ...suppliers];
  const counts = groups.map(([p]) => all.filter(s => s.process === p).length);
  const total = all.length || 1;
  $('#stack').innerHTML = groups.map(([p, c], i) => `<span style="width:${counts[i] / total * 100}%;background:${c}">${esc(p)} ${counts[i]}</span>`).join('');
  $('#stacknote').innerHTML = groups.map(([p, c], i) => {
    const caps = all.filter(s => s.process === p).reduce((a, s) => a + num(s.capacity), 0);
    return `<div class="row"><b>${counts[i]} 家</b><div class="bar"><i style="width:${counts[i] / total * 100}%;background:${c}"></i></div><span style="width:120px;text-align:right">${fmt(caps)} ${esc(M.unit)}</span></div>`;
  }).join('') + `<div class="row"><b>合计</b><div class="bar"><i style="width:100%;background:#0b1b2b"></i></div><span style="width:120px;text-align:right">${fmt(all.reduce((a, s) => a + num(s.capacity), 0))} ${esc(M.unit)}</span></div>`;
  const top = groups.map(([p], i) => ({ p, n: counts[i] })).sort((a, b) => b.n - a.n)[0];
  $('#stackNoteTop').textContent = `${suppliers.length} 家备选 + 现有供应商；${top ? top.p + ' 占多数（' + top.n + ' 家）' : ''}`;
  $('#stackInsight').textContent = M.process_insight || '工艺只决定“成本倾向”，不决定质量；同工艺不等于同规格，新装置/新工艺/非准入仍需首样验证。';
}

/* ---------- Same source ---------- */
function renderSameSource() {
  const flagColor = f => /同源|纵向|不独立/.test(f) ? '#b42318' : /同集团/.test(f) ? '#b45309' : /非同源/.test(f) ? '#067647' : '#64748b';
  $('#sourcegrid').innerHTML = sameGroups.length ? sameGroups.map(g => `
    <div class="sourcecard">
      <span class="flag" style="color:${flagColor(g.flag)};border-color:${flagColor(g.flag)}55;background:${flagColor(g.flag)}12">${esc(g.flag || '关系')}</span>
      <h3>${esc(g.group)}</h3>
      <div class="parent">${esc(g.parent || '')}</div>
      <div class="entities">${(g.entities || []).map(e => `<div class="entity">${esc(e)}</div>`).join('')}</div>
      <div class="sub">关系：${esc(g.relation || '')}</div>
      <div class="impl"><b>影响：</b>${esc(g.implication || '')}<br><b>核实：</b>${esc(g.verify || '')}</div>
    </div>`).join('') : `<div class="panel">未发现同源/同集团关系；仍需逐家做股权穿透。</div>`;
  $('#sameNote').innerHTML = M.same_source_note ? `<strong>特别提示：</strong>${esc(M.same_source_note)}` : '';
}

/* ---------- Spec ---------- */
function renderSpec() {
  const items = specItems;
  const head = `<thead><tr><th>企业</th>${items.map(i => `<th>${esc(i.label)}<div class="sub" style="font-weight:400">${esc(i.target || '')}</div></th>`).join('')}</tr></thead>`;
  const body = suppliers.map(s => {
    const st = specStatus[s.id] || {};
    return `<tr><td><b>${esc(s.short)}</b><div class="sub">${esc(s.process)} · ${s.qualified ? esc(M.qualification_short) : '非' + esc(M.qualification_short)}</div></td>${items.map(i => {
      const v = st[i.id] || '试样';
      const cls = v === 'COA' ? 'coa' : v === '试样' ? 'sample' : 'audit';
      return `<td><span class="st ${cls}">${esc(v)}</span></td>`;
    }).join('')}</tr>`;
  }).join('');
  $('#spectable').innerHTML = head + `<tbody>${body}</tbody>`;
  $('#specLegend').innerHTML = `<span><span class="st coa">COA</span> 可凭批次 COA/出厂检验追溯</span>
    <span><span class="st sample">试样</span> 必须首样或小批量验证</span>
    <span><span class="st audit">审核</span> 需现场审核/封样/包装确认</span>
    <span>${esc(M.spec_note || '首样建议：每家 20–50 kg × 3 批；检测周期 7–10 个工作日；判定依据客户内控 + 国标/行标。')}</span>`;
}

/* ---------- Risks ---------- */
const RISK_CATS = ['全部'].concat(M.risk_categories || []);
function riskCat(r) {
  if (r.category) return r.category;
  const t = String(r.type || '');
  if (/财务|成本|价格|亏损/.test(t)) return '财务';
  if (/装置|产能|环保|安全|供给/.test(t)) return '装置';
  if (/资质|规模|准入|质量/.test(t)) return '资质';
  if (/同源|股权|独立性/.test(t)) return '同源';
  return '行业';
}
function renderRiskHead() {
  $('#riskhead').innerHTML = RISK_CATS.map(c => {
    const n = c === '全部' ? risks.length : risks.filter(r => riskCat(r) === c).length;
    return `<button class="chip ${state.riskFilter === c ? 'on' : ''}" data-risk="${esc(c)}">${esc(c)}<b>${n}</b></button>`;
  }).join('');
  $$('#riskhead .chip').forEach(b => b.addEventListener('click', () => { state.riskFilter = b.dataset.risk; renderRiskHead(); renderRisks(); }));
}
function renderRisks() {
  const list = state.riskFilter === '全部' ? risks : risks.filter(r => riskCat(r) === state.riskFilter);
  const dot = c => ({'财务':'f','装置':'e','资质':'q','同源':'s'}[c] || 'i');
  $('#risktable').innerHTML = `<thead><tr><th>企业</th><th>类型</th><th>公开事实</th><th>影响</th><th>来源</th><th>状态</th></tr></thead><tbody>${list.map(r => {
    const cat = riskCat(r);
    return `<tr>
      <td><b>${esc(r.company || '')}</b></td>
      <td><span class="riskdot ${dot(cat)}"></span>${esc(cat)}</td>
      <td>${esc(r.fact || '')}</td>
      <td>${esc(r.impact || '')}</td>
      <td>${sourceLink(r.source_id, r.source, r.url)}</td>
      <td><span class="status ${r.status === '已公开' ? 'ok' : 'pending'}">${esc(r.status || '待核实')}</span></td>
    </tr>`;
  }).join('')}</tbody>`;
}

/* ---------- Actions ---------- */
function renderActions() {
  $('#actionTitle').textContent = `${M.action_window || '90 天'}推进清单`;
  $('#actions').innerHTML = actions.map(a => `<div class="action">
    <span class="phase">${esc(a.phase || '')}</span>
    <h3>${esc(a.action || '')}</h3>
    <p>${esc(a.detail || '')}</p>
    <div class="meta"><span>责任：<b>${esc(a.owner || '待定')}</b></span><span>产出：<b>${esc(a.output || '')}</b></span></div>
  </div>`).join('');
}

/* ---------- Method / sources / footer ---------- */
function renderMethod() {
  const steps = M.method_steps || [];
  const js = M.key_judgements || [];
  if (!steps.length && !js.length) { $('#methodSec').classList.add('hide'); return; }
  $('#methodSub').textContent = M.method_note || '研究口径可复核；结论只用于缩小验证范围，不替代采购决策。';
  $('#methodSteps').innerHTML = steps.map((s, i) => `<div class="mstep"><b>${i + 1}</b><div><strong>${esc(s.label || s.title || '')}</strong><div>${esc(s.text || '')}</div></div></div>`).join('');
  $('#judgements').innerHTML = js.map(s => `<div class="judgement"><b>${esc(s.label || '')}</b><div>${esc(s.text || '')}</div></div>`).join('');
}
function renderSources() {
  $('#sources').innerHTML = sources.map((s, i) => `<div class="src"><span class="grade">${esc(s.grade || '?')}</span><b>${i + 1}.</b> ${esc(s.name)}${s.date ? ` <span class="sub">（${esc(s.date)}）</span>` : ''}${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">原文</a>` : ''}</div>`).join('');
  const xlsx = '__XLSX_NAME__';
  $('#footerText').innerHTML = `${esc(M.disclaimer || '本页为采购研究辅助材料，不构成供应商选择、替换或授标建议。')}<br>
    配套工作簿：<a href="${esc(xlsx)}" download>${esc(xlsx)}</a>（10 个工作表：说明 / 备选池 / 图表 / 横向对比 / 试样 / 同源 / 风险 / 行动 / 来源 / 尽调）<br>
    ${M.asof ? '数据截止 ' + esc(M.asof) + ' · ' : ''}场景：${esc(M.buyer_site || '')} / ${esc(M.product)} ${esc(M.volume || '')} / 现有供应商 ${esc(base.short || '')} · 仅用于内部采购评估。`;
}

/* ---------- Compare ---------- */
const CMP_ROWS = [
  { label: '企业全称', get: s => esc(s.name) },
  { label: '集团 / 实控人', get: s => `${esc(s.group || '')}<div class="sub">${esc(s.controller || '')}</div>` },
  { label: '股权性质', get: s => esc(s.ownership || '') },
  { label: '生产地', get: s => `${esc(s.province || '')} · ${esc(s.city || '')}<div class="sub">${esc(s.site || '')}</div>` },
  { label: `距${buyerShort}（km）`, get: s => fmt(s.distance), num: 'low', val: s => num(s.distance) },
  { label: '运输方式', get: s => esc(s.transport || '') },
  { label: '估算运费中值（元/吨）', get: s => fmt((num(s.freight_low) + num(s.freight_high)) / 2), num: 'low', val: s => (num(s.freight_low) + num(s.freight_high)) / 2 },
  { label: '工艺', get: s => esc(s.process || '') },
  { label: `${M.product_short}产能（${M.unit}）`, get: s => fmt(s.capacity), num: 'high', val: s => num(s.capacity) },
  { label: M.grade_label || '等级 / 品牌', get: s => `${esc(s.grade || '')}<div class="sub">${esc(s.brand || '')}</div>` },
  { label: '主营产品', get: s => esc(s.products || '') },
  { label: `${FY}营收（亿元）`, get: s => esc(s.revenue == null ? '—' : s.revenue) },
  { label: `${FY}净利（亿元）`, get: s => esc(s.profit == null ? '—' : s.profit) },
  { label: '员工（公开）', get: s => esc(s.employees || '—') },
  { label: M.qualification_label || '准入 / 资质', get: s => s.qualified ? '是' : '否' },
  { label: '规格兼容性', get: s => esc(s.spec_fit || '待核') },
  { label: '试样要求', get: s => esc(s.sample || '—') },
  { label: '风险等级', get: s => esc(s.risk_level || '') },
  { label: '风险分（1–5，低=好）', get: s => esc(s.risk_score), num: 'low', val: s => num(s.risk_score) },
  { label: '同源关系', get: s => esc(s.same_source || '无') },
  { label: '同源说明', get: s => esc(s.same_note || '') },
  { label: '需人工核实', get: s => (s.verify || []).map(v => esc(v)).join('；') },
  { label: `与${base.short || '现有'}差异`, get: s => esc(s.diff || '') }
];

function openCompare() {
  const chosen = [...state.selected].map(id => suppliers.find(s => s.id === id)).filter(Boolean);
  if (chosen.length < 2) { toast('请至少选择 2 家'); return; }
  const cols = [base, ...chosen];
  $('#modalTitle').textContent = `横向比较 · 现有供应商 + ${chosen.length} 家备选`;
  $('#modalSub').textContent = `第一列为现有供应商 ${base.name}；绿色/红色标记可量化项在“现有 + 所选备选”中的相对位置，不代表替换建议。`;
  let html = `<thead><tr><th>对比维度</th>${cols.map((s, i) => `<th class="${i === 0 ? 'base' : ''}">${esc(s.short)}<div class="sub" style="font-weight:400">${i === 0 ? '现有供应商' : esc(s.process) + ' · ' + fmt(s.capacity) + ' ' + esc(M.unit)}</div></th>`).join('')}</tr></thead><tbody>`;
  CMP_ROWS.forEach(row => {
    let best = null, worst = null;
    if (row.num) {
      const vals = cols.map(row.val);
      best = row.num === 'low' ? Math.min(...vals) : Math.max(...vals);
      worst = row.num === 'low' ? Math.max(...vals) : Math.min(...vals);
    }
    html += `<tr><th>${esc(row.label)}</th>${cols.map((s, i) => {
      let cls = '';
      if (row.num) {
        const v = row.val(s);
        if (v === best && best !== worst) cls = 'best';
        if (v === worst && best !== worst) cls = 'worst';
      }
      return `<td class="${cls} ${i === 0 ? 'base' : ''}">${row.get(s)}</td>`;
    }).join('')}</tr>`;
  });
  $('#cmptable').innerHTML = html + '</tbody>';

  const axes = [
    { label: '产能规模', v: s => Math.min(100, Math.log10(Math.max(num(s.capacity), 1)) / Math.log10(Math.max(...cols.map(x => num(x.capacity)), 1)) * 100) },
    { label: '区位物流', v: s => Math.max(4, 100 - num(s.distance) / Math.max(...cols.map(x => num(x.distance)), 1) * 100) },
    { label: '成本潜力', v: s => procCost(s.process) },
    { label: '资质合规', v: s => s.qualified ? 100 : 55 },
    { label: '风险稳健', v: s => 100 - (num(s.risk_score) - 1) * 20 },
    { label: '供应独立性', v: s => s.same_source === '无' ? 100 : 45 }
  ];
  $('#radar').innerHTML = radarSVG(axes, cols);
  $('#radarLegend').innerHTML = cols.map((s, i) => `<span><i style="background:${i === 0 ? '#64748b' : procColor(s.process)}"></i>${esc(s.short)}${i === 0 ? '（现有）' : ''}</span>`).join('');
  $('#diffList').innerHTML = chosen.map(s => {
    const d = num(s.distance) - num(base.distance);
    const c = num(s.capacity) - num(base.capacity);
    const pct = base.capacity ? Math.round(Math.abs(c) / num(base.capacity) * 100) : 0;
    const dir = d === 0 ? '持平' : (d < 0 ? `缩短 ${fmt(Math.abs(d))} km` : `增加 ${fmt(Math.abs(d))} km`);
    return `<li><b>${esc(s.short)}</b>：工艺${s.process === base.process ? '同为 ' + esc(s.process) : '由 ' + esc(base.process) + ' 转为 ' + esc(s.process)}；运距${dir}；产能${c >= 0 ? '+' : '-'}${fmt(Math.abs(c))} ${esc(M.unit)}（${pct}%）；${esc(M.qualification_short)}${s.qualified ? '具备' : '不具备'}；风险等级${esc(s.risk_level || '待核')}。<span class="sub">${s.same_source && s.same_source !== '无' ? '同源提示：' + esc(s.same_source) + '。' : ''}</span></li>`;
  }).join('');
  $('#modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function radarSVG(axes, list) {
  const cx = 200, cy = 200, R = 132, n = axes.length;
  const ang = i => -Math.PI / 2 + i * 2 * Math.PI / n;
  const hasBase = list[0] && (list[0].role === '现有供应商' || list[0].id === base.id);
  let out = '';
  [0.25, 0.5, 0.75, 1].forEach(k => {
    const pts = axes.map((_, i) => `${cx + Math.cos(ang(i)) * R * k},${cy + Math.sin(ang(i)) * R * k}`).join(' ');
    out += `<polygon points="${pts}" fill="none" stroke="#dbe5ef" stroke-width="1"/>`;
  });
  axes.forEach((a, i) => {
    out += `<line x1="${cx}" y1="${cy}" x2="${cx + Math.cos(ang(i)) * R}" y2="${cy + Math.sin(ang(i)) * R}" stroke="#e3ebf3"/>`;
    const lx = cx + Math.cos(ang(i)) * (R + 26), ly = cy + Math.sin(ang(i)) * (R + 26);
    out += `<text x="${lx}" y="${ly + 4}" text-anchor="middle" font-size="11" fill="#5a6b7d">${esc(a.label)}</text>`;
  });
  list.forEach((s, idx) => {
    const isBase = hasBase && idx === 0;
    const color = isBase ? '#64748b' : procColor(s.process);
    const pts = axes.map((a, i) => {
      const v = Math.max(0, Math.min(100, a.v(s))) / 100;
      return `${cx + Math.cos(ang(i)) * R * v},${cy + Math.sin(ang(i)) * R * v}`;
    }).join(' ');
    out += `<polygon points="${pts}" fill="${color}" fill-opacity="${isBase ? '.05' : '.12'}" stroke="${color}" stroke-width="2" ${isBase ? 'stroke-dasharray="5 4"' : ''}/>`;
    axes.forEach((a, i) => {
      const v = Math.max(0, Math.min(100, a.v(s))) / 100;
      out += `<circle cx="${cx + Math.cos(ang(i)) * R * v}" cy="${cy + Math.sin(ang(i)) * R * v}" r="${isBase ? 2.6 : 3}" fill="${color}"/>`;
    });
  });
  return out;
}

/* ---------- Init ---------- */
function init() {
  renderHero();
  renderKpis();
  renderBaseline();
  renderParams();
  renderChips();
  renderPool();
  drawScatter();
  drawStack();
  renderSameSource();
  renderSpec();
  renderRiskHead();
  renderRisks();
  renderActions();
  renderMethod();
  renderSources();

  $('#q').addEventListener('input', e => { state.q = e.target.value; renderPool(); });
  $('#sort').addEventListener('change', e => { state.sort = e.target.value; renderPool(); });
  $('#viewCard').addEventListener('click', () => { state.view = 'card'; $('#viewCard').classList.add('on'); $('#viewTable').classList.remove('on'); renderPool(); });
  $('#viewTable').addEventListener('click', () => { state.view = 'table'; $('#viewTable').classList.add('on'); $('#viewCard').classList.remove('on'); renderPool(); });
  $('#clearBtn').addEventListener('click', () => { state.selected.clear(); syncSelection(); });
  $('#compareBtn').addEventListener('click', openCompare);
  $('#closeModal').addEventListener('click', () => { $('#modal').classList.remove('open'); document.body.style.overflow = ''; });
  $('#modal').addEventListener('click', e => { if (e.target.id === 'modal') { $('#modal').classList.remove('open'); document.body.style.overflow = ''; } });
  $('#printCompare').addEventListener('click', () => {
    document.body.classList.add('printing-compare');
    window.print();
    setTimeout(() => document.body.classList.remove('printing-compare'), 400);
  });
  window.addEventListener('beforeprint', () => {
    if ($('#modal').classList.contains('open')) document.body.classList.add('printing-compare');
  });
  window.addEventListener('afterprint', () => document.body.classList.remove('printing-compare'));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { $('#modal').classList.remove('open'); document.body.style.overflow = ''; } });
  window.addEventListener('resize', () => { drawScatter(); });
  syncSelection();
}
init();
