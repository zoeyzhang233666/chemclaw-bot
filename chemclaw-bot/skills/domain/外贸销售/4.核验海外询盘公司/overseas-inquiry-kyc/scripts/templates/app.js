/* overseas-inquiry-kyc · 报告渲染层
   纯前端、零依赖、可离线。数据只来自内联的 DATA。
   结构：工具函数 → 各区块 renderer → 初始化。 */

'use strict';

const M = DATA.meta || {};
const ST = DATA.stats || {};
const LABEL = { verified: '已核实', discrepancy: '存在疑点', unverified: '未核实', not_applicable: '不适用' };
const ORDER = ['verified', 'discrepancy', 'unverified', 'not_applicable'];
const COLOR = { verified: 'var(--ok)', discrepancy: 'var(--bad)', unverified: 'var(--gray)', not_applicable: 'var(--na)' };
const SEV = { high: '高', medium: '中', low: '低' };
const SECTIONS = DATA.sections || [
  { id: 'A', key: 'identity', title: '身份核验', subtitle: '主体是否真实存在、名称与登记是否一致' },
  { id: 'B', key: 'business', title: '业务相关性', subtitle: '主营业务与询价产品是否合理相关' },
  { id: 'C', key: 'contact', title: '网站域名与联系方式', subtitle: '官网、域名、邮箱、地址、电话是否自洽' },
  { id: 'D', key: 'risk', title: '公开风险', subtitle: '经营异常、诉讼、制裁、负面报道' },
  { id: 'E', key: 'gaps', title: '待补充资料', subtitle: '需要向对方索取的材料与下一步动作' }
];
const SOURCE = {};
(DATA.sources || []).forEach(s => { SOURCE[s.id] = s; });

/* ------------------------------------------------------------------ 工具 */
const esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

function arr(x) { return Array.isArray(x) ? x : (x == null || x === '' ? [] : [x]); }
function n(x) { return Number(x || 0); }
function byId(id) { return document.getElementById(id); }

function chip(status, extra) {
  const s = status || 'unverified';
  return `<span class="chip ${esc(s)} ${extra || ''}">${LABEL[s] || esc(s)}</span>`;
}
function sevChip(sev) {
  return `<span class="chip sev-${esc(sev)}">${SEV[sev] || sev}风险</span>`;
}
function gradeChip(g) {
  return `<span class="chip grade-${esc((g || 'd').toLowerCase())}">${esc(g)} 级</span>`;
}
function srcPill(id) {
  const s = SOURCE[id];
  if (!s) return '';
  return `<a class="src-pill" href="#src-${esc(id)}" onclick="jumpSource(event,'${esc(id)}')">${gradeChip(s.grade)}<span class="mono">${esc(id)}</span></a>`;
}
function srcRow(ids) {
  const list = arr(ids);
  if (!list.length) return '';
  return `<div class="srcrow"><span class="tiny muted">来源</span>${list.map(srcPill).join('')}</div>`;
}
function listOr(items, empty, cls) {
  const l = arr(items);
  if (!l.length) return `<div class="tiny muted">${esc(empty || '—')}</div>`;
  return `<ul>${l.map(x => `<li class="${cls || ''}">${esc(x)}</li>`).join('')}</ul>`;
}
function donut(segments, size, width) {
  const R = 52, C = 2 * Math.PI * R, total = segments.reduce((a, b) => a + n(b.v), 0) || 1;
  let off = 0, parts = '';
  segments.forEach(s => {
    const len = n(s.v) / total * C;
    if (len > 0) {
      parts += `<circle cx="70" cy="70" r="${R}" fill="none" stroke="${s.c}" stroke-width="${width || 16}"
        stroke-dasharray="${len.toFixed(2)} ${(C - len).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}"
        transform="rotate(-90 70 70)"></circle>`;
      off += len;
    }
  });
  return `<svg width="${size || 140}" height="${size || 140}" viewBox="0 0 140 140" role="img" aria-label="核验状态分布">
    <circle cx="70" cy="70" r="${R}" fill="none" stroke="var(--paper-3)" stroke-width="${width || 16}"></circle>
    ${parts}
    <text x="70" y="66" text-anchor="middle" font-size="26" font-weight="700" fill="var(--ink)">${total}</text>
    <text x="70" y="86" text-anchor="middle" font-size="11" fill="var(--ink-4)">核验项</text>
  </svg>`;
}

/* ------------------------------------------------------------------ 状态：只在内存 */
const UI = {
  statusFilter: new Set(ORDER),
  sectionFilter: new Set(SECTIONS.map(s => s.id)),
  query: '',
  done: new Set(),
  msgTab: 0
};

/* ------------------------------------------------------------------ 导航 */
function renderNav() {
  const links = [
    ['#sec-hero', '总览'], ['#sec-inquiry', '询盘原文'], ['#sec-extract', '字段提取'],
    ['#sec-subject', '主体识别'], ['#sec-business', '业务相关性'], ['#sec-contact', '联系方式'],
    ['#sec-checks', '核验结论'], ['#sec-risk', '公开风险'], ['#sec-gaps', '待补充与话术'], ['#sec-sources', '来源库']
  ];
  byId('navLinks').innerHTML = links.map(([h, t]) => `<button onclick="location.hash='${h}'">${t}</button>`).join('');
  byId('navBrand').textContent = M.short_title || '海外询盘企业核验';
  byId('navMeta').textContent = '核验日 ' + (M.as_of || '');
  if (M.synthetic) byId('mockBar').hidden = false;
}

