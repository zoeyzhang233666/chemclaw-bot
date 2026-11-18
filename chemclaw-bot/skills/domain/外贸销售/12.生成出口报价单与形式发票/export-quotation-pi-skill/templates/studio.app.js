/* =============================================================================
   Export Quotation & Proforma Invoice Studio — application shell
   Depends on window.QuoteEngine (engine.js) and window.__DEMO_DATA__ (embedded
   demo case). All commercial values come from the data model only.
   ============================================================================= */
(function () {
  'use strict';
  var E = window.QuoteEngine;
  var EMBEDDED = window.__DEMO_DATA__ || null;
  var LS_KEY = 'eqpi-studio-draft-v1';
  var TPL_KEY = 'eqpi-studio-template-v1';
  var LOG_KEY = 'eqpi-studio-log-v1';

  var S = {
    doc: null,
    tab: 'doc',
    zoom: 0.8,
    font: null,
    openItems: {},
    log: [],
    template: null   // saved company template: {brand, sellerNoBrand}
  };

  /* ------------------------------------------------------------- utilities */
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; });
  }
  function pad(n) { return String(n).padStart(2, '0'); }
  function todayISO() { var d = new Date(); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function nowStamp() { var d = new Date(); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()); }
  function money(v, dp) {
    if (v === null || v === undefined || v === '' || isNaN(Number(v))) return '—';
    dp = (dp === undefined) ? 2 : dp;
    return Number(v).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
  }
  function curCode() { return (S.doc.currency && S.doc.currency.code) || ''; }
  function curDp() { var d = S.doc.currency && S.doc.currency.decimals; return (d === 0 || d === 2) ? d : 2; }
  function amend() {
    S.doc.state = S.doc.state || {};
    S.doc.state.reviewConfirmed = false;
    if (S.doc.state.stage === 'FORMAL') S.doc.state.stage = 'DRAFT';
    S.doc.review = S.doc.review || {};
    S.doc.review.signoff = null;
  }
  function logEvent(kind, msg, extra) {
    S.log.push(Object.assign({ at: nowStamp(), kind: kind, msg: msg, docNo: refText() }, extra || {}));
    try { localStorage.setItem(LOG_KEY, JSON.stringify(S.log.slice(-200))); } catch (e) { }
  }
  function toast(msg) { var t = $('#toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(toast._t); toast._t = setTimeout(function () { t.classList.remove('on'); }, 2600); }

  /* ------------------------------------------------------- data accessors */
  function getPath(o, p) {
    var parts = String(p).split('.'), cur = o;
    for (var i = 0; i < parts.length; i++) { if (cur == null) return undefined; cur = cur[parts[i]]; }
    return cur;
  }
  function setPath(o, p, v) {
    var parts = String(p).split('.'), cur = o;
    for (var i = 0; i < parts.length - 1; i++) { if (!cur[parts[i]] || typeof cur[parts[i]] !== 'object') cur[parts[i]] = {}; cur = cur[parts[i]]; }
    cur[parts[parts.length - 1]] = v;
  }
  function refText() { return (S.doc.reference && S.doc.reference.text) || 'DRAFT'; }
  function isSimulated() {
    var m = S.doc.meta || {}, v = S.doc.view || {};
    if (v.watermark !== false) return true;
    return /simulat|demo/i.test([m.dataClass, S.doc.seller && S.doc.seller.name, S.doc.buyer && S.doc.buyer.name].join(' '));
  }

  /* --------------------------------------------------------- validation   */
  function valid() { return E.validate(S.doc); }

  /* ================================================================ EDITOR */
  var TABS = {
    doc: '单据', parties: '买卖双方', items: '货品/价格', terms: '商务条款', bank: '银行与单证', check: '字段检查', template: '模板与数据'
  };

  function renderForms() {
    var host = $('#forms');
    var scroll = host.scrollTop;
    host.innerHTML = '';
    var openSet = {};
    $$('#forms details.fs').forEach(function (d, i) { openSet[i] = d.open; });
    if (S.tab === 'doc') host.appendChild(formDoc());
    else if (S.tab === 'parties') host.appendChild(formParties());
    else if (S.tab === 'items') host.appendChild(formItems());
    else if (S.tab === 'terms') host.appendChild(formTerms());
    else if (S.tab === 'bank') host.appendChild(formBank());
    else if (S.tab === 'check') host.appendChild(formCheck());
    else if (S.tab === 'template') host.appendChild(formTemplate());
    $$('#forms details.fs').forEach(function (d, i) { if (openSet[i] !== undefined) d.open = openSet[i]; });
    host.scrollTop = scroll;
  }

  function fld(opts) {
    var wrap = document.createElement('div');
    wrap.className = 'fld' + (opts.full ? ' full' : '');
    var id = 'f_' + (opts.id || Math.random().toString(36).slice(2, 8));
    var lab = document.createElement('label');
    lab.setAttribute('for', id);
    lab.innerHTML = esc(opts.label) + (opts.req ? ' <span class="req">*</span>' : '') + (opts.hint ? ' <span class="hint">' + esc(opts.hint) + '</span>' : '');
    wrap.appendChild(lab);
    var el;
    if (opts.type === 'select') {
      el = document.createElement('select');
      (opts.options || []).forEach(function (o) {
        var op = document.createElement('option');
        if (typeof o === 'string') { op.value = o; op.textContent = o; } else { op.value = o.v; op.textContent = o.t; }
        el.appendChild(op);
      });
      el.value = opts.value === undefined || opts.value === null ? '' : opts.value;
    } else if (opts.type === 'textarea') {
      el = document.createElement('textarea'); el.value = opts.value || '';
    } else {
      el = document.createElement('input');
      el.type = opts.type || 'text';
      if (opts.step) el.step = opts.step;
      el.value = opts.value === undefined || opts.value === null ? '' : opts.value;
      if (opts.placeholder) el.placeholder = opts.placeholder;
    }
    el.id = id;
    if (opts.disabled) el.disabled = true;
    el.addEventListener('input', function () { opts.onInput && opts.onInput(el.value, el); });
    el.addEventListener('change', function () { opts.onChange && opts.onChange(el.value, el); });
    if (opts.after) el.addEventListener('blur', opts.after);
    wrap.appendChild(el);
    if (opts.msg) { var m = document.createElement('div'); m.className = 'msg'; m.textContent = opts.msg; wrap.appendChild(m); }
    return wrap;
  }
  function bind(path, opts) {
    opts = opts || {};
    var v = getPath(S.doc, path);
    return Object.assign({
      value: v,
      onInput: function (val, el) {
        var out = val;
        if (opts.num) { out = val === '' ? '' : Number(val); if (isNaN(out)) out = ''; }
        setPath(S.doc, path, out);
        amend();
        if (opts.noRerender) { softUpdate(); } else { rerender({ keepFocus: el.id }); }
      }
    }, opts);
  }
  function fs(title, open, bodyNodes, meta) {
    var d = document.createElement('details');
    d.className = 'fs'; if (open) d.open = true;
    var s = document.createElement('summary');
    s.innerHTML = esc(title) + (meta ? ' <span class="mini" style="font-weight:500">' + meta + '</span>' : '');
    d.appendChild(s);
    var b = document.createElement('div'); b.className = 'body';
    bodyNodes.forEach(function (n) { if (n) b.appendChild(n); });
    d.appendChild(b);
    return d;
  }
  function grid(cls, nodes) { var g = document.createElement('div'); g.className = cls; nodes.forEach(function (n) { if (n) g.appendChild(n); }); return g; }
  function hint(text) { var p = document.createElement('div'); p.className = 'mini'; p.style.margin = '6px 0'; p.innerHTML = text; return p; }
  function checkbox(label, checked, onChange) {
    var l = document.createElement('label'); l.className = 'chk';
    var i = document.createElement('input'); i.type = 'checkbox'; i.checked = !!checked;
    i.addEventListener('change', function () { onChange(i.checked); });
    var s = document.createElement('span'); s.textContent = label;
    l.appendChild(i); l.appendChild(s); return l;
  }

  function formDoc() {
    var frag = document.createDocumentFragment();
    var dpts = [{ v: 'QUOTATION', t: 'Quotation 报价单' }, { v: 'PROFORMA_INVOICE', t: 'Proforma Invoice 形式发票' }];
    frag.appendChild(fs('① 单据基本资料', true, [
      grid('g2', [
        fld(Object.assign({ label: '单据类型 Document type', type: 'select', options: dpts, req: true }, bind('docType', { onChange: function (v) { S.doc.docType = v; amend(); rerender(); } }))),
        fld(Object.assign({ label: '单据编号 Document No.', req: true, hint: 'auto, editable' }, bind('reference.text', { noRerender: true }))),
        fld(Object.assign({ label: '签发日期 Issue date', type: 'date', req: true }, bind('issueDate'))),
        fld(Object.assign({ label: '我方报价参考 Our reference' }, bind('reference.quotationRef'))),
        fld(Object.assign({ label: '买方询盘参考 Your enquiry ref.' }, bind('reference.buyerInquiryRef'))),
        fld(Object.assign({ label: '买方订单号 PO / reference' }, bind('reference.buyerPoNo'))),
        fld(Object.assign({ label: '币种 Currency', type: 'select', req: true, options: ['USD', 'EUR', 'CNY', 'IDR', 'SGD', 'JPY', 'HKD', 'AUD', 'GBP', 'INR'] }, bind('currency.code', { onChange: function (v) { S.doc.currency.code = v; S.doc.currency.decimals = v === 'IDR' || v === 'JPY' ? 0 : 2; amend(); rerender(); } }))),
        fld(Object.assign({ label: '小数位 Decimals', type: 'select', options: [{ v: '2', t: '2 decimals' }, { v: '0', t: '0 decimals' }] }, bind('currency.decimals', { onChange: function (v) { S.doc.currency.decimals = Number(v); amend(); rerender(); } })))
      ])
    ]));
    frag.appendChild(fs('② 报价有效期', true, [
      grid('g2', [
        fld(Object.assign({ label: '有效期方式', type: 'select', options: [{ v: 'date', t: '截止日期 date' }, { v: 'days', t: '天数 days' }] }, bind('validity.type', { onChange: function (v) { S.doc.validity.type = v; amend(); rerender(); } }))),
        S.doc.validity.type === 'days'
          ? fld(Object.assign({ label: '有效天数 Days', type: 'number' }, bind('validity.days', { num: true })))
          : fld(Object.assign({ label: '有效期截止 Valid until', type: 'date', req: true }, bind('validity.validUntil')))
      ])
    ]));
    frag.appendChild(fs('③ 汇率参考（仅供备注，不进入报价金额）', false, [
      grid('g3', [
        fld({ label: '基准币种', hint: '同币种无意义', type: 'select', value: (S.doc.currency.exchangeRate || {}).base, options: ['', 'USD', 'EUR', 'CNY', 'IDR', 'SGD', 'JPY', 'HKD'],
          onChange: function (v) { ensureFx().base = v; amend(); rerender(); } }),
        fld({ label: '汇率 1 基准 = ? 报价币', type: 'number', step: '0.0001', value: (S.doc.currency.exchangeRate || {}).rate,
          onInput: function (v) { ensureFx().rate = v === '' ? '' : Number(v); ensureFx().state = 'reference'; amend(); softUpdate(); } }),
        fld({ label: '取数日期', type: 'date', value: (S.doc.currency.exchangeRate || {}).asOf,
          onChange: function (v) { ensureFx().asOf = v; amend(); rerender(); } })
      ]),
      hint('汇率仅作脚注参考；报价金额以确认单价与数量计算，不因汇率变动自动改写。'),
      checkbox('确认该汇率快照（用户确认后才可在单据脚注显示为确认值）', (S.doc.currency.exchangeRate || {}).state === 'confirmed',
        function (c) { ensureFx().state = c ? 'confirmed' : 'reference'; if (c) ensureFx().confirmedBy = 'operator'; amend(); rerender(); }),
      fld({ label: '脚注显示方式', type: 'select', value: (S.doc.currency.exchangeRate || {}).display, options: [{ v: 'footnote', t: 'footnote 脚注' }, { v: 'quotation', t: 'quotation 单据内注明' }, { v: 'none', t: 'none 不显示' }],
        onChange: function (v) { ensureFx().display = v; amend(); rerender(); } })
    ]));
    frag.appendChild(fs('④ 单证与签署', false, [
      fld({ label: '所需单证 Documents required（每行一项）', type: 'textarea', value: (S.doc.documents || []).map(function (x) { return x.name; }).join('\n'),
        onInput: function (v) { S.doc.documents = v.split('\n').map(function (s) { return s.trim(); }).filter(Boolean).map(function (n) { return { name: n }; }); amend(); softUpdate(); } }),
      fld({ label: '签署人职务 Signatory title', value: (S.doc.review && S.doc.review.signatoryTitle) || 'Export Sales Manager',
        onInput: function (v) { S.doc.review = S.doc.review || {}; S.doc.review.signatoryTitle = v; } }),
      checkbox('显示签名线 Signature block', (S.doc.view || {}).signature !== false, function (c) { S.doc.view.signature = c; rerender(); })
    ]));
    return frag;
  }

  function formParties() {
    var frag = document.createDocumentFragment();
    var L = '卖家 Seller', B = '买家 Buyer';
    frag.appendChild(fs('① 卖方信息 Seller', true, [
      grid('g2', [
        fld(Object.assign({ label: 'Company name', req: true, full: true }, bind('seller.name'))),
        fld(Object.assign({ label: 'Address', req: true, type: 'textarea', full: true }, bind('seller.address'))),
        fld(Object.assign({ label: 'Country', full: false }, bind('seller.country'))),
        fld(Object.assign({ label: 'Tax ID / USCI' }, bind('seller.taxId'))),
        fld(Object.assign({ label: 'Contact person' }, bind('seller.contact'))),
        fld(Object.assign({ label: 'Phone' }, bind('seller.phone'))),
        fld(Object.assign({ label: 'E-mail', full: true }, bind('seller.email'))),
        fld(Object.assign({ label: 'Logo 文字 (≤12 字符)', hint: '文件内可直接替换 Logo' }, bind('seller.logoText'))),
        fld(Object.assign({ label: '页脚简称 Footer mark' }, bind('seller.shortName')))
      ])
    ]));
    frag.appendChild(fs('② 买方信息 Buyer', true, [
      grid('g2', [
        fld(Object.assign({ label: 'Company name', req: true, full: true }, bind('buyer.name'))),
        fld(Object.assign({ label: 'Address', req: true, type: 'textarea', full: true }, bind('buyer.address'))),
        fld(Object.assign({ label: 'Country', req: true }, bind('buyer.country'))),
        fld(Object.assign({ label: 'Attention 联系人' }, bind('buyer.contact'))),
        fld(Object.assign({ label: 'Position' }, bind('buyer.position'))),
        fld(Object.assign({ label: 'Phone' }, bind('buyer.phone'))),
        fld(Object.assign({ label: 'E-mail' }, bind('buyer.email'))),
        fld(Object.assign({ label: 'Tax number NPWP / VAT' }, bind('buyer.npwp')))
      ])
    ]));
    return frag;
  }

  function formItems() {
    var frag = document.createDocumentFragment();
    var items = S.doc.items || [];
    var calc = E.compute(S.doc);
    items.forEach(function (it, i) {
      var L = calc.lines[i] || {};
      var open = !!S.openItems[it.id];
      var card = document.createElement('details');
      card.className = 'itemcard'; card.open = open; card.style.marginBottom = '10px';
      card.addEventListener('toggle', function () { S.openItems[it.id] = card.open; });
      var hd = document.createElement('summary');
      hd.style.cssText = 'cursor:pointer;list-style:none';
      hd.innerHTML = '<span>#' + (i + 1) + ' &nbsp;' + esc(it.name || '(未填品名)') + '</span><span style="font-variant-numeric:tabular-nums">' + esc(it.quantity) + ' ' + esc(it.unit) + ' × ' + esc(curCode()) + ' ' + esc(it.unitPrice) + '</span>';
      card.appendChild(hd);
      var bd = document.createElement('div'); bd.className = 'bd';
      bd.appendChild(grid('g2', [
        fld(Object.assign({ label: 'English product name', req: true, full: true }, bind('items.' + i + '.name'))),
        fld(Object.assign({ label: 'CAS Registry No.', hint: 'format NNNNNNN-NN-N' }, bind('items.' + i + '.cas'))),
        fld(Object.assign({ label: 'HS code (6/8/10 digits)' }, bind('items.' + i + '.hsCode'))),
        fld(Object.assign({ label: 'Specification / grade', req: true, type: 'textarea', full: true }, bind('items.' + i + '.spec'))),
        fld(Object.assign({ label: 'Origin' }, bind('items.' + i + '.origin'))),
        fld(Object.assign({ label: 'Moisture / assay % (optional)' }, bind('items.' + i + '.moisturePct', { num: true }))),
        fld(Object.assign({ label: 'Quantity', req: true, type: 'number', step: '0.001' }, bind('items.' + i + '.quantity', { num: true }))),
        fld(Object.assign({ label: 'Unit', req: true, type: 'select', options: ['MT', 'KG', 'L', 'IBC', 'DRUM', 'BAG', 'PCS'] }, bind('items.' + i + '.unit'))),
        fld(Object.assign({ label: 'Unit price (' + curCode() + '/' + (it.unit || 'unit') + ')', req: true, hint: 'user-confirmed', type: 'number', step: '0.0001' }, bind('items.' + i + '.unitPrice', { num: true }))),
        fld(Object.assign({ label: 'Discount %', type: 'number', step: '0.01' }, bind('items.' + i + '.discountPct', { num: true }))),
        fld(Object.assign({ label: 'Packages (bags/drums)', type: 'number' }, bind('items.' + i + '.packageCount', { num: true }))),
        fld({ label: 'Gross kg / package', type: 'number', step: '0.001', value: (it.packageWeight || {}).value,
          onInput: function (v) { it.packageWeight = Object.assign({ unit: 'KG' }, it.packageWeight || {}); it.packageWeight.value = v === '' ? '' : Number(v); amend(); softUpdate(); } })
      ]));
      // Dangerous goods
      var dg = it.dangerousGoods || {};
      bd.appendChild(grid('g2', [
        fld({ label: 'DG status', type: 'select', value: dg.status || 'UNKNOWN', options: [{ v: 'UNKNOWN', t: 'UNKNOWN — not verified' }, { v: 'NOT_REGULATED', t: 'NOT REGULATED — not DG' }, { v: 'DG', t: 'DG — dangerous goods' }],
          onChange: function (v) { it.dangerousGoods = it.dangerousGoods || {}; it.dangerousGoods.status = v; amend(); rerender(); } }),
        fld({ label: 'GHS summary', value: dg.ghsSummary || '', onInput: function (v) { it.dangerousGoods = it.dangerousGoods || {}; it.dangerousGoods.ghsSummary = v; amend(); softUpdate(); } }),
        fld({ label: 'DG basis / UN No. / class / PG', full: true, value: [dg.basis, dg.unNumber, dg.class, dg.packingGroup].filter(Boolean).join(' | '), onInput: function (v) { it.dangerousGoods = it.dangerousGoods || {}; it.dangerousGoods.basis = v; amend(); softUpdate(); } })
      ]));
      // live calc
      var box = document.createElement('div'); box.className = 'calcbox';
      var conf = (it.amountState && it.amountState !== 'draft');
      box.innerHTML =
        '<div class="line"><span>数量 × 单价</span><b>' + esc(it.quantity) + ' × ' + esc(it.unitPrice) + ' = ' + esc(money(L.gross, curDp())) + '</b></div>' +
        '<div class="line"><span>折扣</span><b>' + esc(it.discountPct || 0) + '%</b></div>' +
        '<div class="line"><span>行金额 Amount</span><b style="color:#14304e">' + (L.netForTotal !== undefined ? esc(curCode()) + ' ' + esc(money(L.netForTotal, curDp())) : '<span class="placeholder">UNIT PRICE MISSING</span>') + '</b></div>' +
        '<div class="formula">' + (L.netForTotal !== undefined ? esc(money(L.gross, curDp())) + ' × (1 − ' + esc((it.discountPct || 0) / 100) + ') = ' + esc(money(L.netForTotal, curDp())) : 'no amount until unit price is entered') + '</div>' +
        (conf && L.confirmedDiff !== undefined ? '<div class="line"><span>确认金额 Confirmed</span><b>' + esc(money(it.amountConfirmedValue, curDp())) + '</b></div>' : '') +
        (L.confirmedDiff !== undefined && Math.abs(L.confirmedDiff) > 0.005 ? '<div class="mismatch">⚠ 确认金额与重算不一致：差额 ' + esc(money(L.confirmedDiff, curDp())) + '</div>' : '');
      bd.appendChild(box);
      bd.appendChild(checkbox('我已确认该行单价与金额（' + (it.unitPrice === '' ? '未填' : '单价 ' + it.unitPrice + ' ' + curCode() + '/' + (it.unit || '') + '，金额 ' + money(L.netForTotal, curDp())) + '）', conf && !L.confirmedDiff,
        function (c) {
          it.amountState = c ? 'confirmed' : 'draft';
          if (c) it.amountConfirmedValue = L.netForTotal; else delete it.amountConfirmedValue;
          amend(); logEvent(c ? 'PRICE_CONFIRMED' : 'PRICE_UNCONFIRMED', 'Line ' + (i + 1) + ' price ' + (c ? 'confirmed' : 'un-confirmed by user') + ': ' + it.unitPrice + ' ' + curCode() + '/' + it.unit + ' × ' + it.quantity + ' = ' + (L.netForTotal !== undefined ? L.netForTotal : ''));
          rerender();
        }));
      if (items.length > 1) {
        var del = document.createElement('button'); del.className = 'btn sm danger'; del.textContent = '删除此行';
        del.addEventListener('click', function () { items.splice(i, 1); amend(); rerender(); });
        var rr = document.createElement('div'); rr.className = 'row'; rr.style.marginTop = '8px'; rr.appendChild(del); bd.appendChild(rr);
      }
      card.appendChild(bd);
      frag.appendChild(card);
    });
    var addBtn = document.createElement('button'); addBtn.className = 'btn'; addBtn.textContent = '＋ 增加产品行';
    addBtn.addEventListener('click', function () {
      var tpl = clone(items[0] || { unit: 'MT', dangerousGoods: { status: 'UNKNOWN' } });
      tpl.id = 'L' + Date.now(); tpl.name = ''; tpl.cas = ''; tpl.hsCode = ''; tpl.spec = '';
      tpl.quantity = ''; tpl.unitPrice = ''; tpl.amountState = 'draft'; delete tpl.amountConfirmedValue; tpl.packageCount = '';
      S.openItems[tpl.id] = true;
      S.doc.items.push(tpl); amend(); rerender();
    });
    var wrap = document.createElement('div'); wrap.className = 'row'; wrap.style.margin = '4px 0 12px'; wrap.appendChild(addBtn); frag.appendChild(wrap);

    // charges
    frag.appendChild(fs('附加费用 Charges（仅用户确认金额才计入总额）', false, (S.doc.charges || []).map(function (c, i) {
      return grid('g3', [
        fld({ label: 'Fee name', value: c.name, onInput: function (v) { c.name = v; amend(); softUpdate(); } }),
        fld({ label: 'Amount (' + curCode() + ')', type: 'number', step: '0.01', value: c.amount, onInput: function (v) { c.amount = v === '' ? '' : Number(v); amend(); rerender(); } }),
        fld({ label: 'Add to total', type: 'select', value: c.addToTotal === false ? 'no' : 'yes', options: [{ v: 'yes', t: 'yes 计入总额' }, { v: 'no', t: 'no 参考/买方承担' }], onChange: function (v) { c.addToTotal = v === 'yes'; amend(); rerender(); } })
      ]);
    })));
    return frag;
  }

  function formTerms() {
    var frag = document.createDocumentFragment();
    var t = S.doc.tradeTerm, inc = Object.keys(E.TERMS);
    frag.appendChild(fs('① 贸易术语 Incoterms®', true, [
      grid('g3', [
        fld(Object.assign({ label: 'Rule', req: true, type: 'select', options: inc.map(function (k) { return { v: k, t: k + ' · ' + E.TERMS[k].name }; }) }, bind('tradeTerm.code', { onChange: function (v) { S.doc.tradeTerm.code = v; amend(); rerender(); } }))),
        fld(Object.assign({ label: 'Version', req: true, type: 'select', options: [{ v: '2020', t: 'Incoterms® 2020' }, { v: '2010', t: 'Incoterms® 2010' }] }, bind('tradeTerm.version', { onChange: function (v) { S.doc.tradeTerm.version = v; amend(); rerender(); } }))),
        fld(Object.assign({ label: 'Transport mode', type: 'select', options: ['SEA', 'AIR', 'MULTIMODAL'] }, bind('tradeTerm.transportMode', { onChange: function (v) { S.doc.tradeTerm.transportMode = v; amend(); rerender(); } })))
      ]),
      fld(Object.assign({ label: (t && E.TERMS[t.code] && E.TERMS[t.code].named === 'port' ? 'Named port' : 'Named place') + ' — required', req: true, full: true }, bind('tradeTerm.namedPlace', { noRerender: true }))),
      fld(Object.assign({ label: 'Insurance cover (CIF/CIP)', full: true }, bind('tradeTerm.insuranceBasis', { noRerender: true }))),
      grid('g2', [
        fld(Object.assign({ label: 'Port of loading' }, bind('freight.estimatedPol', { noRerender: true }))),
        fld(Object.assign({ label: 'Port of discharge' }, bind('freight.estimatedPod', { noRerender: true })))
      ])
    ]));
    // cost matrix
    var rows = E.COST_MATRIX.rows;
    var std = E.COST_MATRIX.standard[t.code] || {};
    var ca = t.costAllocation || {};
    frag.appendChild(fs('② 费用责任划分（勾选 = 卖方承担；与术语冲突会提示）', false, rows.map(function (r) {
      var seller = String(ca[r.key] || std[r.key] || 'B').toLowerCase().charAt(0) === 's';
      return checkbox(r.label + ' <span class="mini">[标准 ' + (std[r.key] || '?').toUpperCase() + ']</span>', seller, function (c) {
        S.doc.tradeTerm.costAllocation = S.doc.tradeTerm.costAllocation || {};
        S.doc.tradeTerm.costAllocation[r.key] = c ? 'Seller' : 'Buyer'; amend(); rerender();
      });
    })));
    frag.appendChild(fs('③ 包装与重量 Packing', true, [
      fld(Object.assign({ label: 'Packing summary', req: true, type: 'textarea', full: true }, bind('packing.summary', { noRerender: true }))),
      fld(Object.assign({ label: 'Packing terms / marking', type: 'textarea', full: true }, bind('packing.terms', { noRerender: true }))),
      grid('g2', [
        fld(Object.assign({ label: 'Net kg per bag (bag-count check)', type: 'number', step: '0.1' }, bind('packing.bagNetKg', { num: true, noRerender: true }))),
        fld(Object.assign({ label: 'Total packages', type: 'number' }, bind('totalPackageCount', { num: true, noRerender: true }))),
        fld(Object.assign({ label: 'Gross weight', hint: 'e.g. 1,008,000 kg (1,008.00 MT)' }, bind('totalGrossWeight', { noRerender: true }))),
        fld(Object.assign({ label: 'Total volume CBM' }, bind('totalVolume', { noRerender: true })))
      ])
    ]));
    frag.appendChild(fs('④ 交期 Delivery', true, [
      fld(Object.assign({ label: 'Lead time', req: true, full: true }, bind('delivery.leadTime', { noRerender: true }))),
      fld(Object.assign({ label: 'Basis of counting', full: true }, bind('delivery.basis', { noRerender: true }))),
      grid('g2', [
        fld(Object.assign({ label: 'Partial shipment', type: 'select', options: ['Not allowed', 'Allowed'] }, bind('delivery.partialShipment', { noRerender: true }))),
        fld(Object.assign({ label: 'Transhipment', type: 'select', options: ['Allowed', 'Not allowed'] }, bind('delivery.transhipment', { noRerender: true })))
      ])
    ]));
    frag.appendChild(fs('⑤ 付款条件 Payment（必须由用户确认填写）', true, [
      fld(Object.assign({ label: 'Payment terms text', req: true, type: 'textarea', full: true }, bind('payment.terms', { noRerender: true }))),
      grid('g2', [
        fld(Object.assign({ label: 'Payment type', type: 'select', options: [{ v: 'PREPAY', t: 'T/T in advance' }, { v: 'LC', t: 'L/C at sight' }, { v: 'DP', t: 'D/P' }, { v: 'DA', t: 'D/A' }, { v: 'OA', t: 'Open account' }, { v: 'MIX', t: 'Split (EA + balance)' }] }, bind('payment.code', { onChange: function (v) { S.doc.payment.code = v; amend(); rerender(); } }))),
        fld(Object.assign({ label: 'Advance share % (if any)', type: 'number' }, bind('payment.amountPct', { num: true, noRerender: true }))),
        fld(Object.assign({ label: 'Payment account / beneficiary', full: true }, bind('payment.beneficiary', { noRerender: true }))),
        fld(Object.assign({ label: 'Beneficiary note', full: true }, bind('payment.beneficiaryNote', { noRerender: true })))
      ])
    ]));
    return frag;
  }

  function formBank() {
    var frag = document.createDocumentFragment();
    var b = S.doc.bank = S.doc.bank || { display: false, sanitized: true, detailsConfirmed: false };
    frag.appendChild(fs('① 银行资料 Banking', true, [
      hint('⚠ 演示规则：<b>绝不生成或引用任何可能被误认为真实的账号</b>。真实业务请从你确认的银行开户资料复制完整信息，并勾选“已核对”。'),
      checkbox('在单据中显示银行信息块', !!b.display, function (c) {
        if (c && b.sanitized) { toast('占位/屏蔽的银行信息不能作为有效银行资料显示'); return; }
        b.display = c; amend(); rerender();
      }),
      checkbox('该资料为占位符 / 已屏蔽（sanitized）', b.sanitized !== false, function (c) { b.sanitized = c; amend(); rerender(); }),
      grid('g2', [
        fld({ label: 'Bank name', full: true, disabled: !!b.sanitized, value: b.bankName, onInput: function (v) { b.bankName = v; amend(); softUpdate(); } }),
        fld({ label: 'Account name', disabled: !!b.sanitized, value: b.accountName, onInput: function (v) { b.accountName = v; amend(); softUpdate(); } }),
        fld({ label: 'A/C No.', disabled: !!b.sanitized, value: b.accountNumber, onInput: function (v) { b.accountNumber = v; amend(); softUpdate(); } }),
        fld({ label: 'SWIFT / BIC', disabled: !!b.sanitized, value: b.swift, onInput: function (v) { b.swift = v; amend(); softUpdate(); } }),
        fld({ label: 'IBAN / Bank address', disabled: !!b.sanitized, value: b.addressLine, onInput: function (v) { b.addressLine = v; amend(); softUpdate(); } })
      ]),
      checkbox('我已对照银行开户资料核对以上全部信息（A/C 号、SWIFT、户名）', !!b.detailsConfirmed, function (c) {
        b.detailsConfirmed = c;
        if (c && !b.bankName) { toast('请先填写银行名称再确认'); b.detailsConfirmed = false; }
        amend(); logEvent(c ? 'BANK_CONFIRMED' : 'BANK_UNCONFIRMED', 'Bank details ' + (c ? 'confirmed by user' : 'un-confirmed by user')); rerender();
      })
    ]));
    frag.appendChild(fs('② 单据复核与签发', true, [
      hint('正式文件必须由持有权限的人完成复核。系统只记录“谁在何时确认”，不替你做决定。'),
      fld({ label: '复核人姓名 Reviewer name', value: (S.doc.review || {}).name || '', onInput: function (v) { S.doc.review = S.doc.review || {}; S.doc.review.name = v; } }),
      fld({ label: '签署人职务 Signatory title', value: (S.doc.review || {}).signatoryTitle || '', onInput: function (v) { S.doc.review = S.doc.review || {}; S.doc.review.signatoryTitle = v; } }),
      checkbox('我已逐项核对价格、数量、币种、金额、包装、贸易术语与付款条件', !!(S.doc.review || {}).itemsChecked, function (c) { S.doc.review = S.doc.review || {}; S.doc.review.itemsChecked = c; amend(); rerender(); }),
      checkbox('我确认这是正式文件，而非草稿（FORMAL ISSUE）', !!(S.doc.review || {}).formalApproved, function (c) {
        S.doc.review = S.doc.review || {}; S.doc.review.formalApproved = c; amend(); logEvent(c ? 'FORMAL_APPROVED_REQUEST' : 'FORMAL_REVOKED', 'User ' + (c ? 'requested formal issue' : 'revoked formal issue')); rerender();
      })
    ]));
    return frag;
  }

  function formCheck() {
    var v = valid();
    var frag = document.createDocumentFragment();
    var wrap = document.createElement('div');
    wrap.innerHTML = '<div class="mini" style="margin-bottom:8px">必要字段 ' + v.completeness.filled + ' / ' + v.completeness.required +
      ' 已填 · 错误 ' + v.errors.length + ' · 提示 ' + v.warnings.length + '</div>';
    var tb = document.createElement('table');
    tb.style.cssText = 'width:100%;border-collapse:collapse;font-size:12px';
    tb.innerHTML = '<thead><tr><th style="text-align:left;padding:5px 4px;border-bottom:1px solid #dde3ec">字段</th><th style="text-align:left;padding:5px 4px;border-bottom:1px solid #dde3ec">状态</th></tr></thead>';
    var tbody = document.createElement('tbody');
    v.completeness.rows.forEach(function (r) {
      var tr = document.createElement('tr');
      var st = r.filled ? (r.required ? 'ok' : 'opt') : (r.required ? 'no' : 'opt');
      var label = r.filled && r.required ? '已确认' : (!r.filled && r.required ? '缺失' : (r.filled ? '已填' : '未填(可选)'));
      tr.innerHTML = '<td style="padding:4px;border-bottom:1px solid #eef2f7">' + esc(r.label) + (r.filled ? '<div class="mini">' + esc(String(r.value).slice(0, 60)) + (String(r.value).length > 60 ? '…' : '') + '</div>' : '') + '</td>' +
        '<td style="padding:4px;border-bottom:1px solid #eef2f7"><span class="tag ' + st + '">' + label + '</span></td>';
      tbody.appendChild(tr);
    });
    tb.appendChild(tbody); wrap.appendChild(tb);
    frag.appendChild(wrap);
    return frag;
  }

  function formTemplate() {
    var frag = document.createDocumentFragment();
    frag.appendChild(fs('① 公司模板 Company template', true, [
      hint('保存公司抬头/品牌样式（主色、字体、Logo 文字、水印）以便下次复用；也可上传 .json 模板文件。'),
      grid('g2', [
        fld({ label: 'Brand accent', type: 'color', value: (S.doc.view || {}).accentColor || '#1b3a5b', onInput: function (v) { S.doc.view = S.doc.view || {}; S.doc.view.accentColor = v; $('#accent').value = v; softUpdate(); } }),
        fld({ label: 'Logo 文字', value: S.doc.seller && S.doc.seller.logoText, onInput: function (v) { S.doc.seller.logoText = v; softUpdate(); } })
      ]),
      checkbox('Mark as simulated demo (adds A4 watermark)', (S.doc.view || {}).watermark !== false, function (c) { S.doc.view = S.doc.view || {}; S.doc.view.watermark = c; $('#wmchk').checked = c; rerender(); }),
      (function () {
        var r = document.createElement('div'); r.className = 'row'; r.style.marginTop = '8px';
        var a = document.createElement('button'); a.className = 'btn'; a.textContent = '💾 保存为公司模板';
        a.addEventListener('click', function () { saveTemplate(); });
        var b2 = document.createElement('button'); b2.className = 'btn'; b2.textContent = '📥 载入公司模板';
        b2.addEventListener('click', function () { loadTemplate(); });
        var c2 = document.createElement('button'); c2.className = 'btn'; c2.textContent = '⬇ 导出模板 JSON';
        c2.addEventListener('click', function () {
          download('company-template-' + todayISO() + '.json', JSON.stringify(templateSnapshot(), null, 2), 'application/json');
        });
        r.appendChild(a); r.appendChild(b2); r.appendChild(c2); return r;
      })()
    ]));
    frag.appendChild(fs('② 数据与示例 Data', false, [
      hint('演示数据类：<b>' + esc((S.doc.meta || {}).dataClass || 'n/a') + '</b><br>请勿把演示数据与真实业务数据混合使用。'),
      (function () {
        var r = document.createElement('div'); r.className = 'row';
        var a = document.createElement('button'); a.className = 'btn'; a.textContent = '📂 载入 JSON 数据';
        a.addEventListener('click', function () { $('#loadfile').click(); });
        var b2 = document.createElement('button'); b2.className = 'btn'; b2.textContent = '🗑 清空为新报价';
        b2.addEventListener('click', function () { if (confirm('清空全部内容并开始一张新单据？')) { S.doc = blankDoc(); amend(); rerender(); } });
        r.appendChild(a); r.appendChild(b2); return r;
      })()
    ]));
    frag.appendChild(fs('③ 操作记录 Log (' + S.log.length + ')', false, S.log.slice(-14).reverse().map(function (l) {
      var d = document.createElement('div'); d.className = 'mini'; d.style.marginBottom = '3px';
      d.textContent = '[' + l.at + '] ' + l.kind + ' — ' + l.msg; return d;
    })));
    return frag;
  }

  function ensureFx() { S.doc.currency = S.doc.currency || {}; S.doc.currency.exchangeRate = S.doc.currency.exchangeRate || { base: '', rate: '', asOf: '', state: 'reference', display: 'footnote' }; return S.doc.currency.exchangeRate; }

  /* =============================================================== PREVIEW */
  function placeholderSpan(txt) { return '<span class="placeholder">' + esc(txt) + '</span>'; }

  function renderPaper() {
    var d = S.doc, v = valid(), calc = v.calc;
    var isPI = d.docType === 'PROFORMA_INVOICE';
    var acc = (d.view || {}).accentColor || '#1b3a5b';
    var dp = curDp();
    var paper = $('#paper');
    paper.style.setProperty('--daccent', acc);
    if (S.font) paper.style.fontFamily = S.font;
    var wm = (d.view || {}).watermark !== false;
    var sim = isSimulated();
    var seller = d.seller || {}, buyer = d.buyer || {};
    var tt = E.tradeTermText(d.tradeTerm);
    var e = esc;
    var missP = function (val, ph) { return (val === undefined || val === null || String(val).trim() === '') ? placeholderSpan(ph || 'TO BE CONFIRMED') : e(val); };
    var ed = function (attr, path, ph) {
      var val = getPath(d, path);
      return '<span class="editable" data-edit="' + attr + '" data-path="' + path + '">' + ((val === undefined || val === null || String(val).trim() === '') ? placeholderSpan(ph) : e(val)) + '</span>';
    };

    var html = '';
    // watermark
    html += '<div class="wm' + (v.state === 'FORMAL' ? ' formal' : '') + '" style="display:' + (wm ? 'grid' : 'none') + '"><span>' + (sim ? 'SIMULATED DEMO · 模拟演示' : (v.state === 'FORMAL' ? 'ORIGINAL' : 'DRAFT')) + '</span></div>';
    html += '<div class="inner">';

    // header
    html += '<div class="doc-head"><div class="left">' +
      ((d.view || {}).logo !== false ? '<div class="logo" title="Click to upload logo">' + e(seller.logoText || 'LOGO') + '</div>' : '') +
      '<div><div class="seller-name editable" data-edit="seller-name" data-path="seller.name">' + missP(seller.name, 'SELLER NAME') + '</div>' +
      '<div class="seller-sub editable" data-edit="seller-addr" data-path="seller.address">' + missP(seller.address, 'SELLER ADDRESS') + '</div>' +
      '<div class="seller-sub">' + (seller.phone ? 'Tel ' + e(seller.phone) : '') + (seller.email ? ' · ' + e(seller.email) : '') + '</div></div></div>' +
      '<div class="doc-title"><h2>' + (isPI ? 'Proforma Invoice' : 'Quotation') + '</h2>' +
      '<div class="sub">' + (isPI ? '形式发票 · For buyer\'s import procedure' : '报价单 · Commercial offer') + '</div>' +
      '<div class="no">No. <span class="editable" data-edit="ref" data-path="reference.text">' + e(refText()) + '</span></div>' +
      '<div class="dt">Date: <span class="editable" data-edit="issueDate" data-path="issueDate">' + missP(d.issueDate, 'ISSUE DATE') + '</span></div></div></div>';

    // addresses
    html += '<div class="addr"><div class="box"><h4>Seller / Exporter</h4><div class="bn">' + missP(seller.name) + '</div>' +
      '<p>' + missP(seller.address) + '</p>' +
      '<p>' + [seller.contact, seller.phone, seller.email].filter(Boolean).map(e).join(' · ') + '</p>' +
      (seller.taxId ? '<p>Tax ID / USCI: ' + e(seller.taxId) + '</p>' : '') + '</div>' +
      '<div class="box"><h4>Buyer / Consignee</h4><div class="bn editable" data-edit="buyer-name" data-path="buyer.name">' + missP(buyer.name, 'BUYER NAME') + '</div>' +
      '<p class="editable" data-edit="buyer-addr" data-path="buyer.address">' + missP(buyer.address, 'BUYER ADDRESS') + '</p>' +
      '<p>' + (buyer.contact ? 'Attn: ' + e(buyer.contact) : '') + (buyer.email ? '<br>E-mail: ' + e(buyer.email) : '') + (buyer.npwp ? '<br>NPWP: ' + e(buyer.npwp) : '') + '</p></div></div>';

    // meta strip
    html += '<div class="meta-strip">' +
      '<div><div class="k">Incoterms 2020</div><div class="v editable" data-edit="incoterm" data-path="tradeTerm.namedPlace">' + missP(tt, 'INCOTERMS REQUIRED') + '</div></div>' +
      '<div><div class="k">Currency</div><div class="v">' + e(curCode()) + '</div></div>' +
      '<div><div class="k">' + (d.validity && d.validity.type === 'days' ? 'Valid for' : (isPI ? 'Proforma valid until' : 'Offer valid until')) + '</div><div class="v">' + (d.validity && d.validity.type === 'days' ? e(d.validity.days + ' days') : missP(v.validUntil, 'VALIDITY')) + '</div></div>' +
      '<div><div class="k">' + (isPI ? 'Payment' : 'Payment terms') + '</div><div class="v sm">' + missP((d.payment || {}).terms, 'PAYMENT TERMS TO BE CONFIRMED').replace(/<span class="placeholder">(.*?)<\/span>/g, '<span class="placeholder">$1</span>') + '</div></div>' +
      '</div>';

    // items table
    html += '<table class="items"><colgroup><col style="width:4%"><col style="width:46%"><col style="width:11%"><col style="width:13%"><col style="width:12%"><col style="width:14%"></colgroup>' +
      '<thead><tr><th>No.</th><th>Description of goods / Specification</th><th style="text-align:right">Quantity</th><th>Unit</th><th style="text-align:right">Unit price (' + e(curCode()) + ')</th><th style="text-align:right">Amount (' + e(curCode()) + ')</th></tr></thead><tbody>';
    (d.items || []).forEach(function (it, i) {
      var L = calc.lines[i] || {};
      html += '<tr><td class="c">' + (i + 1) + '</td><td>' +
        '<div class="pname editable" data-edit="item-name-' + i + '" data-path="items.' + i + '.name">' + missP(it.name, 'PRODUCT NAME') + '</div>' +
        '<div class="pspec editable" data-edit="item-spec-' + i + '" data-path="items.' + i + '.spec">' + missP(it.spec, 'SPECIFICATION') + '</div>' +
        '<div class="pmeta">' + [
          it.cas ? 'CAS No.: ' + e(it.cas) : '<span class="placeholder">CAS No. TBC</span>',
          it.hsCode ? 'HS: ' + e(it.hsCode) : '',
          it.origin ? 'Origin: ' + e(it.origin) : '',
          it.packageCount ? e(it.packageCount) + ' packages' : ''
        ].filter(Boolean).join(' · ') + '</div></td>' +
        '<td class="n">' + (it.quantity === '' ? placeholderSpan('QTY') : e(it.quantity)) + '</td>' +
        '<td>' + e(it.unit || '') + '</td>' +
        '<td class="n editable" data-edit="item-price-' + i + '" data-path="items.' + i + '.unitPrice">' + (it.unitPrice === '' || it.unitPrice === undefined ? placeholderSpan('TO BE CONFIRMED') : e(money(it.unitPrice, 4).replace(/\.?0+$/, '') === '' ? it.unitPrice : money(it.unitPrice, 4).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, ''))) + '</td>' +
        '<td class="n"><b>' + (L.netForTotal !== undefined ? e(money(L.netForTotal, dp)) : placeholderSpan('N/A')) + '</b></td></tr>';
    });
    html += '</tbody><tfoot>';
    (d.charges || []).forEach(function (c) {
      var add = c.addToTotal !== false;
      if (c.amount !== '' && c.amount !== null && c.amount !== undefined && add) {
        html += '<tr><td colspan="5" class="lbl">' + e(c.name) + '</td><td class="n">' + e(money(c.amount, dp)) + '</td></tr>';
      }
    });
    html += '<tr><td colspan="5" class="lbl">Sub-total of goods (' + e(curCode()) + ')</td><td class="n"><b>' + (calc.subtotal !== null ? e(money(calc.subtotal, dp)) : placeholderSpan('—')) + '</b></td></tr>';
    html += '<tr class="grand"><td colspan="5" class="lbl" style="color:#fff">TOTAL (' + e(curCode()) + ')</td><td class="n">' + (calc.total !== null ? e(money(calc.total, dp)) : placeholderSpan('PENDING PRICE')) + '</td></tr>';
    html += '</tfoot></table>';

    // amount in words
    html += '<div class="words"><b>Total amount in words</b>' + (calc.totalInWords ? e(calc.totalInWords) : placeholderSpan('AMOUNT IN WORDS UNAVAILABLE — UNIT PRICE MISSING')) + '</div>';

    // terms grid
    var pay = d.payment || {}, dlv = d.delivery || {}, pk = d.packing || {};
    html += '<div class="terms">' +
      '<div><div class="k">Trade term</div><div class="v">' + missP(tt) + '</div></div>' +
      '<div><div class="k">Price basis</div><div class="v">' + (isPI ? 'Per the trade term above, in ' + e(curCode()) : 'Per the trade term above') + '</div></div>' +
      '<div class="full"><div class="k">Packing</div><div class="v editable" data-edit="packing" data-path="packing.summary">' + missP(pk.summary, 'PACKING TO BE CONFIRMED') + '</div></div>' +
      '<div><div class="k">Total packages</div><div class="v">' + missP(d.totalPackageCount) + '</div></div>' +
      '<div><div class="k">Gross weight</div><div class="v">' + missP(d.totalGrossWeight) + '</div></div>' +
      '<div class="full"><div class="k">Delivery / Lead time</div><div class="v editable" data-edit="lead" data-path="delivery.leadTime">' + missP(dlv.leadTime, 'LEAD TIME TO BE CONFIRMED') + '</div></div>' +
      '<div><div class="k">Partial shipment</div><div class="v">' + missP(dlv.partialShipment) + '</div></div>' +
      '<div><div class="k">Transhipment</div><div class="v">' + missP(dlv.transhipment) + '</div></div>' +
      '<div class="full"><div class="k">Payment terms</div><div class="v editable" data-edit="pay" data-path="payment.terms">' + missP(pay.terms, 'PAYMENT TERMS TO BE CONFIRMED') + '</div></div>' +
      '</div>';

    // banking
    var b = d.bank || {};
    if (b.display && !b.sanitized && b.detailsConfirmed) {
      html += '<div class="bankbox"><div class="k" style="font-family:var(--sans);font-size:7.3pt;letter-spacing:.1em;text-transform:uppercase;color:#6b7787;font-weight:800">Beneficiary bank details</div>' +
        'Bank: ' + e(b.bankName) + ' · Account name: ' + e(b.accountName) + '<br>A/C No.: ' + e(b.accountNumber) + ' · SWIFT: ' + e(b.swift) + '</div>';
    } else {
      html += '<div class="bankbox"><div class="k" style="font-family:var(--sans);font-size:7.3pt;letter-spacing:.1em;text-transform:uppercase;color:#6b7787;font-weight:800">Beneficiary bank details</div>' +
        '<div class="ph">' + e((pay.beneficiaryNote || '[BANK DETAILS TO BE CONFIRMED — A/C No. / SWIFT intentionally not generated]')) + '</div></div>';
    }

    // notes + DG
    html += '<div class="two"><div class="notes"><h5>Notes &amp; conditions</h5><ol>';
    html += '<li>Prices are firm' + (v.validUntil ? ' until ' + e(v.validUntil) : ' for the validity stated') + ' and subject to written confirmation by the Seller.</li>';
    (d.items || []).forEach(function (it) { if (it.dangerousGoods && it.dangerousGoods.ghsSummary) html += '<li>' + e(it.name) + ' — ' + e(it.dangerousGoods.ghsSummary) + '. Handle with care: use eye protection; avoid dust generation.</li>'; });
    (d.documents || []).length && (html += '<li>Documents: ' + (d.documents || []).map(function (x) { return e(x.name); }).join('; ') + '.</li>');
    var fx = (d.currency || {}).exchangeRate;
    if (fx && fx.display !== 'none' && fx.base && fx.rate) {
      html += '<li>Currency reference: 1 ' + e(fx.base) + ' = ' + e(fx.rate) + ' ' + e(curCode()) + ' as of ' + e(fx.asOf || 'n/a') + ' (' + (fx.state === 'confirmed' ? 'confirmed' : 'reference only') + '); prices are fixed in ' + e(curCode()) + '.</li>';
    }
    html += '<li>All figures above follow the confirmed unit price and quantity; any discrepancy must be reported before payment.</li>';
    html += '</ol></div><div class="notes"><h5>Documents &amp; compliance</h5><ul>';
    html += '<li>HS code shown is for reference; the exporter/broker confirms the final classification.</li>';
    html += '<li>Any import duties, value-added tax or destination charges are for the Buyer unless stated otherwise in the trade term.</li>';
    html += '<li>Quality: Certificate of Analysis per shipment' + ((d.items || [])[0] && (d.items[0].moisturePct !== undefined) ? '' : '') + '.</li>';
    html += '</ul></div></div>';

    // DG box
    var anyDG = (d.items || []).some(function (i) { return i.dangerousGoods && i.dangerousGoods.status === 'DG'; });
    var dgUnknown = (d.items || []).some(function (i) { return !i.dangerousGoods || i.dangerousGoods.status === 'UNKNOWN'; });
    if (anyDG || dgUnknown) {
      html += '<div class="dgbox"><b>Transport / packing notice — dangerous goods</b><br>' +
        (dgUnknown ? 'DG status unverified: confirm the UN number, proper shipping name, class, packing group and packaging before any transport document is issued.' : '') +
        (anyDG ? (d.items || []).filter(function (i) { return i.dangerousGoods && i.dangerousGoods.status === 'DG'; }).map(function (i) { return e(i.name) + ': UN ' + e(i.dangerousGoods.unNumber) + ', ' + e(i.dangerousGoods.class) + ', PG ' + e(i.dangerousGoods.packingGroup); }).join('; ') : '') + '</div>';
    } else if ((d.items || []).every(function (i) { return i.dangerousGoods && i.dangerousGoods.status === 'NOT_REGULATED'; })) {
      html += '<div class="dgbox"><b>Transport notice</b><br>Verified as not classified as dangerous goods for transport (basis: ' + ((d.items[0].dangerousGoods || {}).basis || 'SDS') + '). Standard export packing applies; SDS copy accompanies each shipment.</div>';
    }

    // sign-off
    if ((d.view || {}).signature !== false) {
      html += '<div class="sign"><div class="sig"><div class="role">' + (isPI ? 'For and on behalf of the Seller (Authorised Signature)' : 'Accepted by the Buyer (Authorised Signature & Date)') + '</div></div>' +
        '<div class="sig"><div class="role">For and on behalf of the Seller</div><div style="margin-top:12px">' + e((d.review || {}).signatoryTitle || 'Export Sales Manager') + (d.review && d.review.name ? ' — ' + e(d.review.name) : '') + '</div></div></div>';
    }

    // footer
    html += '<div class="footer"><span>' + e(seller.name || '') + (seller.address ? ' · ' + e(seller.address) : '') + '</span><span>' + e(refText()) + ' · Page 1 of 1 · ' + (v.state === 'FORMAL' ? 'Original' : 'Draft — not a valid offer') + '</span></div>';
    html += '</div>';
    paper.innerHTML = html;
    bindInPlace();
  }

  function bindInPlace() {
    $$('#paper .editable').forEach(function (el) {
      el.addEventListener('dblclick', function () { el.setAttribute('contenteditable', 'true'); el.focus(); document.execCommand && document.execCommand('selectAll', false, null); });
      el.addEventListener('blur', function () {
        if (el.getAttribute('contenteditable') !== 'true') return;
        el.removeAttribute('contenteditable');
        var path = el.getAttribute('data-path');
        var txt = el.innerText.trim();
        var val = getPath(S.doc, path);
        var numeric = /\.(quantity|unitPrice|packageCount|bagNetKg|totalPackageCount|days)$/.test(path);
        var newVal = numeric ? (txt === '' ? '' : (isNaN(Number(txt.replace(/,/g, ''))) ? val : Number(txt.replace(/,/g, '')))) : txt;
        if (String(newVal) !== String(val)) {
          setPath(S.doc, path, newVal);
          amend();
          logEvent('INLINE_EDIT', 'Field ' + path + ' changed from "' + val + '" to "' + newVal + '"');
          el.classList.add('edited');
          rerender();
        }
      });
      el.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') { el.blur(); } });
    });
    var logo = $('#paper .logo');
    if (logo) logo.addEventListener('click', function () { $('#logofile').click(); });
  }

  /* --------------------------------------------------------------- dashboard */
  function renderDashboard() {
    var v = valid(), calc = v.calc, d = S.doc;
    if (S.debugRender) console.log('[renderDashboard] state=' + v.state + ' stage=' + (d.state && d.state.stage) + ' rc=' + (d.state && d.state.reviewConfirmed) + ' errors=' + v.errors.length);
    var qty = (d.items || []).reduce(function (s, i) { return s + (Number(i.quantity) || 0); }, 0);
    var unit = ((d.items || [])[0] || {}).unit || '';
    var kpi = [
      { k: 'Document', v: v.state === 'FORMAL' ? 'FORMAL' : (v.state === 'READY_FOR_REVIEW' ? 'REVIEW' : 'DRAFT'), s: d.docType === 'PROFORMA_INVOICE' ? 'Proforma Invoice' : 'Quotation', cls: v.state === 'FORMAL' ? 'good' : (v.state === 'DRAFT' ? 'warn' : '') },
      { k: 'Quantity', v: money(qty, 3).replace(/\.?0+$/, ''), s: unit + ' total' },
      { k: 'Total', v: calc.total !== null ? curCode() + ' ' + money(calc.total, curDp()) : '—', s: calc.total !== null ? '' : 'unit price missing', cls: calc.total !== null ? 'good' : 'bad' },
      { k: 'Validation', v: v.errors.length + ' err', s: v.warnings.length + ' warnings', cls: v.errors.length ? 'bad' : (v.warnings.length ? 'warn' : 'good') },
      { k: 'Completeness', v: v.completeness.filled + '/' + v.completeness.required, s: 'required fields', cls: v.completeness.filled === v.completeness.required ? 'good' : 'warn' }
    ];
    $('#kpis').innerHTML = kpi.map(function (x) {
      return '<div class="kpi ' + (x.cls || '') + '"><div class="k">' + esc(x.k) + '</div><div class="v">' + esc(x.v) + '</div><div class="s">' + esc(x.s) + '</div>' +
        (x.k === 'Completeness' ? '<div class="progress"><i style="width:' + Math.round(100 * v.completeness.filled / Math.max(1, v.completeness.required)) + '%"></i></div>' : '') + '</div>';
    }).join('');
    $('#checkgrid').innerHTML = v.checks.map(function (c) {
      var ico = c.status === 'pass' ? '✓' : (c.status === 'warn' ? '!' : '✕');
      var n = c.errors ? c.errors + ' 错误' : (c.warnings ? c.warnings + ' 提示' : '通过');
      return '<div class="chkitem ' + c.status + '" data-key="' + c.key + '" title="' + esc(c.name) + '"><div class="ico">' + ico + '</div><div><div class="t">' + c.key + '. ' + esc(c.name) + '</div><div class="n">' + n + '</div></div></div>';
    }).join('');
    $$('#checkgrid .chkitem').forEach(function (el) {
      el.addEventListener('click', function () {
        var key = el.getAttribute('data-key');
        var c = v.checks.filter(function (x) { return x.key === key; })[0];
        if (!c || !c.hits.length) { toast('该检查项通过'); return; }
        showModal('检查项 ' + c.key + '. ' + c.name, '<div class="prob ' + (c.errors ? 'error' : 'warning') + '" style="border:0;background:transparent;padding:0">' +
          c.hits.map(function (h) { return '<div class="prob ' + h.severity + '"><div><div><span class="code">' + esc(h.code) + '</span> ' + esc(h.msg) + '</div>' + (h.fix ? '<div class="fix">建议：' + esc(h.fix) + '</div>' : '') + '</div></div>'; }).join('') + '</div>',
          '<button class="btn" data-close>关闭</button>');
      });
    });
    var list = v.problems.slice(0, 8);
    $('#problems').innerHTML = (list.length ? '' : '<div class="prob" style="background:var(--ok-bg);border-color:#bfe3cd;color:var(--ok);font-weight:600">✓ 所有检查通过，可以进入复核环节。</div>') +
      list.map(function (p) {
        return '<div class="prob ' + p.severity + '"><div><div><span class="code">' + esc(p.code) + '</span> ' + esc(p.msg) + '</div>' + (p.fix ? '<div class="fix">建议：' + esc(p.fix) + '</div>' : '') + '</div></div>';
      }).join('') +
      (v.problems.length > 8 ? '<div class="mini">另有 ' + (v.problems.length - 8) + ' 条，见“检查”页或检查项卡片。</div>' : '');
    // pills + badges
    var pill = $('#statepill'); pill.className = 'pill st-' + v.state;
    $('#statetext').textContent = (v.state === 'FORMAL' ? 'FORMAL / ISSUED' : v.state === 'READY_FOR_REVIEW' ? 'READY FOR REVIEW' : 'DRAFT — 非有效报价') + (isSimulated() ? ' · SIM' : '');
    var ec = v.checks.filter(function (c) { return c.errors; }).length, wc = v.checks.filter(function (c) { return !c.errors && c.warnings; }).length;
    $('#b-check').textContent = v.errors.length ? v.errors.length : '';
    $('#b-check').className = 'badge' + (v.errors.length ? '' : ' w');
    if (!v.errors.length) $('#b-check').textContent = v.warnings.length ? '!' : '';
    $('#demotag').style.display = isSimulated() ? '' : 'none';
  }

  /* ------------------------------------------------------------- full render */
  function rerender(opts) {
    opts = opts || {};
    renderForms();
    renderPaper();
    renderDashboard();
    if (opts.keepFocus) {
      var el = document.getElementById(opts.keepFocus);
      if (el && el.focus) { el.focus(); try { el.setSelectionRange(el.value.length, el.value.length); } catch (e) { } }
    }
    autosave();
  }
  function softUpdate() { renderPaper(); renderDashboard(); autosave(); }

  function autosave() { try { localStorage.setItem(LS_KEY, JSON.stringify(S.doc)); } catch (e) { } }

  /* ------------------------------------------------------------------ modals */
  function showModal(title, body, foot) {
    $('#modaltitle').textContent = title;
    $('#modalbody').innerHTML = body;
    $('#modalfoot').innerHTML = foot || '<button class="btn" data-close>关闭</button>';
    $('#modal').classList.add('on');
    $$('#modal [data-close]').forEach(function (b) { b.addEventListener('click', closeModal); });
  }
  function closeModal() { $('#modal').classList.remove('on'); }

  /* ---------------------------------------------------------------- review  */
  function openReview() {
    var v = valid(), d = S.doc;
    var rv = d.review = d.review || {};
    var blockers = v.errors.slice();
    var rows = E.fieldList(d);
    var confirmedRows = rows.filter(function (r) { return r.state === 'confirmed'; });
    var missingRows = rows.filter(function (r) { return r.state === 'missing'; });
    var optionalNotShown = rows.filter(function (r) { return r.state === 'optional'; });
    var body = '';
    body += '<div class="row" style="gap:10px;margin-bottom:12px">' +
      '<span class="tag ok">已确认 ' + confirmedRows.length + '</span><span class="tag no">待填写 ' + missingRows.length + '</span>' +
      '<span class="tag opt">未采用 ' + optionalNotShown.length + '</span>' +
      '<span class="tag ' + (blockers.length ? 'no' : 'ok') + '">阻断问题 ' + blockers.length + '</span></div>';
    body += '<table><thead><tr><th>章节</th><th>字段</th><th>内容</th><th>状态</th></tr></thead><tbody>';
    rows.forEach(function (r) {
      var tag = r.state === 'confirmed' ? '<span class="tag ok">已确认</span>' : r.state === 'missing' ? '<span class="tag no">待填写</span>' : '<span class="tag opt">未采用</span>';
      var val = typeof r.value === 'number' ? money(r.value, curDp()) : r.value;
      body += '<tr><td style="color:#6b7a90;white-space:nowrap">' + esc(r.section) + '</td><td>' + esc(r.label) + '</td><td>' + (val === '' || val === undefined ? '<span style="color:#b42318">—</span>' : esc(String(val))) + '</td><td>' + tag + '</td></tr>';
    });
    body += '</tbody></table>';
    if (blockers.length) {
      body += '<h4 style="margin:16px 0 6px;color:#b42318">阻断问题（正式文件前必须解决）</h4>';
      blockers.forEach(function (b) { body += '<div class="prob error"><div><span class="code">' + esc(b.code) + '</span> ' + esc(b.msg) + '</div></div>'; });
    }
    if (v.warnings.length) {
      body += '<h4 style="margin:16px 0 6px;color:#9a6700">提示（建议处理）</h4>';
      v.warnings.forEach(function (b) { body += '<div class="prob warning"><div><span class="code">' + esc(b.code) + '</span> ' + esc(b.msg) + '</div></div>'; });
    }
    body += '<div style="margin-top:16px;border:1px solid #dde3ec;border-radius:10px;padding:12px">' +
      '<label class="chk"><input type="checkbox" id="rv1" ' + (rv.itemsChecked ? 'checked' : '') + '><span>我逐条核对以上全部字段，确认价格、数量、币种、金额、包装、贸易术语、付款与交期均由我确认。</span></label>' +
      '<div class="g2" style="margin-top:8px"><div class="fld"><label>复核人姓名</label><input id="rvname" value="' + esc(rv.name || '') + '" placeholder="输入姓名"></div>' +
      '<div class="fld"><label>签署人职务</label><input id="rvtitle" value="' + esc(rv.signatoryTitle || 'Export Sales Manager') + '"></div></div>' +
      '<label class="chk"><input type="checkbox" id="rv2" ' + (rv.formalApproved ? 'checked' : '') + '><span>以正式文件（FORMAL）签发，而非草稿/占位版本。</span></label>' +
      '</div>';
    var foot = '<button class="btn" data-close>返回修改</button>' +
      '<button class="btn" id="rvExport">导出复核清单</button>' +
      '<button class="btn gold" id="rvConfirm">确认复核</button>';
    showModal('复核与签发前确认 — ' + (d.docType === 'PROFORMA_INVOICE' ? 'Proforma Invoice' : 'Quotation') + ' ' + refText(), body, foot);
    $('#modalbody').querySelector('#rv1').addEventListener('change', function (e) { rv.itemsChecked = e.target.checked; });
    $('#modalbody').querySelector('#rv2').addEventListener('change', function (e) { rv.formalApproved = e.target.checked; });
    $('#modalbody').querySelector('#rvname').addEventListener('input', function (e) { rv.name = e.target.value; });
    $('#modalbody').querySelector('#rvtitle').addEventListener('input', function (e) { rv.signatoryTitle = e.target.value; });
    $('#rvExport').addEventListener('click', exportReview);
    $('#rvConfirm').addEventListener('click', function () {
      rv.name = $('#rvname').value; rv.signatoryTitle = $('#rvtitle').value;
      if (!rv.itemsChecked) { toast('请先勾选“已逐条核对”'); return; }
      if (!rv.name || !rv.name.trim()) { toast('请填写复核人姓名'); return; }
      var v2 = valid();
      if (rv.formalApproved) {
        if (v2.errors.length) { toast('仍有 ' + v2.errors.length + ' 个阻断问题，不能签发正式文件'); return; }
        if (isSimulated()) { toast('演示数据不能签发为正式有效文件（需先移除模拟标记并确认全部数据）'); return; }
        if ((d.view || {}).watermark !== false) { toast('请先在模板中关闭演示水印'); return; }
      }
      d.state = d.state || {};
      d.state.reviewConfirmed = true;
      d.state.stage = rv.formalApproved ? 'FORMAL' : 'READY_FOR_REVIEW';
      d.state.confirmedAt = nowStamp();
      d.state.confirmedBy = rv.name;
      logEvent(rv.formalApproved ? 'FORMAL_ISSUED' : 'REVIEW_CONFIRMED', 'Reviewed by ' + rv.name + '; stage=' + d.state.stage);
      closeModal(); rerender();
      toast(rv.formalApproved ? '已签发正式文件（记录复核人：' + rv.name + '）' : '复核已确认，当前仍为待签发状态');
    });
  }

  function exportReview() {
    var v = valid();
    var lines = ['EXPORT QUOTATION / PROFORMA INVOICE — REVIEW RECORD', 'Document: ' + refText() + ' (' + S.doc.docType + ')', 'Generated: ' + nowStamp(), ''];
    E.fieldList(S.doc).forEach(function (r) { lines.push('[' + r.state.toUpperCase() + '] ' + r.section + ' | ' + r.label + ' | ' + (typeof r.value === 'number' ? money(r.value, curDp()) : (r.value || ''))); });
    lines.push('', 'STATE: ' + v.state + ' — ' + v.label, 'ERRORS:'); v.errors.forEach(function (e) { lines.push('  ' + e.code + ' ' + e.msg); });
    lines.push('WARNINGS:'); v.warnings.forEach(function (e) { lines.push('  ' + e.code + ' ' + e.msg); });
    download('review-' + refText() + '.txt', lines.join('\n'), 'text/plain');
  }

  /* ----------------------------------------------------------------- export  */
  function download(name, content, mime) {
    var blob = new Blob([content], { type: mime + ';charset=utf-8' });
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 400);
  }
  function csvOf() {
    var rows = [['Section', 'Label', 'Value', 'Status']];
    E.fieldList(S.doc).forEach(function (r) { rows.push([r.section, r.label, typeof r.value === 'number' ? String(r.value) : (r.value || ''), r.state]); });
    return rows.map(function (r) { return r.map(function (c) { return '"' + String(c).replace(/"/g, '""') + '"'; }).join(','); }).join('\r\n');
  }
  function printDoc() {
    var v = valid();
    if (v.state !== 'FORMAL') { toast('当前为 ' + v.state + '：打印件将标注草稿/演示水印'); }
    logEvent('PRINT_EXPORT', 'Printed/preview exported while state=' + v.state);
    setTimeout(function () { window.print(); }, 120);
  }
  function templateSnapshot() {
    return { kind: 'eqpi-company-template', version: 1, savedAt: nowStamp(),
      brand: { accentColor: (S.doc.view || {}).accentColor, font: S.font, logoText: (S.doc.seller || {}).logoText, shortName: (S.doc.seller || {}).shortName, watermark: (S.doc.view || {}).watermark },
      seller: S.doc.seller };
  }
  function saveTemplate() { S.template = templateSnapshot(); try { localStorage.setItem(TPL_KEY, JSON.stringify(S.template)); } catch (e) { } logEvent('TEMPLATE_SAVED', 'Company template saved'); toast('公司模板已保存到本浏览器'); rerender(); }
  function loadTemplate() {
    try {
      var raw = S.template || JSON.parse(localStorage.getItem(TPL_KEY) || 'null');
      if (!raw) { toast('尚无保存的模板'); return; }
      S.doc.view = S.doc.view || {};
      S.doc.seller = S.doc.seller || {};
      if (raw.brand) { S.doc.view.accentColor = raw.brand.accentColor || S.doc.view.accentColor; S.font = raw.brand.font || S.font; S.doc.seller.logoText = raw.brand.logoText || S.doc.seller.logoText; S.doc.seller.shortName = raw.brand.shortName || S.doc.seller.shortName; S.doc.view.watermark = raw.brand.watermark; }
      if (raw.seller) S.doc.seller = Object.assign({}, raw.seller);
      $('#accent').value = S.doc.view.accentColor || '#1b3a5b';
      logEvent('TEMPLATE_LOADED', 'Company template loaded'); rerender(); toast('公司模板已载入');
    } catch (e) { toast('模板读取失败'); }
  }

  function blankDoc() {
    return {
      meta: { dataClass: 'USER DATA', caseId: 'NEW-' + todayISO(), preparedAt: todayISO() },
      docType: 'QUOTATION', state: { stage: 'DRAFT', reviewConfirmed: false },
      reference: { text: 'QT-' + todayISO().replace(/-/g, '') + '-001' }, issueDate: todayISO(),
      seller: { name: '', address: '', country: 'China', logoText: 'LOGO' },
      buyer: { name: '', address: '', country: '' },
      currency: { code: 'USD', decimals: 2, exchangeRate: { base: '', rate: '', asOf: '', state: 'reference', display: 'footnote' } },
      tradeTerm: { code: '', version: '2020', namedPlace: '', transportMode: 'SEA', costAllocation: {} },
      items: [{ id: 'L1', name: '', cas: '', spec: '', hsCode: '', unit: 'MT', quantity: '', unitPrice: '', discountPct: 0, packageCount: '', packageWeight: { value: '', unit: 'KG' }, amountState: 'draft', dangerousGoods: { status: 'UNKNOWN' } }],
      charges: [], packing: {}, delivery: {}, payment: {}, validity: { type: 'date', validUntil: '' },
      documents: [], bank: { display: false, sanitized: true, detailsConfirmed: false },
      view: { watermark: false, logo: true, signature: true, accentColor: '#1b3a5b' },
      review: {}, fatal: []
    };
  }

  /* ------------------------------------------------------------------- boot  */
  function boot() {
    var fromHash = location.hash.indexOf('data=') >= 0 ? decodeURIComponent(location.hash.split('data=')[1]) : null;
    var initial = null;
    try { initial = fromHash ? JSON.parse(atob(fromHash)) : null; } catch (e) { initial = null; }
    if (!initial) initial = clone(EMBEDDED);
    S.doc = initial || blankDoc();
    try { S.log = JSON.parse(localStorage.getItem(LOG_KEY) || '[]'); } catch (e) { S.log = []; }
    if (!S.log.length) S.log.push({ at: nowStamp(), kind: 'DOC_LOADED', msg: 'Loaded ' + ((S.doc.meta || {}).caseId || 'blank document') + ' — ' + ((S.doc.meta || {}).dataClass || ''), docNo: refText() });
    $('#appver').textContent = E.VERSION;
    $('#accent').value = (S.doc.view || {}).accentColor || '#1b3a5b';
    $('#wmchk').checked = (S.doc.view || {}).watermark !== false;
    $('#logochk').checked = (S.doc.view || {}).logo !== false;

    // tabs
    $$('#tabs button').forEach(function (b) {
      b.addEventListener('click', function () {
        $$('#tabs button').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on'); S.tab = b.getAttribute('data-tab'); renderForms();
      });
    });
    // doc type
    $$('#docseg button').forEach(function (b) {
      b.addEventListener('click', function () {
        $$('#docseg button').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        S.doc.docType = b.getAttribute('data-dt');
        var r = S.doc.reference || {};
        var no = (r.text || '');
        if (/^QT-/.test(no) && S.doc.docType === 'PROFORMA_INVOICE') r.text = no.replace(/^QT-/, 'PI-');
        else if (/^PI-/.test(no) && S.doc.docType === 'QUOTATION') r.text = no.replace(/^PI-/, 'QT-');
        amend(); logEvent('DOC_TYPE_CHANGED', 'Switched to ' + S.doc.docType); rerender();
      });
    });
    $$('#docseg button').forEach(function (b) { if (b.getAttribute('data-dt') === S.doc.docType) { $$('#docseg button').forEach(function (x) { x.classList.remove('on'); }); b.classList.add('on'); } });

    // toolbar
    $('#fontsel').addEventListener('change', function (e) { S.font = e.target.value; renderPaper(); });
    $('#accent').addEventListener('input', function (e) { S.doc.view = S.doc.view || {}; S.doc.view.accentColor = e.target.value; renderPaper(); });
    $('#wmchk').addEventListener('change', function (e) { S.doc.view = S.doc.view || {}; S.doc.view.watermark = e.target.checked; renderPaper(); });
    $('#logochk').addEventListener('change', function (e) { S.doc.view = S.doc.view || {}; S.doc.view.logo = e.target.checked; renderPaper(); });
    var zoom = function (dz) { S.zoom = Math.min(1.3, Math.max(0.5, S.zoom + dz)); $('#paper').style.transform = 'scale(' + S.zoom + ')'; $('#zoomlbl').textContent = Math.round(S.zoom * 100) + '%'; $('#paper').style.marginBottom = (S.zoom < 1 ? -(1 - S.zoom) * 1130 : 0) + 'px'; };
    $('#zoomin').addEventListener('click', function () { zoom(0.1); });
    $('#zoomout').addEventListener('click', function () { zoom(-0.1); });
    zoom(0);
    $('#btnPrint').addEventListener('click', printDoc);
    $('#btnHtml').addEventListener('click', function () {
      var doc = document.documentElement.outerHTML.replace(/<div class="modal[\s\S]*?<\/div>\s*<\/div>\s*<\/div>\s*<\/div>\s*<div class="toast"/, '<div class="toast"');
      download('quote-' + refText() + '.html', '<!DOCTYPE html>\n' + doc, 'text/html');
      logEvent('EXPORT_HTML', 'Standalone HTML exported');
    });
    $('#btnJson').addEventListener('click', function () { download('quote-' + refText() + '.json', JSON.stringify(S.doc, null, 2), 'application/json'); logEvent('EXPORT_JSON', 'Data JSON exported'); });
    $('#btnCsv').addEventListener('click', function () { download('quote-' + refText() + '.csv', '\ufeff' + csvOf(), 'text/csv'); logEvent('EXPORT_CSV', 'Field CSV exported'); });
    $('#btnReview').addEventListener('click', openReview);
    $('#btnSave').addEventListener('click', function () { autosave(); logEvent('DRAFT_SAVED', 'Draft saved to browser storage'); toast('草稿已保存'); });
    $('#btnLoad').addEventListener('click', function () {
      try { var raw = localStorage.getItem(LS_KEY); if (!raw) { toast('浏览器中没有草稿'); return; } S.doc = JSON.parse(raw); rerender(); toast('已载入浏览器草稿'); }
      catch (e) { toast('载入失败'); }
    });
    $('#modalx').addEventListener('click', closeModal);
    $('#modal').addEventListener('click', function (e) { if (e.target === $('#modal')) closeModal(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeModal(); });

    // uploads (hidden inputs)
    var lf = document.createElement('input'); lf.type = 'file'; lf.id = 'logofile'; lf.accept = 'image/*'; lf.style.display = 'none';
    lf.addEventListener('change', function () {
      var f = lf.files[0]; if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        var logo = $('#paper .logo');
        if (logo) { logo.innerHTML = '<img alt="logo" src="' + rd.result + '" style="max-width:100%;max-height:100%">'; logo.style.background = 'transparent'; }
        S.doc.seller.logoData = rd.result; toast('Logo 已载入（仅本地）');
      };
      rd.readAsDataURL(f);
    });
    document.body.appendChild(lf);
    var jf = document.createElement('input'); jf.type = 'file'; jf.id = 'loadfile'; jf.accept = '.json,application/json'; jf.style.display = 'none';
    jf.addEventListener('change', function () {
      var f = jf.files[0]; if (!f) return;
      var rd = new FileReader();
      rd.onload = function () { try { var obj = JSON.parse(rd.result); if (obj && obj.kind === 'eqpi-company-template') { S.template = obj; loadTemplate(); return; } S.doc = obj; amend(); logEvent('DATA_LOADED', 'JSON data loaded from file'); rerender(); toast('已载入数据文件'); } catch (e) { toast('JSON 解析失败'); } };
      rd.readAsText(f, 'utf-8');
    });
    document.body.appendChild(jf);
    $('#tplup').addEventListener('change', function () {
      var f = $('#tplup').files[0]; if (!f) return;
      var rd = new FileReader();
      rd.onload = function () { try { var obj = JSON.parse(rd.result); if (obj.kind === 'eqpi-company-template') { S.template = obj; loadTemplate(); } else toast('模板文件须为 eqpi-company-template JSON'); } catch (e) { toast('模板解析失败（请上传模板 JSON）'); } };
      rd.readAsText(f, 'utf-8');
    });

    // hidden setup for line price formatting hook
    renderForms(); renderPaper(); renderDashboard();
  }

  document.addEventListener('DOMContentLoaded', boot);
  window.__STUDIO = { get doc() { return S.doc; }, set doc(v) { S.doc = v; }, valid: valid, store: S };
})();
