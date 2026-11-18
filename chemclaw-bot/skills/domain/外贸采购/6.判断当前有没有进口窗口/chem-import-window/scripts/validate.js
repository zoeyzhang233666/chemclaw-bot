#!/usr/bin/env node
/**
 * validate.js — 校验 case.json 是否满足数据契约，并做逻辑一致性检查
 *
 * 用法：node scripts/validate.js <case.json> [--quiet]
 *
 * 除了 schema 层的必填/类型，还检查这些"会让结论变错"的逻辑：
 *   · 报价日期与国内价日期的关系（不一致必须被说明）
 *   · 规格是否一致
 *   · 汇率序列是否覆盖报价日期
 *   · FOB 报价是否配了运费（否则不允许出现价差）
 *   · 来源引用是否都存在（source_id 悬空 = 无法核验）
 *   · 禁用词（预测/交易指令）
 *   · 模拟情景是否被明确标注
 *   · 缺口是否给了补法
 */
'use strict';

const fs = require('fs');
const path = require('path');

const FILE = process.argv[2];
const QUIET = process.argv.includes('--quiet');
if (!FILE) { console.error('用法: node scripts/validate.js <case.json>'); process.exit(2); }

const ROOT = path.resolve(__dirname, '..');
const CASE = JSON.parse(fs.readFileSync(FILE, 'utf8'));
const ENGINE = require(path.join(ROOT, 'scripts/lib/import-window-engine.js'));

const errors = [];
const warns = [];
const E = (m) => errors.push(m);
const W = (m) => warns.push(m);

// ---------------------------------------------------------------- schema 最小实现
const SCHEMA = JSON.parse(fs.readFileSync(path.join(ROOT, 'schema/data.schema.json'), 'utf8'));

function typeOf(v) {
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'array';
  if (typeof v === 'number') return Number.isInteger(v) ? 'integer' : 'number';
  return typeof v;
}

function checkType(v, t) {
  const actual = typeOf(v);
  const list = Array.isArray(t) ? t : [t];
  return list.some((x) => x === actual || (x === 'number' && actual === 'integer'));
}

function validate(node, schema, pathStr) {
  if (!schema) return;
  if (schema.type && !checkType(node, schema.type)) {
    E(`${pathStr}: 类型应为 ${[].concat(schema.type).join('|')}，实为 ${typeOf(node)}`);
    return;
  }
  if (schema.const !== undefined && node !== schema.const) E(`${pathStr}: 必须恒为 ${schema.const}`);
  if (schema.enum && !schema.enum.includes(node)) E(`${pathStr}: 必须属于 ${JSON.stringify(schema.enum)}，实为 ${JSON.stringify(node)}`);
  if (schema.pattern && typeof node === 'string' && !new RegExp(schema.pattern).test(node)) {
    E(`${pathStr}: "${node}" 不匹配 ${schema.pattern}`);
  }
  if (typeof node === 'string') {
    if (schema.minLength && node.length < schema.minLength) E(`${pathStr}: 长度 < ${schema.minLength}`);
  }
  if (typeof node === 'number') {
    if (schema.exclusiveMinimum !== undefined && !(node > schema.exclusiveMinimum)) E(`${pathStr}: 必须 > ${schema.exclusiveMinimum}`);
    if (schema.minimum !== undefined && node < schema.minimum) E(`${pathStr}: 必须 >= ${schema.minimum}`);
    if (schema.maximum !== undefined && node > schema.maximum) E(`${pathStr}: 必须 <= ${schema.maximum}`);
  }
  if (schema.type === 'object' || (!schema.type && schema.properties)) {
    if (schema.required) {
      schema.required.forEach((k) => {
        if (node[k] === undefined) E(`${pathStr}: 缺少必填字段 "${k}"`);
      });
    }
    Object.keys(schema.properties || {}).forEach((k) => {
      if (node[k] !== undefined) validate(node[k], schema.properties[k], `${pathStr}.${k}`);
    });
  }
  if (schema.type === 'array' || (Array.isArray(node) && schema.items)) {
    if (schema.minItems && node.length < schema.minItems) E(`${pathStr}: 至少需要 ${schema.minItems} 项，实为 ${node.length}`);
    (node || []).forEach((x, i) => validate(x, schema.items, `${pathStr}[${i}]`));
  }
}

