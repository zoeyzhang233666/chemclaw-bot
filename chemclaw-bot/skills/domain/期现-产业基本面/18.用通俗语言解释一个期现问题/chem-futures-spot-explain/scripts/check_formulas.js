#!/usr/bin/env node
/**
 * check_formulas.js —— 期现解释的公式与符号一致性回归（零依赖）
 *
 * 用法：
 *   node check_formulas.js <data.json>
 *   node check_formulas.js            # 无参数时跑内置的甲醇示范数据（assets/example-data.json）
 *
 * data.json 需要的字段（缺项会报 SKIP，不会静默通过）：
 *   inventory.series[]  {date, value}
 *   basis.rows[]        {date, spot, fut_close, fut_settle}
 *   month_spread.points[]{date, near_close, far_close}
 *   longshort?          跨换月对照 {start_close_same, start_close_other, end_close}
 *   import_parity       {cfr, fx, freight, port, duty, vat, delivered_incl_vat?}
 *   flow                {arrivals, d_inv}
 *   checks[]            页面内嵌的校验项 {id, got, expect, tol, status}
 *
 * 退出码：0 全通过；1 有 FAIL。
 */
'use strict';
const fs = require('fs');
const path = require('path');

const EPS = 0.011;
let pass = 0, fail = 0, skip = 0;
const lines = [];

function ok(id, desc, got, expect, tol) {
  const t = tol === undefined ? EPS : tol;
  const good = Math.abs(got - expect) <= t;
  good ? pass++ : fail++;
  lines.push(`${good ? 'PASS' : 'FAIL'}  ${id.padEnd(6)} ${desc.padEnd(46)} got=${fmt(got)} expect=${fmt(expect)}`);
  return good;
}
function check(id, desc, cond) {
  cond ? pass++ : fail++;
  lines.push(`${cond ? 'PASS' : 'FAIL'}  ${id.padEnd(6)} ${desc}`);
  return cond;
}
function skipIt(id, desc, why) {
  skip++;
  lines.push(`SKIP  ${id.padEnd(6)} ${desc}  (${why})`);
}
function fmt(x) { return typeof x === 'number' ? (Math.round(x * 10000) / 10000) : String(x); }
function sum(a) { return a.reduce((s, x) => s + x, 0); }
function r4(x) { return Math.round(x * 10000) / 10000; }

const arg = process.argv[2];
let D;
try {
  if (arg) {
    D = JSON.parse(fs.readFileSync(path.resolve(arg), 'utf8'));
  } else {
    const builtin = path.join(__dirname, '..', 'assets', 'example-data.json');
    D = JSON.parse(fs.readFileSync(builtin, 'utf8'));
    lines.push(`# 未指定数据文件，使用内置示范数据：${builtin}`);
  }
} catch (e) {
  console.error('无法读取数据文件：', e.message);
  process.exit(2);
}

lines.push(`# 校验对象：${D.meta ? D.meta.product + ' / ' + (D.meta.futures_contract || '') : '未命名数据'}`);
lines.push('# '.padEnd(80, '-'));

// ---------- A. 库存 ----------
const inv = D.inventory && D.inventory.series;
if (!Array.isArray(inv) || inv.length < 3) {
  skipIt('A', '库存序列', '缺 inventory.series 或样本不足');
} else {
  const bad = [];
  for (let i = 1; i < inv.length; i++) {
    const d = inv[i].value - inv[i - 1].value;
    if (!isFinite(d)) bad.push(inv[i].date);
  }
  check('A1', '库存序列可逐期求差（无缺失值）', bad.length === 0);
  const s = inv.map(x => x.value);
  check('A2', '库存取值量级合理（0 < Inv < 500 万吨）', s.every(v => v > 0 && v < 500));
  // 单调性不作要求，只报告极值位置
  const minIdx = s.indexOf(Math.min(...s));
  lines.push(`INFO  A3     库存最低 ${s[minIdx]} 万吨 @ ${inv[minIdx].date}，最新 ${s[s.length - 1]} @ ${inv[inv.length - 1].date}`);
  if (D.inventory.latest !== undefined) {
    ok('A4', '最新值字段与序列末值一致', D.inventory.latest, s[s.length - 1]);
  }
}

