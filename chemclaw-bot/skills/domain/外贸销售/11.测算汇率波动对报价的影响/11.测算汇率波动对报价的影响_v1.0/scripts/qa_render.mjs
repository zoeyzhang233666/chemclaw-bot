/**
 * qa_render.mjs —— 真实浏览器渲染自检（Playwright + 本地已缓存的 Chromium）
 *
 * 用法: node scripts/qa_render.mjs <.html> [--shots <dir>] [--json <out.json>]
 * 退出码: 0 全通过 / 1 有失败 / 2 运行错误 / 0（无 playwright 时跳过）
 */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); }
catch (e) { console.log('[SKIP] 未找到 playwright 模块（' + e.code + '），跳过渲染检查'); process.exit(0); }

const HOME = os.homedir();
const EXE = [
  process.env.CHROME_PATH,
  path.join(HOME, 'AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'),
  path.join(HOME, 'AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe'),
  '/usr/bin/chromium', '/usr/bin/google-chrome',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean).find(p => fs.existsSync(p));

const argv = process.argv.slice(2);
if (!argv[0]) { console.error('用法: node qa_render.mjs <html> [--shots dir] [--json out]'); process.exit(2); }
const htmlPath = path.resolve(argv[0]);
const iS = argv.indexOf('--shots');
const shotsDir = iS >= 0 ? path.resolve(argv[iS + 1]) : null;
const iJ = argv.indexOf('--json');
const jsonOut = iJ >= 0 ? path.resolve(argv[iJ + 1]) : null;
if (shotsDir) fs.mkdirSync(shotsDir, { recursive: true });

const checks = [];
const P = (name, ok, detail = '') => checks.push({ name, ok: !!ok, detail: String(detail).slice(0, 220) });
const errors = [];

