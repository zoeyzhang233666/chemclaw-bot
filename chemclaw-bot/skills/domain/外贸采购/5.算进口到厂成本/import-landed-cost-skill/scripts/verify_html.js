// verify_html.js — 用 node 跑 HTML 内嵌引擎，与 Python 引擎结果对账
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'assets', 'import_landed_cost_calculator.html'), 'utf8');
const m = html.match(/const CUSTOMS_INS_RATE[\s\S]*?\n\/\* =+ 演示数据/);
if (!m) { console.error('未找到引擎脚本段'); process.exit(1); }
const src = m[0].replace(/\/\* =+ 演示数据[\s\S]*$/, '');
const engine = new Function(src + '; return {compute, INCOTERMS, CUSTOMS_INS_RATE};')();

const COMMON = {
  incoterm: 'FOB', unitPrice: 640, qty: 62.5, currency: 'USD', priceUnit: 'MT',
  packingIncluded: true, packingExtra: 0, originCharges: null, exportClearance: null,
  freightPerMt: 45, freightTotal: null, insuranceRatePct: 0.55, insuranceAmount: null,
  insuranceIncluded: null, fxMarket: 6.6807, fxCustoms: 6.72,
  tariffMfn: 0.055, tariffApplied: 0.055, antiDumpingRate: 0, vatRate: 0.13, vatDeductible: true,
  portCharges: 600, customsBroker: 500, inspection: 0, warehouse: 3000, inlandTruck: 7812.5, financing: 0,
};
const CASES = {
  FOB: Object.assign({}, COMMON, {incoterm: 'FOB', unitPrice: 640.00, freightPerMt: 45.00, insuranceIncluded: false}),
  CFR: Object.assign({}, COMMON, {incoterm: 'CFR', unitPrice: 685.00, freightPerMt: null, insuranceIncluded: false}),
  CIF: Object.assign({}, COMMON, {incoterm: 'CIF', unitPrice: 685.05, freightPerMt: null, insuranceIncluded: true}),
};

const expected = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'build', 'engine_expected.json'), 'utf8'));

let pass = 0, fail = 0;
const rows = [];
function check(caseName, item, got, exp, tol) {
  const ok = typeof got === 'number' && Math.abs(got - exp) < tol;
  rows.push({case: caseName, item, js: got, py: exp, ok});
  ok ? pass++ : fail++;
}

for (const [name, cfg] of Object.entries(CASES)) {
  const r = engine.compute(cfg);
  const e = expected[name];
  check(name, 'customs_value_cny', r.cvCny, e.customs_value_cny, 0.02);
  check(name, 'duty_cny', r.duty, e.duty_cny, 0.02);
  check(name, 'vat_cash', r.vatCash, e.import_vat_cash_cny, 0.02);
  check(name, 'vat_credit', r.credit, e.import_vat_input_credit_cny, 0.02);
  check(name, 'cif_cny', r.s1, e.cif_equivalent_total_cny, 0.02);
  check(name, 'cash_out', r.cashOut, e.cash_out_total_cny, 0.02);
  check(name, 'final_total', r.finalTot, e.final_cost_total_cny, 0.02);
  check(name, 'per_ton', r.perTon.final, e.landed_cost_per_ton_cny, 0.02);
  const okStatus = r.status === e.status;
  rows.push({case: name, item: 'status', js: r.status, py: e.status, ok: okStatus});
  okStatus ? pass++ : fail++;
}

// 空白安全：清空海关汇率 → 必须待补全，且不得静默按市场汇率
const noFx = engine.compute(Object.assign({}, CASES.FOB, {fxCustoms: null}));
const gapOk = noFx.status === '待补全' && noFx.cvCny === null && noFx.perTon.final === null;
rows.push({case: 'FOB', item: '清空海关汇率→待补全', js: noFx.status, py: '待补全', ok: gapOk});
gapOk ? pass++ : fail++;

// 不可抵扣 → 成本更高
const nd = engine.compute(Object.assign({}, CASES.FOB, {vatDeductible: false}));
const base = engine.compute(CASES.FOB);
const ndOk = nd.perTon.final > base.perTon.final &&
             Math.abs((nd.perTon.final - base.perTon.final) - base.vatCash / base.qty) < 0.02;
rows.push({case: 'FOB', item: '不可抵扣→成本+增值税全额', js: nd.perTon.final, py: base.perTon.final + base.vatCash/base.qty, ok: ndOk});
ndOk ? pass++ : fail++;

// 三口径一致性
const f = engine.compute(CASES.FOB).perTon.final;
const cf = engine.compute(CASES.CFR).perTon.final;
const ci = engine.compute(CASES.CIF).perTon.final;
const same = Math.abs(f - cf) < 0.02;
rows.push({case: '一致性', item: 'FOB 与 CFR 到厂成本相同', js: cf, py: f, ok: same});
same ? pass++ : fail++;

console.log(`HTML 引擎对账：${pass + fail} 项，通过 ${pass}，失败 ${fail}`);
rows.filter(r => !r.ok).forEach(r => console.log('  ✗', JSON.stringify(r)));
fs.writeFileSync(path.join(__dirname, '..', 'build', 'html_reconciliation.json'),
  JSON.stringify({pass, fail, rows}, null, 2));
process.exit(fail ? 1 : 0);