validate(CASE, SCHEMA, '$');

// ---------------------------------------------------------------- 逻辑检查
const SRC_IDS = new Set((CASE.sources || []).map((s) => s.id));
function needSrc(id, where) {
  if (!id) return;
  if (!SRC_IDS.has(id)) E(`${where}: 引用了不存在的来源 "${id}"（无法核验）`);
}
needSrc(CASE.quote && CASE.quote.source_id, 'quote.source_id');
needSrc(CASE.domestic && CASE.domestic.source_id, 'domestic.source_id');
needSrc(CASE.fx && CASE.fx.source_id, 'fx.source_id');
(CASE.quote && CASE.quote.source_secondary_ids || []).forEach((x, i) => needSrc(x, `quote.source_secondary_ids[${i}]`));
((CASE.tax && CASE.tax.profiles) || []).forEach((p, i) => needSrc(p.source_id, `tax.profiles[${i}]`));
((CASE.fx && CASE.fx.rows) || []).forEach((r, i) => needSrc(r.source_id, `fx.rows[${i}]`));
(CASE.events || []).forEach((e, i) => needSrc(e.source_id, `events[${i}].source_id`));
(CASE.freight && CASE.freight.reference_values || []).forEach((r, i) => needSrc(r.source_id, `freight.reference_values[${i}]`));
(CASE.quotes_hist || []).forEach((q, i) => needSrc(q.source_id, `quotes_hist[${i}].source_id`));

// 规格一致
const qSpec = CASE.quote && CASE.quote.spec;
const dSpec = CASE.domestic && CASE.domestic.spec;
if (qSpec && dSpec && qSpec !== dSpec) {
  E(`规格不一致：海外 "${qSpec}" vs 国内 "${dSpec}" —— 不同规格不可直接比价`);
}

// 日期
if (CASE.quote && CASE.domestic && CASE.quote.date !== CASE.domestic.date) {
  W(`价格日期不一致：海外 ${CASE.quote.date} vs 国内 ${CASE.domestic.date}（价差将降级为"近似"）`);
}

// 汇率覆盖
const fxDates = new Set(((CASE.fx && CASE.fx.rows) || []).map((r) => r.date));
if (CASE.quote && fxDates.size && !fxDates.has(CASE.quote.date)) {
  E(`汇率序列不含报价日 ${CASE.quote.date} —— 引擎将拒绝折算（不做插值）`);
}

// 税率版本覆盖
const prof = ((CASE.tax && CASE.tax.profiles) || []).slice().sort((a, b) => (a.effective_from > b.effective_from ? 1 : -1));
if (prof.length && CASE.quote && prof[0].effective_from > CASE.quote.date) {
  E(`最早的税率版本生效于 ${prof[0].effective_from}，晚于报价日 ${CASE.quote.date}`);
}

// FOB 必须有运费
const term = (CASE.quote && CASE.quote.term || '').toUpperCase();
const frt = CASE.freight || {};
const hasFrt = ENGINE._util.num(frt.usd_per_ton) !== null || ENGINE._util.num(CASE.quote && CASE.quote.freight_usd) !== null;
if ((term === 'FOB' || term === 'EXW') && !hasFrt) {
  W(`报价术语为 ${term} 但未配置运费 —— 引擎将拒绝给出价差（这是正确行为，请确认页面已明示"运费缺口"）`);
}

// 缺口规范性
(CASE.gaps || []).forEach((g, i) => {
  if (!g.fix || g.fix.length < 6) E(`gaps[${i}] 缺少可执行的"补法"(fix)`);
  if (!g.impact || g.impact.length < 6) E(`gaps[${i}] 缺少"影响"(impact)`);
});

// 模拟情景必须标注
(CASE.sim_scenarios || []).forEach((s, i) => {
  if (s.is_simulated !== true) E(`sim_scenarios[${i}] 的 is_simulated 必须为 true`);
  if (!/模拟/.test(s.label || '')) W(`sim_scenarios[${i}] 的 label 未含"模拟"字样，可能被误读为真实数据`);
});

