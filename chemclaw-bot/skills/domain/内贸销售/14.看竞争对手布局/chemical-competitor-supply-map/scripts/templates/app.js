/* ============================================================
   化工品 · 竞争供给布局 / 交互层（通用版）
   数据契约见 references/data-contract.md
   ============================================================ */
const D = window.__DATA__;
const M = D.meta || {};
const T = D.target;
const PRODUCT = M.product_short || D.product || '目标化工品';
const CITY = T.city || M.city || '目标城市';
const PROV = T.province || M.province || '';
const REGION = T.region || M.region || `${PROV} · ${CITY}`;
const CO = Object.fromEntries((D.companies || []).map(c => [c.id, c]));
const PL = Object.fromEntries((D.plants || []).map(p => [p.id, p]));
const PR = Object.fromEntries((D.projects || []).map(p => [p.id, p]));
const CU = Object.fromEntries((D.prospects || []).map(p => [p.id, p]));
const SRC = Object.fromEntries((D.sources || []).map(s => [s.id, s]));
const PROC_COLORS = Object.fromEntries((M.processes || []).map(p => [p.name, p.color]));
const BANDS = M.distance_bands || (D.bands || []).map(b => ({ label: b.band, max: null }));
const TARGET_YEAR = parseInt(String(M.asof || D.asof || '').slice(0, 4), 10) || new Date().getFullYear();
const LABEL_PROV = M.label_province || ((D.provs || [])[0] || {}).province || PROV;
const PROJECT_LABELS = new Set(M.project_labels || (D.projects || []).slice().sort((a, b) => b.capacity - a.capacity).slice(0, 2).map(p => p.id));
const COL = { amber: '#e0b16b', red: '#e06b4f', line: '#6fa8c7' };
const state = {
  co: new Set((D.companies || []).map(c => c.id)),
  proc: 'all', prov: null,
  lines: true, projects: true, labels: true,
  mproc: 'all', q: '', onlyNew: false,
  sort: { key: 'capacity', dir: -1 },
  seg: 'all'
};
let mapChart = null, chProv = null, chBand = null, chProc = null;
const RENDERER = new URLSearchParams(location.search).get('renderer') === 'svg' ? 'svg' : 'canvas';
let toastTimer = null;

const fmt = n => (n == null || isNaN(Number(n)) ? '—' : Number(n).toLocaleString('zh-CN'));
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
const shortProv = n => String(n || '').replace(/壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|省|市$/g, '');
const bandClass = b => b == null ? '' : (b.indexOf('本地') >= 0 ? 'gA2' : b.indexOf('近邻') >= 0 ? 'gB2' : '');
const procColor = p => PROC_COLORS[p] || (p && p.indexOf('天然') >= 0 ? '#c9793f' : p && p.indexOf('联') >= 0 ? '#3f86a8' : '#87975f');
const gradeLabel = g => ({ A: 'A 产能数据', B: 'B 公开口径', C: 'C 业务信息', D: 'D 推断' }[g] || g);
const unit = () => M.unit || '万吨/年';
const bandShort = b => String(b || '').replace(/^[<>≤≥0-9.\-–—km\s]+/g, '').trim() || String(b || '');

function toast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2400);
}

function provInfo(name) {
  return (D.provs || []).find(p => p.province === name) || {
    province: name, capacity: 0, plants: 0, n_companies: 0, companies: [],
    dominant: '—', judge: '空白', km_min: null, prospect_count: 0, prospects: []
  };
}

function srcLinks(ids) {
  return (ids || []).map(id => {
    const s = SRC[id];
    if (!s) return '';
    return `<a href="${s.url}" target="_blank" rel="noopener" title="${esc((s.org || '') + ' · ' + (s.title || ''))}">${id}</a>`;
  }).filter(Boolean).join(' · ');
}

/* ============================================================
   MATRIX
   ============================================================ */
function matrixRows() {
  let rows = (D.companies || []).filter(c => state.mproc === 'all' || (c.process || '').indexOf(state.mproc) >= 0);
  if (state.onlyNew) rows = rows.filter(c => (c.projects || []).length > 0);
  if (state.q.trim()) {
    const q = state.q.trim().toLowerCase();
    rows = rows.filter(c => {
      const hay = [c.name, c.short, c.hq, c.process, c.products, c.coverage, c.new, ...(c.plants || []).map(p => p.name + p.province + p.city)].join(' ').toLowerCase();
      return hay.indexOf(q) >= 0;
    });
  }
  rows.sort((a, b) => {
    const k = state.sort.key;
    let x = a[k], y = b[k];
    if (k === 'name') { x = a.name; y = b.name; }
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    if (typeof x === 'string') return String(x).localeCompare(String(y), 'zh') * state.sort.dir;
    return (x - y) * state.sort.dir;
  });
  return rows;
}