/* ------------------------------------------------------------------ 1 封面 */
function renderHero() {
  const segs = ORDER.map(k => ({ k, v: n(ST.status && ST.status[k]), c: COLOR[k] }));
  const legend = segs.map(s => `
    <div class="legend-row" onclick="toggleStatus('${s.k}')" data-legend="${s.k}">
      <span class="sw ${s.k}"></span><span>${LABEL[s.k]}</span><span class="n">${s.v}</span>
    </div>`).join('');

  const cards = SECTIONS.map(s => {
    const c = (ST.section && ST.section[s.id]) || {};
    const total = n(c.verified) + n(c.discrepancy) + n(c.unverified) + n(c.not_applicable);
    const bar = ORDER.map(k => c[k] ? `<i style="width:${(n(c[k]) / total * 100).toFixed(1)}%;background:${COLOR[k]}"></i>` : '').join('');
    const flag = n(c.discrepancy) ? `<span class="flag">${c.discrepancy} 疑点</span>` : '';
    return `<button class="score-cell" onclick="focusSection('${esc(s.id)}')">
      ${flag}<div class="id">区块 ${esc(s.id)}</div><div class="t">${esc(s.title)}</div>
      <div class="bar">${bar}</div>
      <div class="nums"><span>已核实 <b>${n(c.verified)}</b></span><span>疑点 <b>${n(c.discrepancy)}</b></span><span>未核实 <b>${n(c.unverified)}</b></span></div>
    </button>`;
  }).join('');

  const meta = [
    ['询盘编号', M.inquiry_id], ['核验基准日', M.as_of], ['产品', M.product],
    ['询盘数量', M.quantity], ['交付条款', M.incoterm], ['包装', M.packaging]
  ].filter(x => x[1]).map(([k, v]) => `<div class="meta-cell"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`).join('');

  return `<section class="section" id="sec-hero">
    <div class="hero">
      <div class="hero-grid">
        <div>
          <div class="kicker">INQUIRY KYC · OVERSEAS COUNTERPARTY VERIFICATION</div>
          <h1>${esc(M.title)}</h1>
          ${M.subtitle ? `<p class="lede">${esc(M.subtitle)}</p>` : ''}
          <div class="verdict">
            <div class="lbl">一句话结论</div>
            <div class="txt">${esc(ST.verdict_line || '—')}</div>
          </div>
          <div class="meta-grid">${meta}</div>
        </div>
        <div class="donut-card">
          <div class="card-h"><h3>核验状态分布</h3><span class="right">共 ${n(ST.checks_total)} 项</span></div>
          <div class="donut">${donut(segs, 140, 16)}<div class="legend">${legend}</div></div>
          <div class="tiny muted" style="margin-top:12px">点击图例可按状态筛选下方核验结论。</div>
        </div>
      </div>
      <div class="scorecard" style="margin-top:22px">${cards}</div>
    </div>
  </section>`;
}

/* ------------------------------------------------------------------ 2 询盘原文 */
function renderInquiry() {
  const q = DATA.inquiry || {};
  const body = arr(q.body_lines).map(l => {
    let t = esc(l);
    // 高亮关键实体
    t = t.replace(/(PT [A-Z][A-Za-z ]+)/g, '<span class="hi">$1</span>');
    t = t.replace(/(25,000 MT\/year)/g, '<span class="hi">$1</span>');
    t = t.replace(/(www\.sinarkacanusa\.co\.id|andi\.pratama@sinarkacanusa\.co\.id)/g, '<span class="hi">$1</span>');
    return t;
  }).join('\n');

  const atts = arr(q.attachments).map(a => `<div class="tiny" style="padding:5px 0;border-bottom:1px dashed var(--line-2)"><b>${esc(a.name)}</b><span class="muted"> · ${esc(a.note || '')}</span></div>`).join('');
  const notes = arr(q.notes).map(x => `<li>${esc(x)}</li>`).join('');

  return `<section class="section" id="sec-inquiry">
    <div class="sec-head"><span class="idx">01</span><h2>询盘原文与初步观察</h2>
      <span class="sub">把“对方说了什么”和“我方看到了什么”分开记录</span></div>
    <div class="grid-2" style="grid-template-columns:minmax(0,1.5fr) minmax(280px,.8fr)">
      <div class="mail">
        <div class="mail-top">
          <div class="subj">${esc(q.subject)}</div>
          <div class="mail-row"><b>发件人</b><span class="mono">${esc(q.from)}</span></div>
          <div class="mail-row"><b>收件人</b><span class="mono">${esc(q.to)}</span></div>
          <div class="mail-row"><b>时间</b><span class="mono">${esc(q.date)}</span></div>
          ${q.reply_to ? `<div class="mail-row"><b>Reply-To</b><span class="mono">${esc(q.reply_to)}</span></div>` : ''}
        </div>
        <div class="mail-body">${body}</div>
        <div class="mail-foot">附件 ${arr(q.attachments).length} 个 · 正文关键词已高亮 · 本邮件为模拟数据</div>
      </div>
      <div style="display:grid;gap:14px;align-content:start">
        <div class="bizcard">
          <div><div class="logo">PT SINAR KACA NUSANTARA</div></div>
          <div><div class="nm">Andi Pratama Wibowo</div><div class="ps">Senior Procurement Manager</div></div>
          <div class="ct">M +62 812-3456-7890<br>E andi.pratama@sinarkacanusa.co.id<br>W www.sinarkacanusa.co.id<br>Jl. Raya Bekasi KM 27, Cakung, Jakarta Timur 13910</div>
        </div>
        <div class="card pad">
          <div class="card-h"><h3>附件清单</h3><span class="right">${arr(q.attachments).length} 项</span></div>
          ${atts || '<div class="tiny muted">无附件</div>'}
        </div>
        <div class="card pad">
          <div class="card-h"><h3>初步观察</h3></div>
          ${notes ? `<ul style="margin:0;padding-left:18px;font-size:12.8px">${notes}</ul>` : '<div class="tiny muted">—</div>'}
        </div>
      </div>
    </div>
  </section>`;
}