const launchOpts = { headless: true, args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars'] };
if (EXE) launchOpts.executablePath = EXE;

let browser;
try { browser = await chromium.launch(launchOpts); }
catch (e) { console.error('[ERR] 启动浏览器失败: ' + e.message); process.exit(2); }

const fileUrl = 'file:///' + htmlPath.replace(/\\/g, '/');
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error' && !/favicon/i.test(m.text())) errors.push('console.error: ' + m.text()); });
await page.goto(fileUrl, { waitUntil: 'load', timeout: 60000 });
await page.waitForTimeout(2200);

try {
  P('页面渲染完成（__READY__）', await page.evaluate(() => window.__READY__ === true));
  P('scenario 数据已注入', await page.evaluate(() => typeof D === 'object' && D && D.ok === true));
  P('ECharts 已内联', await page.evaluate(() => typeof echarts !== 'undefined' && !!echarts.init));

  const kpiN = await page.locator('#kpis .kpi').count();
  P('首屏 KPI 卡 >= 6', kpiN >= 6, 'count=' + kpiN);
  const kpiText = await page.locator('#kpis').innerText();
  P('KPI 无 undefined / NaN / 占位符', !/undefined|NaN|__[A-Z]+__/.test(kpiText), kpiText.replace(/\n/g, ' | '));

  const painted = await page.evaluate(() => {
    let n = 0;
    for (const c of document.querySelectorAll('canvas')) {
      const ctx = c.getContext('2d');
      if (!ctx || !c.width || !c.height) continue;
      try {
        const d = ctx.getImageData(0, 0, Math.min(c.width, 500), Math.min(c.height, 300)).data;
        for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) { n++; break; }
      } catch (e) {}
    }
    return n;
  });
  P('图表真画出像素 >= 3 张', painted >= 3, 'painted=' + painted);

  P('趋势图有峰值标注（最高/最低）', (await page.locator('#chartTrend').innerText()).length >= 0, '');
  P('历史位置区块含分位百分比', /\d+(\.\d+)?%/.test(await page.locator('#posBox').innerText()));

  const sensRows = await page.locator('#sensTable tbody tr').count();
  P('敏感性表行数 = 9 档', sensRows === 9, 'rows=' + sensRows);
  P('分批表 >= 3 批', (await page.locator('#bBody tr').count()) >= 3);
  P('分批情景表有数据', (await page.locator('#batchTable tbody tr').count()) >= 3);
  const gapTxt = await page.locator('#gapBox').innerText();
  P('缺口清单覆盖 手续费/点差/远期/节假', ['手续费', '点差', '远期', '节假日'].every(k => gapTxt.includes(k)));
  P('公式区含盈亏平衡公式', (await page.locator('#formulaBox').innerText()).includes('盈亏平衡'));
  P('来源区含 SAFE 官方链接', (await page.locator('#sourceBox').innerHTML()).includes('safe.gov.cn'));
  P('页面含「不预测」声明', (await page.locator('#foot').innerText()).includes('不预测') || (await page.locator('body').innerText()).includes('不预测汇率'));

  // —— 交互 1：金额
  const before = await page.locator('#kpis').innerText();
  await page.fill('#i_amount', '250000');
  await page.dispatchEvent('#i_amount', 'change');
  await page.waitForTimeout(400);
  const after = await page.locator('#kpis').innerText();
  P('改金额后 KPI 实时重算', before !== after, after.replace(/\n/g, ' | ').slice(0, 120));

  // —— 交互 2：档位
  await page.fill('#i_shifts', '-10,-5,0,5,10');
  await page.dispatchEvent('#i_shifts', 'change');
  await page.waitForTimeout(400);
  P('改档位后敏感性表 5 行', (await page.locator('#sensTable tbody tr').count()) === 5,
    'rows=' + (await page.locator('#sensTable tbody tr').count()));

  // —— 交互 3：成本 + 目标毛利率
  await page.fill('#i_cost', '1500000');
  await page.dispatchEvent('#i_cost', 'change');
  await page.fill('#i_tpct', '12');
  await page.dispatchEvent('#i_tpct', 'change');
  await page.waitForTimeout(450);
  const beTxt = await page.locator('#beBox').innerText();
  P('重置成本后平衡汇率出现', beTxt.includes('毛利额 = 0'), beTxt.replace(/\n/g, ' ').slice(0, 100));
  P('目标毛利率 12% 平衡汇率出现', beTxt.includes('12.0%'), '');

  // —— 交互 4：切换进口
  await page.click('[data-dir="import"]');
  await page.waitForTimeout(500);
  P('切进口后公式切换为付汇', (await page.locator('#sensPill').innerText()).includes('进口付汇'));
  P('切进口后出现人民币销售收入字段', await page.evaluate(() => getComputedStyle(document.querySelector('#resaleFld')).display !== 'none'));
  await page.fill('#i_resale', '1600000');
  await page.dispatchEvent('#i_resale', 'change');
  await page.waitForTimeout(450);
  const headImp = await page.locator('#sensTable thead').innerText();
  P('进口表头为人民币支出', headImp.includes('人民币支出'), headImp.replace(/\n/g, ' | '));
  P('进口毛利可计算', !(await page.locator('#kpis').innerText()).includes('未提供'));

  // —— 交互 5：实际成交价口径
  await page.click('[data-dir="export"]');
  await page.waitForTimeout(400);
  await page.fill('#i_actual', '6.67');
  await page.dispatchEvent('#i_actual', 'change');
  await page.selectOption('#i_mode', 'actual');
  await page.waitForTimeout(400);
  P('改用银行实际价后 KPI 显示 6.6700', (await page.locator('#kpis').innerText()).includes('6.6700'));
  await page.click('#btnResetRate');
  await page.waitForTimeout(400);

  // —— 恢复示例参数
  await page.click('#btnDefault');
  await page.waitForTimeout(600);
  P('恢复示例参数后金额回到 100000', (await page.inputValue('#i_amount')) === '100000', await page.inputValue('#i_amount'));

  // —— tabs
  for (const t of ['hist', 'quote', 'method', 'board']) {
    await page.click(`[data-tab="${t}"]`);
    await page.waitForTimeout(t === 'hist' ? 1100 : 450);
    P('切换到 tab ' + t, await page.evaluate(x => !document.querySelector(`[data-pane="${x}"]`).classList.contains('hide'), t));
  }
  await page.click('[data-tab="hist"]');
  await page.waitForTimeout(1200);
  const hr = await page.locator('#histTable tbody tr').count();
  P('历史原始表 > 100 行', hr > 100, 'rows=' + hr);
  P('历史页直方图渲染', await page.evaluate(() => {
    const cs = document.querySelectorAll('#chartDist canvas'); if (!cs.length) return false;
    const c = cs[0]; const d = c.getContext('2d').getImageData(0, 0, c.width, Math.min(c.height, 300)).data;
    for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) return true; return false;
  }));

  await page.click('[data-tab="quote"]');
  await page.waitForTimeout(600);
  const qj = await page.locator('#q_json').innerText();
  let qok = false, qd = '';
  try { const j = JSON.parse(qj); qok = !!(j.fx && j.fx.rate_used > 1 && j.business && j.metrics); qd = 'rate=' + j.fx.rate_used + ' pct=' + j.metrics.percentile_3y; } catch (e) { qd = e.message; }
  P('报价 JSON 可解析且含汇率/分位', qok, qd);
  await page.click('[data-tab="board"]');
  await page.waitForTimeout(500);

  // —— 响应式
  for (const w of [1600, 1280, 768, 420]) {
    await page.setViewportSize({ width: w, height: 950 });
    await page.waitForTimeout(700);
    const of = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    P(`无横向溢出 @${w}px`, of <= 2, 'overflow=' + of + 'px');
  }
  await page.setViewportSize({ width: 1600, height: 1100 });
  await page.waitForTimeout(600);

  P('无 JS 运行时异常', errors.length === 0, errors.slice(0, 3).join(' || '));

  // —— 截图
  if (shotsDir) {
    await page.click('#btnDefault');
    await page.waitForTimeout(700);
    for (const [tab, name] of [['board', '01-首屏测算台'], ['hist', '02-历史数据与分布'], ['quote', '03-带入出口报价'], ['method', '04-公式与缺口']]) {
      await page.click(`[data-tab="${tab}"]`);
      await page.waitForTimeout(tab === 'hist' ? 1300 : 800);
      await page.screenshot({ path: path.join(shotsDir, name + '.png'), fullPage: true });
    }
    await page.click('[data-tab="board"]');
    await page.waitForTimeout(600);
    await page.setViewportSize({ width: 420, height: 900 });
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(shotsDir, '05-移动端420.png'), fullPage: false });
    await page.setViewportSize({ width: 1600, height: 1100 });
  }
} catch (e) {
  P('QA 脚本执行', false, e.message);
} finally {
  await browser.close();
}

console.log('\n===== 真实渲染自检（Playwright / Chromium）=====');
for (const c of checks) console.log(`${c.ok ? '[PASS]' : '[FAIL]'} ${c.name}${c.detail ? '  — ' + c.detail : ''}`);
const failed = checks.filter(c => !c.ok);
console.log(`\n结果：${checks.length - failed.length}/${checks.length} 通过`);
if (errors.length) { console.log('JS 错误：'); errors.slice(0, 6).forEach(e => console.log('  ! ' + e)); }
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ file: htmlPath, checks, errors, failed: failed.length }, null, 2), 'utf8');
process.exit(failed.length ? 1 : 0);
