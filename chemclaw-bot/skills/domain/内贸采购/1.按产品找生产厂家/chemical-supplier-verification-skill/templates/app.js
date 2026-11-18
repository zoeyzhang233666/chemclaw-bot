/* 化工品生产厂家核验池 · 交互层 */
(function () {
  'use strict';

  const META = (DATA && DATA.meta) || {};
  const SPEC_COUNT = ((DATA && DATA.specs) || []).length || 8;
  const DEST = META.destination_short || "收货地";
  const PRODUCT = META.product_short || META.product || "产品";
  const CAP_UNIT = META.capacity_unit || "万吨/年";
  const QTY_UNIT = META.quantity_unit || "吨";
  const APPLICATION = META.application || "下游";
  const PACKAGING = (DATA.rfq && DATA.rfq.packaging) || "包装/运输方式";
  const nearestCity = (c) => c.nearest_city || (((c.plants || []).find((p) => p.name === c.nearest_plant) || (c.plants || [])[0] || {}).city) || "";
  const specGaps = (c) => (c.spec_gaps || (c.spec_rows || []).filter((r) => r.status !== "部分公开").map((r) => r.label));
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const fmt = (n) => (n === null || n === undefined || n === '') ? '—' : Number(n).toLocaleString('zh-CN');
  const esc = (v) => String(v === null || v === undefined ? '' : v).replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  const tierClass = (t) => t === '优先谈判' ? 't1' : (t === '重点备选' ? 't2' : 't3');
  const levelClass = (l) => l && l.indexOf('A') > -1 ? 'a' : (l && l.indexOf('B') > -1 ? 'b' : (l && l.indexOf('C') > -1 ? 'c' : 'd'));
  const statusClass = (s) => s === '部分公开' ? 'part' : (s === '未公开' ? 'miss' : 'na');
  const initial = (name) => {
    const clean = String(name).replace(/（.*?）/g, '').replace(/\(.*?\)/g, '');
    return clean.slice(0, 2);
  };
  const byId = (id) => DATA.companies.find((c) => c.id === id);

  const state = {
    identity: 'all', region: 'all', scale: 'all', distance: 'all', evidence: 'all',
    sort: 'composite', search: '', view: 'table', compare: [], currentId: null, currentTab: 'overview'
  };

  /* ---------------- table / cards ---------------- */
  function filtered() {
    let arr = DATA.companies.slice();
    if (state.identity === 'trader') return [];
    arr = arr.filter((c) => {
      if (state.region !== 'all' && !c.regions.includes(state.region)) return false;
      if (state.scale !== 'all') {
        const cap = c.capacity;
        if (state.scale === 'xl' && cap < 300) return false;
        if (state.scale === 'lg' && (cap < 100 || cap >= 300)) return false;
        if (state.scale === 'md' && (cap < 50 || cap >= 100)) return false;
        if (state.scale === 'sm' && cap >= 50) return false;
      }
      if (state.distance !== 'all') {
        const d = c.distance_km;
        if (state.distance === 'near' && d > 300) return false;
        if (state.distance === 'mid' && (d <= 300 || d > 800)) return false;
        if (state.distance === 'far' && (d <= 800 || d > 1500)) return false;
        if (state.distance === 'xfar' && d <= 1500) return false;
      }
      if (state.evidence === 'a' && !c.evidence.some((e) => e.level === '直接-A')) return false;
      if (state.evidence === 'b' && !c.evidence.some((e) => e.level === '直接-B')) return false;
      if (state.search) {
        const q = state.search.toLowerCase();
        const hay = [c.name, c.full_name || c.full, c.products, c.process, c.ticker, c.hq, c.nearest_city]
          .concat(c.plants.map((p) => p.name + ' ' + p.address + ' ' + p.city))
          .join(' ').toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });
    const key = state.sort;
    arr.sort((a, b) => {
      if (key === 'distance') return a.distance_km - b.distance_km;
      if (key === 'capacity') return b.capacity - a.capacity;
      if (key === 'certainty') return b.certainty - a.certainty;
      if (key === 'spec') return b.spec_score - a.spec_score;
      return b.composite - a.composite;
    });
    return arr;
  }

  function evidenceDots(c) {
    const a = c.evidence.filter((e) => e.level === '直接-A').length;
    const b = c.evidence.filter((e) => e.level === '直接-B').length;
    const cc = c.evidence.filter((e) => e.level === '间接-C').length;
    let html = '<div class="ev-dots">';
    for (let i = 0; i < Math.min(a, 5); i++) html += '<i></i>';
    for (let i = 0; i < Math.min(b, 3); i++) html += '<i class="b"></i>';
    for (let i = 0; i < Math.min(cc, 2); i++) html += '<i class="c"></i>';
    html += '<span>A' + a + ' · B' + b + '</span></div>';
    return html;
  }

  function rowHTML(c) {
    const rankCls = c.rank === 1 ? 'top' : (c.rank === 2 ? 'p2' : (c.rank === 3 ? 'p3' : ''));
    const active = state.compare.includes(c.id) ? ' active' : '';
    return `<tr data-id="${c.id}" class="${state.compare.includes(c.id) ? 'selected' : ''}">
      <td><span class="rank ${rankCls}">${c.rank}</span></td>
      <td><div class="comp-cell"><div class="avatar">${esc(initial(c.name))}</div><div><div class="nm">${esc(c.name)}</div><div class="meta">${esc(c.ticker === '—' ? '非上市' : c.ticker)} · ${esc(c.process)}</div></div></div></td>
      <td><span class="badge teal">生产厂家</span><div style="margin-top:3px"><span class="tier ${tierClass(c.tier)}">${esc(c.tier)}</span></div></td>
      <td><div style="font-weight:600;font-size:11px">${esc(c.nearest_plant)}</div><div style="font-size:9px;color:var(--muted);margin-top:2px">${esc(nearestCity(c))}</div></td>
      <td><div class="cap">${fmt(c.capacity)}<span>${CAP_UNIT}</span></div><div style="font-size:9px;color:var(--muted)">${esc(c.capacity_year)}</div></td>
      <td><div class="dist">${fmt(c.distance_km)} km<span>${esc(c.distance_band)}</span></div></td>
      <td><div class="spec-meter"><div class="m"><i style="width:${Math.round(c.spec_open / SPEC_COUNT * 100)}%"></i></div><b>${c.spec_open}/${SPEC_COUNT}</b></div><div style="font-size:9px;color:var(--muted);margin-top:3px">公开可对标</div></td>
      <td>${evidenceDots(c)}</td>
      <td><span class="score-pill">${c.composite}<small>/100</small></span></td>
      <td><div class="row-actions"><button class="mini-btn" data-open="${c.id}">详情</button><button class="mini-btn${active}" data-compare="${c.id}">${active ? '已选' : '对比'}</button></div></td>
    </tr>`;
  }

  function cardHTML(c) {
    const active = state.compare.includes(c.id);
    return `<article class="card pool-card" data-id="${c.id}">
      <div class="pc-top"><span class="rank ${c.rank === 1 ? 'top' : ''}">${c.rank}</span><span class="tier ${tierClass(c.tier)}">${esc(c.tier)}</span><span class="score-pill" style="margin-left:auto">${c.composite}<small>/100</small></span></div>
      <div class="pc-name">${esc(c.name)}</div>
      <div class="pc-meta">${esc(c.full_name || c.full)} · ${esc(c.process)}</div>
      <div class="pc-stats">
        <div><b>${fmt(c.capacity)}</b><span>${CAP_UNIT}</span></div>
        <div><b>${fmt(c.distance_km)}</b><span>km 到${DEST}</span></div>
        <div><b>${c.spec_open}/${SPEC_COUNT}</b><span>规格公开</span></div>
      </div>
      <div class="pc-line"><span>最近基地</span><b>${esc(c.nearest_plant)}</b></div>
      <div class="pc-line"><span>证据</span><b>${c.evidence.filter(e => e.level.indexOf('直接') === 0).length} 条直接</b></div>
      <div class="pc-actions"><button class="btn btn-primary btn-sm" data-open="${c.id}">查看核验</button><button class="mini-btn${active ? ' active' : ''}" data-compare="${c.id}">${active ? '已选' : '加入对比'}</button></div>
    </article>`;
  }

  function renderTable() {
    const arr = filtered();
    const body = $('#poolBody');
    const empty = $('#emptyState');
    if (state.identity === 'trader') {
      body.innerHTML = '';
      empty.style.display = 'block';
      empty.innerHTML = '<b>贸易商在 04 单独列出</b>候选池只放生产厂家；贸易商、代理与仅工商样本请查看“贸易商与代理”区。';
    } else if (arr.length === 0) {
      body.innerHTML = '';
      empty.style.display = 'block';
      empty.innerHTML = '<b>没有匹配结果</b>放宽筛选或清空搜索词再试。';
    } else {
      empty.style.display = 'none';
      body.innerHTML = arr.map(rowHTML).join('');
    }
    const plants = arr.reduce((n, c) => n + c.plants.length, 0);
    $('#resultCount').textContent = state.identity === 'trader' ? '0 家 · 贸易商见 04' : `${arr.length} 家 · ${plants} 个基地`;
    if (state.view === 'card') {
      $('#cardView').innerHTML = arr.length
        ? `<div class="pool-cards">${arr.map(cardHTML).join('')}</div>`
        : `<div class="card" style="padding:40px 20px;text-align:center;color:var(--muted)"><b style="display:block;font-family:var(--serif);font-size:19px;color:var(--ink);margin-bottom:4px">没有匹配结果</b>放宽筛选或清空搜索词再试。</div>`;
      $('#cardView').style.display = 'block';
      $('#tableView').style.display = 'none';
    } else {
      $('#cardView').innerHTML = '';
      $('#cardView').style.display = 'none';
      $('#tableView').style.display = 'block';
    }
    $$('#poolBody [data-compare]').forEach((b) => {
      b.onclick = (ev) => { ev.stopPropagation(); toggleCompare(b.dataset.compare); };
    });
    $$('#poolBody [data-open]').forEach((b) => {
      b.onclick = (ev) => { ev.stopPropagation(); openDrawer(b.dataset.open); };
    });
    $$('#poolBody tr').forEach((tr) => {
      tr.onclick = (ev) => { if (!ev.target.closest('button')) openDrawer(tr.dataset.id); };
    });
    $$('#cardView [data-open]').forEach((b) => { b.onclick = () => openDrawer(b.dataset.open); });
    $$('#cardView [data-compare]').forEach((b) => { b.onclick = () => toggleCompare(b.dataset.compare); });
  }

  /* ---------------- scatter ---------------- */
  function renderScatter() {
    const svg = $('#scatter');
    if (!svg) return;
    const W = 760, H = 380, L = 46, R = 18, T = 18, B = 38;
    const xMax = 1900, yMin = 65, yMax = 95;
    const px = (km) => L + (Math.min(km, xMax) / xMax) * (W - L - R);
    const py = (v) => H - B - ((Math.max(yMin, Math.min(yMax, v)) - yMin) / (yMax - yMin)) * (H - T - B);
    const color = (t) => t === '优先谈判' ? '#0f766e' : (t === '重点备选' ? '#d97706' : '#8b97a7');
    let s = '';
    for (let v = 65; v <= 95; v += 5) {
      s += `<line class="grid" x1="${L}" y1="${py(v)}" x2="${W - R}" y2="${py(v)}"/>`;
      s += `<text class="axis" x="${L - 8}" y="${py(v) + 3}" text-anchor="end">${v}</text>`;
    }
    [0, 300, 600, 900, 1200, 1500, 1800].forEach((km) => {
      s += `<line class="grid" x1="${px(km)}" y1="${T}" x2="${px(km)}" y2="${H - B}"/>`;
      s += `<text class="axis" x="${px(km)}" y="${H - B + 16}" text-anchor="middle">${km === 0 ? '0' : km}</text>`;
    });
    s += `<text class="axis" x="${W / 2}" y="${H - 6}" text-anchor="middle">到${DEST}直线距离（km）</text>`;
    s += `<text class="axis" x="12" y="${T + 8}" text-anchor="start">综合分</text>`;
    DATA.companies.forEach((c) => {
      const x = px(c.distance_km), y = py(c.composite), r = 4 + Math.sqrt(c.capacity) * 0.52;
      s += `<circle class="dot" cx="${x}" cy="${y}" r="${r}" fill="${color(c.tier)}" fill-opacity=".82" data-open="${c.id}"><title>${esc(c.name)}｜${c.composite}分｜${fmt(c.capacity)}万吨｜${fmt(c.distance_km)}km</title></circle>`;
    });
    DATA.companies.slice(0, 6).forEach((c, i) => {
      const x = px(c.distance_km), y = py(c.composite);
      const anchor = x > W - 120 ? 'end' : 'start';
      const dx = anchor === 'end' ? -10 : 10;
      const dy = i % 2 === 0 ? -10 : 16;
      s += `<rect class="lab-bg" x="${x + dx - (anchor === 'end' ? 58 : 0)}" y="${y + dy - 10}" width="62" height="14" rx="4"/>`;
      s += `<text class="lab" x="${x + dx}" y="${y + dy}" text-anchor="${anchor}">${esc(c.name)}</text>`;
    });
    svg.innerHTML = s;
    $$('#scatter [data-open]').forEach((el) => { el.onclick = () => openDrawer(el.dataset.open); });
  }

  /* ---------------- drawer ---------------- */
  function openDrawer(id) {
    const c = byId(id);
    if (!c) return;
    state.currentId = id;
    state.currentTab = 'overview';
    $('#drawerRank').innerHTML = `<span class="rank ${c.rank === 1 ? 'top' : ''}" style="width:22px;height:22px;border-radius:7px;font-size:10px">${c.rank}</span><span>综合排名 / ${DATA.companies.length}</span><span>·</span><span>${esc(c.tier)}</span>`;
    $('#drawerName').textContent = c.name;
    $('#drawerFull').textContent = (c.full_name || c.full) + ' · ' + (c.ticker === '—' ? '非上市' : c.ticker) + ' · ' + c.hq;
    $('#drawerScore').textContent = c.composite;
    $('#drawerBadges').innerHTML = [
      `<span class="badge teal">生产厂家</span>`,
      `<span class="badge ${c.certainty >= 90 ? 'teal' : 'amber'}">生产确定性 ${c.certainty}</span>`,
      `<span class="badge blue">规格 ${c.spec_score}</span>`,
      `<span class="badge gray">${esc(c.process)}</span>`,
      `<span class="badge gray">${fmt(c.capacity)} ${CAP_UNIT}</span>`,
      `<span class="badge gray">${fmt(c.distance_km)} km</span>`,
      c.availability < 60 ? `<span class="badge red">外销可得性 ${c.availability}</span>` : ''
    ].join('');
    $$('#drawerTabs .drawer-tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === 'overview'));
    $('#drawerBody').innerHTML = panelOverview(c);
    $('#drawerBody').scrollTop = 0;
    $('#overlay').classList.add('show');
    $('#drawer').classList.add('show');
    document.body.style.overflow = 'hidden';
    bindDrawerActions();
  }

  function closeDrawer() {
    $('#overlay').classList.remove('show');
    $('#drawer').classList.remove('show');
    document.body.style.overflow = '';
    state.currentId = null;
  }

  function panelOverview(c) {
    const nearest = c.plants.find((p) => p.name === c.nearest_plant) || c.plants[0];
    const fy = parseInt(c.founded, 10);
    const age = Number.isFinite(fy) ? (2026 - fy) : null;
    const plants = c.plants.map((p) => `<div class="plant"><div><b>${esc(p.name)}</b><div class="addr">${esc(p.address)}</div><div class="addr">${esc(p.process)} · ${esc(p.capacity_year || p.year)} · 距${DEST} ${fmt(p.distance_km)}km</div></div><div class="right"><b>${fmt(p.capacity)}</b><span>${CAP_UNIT}</span></div></div>`).join('');
    const bars = [
      ['生产确定性', c.certainty, '35%'], ['规格匹配', c.spec_score, '30%'],
      ['规模', c.scale_score, '20%'], ['距离', c.distance_score, '15%']
    ].map(([l, v, w]) => `<div class="bs"><span>${l} <small style="color:var(--muted)">${w}</small></span><div class="b"><i style="width:${v}%"></i></div><b>${v}</b></div>`).join('');
    return `<div class="kv-grid">
        <div class="kv"><label>生产身份</label><b>生产厂家</b><span>${esc(c.process)} · ${c.plants.length} 个基地</span></div>
        <div class="kv"><label>${PRODUCT}产能</label><b>${fmt(c.capacity)} ${CAP_UNIT}</b><span>${esc(c.capacity_year)} · 样本口径</span></div>
        <div class="kv"><label>${c.output_year || "最新"} 产量</label><b>${c.output == null ? '未披露' : fmt(c.output) + ' ' + CAP_UNIT}</b><span>${esc(c.output_year)}</span></div>
        <div class="kv"><label>最近基地</label><b>${fmt(c.distance_km)} km</b><span>${esc(nearestCity(c))} · 直线距离</span></div>
        <div class="kv"><label>成立年份</label><b>${esc(c.founded)} 年${age === null ? '' : ' · ' + age + ' 年'}</b><span>${esc(c.founded_note)}</span></div>
        <div class="kv"><label>员工/规模</label><b>${c.employees ? fmt(c.employees) + ' 人' : '未披露'}</b><span>${esc(c.employees_note)}</span></div>
        <div class="kv"><label>外销可得性</label><b>${c.availability} / 100</b><span>${c.availability < 60 ? '自用比例高/外销待确认' : '需确认月度可供量'}</span></div>
        <div class="kv"><label>规格公开</label><b>${c.spec_open} / ${SPEC_COUNT} 项</b><span>0 项批次 COA</span></div>
      </div>
      <div class="note-box" style="margin:0 0 14px"><b>主营产品：</b>${esc(c.products)}。${esc(c.capacity_year)} 产能口径，产能与产量分列；外销量与长协比例未披露时，不以产能替代可供量。</div>
      <div class="subhead"><h4>生产基地与地址</h4><span>${c.plants.length} 个基地 · 坐标为近似点</span></div>
      <div class="plant-list">${plants}</div>
      <div class="note-box"><b>最近基地：</b>${esc(nearest.name)}，${esc(nearest.address)}。产能 ${fmt(nearest.capacity)} ${CAP_UNIT}；到${DEST}直线 ${fmt(nearest.distance_km)}km。直线距离不是运费，实际到厂价需物流商按${PACKAGING}、批量、港口/铁路专用线重新报价。</div>
      <div class="subhead"><h4>评分拆解</h4><span>综合 ${c.composite} / 100</span></div>
      <div class="bar-score">${bars}</div>
      <div class="note-box"><b>规模说明：</b>${esc(c.scale_note)}</div>
      <div class="subhead"><h4>优势 / 数据缺口</h4><span>不猜测填充</span></div>
      <div class="strength-grid">${c.strengths.map((x) => `<div class="strength">✓ ${esc(x)}</div>`).join('')}<div class="gap-box">⚠ ${c.gaps.map(esc).join('<br>⚠ ')}</div></div>
      <div class="drawer-actions">
        <button class="btn btn-primary btn-sm" data-action="qual">做供应商准入尽调</button>
        <button class="btn btn-ghost btn-sm" data-action="compare">${state.compare.includes(c.id) ? '移出对比' : '加入对比'}</button>
        <button class="btn btn-ghost btn-sm" data-action="copy">复制核验摘要</button>
      </div>`;
  }

  function panelEvidence(c) {
    const items = c.evidence.map((e) => {
      const cls = e.level === '直接-A' ? '' : (e.level === '直接-B' ? 'b' : 'c');
      return `<div class="ev-item ${cls}">
        <div class="ev-top"><span class="badge ${e.level === '直接-A' ? 'teal' : (e.level === '直接-B' ? 'blue' : 'amber')}">${esc(e.level)}</span><b>${esc(e.title)}</b><span class="date">${esc(e.date)}</span></div>
        <p>“${esc(e.quote)}”</p>
        <div class="proves">证明：${esc(e.proves)} · 来源：${esc(e.org)} ${e.source_id ? '· ' + esc(e.source_id) : ''}</div>
        ${e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.url)}</a>` : ''}
      </div>`;
    }).join('');
    const a = c.evidence.filter((e) => e.level === '直接-A').length;
    const b = c.evidence.filter((e) => e.level === '直接-B').length;
    const cc = c.evidence.filter((e) => e.level === '间接-C').length;
    return `<div class="note-box"><b>判定：</b>${a} 条直接-A、${b} 条直接-B、${cc} 条间接-C。生产身份成立；但“有产能”不等于“有可售量”，也不等于“批次规格合格”。</div>
      <div class="subhead"><h4>证据时间线</h4><span>${c.evidence.length} 条</span></div>
      <div class="timeline">${items}</div>
      <div class="note-box amber"><b>仍需补：</b>${c.gaps.map(esc).join('；')}。</div>
      <div class="drawer-actions"><button class="btn btn-primary btn-sm" data-action="qual">进入准入尽调</button><button class="btn btn-ghost btn-sm" data-action="compare">${state.compare.includes(c.id) ? '移出对比' : '加入对比'}</button></div>`;
  }

  function panelSpec(c) {
    const rows = c.spec_rows.map((r) => `<tr><td><b>${esc(r.label)}</b></td><td class="req">${esc(r.requirement || r.req)}</td><td><span class="status ${statusClass(r.status)}">${esc(r.status)}</span></td><td>${esc(r.public_info || r.public)}</td><td>${esc(r.gap)}</td></tr>`).join('');
    return `<div class="note-box"><b>规格结论：</b>${esc(c.spec_conclusion)} 公开标准/宣称只能用于“可对标”，不能替代批次 COA；${APPLICATION}尤其要盯关键指标（Fe₂O₃、氯化物、粒度、水分等）。</div>
      <div class="subhead"><h4>${SPEC_COUNT} 项指标逐项对照</h4><span>采购要求 vs 公开信息</span></div>
      <table class="spec-table"><thead><tr><th>指标</th><th>要求</th><th>状态</th><th>公开信息</th><th>缺口 / 动作</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="note-box amber"><b>下一步：</b>向 ${esc(c.name)} 索取连续 3 批 COA（批次号与发货批一致），并做 200kg 小试；重点记录飞料、澄清时间、色差与窑炉波动。没有批次数据前，不写“符合”。</div>
      <div class="drawer-actions"><button class="btn btn-primary btn-sm" data-action="qual">按规格做准入尽调</button><button class="btn btn-ghost btn-sm" data-action="copySpec">复制规格追问清单</button></div>`;
  }

  function panelAction(c) {
    const checklist = [
      '营业执照、生产地址与排污许可证地址一致',
      `${PRODUCT}装置产能、最新实际产量、当月排产`,
      '连续 3 批 COA（总碱量、水分、氯化物、Fe₂O₃、水不溶物、堆积密度、粒度、灼烧失量）',
      'ISO9001 / ISO14001 / ISO45001 及客户审厂报告',
      `${APPLICATION}客户案例（可脱敏）与联系人`,
      `${PACKAGING}、装车能力、日发运量、港口/铁路专用线`,
      '长协占比、检修计划、断供预案、质量罚则',
      `报价：出厂价、到${DEST}门到价、账期、最小起订量`,
      '关联交易/代理链：销售主体、授权书、收款账户一致性',
      '现场审核：装置、成品仓、化验室、发运区、批次追溯'
    ];
    const checks = checklist.map((x, i) => `<label class="check"><input type="checkbox" data-check="${i}"><span>${esc(x)}</span></label>`).join('');
    const gaps = c.gaps.map((g) => `<li>${esc(g)}</li>`).join('');
    return `<div class="note-box"><b>准入结论（基于公开信息）：</b>生产身份成立，建议进入“文件审核 + 小试 + 现场审核”三阶段；在批次 COA 与到厂价未确认前，不授予主供资格。</div>
      <div class="subhead"><h4>文件/样品/现场 10 项清单</h4><span>可勾选，生成清单</span></div>
      <div class="checklist">${checks}</div>
      <div class="subhead"><h4>该企业专属缺口</h4><span>${c.gaps.length} 项</span></div>
      <div class="gap-box" style="font-size:10.5px"><ul style="margin:0;padding-left:16px">${gaps}</ul></div>
      <div class="subhead"><h4>现场审核 6 看</h4><span>建议 1 天内完成</span></div>
      <div class="strength-grid">
        <div class="strength">看装置：实际运行负荷、检修记录、联碱/氨碱工艺与副产物。</div>
        <div class="strength">看成品仓：重质/轻质分仓、防潮、批次标识、先进先出。</div>
        <div class="strength">看化验室：Fe₂O₃、氯化物、粒度、水分是否自检，留样多久。</div>
        <div class="strength">看发运：${PACKAGING}装车、日发运量、港口/铁路专用线。</div>
        <div class="strength">看追溯：批次号—生产记录—COA—发货单能否闭环。</div>
        <div class="strength">看客户：${APPLICATION}客户名单、审厂报告、质量异议记录。</div>
      </div>
      <div class="drawer-actions"><button class="btn btn-primary btn-sm" data-action="download">生成尽调清单</button><button class="btn btn-ghost btn-sm" data-action="compare">${state.compare.includes(c.id) ? '移出对比' : '加入对比'}</button></div>`;
  }

  function renderTab(tab) {
    const c = byId(state.currentId);
    if (!c) return;
    state.currentTab = tab;
    $$('#drawerTabs .drawer-tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === tab));
    const map = { overview: panelOverview, evidence: panelEvidence, spec: panelSpec, action: panelAction };
    $('#drawerBody').innerHTML = map[tab](c);
    $('#drawerBody').scrollTop = 0;
    bindDrawerActions();
  }

  function bindDrawerActions() {
    $$('#drawerBody [data-action]').forEach((b) => {
      b.onclick = () => {
        const c = byId(state.currentId);
        if (!c) return;
        if (b.dataset.action === 'qual') openQualification(c);
        if (b.dataset.action === 'compare') { toggleCompare(c.id); renderTab(state.currentTab); }
        if (b.dataset.action === 'copy') copyText(summaryText(c)).then(() => toast('核验摘要已复制'));
        if (b.dataset.action === 'copySpec') copyText(specText(c)).then(() => toast('规格追问清单已复制'));
        if (b.dataset.action === 'download') downloadChecklist(c);
      };
    });
  }

  function summaryText(c) {
    return [
      `【${c.name}】${c.full}`,
      `生产身份：生产厂家｜${c.process}｜${c.plants.length}个基地`,
      `综合评分：${c.composite}/100（确定性${c.certainty}/规格${c.spec_score}/规模${c.scale_score}/距离${c.distance_score}）`,
      `产能：${c.capacity} ${CAP_UNIT}（${c.capacity_year}）；${c.output_year || "最新"}产量：${c.output == null ? '未披露' : c.output + '万吨'}`,
      `最近基地：${c.nearest_plant}（${nearestCity(c)}），距${DEST}直线${c.distance_km}km`,
      `规格公开：${c.spec_open}/${SPEC_COUNT}项；无公开：${specGaps(c).join('、') || '无'}；0项批次COA`,
      `优势：${c.strengths.join('；')}`,
      `缺口：${c.gaps.join('；')}`,
      `建议：${c.action}`
    ].join('\n');
  }

  function specText(c) {
    return [
      `【${c.name}｜规格追问清单】`,
      ...c.spec_rows.map((r) => `- ${r.label}：要求${r.requirement || r.req}；当前${r.status}；${r.gap}`),
      `- 请提供连续3批COA（批次号与发货批一致）`,
      `- 请确认产品等级/牌号、内控标准与关键指标`,
      `- 请报出厂价、到${DEST}门到价、月可供量、账期`
    ].join('\n');
  }

  function downloadChecklist(c) {
    const lines = [
      `${c.name} 供应商准入尽调清单`,
      `生成日期：${new Date().toLocaleDateString('zh-CN')}`,
      `企业：${c.full}`,
      `生产身份：生产厂家｜${c.process}｜${c.plants.length}个基地`,
      `产能：${c.capacity} ${CAP_UNIT}（${c.capacity_year}）｜${c.output_year || "最新"}产量：${c.output == null ? '未披露' : c.output + '万吨'}`,
      `最近基地：${c.nearest_plant}（${nearestCity(c)}）｜距${DEST}直线${c.distance_km}km`,
      '',
      '一、文件清单',
      '□ 营业执照、生产地址与排污许可证地址一致',
      `□ ${PRODUCT}装置产能、最新实际产量、当月排产`,
      '□ 连续3批COA（总碱量、水分、氯化物、Fe₂O₃、水不溶物、堆积密度、粒度、灼烧失量）',
      '□ ISO9001/ISO14001/ISO45001及客户审厂报告',
      `□ ${APPLICATION}客户案例（可脱敏）`,
      '□ 长协占比、检修计划、断供预案、质量罚则',
      `□ 报价：出厂价、到${DEST}门到价、账期、最小起订量`,
      '□ 销售主体/授权链/收款账户一致性',
      '',
      '二、该企业专属缺口',
      ...c.gaps.map((g) => `- ${g}`),
      '',
      '三、现场审核6看',
      '1. 装置：实际负荷、检修记录、工艺与副产物',
      '2. 成品仓：重质/轻质分仓、防潮、批次标识、先进先出',
      '3. 化验室：Fe₂O₃、氯化物、粒度、水分自检与留样',
      `4. 发运：${PACKAGING}装车、日发运量、港口/铁路专用线`,
      '5. 追溯：批次号—生产记录—COA—发货单闭环',
      `6. 客户：${APPLICATION}客户名单、审厂报告、质量异议记录`,
      '',
      `四、建议：${c.action}`
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${c.name}_供应商准入尽调清单.txt`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    toast('尽调清单已生成');
  }

  /* ---------------- compare ---------------- */
  function toggleCompare(id) {
    const i = state.compare.indexOf(id);
    if (i > -1) state.compare.splice(i, 1);
    else {
      if (state.compare.length >= 3) { toast('最多对比 3 家'); return; }
      state.compare.push(id);
    }
    renderCompareBar();
    renderTable();
    $$('[data-compare="' + id + '"]').forEach((b) => {
      const on = state.compare.includes(id);
      if (b.classList.contains('mini-btn')) { b.classList.toggle('active', on); b.textContent = on ? '已选' : (b.closest('.row-actions') ? '对比' : '加入对比'); }
    });
    if (state.currentId) renderTab(state.currentTab);
  }

  function renderCompareBar() {
    const bar = $('#compareBar');
    const names = $('#compareNames');
    $('#compareCount').textContent = `${state.compare.length} / 3`;
    names.innerHTML = state.compare.map((id) => {
      const c = byId(id);
      return `<span class="cn">${esc(c.name)}<button data-remove="${id}" aria-label="移除">×</button></span>`;
    }).join('');
    bar.classList.toggle('show', state.compare.length > 0);
    $$('#compareNames [data-remove]').forEach((b) => { b.onclick = () => toggleCompare(b.dataset.remove); });
  }

  function openCompare() {
    if (state.compare.length < 2) { toast('至少选 2 家再对比'); return; }
    const cs = state.compare.map(byId).filter(Boolean);
    const best = (key, mode) => {
      const vals = cs.map((c) => c[key]);
      return mode === 'min' ? Math.min(...vals) : Math.max(...vals);
    };
    const rows = [
      ['综合评分', (c) => c.composite, 'max'], ['生产确定性', (c) => c.certainty, 'max'],
      ['规格匹配', (c) => c.spec_score, 'max'], ['规模分', (c) => c.scale_score, 'max'],
      ['距离分', (c) => c.distance_score, 'max'], [`${PRODUCT}产能（${CAP_UNIT}）`, (c) => c.capacity, 'max'],
      [`到${DEST}直线（km）`, (c) => c.distance_km, 'min'], [`规格公开（/${SPEC_COUNT}）`, (c) => c.spec_open, 'max'],
      ['外销可得性', (c) => c.availability, 'max'], ['成立年份', (c) => c.founded, 'none'],
      [`最新产量（${CAP_UNIT}）`, (c) => c.output, 'max'], ['员工人数', (c) => c.employees, 'max']
    ];
    const table = `<div style="overflow:auto"><table class="compare-table"><thead><tr><th>维度</th>${cs.map((c) => `<th>${esc(c.name)}<br><span style="font-weight:400;color:var(--muted)">${esc(c.tier)}</span></th>`).join('')}</tr></thead><tbody>
      ${rows.map(([label, fn, mode]) => {
        const values = cs.map(fn);
        const bid = mode === 'none' ? null : (mode === 'min' ? Math.min(...values.filter((v) => v !== null)) : Math.max(...values.filter((v) => v !== null)));
        return `<tr><td>${label}</td>${cs.map((c, i) => `<td class="${values[i] === bid && cs.length > 1 ? 'best' : ''}">${values[i] === null ? '未披露' : (typeof values[i] === 'number' ? fmt(values[i]) : esc(values[i]))}</td>`).join('')}</tr>`;
      }).join('')}
      <tr><td>证据结构</td>${cs.map((c) => `<td>A${c.evidence.filter(e => e.level === '直接-A').length} / B${c.evidence.filter(e => e.level === '直接-B').length} / C${c.evidence.filter(e => e.level === '间接-C').length}</td>`).join('')}</tr>
      <tr><td>规格缺口</td>${cs.map((c) => `<td>${esc(specGaps(c).join('、') || '无')}</td>`).join('')}</tr>
      <tr><td>建议</td>${cs.map((c) => `<td>${esc(c.action)}</td>`).join('')}</tr>
    </tbody></table></div>`;
    openModal('供应商对比', '最多 3 家 · 绿色为该维度最优（距离越短越优）', table, `<button class="btn btn-primary btn-sm" id="copyCompare">复制对比结论</button><button class="btn btn-ghost btn-sm" data-close-modal>关闭</button>`);
    $('#copyCompare').onclick = () => {
      const txt = cs.map((c) => `${c.name}：综合${c.composite}，产能${c.capacity} ${CAP_UNIT}，距离${c.distance_km}km，规格${c.spec_open}/${SPEC_COUNT}，外销${c.availability}`).join('\n');
      copyText(txt).then(() => toast('对比结论已复制'));
    };
  }

  /* ---------------- qualification ---------------- */
  function openQualification(c) {
    const checks = [
      '营业执照、生产地址与排污许可证地址一致',
      `${PRODUCT}装置产能、最新实际产量、当月排产`,
      `连续 3 批 COA（${SPEC_COUNT} 项指标，批次号与发货批一致）`,
      'ISO9001 / ISO14001 / ISO45001 及客户审厂报告',
      `${APPLICATION}客户案例与联系人`,
      `${PACKAGING}、装车能力、日发运量、港口/铁路专用线`,
      '长协占比、检修计划、断供预案、质量罚则',
      `报价：出厂价、到${DEST}门到价、账期、最小起订量`,
      '销售主体/授权链/收款账户一致性',
      '现场审核：装置、成品仓、化验室、发运、批次追溯'
    ];
    const body = `<div class="qual-company"><div class="avatar">${esc(initial(c.name))}</div><div><b>${esc(c.name)}</b><span>${esc(c.full_name || c.full)} · ${esc(c.process)} · ${fmt(c.capacity)} ${CAP_UNIT}</span></div></div>
      <div class="note-box"><b>当前结论：</b>生产身份成立；综合 ${c.composite}/100；规格公开 ${c.spec_open}/${SPEC_COUNT} 项；0 项批次 COA。准入需完成“文件审核 + 小样检测 + 现场审核”三段。</div>
      <div class="qual-section"><h4>一、文件/样品清单（可勾选）</h4><div class="checklist">${checks.map((x, i) => `<label class="check"><input type="checkbox" data-qcheck="${i}"><span>${esc(x)}</span></label>`).join('')}</div></div>
      <div class="qual-section"><h4>二、该企业专属缺口</h4><div class="gap-box"><ul style="margin:0;padding-left:16px">${c.gaps.map((g) => `<li>${esc(g)}</li>`).join('')}</ul></div></div>
      <div class="qual-section"><h4>三、现场审核 6 看</h4><div class="strength-grid">
        <div class="strength">看装置：实际运行负荷、检修记录、联碱/氨碱工艺与副产物。</div>
        <div class="strength">看成品仓：重质/轻质分仓、防潮、批次标识、先进先出。</div>
        <div class="strength">看化验室：Fe₂O₃、氯化物、粒度、水分是否自检，留样多久。</div>
        <div class="strength">看发运：${PACKAGING}装车、日发运量、港口/铁路专用线。</div>
        <div class="strength">看追溯：批次号—生产记录—COA—发货单能否闭环。</div>
        <div class="strength">看客户：${APPLICATION}客户名单、审厂报告、质量异议记录。</div>
      </div></div>
      <div class="note-box amber"><b>建议：</b>${esc(c.action)} 在批次 COA、到厂价、月度可供量未确认前，不授予主供资格。</div>`;
    openModal('供应商准入尽调', `${c.name} · 公开信息核验 + 待补清单`, body,
      `<button class="btn btn-primary btn-sm" id="qualDownload">下载尽调清单</button><button class="btn btn-ghost btn-sm" data-close-modal>关闭</button>`);
    $('#qualDownload').onclick = () => downloadChecklist(c);
  }

  /* ---------------- modal ---------------- */
  function openModal(title, sub, body, foot) {
    $('#modalTitle').textContent = title;
    $('#modalSub').textContent = sub || '';
    $('#modalBody').innerHTML = body;
    $('#modalFoot').innerHTML = foot || '<button class="btn btn-ghost btn-sm" data-close-modal>关闭</button>';
    $('#modalOverlay').classList.add('show');
    document.body.style.overflow = 'hidden';
    $$('#modalOverlay [data-close-modal]').forEach((b) => { b.onclick = closeModal; });
  }
  function closeModal() {
    $('#modalOverlay').classList.remove('show');
    if (!$('#drawer').classList.contains('show')) document.body.style.overflow = '';
  }

  /* ---------------- upload / RFQ ---------------- */
  function parseSpecText(text) {
    const out = [];
    const add = (label, val, unit) => { if (val !== null && val !== undefined && val !== '') out.push({ label, val: String(val).replace(/\s+/g, ' ').slice(0, 42), unit: unit || '' }); };
    const grab = (re) => { const m = text.match(re); return m ? m[1] : null; };
    add('总碱量', grab(/(?:总碱量|Na2CO3|Na₂CO₃|碳酸钠)[^\d]{0,24}([0-9]+(?:\.[0-9]+)?)\s*%/i), '%');
    add('水分', grab(/(?:水分|含水率|含水)[^\d]{0,24}([0-9]+(?:\.[0-9]+)?)\s*%/i), '%');
    add('氯化物', grab(/(?:氯化物|Cl-|Cl⁻|NaCl)[^\d]{0,24}([0-9]+(?:\.[0-9]+)?)\s*%/i), '%');
    add('Fe₂O₃', grab(/(?:Fe2O3|Fe₂O₃|三氧化二铁|铁含量)[^\d]{0,24}([0-9]+(?:\.[0-9]+)?)\s*%/i), '%');
    add('水不溶物', grab(/(?:水不溶物)[^\d]{0,24}([0-9]+(?:\.[0-9]+)?)\s*%/i), '%');
    add('堆积密度', grab(/(?:堆积密度|松密度)[^\d]{0,24}([0-9]+(?:\.[0-9]+)?)/i), 'g/cm³');
    add('灼烧失量', grab(/(?:灼烧失量|烧失量)[^\d]{0,24}([0-9]+(?:\.[0-9]+)?)\s*%/i), '%');
    const pm = text.match(/(?:粒度|粒径)[^\n]{0,80}/i);
    if (pm) add('粒度', pm[0].replace(/^(粒度|粒径)\s*[:：]?\s*/i, '').replace(/\s+/g, ' ').slice(0, 48), '');
    const qm = text.match(/(?:数量|月需|年需|需求)[^\n]{0,40}/i);
    if (qm) add('数量', qm[0].replace(/\s+/g, ' ').slice(0, 40), '');
    return out;
  }

  function handleSpecFile(file) {
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { toast('文件超过 2MB，请粘贴关键段落'); return; }
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || '');
      const items = parseSpecText(text);
      const box = $('#parsedSpecs');
      if (!items.length) {
        box.innerHTML = '<span class="chip warn">未识别到指标，请把规格段落粘贴到需求卡</span>';
        toast('未识别到指标，可手动修改需求');
        return;
      }
      box.innerHTML = items.map((x) => `<span class="chip">${esc(x.label)} ${esc(x.val)}${esc(x.unit)}</span>`).join('');
      toast(`已识别 ${items.length} 项，请人工确认`);
    };
    reader.readAsText(file, 'utf-8');
  }

  const RFQ_DEFAULT = {
    product: DATA.rfq.product || DATA.meta.product || '',
    qty: String(DATA.rfq.qty_month || ''),
    dest: DATA.rfq.destination || DATA.meta.destination || '',
    region: '华东优先；华北、华中可接受；西北成本备选'
  };
  function applyRfq() {
    const p = $('#rfqProduct').value.trim() || RFQ_DEFAULT.product;
    const q = $('#rfqQty').value || RFQ_DEFAULT.qty;
    const d = $('#rfqDest').value.trim() || RFQ_DEFAULT.dest;
    const r = $('#rfqRegion').value;
    const productEl = $('.hero-q .product');
    if (productEl) productEl.innerHTML = esc(p).replace(/\s*[（(]/, '<br>（');
    const lines = $$('.hero-q .spec-line');
    if (lines[4]) lines[4].innerHTML = `<span>收货地</span><b>${esc(d)}</b>`;
    $('.hero-q .big strong').textContent = Number(q).toLocaleString('zh-CN');
    $('.hero-q .big span').textContent = `吨 / 月 · ${(Number(q) * 12).toLocaleString('zh-CN')} 吨 / 年`;
    $('.hero-card-head b').textContent = '已应用';
    toast(`需求已更新：${p}｜${q} 吨/月｜${d}`);
  }
  function resetRfq() {
    $('#rfqProduct').value = RFQ_DEFAULT.product;
    $('#rfqQty').value = RFQ_DEFAULT.qty;
    $('#rfqDest').value = RFQ_DEFAULT.dest;
    $('#rfqRegion').value = RFQ_DEFAULT.region;
    $('#parsedSpecs').innerHTML = '';
    $('.hero-q .product').innerHTML = `${esc(DATA.meta.product || PRODUCT)}<br>${esc(DATA.meta.application || '')}`;
    $('.hero-q .big strong').textContent = '2,000';
    $('.hero-q .big span').textContent = '吨 / 月 · 24,000 吨 / 年';
    const lines = $$('.hero-q .spec-line');
    if (lines[4]) lines[4].innerHTML = `<span>收货地</span><b>${esc(DATA.meta.destination || '')}</b>`;
    $('.hero-card-head b').textContent = '示例需求';
    toast('已恢复示例需求');
  }

  /* ---------------- copy / toast ---------------- */
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
    }
    return Promise.resolve(fallbackCopy(text));
  }
  function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
  }
  let toastTimer = null;
  function toast(msg) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2600);
  }

  /* ---------------- bind ---------------- */
  function bind() {
    $$('.filters [data-filter] .chip-filter').forEach((b) => {
      b.onclick = () => {
        const group = b.closest('[data-filter]').dataset.filter;
        state[group] = b.dataset.value;
        $$('.filters [data-filter="' + group + '"] .chip-filter').forEach((x) => x.classList.remove('active'));
        b.classList.add('active');
        if (group === 'identity' && b.dataset.value === 'trader') toast('贸易商在 04 单独列出，候选池只放生产厂家');
        renderTable();
      };
    });
    $('#resetFilters').onclick = () => {
      state.identity = 'all'; state.region = 'all'; state.scale = 'all'; state.distance = 'all'; state.evidence = 'all'; state.search = ''; state.sort = 'composite';
      $('#searchInput').value = ''; $('#sortSelect').value = 'composite';
      $$('.filters [data-filter] .chip-filter').forEach((x) => x.classList.toggle('active', x.dataset.value === 'all'));
      renderTable();
    };
    $('#sortSelect').onchange = (e) => { state.sort = e.target.value; renderTable(); };
    $('#searchInput').oninput = (e) => { state.search = e.target.value.trim(); renderTable(); };
    $$('.view-toggle button').forEach((b) => {
      b.onclick = () => {
        state.view = b.dataset.view;
        $$('.view-toggle button').forEach((x) => x.classList.toggle('active', x === b));
        renderTable();
      };
    });
    $('#drawerClose').onclick = closeDrawer;
    $('#overlay').onclick = closeDrawer;
    $('#drawerTabs').onclick = (e) => {
      const t = e.target.closest('.drawer-tab');
      if (t) renderTab(t.dataset.tab);
    };
    $('#openCompareTop').onclick = openCompare;
    $('#openCompare').onclick = openCompare;
    $('#clearCompare').onclick = () => { state.compare = []; renderCompareBar(); renderTable(); };
    $('#modalClose').onclick = closeModal;
    $('#modalOverlay').onclick = (e) => { if (e.target === $('#modalOverlay')) closeModal(); };
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { closeModal(); if ($('#drawer').classList.contains('show')) closeDrawer(); }
    });
    $('#applyRfq').onclick = applyRfq;
    $('#resetRfq').onclick = resetRfq;
    $('#specFile').onchange = (e) => handleSpecFile(e.target.files && e.target.files[0]);
    $$('.nav a').forEach((a) => { a.onclick = (e) => { e.preventDefault(); const t = $(a.getAttribute('href')); if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' }); }; });
  }

  function revealSections() {
    if (!('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add('reveal'); io.unobserve(en.target); } });
    }, { threshold: 0.06 });
    $$('.section').forEach((s) => io.observe(s));
  }

  document.addEventListener('DOMContentLoaded', () => {
    bind();
    renderTable();
    renderScatter();
    renderCompareBar();
    revealSections();
  });
})();