/* ------------------------------------------------------------------ 3 字段提取 */
function renderExtract() {
  const rows = arr(DATA.extraction).map(e => `<tr>
    <td class="mono muted">${esc(e.id)}</td>
    <td class="k">${esc(e.field)}</td>
    <td><b>${esc(e.value)}</b></td>
    <td class="tiny muted">${esc(e.evidence)}</td>
    <td class="tiny"><span class="chip ghost">${esc(e.confidence || 'medium')}</span></td>
    <td class="tiny muted">${esc(e.note || '')}</td>
  </tr>`).join('');

  return `<section class="section" id="sec-extract">
    <div class="sec-head"><span class="idx">02</span><h2>询盘字段提取</h2>
      <span class="sub">公司名 / 地址 / 网站 / 域名 / 邮箱 / 联系人 / 产品 —— 逐项落到原文出处</span></div>
    <div class="card" style="overflow:hidden">
      <div style="max-height:520px;overflow:auto">
        <table class="tbl">
          <thead><tr><th style="width:52px">编号</th><th style="width:96px">字段</th><th style="width:220px">提取值</th><th>原文出处</th><th style="width:84px">置信度</th><th style="width:30%">备注 / 口径</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
    <div class="tiny muted" style="margin-top:8px">提示：提取只做“照抄 + 标注出处”，不做判断。任何结论都必须留到后面的核验项里。</div>
  </section>`;
}

/* ------------------------------------------------------------------ 4 主体识别 */
function renderSubject() {
  const s = DATA.subject || {};
  const rows = arr(s.summary_rows).map(r => `<tr>
    <td class="k" style="width:34%">${esc(r.k)}</td><td>${esc(r.v)}</td>
    <td style="width:92px" class="right">${r.verified ? chip('verified') : chip('unverified')}</td></tr>`).join('');

  function block(title, obj, portal) {
    if (!obj) return '';
    const st = obj.status === 'verified' ? chip('verified') : chip('unverified');
    return `<div class="card pad" style="margin-bottom:12px">
      <div class="card-h"><h3>${esc(title)}</h3><span class="right">${st}</span></div>
      <div class="tiny muted" style="margin-bottom:6px"><b>入口</b> ${esc(obj.portal || portal || '')}</div>
      ${arr(obj.search_terms).length ? `<div class="tiny muted" style="margin-bottom:6px"><b>检索词</b> ${arr(obj.search_terms).map(t => `<span class="mono">${esc(t)}</span>`).join(' / ')}</div>` : ''}
      <div style="font-size:13px;margin-bottom:6px"><b>结果：</b>${esc(obj.result || '—')}</div>
      ${obj.result_note ? `<div class="boundary">${esc(obj.result_note)}</div>` : ''}
    </div>`;
  }

  return `<section class="section" id="sec-subject">
    <div class="sec-head"><span class="idx">03</span><h2>注册主体识别</h2>
      <span class="sub">名称 → 登记全称 → 登记号 / NIB → KBLI —— 只有登记号相同才算同一主体</span></div>
    <div class="grid-2" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
      <div>
        <div class="card pad" style="margin-bottom:12px">
          <div class="card-h"><h3>主体摘要</h3><span class="right">待核项以灰色标记</span></div>
          <div class="table-card" style="overflow-x:auto"><table class="tbl" style="font-size:13px">${rows}</table></div>
        </div>
        <div class="card pad">
          <div class="card-h"><h3>同名 / 错配排查规则</h3></div>
          ${arr(DATA.linkage).map(l => `<div style="padding:7px 0;border-bottom:1px dashed var(--line-2)">
            <div style="font-weight:600;font-size:13px">${esc(l.name)} <span class="chip ghost">${esc(l.relation)}</span></div>
            <div class="tiny muted">${esc(l.detail)}</div>
            <div class="tiny" style="color:var(--brand);margin-top:2px">规则：${esc(l.rule)}</div>
          </div>`).join('')}
        </div>
      </div>
      <div>
        ${block('AHU 登记检索（官方）', s.registry_check)}
        ${block('NIB / OSS 检索（官方）', s.nib_oss)}
        ${block('NPWP 税号（官方/对方）', s.npwp_tax)}
        ${block('海关进口商识别号', s.customs_id)}
      </div>
    </div>
  </section>`;
}