// 来源 URL 唯一性 & 摘要质量
const seenUrl = new Map();
(CASE.sources || []).forEach((s) => {
  if (seenUrl.has(s.url)) W(`来源 "${s.id}" 与 "${seenUrl.get(s.url)}" 的 URL 重复`);
  seenUrl.set(s.url, s.id);
  if (!s.excerpt || s.excerpt.replace(/\s/g, '').length < 12) {
    W(`来源 "${s.id}" 的 excerpt 过短，无法体现原文中的数字`);
  }
  if (!/[0-9]/.test(s.excerpt || '')) {
    W(`来源 "${s.id}" 的 excerpt 不含数字，复核时需重新打开原文`);
  }
});

// ---------------------------------------------------------------- 禁用词（预测/指令）
const BANNED = [
  '必涨', '必跌', '将会上涨', '将会下跌', '一定会涨', '一定会跌',
  '建议买入', '建议卖出', '建议采购', '建议囤货', '建议进货', '果断进',
  '目标价', '后市看涨', '后市看跌', '大概率上涨', '大概率下跌',
  '抄底', '抢货', '建仓', '加仓', '止盈', '止损'
];
function scanBanned(obj, p) {
  if (typeof obj === 'string') {
    BANNED.forEach((w) => {
      if (obj.includes(w)) E(`${p}: 出现禁用词「${w}」（不得预测价格或给出交易指令）`);
    });
  } else if (Array.isArray(obj)) obj.forEach((x, i) => scanBanned(x, `${p}[${i}]`));
  else if (obj && typeof obj === 'object') Object.keys(obj).forEach((k) => scanBanned(obj[k], `${p}.${k}`));
}
scanBanned(CASE, '$');

// ---------------------------------------------------------------- 引擎可运行性
let res = null;
try {
  res = ENGINE.analyze(CASE);
  if (res.verdict === 'not_calculable') {
    W('引擎判定为"不可计算"：' + ((res.current.blockers[0] || {}).text || ''));
  } else if (res.verdict === 'incomparable') {
    E('引擎判定为"口径不可比"：' + ((res.compatibility.checks.find((c) => c.status === 'fail') || {}).detail || ''));
  }
} catch (e) {
  E('引擎运行异常: ' + e.message);
}

// 历史一致性：有历史点但全部是 gap 时要说明
if (res && (CASE.quotes_hist || []).length) {
  const okN = res.history.filter((h) => h.status === 'ok').length;
  if (okN === 0) {
    W('所有历史点都无法配对（缺汇率/国内价），历史图将为空 —— 请确认 history_gaps 已逐条说明原因');
  }
}

// ---------------------------------------------------------------- 输出
if (!QUIET) {
  console.log('文件: ' + FILE);
  console.log('案例: ' + CASE.meta.title + '（' + CASE.meta.generated_at + '）');
  if (res) {
    console.log('引擎: verdict=' + res.verdict + ' tier=' + res.current.tier
      + ' net=' + (res.current.totals.net_cost !== null ? Math.round(res.current.totals.net_cost) : '—')
      + ' spread=' + (res.current.spread.abs_cny !== null ? Math.round(res.current.spread.abs_cny) : '—'));
    console.log('可比性: ' + res.compatibility.verdict
      + '（失败 ' + res.compatibility.fails + ' / 保留 ' + res.compatibility.warns + ' / 待确认 ' + res.compatibility.unknowns + '）');
    console.log('历史: ' + res.history.filter((h) => h.status === 'ok').length + ' 个可配对 / 共 ' + res.history.length + ' 个锚点');
    console.log('来源: ' + (CASE.sources || []).length + ' 条，缺口: ' + (CASE.gaps || []).length + ' 项');
  }
  if (warns.length) {
    console.log('\n提示 (' + warns.length + '):');
    warns.forEach((w) => console.log('  ! ' + w));
  }
  if (errors.length) {
    console.log('\n错误 (' + errors.length + '):');
    errors.forEach((e) => console.log('  x ' + e));
  }
  console.log('\n结果: ' + (errors.length ? '校验失败' : '校验通过'));
}
process.exit(errors.length ? 1 : 0);
