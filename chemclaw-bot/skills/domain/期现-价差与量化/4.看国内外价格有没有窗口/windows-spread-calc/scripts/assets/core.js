/* 内外价差 / 进口成本折算 —— 计算内核（JS 镜像版）
 *
 * 本文件与 scripts/core.py 逐行等价，唯一用途是 HTML 报告里的交互重算。
 * 任何一侧改公式，另一侧必须同步改，并跑 `python scripts/check_consistency.py`
 * 做随机参数比对（容差 1e-6），不通过即视为交付失败。
 *
 * 暴露：window.WSC = {import_cost, comparable_price, gap_table, contribution, ...}
 */
(function (root) {
  'use strict';

  var ROUND = 6;

  var TERM_INCLUDES = {
    EXW: { goods: 1, inland_origin: 0, export_clear: 0, freight: 0, insurance: 0, discharge: 0, inland_dest: 0 },
    FCA: { goods: 1, inland_origin: 1, export_clear: 1, freight: 0, insurance: 0, discharge: 0, inland_dest: 0 },
    FOB: { goods: 1, inland_origin: 1, export_clear: 1, freight: 0, insurance: 0, discharge: 0, inland_dest: 0 },
    CFR: { goods: 1, inland_origin: 1, export_clear: 1, freight: 1, insurance: 0, discharge: 0, inland_dest: 0 },
    CIF: { goods: 1, inland_origin: 1, export_clear: 1, freight: 1, insurance: 1, discharge: 0, inland_dest: 0 },
    DAP: { goods: 1, inland_origin: 1, export_clear: 1, freight: 1, insurance: 1, discharge: 1, inland_dest: 1 }
  };
  var TERM_ALIASES = {
    '': 'CFR', 'C&F': 'CFR', CNF: 'CFR', 'CFR中国': 'CFR', 'CIF中国': 'CIF',
    CFRCHINA: 'CFR', CIFCHINA: 'CIF', FAS: 'FOB', FOBCHINA: 'FOB'
  };
  var TERM_LABEL = {
    EXW: 'EXW 工厂交货', FCA: 'FCA 货交承运人', FOB: 'FOB 装运港船上交货',
    CFR: 'CFR 成本加运费（至中国主港）', CIF: 'CIF 成本加保险费加运费（至中国主港）',
    DAP: 'DAP 目的地交货'
  };
  var TERM_GUARDED = {
    freight: ['ocean_freight', '国际运费（海运）'],
    insurance: ['insurance_rate_pct', '保险费率'],
    inland_origin: ['inland_origin', '出口国内陆运费'],
    export_clear: ['export_clear', '出口报关杂费'],
    discharge: ['discharge_fee', '目的港卸货/港杂费'],
    inland_dest: ['inland_dest', '进口国内陆运杂费']
  };

  function fnum(v, dflt) {
    if (dflt === undefined) { dflt = null; }
    if (v === null || v === undefined || v === '' || v === '—' || v === '-') { return dflt; }
    var n = typeof v === 'number' ? v : parseFloat(String(v).replace(/,/g, ''));
    return isNaN(n) ? dflt : n;
  }

  function r6(x) {
    if (x === null || x === undefined || isNaN(x)) { return null; }
    return parseFloat(Number(x).toFixed(ROUND));
  }

  function norm_term(t) {
    var k = String(t || '').trim().toUpperCase().replace(/\s+/g, '');
    if (Object.prototype.hasOwnProperty.call(TERM_ALIASES, k)) { return TERM_ALIASES[k]; }
    return Object.prototype.hasOwnProperty.call(TERM_INCLUDES, k) ? k : 'CFR';
  }

  function import_cost(p) {
    var term = norm_term(p.term);
    var inc = TERM_INCLUDES[term];
    var cur = String(p.currency || 'USD').trim().toUpperCase();
    var fx_in = fnum(p.fx_usdcny, 0) || 0;
    var fx = cur === 'USD' ? fx_in : 1;
    var quote = fnum(p.price_quote, 0) || 0;
    var purity = fnum(p.purity, 1) || 1;
    var gross = fnum(p.gross_weight_factor, 1) || 1;

    function gate(flag) { return inc[flag] ? 1 : 0; }
    function v(key) { return (fnum(p[key], 0) || 0) * fx; }

    var goods_cny = quote * fx;
    var inland_o = v('inland_origin') * (1 - gate('inland_origin'));
    var export_c = v('export_clear') * (1 - gate('export_clear'));
    var freight = v('ocean_freight') * (1 - gate('freight'));
    var ins_rate = fnum(p.insurance_rate_pct, 0) || 0;
    var ins_mark = fnum(p.insurance_rate, 1.1);
    if (ins_mark === null) { ins_mark = 1.1; }
    var insurance = gate('insurance') ? 0 : (goods_cny + inland_o + export_c + freight) * ins_mark * ins_rate;
    var discharge = v('discharge_fee') * (1 - gate('discharge'));
    var inland_d = v('inland_dest') * (1 - gate('inland_dest'));
    var unload = v('unload_fee') * (1 - gate('inland_dest'));

    var cif = goods_cny + inland_o + export_c + freight + insurance;
    var duty_rate = fnum(p.duty_rate, 0) || 0;
    var other_rate = fnum(p.other_tax_rate, 0) || 0;
    var vat_rate = fnum(p.vat_rate, 0.13);
    if (vat_rate === null) { vat_rate = 0.13; }
    var credit_ratio = fnum(p.vat_credit_ratio, 1);
    if (credit_ratio === null) { credit_ratio = 1; }
    credit_ratio = Math.max(0, Math.min(1, credit_ratio));

    var duty = (cif + discharge) * duty_rate;
    var other_tax = (cif + discharge) * other_rate;
    var vat = (cif + discharge + duty) * vat_rate;
    var vat_credit = vat * credit_ratio;

    var landed_cash = cif + discharge + duty + other_tax + vat + inland_d + unload;
    var net_cash = landed_cash - vat_credit;
    var cash_out = duty + other_tax + (vat - vat_credit);
    var unit_net = net_cash / purity * gross;

    return {
      term: term, term_label: TERM_LABEL[term] || term, currency: cur,
      fx: r6(fx_in), quote: r6(quote), purity: r6(purity),
      goods_cny: r6(goods_cny), inland_origin: r6(inland_o), export_clear: r6(export_c),
      freight: r6(freight), insurance: r6(insurance), cif: r6(cif),
      discharge: r6(discharge), duty: r6(duty), other_tax: r6(other_tax),
      vat: r6(vat), vat_credit: r6(vat_credit), inland_dest: r6(inland_d),
      unload: r6(unload), landed_cash: r6(landed_cash), cash_out: r6(cash_out),
      net_cash: r6(net_cash), unit_net: r6(unit_net),
      taxable: r6(cif + discharge + duty), vat_rate: vat_rate, includes: inc
    };
  }

  function comparable_price(cfg, cost) {
    var vat_rate = fnum(cfg.vat_rate, 0.13);
    if (vat_rate === null) { vat_rate = 0.13; }
    var dom_quote = fnum(cfg.dom_quote, 0) || 0;
    var tax = String(cfg.dom_tax || '含税').trim();
    var add_freight = cfg.dom_term_incl_freight ? 0 : (fnum(cfg.dom_freight_to_bench, 0) || 0);
    var adj = fnum(cfg.dom_scale_adj, 0) || 0;
    var net_price, gross_price;
    if (tax === '不含税' || tax === '未税') {
      net_price = dom_quote + add_freight + adj;
      gross_price = net_price * (1 + vat_rate);
    } else {
      gross_price = dom_quote + add_freight + adj;
      net_price = gross_price / (1 + vat_rate);
    }
    var out = {
      dom_quote: r6(dom_quote), dom_freight_added: r6(add_freight), dom_adj: r6(adj),
      dom_price: r6(gross_price), dom_net_price: r6(net_price),
      dom_vat_in: r6(gross_price - net_price), tax: tax, vat_rate: vat_rate
    };
    if (cost) {
      out.cif = cost.cif;
      out.cif_incl_vat = r6(cost.cif * (1 + vat_rate));
      out.gap_vs_landed_cash = r6(gross_price - cost.landed_cash);
      out.gap_vs_net_cash = r6(gross_price - cost.net_cash);
      out.gap_vs_cif = r6(net_price - cost.cif);
    }
    return out;
  }

  function gap_table(bid_px, cost, comp) {
    if (bid_px === null || bid_px === undefined || !cost || !comp) { return []; }
    var defs = [
      ['G1_cif_vs_domnet', 'CIF 折人民币 vs 国内未税', '国内未税送到 − 进口 CIF 折人民币',
        '纯价格口径：两边都不含增值税，反映国际与国内价格本身的高低', comp.dom_net_price - cost.cif],
      ['G2_landedcash_vs_domallin', '含税到岸 vs 国内含税送到', '国内含税送到 − 进口含税到岸 landed_cash',
        '现金口径：两边都含税，反映全部现金付出之差', bid_px - cost.landed_cash],
      ['G3_netcash_vs_domallin', '经济成本 vs 国内含税送到', '国内含税送到 − 进口经济成本 net_cash',
        '经济口径：进口增值税按可抵扣处理后的真实可比成本', bid_px - cost.net_cash],
      ['G4_vatadj', '进项税抵扣调整后', '国内未税送到 − 进口经济成本',
        '税制口径：看价格差里有多少来自增值税抵扣权的估值差异', comp.dom_net_price - cost.net_cash]
    ];
    return defs.map(function (d) {
      return { code: d[0], name: d[1], formula: d[2], meaning: d[3], value: r6(d[4]) };
    });
  }

  var COST_KEYS = ['goods_cny', 'inland_origin', 'export_clear', 'freight', 'insurance',
    'discharge', 'duty', 'other_tax', 'vat_net', 'inland_dest', 'unload'];

  function normalized_cost(c) {
    var d = {};
    for (var k in c) { if (Object.prototype.hasOwnProperty.call(c, k)) { d[k] = c[k]; } }
    d.vat_net = (c.vat || 0) - (c.vat_credit || 0);
    return d;
  }

  function contribution(a, b) {
    var na = normalized_cost(a), nb = normalized_cost(b), parts = {}, sum = 0;
    COST_KEYS.forEach(function (k) {
      parts[k] = r6(-(nb[k] - na[k]));
      sum += parts[k];
    });
    var total = nb.net_cash - na.net_cash;
    parts._total_cost_change = r6(total);
    parts._sum = r6(sum);
    parts._closure = r6(-total - parts._sum);
    return parts;
  }

  function implied_other_costs(bid_px, cif_cny, freight_cny, insurance_cny, discharge_cny) {
    if (bid_px === null || bid_px === undefined || cif_cny === null || cif_cny === undefined) { return null; }
    return r6(bid_px - cif_cny - (freight_cny || 0) - (insurance_cny || 0) - (discharge_cny || 0));
  }

  var SENS_KEY_MAP = {
    freight: 'ocean_freight', fx: 'fx_usdcny', duty: 'duty_rate', vat: 'vat_rate',
    insurance_pct: 'insurance_rate_pct', credit: 'vat_credit_ratio',
    discharge: 'discharge_fee', inland_dest: 'inland_dest', price: 'price_quote', term: 'term'
  };

  function sensitivity_one(base_params, key, values) {
    var base = import_cost(base_params);
    var pkey = SENS_KEY_MAP[key] || key;
    return values.map(function (pair) {
      var p = {}, k;
      for (k in base_params) { if (Object.prototype.hasOwnProperty.call(base_params, k)) { p[k] = base_params[k]; } }
      p[pkey] = pair[1];
      var res = import_cost(p);
      return {
        key: key, label: pair[0], value: pair[1],
        cif: res.cif, landed_cash: res.landed_cash, net_cash: res.net_cash,
        delta_vs_base: r6(res.net_cash - base.net_cash)
      };
    });
  }

  function check_terms(p) {
    var term = norm_term(p.term);
    var inc = TERM_INCLUDES[term];
    var issues = [];
    Object.keys(TERM_GUARDED).forEach(function (flag) {
      if (!inc[flag]) { return; }
      var key = TERM_GUARDED[flag][0], label = TERM_GUARDED[flag][1];
      var val = fnum(p[key], 0) || 0;
      if (val > 0) {
        issues.push({
          level: 'error', code: 'DOUBLE_COUNT_' + key.toUpperCase(),
          msg: term + ' 报价已包含「' + label + '」，参数里又填了 ' + val +
            '；为避免重复计费，该项已按 0 处理。请把术语改成不含该项的口径，或删除该参数。'
        });
      }
    });
    return issues;
  }

  function check_config(cfg) {
    var issues = [];
    var vat = fnum(cfg.vat_rate, 0.13);
    if (vat === null || !(vat >= 0 && vat < 1)) { issues.push({ level: 'error', code: 'VAT_RANGE', msg: '增值税率必须落在 [0,1)' }); }
    var cr = fnum(cfg.vat_credit_ratio, 1);
    if (cr === null || !(cr >= 0 && cr <= 1)) { issues.push({ level: 'error', code: 'CREDIT_RANGE', msg: '可抵扣比例必须落在 [0,1]' }); }
    if (!((fnum(cfg.price_quote, 0) || 0) > 0)) { issues.push({ level: 'error', code: 'QUOTE_POSITIVE', msg: '海外报价必须为正' }); }
    var cur = String(cfg.currency || 'USD').toUpperCase();
    var fx = fnum(cfg.fx_usdcny, 0) || 0;
    if (cur === 'USD' && !(fx >= 4 && fx <= 12)) {
      issues.push({ level: 'error', code: 'FX_RANGE', msg: 'USD/CNY=' + fx.toFixed(4) + ' 不在 4~12 的合理区间' });
    }
    var dq = fnum(cfg.dom_quote, 0);
    if (dq === null || dq === 0) { issues.push({ level: 'warn', code: 'DOM_QUOTE', msg: '国内现货价未填：价差全部为空' }); }
    return issues;
  }

  var WSC = {
    ROUND: ROUND, TERM_INCLUDES: TERM_INCLUDES, TERM_LABEL: TERM_LABEL,
    fnum: fnum, r6: r6, norm_term: norm_term,
    import_cost: import_cost, comparable_price: comparable_price, gap_table: gap_table,
    contribution: contribution, implied_other_costs: implied_other_costs,
    sensitivity_one: sensitivity_one, check_terms: check_terms, check_config: check_config,
    COST_KEYS: COST_KEYS
  };

  if (typeof module !== 'undefined' && module.exports) { module.exports = WSC; }
  root.WSC = WSC;
})(typeof window !== 'undefined' ? window : globalThis);
