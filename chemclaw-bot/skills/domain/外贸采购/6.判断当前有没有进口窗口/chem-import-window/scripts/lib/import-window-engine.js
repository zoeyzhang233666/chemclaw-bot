/**
 * import-window-engine.js — 进口窗口（进口价差）计算引擎（单一计算真源）
 * ---------------------------------------------------------------------------
 * 纯函数、零依赖，同时被三处复用，保证 HTML / Excel / Python 三路结果一致：
 *   1) 浏览器：scripts/build_html.cjs 把本文件内联进 HTML（页面内暴露 ImportWindowEngine）
 *   2) Node  ：scripts/validate.js、tools/calc_verify.js 直接 require
 *   3) Excel ：build_xlsx.py 把窗口参数写进「1-参数」，Excel 内用公式复刻本引擎的口径，
 *              再由 tools/calc_verify.js 用本引擎计算同一窗口并写回归一列做交叉校验
 *
 * 设计约束（对应 SKILL.md 的红线）：
 *   · 不内置任何具体品种/税率/运价/规格；一切来自 case 数据。
 *   · 缺值一律 null，绝不把缺失当成 0；缺关键项就返回 calculable=false 并说明原因。
 *   · 不预测：本引擎只做"同一口径下的当日/历史折算"，不含任何趋势外推。
 *
 * 术语与口径（全部可比较到"中国进口商可达、含税、指定交货地"）：
 *   海外报价 FOB / CFR / CIF（USD/吨，可选带升贴水）
 *     → 到岸价 CIF（若报价为 FOB 或 CFR 则加国际运费/保险）
 *     → 关税完税价格（人民币）= CIF 美元价 × 汇率 × (1 + 保险费率 + 申报调整项)
 *     → 关税 = 完税价 × 关税税率
 *     → 进口环节增值税 = (完税价 + 关税) × 增值税率
 *     → 不含可抵扣增值税的进口成本（"含税净成本"）= 完税价 + 关税 + 港口/清关/内陆等费用
 *   与国内现货含税价比较时：国内含税价（增值税可抵扣）↔ 进口"含税净成本"（增值税可抵扣）
 *   不可抵扣增值税只作为资金/实际成本在"真实利润"口径里另计。
 */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.ImportWindowEngine = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : (typeof self !== 'undefined' ? self : (typeof window !== 'undefined' ? window : this)), function () {
  'use strict';

  // ============================================================ 基础工具
  function isNum(v) {
    return typeof v === 'number' && isFinite(v);
  }

  function num(v, dflt) {
    if (isNum(v)) return v;
    if (typeof v === 'string' && v.trim() !== '' && isFinite(Number(v))) return Number(v);
    return dflt === undefined ? null : dflt;
  }

  function round(v, nd) {
    if (!isNum(v)) return null;
    var p = Math.pow(10, nd === undefined ? 2 : nd);
    return Math.round(v * p) / p;
  }

  function pct(v) {
    var n = num(v);
    return n === null ? null : n / 100;
  }

  function get(obj, path, dflt) {
    var cur = obj;
    var parts = String(path).split('.');
    for (var i = 0; i < parts.length; i++) {
      if (cur === null || cur === undefined || typeof cur !== 'object') return dflt === undefined ? null : dflt;
      cur = cur[parts[i]];
    }
    return cur === undefined ? (dflt === undefined ? null : dflt) : cur;
  }

  var TERMS = ['FOB', 'CFR', 'CIF', 'EXW', 'DDP'];
  var BASE_PORT_TERMS = ['CFR', 'CIF'];

  // ============================================================ 汇率
  /**
   * 取某日汇率（直接标价：1 外币 = X CNY）。
   * 只做"精确匹配"，不做插值 —— 历史价差必须用同期汇率。
   */
  function fxOnDate(fxSeries, date) {
    if (!fxSeries || !fxSeries.rows) return null;
    var rows = fxSeries.rows;
    for (var i = rows.length - 1; i >= 0; i--) {
      if (rows[i].date === date) {
        var v = num(rows[i].rate);
        if (v === null) return null;
        return { seriesId: fxSeries.id, date: date, rate: v, exact: true };
      }
    }
    return null;
  }

  /** 汇率序列覆盖范围 */
  function fxRange(fxSeries) {
    if (!fxSeries || !fxSeries.rows || !fxSeries.rows.length) return null;
    var ds = fxSeries.rows.map(function (r) { return r.date; }).sort();
    return { first: ds[0], last: ds[ds.length - 1], n: ds.length };
  }

  // ============================================================ 税费参数
  /**
   * 解析税费参数：支持"随日期生效"的多版本，历史回算时按当期版本取用。
   * tax.profiles = [{ effective_from, vat_rate, duty_rate, duty_basis, duty_hs, duty_source_id, note }]
   */
  function taxProfileOn(tax, date) {
    if (!tax) return null;
    var profiles = tax.profiles || [];
    if (!profiles.length) {
      return tax.vat_rate === undefined ? null : {
        effective_from: null, vat_rate: tax.vat_rate, duty_rate: tax.duty_rate,
        duty_hs: tax.duty_hs, duty_note: tax.duty_note, exact: true, provisional: false
      };
    }
    var best = null;
    for (var i = 0; i < profiles.length; i++) {
      var p = profiles[i];
      if (!p.effective_from || p.effective_from <= date) {
        if (!best || (p.effective_from || '') > (best.effective_from || '')) best = p;
      }
    }
    if (!best) {
      // 日期早于最早生效版本：不能倒推历史税率
      return null;
    }
    return best;
  }

  // ============================================================ 运费
  /**
   * 取某日报价可用的运费：
   *   1) quote 自带 freight_usd（供应商/货代直接报价，优先级最高）
   *   2) 外部运费序列 freight 的最新值（带日期，非该日则标记 stale）
   *   3) 都没有 → null（不估算）
   */
  function resolveFreight(caseData, quote, date, opts) {
    var o = opts || {};
    if (quote && isNum(num(quote.freight_usd))) {
      return {
        usd: num(quote.freight_usd),
        basis: '报价自带',
        date: quote.date || date,
        stale: false,
        source_id: quote.source_id || null
      };
    }
    var fr = caseData && caseData.freight;
    if (fr && fr.source === 'none') return null;
    if (fr && isNum(num(fr.usd_per_ton))) {
      var stale = fr.date !== date;
      // 历史回算时，运费日期与价格日期不一致就必须标记（除非显式允许跨期）
      if (stale && o.requireSameDate) {
        return { usd: num(fr.usd_per_ton), basis: fr.basis || '外部序列', date: fr.date, stale: true, source_id: fr.source_id || null };
      }
      return { usd: num(fr.usd_per_ton), basis: fr.basis || '外部序列', date: fr.date, stale: stale, source_id: fr.source_id || null };
    }
    if (fr && fr.series && fr.series.rows) {
      var rows = fr.series.rows;
      var hit = null;
      for (var i = rows.length - 1; i >= 0; i--) {
        if (rows[i].date <= date) { hit = rows[i]; break; }
      }
      if (hit) {
        return { usd: num(hit.usd), basis: fr.basis || '运费序列', date: hit.date, stale: hit.date !== date, source_id: fr.source_id || null };
      }
    }
    return null;
  }

  // ============================================================ 核心折算
  /**
   * 计算一天（或一个报价快照）的进口成本。
   *
   * @param {Object} caseData 整份 case 数据
   * @param {Object} snapshot {
   *     date, quote(可选，为 null 用 caseData.quote), fx_rate(可选覆盖),
   *     freight_usd(可选覆盖), domestic_price(可选覆盖), params(可选覆盖)
   * }
   * @returns {Object} 结果（绝不抛错；不可算时 calculable=false + blockers[]）
   */
  function computeLanding(caseData, snapshot) {
    var snap = snapshot || {};
    var date = snap.date || get(caseData, 'asof.date');
    var res = {
      date: date,
      calculable: false,
      blockers: [],
      gaps: [],
      warnings: [],
      quote: null,
      fx: null,
      freight: null,
      tax: null,
      domestic: null,
      lineItems: [],
      totals: {},
      spread: {},
      tier: 'none'                       // none | fragile | indicative | full
    };

    var quote = snap.quote || (caseData && caseData.quote);
    if (!quote) {
      res.blockers.push({ code: 'NO_QUOTE', text: '没有海外报价，无法折算进口成本' });
      return res;
    }
    res.quote = quote;

    var p = Object.assign({}, (caseData && caseData.params) || {}, snap.params || {});

    // ---------- 1. 报价基础字段校验
    var price = num(quote.price_usd);
    var term = (quote.term || '').toUpperCase();
    if (price === null) res.blockers.push({ code: 'NO_PRICE', text: '海外报价缺少数值' });
    if (TERMS.indexOf(term) < 0) res.blockers.push({ code: 'NO_TERM', text: '海外报价缺少有效贸易术语（FOB/CFR/CIF）' });
    if (num(quote.premium_usd, 0) === null) res.warnings.push('升贴水非数值，按 0 处理');

    // ---------- 2. 汇率（不估算）
    var fxRec = null;
    if (isNum(num(snap.fx_rate))) {
      fxRec = { rate: num(snap.fx_rate), date: date, basis: '手动指定', stale: false };
    } else {
      fxRec = fxOnDate(caseData && caseData.fx, date);
      if (fxRec) fxRec.basis = '汇率序列精确匹配';
    }
    if (!fxRec) {
      res.fx = null;
      res.blockers.push({
        code: 'NO_FX',
        text: '缺少 ' + date + ' 当日的汇率（不做插值），无法折算人民币'
      });
    } else {
      res.fx = fxRec;
    }

    // ---------- 3. 税费（按生效版本，不倒推）
    var tax = snap.tax_profile || taxProfileOn(caseData && caseData.tax, date);
    if (!tax) {
      res.blockers.push({
        code: 'NO_TAX',
        text: '缺 ' + date + ' 适用的关税/增值税税率版本（历史区间不得用当前税率倒推）'
      });
    }
    var vatRate = tax ? pct(tax.vat_rate) : null;
    var dutyRate = tax ? pct(tax.duty_rate) : null;
    if (tax && vatRate === null) res.blockers.push({ code: 'NO_VAT_RATE', text: '缺增值税率' });
    if (tax && dutyRate === null) res.blockers.push({ code: 'NO_DUTY_RATE', text: '缺关税税率' });
    if (tax && tax.provisional) {
      res.warnings.push('关税税率来自暂定/协定口径（' + (tax.duty_hs || '未注税号') + '），须以实际报关税号与报关日税率为准');
    }
    res.tax = tax;

    // ---------- 4. 运费与保险
    var freight = null;
    if (term === 'FOB' || term === 'EXW') {
      freight = resolveFreight(caseData, quote, date, snap);
      if (!freight || !isNum(freight.usd)) {
        res.blockers.push({
          code: 'NO_FREIGHT',
          text: '报价为 ' + term + '，成交前必须加国际运费；当前没有可用运费数据，不做估算'
        });
        freight = null;
      }
    } else if (term === 'CFR' || term === 'CIF') {
      freight = { usd: 0, basis: '已含在 ' + term + ' 报价中', date: date, stale: false };
    }
    if (freight && freight.stale) {
      res.warnings.push('运费数据日期（' + freight.date + '）与价格日期（' + date + '）不一致');
    }
    res.freight = freight;

    // 保险：CIF 已含保险；FOB/CFR 按 params.insurance_rate 与 params.insurance_basis 计
    var cfrUsd = null;
    var insuranceUsd = 0;
    if (isNum(price)) {
      var prem = num(quote.premium_usd, 0);
      var baseUsd = price + prem;            // 升贴水后的美元单价
      res.quote = Object.assign({}, quote, { net_usd: baseUsd });

      if (term === 'CIF') {
        cfrUsd = baseUsd;
      } else if (term === 'CFR') {
        cfrUsd = baseUsd;
      } else if ((term === 'FOB' || term === 'EXW') && freight) {
        cfrUsd = baseUsd + freight.usd;
      }

      var insBase = (p.insurance_basis === 'cif' && cfrUsd !== null) ? cfrUsd : cfrUsd;
      if (term !== 'CIF' && cfrUsd !== null) {
        var insRate = pct(p.insurance_rate);
        var insFactor = num(p.insurance_on_110, 1);  // 保险费通常按 CIF×110% 计保额
        if (insRate === null) {
          res.gaps.push('保险费率未提供：口岸的"到岸价"口径可能因此少计一笔保险费（通常影响 <0.5%）');
          insuranceUsd = 0;
        } else {
          var cifGuess = cfrUsd / (1 - insRate * (insFactor === 1 ? 1.1 : 1));
          insuranceUsd = cifGuess * insRate * (insFactor === 1 ? 1.1 : 1);
        }
      }
      var cifUsd = cfrUsd === null ? null : cfrUsd + insuranceUsd;

      res.lineItems.push({ key: 'price', label: '海外报价（' + term + '）', usd: price, cny: null });
      if (prem !== 0) res.lineItems.push({ key: 'premium', label: '品质/船期升贴水', usd: prem, cny: null });
      if (freight && freight.usd) res.lineItems.push({ key: 'freight', label: '国际运费', usd: freight.usd, cny: null });
      if (insuranceUsd) res.lineItems.push({ key: 'insurance', label: '保险费', usd: insuranceUsd, cny: null });

      res.totals.cfr_usd = cfrUsd;
      res.totals.cif_usd = cifUsd;
    }

    // ---------- 5. 人民币完税与成本（需要汇率 + 税率 + CIF）
    var blocked = res.blockers.length > 0;
    var fx = res.fx ? res.fx.rate : null;
    var cifUsd = res.totals.cif_usd;

    if (!blocked) {
      // 完税价格调整（如运费需计入完税价、佣金、境外运输杂费），按申报口径折算
      var adjRate = pct(p.dutiable_adjust_rate);
      var adj = adjRate === null ? 0 : cifUsd * adjRate;
      res.totals.dutiable_adjust_usd = adj;

      var cifCny = (cifUsd + adj) * fx;
      var duty = cifCny * dutyRate;
      var vatBase = cifCny + duty;
      var vat = vatBase * vatRate;

      // 港口/清关/内陆等境内费用（人民币/吨）。缺省按 0 但必须登记为假设
      var inland = num(p.inland_cost_cny);
      if (inland === null) {
        res.gaps.push('境内费用（港杂、报关、仓储、内陆运输等）未提供，按 0 计');
        inland = 0;
      }
      var misc = num(p.other_cost_cny, 0) || 0;

      // 增值税是否可抵扣：可抵扣 → 不计入可比成本；不可抵扣 → 计入
      var vatRecoverable = p.vat_recoverable !== false;
      var vatCost = vatRecoverable ? 0 : vat;

      var netCost = cifCny + duty + inland + misc + vatCost;   // 与国内含税价可比的口径
      var grossCost = cifCny + duty + vat + inland + misc;     // 全部付现（含可抵扣增值税）

      res.totals.cif_cny = cifCny;
      res.totals.dutiable_adjust_cny = adj * fx;
      res.totals.duty = duty;
      res.totals.vat = vat;
      res.totals.vat_recoverable = vatRecoverable;
      res.totals.inland = inland;
      res.totals.other = misc;
      res.totals.net_cost = netCost;        // ← 与国内含税现货价直接相减的口径
      res.totals.gross_cost = grossCost;    // ← 全口径付现（含可抵扣增值税）
      res.totals.cost_per_usd = (fx > 0 ? netCost / (cifUsd * fx) : null);

      res.lineItems.push({ key: 'duty', label: '关税', usd: null, cny: duty });
      res.lineItems.push({ key: 'vat', label: '进口环节增值税' + (vatRecoverable ? '（可抵扣，不计入成本）' : '（不可抵扣，计入成本）'), usd: null, cny: vatCost });
      if (inland) res.lineItems.push({ key: 'inland', label: '境内费用（港口/清关/内陆）', usd: null, cny: inland });
      if (misc) res.lineItems.push({ key: 'other', label: '其他费用', usd: null, cny: misc });

      res.calculable = true;
      res.tier = computeTier(res, caseData);
    } else {
      res.tier = 'none';
    }

    // ---------- 6. 国内现货（含税、指定交货地）
    var dom = snap.domestic;
    if (!dom && caseData && caseData.domestic) {
      dom = caseData.domestic;
    }
    if (dom) {
      var dval = num(dom.price_cny);
      res.domestic = {
        price_cny: dval,
        date: dom.date || null,
        delivery: dom.delivery || null,
        tax_included: dom.tax_included !== false,
        region: dom.region || null,
        source_id: dom.source_id || null,
        date_match: !dom.date || dom.date === date
      };
      if (dom.date && dom.date !== date) {
        res.warnings.push('国内价格日期（' + dom.date + '）与海外价格日期（' + date + '）不一致，价差仅作同期近似');
        res.tier = lowerTier(res.tier, 'indicative');
      }
    } else {
      res.gaps.push('缺少同规格、同交货地的国内含税现货价，无法计算价差');
    }

    // ---------- 7. 价差
    if (res.calculable && res.domestic && isNum(res.domestic.price_cny)) {
      var domestic = res.domestic.price_cny;
      var net = res.totals.net_cost;
      res.spread = {
        // 定义：国内现货含税价 − 进口含税净成本（增值税同口径：可抵扣）
        abs_cny: domestic - net,
        pct_of_domestic: domestic ? (domestic - net) / domestic * 100 : null,
        pct_of_cost: net ? (domestic - net) / net * 100 : null,
        win: (domestic - net) > 0
      };
    } else {
      res.spread = { abs_cny: null, pct_of_domestic: null, pct_of_cost: null, win: null };
    }

    return res;
  }

  var TIERS = ['none', 'fragile', 'indicative', 'full'];

  function lowerTier(a, b) {
    return TIERS.indexOf(a) <= TIERS.indexOf(b) ? a : b;
  }

  /**
   * 可比性等级（决定"这个价差能不能拿来当依据"）：
   *   none       缺关键项，不计算
   *   fragile    关键项靠假设/参照值撑起（如运费非中标价、税率待确认、境内费用未含）
   *   indicative 关键项齐全，但仍有口径不一致（日期错配、交货地不一致等）
   *   full       同日期、同规格、同税口径、同交货地、费率均可核验
   */
  function computeTier(res, caseData) {
    var hard = 0;
    var soft = 0;
    // 运费是否来自报价/序列
    if (res.freight) {
      if (res.freight.stale) soft++;
      if (/参照|proxy|benchmark/i.test(String(res.freight.basis || '')) || (caseData && caseData.freight && caseData.freight.quality === 'proxy')) hard++;
    }
    // 关税口径不确定（暂定/协定）
    if (res.tax && res.tax.provisional) hard++;
    if (res.tax && res.tax.exact === false) soft++;
    // 境内费用缺失
    if (res.gaps && res.gaps.length) soft++;
    // 国内价格日期不一致
    if (res.domestic && res.domestic.date_match === false) soft++;
    if (res.domestic && res.domestic.tax_included === false) soft++;
    if (!res.fx || res.fx.stale) soft++;
    if (hard > 0) return 'fragile';
    if (soft > 0) return 'indicative';
    return 'full';
  }

  // ============================================================ 敏感性
  /**
   * 对当前快照做单因素敏感性：
   *   fx_delta: [-0.03, -0.015, 0, 0.015, 0.03]  （汇率 ±3%）
   *   freight_delta_usd: [-20, -10, 0, 10, 20]   （运费每吨变动，默认按现有运费的 ±20% 生成步长）
   *   premium_delta_usd / offshore_pct: 海外报价 ±3%
   */
  function sensitivity(caseData, snapshot, opts) {
    var o = opts || {};
    var base = computeLanding(caseData, snapshot);
    var fxDeltas = o.fx_deltas || [-0.03, -0.015, 0, 0.015, 0.03];
    var offPcts = o.offshore_pcts || [-0.03, -0.015, 0, 0.015, 0.03];
    var frAbs = base.freight && base.freight.usd ? Math.abs(base.freight.usd) : 0;
    var frStep = o.freight_step_usd !== undefined ? o.freight_step_usd : Math.max(5, Math.round(frAbs * 0.2));
    var frDeltas = o.freight_deltas || [-2 * frStep, -frStep, 0, frStep, 2 * frStep];

    function run(overrides) {
      return computeLanding(caseData, Object.assign({}, snapshot, overrides));
    }

    var baseFx = base.fx ? base.fx.rate : null;
    var out = {
      base: base,
      fx: [],
      offshore: [],
      freight: [],
      tornado: []
    };

    if (baseFx !== null) {
      fxDeltas.forEach(function (d) {
        var r = run({ fx_rate: baseFx * (1 + d) });
        out.fx.push({ delta: d, fx_rate: baseFx * (1 + d), net_cost: r.totals.net_cost, spread: r.spread.abs_cny, calculable: r.calculable });
      });
    }
    offPcts.forEach(function (d) {
      var q = Object.assign({}, base.quote);
      var pr = num(q.price_usd);
      if (pr === null) return;
      q.price_usd = pr * (1 + d);
      var r = run({ quote: q });
      out.offshore.push({ delta: d, price_usd: q.price_usd, net_cost: r.totals.net_cost, spread: r.spread.abs_cny, calculable: r.calculable });
    });
    frDeltas.forEach(function (d) {
      if (!base.freight) return;
      var r = run({ freight_usd: base.freight.usd + d });
      out.freight.push({ delta_usd: d, freight_usd: base.freight.usd + d, net_cost: r.totals.net_cost, spread: r.spread.abs_cny, calculable: r.calculable });
    });

    // 龙卷风图：单因素 ±1 个"典型波动"对价差的绝对影响
    function pick(arr, key) {
      return arr.map(function (x) { return x[key]; }).filter(isNum);
    }
    function range(arr) {
      var v = pick(arr, 'spread');
      if (v.length < 2) return null;
      return { low: Math.min.apply(null, v), high: Math.max.apply(null, v), span: Math.max.apply(null, v) - Math.min.apply(null, v) };
    }
    [
      { key: 'fx', label: '汇率 ±3%', r: range(out.fx) },
      { key: 'offshore', label: '海外报价 ±3%', r: range(out.offshore) },
      { key: 'freight', label: '运费 ±' + (2 * frStep) + ' USD/吨', r: range(out.freight) }
    ].forEach(function (x) {
      if (x.r) out.tornado.push({ key: x.key, label: x.label, low: x.r.low, high: x.r.high, span: x.r.span, base: base.spread.abs_cny });
    });
    out.tornado.sort(function (a, b) { return b.span - a.span; });

    // 盈亏平衡：在当前各项参数下，价差归零需要汇率/海外价变动多少
    out.breakeven = breakeven(caseData, snapshot, base);
    return out;
  }

  /**
   * 盈亏平衡点（不是价格预测，只是"当前参数下的零点位置"）。
   */
  function breakeven(caseData, snapshot, base) {
    base = base || computeLanding(caseData, snapshot);
    var out = { fx_rate: null, offshore_pct: null, freight_usd: null, spread_now: base.spread.abs_cny };
    if (!base.calculable || !isNum(base.spread.abs_cny)) return out;
    var spread = base.spread.abs_cny;

    // 汇率：价差对汇率近似线性（成本中 CIF 部分按汇率缩放）
    var fx = base.fx ? base.fx.rate : null;
    if (fx) {
      var rPlus = computeLanding(caseData, Object.assign({}, snapshot, { fx_rate: fx * 1.05 }));
      var rMinus = computeLanding(caseData, Object.assign({}, snapshot, { fx_rate: fx * 0.95 }));
      if (isNum(rPlus.spread.abs_cny) && isNum(rMinus.spread.abs_cny)) {
        var slope = (rPlus.spread.abs_cny - rMinus.spread.abs_cny) / (fx * 0.1); // 每 1 CNY 汇率对应的价差变化
        if (slope !== 0) {
          var fxAt = fx + (-spread) / slope;
          if (fxAt > 0) {
            out.fx_rate = fxAt;
            out.fx_move_pct = (fxAt / fx - 1) * 100;
            // 变动幅度过大时，零点仍是数学事实，但必须提示"远超常见波动区间"
            out.fx_out_of_range = Math.abs(out.fx_move_pct) > 15;
            if (out.fx_out_of_range) {
              out.fx_note = '汇率零点距当前 ' + out.fx_move_pct.toFixed(1) + '%，远超一个季度内的常见波动（±3%），'
                + '说明按当前参数价差不会因汇率常规波动而消失；该数值仅作数学说明，不是汇率预测。';
            }
          }
        }
      }
    }
    // 海外报价：美元价每变动 1 USD/吨 → 人民币成本变动
    var q = base.quote || (caseData && caseData.quote);
    var pr = q ? num(q.price_usd) : null;
    if (pr && fx) {
      var q2 = Object.assign({}, q, { price_usd: pr * 1.02 });
      var r2 = computeLanding(caseData, Object.assign({}, snapshot, { quote: q2 }));
      if (isNum(base.totals.net_cost) && isNum(r2.totals.net_cost)) {
        var dCost = r2.totals.net_cost - base.totals.net_cost;   // 报价 +2% 引起的成本变化
        if (dCost !== 0) {
          var needed = -spread;                                  // 成本需上升多少才让价差归零
          var pct = (needed / dCost) * 2 * 100;                  // 换算为百分比
          // 只有在"报价仍为正、且变动幅度在合理区间（±50%）"时，零点才具备经济含义。
          // 否则（例如需要报价跌到负数）明确标注"超出可达范围"，不输出荒谬数值。
          var priceAt = pr * (1 + pct / 100);
          if (priceAt > 0 && Math.abs(pct) <= 50) {
            out.offshore_pct = pct;
            out.offshore_price_usd = priceAt;
            out.offshore_reachable = true;
          } else {
            out.offshore_pct = null;
            out.offshore_price_usd = null;
            out.offshore_reachable = false;
            out.offshore_note = '在当前参数下要使价差归零，海外报价需变动 ' + pct.toFixed(0)
              + '%（约合 ' + priceAt.toFixed(1) + ' USD/吨），已超出可达范围（报价须为正且在 ±50% 内），'
              + '说明本案例的价差并非由报价一项主导 —— 这本身就是结论的一部分，不给出无意义的零点。';
          }
        }
      }
    }
    // 运费盈亏点（仅 FOB/CFR）
    if (base.freight && isNum(base.freight.usd) && fx) {
      var f0 = base.freight.usd;
      var ra = computeLanding(caseData, Object.assign({}, snapshot, { freight_usd: f0 + 10 }));
      var rb = computeLanding(caseData, Object.assign({}, snapshot, { freight_usd: f0 }));
      if (isNum(ra.totals.net_cost) && isNum(rb.totals.net_cost)) {
        var perUsd = (ra.totals.net_cost - rb.totals.net_cost) / 10;
        if (perUsd > 0) out.freight_usd = f0 + (base.totals.net_cost - (base.domestic ? base.domestic.price_cny : NaN)) / perUsd;
      }
    }
    return out;
  }

  // ============================================================ 贡献分解
  /**
   * 成本贡献：把"进口净成本"与"国内现货价"之差拆成价格成分与费用成分。
   */
  function costContribution(res) {
    if (!res || !res.calculable) return null;
    var t = res.totals;
    var d = res.domestic ? res.domestic.price_cny : null;
    var items = [
      { key: 'cif_cny', label: 'CIF 货值', value: t.cif_cny },
      { key: 'duty', label: '关税', value: t.duty },
      { key: 'inland', label: '境内费用', value: t.inland + (t.other || 0) }
    ];
    var sum = 0;
    items.forEach(function (x) { sum += x.value || 0; });
    return {
      items: items,
      vat: t.vat,
      vat_recoverable: t.vat_recoverable,
      net_cost: t.net_cost,
      domestic: d,
      spread: isNum(d) ? d - t.net_cost : null
    };
  }

  // ============================================================ 历史序列
  /**
   * 构建历史进口价差序列。
   *
   * 硬约束（实现层保证）：
   *   · 每个历史点必须用自己的报价、自己的汇率、自己的税率版本；
   *   · 汇率必须精确匹配当日，缺失记 gap，不插值；
   *   · 运费若为外部参照值，历史点标记 freight_proxy=true，并降级为 reference_only；
   *   · 任何点缺关键项 → 该点 status='gap'，不输出价差，绝不"用当前参数补历史"。
   */
  function buildHistory(caseData, opts) {
    var o = opts || {};
    var quotes = (caseData && caseData.quotes_hist) || [];
    var domRows = (caseData && caseData.domestic_hist && caseData.domestic_hist.rows) || [];
    var domMap = {};
    domRows.forEach(function (r) { domMap[r.date] = r; });

    var out = [];
    quotes.slice().sort(function (a, b) { return a.date < b.date ? -1 : 1; }).forEach(function (q) {
      var snap = { date: q.date, quote: q };
      var dom = domMap[q.date];
      if (dom) snap.domestic = dom;
      var r = computeLanding(caseData, snap);

      var status = 'ok';
      var gapReason = null;
      if (!r.calculable) { status = 'gap'; gapReason = (r.blockers[0] || {}).text || '缺关键参数'; }
      else if (!dom) { status = 'gap'; gapReason = '缺少同日国内现货价'; }

      var fp = false;
      var fq = caseData && caseData.freight && caseData.freight.quality;
      if ((q.term === 'FOB' || q.term === 'CFR' || q.term === 'EXW') && (fq === 'proxy' || fq === 'reference')) fp = true;
      if (r.freight && r.freight.basis && /参照|proxy|benchmark/i.test(String(r.freight.basis))) fp = true;

      out.push({
        date: q.date,
        status: status,
        gap_reason: gapReason,
        tier: r.tier,
        quote_usd: num(q.price_usd),
        term: q.term,
        fx: r.fx ? r.fx.rate : null,
        fx_missing: !r.fx,
        freight_usd: r.freight ? r.freight.usd : null,
        freight_proxy: fp,
        net_cost: r.calculable ? r.totals.net_cost : null,
        vat: r.calculable ? r.totals.vat : null,
        duty: r.calculable ? r.totals.duty : null,
        cif_cny: r.calculable ? r.totals.cif_cny : null,
        domestic: dom ? num(dom.price_cny) : null,
        domestic_delivery: dom ? dom.delivery : null,
        spread: status === 'ok' ? r.spread.abs_cny : null,
        spread_pct: status === 'ok' ? r.spread.pct_of_domestic : null,
        reference_only: fp,
        results: o.keepResults ? r : undefined
      });
    });
    return out;
  }

  // ============================================================ 口径可比性检查
  /**
   * 自动检查"海外报价"与"国内现货价"是否真正可比（问用户之前先自查）。
   * 返回 {checks:[{id,label,status:'pass'|'warn'|'fail'|'unknown',detail}], verdict}
   */
  function compatibility(caseData, landing) {
    landing = landing || computeLanding(caseData, {});
    var q = (caseData && caseData.quote) || {};
    var d = (caseData && caseData.domestic) || {};
    var checks = [];

    function add(id, label, status, detail) {
      checks.push({ id: id, label: label, status: status, detail: detail });
    }

    // 1 产品与规格
    var qspec = q.spec || null;
    var dspec = d.spec || null;
    if (qspec && dspec && qspec === dspec) add('spec', '产品规格一致', 'pass', '海外：' + qspec + '；国内：' + dspec);
    else if (qspec && dspec) add('spec', '产品规格一致', 'fail', '海外：' + qspec + '；国内：' + dspec + '（规格不同，价差不可直接比较）');
    else add('spec', '产品规格一致', 'unknown', '至少一方未标注规格');

    // 2 日期
    if (q.date && d.date && q.date === d.date) add('date', '价格日期一致', 'pass', q.date);
    else if (q.date && d.date) add('date', '价格日期一致', 'fail', '海外 ' + q.date + '；国内 ' + d.date);
    else add('date', '价格日期一致', 'unknown', '日期缺失');

    // 3 贸易术语
    if (BASE_PORT_TERMS.indexOf((q.term || '').toUpperCase()) >= 0) {
      add('term', '海外术语可折算', 'pass', q.term + ' → 可加到 CIF（' + (q.term === 'CIF' ? '已含运费保险' : '需另计运费与保险') + '）');
    } else if ((q.term || '').toUpperCase() === 'FOB') {
      add('term', '海外术语可折算', landing && landing.freight ? 'pass' : 'unknown',
        'FOB 需另计运费：' + (landing && landing.freight ? '已取得运费' : '运费缺失，不可折算'));
    } else {
      add('term', '海外术语可折算', 'fail', '术语缺失或不可识别：' + (q.term || '未填'));
    }

    // 4 国内价税口径
    if (d.tax_included === true) add('tax', '国内价为含税价', 'pass', '含税（增值税），可与"含税净成本"比较');
    else if (d.tax_included === false) add('tax', '国内价为含税价', 'fail', '国内价为不含税，须先换算成含税价');
    else add('tax', '国内价为含税价', 'unknown', '未标注是否含税');

    // 5 交货地点与交货方式（最容易被忽略）
    var dDel = (d.delivery || '').toLowerCase();
    if (/送到|到厂|delivered|dap|ddp/.test(dDel)) {
      add('delivery', '交货方式可比', 'warn', '国内价含送到：进口成本未含同段内陆运输时，价差会偏向进口');
    } else if (/自提|出厂|罐区|库提|ex-?works|ex-tank|fca|port/.test(dDel)) {
      add('delivery', '交货方式可比', 'warn', '国内价为自提/出厂：进口成本须同样只算到罐区/口岸，不能含内陆配送');
    } else {
      add('delivery', '交货方式可比', 'unknown', '交货方式未标注');
    }

    // 6 增值税抵扣条件
    var vr = caseData && caseData.params ? caseData.params.vat_recoverable : undefined;
    if (vr === true) add('vat_rec', '增值税抵扣条件', 'pass', '进口增值税可抵扣，按"含税净成本"比较');
    else if (vr === false) add('vat_rec', '增值税抵扣条件', 'warn', '进口增值税不可抵扣，已计入成本；国内价对应的进项抵扣也需同步核实');
    else add('vat_rec', '增值税抵扣条件', 'unknown', '未提供抵扣条件');

    // 7 数量/包装
    if (d.quantity && q.quantity && d.quantity === q.quantity) add('qty', '交易数量口径', 'pass', d.quantity);
    else if (q.quantity || d.quantity) add('qty', '交易数量口径', 'warn', '海外：' + (q.quantity || '未注') + '；国内：' + (d.quantity || '未注') + '（散装/整船 vs 罐区零单，价格基础可能不同）');
    else add('qty', '交易数量口径', 'unknown', '双方均未标注数量/包装');

    // 8 汇率
    if (landing && landing.fx) add('fx', '汇率为同期值', 'pass', landing.fx.date + ' 中间价 ' + landing.fx.rate + '（精确匹配日期）');
    else add('fx', '汇率为同期值', 'unknown', '缺少当日汇率');

    // 9 运费
    if (landing && landing.freight && !landing.freight.stale && (q.term || '').toUpperCase() !== 'CIF') {
      add('freight', '运费可核验', 'pass', landing.freight.basis + '（' + landing.freight.date + '）');
    } else if (landing && landing.freight && landing.freight.stale) {
      add('freight', '运费可核验', 'warn', '运费日期 ' + landing.freight.date + ' 与价格日期不一致');
    } else if ((q.term || '').toUpperCase() === 'CIF') {
      add('freight', '运费可核验', 'pass', 'CIF 已含运费与保险');
    } else {
      add('freight', '运费可核验', 'fail', '无运费数据');
    }

    var fails = checks.filter(function (c) { return c.status === 'fail'; }).length;
    var unknowns = checks.filter(function (c) { return c.status === 'unknown'; }).length;
    var warns = checks.filter(function (c) { return c.status === 'warn'; }).length;
    var verdict;
    if (fails) verdict = 'blocked';            // 存在硬性不可比项
    else if (unknowns) verdict = 'needs_info';
    else if (warns) verdict = 'comparable_with_caveats';
    else verdict = 'comparable';
    return { checks: checks, verdict: verdict, fails: fails, warns: warns, unknowns: unknowns };
  }

  // ============================================================ 异常阶段
  /**
   * 历史异常点识别：价差绝对值相对滚动中位数的偏离（描述性，不含预测）。
   */
  function anomalyPhases(history, opts) {
    var o = opts || {};
    var win = o.window || 5;
    var thr = o.threshold_pct === undefined ? 25 : o.threshold_pct;
    var pts = history.filter(function (h) { return h.status === 'ok' && isNum(h.spread); });
    var out = [];
    pts.forEach(function (h, i) {
      var lo = Math.max(0, i - win);
      var hi = Math.min(pts.length, i + win + 1);
      var neighbours = pts.slice(lo, hi).filter(function (x) { return x.date !== h.date; }).map(function (x) { return x.spread; });
      if (neighbours.length < 3) return;
      neighbours.sort(function (a, b) { return a - b; });
      var med = neighbours[Math.floor(neighbours.length / 2)];
      var dev = med === 0 ? 0 : (h.spread - med) / Math.abs(med) * 100;
      if (Math.abs(dev) >= thr) {
        out.push({ date: h.date, spread: h.spread, median: med, deviation_pct: dev, direction: dev > 0 ? 'higher' : 'lower' });
      }
    });
    return out;
  }

  // ============================================================ 汇总
  /**
   * 一次性产出 HTML/Excel/校验都需要的结果包。
   */
  function analyze(caseData, opts) {
    var o = opts || {};
    var current = computeLanding(caseData, {});
    var compat = compatibility(caseData, current);
    var sens = sensitivity(caseData, {});
    var hist = buildHistory(caseData, { keepResults: false });
    return {
      asof: get(caseData, 'asof.date'),
      current: current,
      compatibility: compat,
      sensitivity: sens,
      history: hist,
      anomalies: anomalyPhases(hist, o.anomaly),
      contribution: costContribution(current),
      verdict: current.calculable
        ? (compat.verdict === 'blocked' ? 'incomparable' : (current.tier === 'fragile' ? 'fragile' : 'calculable'))
        : 'not_calculable'
    };
  }

  return {
    version: '1.0.0',
    TERMS: TERMS,
    computeLanding: computeLanding,
    taxProfileOn: taxProfileOn,
    fxOnDate: fxOnDate,
    fxRange: fxRange,
    resolveFreight: resolveFreight,
    sensitivity: sensitivity,
    breakeven: breakeven,
    costContribution: costContribution,
    buildHistory: buildHistory,
    compatibility: compatibility,
    anomalyPhases: anomalyPhases,
    analyze: analyze,
    _util: { num: num, round: round, pct: pct, isNum: isNum, get: get, lowerTier: lowerTier, TIERS: TIERS }
  };
});