/* ------------------------------------------------------------------ 5 业务相关性 */
function renderBusiness() {
  const b = DATA.business_fit || {};
  const kw = arr(b.keywords).map(k => `<tr>
    <td class="mono">${esc(k.kode)}</td><td><b>${esc(k.label)}</b><div class="tiny muted">${esc(k.why)}</div></td>
    <td class="right">${chip(k.status)}</td><td class="tiny muted">${esc(k.note || '')}</td></tr>`).join('');
  const sig = arr(b.signals).map(s => `<div style="padding:7px 0;border-bottom:1px dashed var(--line-2);display:flex;gap:10px">
    <div style="flex:1"><div style="font-weight:600;font-size:13px">${esc(s.signal)}</div>
      <div class="tiny muted">${esc(s.note)}</div></div>
    <div style="flex:0 0 auto">${chip(s.status)}</div></div>`).join('');

  const dm = arr(b.demand_math).map(d => `<tr><td class="k" style="width:30%">${esc(d.label)}</td><td><b>${esc(d.value)}</b></td><td class="tiny muted">${esc(d.note)}</td></tr>`).join('');

  return `<section class="section" id="sec-business">
    <div class="sec-head"><span class="idx">04</span><h2>业务相关性</h2>
      <span class="sub">${esc(b.subtitle || '主营业务、产品目录、经营活动与询价产品是否合理相关')}</span></div>
    <div class="card pad" style="margin-bottom:14px;border-left:3px solid var(--brand)">
      <div style="font-size:16px;font-weight:700">${esc(b.headline || '')}</div>
      ${b.product_use ? `<div class="tiny muted" style="margin-top:6px">${esc(b.product_use)}</div>` : ''}
    </div>
    <div class="grid-2">
      <div class="card" style="overflow:hidden">
        <div class="card-h" style="padding:14px 18px 0"><h3>KBLI / 业务分类对照</h3><span class="right">${arr(b.keywords).length} 项</span></div>
        <div style="overflow-x:auto"><table class="tbl" style="margin-top:10px"><tbody>${kw || '<tr><td class="muted tiny">—</td></tr>'}</tbody></table></div>
      </div>
      <div style="display:grid;gap:14px;align-content:start">
        <div class="card pad">
          <div class="card-h"><h3>需求量化</h3></div>
          <div style="overflow-x:auto"><table class="tbl" style="font-size:13px"><tbody>${dm || '<tr><td class="muted tiny">—</td></tr>'}</tbody></table></div>
        </div>
        <div class="card pad">
          <div class="card-h"><h3>业务信号</h3><span class="right">${arr(b.signals).length} 项</span></div>
          ${sig || '<div class="tiny muted">—</div>'}
        </div>
      </div>
    </div>
  </section>`;
}

/* ------------------------------------------------------------------ 6 联系方式一致性 */
function renderContact() {
  const M2 = DATA.matrix || [];
  const mismatchRow = s => {
    const c = s.mismatch || 'unknown';
    const cls = { same: 'same', partial: 'partial', different: 'different', misattribution: 'misattribution', unknown: 'unknown' }[c] || 'unknown';
    const label = { same: '一致', partial: '部分一致', different: '不一致', misattribution: '疑似错配', unknown: '无法比对' }[c] || c;
    return `<span class="cell ${cls}">${esc(label)}</span>`;
  };
  const rows = M2.map(r => `<tr>
    <td class="mono muted">${esc(r.id)}</td><td class="k">${esc(r.item)}</td>
    <td class="l">${esc(r.claimed)}</td><td class="l">${esc(r.other)}</td>
    <td>${mismatchRow(r)}</td><td class="tiny muted" style="text-align:left">${esc(r.note || '')}</td></tr>`).join('');

  const ea = arr(DATA.email_auth).map(e => `<tr>
    <td class="k">${esc(e.item)}</td><td class="l mono">${esc(e.observed)}</td><td class="tiny muted">${esc(e.expected)}</td>
    <td>${mismatchRow(e)}</td></tr>`).join('');

  const dom = arr(DATA.domains).map(d => `<div class="card pad">
    <div class="card-h"><h3 class="mono">${esc(d.domain)}</h3><span class="right">${esc(d.tld || '')}</span></div>
    <div style="overflow-x:auto"><table class="tbl" style="font-size:12.5px"><tbody>
      ${[['解析', d.resolve], ['WHOIS', d.whois], ['官网抓取', d.website], ['SSL', d.ssl], ['MX', d.mx]]
        .map(([k, v]) => `<tr><td class="k" style="width:88px">${k}</td><td class="tiny">${esc(v || '—')}</td></tr>`).join('')}
    </tbody></table></div>
    <div class="boundary" style="margin-top:10px">${esc(d.note || '')}</div>
  </div>`).join('');

  return `<section class="section" id="sec-contact">
    <div class="sec-head"><span class="idx">05</span><h2>网站、域名与联系方式一致性</h2>
      <span class="sub">官网 / 域名 / 邮箱 / 地址 / 电话 —— 五项互相对照，谁跟谁对不上要写清楚</span></div>
    <div class="card" style="overflow:hidden;margin-bottom:14px">
      <div class="matrix-wrap" style="border:0;border-radius:0">
        <table class="matrix">
          <thead><tr><th class="l" style="width:46px">编号</th><th class="l" style="width:104px">核对项</th>
            <th class="l">询盘中的说法</th><th class="l">另一来源的说法</th><th style="width:92px">比对</th><th class="l" style="width:30%">说明 / 下一步</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
    <div class="grid-2">
      <div class="card" style="overflow:hidden">
        <div class="card-h" style="padding:14px 18px 0"><h3>发信认证检查</h3><span class="right">From / Reply-To / SPF / DMARC / 邮件头</span></div>
        <div style="overflow-x:auto"><table class="tbl" style="margin-top:10px">
          <thead><tr><th style="width:118px">项目</th><th>观测值</th><th>期望</th><th style="width:90px">比对</th></tr></thead>
          <tbody>${ea || '<tr><td class="muted tiny">—</td></tr>'}</tbody>
        </table>
      </div>
      ${dom || '<div class="card pad tiny muted">未提供域名信息</div>'}
    </div>
  </section>`;
}

