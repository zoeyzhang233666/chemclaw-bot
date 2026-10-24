/* ==========================================================================
   export-quotation-engine v1.0.0
   Pure, dependency-free calculation / validation / document-state engine for
   English export Quotation & Proforma Invoice documents.
   Runs unchanged in browsers and Node.js (>= 14). No network, no DOM access.
   Every commercial figure must originate from user-confirmed input; the engine
   never invents prices, payment terms, bank data or delivery dates.
   ========================================================================== */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(); }
  else { root.QuoteEngine = factory(); }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var VERSION = '1.0.0';

  /* ---------------------------------------------------------------- helpers */
  function num(x) {
    if (x === null || x === undefined || x === '') return null;
    var n = (typeof x === 'number') ? x : Number(String(x).replace(/[,\s]/g, ''));
    return isFinite(n) ? n : null;
  }
  /** Parse a free-text weight ("1,008,000 kg (1,008.00 MT)", "1008 MT", "1,008 t") into kg. */
  function parseWeight(text) {
    if (text === null || text === undefined) return null;
    var s = String(text).toLowerCase().replace(/tonnes?|tons?/g, 'mt');
    var mult = 1;
    var firstUnit = (s.match(/(kgs?|mts?|t|g)\b/) || [])[1] || '';
    if (firstUnit === 'mt' || firstUnit === 'mts' || firstUnit === 't') mult = 1000;
    else if (firstUnit === 'g') mult = 0.001;
    var m = s.match(/(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?/);
    if (!m) return null;
    var n = num((m[1] + (m[2] || '')).replace(/,/g, ''));
    return n === null ? null : n * mult;
  }

  /** Round half-up (commercial convention), returns number scaled by 10^dp */
  function roundHalfUp(value, dp) {
    dp = (dp === undefined || dp === null) ? 2 : dp;
    var m = Math.pow(10, dp);
    var x = value * m;
    var r = (x < 0 ? -Math.round(-x + 1e-9) : Math.round(x + 1e-9));
    return r / m;
  }

  /** A confirmation state that must never be silently trusted. */
  function isConfirmed(state) {
    return state === 'confirmed' || state === 'confirmed_exact' || state === 'confirmed_best';
  }
  function confirmedLegacy(flag) {
    // Legacy boolean fields (amountConfirmed / exchangeRateConfirmed / grossWeightConfirmed ...)
    return flag === true;
  }

  var AMOUNT_WORDS = {
    zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9,
    ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16,
    seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20, thirty: 30, forty: 40, fifty: 50,
    sixty: 60, seventy: 70, eighty: 80, ninety: 90
  };
  var SCALES = [[1e9, 'billion'], [1e6, 'million'], [1e3, 'thousand']];

  /** Camelot-style integer writer: 108500 -> "One Hundred Eight Thousand Five Hundred" */
  function underThousand(n) {
    var units = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
      'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'];
    var tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];
    var out = [];
    if (n >= 100) { out.push(units[Math.floor(n / 100)], 'hundred'); n %= 100; }
    if (n >= 20) { out.push(tens[Math.floor(n / 10)]); if (n % 10) out.push(units[n % 10]); }
    else if (n > 0) out.push(units[n]);
    return out.join(' ');
  }
  function intToWords(n) {
    if (n === 0) return 'zero';
    var parts = [];
    for (var i = 0; i < SCALES.length; i++) {
      var div = SCALES[i][0];
      if (n >= div) { parts.push(underThousand(Math.floor(n / div)) + ' ' + SCALES[i][1]); n %= div; }
    }
    if (n > 0) parts.push(underThousand(n));
    return parts.join(' ');
  }
  function titleCase(s) {
    return s.replace(/\b[a-z]/g, function (c) { return c.toUpperCase(); });
  }
  /** 108500.50 + "USD" -> "US Dollars One Hundred Eight Thousand Five Hundred and Fifty Cents Only" */
  function amountInWords(amount, currency, dp) {
    dp = (dp === undefined || dp === null) ? 2 : dp;
    if (amount === null || amount === undefined || !isFinite(amount)) return '';
    var neg = amount < 0;
    var abs = roundHalfUp(Math.abs(amount), dp);
    var whole = Math.floor(abs + 1e-9);
    var cents = Math.round((abs - whole) * Math.pow(10, dp));
    var names = { USD: 'US Dollars', EUR: 'Euro', CNY: 'Renminbi', JPY: 'Japanese Yen', IDR: 'Indonesian Rupiah', GBP: 'Pound Sterling', SGD: 'Singapore Dollars', AUD: 'Australian Dollars', HKD: 'Hong Kong Dollars', INR: 'Indian Rupees' };
    var unit = { USD: 'Cents', EUR: 'Cents', CNY: 'Fen', IDR: 'Sen', SGD: 'Cents', AUD: 'Cents', HKD: 'Cents', INR: 'Paise', JPY: '', GBP: 'Pence' };
    var curName = names[currency] || currency;
    var txt = (neg ? 'Minus ' : '') + curName + ' ' + titleCase(intToWords(whole));
    if (cents > 0) {
      txt += ' and ' + titleCase(intToWords(cents)) + ' ' + (unit[currency] || (dp === 2 ? 'Cents' : ''));
    }
    // Whole-currency wording: "... Only" ; with decimals: "... Cents (or 'and Zero Cents') Only"
    if (cents === 0 && dp > 0) txt += ' and ' + titleCase(intToWords(0)) + ' ' + (unit[currency] || 'Cents');
    return txt.replace(/\s+/g, ' ').trim() + ' Only';
  }

  function addDays(isoDate, days) {
    if (!isoDate) return null;
    var d = new Date(isoDate + 'T00:00:00Z');
    if (isNaN(d.getTime())) return null;
    d.setUTCDate(d.getUTCDate() + Number(days || 0));
    return d.toISOString().slice(0, 10);
  }
  function todayISO() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  /* ---------------------------------------------------- amount computation */
  /**
   * Compute line totals, charges and grand total.
   * mode = 'precise'  : amount = unitPrice * qty * (1 - disc/100), rounded at the end
   * mode = 'per_unit' : unit price is first rounded to `lineRounding` dp (see note)
   * Returns { ok, lines, warnings, subtotal, charges, total, roundingDiff }
   */
  function compute(doc) {
    doc = doc || {};
    var dp = isNaN(doc.currency && doc.currency.decimals) ? 2 : Number(doc.currency.decimals);
    var mode = doc.lineAmountRule === 'per_unit' ? 'per_unit' : 'precise';
    var res = { ok: true, lines: [], warnings: [], errors: [], subtotal: null, charges: [], total: null, dp: dp };
    var seen = {};
    var sum = 0;
    (doc.items || []).forEach(function (it, idx) {
      var qty = num(it.quantity), price = num(it.unitPrice);
      var disc = num(it.discountPct) || 0;
      var L = { index: idx + 1, id: it.id, net: null, gross: null, grossUnit: null };
      if (qty === null || price === null || qty === 0) {
        L.missing = true;
        res.lines.push(L);
        if (price === null) res.warnings.push({ code: 'LINE_PRICE_MISSING', severity: 'error', where: 'item:' + (idx + 1), msg: 'Unit price missing for line ' + (idx + 1) + ' — total cannot be computed.' });
        if (qty === null) res.warnings.push({ code: 'LINE_QTY_MISSING', severity: 'error', where: 'item:' + (idx + 1), msg: 'Quantity missing for line ' + (idx + 1) + '.' });
        res.ok = false;
        return;
      }
      L.discountPct = disc;
      L.gross = roundHalfUp(qty * price, dp);
      L.grossUnit = roundHalfUp(price, dp);
      L.net = roundHalfUp(qty * price * (1 - disc / 100), dp);
      if (mode === 'per_unit') {
        L.netForTotal = roundHalfUp(L.grossUnit * (1 - disc / 100), dp);
        L.netForTotal = roundHalfUp(L.netForTotal * qty, dp);
      } else {
        L.netForTotal = L.net;
      }
      if (it.packageCount !== undefined && it.packageCount !== null && it.packageCount !== '' &&
          it.packageWeight && num(it.packageWeight.value) !== null) {
          L.grossWeight = roundHalfUp(num(it.packageCount) * num(it.packageWeight.value), 3);
        L.netWeight = (it.packageWeight.net !== undefined && num(it.packageWeight.net) !== null)
          ? roundHalfUp(num(it.packageCount) * num(it.packageWeight.net), 3) : null;
      }
      if (it.amountState && isConfirmed(it.amountState) && it.amountConfirmedValue !== undefined && it.amountConfirmedValue !== null) {
        var diff = roundHalfUp(L.netForTotal - num(it.amountConfirmedValue), dp);
        L.confirmedDiff = diff;
        if (Math.abs(diff) > 0.005) {
          res.warnings.push({ code: 'AMOUNT_MISMATCH', severity: 'error', where: 'item:' + (idx + 1),
            msg: 'Line ' + (idx + 1) + ': confirmed amount ' + num(it.amountConfirmedValue) + ' ≠ recalculated ' + L.netForTotal + ' (difference ' + diff + ').' });
          res.ok = false;
        }
      }
      // HS / CAS duplicates
      if (it.hsCode) { seen['hs:' + it.hsCode] = (seen['hs:' + it.hsCode] || 0) + 1; }
      sum += L.netForTotal;
      res.lines.push(L);
    });
    res.subtotal = res.ok ? roundHalfUp(sum, dp) : null;
    var charges = [];
    var chargeSum = 0;
    (doc.charges || []).forEach(function (c) {
      var amt = num(c.amount);
      var sign = (c.addToTotal === false || c.direction === 'none') ? 0 : 1;
      charges.push({ name: c.name, amount: amt, basis: c.basis || 'Total', sign: (c.amount === '' || c.amount === null) ? null : sign });
      if (amt !== null && sign === 1) chargeSum += amt;
    });
    res.charges = charges;
    if (res.subtotal !== null) {
      var extra = roundHalfUp(chargeSum, dp);
      var diff = roundHalfUp(res.subtotal + extra, dp);
      if (doc.amountState && isConfirmed(doc.amountState) && num(doc.amountConfirmedValue) !== null) {
        var d2 = roundHalfUp(diff - num(doc.amountConfirmedValue), dp);
        if (Math.abs(d2) > 0.005) {
          res.warnings.push({ code: 'GRAND_TOTAL_MISMATCH', severity: 'error', where: 'total',
            msg: 'Confirmed total ' + num(doc.amountConfirmedValue) + ' ≠ recalculated ' + diff + ' (difference ' + d2 + '). Must be resolved by the user.' });
          res.ok = false;
        }
      }
      res.total = diff;
      res.roundingDiff = res.ok ? 0 : null;
    } else {
      res.total = null;
    }
    // totals check: sum of line nets vs subtotal
    if (res.ok) {
      var ls = 0; res.lines.forEach(function (L) { if (L.netForTotal !== undefined) ls += L.netForTotal; });
      res.linesSumCheck = Math.abs(roundHalfUp(ls, dp) - res.subtotal) < 1e-9;
    }
    res.totalInWords = res.total !== null ? amountInWords(res.total, doc.currency && doc.currency.code, dp) : '';
    return res;
  }

  /* ---------------------------------------------------------- compliance   */
  var TERMS = {
    EXW: { name: 'Ex Works', group: 'any', mode: 'any', named: 'place' },
    FCA: { name: 'Free Carrier', group: 'any', mode: 'any', named: 'place' },
    FAS: { name: 'Free Alongside Ship', group: 'sea', mode: 'sea', named: 'port' },
    FOB: { name: 'Free On Board', group: 'sea', mode: 'sea', named: 'port' },
    CFR: { name: 'Cost and Freight', group: 'sea', mode: 'sea', named: 'port' },
    CIF: { name: 'Cost, Insurance and Freight', group: 'sea', mode: 'sea', named: 'port' },
    CPT: { name: 'Carriage Paid To', group: 'any', mode: 'any', named: 'place' },
    CIP: { name: 'Carriage and Insurance Paid To', group: 'any', mode: 'any', named: 'place' },
    DAP: { name: 'Delivered at Place', group: 'any', mode: 'any', named: 'place' },
    DPU: { name: 'Delivered at Place Unloaded', group: 'any', mode: 'any', named: 'place' },
    DDP: { name: 'Delivered Duty Paid', group: 'any', mode: 'any', named: 'place' }
  };

  /**
   * Required-field matrix per document type. required / recommended / advanced
   * keys point at doc paths. `confirmation: 'price'` marks fields the engine
   * treats as user-confirmed commercial data (never auto-filled).
   */
  var FIELD_MATRIX = {
    seller: [
      { key: 'seller.name', label: 'Seller legal name', required: true, owner: 'user_confirmed' },
      { key: 'seller.address', label: 'Seller address', required: true, owner: 'user_confirmed' },
      { key: 'seller.country', label: 'Seller country', required: false, owner: 'user_confirmed' },
      { key: 'seller.contact', label: 'Seller contact person', required: false, owner: 'user_confirmed' },
      { key: 'seller.phone', label: 'Seller phone', required: false, owner: 'user_confirmed' },
      { key: 'seller.email', label: 'Seller e-mail', required: false, owner: 'user_confirmed' },
      { key: 'seller.taxId', label: 'Seller tax ID / USCI', required: false, owner: 'user_confirmed' }
    ],
    buyer: [
      { key: 'buyer.name', label: 'Buyer legal name', required: true, owner: 'user_confirmed' },
      { key: 'buyer.address', label: 'Buyer address', required: true, owner: 'user_confirmed' },
      { key: 'buyer.country', label: 'Buyer country', required: true, owner: 'user_confirmed' },
      { key: 'buyer.contact', label: 'Buyer contact person', required: false, owner: 'user_confirmed' },
      { key: 'buyer.email', label: 'Buyer e-mail', required: false, owner: 'user_confirmed' },
      { key: 'buyer.phone', label: 'Buyer phone', required: false, owner: 'user_confirmed' },
      { key: 'buyer.npwp', label: 'Buyer NPWP / tax number', required: false, owner: 'user_confirmed' }
    ],
    doc: [
      { key: 'doc.tradeTerm.code', label: 'Incoterms rule (e.g. FOB / CIF)', required: true, owner: 'user_confirmed' },
      { key: 'doc.tradeTerm.namedPlace', label: 'Named port / place of delivery', required: true, owner: 'user_confirmed' },
      { key: 'doc.tradeTerm.version', label: 'Incoterms version', required: true, owner: 'user_confirmed' },
      { key: 'doc.currency.code', label: 'Currency', required: true, owner: 'user_confirmed' },
      { key: 'doc.validity.type', label: 'Validity: date or days', required: true, owner: 'user_confirmed' },
      { key: 'doc.payment.terms', label: 'Payment terms', required: true, owner: 'user_confirmed' },
      { key: 'doc.delivery.leadTime', label: 'Delivery lead time', required: true, owner: 'user_confirmed' },
      { key: 'doc.packing.summary', label: 'Packing (type) ', required: true, owner: 'user_confirmed' },
      { key: 'doc.reference.quoteNo', label: 'Document reference number', required: true, owner: 'system_generated' },
      { key: 'doc.issueDate', label: 'Issue date', required: true, owner: 'system_generated' }
    ],
    item: [
      { key: 'items[].name', label: 'Product English name', required: true, owner: 'user_confirmed' },
      { key: 'items[].cas', label: 'CAS Registry Number', required: false, owner: 'product_reference' },
      { key: 'items[].spec', label: 'Specification / grade', required: true, owner: 'user_confirmed' },
      { key: 'items[].hsCode', label: 'HS code (for export docs)', required: false, owner: 'user_confirmed' },
      { key: 'items[].unit', label: 'Quantity unit', required: true, owner: 'user_confirmed' },
      { key: 'items[].quantity', label: 'Quantity', required: true, owner: 'user_confirmed' },
      { key: 'items[].unitPrice', label: 'Unit price', required: true, owner: 'user_confirmed' },
      { key: 'items[].packageCount', label: 'Package count', required: false, owner: 'user_confirmed' }
    ],
    pi_only: [
      { key: 'buyer.poNumber', label: "Buyer's PO / reference (optional but standard on PI)", required: false, owner: 'user_confirmed' },
      { key: 'doc.proforma.piValidityNote', label: 'PI: date validity is mandatory', required: true, owner: 'user_confirmed' }
    ],
    advanced: [
      { key: 'doc.reference.exporterReference', label: 'Supplier invoice No. used as exporter reference', required: false, owner: 'user_confirmed' },
      { key: 'doc.bank', label: 'Banking details', required: false, owner: 'user_confirmed' },
      { key: 'doc.charges', label: 'Freight / insurance charge amounts', required: false, owner: 'user_confirmed' },
      { key: 'doc.freight.estimatedPol', label: 'Port of loading / discharge', required: false, owner: 'user_confirmed' },
      { key: 'doc.totalGrossWeight', label: 'Gross weight', required: false, owner: 'user_confirmed' },
      { key: 'doc.totalVolume', label: 'Total volume', required: false, owner: 'user_confirmed' }
    ]
  };

  function get(doc, path) {
    var parts = String(path).replace(/\[\]/g, '').split('.');
    var cur = doc;
    if (parts.length && parts[0] === 'doc') parts = parts.slice(1); // 'doc.' = the root document
    for (var i = 0; i < parts.length; i++) {
      if (cur === null || cur === undefined) return undefined;
      if (Array.isArray(cur)) { cur = cur[0]; i--; continue; }
      cur = cur[parts[i]];
    }
    if (Array.isArray(cur)) return cur.length ? cur : undefined;
    return cur;
  }
  function blank(v) {
    if (v === null || v === undefined) return true;
    if (typeof v === 'string') return v.trim() === '';
    if (Array.isArray(v)) return v.length === 0;
    return false;
  }

  function fieldStatus(doc) {
    var rows = [];
    ['seller', 'buyer', 'doc', 'item'].forEach(function (g) {
      FIELD_MATRIX[g].forEach(function (f) {
        var v = get(doc, f.key);
        var filled = !blank(v);
        rows.push({
          group: g, key: f.key, label: f.label, required: !!f.required,
          owner: f.owner, filled: filled, value: filled ? v : '',
          state: filled ? 'confirmed' : (f.required ? 'missing' : 'optional')
        });
      });
    });
    var extra = FIELD_MATRIX.advanced.slice();
    if ((doc.docType || 'QUOTATION') === 'PROFORMA_INVOICE') extra = extra.concat(FIELD_MATRIX.pi_only);
    extra.forEach(function (f) {
      var v = get(doc, f.key);
      var filled = !blank(v);
      rows.push({ group: f.key.indexOf('buyer') === 0 ? 'buyer' : 'doc', key: f.key, label: f.label,
        required: !!f.required, owner: f.owner, filled: filled, value: filled ? v : '',
        state: filled ? 'confirmed' : (f.required ? 'missing' : 'optional'), branch: 'supplementary' });
    });
    (doc.items || []).forEach(function (it, i) {
      ['name', 'cas', 'spec', 'hsCode', 'unit', 'quantity', 'unitPrice'].forEach(function (k) {
        var v = it[k];
        var label = { name: 'Product name', cas: 'CAS No.', spec: 'Specification', hsCode: 'HS code', unit: 'Unit', quantity: 'Quantity', unitPrice: 'Unit price' }[k] + ' (line ' + (i + 1) + ')';
        rows.push({ group: 'item', key: 'items[' + i + '].' + k, label: label, required: ['name', 'spec', 'unit', 'quantity', 'unitPrice'].indexOf(k) >= 0,
          owner: (k === 'cas' ? 'product_reference' : 'user_confirmed'), filled: !blank(v), value: blank(v) ? '' : v, state: !blank(v) ? 'confirmed' : 'missing', line: i + 1 });
      });
    });
    return rows;
  }

  /** Full validation. Returns { state, errors, warnings, checks, completeness } */
  function validate(doc) {
    doc = doc || {};
    var problems = [];
    function add(code, severity, where, msg, fix) { problems.push({ code: code, severity: severity, where: where, msg: msg, fix: fix || '' }); }
    var docType = doc.docType || 'QUOTATION';
    var t = doc.tradeTerm || {};
    var cur = (doc.currency && doc.currency.code) || '';
    var code = t.code || '';
    var rule = TERMS[code];

    /* --- seller / buyer --- */
    if (blank(doc.seller && doc.seller.name)) add('SELLER_NAME', 'error', 'seller.name', 'Seller legal name missing.', 'Enter full registered company name.');
    if (blank(doc.seller && doc.seller.address)) add('SELLER_ADDRESS', 'error', 'seller.address', 'Seller address missing.', '');
    if (blank(doc.buyer && doc.buyer.name)) add('BUYER_NAME', 'error', 'buyer.name', 'Buyer legal name missing.', '');
    if (blank(doc.buyer && doc.buyer.address)) add('BUYER_ADDRESS', 'error', 'buyer.address', 'Buyer address missing.', '');
    if (blank(doc.buyer && doc.buyer.country)) add('BUYER_COUNTRY', 'warning', 'buyer.country', 'Buyer country missing.', '');

    /* --- incoterms --- */
    if (!code) add('INCOTERM_MISSING', 'error', 'doc.tradeTerm.code', 'Incoterms rule missing — required since Incoterms 2010.', '');
    else if (!rule) add('INCOTERM_INVALID', 'error', 'doc.tradeTerm.code', 'Unknown Incoterms rule "' + code + '".', 'Use one of ' + Object.keys(TERMS).join(', ') + '.');
    if (blank(t.namedPlace)) add('INCOTERM_PLACE', 'error', 'doc.tradeTerm.namedPlace', (rule ? rule.name + ' requires' : 'Incoterms rule requires') + ' a ' + (rule ? rule.named : 'named port/place') + ' (named place).', '');
    if (blank(t.version)) add('INCOTERM_VERSION', 'error', 'doc.tradeTerm.version', 'Incoterms version missing (2020 recommended).', '');
    if (rule && rule.named === 'place' && /\b(port|pelabuhan)\b/i.test(t.namedPlace || '') && ['EXW', 'FCA', 'CPT', 'CIP', 'DAP', 'DPU', 'DDP'].indexOf(code) >= 0) {
      add('INCOTERM_PLACE_KIND', 'warning', 'doc.tradeTerm.namedPlace', 'Named place reads like a port; for ' + code + ' specify a place (warehouse, factory gate, depot).', '');
    }
    if (rule && rule.mode === 'sea' && t.transportMode && t.transportMode !== 'SEA') {
      add('INCOTERM_MODE_MISMATCH', 'error', 'doc.tradeTerm.code', code + ' applies to sea / inland-waterway transport only.', 'Switch to FCA/CPT/CIP for air or multi-modal.');
    }
    if (rule && rule.mode === 'sea' && blank(t.transportMode)) {
      add('TRANSPORT_MODE', 'warning', 'doc.tradeTerm.transportMode', 'Transport mode not confirmed; ' + code + ' implies sea freight.', '');
    }
    if (t.version === '2010' || t.version === '2000') add('INCOTERM_OLD_VERSION', 'warning', 'doc.tradeTerm.version', 'Incoterms ' + t.version + ' is superseded; state the version on the contract.', '');
    if (code === 'CIF' || code === 'CIP') {
      if (!(doc.freight && doc.freight.insuranceBasis)) add('INSURANCE_BASIS', 'warning', 'doc.freight.insuranceBasis', code + ': insurance is included — state the cover and sum insured (e.g. ICC(A), 110% of CIF value).', '');
    }
    // cost allocation matrix
    var costMap = (doc.tradeTerm && doc.tradeTerm.costAllocation) || {};
    var allocIssues = costAllocationIssues(code, costMap);
    allocIssues.forEach(function (a) { add(a.code, 'warning', 'doc.tradeTerm.costAllocation.' + a.key, a.msg, ''); });

    /* --- currency --- */
    if (!cur) add('CURRENCY_MISSING', 'error', 'doc.currency.code', 'Currency missing.', '');
    if (!(doc.currency && num(doc.currency.decimals) !== null && (num(doc.currency.decimals) === 0 || num(doc.currency.decimals) === 2))) {
      add('CURRENCY_DECIMALS', 'warning', 'doc.currency.decimals', 'Currency decimals not set; engine assumed 2.', '');
    }
    if (doc.currency && doc.currency.code === 'IDR' && (doc.currency.decimals !== 0)) {
      add('CURRENCY_DECIMALS_IDR', 'warning', 'doc.currency.decimals', 'IDR quotation normally uses 0 decimals.', '');
    }
    var base = doc.currency && doc.currency.exchangeRate && doc.currency.exchangeRate.base;
    if (doc.currency && doc.currency.exchangeRate && (doc.currency.exchangeRate.base === cur)) {
      add('FX_SAME_CURRENCY', 'warning', 'doc.currency.exchangeRate', 'Exchange rate base equals quotation currency — the reference figure is meaningless.', '');
    }
    if (doc.currency && doc.currency.exchangeRate && doc.currency.exchangeRate.display === 'quotation' && !isConfirmed(doc.currency.exchangeRate.state)) {
      add('FX_UNCONFIRMED', 'warning', 'doc.currency.exchangeRate.state', 'Quotation shows an exchange-rate note that is not confirmed by the user.', 'Confirm the FX snapshot or remove the note.');
    }
    if (doc.currency && doc.currency.exchangeRate) {
      var fxAge = daysBetween(doc.currency.exchangeRate.asOf, doc.issueDate || todayISO());
      if (fxAge !== null && fxAge > 7 && isConfirmed(doc.currency.exchangeRate.state)) {
        add('FX_STALE', 'warning', 'doc.currency.exchangeRate.asOf', 'Exchange-rate reference is ' + fxAge + ' days old vs issue date; re-snapshot before issue.', '');
      }
    }

    /* --- validity --- */
    var val = doc.validity || {};
    var issue = doc.issueDate;
    if (val.type === 'days' && !(num(val.days) > 0)) add('VALIDITY_DAYS', 'error', 'doc.validity.days', 'Validity in days missing or zero.', '');
    if (val.type === 'date' && blank(val.validUntil)) add('VALIDITY_DATE', 'error', 'doc.validity.validUntil', 'Validity end date missing.', '');
    if (!val.type) add('VALIDITY_TYPE', 'error', 'doc.validity.type', 'Validity basis (date / days) not set.', '');
    var validUntil = val.type === 'days' ? addDays(issue, num(val.days)) : val.validUntil;
    if (issue && validUntil) {
      if (validUntil < issue) add('VALIDITY_ORDER', 'error', 'doc.validity', 'Validity end date (' + validUntil + ') precedes issue date (' + issue + ').', '');
      var span = daysBetween(issue, validUntil);
      if (span !== null && span > 120) add('VALIDITY_TOO_LONG', 'warning', 'doc.validity', 'Validity of ' + span + ' days is unusually long in chemicals trade (typical 15–60 days).', '');
      if (span !== null && span < 3) add('VALIDITY_TOO_SHORT', 'warning', 'doc.validity', 'Validity under 3 days is hard to accept.', '');
      if (validUntil < todayISO()) add('VALIDITY_EXPIRED', 'warning', 'doc.validity', 'Document already expired at load time (' + validUntil + ').', '');
    }
    if (docType === 'PROFORMA_INVOICE' && val.type === 'days') {
      add('PI_VALIDITY', 'warning', 'doc.validity.type', 'On a Proforma Invoice use an explicit validity date (common import-permit requirement).', 'Switch type to "date".');
    }

    /* --- payment --- */
    var pay = doc.payment || {};
    if (blank(pay.terms)) add('PAYMENT_TERMS', 'error', 'doc.payment.terms', 'Payment terms missing.', '');
    if (pay.code === 'LC') {
      if (blank(pay.lcType)) add('LC_TYPE', 'warning', 'doc.payment.lcType', 'LC type (at sight / usance) not stated.', '');
      if (blank(pay.lcOpenedBy)) add('LC_OPENING_DATE', 'warning', 'doc.payment.lcOpenedBy', 'LC opening deadline not stated.', '');
      if (blank(pay.bank)) add('LC_BANK', 'warning', 'doc.payment.bank', 'Advising bank / issuing-bank requirement not stated.', '');
    }
    if (pay.code === 'PREPAY' && blank(pay.amountPct)) {
      add('PREPAY_PCT', 'warning', 'doc.payment.amountPct', 'Share paid in advance not stated.', '');
    }

    /* --- delivery --- */
    var dlv = doc.delivery || {};
    if (blank(dlv.leadTime)) add('LEAD_TIME', 'error', 'doc.delivery.leadTime', 'Delivery lead time missing.', '');
    if (dlv.readyDateMode === 'exact' && blank(dlv.readyDate)) add('READY_DATE', 'error', 'doc.delivery.readyDate', 'Exact ready date selected but empty.', '');
    if (dlv.readyDateMode === 'relative' && !(num(dlv.daysAfterReceipt) > 0)) add('READY_DATE_REL', 'error', 'doc.delivery.daysAfterReceipt', 'Days after receipt selected but not set.', '');

    /* --- packing --- */
    var pk = doc.packing || {};
    if (blank(pk.summary)) add('PACKING', 'error', 'doc.packing.summary', 'Packing not stated.', '');
    if (blank(pk.terms)) add('PACKING_TERMS', 'warning', 'doc.packing.terms', 'Packing standard / certificate wording missing.', '');

    /* --- items --- */
    var totalQty = 0, qtyComplete = true, allGross = 0, grossComplete = true;
    var pkgSum = 0, pkgCounted = false;
    (doc.items || []).forEach(function (it, i) {
      var n = i + 1;
      if (blank(it.name)) add('ITEM_NAME', 'error', 'items[' + i + '].name', 'Line ' + n + ': product name missing.', '');
      if (blank(it.spec)) add('ITEM_SPEC', 'error', 'items[' + i + '].spec', 'Line ' + n + ': specification missing.', '');
      if (blank(it.cas)) add('ITEM_CAS', 'warning', 'items[' + i + '].cas', 'Line ' + n + ': CAS number missing — required for customs, SDS and trend searches.', '');
      else if (!/^\d{2,7}-\d{2}-\d$/.test(String(it.cas).trim()) && !/^\d{4,7}-\d{2}-\d$/.test(String(it.cas).trim())) add('ITEM_CAS_FORMAT', 'warning', 'items[' + i + '].cas', 'Line ' + n + ': CAS number format looks wrong (NNNNNNN-NN-N).', '');
      if (blank(it.hsCode)) add('ITEM_HS', 'warning', 'items[' + i + '].hsCode', 'Line ' + n + ': HS code missing — needed by the exporter/broker and on the PI as reference.', '');
      else if (!/^\d{6}(\d{2}(\d{2})?)?$/.test(String(it.hsCode).replace(/\s/g, ''))) add('ITEM_HS_FORMAT', 'warning', 'items[' + i + '].hsCode', 'Line ' + n + ': HS code must be 6, 8 or 10 digits.', '');
      if (blank(it.unit)) add('ITEM_UNIT', 'error', 'items[' + i + '].unit', 'Line ' + n + ': unit missing.', '');
      var q = num(it.quantity);
      if (q === null || q <= 0) { add('ITEM_QTY', 'error', 'items[' + i + '].quantity', 'Line ' + n + ': quantity missing or ≤ 0.', ''); qtyComplete = false; }
      else totalQty += q;
      if (num(it.unitPrice) === null || num(it.unitPrice) < 0) add('ITEM_PRICE', 'error', 'items[' + i + '].unitPrice', 'Line ' + n + ': unit price missing — no formal document can be issued.', '');
      if (it.unit === 'MT' && q !== null && q < 1) add('ITEM_QTY_SMALL', 'warning', 'items[' + i + '].quantity', 'Line ' + n + ': quantity below 1 MT — confirm unit is MT and not KG.', '');
      if (it.unit === 'KG' && q !== null && q > 20000) add('ITEM_QTY_LARGE', 'warning', 'items[' + i + '].quantity', 'Line ' + n + ': quantity above 20,000 KG — confirm unit is not MT.', '');
      if (num(it.discountPct) > 0 && !isConfirmed(it.discountState)) add('DISCOUNT_UNCONFIRMED', 'warning', 'items[' + i + '].discountPct', 'Line ' + n + ': discount entered but not confirmed.', '');
      if (num(it.unitPrice) !== null && q !== null) { /* line amount handled by compute() */ }
      if (it.packageCount !== undefined && it.packageCount !== '' && it.packageCount !== null) {
        pkgCounted = true; pkgSum += num(it.packageCount) || 0;
      }
      if (it.packageWeight && num(it.packageWeight.value) !== null && it.packageCount) {
        allGross += num(it.packageCount) * num(it.packageWeight.value);
      } else if (it.packageCount) { grossComplete = false; }
      if (it.moisturePct !== undefined && num(it.moisturePct) !== null) {
        if (num(it.moisturePct) >= 100) add('ITEM_MOISTURE', 'error', 'items[' + i + '].moisturePct', 'Line ' + n + ': moisture % ≥ 100 is impossible.', '');
      }
      // dangerous goods fields
      var dg = it.dangerousGoods || {};
      if (dg.status === 'DG') {
        if (blank(dg.unNumber)) add('DG_UN', 'error', 'items[' + i + '].dangerousGoods.unNumber', 'Line ' + n + ': DG confirmed but UN number missing.', '');
        if (blank(dg.properShippingName)) add('DG_PSN', 'error', 'items[' + i + '].dangerousGoods.properShippingName', 'Line ' + n + ': proper shipping name missing.', '');
        if (blank(dg.class)) add('DG_CLASS', 'error', 'items[' + i + '].dangerousGoods.class', 'Line ' + n + ': DG class missing.', '');
        if (blank(dg.packingGroup)) add('DG_PG', 'warning', 'items[' + i + '].dangerousGoods.packingGroup', 'Line ' + n + ': packing group missing.', '');
        if (blank(dg.unPackagingCode)) add('DG_PACKAGE', 'warning', 'items[' + i + '].dangerousGoods.unPackagingCode', 'Line ' + n + ': UN packaging marking not stated (UN-approved drum/bag).', '');
        if (blank(dg.msdsVersion)) add('DG_MSDS', 'warning', 'items[' + i + '].dangerousGoods.msdsVersion', 'Line ' + n + ': SDS revision not stated — shipper needs current SDS.', '');
      } else if (dg.status === 'UNKNOWN') {
        add('DG_UNKNOWN', 'error', 'items[' + i + '].dangerousGoods.status', 'Line ' + n + ': dangerous-goods status not verified — verify before issuing a shipping document.', '');
      } else if (dg.status === 'NOT_REGULATED' && blank(dg.basis)) {
        add('DG_BASIS', 'warning', 'items[' + i + '].dangerousGoods.basis', 'Line ' + n + ': "not regulated" must cite an SDS / supplier statement.', '');
      }
    });
    if (pkgCounted && pkgSum > 0 && blank(doc.totalPackageCount)) add('PACKAGE_TOTAL', 'warning', 'doc.totalPackageCount', 'Line package counts do not add up to a stated document total.', '');
    if (num(doc.totalPackageCount) !== null && pkgCounted && num(doc.totalPackageCount) !== pkgSum) {
      add('PACKAGE_SUM_MISMATCH', 'error', 'doc.totalPackageCount', 'Document package total (' + doc.totalPackageCount + ') ≠ sum of line package counts (' + pkgSum + ').', '');
    }
    if (!blank(doc.totalGrossWeight) && grossComplete && allGross > 0) {
      var wt = parseWeight(doc.totalGrossWeight);
      if (wt !== null && Math.abs(wt - allGross) > 0.6) add('WEIGHT_SUM_MISMATCH', 'warning', 'doc.totalGrossWeight', 'Stated gross weight ' + doc.totalGrossWeight + ' differs from package count × package weight (' + roundHalfUp(allGross, 3) + ' kg).', '');
    }
    if (num(doc.totalVolume) !== null && num(doc.freight && doc.freight.volumeCheck) !== null) { /* optional CBM vs freight calc handled in calculator */ }

    /* --- figures --- */
    var calc = compute(doc);
    calc.warnings.forEach(function (w) { problems.push(w); });

    /* --- total vs package consistency and per-unit price vs packing --- */
    if (doc.packing && num(doc.packing.bagNetKg) && totalQty && qtyComplete) {
      var expectedBags = totalQty * 1000 / num(doc.packing.bagNetKg);
      if (pkgCounted && pkgSum > 0 && Math.abs(expectedBags - pkgSum) > 0.5) {
        add('BAG_COUNT_CHECK', 'error', 'packing.bagNetKg', 'Quantity (' + totalQty + ' MT) ÷ bag net (' + doc.packing.bagNetKg + ' kg) = ' + roundHalfUp(expectedBags, 0) + ' bags, but ' + pkgSum + ' packages are quoted.', '');
      }
      if (num(doc.totalPackageCount) !== null && Math.abs(expectedBags - num(doc.totalPackageCount)) > 0.5) {
        add('BAG_TOTAL_CHECK', 'error', 'totalPackageCount', 'Bags implied by quantity (' + roundHalfUp(expectedBags, 0) + ') ≠ stated total packages (' + doc.totalPackageCount + ').', '');
      }
    }

    /* --- banking --- */
    if (doc.bank && (doc.bank.bankName || doc.bank.sanitized)) {
      if (!doc.bank.sanitized) {
        if (doc.bank.detailsConfirmed !== true) add('BANK_UNCONFIRMED', 'error', 'doc.bank.detailsConfirmed', 'Bank details present but not confirmed by the user — do not issue with unconfirmed banking details.', '');
        else if (doc.bank.display) add('BANK_DISPLAY_CONFIRMED', 'error', 'doc.bank.display', 'Bank details are confirmed but display is disabled — enable or remove the block to avoid an ambiguous document.', '');
      } else if (doc.bank.display) {
        add('BANK_SANITIZED_DISPLAY', 'error', 'doc.bank.display', 'Placeholder/sanitized bank block cannot be displayed as valid banking details.', 'Turn display off.');
      }
    } else if (docType === 'PROFORMA_INVOICE' && !doc.bank) {
      add('BANK_MISSING_PI', 'warning', 'doc.bank', 'Proforma Invoice without banking details: the buyer cannot make payment. Provide the full bank block (account number, SWIFT/BIC, IBAN) from your confirmed source.', '');
    }

    /* --- charges / freight --- */
    var charges = doc.charges || [];
    var freightCharge = charges.filter(function (c) { return /freight/i.test(c.name || ''); })[0];
    var insCharge = charges.filter(function (c) { return /insurance/i.test(c.name || ''); })[0];
    if (freightCharge && num(freightCharge.amount) === null) add('FREIGHT_AMOUNT', 'warning', 'doc.charges.freight', 'Freight line present without amount — the cargo-sale total does not include freight. Label it clearly if intentional.', '');
    if ((code === 'CIF' || code === 'CIP') && !insCharge) add('INSURANCE_CHARGE', 'warning', 'doc.charges.insurance', code + ' price should include insurance; add an insurance line or state that cover is arranged under the rule.', '');
    if ((code === 'FOB' || code === 'FCA' || code === 'EXW') && freightCharge && num(freightCharge.amount)) {
      add('FREIGHT_ON_FOB', 'error', 'doc.tradeTerm.code', code + ' excludes main freight, but a freight amount is added to the total.', 'Move freight to the optional freight-cost calculator.');
    }
    if ((code === 'CFR' || code === 'CIF') && doc.freight && num(doc.freight.volumeCheck) !== null && num(doc.freight.quotedVolume) !== null) {
      if (Math.abs(num(doc.freight.volumeCheck) - num(doc.freight.quotedVolume)) > 1) {
        add('FREIGHT_VOLUME', 'warning', 'doc.freight.volumeCheck', 'Package volume (' + doc.freight.quotedVolume + ') differs from computed volume (' + doc.freight.volumeCheck + ') — confirm chargeable freight basis.', '');
      }
    }

    /* --- fatality checks that would stop a formal document --- */
    (doc.fatal || []).forEach(function (f) {
      add(f.code || 'FATAL', 'error', f.where || 'doc', 'BLOCKING: ' + f.msg, '');
    });

    /* --- document state --- */
    var ds = docState(doc, problems);
    var fieldRows = fieldStatus(doc);
    var required = fieldRows.filter(function (r) { return r.required; });
    var completeness = {
      required: required.length,
      filled: required.filter(function (r) { return r.filled; }).length,
      missing: required.filter(function (r) { return !r.filled; }).map(function (r) { return r.label; }),
      optionalFilled: fieldRows.filter(function (r) { return !r.required && r.filled; }).length,
      rows: fieldRows
    };
    var errors = problems.filter(function (p) { return p.severity === 'error'; });
    var warnings = problems.filter(function (p) { return p.severity === 'warning'; });
    return { state: ds.state, label: ds.label, errors: errors, warnings: warnings, problems: problems,
      checks: groupChecks(problems), completeness: completeness, calc: calc, validUntil: validUntil || null,
      tradeTermText: tradeTermText(t), docType: docType };
  }

  function daysBetween(a, b) {
    if (!a || !b) return null;
    var x = new Date(a + 'T00:00:00Z'), y = new Date(b + 'T00:00:00Z');
    if (isNaN(x) || isNaN(y)) return null;
    return Math.round((y - x) / 86400000);
  }

  var CHECK_GROUPS = [
    ['A', 'Commercial fields', ['SELLER_', 'BUYER_', 'ITEM_NAME', 'ITEM_SPEC', 'ITEM_CAS', 'ITEM_HS']],
    ['B', 'Quantity & unit', ['ITEM_QTY', 'ITEM_UNIT', 'BAG_', 'PACKAGE_', 'WEIGHT_']],
    ['C', 'Price & amount', ['ITEM_PRICE', 'AMOUNT_MISMATCH', 'GRAND_TOTAL_MISMATCH', 'DISCOUNT']],
    ['D', 'Currency & exchange rate', ['CURRENCY', 'FX_']],
    ['E', 'Incoterms & costs', ['INCOTERM', 'TRANSPORT_MODE', 'INSURANCE', 'FREIGHT', 'COST_ALLOC']],
    ['F', 'Packing', ['PACKING']],
    ['G', 'Delivery', ['LEAD_TIME', 'READY_DATE']],
    ['H', 'Payment', ['PAYMENT', 'LC_', 'PREPAY']],
    ['I', 'Validity', ['VALIDITY', 'PI_VALIDITY']],
    ['J', 'Banking', ['BANK_']],
    ['K', 'Dangerous goods', ['DG_']]
  ];
  function groupChecks(problems) {
    var out = [];
    CHECK_GROUPS.forEach(function (g) {
      var hits = problems.filter(function (p) { return g[2].some(function (pref) { return p.code.indexOf(pref) === 0; }); });
      var failed = hits.filter(function (h) { return h.severity === 'error'; }).length;
      var warn = hits.length - failed;
      out.push({ key: g[0], name: g[1], status: failed ? 'fail' : (warn ? 'warn' : 'pass'), errors: failed, warnings: warn, hits: hits });
    });
    return out;
  }

  /** Document state machine: DRAFT -> READY_FOR_REVIEW -> FORMAL */
  function docState(doc, problems) {
    problems = problems || [];
    var hasError = problems.some(function (p) { return p.severity === 'error'; });
    var explicit = doc.state && doc.state.stage;
    if (explicit === 'FORMAL' && doc.state.reviewConfirmed === true && !hasError) {
      return { state: 'FORMAL', label: 'FORMAL / ISSUED' };
    }
    if (explicit === 'FORMAL' && (doc.state.reviewConfirmed !== true || hasError)) {
      return { state: 'READY_FOR_REVIEW', label: doc.state.reviewConfirmed === true ? 'BLOCKED — errors must be cleared' : 'AWAITING REVIEW CONFIRMATION' };
    }
    if (doc.state && doc.state.reviewConfirmed === true && !hasError) {
      return { state: 'READY_FOR_REVIEW', label: 'REVIEWED — awaiting formal issue' };
    }
    return { state: 'DRAFT', label: 'DRAFT — NOT A VALID OFFER' };
  }

  function tradeTermText(t) {
    t = t || {};
    if (!t.code) return '';
    var r = TERMS[t.code];
    var s = t.code + (r ? ' ' + r.name : '');
    if (t.namedPlace) s += ' ' + t.namedPlace;
    if (t.version) s += ', Incoterms® ' + t.version;
    return s;
  }

  /* Cost-responsibility matrix (Incoterms 2020 allocation of main cost items). */
  var COST_MATRIX = {
    rows: [
      { key: 'exportPacking', label: 'Export packing' },
      { key: 'loadingCharges', label: 'Loading on board / at carrier' },
      { key: 'exportCustoms', label: 'Export customs clearance' },
      { key: 'originCharges', label: 'Origin terminal / THC' },
      { key: 'mainFreight', label: 'Main carriage / freight' },
      { key: 'insurance', label: 'Cargo insurance' },
      { key: 'destinationCharges', label: 'Destination terminal / THC' },
      { key: 'importCustoms', label: 'Import customs clearance & duties' },
      { key: 'unloading', label: 'Unloading at destination' }
    ],
    standard: {
      EXW: { exportPacking: 'S', loadingCharges: 'B', exportCustoms: 'B', originCharges: 'B', mainFreight: 'B', insurance: 'B', destinationCharges: 'B', importCustoms: 'B', unloading: 'B' },
      FCA: { exportPacking: 'S', loadingCharges: 'S', exportCustoms: 'S', originCharges: 'B', mainFreight: 'B', insurance: 'B', destinationCharges: 'B', importCustoms: 'B', unloading: 'B' },
      FAS: { exportPacking: 'S', loadingCharges: 'B', exportCustoms: 'S', originCharges: 'B', mainFreight: 'B', insurance: 'B', destinationCharges: 'B', importCustoms: 'B', unloading: 'B' },
      FOB: { exportPacking: 'S', loadingCharges: 'S', exportCustoms: 'S', originCharges: 'B', mainFreight: 'B', insurance: 'B', destinationCharges: 'B', importCustoms: 'B', unloading: 'B' },
      CFR: { exportPacking: 'S', loadingCharges: 'S', exportCustoms: 'S', originCharges: 'S', mainFreight: 'S', insurance: 'B', destinationCharges: 'B', importCustoms: 'B', unloading: 'B' },
      CIF: { exportPacking: 'S', loadingCharges: 'S', exportCustoms: 'S', originCharges: 'S', mainFreight: 'S', insurance: 'S', destinationCharges: 'B', importCustoms: 'B', unloading: 'B' },
      CPT: { exportPacking: 'S', loadingCharges: 'S', exportCustoms: 'S', originCharges: 'S', mainFreight: 'S', insurance: 'B', destinationCharges: 'B', importCustoms: 'B', unloading: 'B' },
      CIP: { exportPacking: 'S', loadingCharges: 'S', exportCustoms: 'S', originCharges: 'S', mainFreight: 'S', insurance: 'S', destinationCharges: 'B', importCustoms: 'B', unloading: 'B' },
      DAP: { exportPacking: 'S', loadingCharges: 'S', exportCustoms: 'S', originCharges: 'S', mainFreight: 'S', insurance: 'B', destinationCharges: 'S', importCustoms: 'B', unloading: 'B' },
      DPU: { exportPacking: 'S', loadingCharges: 'S', exportCustoms: 'S', originCharges: 'S', mainFreight: 'S', insurance: 'B', destinationCharges: 'S', importCustoms: 'B', unloading: 'S' },
      DDP: { exportPacking: 'S', loadingCharges: 'S', exportCustoms: 'S', originCharges: 'S', mainFreight: 'S', insurance: 'B', destinationCharges: 'S', importCustoms: 'S', unloading: 'B' }
    }
  };
  /** user costAllocation values are authoritative; mismatches flag the quote text vs reality */
  function costAllocationIssues(code, userMap) {
    var std = COST_MATRIX.standard[code];
    var out = [];
    if (!std || !userMap) return out;
    Object.keys(std).forEach(function (k) {
      var u = userMap[k];
      if (!u) return;
      var uu = String(u).toLowerCase().charAt(0);
      var su = std[k].toLowerCase().charAt(0);
      if (uu !== su && uu !== 'b' && su !== 'b') {
        out.push({ code: 'COST_ALLOC_' + k.toUpperCase(), key: k,
          msg: 'Cost allocation for "' + k + '" contradicts ' + code + ' (' + su.toUpperCase() + ' standard). If the seller bears this cost, state it explicitly as commercial goodwill wording.' });
      } else if (uu === 's' && su === 'b') {
        // seller voluntarily bearing a buyer cost is allowed but must be explicit
        out.push({ code: 'COST_ALLOC_' + k.toUpperCase(), key: k,
          msg: 'Seller bears cost normally on the buyer under ' + code + ' ("' + k + '") — add explicit commercial wording, as the Incoterms® rule does not transfer it.' });
      }
    });
    return out;
  }

  /* ------------------------------------------------------------- documents */
  /** Build the human-readable field list in standard trade-document order */
  function fieldList(doc) {
    var t = doc.tradeTerm || {};
    var calc = compute(doc);
    var rows = [];
    function R(section, label, value, opts) {
      rows.push(Object.assign({ section: section, label: label, value: value,
        state: (value === '' || value === null || value === undefined) ? 'missing' : (opts && opts.state ? opts.state : 'confirmed'),
        note: (opts && opts.note) || '', owner: (opts && opts.owner) || 'user_confirmed' }, opts || {}));
    }
    R('Document', 'Document type', doc.docType === 'PROFORMA_INVOICE' ? 'Proforma Invoice' : 'Quotation');
    R('Document', 'Document No.', (doc.reference || {}).text);
    R('Document', 'Date of issue', doc.issueDate);
    R('Document', 'Our reference', (doc.reference || {}).quotationRef, { owner: 'user_confirmed' });
    R('Document', 'Your enquiry reference', (doc.reference || {}).buyerInquiryRef, { owner: 'user_confirmed' });
    R('Document', 'Our quotation reference', (doc.reference || {}).supplierQuoteRef, { owner: 'user_confirmed' });
    R('Document', 'Exporter reference (supplier invoice No.)', (doc.reference || {}).exporterReference, { owner: 'user_confirmed' });
    R('Document', "Buyer's PO / reference", (doc.reference || {}).buyerPoNo, { owner: 'user_confirmed' });
    R('Document', 'Issued by (operator)', (doc.preparation || {}).issuedBy, { owner: 'system_generated' });

    R('Seller', 'Company name', (doc.seller || {}).name);
    R('Seller', 'Address', (doc.seller || {}).address);
    R('Seller', 'Contact / phone / e-mail', [(doc.seller || {}).contact, (doc.seller || {}).phone, (doc.seller || {}).email].filter(Boolean).join(' | '));
    R('Seller', 'Tax ID / USCI', (doc.seller || {}).taxId);

    R('Buyer', 'Company name', (doc.buyer || {}).name);
    R('Buyer', 'Address', (doc.buyer || {}).address);
    R('Buyer', 'Attention', [(doc.buyer || {}).contact, (doc.buyer || {}).email, (doc.buyer || {}).phone].filter(Boolean).join(' | '));
    R('Buyer', 'Tax number (NPWP)', (doc.buyer || {}).npwp);

    R('Goods', 'Product', (doc.items || []).map(function (i) { return i.name; }).join('; '));
    R('Goods', 'CAS Registry Number', (doc.items || []).map(function (i) { return i.cas; }).join('; '));
    R('Goods', 'Specification', (doc.items || []).map(function (i) { return i.spec; }).join('; '));
    R('Goods', 'HS code', (doc.items || []).map(function (i) { return i.hsCode; }).join('; '));
    R('Goods', 'Origin', (doc.items || []).map(function (i) { return i.origin; }).join('; '));
    R('Goods', 'Quantity', (doc.items || []).map(function (i) { return i.quantity + ' ' + i.unit; }).join('; '));
    R('Goods', 'Unit price', (doc.items || []).map(function (i) { return i.unitPrice + ' ' + (doc.currency || {}).code + '/' + i.unit; }).join('; '));
    R('Goods', 'Amount excl. charges', calc.subtotal, { state: calc.subtotal !== null ? 'confirmed' : 'missing' });
    R('Goods', 'TOTAL', calc.total, { state: calc.total !== null ? 'confirmed' : 'missing' });
    R('Goods', 'Total in words', calc.totalInWords, { state: calc.totalInWords ? 'confirmed' : 'missing' });

    R('Terms', 'Incoterms® 2020', tradeTermText(t) || '');
    R('Terms', 'Named place', t.namedPlace);
    R('Terms', 'Transport mode', t.transportMode);
    R('Terms', 'Port of loading', (doc.freight || {}).estimatedPol);
    R('Terms', 'Port of discharge', (doc.freight || {}).estimatedPod);
    R('Terms', 'Packing', (doc.packing || {}).summary);
    R('Terms', 'Total packages', doc.totalPackageCount);
    R('Terms', 'Gross weight', doc.totalGrossWeight);
    R('Terms', 'Volume', doc.totalVolume);
    R('Terms', 'Lead time', (doc.delivery || {}).leadTime, { note: (doc.delivery || {}).basis || '' });
    R('Terms', 'Partial shipment', (doc.delivery || {}).partialShipment);
    R('Terms', 'Transhipment', (doc.delivery || {}).transhipment);
    R('Terms', 'Payment terms', (doc.payment || {}).terms);
    R('Terms', 'Payment account / beneficiary', (doc.payment || {}).beneficiary, { note: (doc.payment || {}).beneficiaryNote || '' });
    R('Terms', 'Validity', doc.validity && doc.validity.type === 'days' ? 'Valid for ' + doc.validity.days + ' days from date of issue' : (doc.validity || {}).validUntil, { state: ((doc.validity || {}).type) ? 'confirmed' : 'missing' });
    R('Terms', 'Currency', doc.currency && doc.currency.code ? doc.currency.code + ' (' + (doc.currency.name || '') + ')' : '');
    R('Terms', 'Documents required', (doc.documents || []).map(function (d) { return d.name; }).join('; '));

    R('Dangerous goods', 'DG status', (doc.items || []).map(function (i) { return i.dangerousGoods && i.dangerousGoods.status || 'UNKNOWN'; }).join('; '));
    R('Dangerous goods', 'GHS hazard statement', (doc.items || []).map(function (i) { return (i.dangerousGoods || {}).ghsSummary; }).filter(Boolean).join('; '));

    R('Banking', 'Bank name', (doc.bank || {}).bankName, { state: (doc.bank || {}).display ? ((doc.bank || {}).detailsConfirmed ? 'confirmed' : 'missing') : 'optional' });
    R('Banking', 'A/C No. shown?', (doc.bank || {}).display ? 'Yes' : 'No — intentionally omitted', { owner: 'user_confirmed' });
    return rows;
  }

  /** Placeholders used when a price is missing (draft-only documents) */
  function placeholders(doc) {
    var out = [];
    (doc.items || []).forEach(function (it, i) {
      if (num(it.unitPrice) === null) out.push('Line ' + (i + 1) + ' UNIT PRICE — TO BE CONFIRMED [____]');
    });
    if (num((doc.payment || {}).amountPct) === null && /advance|prepay/i.test((doc.payment || {}).terms || '')) out.push('ADVANCE SHARE [__ %]');
    return out;
  }

  return {
    VERSION: VERSION,
    TERMS: TERMS,
    COST_MATRIX: COST_MATRIX,
    FIELD_MATRIX: FIELD_MATRIX,
    compute: compute,
    validate: validate,
    docState: docState,
    fieldStatus: fieldStatus,
    fieldList: fieldList,
    tradeTermText: tradeTermText,
    amountInWords: amountInWords,
    roundHalfUp: roundHalfUp, parseWeight: parseWeight,
    costAllocationIssues: costAllocationIssues,
    addDays: addDays,
    placeholders: placeholders
  };
}));
