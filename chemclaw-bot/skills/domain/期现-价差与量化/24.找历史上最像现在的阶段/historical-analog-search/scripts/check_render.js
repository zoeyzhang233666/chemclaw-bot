// check_render.js — 用 Playwright 真实渲染 HTML，抓控制台错误并验证关键内容
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const file = process.argv[2];
  const shot = process.argv[3] || null;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  const errors = [], warns = [];
  page.on('console', m => {
    if (m.type() === 'error') errors.push(m.text());
    if (m.type() === 'warning') warns.push(m.text());
  });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  await page.goto('file://' + path.resolve(file).replace(/\\/g, '/'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);

  const info = await page.evaluate(() => {
    const txt = id => (document.getElementById(id) || {}).innerText || '';
    return {
      hasECharts: typeof echarts !== 'undefined',
      rankRows: document.querySelectorAll('#rankbox tbody tr').length,
      cmpRows: document.querySelectorAll('#cmpbox tbody tr').length,
      fwdRows: document.querySelectorAll('#fwd-table tbody tr').length,
      tierRows: document.querySelectorAll('#tier-box tbody tr').length,
      overlaps: txt('overlap-box').slice(0, 260),
      dedup: txt('dedup-note').slice(0, 260),
      sens: txt('sens-box').slice(0, 160),
      limits: document.querySelectorAll('#limits-box li').length,
      nowKpis: document.querySelectorAll('#now-kpis .kpi').length,
      detailTitle: txt('detail-title'),
      canvases: document.querySelectorAll('canvas').length,
      chartNodes: document.querySelectorAll('div[_echarts_instance_]').length,
    };
  });

  // 交互测试：改权重后重算
  const before = await page.evaluate(() => document.getElementById('rankbox').innerText.slice(0, 200));
  await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.indrow')];
    const r = rows.find(x => x.dataset.k === 'port_inv');
    if (r) { const s = r.querySelector('input[type=range]'); s.value = 3; s.dispatchEvent(new Event('change', {bubbles:true})); }
  });
  await page.waitForTimeout(1200);
  const after = await page.evaluate(() => document.getElementById('rankbox').innerText.slice(0, 200));

  // 交互测试：切换宽松口径
  await page.selectOption('#p-strict', '0').catch(()=>{});
  await page.waitForTimeout(1200);
  const loose = await page.evaluate(() => ({
    rows: document.querySelectorAll('#rankbox tbody tr').length,
    note: document.getElementById('dedup-note').innerText.slice(0, 200)
  }));

  if (shot) await page.screenshot({ path: shot, fullPage: true });

  console.log(JSON.stringify({
    errors: errors.slice(0, 12), warns: warns.slice(0, 6), info,
    weightChangeTookEffect: before !== after,
    looseTier: loose
  }, null, 1));
  await browser.close();
})();