/* ------------------------------------------------------------------ 7 核验结论（可筛选） */
function checkMatches(c) {
  if (!UI.statusFilter.has(c.status)) return false;
  if (!UI.sectionFilter.has(c.section)) return false;
  if (!UI.query) return true;
  const hay = [c.id, c.title, c.question, c.finding, c.action, (c.verified_facts || []).join(' '),
    (c.doubts || []).join(' '), (c.unknowns || []).join(' '), (c.boundary || '')].join(' ').toLowerCase();
  return hay.indexOf(UI.query) >= 0;
}

function checkCard(c) {
  const sec = SECTIONS.find(s => s.id === c.section) || {};
  const tiny = (l) => `<div style="font-size:11.5px;font-weight:700;letter-spacing:.06em;margin-bottom:6px">${l}</div>`;
  return `<article class="chk is-${esc(c.status)}" data-id="${esc(c.id)}" data-section="${esc(c.section)}">
    <div class="chk-head" onclick="toggleCheck('${esc(c.id)}')" role="button" tabindex="0"
         onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleCheck('${esc(c.id)}')}">
      <span class="id">${esc(c.id)}</span>
      <div style="flex:1;min-width:0">
        <div class="t">${esc(c.title)}</div>
        <div class="q">${esc(c.question)}</div>
      </div>
      <div class="tags">
        <span class="chip ghost">${esc(sec.id || '')} · ${esc(sec.title || '')}</span>
        ${c.status === 'discrepancy' ? sevChip(c.severity) : ''}
        ${chip(c.status)}
        <span class="caret">▶</span>
      </div>
    </div>
    <div class="chk-body">
      <div class="finding">${esc(c.finding)}</div>
      <div class="cols3">
        <div class="col-box verified">${tiny('✓ 已核实的事实')}${listOr(c.verified_facts, '暂无')}</div>
        <div class="col-box doubt">${tiny('! 存在疑点')}${listOr(c.doubts, '无')}</div>
        <div class="col-box unknown">${tiny('? 无法确认')}${listOr(c.unknowns, '无')}</div>
      </div>
      ${c.boundary ? `<div class="boundary"><b>边界说明：</b>${esc(c.boundary)}</div>` : ''}
      ${srcRow(c.source_ids)}
      <div class="nextrow">
        <span class="lbl">下一步</span><span>${esc(c.action || '—')}</span>
        ${arr(c.next_ids).map(id => `<button class="btn sm" onclick="gotoRequest('${esc(id)}')">索取 ${esc(id)}</button>`).join('')}
      </div>
    </div>
  </article>`;
}

function renderChecks() {
  const all = DATA.checks || [];
  const fbtn = (key, label, on, cnt) => `<button class="${on ? 'on' : ''}" onclick="${key}"><span>${label}</span><span class="cnt">${cnt}</span></button>`;
  const statusBtns = ORDER.map(k => fbtn(`toggleStatus('${k}')`, LABEL[k], UI.statusFilter.has(k), all.filter(c => c.status === k).length)).join('');
  const secBtns = SECTIONS.map(s => fbtn(`toggleSection('${s.id}')`, `${s.id} ${s.title}`, UI.sectionFilter.has(s.id), all.filter(c => c.section === s.id).length)).join('');

  return `<section class="section" id="sec-checks">
    <div class="sec-head"><span class="idx">06</span><h2>核验结论</h2>
      <span class="sub">按“已核实 / 存在疑点 / 未核实”三分，点开任一结论看来源与下一步</span>
      <span class="right"><button class="btn sm" onclick="expandAll(true)">全部展开</button><button class="btn sm" onclick="expandAll(false)">全部收起</button></span></div>
    <div class="toolbar" id="toolbar">
      <div class="filters" id="fStatus">${statusBtns}</div>
      <div style="width:1px;height:20px;background:var(--line)"></div>
      <div class="filters" id="fSection">${secBtns}</div>
      <div class="search"><span class="muted tiny">🔍</span><input id="q" placeholder="搜索结论 / 疑点 / 来源…" oninput="onSearch(this.value)" value="${esc(UI.query)}"></div>
    </div>
    <div class="checks" id="checkList"></div>
    <div class="tiny muted" id="emptyHint" style="display:none;padding:24px;text-align:center">当前筛选没有结果 —— 放宽状态或区块，或清空搜索词。</div>
  </section>`;
}

function renderCheckList() {
  const list = (DATA.checks || []).filter(checkMatches);
  byId('checkList').innerHTML = list.map(checkCard).join('');
  byId('emptyHint').style.display = list.length ? 'none' : 'block';
  // 保持已展开状态
  expanded.forEach(id => { const el = document.querySelector(`.chk[data-id="${id}"]`); if (el) el.classList.add('open'); });
}

