'use strict';
/**
 * model.cjs —— research.json → 计算模型输入（JSON 可直接喂给浏览器里的 geo.js）
 *
 * 本文件是「数据契约」与「计算引擎」之间的唯一适配层。
 * 浏览器端 index.html 里的 <script type="application/json" id="model-data">
 * 就是本函数输出的 model（再加上 defaultParams，便于用户实时改参数）。
 */

const G = require('./geo.cjs');

function pct(v) { return v === null || v === undefined ? null : Math.round(v * 1000) / 10; }

/** 把一条铁路/水路/公路报价换算到「元/吨」 */
function toPerTon(value, unit, density) {
  if (!Number.isFinite(value)) return null;
  switch (unit) {
    case '元/吨': return value;
    case '元/千克': return value * 1000;
    case '元/公斤': return value * 1000;
    case '元/立方米':
      if (!Number.isFinite(density) || density <= 0) return null;
      return value * density; // 密度 t/m³ → 每 m³ 的重量
    case '元/袋': return null; // 需另给每袋净重，强制走 quote.package_weight
    default: return null;
  }
}

/** 含税 ↔ 不含税 */
function taxAdjust(v, from, to, rate) {
  if (v === null) return null;
  if (from === to) return v;
  if (from === '含税' && to === '不含税') return v / (1 + rate);
  if (from === '不含税' && to === '含税') return v * (1 + rate);
  return null;
}

/**
 * @param {object} doc research.json
 * @param {object} opts { defaultParams: COST_PARAMS }
 * @returns {object} model
 */
