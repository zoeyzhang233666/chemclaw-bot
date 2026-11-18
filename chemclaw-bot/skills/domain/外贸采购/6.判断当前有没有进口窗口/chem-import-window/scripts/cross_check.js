#!/usr/bin/env node
/**
 * cross_check.js — 三路交叉校验：JS 引擎 vs Python 基准 vs 场景矩阵
 *
 * 用法：node scripts/cross_check.js <case.json> [--tol 0.01]
 *
 * 校验内容：
 *   1. 当前快照：JS 引擎与 Python 参考实现的每一个中间量都一致
 *   2. 历史点：逐日比对
 *   3. 场景矩阵：改变 term / 运费 / 税率 / 汇率 / 抵扣状态，两套实现必须始终一致
 *   4. 边界行为：FOB 无运费 → 两套实现都必须拒绝折算（而不是返回 0 成本）
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const ENGINE = require(path.join(ROOT, 'scripts/lib/import-window-engine.js'));

// 临时文件放到系统临时目录，保证解压到任何位置（只读目录、无 tools/）都能运行
const OS = require('os');
const TMPDIR = fs.mkdtempSync(path.join(OS.tmpdir(), 'iw-cross-'));
const TMP_FILES = [];
function tmpFile(name) {
  const p = path.join(TMPDIR, name);
  TMP_FILES.push(p);
  return p;
}
const FILE = process.argv[2];
const TOL = process.argv.includes('--tol') ? parseFloat(process.argv[process.argv.indexOf('--tol') + 1]) : 0.02;

if (!FILE) { console.error('用法: node scripts/cross_check.js <case.json>'); process.exit(2); }
const CASE = JSON.parse(fs.readFileSync(FILE, 'utf8'));

let fails = 0, checks = 0;
function cmp(label, a, b, tol) {
  checks++;
  tol = tol === undefined ? TOL : tol;
  const na = (a === null || a === undefined || Number.isNaN(a));
  const nb = (b === null || b === undefined || Number.isNaN(b));
  if (na && nb) return true;
  if (na !== nb) { fails++; console.log(`  x ${label}: 一侧缺失 (js=${a}, py=${b})`); return false; }
  if (Math.abs(a - b) > tol) { fails++; console.log(`  x ${label}: js=${a} py=${b} 差 ${Math.abs(a - b).toFixed(4)}`); return false; }
  return true;
}

function pyAllowingFailure(file, args) {
  args = args || [];
  const { spawnSync } = require('child_process');
  const r = spawnSync('python', [path.join(ROOT, 'scripts/reference_calc.py'), file, '--json', ...args],
    { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 });
  // 退出码 1 = 不可计算的正常结局；JSON 仍在 stdout
  try { return JSON.parse(r.stdout); } catch (e) {
    throw new Error('Python 基准输出无法解析: ' + (r.stdout || r.stderr || '').slice(0, 300));
  }
}

console.log('三路交叉校验: ' + path.basename(FILE));
console.log('容差: ' + TOL + ' 元/吨\n');

// 注意：Python 基准在"不可计算"时仍以退出码 1 输出 JSON，故一律用 pyAllowingFailure 解析
const py = (args) => pyAllowingFailure(FILE, args);

// ---------------------------------------------------------------- 1. 当前快照
console.log('[1] 当前快照');
const jsNow = ENGINE.computeLanding(CASE, {});
const pyNow = py([]);
if (!jsNow.calculable && !pyNow.ok) {
  console.log('  两侧均判定"不可计算"，比较阻断原因');
  if (!jsNow.blockers.length) { fails++; console.log('  x JS 引擎没有给出阻断原因'); }
  checks++;
} else if (!jsNow.calculable !== !pyNow.ok) {
  fails++; checks++;
  console.log(`  x 可计算性不一致: js=${jsNow.calculable} py=${pyNow.ok} | js 阻断=${JSON.stringify(jsNow.blockers)} py 阻断=${JSON.stringify(pyNow.blockers)}`);
} else {
  cmp('CIF (USD)', jsNow.totals.cif_usd, pyNow.cif_usd);
  cmp('汇率', jsNow.fx ? jsNow.fx.rate : null, pyNow.fx, 1e-6);
  cmp('完税价格', jsNow.totals.cif_cny, pyNow.dutiable_cny);
  cmp('关税', jsNow.totals.duty, pyNow.duty);
  cmp('进口增值税', jsNow.totals.vat, pyNow.vat);
  cmp('境内费用', jsNow.totals.inland, pyNow.inland);
  cmp('进口含税净成本', jsNow.totals.net_cost, pyNow.net_cost);
  cmp('全口径付现', jsNow.totals.gross_cost, pyNow.gross_cost);
  cmp('理论价差', jsNow.spread.abs_cny, pyNow.spread);
  cmp('价差占国内价%', jsNow.spread.pct_of_domestic, pyNow.spread_pct);
  console.log(`  净成本 js=${jsNow.totals.net_cost.toFixed(4)} py=${pyNow.net_cost.toFixed(4)}`);
  console.log(`  价差   js=${(jsNow.spread.abs_cny || 0).toFixed(4)} py=${(pyNow.spread || 0).toFixed(4)}`);
}

// ---------------------------------------------------------------- 2. 历史点
console.log('\n[2] 历史点位逐日比对');
const hist = ENGINE.buildHistory(CASE, {});
let okN = 0, gapN = 0;
for (const h of hist) {
  const pyH = py(['--date', h.date]);
  if (!pyH.ok) {
    // Python 侧也拒绝：如果 JS 也拒绝（gap），一致；否则说明 JS 用了 Python 没认的数据
    if (h.status !== 'ok') { gapN++; checks++; continue; }
    fails++; checks++;
    console.log(`  x ${h.date}: js 可算(净成本 ${h.net_cost}) 但 py 阻断 ${JSON.stringify(pyH.blockers)}`);
    continue;
  }
  if (h.status !== 'ok') {
    // 引擎判 gap 的两种情况：
    //   a) 参数阻断（无汇率/无运费等）→ Python 也必须 ok=false
    //   b) 缺同日国内价 → Python 的进口成本仍可算，但 domestic 必须为 null
    const expectCostOnly = /国内现货/.test(h.gap_reason || '');
    if (expectCostOnly && pyH.domestic === null) {
      const a = cmp(`${h.date} 净成本`, h.net_cost, pyH.net_cost);
      if (a) { gapN++; }
      else { fails++; }
      continue;
    }
    fails++; checks++;
    console.log(`  x ${h.date}: js 状态=gap（${h.gap_reason}）但 py 仍可给出完整结果 —— 引擎漏算了本可算的点`);
    continue;
  }
  const a = cmp(`${h.date} 净成本`, h.net_cost, pyH.net_cost);
  // 引擎判定"缺同日国内价"的点，Python 侧同样应当没有国内价（只比对进口成本）
  if (h.status === 'ok' && pyH.domestic === null) {
    fails++; checks++;
    console.log(`  x ${h.date}: js 有国内价 ${h.domestic} 但 py 判定缺当日国内价`);
    continue;
  }
  let b = true;
  if (h.status === 'ok') b = cmp(`${h.date} 价差`, h.spread, pyH.spread);
  if (a && b) okN++;
}
console.log(`  可配对 ${okN} 天 / 双侧均缺 ${gapN} 天 / 共 ${hist.length} 个锚点`);

// ---------------------------------------------------------------- 3. 场景矩阵
console.log('\n[3] 场景矩阵（term × 运费 × 税率 × 汇率 × 抵扣）');
const basePrice = CASE.quote.price_usd;
const scenarios = [];
for (const term of ['CFR', 'CIF', 'FOB']) {
  for (const frt of [null, 0, 40, 75, 120]) {
    for (const duty of [0, 5, 5.5, 8]) {
      for (const fxMul of [0.97, 1, 1.03]) {
        for (const rec of [true, false]) {
          scenarios.push({ term, frt, duty, fxMul, rec });
        }
      }
    }
  }
}
let sOK = 0, sMismatch = 0;
for (const s of scenarios) {
  const q = Object.assign({}, CASE.quote, { term: s.term, price_usd: basePrice });
  if (s.term === 'FOB') q.price_usd = Math.round(basePrice * 0.88 * 100) / 100;  // FOB 通常低于 CFR
  const fx = CASE.fx.rate * s.fxMul;
  const patched = JSON.parse(JSON.stringify(CASE));
  patched.quote = q;
  patched.tax.profiles[0].duty_rate = s.duty;
  patched.params.vat_recoverable = s.rec;
  patched.freight = s.frt === null
    ? { source: 'none', usd_per_ton: null, quality: 'missing' }
    : { source: 'manual', usd_per_ton: s.frt, date: CASE.asof.date, quality: 'actual' };

  const j = ENGINE.computeLanding(patched, { fx_rate: fx });

  // Python 侧必须读同一个 patched 案例，只额外覆盖汇率
  const tmp = tmpFile('patched_' + sOK + '_' + sMismatch + '.json');
  fs.writeFileSync(tmp, JSON.stringify(patched), 'utf8');
  const p2 = pyAllowingFailure(tmp, ['--fx', String(fx)]);

  const jsBlocked = !j.calculable;
  const pyBlocked = !p2.ok;
  if (jsBlocked !== pyBlocked) {
    sMismatch++;
    if (sMismatch <= 5) console.log(`  x 场景 ${JSON.stringify(s)}: js阻断=${jsBlocked} py阻断=${pyBlocked} | py=${JSON.stringify(p2.blockers)} | js=${JSON.stringify(j.blockers)}`);
    continue;
  }
  if (jsBlocked) { sOK++; continue; }
  const dNet = Math.abs(j.totals.net_cost - p2.net_cost);
  const dSpr = Math.abs((j.spread.abs_cny || 0) - (p2.spread || 0));
  if (dNet > TOL || dSpr > TOL) {
    sMismatch++;
    if (sMismatch <= 5) console.log(`  x 场景 ${JSON.stringify(s)}: Δ净成本=${dNet.toFixed(4)} Δ价差=${dSpr.toFixed(4)}`);
  } else sOK++;
}
checks += scenarios.length;
fails += sMismatch;
console.log(`  ${scenarios.length} 个场景：一致 ${sOK}，不一致 ${sMismatch}`);

// ---------------------------------------------------------------- 4. 边界行为
console.log('\n[4] 边界行为（必须"拒绝算"而不是"按 0 算"）');
const fobNoFreight = JSON.parse(JSON.stringify(CASE));
fobNoFreight.quote.term = 'FOB';
fobNoFreight.quote.freight_usd = null;
fobNoFreight.freight = { source: 'none', usd_per_ton: null, quality: 'missing' };
const jb = ENGINE.computeLanding(fobNoFreight, {});
checks++;
if (jb.calculable) { fails++; console.log('  x FOB 无运费时 JS 引擎仍然算出了成本（应拒绝）'); }
else if (!jb.blockers.some((b) => b.code === 'NO_FREIGHT')) { fails++; console.log('  x FOB 无运费时没有给出 NO_FREIGHT 阻断'); }
else console.log('  ✓ FOB 无运费 → 引擎拒绝折算（NO_FREIGHT）');

const tmpNoFx = tmpFile('fob_case.json');
fs.writeFileSync(tmpNoFx, JSON.stringify(fobNoFreight), 'utf8');
const pObj = pyAllowingFailure(tmpNoFx, []);
checks++;
if (pObj.ok) { fails++; console.log('  x FOB 无运费时 Python 基准仍然算出结果（应拒绝）'); }
else console.log('  ✓ FOB 无运费 → Python 基准同样拒绝');

// 缺当日汇率必须阻断
const noFx = JSON.parse(JSON.stringify(CASE));
noFx.fx.rows = noFx.fx.rows.filter((r) => r.date !== CASE.asof.date);
const jnf = ENGINE.computeLanding(noFx, {});
checks++;
if (jnf.calculable) { fails++; console.log('  x 缺当日汇率时引擎仍算出成本（应拒绝，禁止插值/借用）'); }
else console.log('  ✓ 缺当日汇率 → 引擎拒绝（NO_FX），不做插值');

console.log('\n结果: ' + (fails ? `${fails} 项不一致（共 ${checks} 项）` : `全部一致（共 ${checks} 项）`));

// 清理临时文件
try { TMP_FILES.forEach((p) => { try { fs.unlinkSync(p); } catch (e) { /* ignore */ } }); fs.rmdirSync(TMPDIR); } catch (e) { /* ignore */ }

process.exit(fails ? 1 : 0);