const expanded = new Set(['K01', 'K12', 'K16']);
function toggleCheck(id) {
  const el = document.querySelector(`.chk[data-id="${id}"]`);
  if (!el) return;
  el.classList.toggle('open');
  if (el.classList.contains('open')) expanded.add(id); else expanded.delete(id);
}
function expandAll(on) {
  document.querySelectorAll('.chk').forEach(el => {
    el.classList.toggle('open', on);
    if (on) expanded.add(el.dataset.id); else expanded.delete(el.dataset.id);
  });
}
function toggleStatus(k) {
  if (UI.statusFilter.has(k)) UI.statusFilter.delete(k); else UI.statusFilter.add(k);
  if (!UI.statusFilter.size) ORDER.forEach(x => UI.statusFilter.add(x));
  syncFilters(); renderCheckList();
}
function toggleSection(id) {
  if (UI.sectionFilter.has(id)) UI.sectionFilter.delete(id); else UI.sectionFilter.add(id);
  if (!UI.sectionFilter.size) SECTIONS.forEach(s => UI.sectionFilter.add(s.id));
  syncFilters(); renderCheckList();
}
function syncFilters() {
  const all = DATA.checks || [];
  byId('fStatus').innerHTML = ORDER.map(k => `<button class="${UI.statusFilter.has(k) ? 'on' : ''}" onclick="toggleStatus('${k}')"><span>${LABEL[k]}</span><span class="cnt">${all.filter(c => c.status === k).length}</span></button>`).join('');
  byId('fSection').innerHTML = SECTIONS.map(s => `<button class="${UI.sectionFilter.has(s.id) ? 'on' : ''}" onclick="toggleSection('${s.id}')"><span>${s.id} ${s.title}</span><span class="cnt">${all.filter(c => c.section === s.id).length}</span></button>`).join('');
  document.querySelectorAll('[data-legend]').forEach(el => el.classList.toggle('off', !UI.statusFilter.has(el.dataset.legend)));
}
let qTimer = null;
function onSearch(v) {
  clearTimeout(qTimer);
  qTimer = setTimeout(() => { UI.query = (v || '').trim().toLowerCase(); renderCheckList(); }, 120);
}
function focusSection(id) {
  location.hash = '#sec-checks';
  UI.sectionFilter = new Set([id]);
  ORDER.forEach(k => UI.statusFilter.add(k));
  syncFilters(); renderCheckList();
}

/* ------------------------------------------------------------------ 8 公开风险 */
function renderRisk() {
  const risks = (DATA.risks || []).slice().sort((a, b) => {
    const o = { high: 0, medium: 1, low: 2 };
    return (o[a.severity] - o[b.severity]) || a.id.localeCompare(b.id);
  });
  const items = risks.map(r => `<div class="risk-item ${esc(r.severity)}">
    <div class="rid">${esc(r.id)}</div>
    <div>
      <div class="fact">${esc(r.fact)}</div>
      <div class="impact">影响：${esc(r.impact || '—')}</div>
      <div class="act">动作：${esc(r.action || '—')}</div>
      ${srcRow(r.source_ids)}
    </div>
    <div class="tags"><span class="chip ghost">${esc(r.category)}</span>${sevChip(r.severity)}${chip(r.status)}</div>
  </div>`).join('');

  const bySev = { high: risks.filter(r => r.severity === 'high').length, medium: risks.filter(r => r.severity === 'medium').length, low: risks.filter(r => r.severity === 'low').length };
  const bars = Object.entries(bySev).map(([k, v]) => `<div class="hbar"><span class="lbl">${SEV[k]}风险</span>
    <span class="tr"><i style="width:${v / (risks.length || 1) * 100}%;background:${k === 'high' ? 'var(--bad)' : k === 'medium' ? '#d08b1a' : 'var(--ink-4)'}"></i></span><span class="n">${v}</span></div>`).join('');

  return `<section class="section" id="sec-risk">
    <div class="sec-head"><span class="idx">07</span><h2>公开风险信息</h2>
      <span class="sub">经营异常、诉讼、制裁、收汇路径 —— 每一项都要说明“看到什么”和“影响什么”</span></div>
    <div class="grid-2" style="grid-template-columns:minmax(0,1fr) 300px">
      <div class="risklist">${items || '<div class="tiny muted">—</div>'}</div>
      <div style="display:grid;gap:14px;align-content:start">
        <div class="card pad"><div class="card-h"><h3>风险分布</h3></div><div class="hbars">${bars}</div>
          <div class="tiny muted" style="margin-top:12px">按“严重度”排序展示；“未核实”状态的风险表示尚未完成检索，不等于无风险。</div></div>
        <div class="card pad"><div class="card-h"><h3>本报告不做的事</h3></div>
          <ul class="boundary-list" style="padding-left:16px;margin:0">
            <li>不给诈骗概率</li><li>不以域名注册时间判断企业真假</li>
            <li>不把同名企业的负面信息归到本主体</li><li>不把“查不到”写成“不存在”</li>
          </ul></div>
      </div>
    </div>
  </section>`;
}