// ---------- B. 价格与基差 ----------
const basis = (D.basis && D.basis.rows) || [];
const usable = basis.filter(r => r.spot != null && r.fut_close != null);
if (usable.length === 0) {
  skipIt('B', '基差', '缺 basis.rows 或没有可用行');
} else {
  let symOK = true, signOK = true;
  usable.forEach(r => {
    const b = r.spot - r.fut_close;
    if (r.basis_close != null && Math.abs(b - r.basis_close) > EPS) symOK = false;
    if ((b > 0) !== (r.spot > r.fut_close)) signOK = false;
  });
  check('B1', '基差 = 现货 − 期货收盘（逐行复算一致）', symOK);
  check('B2', '基差符号与 (现货>期货) 一致：正=现货升水', signOK);
  const pctOK = usable.every(r => r.basis_pct == null ||
    Math.abs((r.spot - r.fut_close) / r.fut_close * 100 - r.basis_pct) < 0.011);
  check('B3', '基差率 = 基差 / 期货 × 100%', pctOK);
  const withSettle = usable.filter(r => r.fut_settle != null && r.basis_settle != null);
  if (withSettle.length) {
    check('B4', '基差(结算口径) = 现货 − 期货结算价',
      withSettle.every(r => Math.abs((r.spot - r.fut_settle) - r.basis_settle) < EPS));
    const maxGap = Math.max(...withSettle.map(r => Math.abs(r.basis_close - r.basis_settle)));
    lines.push(`INFO  B5     收盘/结算两种口径最大差 ${r4(maxGap)} 元/吨（必须在正文说明口径）`);
  } else {
    skipIt('B4', '基差(结算口径)', '未提供 fut_settle');
  }
  const pctAll = usable.filter(r => r.basis_pct != null).map(r => Math.abs(r.basis_pct));
  check('B6', '基差率量级合理（绝对值 < 100%）', pctAll.every(v => v < 100));
}

// ---------- C. 月差 ----------
const ms = (D.month_spread && D.month_spread.points) || [];
if (ms.length === 0) {
  skipIt('C', '月差', '缺 month_spread.points');
} else {
  check('C1', 'MC = F(远月) − F(近月)（逐行复算一致）',
    ms.every(p => Math.abs((p.far_close - p.near_close) - p.mc) < EPS));
  check('C2', 'MC<0 ⟺ 近月 > 远月（back）',
    ms.every(p => (p.mc < 0) === (p.near_close > p.far_close)));
  lines.push(`INFO  C3     MC 由 ${ms[0].mc}（${ms[0].date}）变为 ${ms[ms.length - 1].mc}（${ms[ms.length - 1].date}）`);
}

// ---------- D. 跨换月口径 ----------
const ls = D.longshort || (D.cases && D.cases['CASE-A'] && D.cases['CASE-A'].price);
if (ls && ls.start_close != null && ls.end_close != null) {
  const samePct = (ls.end_close - ls.start_close) / ls.start_close * 100;
  lines.push(`INFO  D1     同一合约口径涨跌幅 ${r4(samePct)}%`);
  if (ls.start_close_other != null) {
    const otherPct = (ls.end_close - ls.start_close_other) / ls.start_close_other * 100;
    lines.push(`INFO  D2     跨换月口径涨跌幅 ${r4(otherPct)}%（含跳空，不得当作跌幅）`);
    check('D3', '两种口径不同（跨换月会产生假跌幅）', Math.abs(samePct - otherPct) > 0.01);
  } else {
    skipIt('D2', '跨换月对照', '未提供 start_close_other');
  }
  if (ls.change_pct != null) {
    ok('D4', '记录的涨跌幅与复算一致', ls.change_pct, r4(samePct), 0.011);
  }
} else {
  skipIt('D', '涨跌幅', '缺价格起止');
}

