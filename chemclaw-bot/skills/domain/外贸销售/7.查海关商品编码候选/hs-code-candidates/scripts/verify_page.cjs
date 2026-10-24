const path = require('path');
const fs = require('fs');
const { createRequire } = require('module');

const skillNodeModules = 'C:/Users/EDY/AppData/Local/Programs/DeepSeek Harness/resources/app.asar.unpacked/dsh/node_modules';
let pw;
try {
  pw = createRequire(skillNodeModules + '/')('playwright');
} catch (e) {
  pw = require('playwright');
}

(async () => {
  const file = process.argv[2];
  const outDir = process.argv[3];
  const candidate = 'C:/Users/EDY/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
  const browser = await pw.chromium.launch(fs.existsSync(candidate) ? { executablePath: candidate } : {});
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('file:///' + file.replace(/\\/g, '/'));
  await page.waitForTimeout(600);
  const ready = await page.evaluate(() => window.__reportReady === true);
  fs.mkdirSync(outDir, { recursive: true });
  const tabs = ['flow','cands','basis','amb','layer','reg','miss','conf','src'];
  for (const t of tabs) {
    await page.click(`.tab[data-tab="${t}"]`);
    await page.waitForTimeout(250);
    const active = await page.evaluate(() => document.querySelector('.panel.active').id);
    if (active !== 'p-' + t) errors.push('tab switch failed: ' + t + ' -> ' + active);
  }
  // back to flow, screenshot top
  await page.click('.tab[data-tab="flow"]');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(outDir, 'v1_flow.png'), fullPage: false });
  await page.click('.tab[data-tab="cands"]');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(outDir, 'v2_cands.png'), fullPage: false });
  // filter test
  await page.click('.fbtn[data-f="cond"]');
  await page.waitForTimeout(200);
  const visible = await page.evaluate(() => [...document.querySelectorAll('.card')].filter(c => c.style.display !== 'none').map(c => c.dataset.code));
  await page.fill('#q', '4002');
  await page.waitForTimeout(200);
  const visible2 = await page.evaluate(() => [...document.querySelectorAll('.card')].filter(c => c.style.display !== 'none').map(c => c.dataset.code));
  await page.fill('#q', '');
  await page.click('.fbtn[data-f="all"]');
  await page.waitForTimeout(200);
  // full page shot of a couple of tabs
  await page.click('.tab[data-tab="reg"]');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(outDir, 'v3_reg.png'), fullPage: false });
  await page.click('.tab[data-tab="layer"]');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(outDir, 'v4_layer.png'), fullPage: false });
  // mobile
  await page.setViewportSize({ width: 390, height: 844 });
  await page.click('.tab[data-tab="cands"]');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(outDir, 'v5_mobile.png'), fullPage: false });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2);
  const out = { ready, errors, visibleCond: visible, visibleQ: visible2, mobileOverflow: overflow };
  fs.writeFileSync(path.join(outDir, 'interaction.json'), JSON.stringify(out, null, 1), 'utf-8');
  console.log(JSON.stringify(out));
  await browser.close();
})();