/* ------------------------------------------------------------------ 9 待补充资料 + 话术 */
function renderGaps() {
  const reqs = DATA.requests || [];
  const items = reqs.map(q => `<div class="req-item ${UI.done.has(q.id) ? 'done' : ''}" id="req-${esc(q.id)}">
    <input type="checkbox" ${UI.done.has(q.id) ? 'checked' : ''} onchange="toggleDone('${esc(q.id)}',this.checked)" aria-label="标记已取得">
    <span class="prio ${esc(q.priority)}">${esc(q.priority)}</span>
    <div><div class="zh">${esc(q.zh)}</div><div class="en">${esc(q.en)}</div><div class="why">${esc(q.why || '')}</div></div>
    <div>${srcRow(q.source_ids)}</div>
  </div>`).join('');

  const acts = (DATA.actions || []).map(a => `<div class="tl-item ${(a.priority || '').toLowerCase()}">
    <div class="ph">${esc(a.phase)} · ${esc(a.priority)}</div>
    <div class="t">${esc(a.action)}</div><div class="d">${esc(a.detail)}</div>
    <div class="o">责任人：${esc(a.owner || '—')}</div></div>`).join('');

  return `<section class="section" id="sec-gaps">
    <div class="sec-head"><span class="idx">08</span><h2>待补充资料与下一步</h2>
      <span class="sub">按“能否独立证明主体”排序索取；每项都配中英双语与理由</span>
      <span class="right"><span class="tiny muted">已完成 <b id="doneCnt">${UI.done.size}</b>/${reqs.length}</span></span></div>
    <div class="grid-2" style="grid-template-columns:minmax(0,1.45fr) minmax(280px,.75fr)">
      <div class="req" id="reqList">${items}</div>
      <div class="card pad"><div class="card-h"><h3>行动时间轴</h3><span class="right">${arr(DATA.actions).length} 步</span></div>
        <div class="timeline">${acts}</div></div>
    </div>
    <div style="margin-top:22px" id="msgZone">${renderMessages()}</div>
  </section>`;
}

function renderMessages() {
  const msgs = DATA.messages || [];
  if (!msgs.length) return '';
  const i = Math.min(UI.msgTab, msgs.length - 1);
  const m = msgs[i];
  const tabs = msgs.map((x, k) => `<button class="msg-tab ${k === i ? 'on' : ''}" onclick="switchMsg(${k})">${esc(x.title)}</button>`).join('');
  const notes = arr(m.notes).map(x => `<li>${esc(x)}</li>`).join('');
  return `<div class="card pad">
    <div class="card-h"><h3>向对方索取的英文消息草稿</h3>
      <span class="right">可直接复制 · 记得替换 [Your name] 等占位符</span></div>
    <div class="msg-tabs">${tabs}</div>
    <div class="tiny muted" style="margin-bottom:8px">用途：${esc(m.purpose || '')}</div>
    <div class="msg-body" id="msgBody">${esc(m.body_en)}</div>
    <div style="margin-top:10px;display:flex;gap:8px">
      <button class="btn primary" onclick="copyMsg()">复制全文</button>
      <span class="tiny muted" id="copyHint" style="align-self:center"></span>
    </div>
    ${notes ? `<div class="msg-notes"><b>写作要点</b><ul style="margin:4px 0 0;padding-left:18px">${notes}</ul></div>` : ''}
  </div>`;
}
function switchMsg(i) { UI.msgTab = i; byId('msgZone').innerHTML = renderMessages(); }
function copyMsg() {
  const t = byId('msgBody').innerText;
  const done = () => { byId('copyHint').textContent = '已复制到剪贴板'; setTimeout(() => { byId('copyHint').textContent = ''; }, 2200); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t).then(done).catch(() => fallbackCopy(t, done));
  } else fallbackCopy(t, done);
}
function fallbackCopy(t, done) {
  const ta = document.createElement('textarea');
  ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0';
  document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy'); done(); } catch (e) { byId('copyHint').textContent = '请手动选择文本复制'; }
  document.body.removeChild(ta);
}
function toggleDone(id, on) {
  if (on) UI.done.add(id); else UI.done.delete(id);
  const el = byId('req-' + id); if (el) el.classList.toggle('done', on);
  byId('doneCnt').textContent = UI.done.size;
}
function gotoRequest(id) {
  location.hash = '#sec-gaps';
  const el = byId('req-' + id);
  if (el) { el.style.outline = '2px solid var(--brand-2)'; setTimeout(() => { el.style.outline = ''; }, 1600); }
}

/* ------------------------------------------------------------------ 10 三分结论汇总 + 边界 */
function renderConclusion() {
  const checks = DATA.checks || [];
  const col = (k, title, cls) => {
    const list = checks.filter(c => c.status === k);
    const li = list.map(c => `<li><b>${esc(c.id)}</b> ${esc(c.title)}${c.status === 'discrepancy' ? ` <span class="chip sev-${esc(c.severity)}">${SEV[c.severity]}</span>` : ''}</li>`).join('');
    return `<div class="concl-col ${cls}"><div class="hd">${title}<span class="n">${list.length}</span></div>
      <ul>${li || '<li class="muted">无</li>'}</ul></div>`;
  };
  const bl = arr(DATA.boundaries).map(b => `<li>${esc(b)}</li>`).join('');
  return `<section class="section" id="sec-concl">
    <div class="sec-head"><span class="idx">09</span><h2>结论三分与使用边界</h2>
      <span class="sub">已核实的、有疑点的、无法确认的，分开列；边界写在页面上，而不是只在心里</span></div>
    <div class="concl-grid">
      ${col('verified', '已核实', 'verified')}
      ${col('discrepancy', '存在疑点', 'discrepancy')}
      ${col('unverified', '无法确认', 'unverified')}
    </div>
    <div class="card pad" style="margin-top:14px">
      <div class="card-h"><h3>使用边界</h3></div>
      <ul class="boundary-list" style="padding-left:18px">${bl}</ul>
      <div class="boundary" style="margin-top:12px">${esc(M.disclaimer || '')}</div>
    </div>
  </section>`;
}