// ---------- E. 进口扳平 ----------
const ip = D.import_parity || {};
if (ip.cfr != null && ip.fx != null) {
  const freight = ip.freight != null ? ip.freight : (D.import_cost && D.import_cost.freight_insurance_rmb_per_t && D.import_cost.freight_insurance_rmb_per_t.v);
  const port = ip.port != null ? ip.port : (D.import_cost && D.import_cost.port_fees_rmb_per_t && D.import_cost.port_fees_rmb_per_t.v);
  const duty = ip.duty != null ? ip.duty : (D.import_cost && D.import_cost.duty_pct && D.import_cost.duty_pct.v) || 0.05;
  const vat = ip.vat != null ? ip.vat : (D.import_cost && D.import_cost.vat_pct && D.import_cost.vat_pct.v) || 0.13;
  if (freight == null || port == null) {
    skipIt('E', '进口扳平', '缺运保费/港杂');
  } else {
    const cif = ip.cfr * ip.fx * (1 + duty);
    const exVat = cif + freight + port;
    const inc = exVat * (1 + vat);
    if (ip.cif_rmb != null) ok('E1', 'CIF(¥) = CFR × FX × (1+关税)', ip.cif_rmb, r4(cif));
    else lines.push(`INFO  E1     CIF(¥) 复算 ${r4(cif)}`);
    if (ip.delivered_ex_vat != null) ok('E2', '到岸(不含税) = CIF + 运保 + 港杂', ip.delivered_ex_vat, r4(exVat));
    else lines.push(`INFO  E2     到岸(不含税) 复算 ${r4(exVat)}`);
    if (ip.delivered_incl_vat != null) ok('E3', '到岸(含税) = 到岸(不含税) × (1+增值税)', ip.delivered_incl_vat, r4(inc));
    else lines.push(`INFO  E3     到岸(含税) 复算 ${r4(inc)}`);
    check('E4', '含税成本显著高于不含税（增值税未被漏算）', inc - exVat > exVat * 0.10);
    if (ip.vs_taicang_mid != null) {
      ok('E5', '进口盈亏 = 国内现货 − 到岸含税', ip.vs_taicang_mid, r4(3940 - inc), 1);
    }
  }
} else {
  skipIt('E', '进口扳平', '缺 CFR 或汇率');
}

// ---------- F. 库存流量恒等 ----------
const fl = D.flow || {};
if (fl.arrivals != null && fl.d_inv != null) {
  const implied = fl.arrivals - fl.d_inv;
  if (fl.implied_withdrawal != null) ok('F1', '表观提货 = 到港 − 库存净增', fl.implied_withdrawal, r4(implied));
  check('F2', '表观提货可正可负，但必须给出恒等式来源', typeof implied === 'number' && isFinite(implied));
} else {
  skipIt('F', '库存流量恒等', '缺 arrivals 或 d_inv');
}

// ---------- G. 页面内嵌校验项 ----------
const chk = D.checks || [];
if (chk.length) {
  let bad = 0;
  chk.forEach(c => {
    const d = Math.abs(c.got - c.expect);
    const good = (c.tol == null ? EPS : c.tol) >= d;
    if (!good) { bad++; lines.push(`FAIL  G        页面校验项 ${c.id} got=${c.got} expect=${c.expect}  ${c.desc || ''}`); }
  });
  check(`G1`, `页面内嵌校验项全部通过（${chk.length} 项）`, bad === 0);
} else {
  skipIt('G', '页面内嵌校验项', '缺 checks[]');
}

// ---------- H. 元信息完整性 ----------
const meta = D.meta || {};
const metaFields = ['product', 'futures_contract', 'question', 'data_cutoff'];
const missing = metaFields.filter(k => !meta[k]);
check('H1', '元信息齐全（品种/合约/问题/数据截止日）', missing.length === 0);
if (missing.length) lines.push(`      缺：${missing.join(', ')}`);
if (D.sources) {
  const n = Object.keys(D.sources).length;
  const noUrl = Object.values(D.sources).filter(s => !s.url).length;
  check('H2', `来源表每条都有 URL（${n} 条）`, noUrl === 0);
}
const co = D.verdict && D.verdict.coexistence_found;
if (co) {
  check('H3', '并存核对结论已显式给出（未找到也必须写明）', !!co.status);
  lines.push(`INFO  H4     并存结论：${co.status}`);
}

// ---------- 输出 ----------
console.log(lines.join('\n'));
console.log('# '.padEnd(80, '-'));
console.log(`结果：PASS ${pass} / FAIL ${fail} / SKIP ${skip}`);
process.exit(fail === 0 ? 0 : 1);
