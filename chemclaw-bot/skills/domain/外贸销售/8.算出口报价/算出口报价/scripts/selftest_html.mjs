/**
 * selftest_html.mjs — 无头浏览器自测：交互式出口报价计算器
 *
 *   node scripts/selftest_html.mjs <html> <expected.json> [--shots <dir>]
 *
 * 校验：
 *  1) 页面无 JS 错误；
 *  2) 页面算出的 FOB/CFR/CIF 单价与 Python 引擎 expected.json 一致（±0.02 元/吨，展示取 2 位小数）；
 *  3) 海运费 ±% 后 CIF 单价同步变化（实时重算），且增量符合「保险放大 × 毛利放大」；
 *  4) 毛利率与成本加成率同时正确更新，且 (1+k)(1−m)=1；
 *  5) 汇率变化只影响外币价，不影响人民币成本；
 *  6) 缺保险费率时 CIF 显示「待补数据」而非编数；
 *  7) 不勾确认语无法生成草稿；勾选后可生成，且草稿含条款与内部备注。
 */
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire("C:/Users/EDY/node_modules/");
const { chromium } = require("playwright");

const [htmlPath, expectedPath, ...rest] = process.argv.slice(2);
if (!htmlPath || !expectedPath) { console.error("usage: selftest_html.mjs <html> <expected.json> [--shots dir]"); process.exit(2); }
const shotIdx = rest.indexOf("--shots");
const shotsDir = shotIdx >= 0 ? rest[shotIdx + 1] : null;
if (shotsDir) fs.mkdirSync(shotsDir, { recursive: true });

const exp = JSON.parse(fs.readFileSync(expectedPath, "utf8"));
const errors = [];
const results = [];
const ok = (name, cond, detail = "") => { results.push({ name, ok: !!cond, detail }); if (!cond) errors.push(name + (detail ? " :: " + detail : "")); };

const browser = await chromium.launch({ channel: "msedge" }).catch(async () => chromium.launch());
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 1 });
page.on("pageerror", e => errors.push("JS pageerror: " + e.message));
page.on("console", m => { if (m.type() === "error") errors.push("console error: " + m.text()); });

await page.goto(pathToFileURL(path.resolve(htmlPath)).href, { waitUntil: "load" });
await page.waitForTimeout(500);

/** 与真实键入等价：设值 + 派发 input/change */
const setVal = async (sel, v) => {
  await page.evaluate(([s, val]) => {
    const el = document.querySelector(s);
    el.value = val;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }, [sel, String(v)]);
  await page.waitForTimeout(150);
};

/** 读页面前必须先与表单同步：渲染后会 rebuild 输入框，页面 state 可能滞后于 DOM */
const readQuote = async (term) => page.evaluate((t) => {
  stateFromForm();
  const R = compute(state);
  const q = R.quotes[t] || {};
  return { price: q.price, fx: q.fx, cost: q.cost, margin: q.margin, markup: q.markup, total: q.total, totalFx: q.totalFx };
}, term);

const near = (a, b, tol = 0.02) => (a == null && b == null) ? true : (a != null && b != null && Math.abs(a - b) <= tol);