/* ------------------------------------------------------------------ 11 来源库 */
function renderSources() {
  const items = (DATA.sources || []).map(s => `<div class="src-item" id="src-${esc(s.id)}">
    <div class="sid">${esc(s.id)}</div>
    <div>${gradeChip(s.grade)}<div class="tiny muted" style="margin-top:4px">${esc(s.kind || '')}</div></div>
    <div class="nm-wrap">
      <div class="nm">${esc(s.name)}</div>
      <div class="org">${esc(s.org || '')} · ${esc(s.date || '')}${s.retrieved ? ' · 检索 ' + esc(s.retrieved) : ''}</div>
      ${s.url ? `<a class="url" href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.url)}</a>` : '<div class="tiny muted">（对方提供 / 无公开链接）</div>'}
      <div class="note">${esc(s.note || '')}</div>
    </div>
  </div>`).join('');
  return `<section class="section" id="sec-sources">
    <div class="sec-head"><span class="idx">10</span><h2>来源库</h2>
      <span class="sub">A=官方登记/政府 · B=独立第三方或企业官网一手 · C=媒体/行业名录 · D=对方自述</span></div>
    <div class="srclist">${items}</div>
  </section>`;
}

/* ------------------------------------------------------------------ 抽屉 */
function openDrawer(title, sub, html) {
  byId('drawerT').textContent = title;
  byId('drawerS').textContent = sub || '';
  byId('drawerB').innerHTML = html;
  byId('drawer').classList.add('on');
  byId('drawer').setAttribute('aria-hidden', 'false');
  byId('mask').classList.add('on');
}
function closeDrawer() {
  byId('drawer').classList.remove('on');
  byId('drawer').setAttribute('aria-hidden', 'true');
  byId('mask').classList.remove('on');
}
function jumpSource(ev, id) {
  ev.preventDefault();
  const s = SOURCE[id];
  if (!s) return;
  openDrawer(s.id + ' · ' + s.name, (s.org || '') + ' · ' + (s.date || ''), `
    <div style="display:flex;gap:8px;margin-bottom:12px">${gradeChip(s.grade)}<span class="chip ghost">${esc(s.kind || '')}</span></div>
    <table class="tbl" style="font-size:13px"><tbody>
      <tr><td class="k" style="width:80px">机构</td><td>${esc(s.org || '—')}</td></tr>
      <tr><td class="k">日期</td><td>${esc(s.date || '—')}</td></tr>
      <tr><td class="k">检索日</td><td>${esc(s.retrieved || '—')}</td></tr>
      <tr><td class="k">类型</td><td>${esc(s.kind || '—')}</td></tr>
      <tr><td class="k">链接</td><td>${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.url)}</a>` : '无公开链接'}</td></tr>
    </tbody></table>
    <div class="boundary" style="margin-top:14px">${esc(s.note || '')}</div>
    <div style="margin-top:16px"><b class="tiny">引用本来源的核验项</b>
      <div style="margin-top:6px">${(DATA.checks || []).filter(c => arr(c.source_ids).indexOf(id) >= 0).map(c => `<span class="chip ghost" style="margin:2px">${esc(c.id)} ${esc(c.title)}</span>`).join('') || '<span class="tiny muted">无</span>'}</div>
    </div>`);
}

/* ------------------------------------------------------------------ 页脚 */
function renderFoot() {
  byId('foot').innerHTML = `<div class="box">
    <div><b>${esc(M.title)}</b> · 编制 ${esc(M.prepared_by || '')} · 核验基准日 ${esc(M.as_of || '')}</div>
    ${M.synthetic ? `<div style="color:var(--warn)"><b>模拟样例：</b>${esc(M.synthetic_note || '')}</div>` : ''}
    <div>${XLSX_NAME ? `配套工作簿：<span class="mono">${esc(XLSX_NAME)}</span>` : ''}</div>
    <div>${esc(M.disclaimer || '')}</div>
  </div>`;
}

/* ------------------------------------------------------------------ 初始化 */
function init() {
  renderNav();
  byId('app').innerHTML = [
    renderHero(), renderInquiry(), renderExtract(), renderSubject(), renderBusiness(),
    renderContact(), renderChecks(), renderRisk(), renderGaps(), renderConclusion(), renderSources()
  ].join('');
  renderCheckList();
  renderFoot();
  syncFilters();
  // 导航高亮
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        document.querySelectorAll('#navLinks button').forEach(b => b.classList.toggle('on', b.getAttribute('onclick').indexOf(e.target.id) >= 0));
      }
    });
  }, { rootMargin: '-80px 0px -70% 0px' });
  document.querySelectorAll('section[id]').forEach(s => obs.observe(s));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