function matrixHTML() {
  const rows = matrixRows();
  if (!rows.length) return `<tr class="empty-row"><td colspan="10">当前筛选下没有企业；试试清空搜索或“全选”。</td></tr>`;
  const maxCap = Math.max(...(D.companies || []).map(c => c.capacity), 1);
  return rows.map(c => {
    const on = state.co.has(c.id);
    const bar = Math.max(4, c.capacity / maxCap * 100);
    const plantNames = (c.plants || []).map(p => p.name.replace('基地', '').replace('厂区', '')).join('、');
    const newText = (c.projects || []).length ? (c.new || c.projects.map(p => p.name).join('、')) : '<span class="muted">无公开新增</span>';
    return `<tr data-co="${c.id}" class="${on ? '' : 'dim'}" onclick="openCompany('${c.id}')">
      <td class="check" onclick="event.stopPropagation()"><input type="checkbox" ${on ? 'checked' : ''} onchange="toggleCompany('${c.id}', this.checked)" aria-label="叠加 ${esc(c.short)}"></td>
      <td><div class="co">${esc(c.name)}<small>${esc(c.ticker || '非上市')}${c.alias ? ' · ' + esc(c.alias) : ''} · ${esc(c.hq || '')}</small></div></td>
      <td><span style="color:${procColor(c.process)};font-weight:600">${esc(c.process)}</span></td>
      <td><span class="num">${fmt(c.capacity)}<small>万吨</small></span><div class="capbar"><i style="width:${bar}%"></i></div><div class="tiny muted" style="margin-top:2px">${esc(c.cap_year || '')}</div></td>
      <td><span class="num">${c.output == null ? '<span class="dash">—</span>' : fmt(c.output)}</span>${c.output == null ? '<div class="tiny muted">未披露</div>' : '<div class="tiny muted">实际产出</div>'}</td>
      <td><span class="num">${c.plant_count || 0}</span><div class="tiny muted" style="max-width:110px;line-height:1.45">${esc(plantNames)}</div></td>
      <td><span class="num">${fmt(c.min_km)}</span><div class="tiny ${bandClass(c.band)}">${esc(c.band || '—')}</div></td>
      <td><div class="txt">${esc(c.coverage || '—')} <span class="tag infer">D</span></div></td>
      <td><div class="txt">${newText}</div></td>
      <td><span class="grade g${esc(c.grade)}" style="white-space:nowrap"><b></b>${esc(c.grade)}</span></td>
    </tr>`;
  }).join('');
}