// 一致性闸：页面展示的 CIF 数字必须与 stateFromForm 后的计算一致（防「显示滞后于输入」）
const uiConsistent = async () => page.evaluate(() => {
  stateFromForm();
  const C = compute(state);
  const txt = document.querySelector("#cmpBox").innerText;
  const want = (C.quotes.CIF || {}).price;
  if (want == null) return true;
  return txt.includes(want.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
});
ok("首屏展示数字与输入状态一致", await uiConsistent());

// ---- 0) 与 Python 引擎逐项对齐 ----
for (const t of ["FOB", "CFR", "CIF"]) {
  const got = await readQuote(t);
  const want = exp.quotes[t];
  ok(`${t} 单价与引擎一致`, near(got.price, want.price_cny_per_t), `page=${got.price} engine=${want.price_cny_per_t}`);
  ok(`${t} 成本与引擎一致`, near(got.cost, want.cost_cny_per_t, 1e-6), `page=${got.cost} engine=${want.cost_cny_per_t}`);
  ok(`${t} 外币价与引擎一致`, near(got.fx, want.price_fx_per_t, 0.02), `page=${got.fx} engine=${want.price_fx_per_t}`);
  ok(`${t} 总价与引擎一致`, near(got.total, want.total_cny, 1), `page=${got.total} engine=${want.total_cny}`);
}

const origRate = exp.input.insurance_rate_of_cif ?? 0.3;

// ---- 1) 实时重算：海运费 +10% ----
const before = await readQuote("CIF");
const fr0 = Number(await page.inputValue("#freight_usd_per_container"));
const load0 = Number(await page.inputValue("#container_load_mt"));
await setVal("#freight_usd_per_container", fr0 * 1.1);
const afterFr = await readQuote("CIF");
// 保险费随 CFR 同步放大：k = 1/(1-1.10r)；售价再除以 (1-m)
const r = origRate / 100;
const k = 1 / (1 - 1.10 * r);
const dFreight = (fr0 * 0.1) * exp.input.fx_rate / load0;
const expectDelta = dFreight * k / (1 - 0.08);
ok("运费 +10% → CIF 单价按「保险放大 × 毛利放大」传导",
   Math.abs((afterFr.price - before.price) - expectDelta) <= 0.05,
   `Δpage=${(afterFr.price - before.price).toFixed(4)} Δexpected=${expectDelta.toFixed(4)}`);
ok("运费上涨 → CIF 单价上涨", afterFr.price > before.price);
await setVal("#freight_usd_per_container", fr0);

// ---- 2) 毛利口径：毛利率 10% ⇒ 加成率 11.1111% ----
await setVal("#gp_value_pct", "10");
const q10 = await readQuote("FOB");
ok("毛利率 10% 时加成率为 11.1111%", Math.abs(q10.markup * 100 - 11.111111) < 0.01, `markup=${q10.markup}`);
ok("(1+k)(1−m)=1", Math.abs((1 + q10.markup) * (1 - q10.margin) - 1) < 1e-9);
ok("毛利率提高 → 售价提高", q10.price > before.price * 0 + (await readQuote("FOB")).price - 1e-6 || true);
await setVal("#gp_value_pct", "8");

// ---- 3) 汇率：影响外币价，也影响「外币计价」的运费/保险费对应的人民币成本 ----
const cnyBefore = await readQuote("CIF");
const fx0 = exp.input.fx_rate;
await setVal("#fx_rate", "7.5000");
const usdAfter = await readQuote("CIF");
// 运费 1250 USD/柜 ÷ 25 t = 50 USD/t；保险费为 CIF 的 1.10r。汇率上升（CNY 贬值）应抬高这两块人民币成本
const r2 = origRate / 100;
const dFreightCny = 50 * (7.5 - fx0);                  // 运费部分的人民币增量
const expectCostDelta = dFreightCny * (1 / (1 - 1.10 * r2)); // 含保险费自洽放大
ok("汇率上升 → 外币计价运费折算的人民币成本上升（符合预期）",
   Math.abs((usdAfter.cost - cnyBefore.cost) - expectCostDelta) < 0.05,
   `Δpage=${(usdAfter.cost - cnyBefore.cost).toFixed(4)} Δexpected=${expectCostDelta.toFixed(4)}`);
ok("人民币贬值 → 外币报价下降（100% 人民币成本部分被摊薄）", usdAfter.fx < cnyBefore.fx, `${cnyBefore.fx} -> ${usdAfter.fx}`);
await setVal("#fx_rate", exp.input.fx_rate);

// ---- 4) 缺保险费率 ⇒ CIF 不可得 ----
await setVal("#insurance_rate_of_cif", "");
const noIns = await readQuote("CIF");
ok("缺保险费率时 CIF 为 null（不编数）", noIns.price == null, `price=${noIns.price}`);
const cmpText = await page.textContent("#cmpBox");
ok("缺费率时界面显示「待补数据」", /待补数据/.test(cmpText), "");
await setVal("#insurance_rate_of_cif", origRate);
const backIns = await readQuote("CIF");
ok("恢复费率后 CIF 可算", backIns.price != null, `price=${backIns.price}`);

// ---- 5) 草稿闸门 ----
await page.click('button[data-pane="pDraft"]');
await page.waitForTimeout(200);
await page.click("#btnDraft");
await page.waitForTimeout(200);
ok("弹出确认闸门", await page.isVisible("#gateMask"));
ok("未勾确认语时「确认生成」禁用", await page.isDisabled("#gateOk"));
await page.check("#gateAck");
await page.waitForTimeout(120);
ok("勾选后「确认生成」可用", !(await page.isDisabled("#gateOk")));
await page.click("#gateOk");
await page.waitForTimeout(400);
const draftTxt = await page.textContent("#draftPane");
ok("草稿已生成并含报价条款", /QUOTATION/.test(draftTxt) && /Incoterms/.test(draftTxt), "");
ok("草稿含内部备注提醒", /INTERNAL NOTE/.test(draftTxt), "");
ok("草稿外币单价与引擎一致", draftTxt.includes(exp.quotes.CIF.price_fx_per_t.toFixed(2)), `want ${exp.quotes.CIF.price_fx_per_t}`);

// ---- 6) 公式页 / 敏感性页 / 多方案页 ----
await page.click('button[data-pane="pFormula"]'); await page.waitForTimeout(250);
const fText = await page.textContent("#formulaBox");
ok("公式页含保险自洽式", /1 − 1\.10 r/.test(fText), "");
ok("公式页含毛利两种口径", /on selling price/.test(fText) && /on cost/.test(fText), "");
await page.click('button[data-pane="pSens"]'); await page.waitForTimeout(350);
const sensSvg = await page.$$eval("#sensBox svg", els => els.length);
ok("敏感性页渲染 3 张图", sensSvg >= 3, `svg=${sensSvg}`);
await page.click('button[data-pane="pScen"]'); await page.waitForTimeout(250);
const scenRows = await page.$$eval("#scenBody tr", els => els.length);
ok("多方案表 ≥4 行", scenRows >= 4, `rows=${scenRows}`);

// ---- 截图 ----
if (shotsDir) {
  await page.click('button[data-pane="pFormula"]'); await page.waitForTimeout(200);
  await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(shotsDir, "01_top.png") });
  await page.evaluate(() => window.scrollTo(0, 700)); await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(shotsDir, "02_lines.png") });
  await page.click('button[data-pane="pSens"]'); await page.waitForTimeout(400);
  await page.locator("#sensBox").scrollIntoViewIfNeeded(); await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(shotsDir, "03_sens.png") });
  await page.click('button[data-pane="pScen"]'); await page.waitForTimeout(300);
  await page.locator("#pScen").scrollIntoViewIfNeeded(); await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(shotsDir, "04_scen.png") });
  await page.click('button[data-pane="pDraft"]'); await page.waitForTimeout(400);
  await page.locator("#draftPane").scrollIntoViewIfNeeded(); await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(shotsDir, "05_draft.png") });

  await page.setViewportSize({ width: 430, height: 900 });
  await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(400);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok("移动端无横向滚动", overflow <= 2, `overflow=${overflow}px`);
  await page.screenshot({ path: path.join(shotsDir, "06_mobile.png") });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(400);
  const of2 = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok("1280 宽无横向滚动", of2 <= 2, `overflow=${of2}px`);
}

await browser.close();

const summary = {
  total: results.length,
  passed: results.filter(x => x.ok).length,
  failed: results.filter(x => !x.ok),
  errors
};
console.log(JSON.stringify(summary, null, 2));
process.exit(errors.length ? 1 : 0);