function buildModel(doc, opts) {
  const o = opts || {};
  const defaultParams = Object.assign({}, G.DEFAULTS.cost, doc.cost_params || {}, o.defaultParams || {});
  // 区分「留空」与「填 0」：留空一律转成 null，浏览器端才能显示"待填"
  const toNumOrNull = (v) => {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  defaultParams.qty = toNumOrNull(defaultParams.qty) === null ? 100 : Number(defaultParams.qty);
  ['loadingUnit', 'unloadingUnit', 'inspectionUnit'].forEach((k) => { defaultParams[k] = toNumOrNull(defaultParams[k]); });

  const density = parseFloat((doc.product && doc.product.density) || '1.0') || 1.0;
  const goodsVat = (doc.product && doc.product.tax && doc.product.tax.goods_vat) || 0.13;

  // ---- 价格：按 quote 与 region 关联 ----
  const quotes = {};
  (doc.quotes || []).forEach((q) => {
    const unit = q.common_quote_unit || '元/吨';
    const v = q.converted != null ? q.converted : q.price;
    const perTon = Number.isFinite(Number(v)) ? toPerTon(Number(v), unit, density) : null;
    const basisTax = q.tax_included === true ? '含税' : (q.tax_included === false ? '不含税' : null);
    const exTax = basisTax ? taxAdjust(perTon, basisTax, '不含税', goodsVat) : null;
    quotes[q.id] = Object.assign({}, q, {
      unit,
      per_ton: perTon,
      ex_tax_per_ton: exTax,
      basis_tax: basisTax,
      comparable: q.comparable !== false,
    });
  });

  // ---- 线路 ----
  const routes = (doc.routes || []).map((r) => {
    const dist = G.routeDistance(r);
    const clean = Object.assign({}, r, {
      distance: dist,
      freight_unit: toNumOrNull(r.freight_unit),
      freight_total: toNumOrNull(r.freight_total),
      loading_total: toNumOrNull(r.loading_total),
      unloading_total: toNumOrNull(r.unloading_total),
      inspection_total: toNumOrNull(r.inspection_total),
      other_total: toNumOrNull(r.other_total) || 0,
    });
    // 多段加成线路：如果给了 freight_lines，就用分段求和
    if (Array.isArray(r.freight_lines) && r.freight_lines.length) {
      clean.freight_lines = r.freight_lines.map((l) => Object.assign({}, l, {
        freight_unit: toNumOrNull(l.freight_unit),
        freight_total: toNumOrNull(l.freight_total),
        km: toNumOrNull(l.km),
      }));
    }
    return clean;
  });

  // ---- 区域 ----
  const regions = (doc.regions || []).filter((x) => x.include !== false).map((rg) => {
    const q = quotes[rg.quote_id] || null;
    const rt = routes.find((x) => x.id === rg.route_id) || null;
    return {
      id: rg.id,
      name: rg.name,
      label: rg.label || rg.name,
      market: rg.market || '',
      producers: rg.producers || [],
      route_id: rg.route_id || null,
      origin_city: rt ? rt.origin_city : null,
      dest_city: rt ? rt.dest_city : null,
      price: q ? {
        value: q.price,
        per_ton: q.per_ton,
        ex_tax_per_ton: q.ex_tax_per_ton,
        unit: q.unit,
        grade: q.grade,
        spec: q.spec,
        date: q.date,
        source_id: q.source_id,
        delivery_basis: q.delivery_basis,
        tax_included: q.tax_included,
        price_low: q.price_low,
        price_high: q.price_high,
        evidence: q.evidence,
        verify: q.verify || q.verification || '',
        comparable: q.comparable,
        comparable_note: q.comparable_note || '',
      } : null,
      quote_id: rg.quote_id,
    };
  });

  // ---- 历史（区域价差区间） ----
  const history = { available: false, series: [], regional_spread: [], monthly: [] };
  if (doc.history) {
    history.span = doc.history.span || '';
    history.series = (doc.history.series || []).map((s) => Object.assign({}, s));
    history.series_note = doc.history.series_note || '';
    history.regional_spread = (doc.history.regional_spread || []).slice();
    history.price_change_window = doc.history.price_change_window || null;
    history.available = history.series.length > 0 || history.regional_spread.length > 0;
  }
  // 由 regional_spread 自动算每个日期的价差（区域 - 基准区域）
  if (history.regional_spread.length) {
    const byDate = {};
    history.regional_spread.forEach((p) => {
      byDate[p.date] = byDate[p.date] || [];
      byDate[p.date].push(p);
    });
    const refName = (regions.find((r) => r.id === doc.benchmark_region_id) || regions[0] || {}).name;
    history.spreads = Object.keys(byDate).sort().map((d) => {
      const pts = byDate[d];
      const get = (key) => pts.find((p) => p.region_key === key) || null;
      const ref = (doc.benchmark_region_id && (pts.find((p) => p.region_key === refName) || null)) || null;
      const mid = (p) => (p ? (p.heavy_low + p.heavy_high) / 2 : null);
      const rows = {};
      regions.forEach((r) => {
        const p = get(r.name) || get(r.id);
        if (!p) { rows[r.id] = null; return; }
        const m = mid(p);
        rows[r.id] = {
          low: p.heavy_low, high: p.heavy_high, mid: m,
          region_note: p.region_note || '',
          source_id: p.source_id,
          spread_vs_ref_mid: ref && m !== null ? Math.round(m - mid(ref)) : null,
          spread_vs_ref_low: ref ? p.heavy_low - ref.heavy_low : null,
          spread_vs_ref_high: ref ? p.heavy_high - ref.heavy_high : null,
        };
      });
      return { date: d, rows, ref_region: refName };
    });
  }

  // ---- 假设 & 缺口 ----
  const gaps = (doc.gaps || []).map((g) => Object.assign({ severity: 'warn' }, g));
  const assumptions = doc.assumptions || [];

  // ---- 汇总统计（供首屏卡片和 HTML 文案用） ----
  const priced = regions.filter((r) => r.price && r.price.per_ton !== null);
  const stats = {
    region_count: regions.length,
    priced_count: priced.length,
    price_low: priced.length ? Math.min(...priced.map((r) => r.price.per_ton)) : null,
    price_high: priced.length ? Math.max(...priced.map((r) => r.price.per_ton)) : null,
    min_distance: routes.filter((r) => r.distance.ok).length ? Math.min(...routes.filter((r) => r.distance.ok).map((r) => r.distance.km)) : null,
    max_distance: routes.filter((r) => r.distance.ok).length ? Math.max(...routes.filter((r) => r.distance.ok).map((r) => r.distance.km_high || r.distance.km)) : null,
    freight_filled: routes.filter((r) => r.freight_unit !== null || r.freight_total !== null).length,
    route_count: routes.length,
    blocker_count: gaps.filter((g) => g.severity === 'blocker').length,
  };
  if (stats.price_low !== null) {
    stats.price_spread = stats.price_high - stats.price_low;
    stats.price_spread_pct = pct(stats.price_spread / stats.price_low);
  }
  // 裸价最低的区域名
  if (priced.length) {
    const low = priced.reduce((a, b) => (b.price.per_ton < a.price.per_ton ? b : a));
    stats.lowest_price_region = low.name;
    stats.lowest_price_region_id = low.id;
  }

  const sources = {};
  (doc.sources || []).forEach((s) => { sources[s.id] = s; });

  return {
    meta: doc.meta,
    request: doc.request,
    product: doc.product,
    basis: doc.basis,
    normalization: doc.normalization,
    quotes,
    sources,
    regions,
    routes,
    destination: doc.destination,
    benchmark_region_id: doc.benchmark_region_id,
    history,
    gaps,
    assumptions,
    gap_rules: doc.gap_rules || [],
    stats,
    defaultParams,
    goodsVat,
  };
}

module.exports = { buildModel, toPerTon, taxAdjust };