function renderMatrix() {
  const el = document.getElementById('matrixBody');
  if (!el) return;
  el.innerHTML = matrixHTML();
  const count = document.getElementById('mcount');
  if (count) count.textContent = `${matrixRows().length} 家 / ${D.total_companies}`;
  document.querySelectorAll('#matrix th[data-sort]').forEach(th => {
    th.classList.toggle('sorted', th.dataset.sort === state.sort.key);
    th.dataset.dir = th.dataset.sort === state.sort.key ? state.sort.dir : '';
  });
}
function setQuery(v) { state.q = v; renderMatrix(); }
function setOnlyNew(v) { state.onlyNew = v; renderMatrix(); }
function setMatrixProc(p) {
  state.mproc = p;
  document.querySelectorAll('[data-mproc]').forEach(b => b.classList.toggle('on', b.dataset.mproc === p));
  renderMatrix();
}
function toggleCompany(id, on) {
  if (on === undefined) on = !state.co.has(id);
  if (on) state.co.add(id); else state.co.delete(id);
  syncChips(); renderMatrix(); renderMap(); renderSide();
}
function allCompanies(flag) {
  state.co = flag ? new Set((D.companies || []).map(c => c.id)) : new Set();
  syncChips(); renderMatrix(); renderMap(); renderSide();
  if (!flag) toast('已清空企业图层；可点“全选”恢复');
}
function syncChips() {
  document.querySelectorAll('.chip.co').forEach(el => {
    const on = state.co.has(el.dataset.co);
    el.classList.toggle('off', !on);
    el.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
}

/* ============================================================
   MAP
   ============================================================ */
function filteredCompanies() { return (D.companies || []).filter(c => state.co.has(c.id)); }
function filteredPlants() {
  const cids = new Set(filteredCompanies().map(c => c.id));
  return (D.plants || []).filter(p => cids.has(p.company_id) && (state.proc === 'all' || p.process === state.proc));
}

function initMap() {
  if (!window.echarts || !window.__GEO__) {
    const el = document.getElementById('map');
    if (el) el.innerHTML = '<div style="padding:40px;color:#b9c5bc">地图组件未加载。</div>';
    return;
  }
  echarts.registerMap('china', window.__GEO__);
  mapChart = echarts.init(document.getElementById('map'), null, { renderer: RENDERER });
  mapChart.on('click', p => {
    if (p.data && p.data.kind === 'plant') { openPlant(p.data.id); return; }
    if (p.data && p.data.kind === 'project') { openProject(p.data.id); return; }
    if (p.data && p.data.kind === 'target') { showProspects(PROV); return; }
    if (p.name) selectProv(shortProv(p.name));
  });
  window.addEventListener('resize', () => mapChart && mapChart.resize());
  renderMap();
}

function renderMap() {
  if (!mapChart) return;
  const cids = new Set(filteredCompanies().map(c => c.id));
  const plants = filteredPlants();
  const provCap = {};
  plants.forEach(p => { provCap[p.province] = (provCap[p.province] || 0) + p.capacity; });
  const geoFeats = (window.__GEO__.features || []);
  const maxProv = Math.max(1, ...Object.values(provCap));

  const plantData = plants.map(p => ({
    kind: 'plant', id: p.id, name: p.name,
    value: [p.lon, p.lat, p.capacity],
    symbolSize: Math.max(9, Math.sqrt(p.capacity) * 1.55),
    itemStyle: { color: procColor(p.process), borderColor: '#f7efdd', borderWidth: 1.2, shadowBlur: 10, shadowColor: 'rgba(0,0,0,.35)' },
    label: {
      show: state.labels && (p.label_show === true || p.capacity >= (M.label_capacity_min || 330) || state.co.size <= 4),
      formatter: `${p.company_short || p.company || ''}\n${p.capacity}`,
      position: p.label_position || 'right', color: '#efe7d3', fontSize: 10, lineHeight: 13,
      textBorderColor: 'rgba(11,31,25,.85)', textBorderWidth: 2
    },
    emphasis: { scale: 1.25, label: { show: true } }
  }));

  const provLabelData = geoFeats.map(f => {
    const sp = shortProv(f.properties.name);
    const cap = provCap[sp] || 0;
    const show = state.labels && cap > 0 && (sp === LABEL_PROV || state.prov === sp);
    const c = f.properties.centroid || f.properties.center || [0, 0];
    return {
      value: c, kind: 'provlabel',
      label: {
        show, formatter: `${sp}\n${cap}`, position: 'inside', align: 'center', verticalAlign: 'middle',
        color: state.prov === sp ? '#ffe1b0' : '#d9e4d8', fontSize: 10, lineHeight: 13, fontWeight: 600,
        textBorderColor: 'rgba(11,31,25,.75)', textBorderWidth: 2
      },
      itemStyle: { opacity: 0 }
    };
  });

  const lineData = state.lines ? plants.filter(p => p.km > 300).map(p => {
    const col = p.km <= 800 ? '#6fa8c7' : p.km <= 1500 ? '#d9a441' : '#b4642d';
    return {
      coords: [[p.lon, p.lat], [T.lon, T.lat]],
      lineStyle: { color: col, width: p.km > 1500 ? 1 : 1.2, opacity: p.km > 1500 ? 0.20 : 0.34, curveness: 0.16, type: 'dashed' }
    };
  }) : [];

  const projData = state.projects ? (D.projects || []).filter(p => cids.has(p.company_id) && p.lon != null && p.lat != null).map(p => ({
    kind: 'project', id: p.id, name: p.name,
    value: [p.lon, p.lat, p.capacity],
    symbol: 'diamond', symbolSize: 14,
    itemStyle: { color: '#e0b16b', borderColor: '#0b1f19', borderWidth: 2, shadowBlur: 10, shadowColor: 'rgba(224,177,107,.45)' },
    label: { show: state.labels && PROJECT_LABELS.has(p.id), formatter: `＋${p.capacity}`, position: 'bottom', color: '#e8c98e', fontSize: 9, textBorderColor: 'rgba(11,31,25,.9)', textBorderWidth: 2 }
  })) : [];

  const targetData = [{
    kind: 'target', id: 'target', name: `目标区域 ${REGION}`,
    value: [T.lon, T.lat, 0], symbol: 'circle', symbolSize: 34,
    itemStyle: { color: 'rgba(224,107,79,.08)', borderColor: COL.red, borderWidth: 2, shadowBlur: 18, shadowColor: 'rgba(224,107,79,.5)' },
    label: {
      show: true, formatter: `目标区域\n${REGION}`, position: 'bottom', distance: 10,
      color: '#ffd9c9', fontSize: 11, fontWeight: 700, lineHeight: 15,
      backgroundColor: 'rgba(11,31,25,.72)', padding: [4, 7], borderRadius: 5,
      borderColor: 'rgba(224,107,79,.45)', borderWidth: 1
    }
  }];

  mapChart.setOption({
    backgroundColor: 'transparent', animationDuration: 500,
    tooltip: {
      trigger: 'item', backgroundColor: 'rgba(16,42,34,.96)', borderColor: 'rgba(224,177,107,.35)',
      borderWidth: 1, padding: [9, 11], textStyle: { color: '#f3ecda', fontSize: 11.5, lineHeight: 18 },
      extraCssText: 'box-shadow:0 18px 40px rgba(0,0,0,.35);border-radius:8px;',
      formatter: p => {
        if (p.data && p.data.kind === 'plant') {
          const x = PL[p.data.id];
          return `<b style="font-size:13px">${esc(x.company)} · ${esc(x.name)}</b><br>
            <span style="color:#b9c5bc">${esc(x.province)} ${esc(x.city)} ｜ ${esc(x.process)}</span><br>
            产能 <b>${fmt(x.capacity)}</b> ${unit()} ｜ 到${CITY} <b>${fmt(x.km)}</b> km<br>
            <span style="color:#b9c5bc">${esc(x.note || '')}</span><br>
            <span style="color:#e0b16b">点击查看工厂明细 →</span>`;
        }
        if (p.data && p.data.kind === 'project') {
          const x = PR[p.data.id];
          return `<b style="font-size:13px">${esc(x.company)} · ${esc(x.name)}</b><br>
            <span style="color:#b9c5bc">${esc(x.location)} ｜ ${esc(x.process)} ｜ ${esc(x.kind)}</span><br>
            规模 <b>${fmt(x.capacity)}</b> ${unit()} ｜ ${esc(x.status)}<br>
            <span style="color:#b9c5bc">${esc(x.timing)}</span><br>
            <span style="color:#e0b16b">点击查看项目 →</span>`;
        }
        if (p.data && p.data.kind === 'target') {
          return `<b>目标区域 · ${esc(REGION)}</b><br>示例客户：${esc(T.customer_short)}<br>本地在产 ${fmt(provInfo(PROV).capacity)} ${unit()}`;
        }
        const sp = shortProv(p.name);
        const info = provInfo(sp);
        if (!info || info.capacity === 0) {
          return `<b>${sp}</b><br><span style="color:#b9c5bc">本省无在产${esc(PRODUCT)}样本</span><br><span style="color:#e0b16b">点击查看最近外省供给 →</span>`;
        }
        return `<b>${sp}</b><br>样本在产 <b>${fmt(info.capacity)}</b> ${unit()} ｜ ${info.plants} 座工厂<br>
          主导工艺：${esc(info.dominant)}<br>到${CITY}最近：${fmt(info.km_min)} km<br>
          <span style="color:#e0b16b">点击查看区域读数 →</span>`;
      }
    },
    geo: {
      map: 'china', roam: true,
      center: (M.map_center || [107.5, 35.2]), zoom: M.map_zoom || 1.08,
      left: 8, right: 8, top: 8, bottom: 8,
      itemStyle: { areaColor: '#152b23', borderColor: '#2a4a3c', borderWidth: 0.8 },
      emphasis: { itemStyle: { areaColor: '#1d3a2f' }, label: { show: false } },
      select: { itemStyle: { areaColor: '#24473a' }, label: { show: false } },
      scaleLimit: { min: 0.85, max: 9 }
    },
    visualMap: {
      show: false, min: 0, max: maxProv, seriesIndex: 0,
      inRange: { color: ['#142820', '#1d3a2f', '#2b5a47', '#3f7d65', '#61a889'] }
    },
    series: [
      { name: '省级供给', type: 'map', map: 'china', geoIndex: 0, selectedMode: false, data: geoFeats.map(f => {
          const sp = shortProv(f.properties.name);
          const cap = provCap[sp] || 0;
          return { name: f.properties.name, value: cap, itemStyle: sp === PROV ? { borderColor: '#e0b16b', borderWidth: 2.4, shadowBlur: 16, shadowColor: 'rgba(224,177,107,.55)' } : undefined };
        }), z: 1, label: { show: false },
        emphasis: { label: { show: true, color: '#fff8e8', formatter: p => `${shortProv(p.name)} · ${fmt(p.value)} ${unit()}` } } },
      { name: '省份标注', type: 'scatter', coordinateSystem: 'geo', z: 2.5, silent: true, symbolSize: 1, data: provLabelData, itemStyle: { opacity: 0 }, labelLayout: { hideOverlap: true } },
      { name: '距离线', type: 'lines', coordinateSystem: 'geo', z: 2, silent: true, data: lineData, polyline: false },
      { name: '工厂', type: 'scatter', coordinateSystem: 'geo', z: 3, data: plantData, cursor: 'pointer', labelLayout: { hideOverlap: true } },
      { name: '新增项目', type: 'scatter', coordinateSystem: 'geo', z: 4, data: projData, cursor: 'pointer', labelLayout: { hideOverlap: true } },
      { name: '目标点', type: 'scatter', coordinateSystem: 'geo', z: 5, silent: true, data: [{ value: [T.lon, T.lat], symbolSize: 8, itemStyle: { color: COL.red, borderColor: '#fff1e8', borderWidth: 1.5 } }] },
      { name: '目标区域', type: 'effectScatter', coordinateSystem: 'geo', z: 5.5, data: targetData, showEffectOn: 'render', rippleEffect: { scale: 2.2, brushType: 'stroke', period: 4 }, cursor: 'pointer' }
    ]
  }, true);
}

function toggleLayer(k) {
  state[k] = !state[k];
  const id = k === 'lines' ? 'tglLines' : k === 'projects' ? 'tglProj' : 'tglLabels';
  const el = document.getElementById(id);
  if (el) el.classList.toggle('on', state[k]);
  renderMap();
}
function setProc(p) {
  state.proc = p;
  document.querySelectorAll('[data-proc]').forEach(b => b.classList.toggle('on', b.dataset.proc === p));
  renderMap(); renderSide();
}
function resetView() {
  state.co = new Set((D.companies || []).map(c => c.id));
  state.proc = 'all'; state.prov = null;
  state.lines = true; state.projects = true; state.labels = true;
  state.mproc = 'all'; state.q = ''; state.onlyNew = false; state.sort = { key: 'capacity', dir: -1 }; state.seg = 'all';
  const q = document.getElementById('q'); if (q) q.value = '';
  const on = document.getElementById('onlyNew'); if (on) on.checked = false;
  document.querySelectorAll('[data-proc]').forEach(b => b.classList.toggle('on', b.dataset.proc === 'all'));
  document.querySelectorAll('[data-mproc]').forEach(b => b.classList.toggle('on', b.dataset.mproc === 'all'));
  ['tglLines', 'tglProj', 'tglLabels'].forEach(id => { const e = document.getElementById(id); if (e) e.classList.add('on'); });
  syncChips(); renderMatrix(); renderMap(); renderSide(); syncProvSel(); setSeg('all');
  if (mapChart) mapChart.setOption({ geo: { center: (M.map_center || [107.5, 35.2]), zoom: M.map_zoom || 1.08 } });
  toast('已重置视图');
}

/* ============================================================
   SIDE PANEL
   ============================================================ */
function sideHTML(prov) {
  if (!prov) {
    const plants = filteredPlants();
    const cap = plants.reduce((s, p) => s + p.capacity, 0);
    const cos = new Set(plants.map(p => p.company_id));
    const provAgg = {};
    plants.forEach(p => {
      const a = provAgg[p.province] || (provAgg[p.province] = { province: p.province, capacity: 0, processes: {} });
      a.capacity += p.capacity; a.processes[p.process] = (a.processes[p.process] || 0) + p.capacity;
    });
    const top = Object.values(provAgg).sort((a, b) => b.capacity - a.capacity).slice(0, 6);
    const bands = Object.fromEntries((D.bands || []).map(b => [b.band, 0]));
    plants.forEach(p => { bands[p.band] = (bands[p.band] || 0) + p.capacity; });
    const within = (km) => plants.filter(p => p.km <= km).reduce((s, p) => s + p.capacity, 0);
    const proj = (D.projects || []).filter(p => p.year >= TARGET_YEAR && cos.has(p.company_id) && (state.proc === 'all' || p.process === state.proc));
    const projCap = proj.reduce((s, p) => s + p.capacity, 0);
    const filtered = state.co.size !== D.total_companies || state.proc !== 'all';
    const targetCap = (provAgg[PROV] || {}).capacity || 0;
    const note = filtered
      ? `当前图层：<b>${cos.size} 家企业 / ${plants.length} 座工厂 / ${fmt(cap)} 万吨</b>；${PROV}本地 ${fmt(targetCap)} 万吨。下方排名仅对当前筛选成立。`
      : (D.narrative.national_note || '先看样本内密集区与目标区域周边分层。');
    return `<div class="s-mini">
      <div><div class="k">样本在产</div><div class="v">${fmt(cap)}<small>${unit()}</small></div></div>
      <div><div class="k">企业与工厂</div><div class="v">${cos.size}<small>家 / ${plants.length} 厂</small></div></div>
      <div><div class="k">800km 内</div><div class="v">${fmt(within(800))}<small>${unit()}</small></div></div>
      <div><div class="k">${TARGET_YEAR}+ 公开新增</div><div class="v">${fmt(projCap)}<small>万吨毛增量</small></div></div>
    </div>
    <div class="s-note">${note}</div>
    <div class="s-label">省级供给 TOP 6</div>
    ${top.map(p => `<div class="s-plant"><span><b>${p.province}</b> <span style="color:#8fa79c">${Object.entries(p.processes).sort((a, b) => b[1] - a[1])[0][0]}</span></span><span class="r">${fmt(p.capacity)} 万吨</span></div>`).join('')}
    <div class="s-label">到${CITY}距离带</div>
    ${Object.entries(bands).map(([b, v]) => `<div class="s-plant"><span>${b}</span><span class="r">${fmt(v)} 万吨</span></div>`).join('')}
    <div class="s-label">怎么读</div>
    <div class="s-note" style="border-left-color:#6fa8c7">${D.narrative.how_to_read || '虚线越密，说明目标区域越依赖远距离调入。'}</div>`;
  }
  const info = provInfo(prov);
  const local = (D.plants || []).filter(p => p.province === prov);
  const outside = (D.plants || []).filter(p => p.province !== prov).sort((a, b) => a.km - b.km).slice(0, 3);
  const prospectList = (D.prospect_by_prov[prov] || []);
  const demand = (D.demand_by_prov && D.demand_by_prov[prov]) || '需求线索待补；本地供给判断仅基于样本产能。';
  const capColor = info.capacity >= 400 ? '#e0b16b' : info.capacity >= 200 ? '#8ec7b3' : info.capacity > 0 ? '#6fa8c7' : '#8fa79c';
  return `<div class="s-mini">
      <div><div class="k">本地在产</div><div class="v" style="color:${capColor}">${fmt(info.capacity)}<small>${unit()}</small></div></div>
      <div><div class="k">工厂 / 企业</div><div class="v">${info.plants}<small>座 / ${info.n_companies} 家</small></div></div>
      <div><div class="k">到${CITY}最近</div><div class="v">${info.km_min == null ? '—' : fmt(info.km_min)}${info.km_min == null ? '' : '<small>km</small>'}</div></div>
      <div><div class="k">潜客样本</div><div class="v">${info.prospect_count}<small>家</small></div></div>
    </div>
    <div class="s-note">${info.capacity ? `<b>${info.judge}</b> · ${esc(info.dominant)}主导。` : '<b>本地无在产样本</b>。'} ${esc(demand)}</div>
    <div class="s-label">本省在产工厂</div>
    ${local.length ? local.map(p => `<div class="s-plant" onclick="openPlant('${p.id}')" style="cursor:pointer"><span><b>${esc(p.company_short || p.company)}</b> · ${esc(p.name)}<br><span style="color:#8fa79c;font-size:10px">${esc(p.process)} · ${esc(p.city)}</span></span><span class="r">${fmt(p.capacity)} 万吨<br>${fmt(p.km)} km</span></div>`).join('') : `<div class="s-empty">本省无在产${esc(PRODUCT)}工厂；供给来自省外调入。</div>`}
    <div class="s-label">最近的外省供给</div>
    ${outside.map(p => `<div class="s-plant" onclick="openPlant('${p.id}')" style="cursor:pointer"><span><b>${esc(p.company_short || p.company)}</b> · ${esc(p.name)}<br><span style="color:#8fa79c;font-size:10px">${esc(p.province)} ${esc(p.city)}</span></span><span class="r">${fmt(p.km)} km<br>${fmt(p.capacity)} 万吨</span></div>`).join('')}
    <div class="s-label">本地潜客</div>
    ${prospectList.length ? prospectList.slice(0, 3).map(cu => `<div class="s-plant" onclick="openProspect('${cu.id}')" style="cursor:pointer"><span><b>${esc(cu.short || cu.name)}</b><br><span style="color:#8fa79c;font-size:10px">${esc(cu.segment)} · ${esc(cu.scale)}</span></span><span class="r">${esc(cu.priority)}</span></div>`).join('') : `<div class="s-empty">${esc(D.narrative.prospect_scope_note || '本演示只内置目标省潜客样本；正式版接入潜客库后可按省展开。')}</div>`}
    <div class="s-label">销售解读</div>
    <div class="s-note" style="border-left-color:#6fa8c7">${info.capacity >= 300 ? '本地供给密集，进入要以成本/指标/服务差异化，单纯拼价格空间小。' : info.capacity > 0 ? '本地有供给但不够厚，适合做“第二供应商/双源”切入。' : '本地无在产，客户依赖外省调入；近距仓储/前置库存是切入口。'}</div>`;
}

function renderSide() {
  const title = document.getElementById('sideTitle');
  const sub = document.getElementById('sideSub');
  const tag = document.getElementById('sideTag');
  const body = document.getElementById('sideBody');
  const cta = document.getElementById('sideCta');
  if (!title) return;
  if (!state.prov) {
    title.textContent = state.co.size === D.total_companies && state.proc === 'all' ? '全国样本' : '当前图层';
    const fplants = filteredPlants();
    const fcos = new Set(fplants.map(p => p.company_id));
    sub.textContent = `${fcos.size} 家企业 · ${fplants.length} 座工厂 · ${fmt(fplants.reduce((s, p) => s + p.capacity, 0))} ${unit()}`;
    tag.textContent = 'OVERVIEW';
    body.innerHTML = sideHTML(null);
    cta.textContent = `查看${PROV}潜客样本 →`;
    cta.onclick = () => showProspects(null);
    return;
  }
  const info = provInfo(state.prov);
  title.textContent = state.prov;
  sub.textContent = `${info.plants} 座工厂 · ${fmt(info.capacity)} ${unit()} · 到${CITY}最近 ${fmt(info.km_min)} km`;
  tag.textContent = info.capacity >= 300 ? 'DENSE' : info.capacity > 0 ? 'THIN' : 'BLANK';
  body.innerHTML = sideHTML(state.prov);
  if (info.prospect_count) {
    cta.textContent = `查看${state.prov}潜客 ${info.prospect_count} 家 →`;
    cta.onclick = () => showProspects(state.prov);
  } else {
    cta.textContent = '本演示仅内置目标省潜客';
    cta.onclick = () => showProspects('__none__');
  }
}

function selectProv(name) {
  if (!name) return;
  state.prov = (state.prov === name) ? null : name;
  renderSide(); renderMap(); syncProvSel();
  if (state.prov) {
    const el = document.querySelector(`#provTable tr[data-prov="${state.prov}"]`);
    if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
}
function syncProvSel() {
  document.querySelectorAll('#provTable tbody tr').forEach(tr => tr.classList.toggle('sel', tr.dataset.prov === state.prov));
}
function showProspects(prov) {
  if (prov === '__none__' || (prov && !(D.prospect_by_prov[prov] || []).length)) {
    toast(D.narrative.prospect_scope_note || '本演示只内置目标省潜客样本；正式版可按省接入潜客库');
    return;
  }
  const sec = document.getElementById('prospectsec');
  if (sec) sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
  setSeg('all');
  if (prov) filterProspectsByProv(prov);
  setTimeout(() => toast(`已定位到${prov || PROV}潜客样本`), 350);
}
function filterProspectsByProv(prov) {
  const has = prov && (D.prospect_by_prov[prov] || []).length;
  document.querySelectorAll('#prospectTable tbody tr').forEach(tr => {
    tr.style.display = (!prov || tr.dataset.prov === prov) ? '' : 'none';
  });
  if (!has) document.querySelectorAll('#prospectTable tbody tr').forEach(tr => { tr.style.display = 'none'; });
  const n = [...document.querySelectorAll('#prospectTable tbody tr')].filter(tr => tr.style.display !== 'none').length;
  const el = document.getElementById('pcount'); if (el) el.textContent = `${n} 家`;
}
function syncProvTable() {
  document.querySelectorAll('#provTable tbody tr').forEach(tr => { tr.onclick = () => selectProv(tr.dataset.prov); });
}

/* ============================================================
   CHARTS
   ============================================================ */
function initCharts() {
  const mk = id => { const el = document.getElementById(id); return el ? echarts.init(el, null, { renderer: RENDERER }) : null; };
  chProv = mk('chProv'); chBand = mk('chBand'); chProc = mk('chProc');
  renderProvChart(); renderBandChart(); renderProcChart();
  window.addEventListener('resize', () => { chProv && chProv.resize(); chBand && chBand.resize(); chProc && chProc.resize(); });
}
function renderProvChart() {
  if (!chProv) return;
  const rows = (D.provs || []).filter(p => p.capacity > 0).slice(0, 12).slice().reverse();
  const max = Math.max(...rows.map(p => p.capacity), 1);
  chProv.setOption({
    grid: { left: 58, right: 54, top: 12, bottom: 18 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: '#102a22', borderColor: 'rgba(224,177,107,.3)', textStyle: { color: '#f3ecda', fontSize: 11 },
      formatter: ps => { const p = rows[ps[0].dataIndex]; return `<b>${p.province}</b><br>样本在产 <b>${fmt(p.capacity)}</b> ${unit()}<br>${p.plants} 厂 · ${p.n_companies} 家 · ${esc(p.dominant)}主导<br><span style="color:#e0b16b">点击查看区域 →</span>`; } },
    xAxis: { type: 'value', max: Math.ceil(max / 100) * 100, axisLabel: { color: '#8b958e', fontSize: 10 }, splitLine: { lineStyle: { color: '#eee7da' } }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'category', data: rows.map(p => p.province), axisLabel: { color: '#3b4a43', fontSize: 11, fontWeight: 600 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: 'bar', barWidth: 15, data: rows.map(p => ({ value: p.capacity, itemStyle: { color: p.province === PROV ? '#d9a441' : procColor(p.dominant), borderRadius: [0, 4, 4, 0], borderColor: p.province === PROV ? '#a23b2a' : 'transparent', borderWidth: p.province === PROV ? 1.5 : 0 } })), label: { show: true, position: 'right', color: '#5d6b63', fontSize: 10, fontWeight: 600, formatter: p => fmt(p.value) }, cursor: 'pointer' }]
  });
  chProv.off('click'); chProv.on('click', p => { if (p.name) selectProv(p.name); });
}
function renderBandChart() {
  if (!chBand) return;
  const labels = (D.bands || []).map(b => bandShort(b.band));
  const vals = (D.bands || []).map(b => b.capacity);
  const colors = ['#a23b2a', '#2f6f8f', '#d9a441', '#b4642d', '#8c7a5b'];
  const ymax = Math.max(10, Math.ceil(Math.max(...vals, 1) / 100) * 100);
  chBand.setOption({
    grid: { left: 38, right: 10, top: 22, bottom: 22 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: '#102a22', borderColor: 'rgba(224,177,107,.3)', textStyle: { color: '#f3ecda', fontSize: 11 }, formatter: ps => `${D.bands[ps[0].dataIndex].band}<br><b>${fmt(ps[0].value)}</b> ${unit()}` },
    xAxis: { type: 'category', data: labels, axisLabel: { color: '#77847c', fontSize: 10 }, axisLine: { lineStyle: { color: '#e0d7c7' } }, axisTick: { show: false } },
    yAxis: { type: 'value', max: ymax, axisLabel: { color: '#9aa59e', fontSize: 9 }, splitLine: { lineStyle: { color: '#eee7da' } }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: 'bar', barWidth: 28, data: vals.map((v, i) => ({ value: v, itemStyle: { color: colors[i % colors.length], borderRadius: [4, 4, 0, 0], opacity: v === 0 ? .25 : 1 } })), label: { show: true, position: 'top', color: '#3b4a43', fontSize: 10, fontWeight: 700, formatter: p => p.value === 0 ? '0' : fmt(p.value) } }]
  });
}
function renderProcChart() {
  if (!chProc) return;
  const data = (M.processes || []).map(p => ({ name: p.name, value: D.process_totals[p.name] || 0, itemStyle: { color: p.color } })).filter(x => x.value > 0);
  chProc.setOption({
    tooltip: { trigger: 'item', backgroundColor: '#102a22', borderColor: 'rgba(224,177,107,.3)', textStyle: { color: '#f3ecda', fontSize: 11 }, formatter: p => `${p.name}<br><b>${fmt(p.value)}</b> ${unit()} · ${p.percent}%` },
    series: [{ type: 'pie', radius: ['58%', '78%'], center: ['50%', '50%'], avoidLabelOverlap: true, itemStyle: { borderColor: '#fffdf8', borderWidth: 3 }, label: { show: true, formatter: p => `${p.name}\n${fmt(p.value)}`, color: '#3b4a43', fontSize: 10, lineHeight: 13 }, labelLine: { length: 8, length2: 6, lineStyle: { color: '#c9bfae' } }, data }],
    graphic: [{ type: 'text', left: 'center', top: '42%', style: { text: `${fmt(D.total_cap)}\n${unit()}`, textAlign: 'center', fill: '#13231d', fontSize: 15, fontWeight: 700, lineHeight: 18 } }]
  });
  chProc.off('click'); chProc.on('click', p => { if (p.name) setProc(p.name); });
}

/* ============================================================
   PROSPECT SEGMENTS
   ============================================================ */
function setSeg(seg) {
  state.seg = seg;
  document.querySelectorAll('[data-seg]').forEach(b => b.classList.toggle('on', b.dataset.seg === seg));
  document.querySelectorAll('#prospectTable tbody tr').forEach(tr => {
    tr.style.display = (seg === 'all' || tr.dataset.seg === seg) ? '' : 'none';
  });
  const n = [...document.querySelectorAll('#prospectTable tbody tr')].filter(tr => tr.style.display !== 'none').length;
  const el = document.getElementById('pcount'); if (el) el.textContent = `${n} 家`;
}

/* ============================================================
   DRAWER
   ============================================================ */
function openDrawer(html, lab) {
  const d = document.getElementById('drawer');
  if (!d) return;
  document.getElementById('drawerBody').innerHTML = html;
  document.getElementById('drawerLab').textContent = lab || 'DETAIL';
  d.classList.add('open'); d.setAttribute('aria-hidden', 'false'); document.body.style.overflow = 'hidden';
}
function closeDrawer() {
  const d = document.getElementById('drawer');
  if (!d) return;
  d.classList.remove('open'); d.setAttribute('aria-hidden', 'true'); document.body.style.overflow = '';
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });

function sourceBlock(ids) {
  const uniq = [...new Set(ids || [])];
  if (!uniq.length) return `<div class="src">来源：企业公开业务信息；未找到可核实的${esc(PRODUCT)}产能/规模披露。</div>`;
  return `<div class="src">来源：${uniq.map(id => {
    const s = SRC[id];
    return s ? `<a href="${s.url}" target="_blank" rel="noopener">${id} ${esc(s.org)} · ${esc(s.title)}</a>` : id;
  }).join('<br>')}</div>`;
}

function openCompany(id) {
  const c = CO[id];
  if (!c) return;
  const plants = (c.plants || []).map(p => `<div class="item" onclick="openPlant('${p.id}')" style="cursor:pointer">
    <span class="r">${fmt(p.capacity)} 万吨 · ${fmt(p.km)} km</span>
    <b>${esc(p.name)}</b><br><span class="muted">${esc(p.province)} ${esc(p.city)} · ${esc(p.process)} · ${esc(p.cap_year || '')}</span>
  </div>`).join('');
  const projects = (c.projects || []).map(p => `<div class="item">
    <span class="r">${fmt(p.capacity)} 万吨 · ${esc(p.status)}</span>
    <b>${esc(p.name)}</b><br><span class="muted">${esc(p.location)} · ${esc(p.kind)} · ${esc(p.timing)}</span>
  </div>`).join('') || `<div class="p muted">无公开新增/在建${esc(PRODUCT)}项目。</div>`;
  openDrawer(`
    <h2>${esc(c.name)}</h2>
    <div class="sub">${esc(c.ticker || '非上市')}${c.alias ? ' · ' + esc(c.alias) : ''} · ${esc(c.process)} · ${esc(c.hq || '')}</div>
    <div class="kpis2">
      <div><div class="k">${esc(PRODUCT)}产能</div><div class="v">${fmt(c.capacity)}<small> 万吨/年</small></div></div>
      <div><div class="k">${esc(M.output_year || '最新')} 产量</div><div class="v">${c.output == null ? '—' : fmt(c.output)}<small>${c.output == null ? ' 未披露' : ' 万吨'}</small></div></div>
      <div><div class="k">在产工厂</div><div class="v">${c.plant_count}<small> 座</small></div></div>
      <div><div class="k">到${CITY}最近</div><div class="v">${fmt(c.min_km)}<small> km</small></div></div>
    </div>
    <div class="p"><b>主营：</b>${esc(c.products || '—')}</div>
    <h4>在产工厂</h4><div class="list">${plants}</div>
    <h4>新增 / 在建</h4><div class="list">${projects}</div>
    <h4>区域覆盖线索 <span class="tag infer">D 推断</span></h4>
    <div class="p">${esc(c.coverage || '—')}</div>
    <div class="p muted" style="margin-top:6px">覆盖线索基于工厂位置、公开业务范围与物流常识推断，不是企业披露的销售分区。</div>
    ${sourceBlock(c.source_ids)}
  `, 'COMPANY · 企业明细');
}

function openPlant(id) {
  const p = PL[id];
  if (!p) return;
  const c = CO[p.company_id];
  openDrawer(`
    <h2>${esc(p.name)}</h2>
    <div class="sub">${esc(p.company)} · ${esc(p.province)} ${esc(p.city)} · ${esc(p.process)}</div>
    <div class="kpis2">
      <div><div class="k">${esc(PRODUCT)}产能</div><div class="v">${fmt(p.capacity)}<small> 万吨/年</small></div></div>
      <div><div class="k">产能数据年</div><div class="v">${esc(p.cap_year || '—')}</div></div>
      <div><div class="k">到${CITY}</div><div class="v">${fmt(p.km)}<small> km</small></div></div>
      <div><div class="k">距离带</div><div class="v" style="font-size:13px">${esc(p.band)}</div></div>
    </div>
    <div class="p"><b>产品：</b>${esc(p.products || '—')}</div>
    <div class="p" style="margin-top:5px"><b>备注：</b>${esc(p.note || '—')}</div>
    <h4>所属企业</h4>
    <div class="item" onclick="openCompany('${c.id}')" style="cursor:pointer"><b>${esc(c.name)}</b> · ${fmt(c.capacity)} 万吨/年 · ${esc(c.process)}<br><span class="muted">点击查看企业全部工厂与新增项目 →</span></div>
    <h4>数据等级</h4><div class="p"><span class="grade g${esc(p.grade)}"><b></b>${gradeLabel(p.grade)}</span></div>
    ${sourceBlock(p.source_ids)}
  `, 'PLANT · 工厂明细');
}

function openProject(id) {
  const p = PR[id];
  if (!p) return;
  const c = CO[p.company_id];
  openDrawer(`
    <h2>${esc(p.name)}</h2>
    <div class="sub">${esc(p.company)} · ${esc(p.location)} · ${esc(p.process)}</div>
    <div class="kpis2">
      <div><div class="k">规模</div><div class="v">${fmt(p.capacity)}<small> 万吨/年</small></div></div>
      <div><div class="k">性质</div><div class="v" style="font-size:14px">${esc(p.kind)}</div></div>
      <div><div class="k">状态</div><div class="v" style="font-size:14px">${esc(p.status)}</div></div>
      <div><div class="k">净增判断</div><div class="v" style="font-size:13px">${esc(p.net)}</div></div>
    </div>
    <div class="p"><b>时间：</b>${esc(p.timing)}</div>
    <h4>对目标区域的影响</h4><div class="p">${esc(p.impact)}</div>
    <h4>所属企业</h4>
    <div class="item" onclick="openCompany('${c.id}')" style="cursor:pointer"><b>${esc(c.name)}</b> · ${fmt(c.capacity)} 万吨/年<br><span class="muted">点击查看企业 →</span></div>
    ${sourceBlock(p.source_ids)}
  `, 'PROJECT · 新增项目');
}

function openProspect(id) {
  const p = CU[id];
  if (!p) return;
  const src = p.source_ids && p.source_ids.length ? sourceBlock(p.source_ids) : `<div class="src">来源：企业公开业务信息；未找到可核实的${esc(PRODUCT)}用量披露。</div>`;
  openDrawer(`
    <h2>${esc(p.name)}</h2>
    <div class="sub">${esc(p.city)} · ${esc(p.segment)} · 优先级 ${esc(p.priority)}</div>
    <div class="kpis2">
      <div><div class="k">公开规模</div><div class="v" style="font-size:13px;line-height:1.5">${esc(p.scale)}</div></div>
      <div><div class="k">${esc(M.dose_label || '用量级')}</div><div class="v" style="font-size:13px;line-height:1.5">${esc(p.ash || p.dose || '—')}</div></div>
    </div>
    <div class="p"><b>${esc(M.use_label || '使用场景')}：</b>${esc(p.scene || '—')}</div>
    <h4>为什么优先</h4><div class="p">${esc(p.why || '—')}</div>
    <h4>下一步动作</h4><div class="p">${esc(p.next || '—')}</div>
    <h4>数据等级</h4><div class="p"><span class="grade g${esc(p.grade)}"><b></b>${gradeLabel(p.grade)}</span></div>
    ${src}
  `, 'PROSPECT · 潜客明细');
}

/* ============================================================
   BOOT
   ============================================================ */
(function boot() {
  document.querySelectorAll('#matrix th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const k = th.dataset.sort;
      if (state.sort.key === k) state.sort.dir *= -1;
      else state.sort = { key: k, dir: k === 'name' || k === 'process' || k === 'grade' ? 1 : -1 };
      renderMatrix();
    });
  });
  renderMatrix(); syncChips(); syncProvTable(); initMap(); initCharts(); setSeg('all'); renderSide();
  setTimeout(() => mapChart && mapChart.resize(), 250);
})();
