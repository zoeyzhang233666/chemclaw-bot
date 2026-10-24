// 用 Chrome DevTools Protocol 驱动无头浏览器，验证 HTML 渲染与实时联动。
// 用法: node cdp_check.mjs <html文件绝对路径>
import { spawn } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const file = process.argv[2];
const PORT = 9333;

const proc = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
  `--remote-debugging-port=${PORT}`,
  '--user-data-dir=' + process.env.TEMP + '\\cdp_check_profile',
  '--window-size=1500,2000',
  'about:blank'
], { stdio: 'ignore' });

let ws, msgId = 0;
const pending = new Map();
const events = [];

async function connect() {
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await r.json();
      const page = list.find(t => t.type === 'page');
      if (page) return page.webSocketDebuggerUrl;
    } catch { /* not up yet */ }
    await sleep(250);
  }
  throw new Error('CDP not reachable');
}

function send(method, params = {}) {
  const id = ++msgId;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((res, rej) => {
    pending.set(id, { res, rej });
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error('timeout ' + method)); } }, 15000);
  });
}

async function evaluate(expr) {
  const r = await send('Runtime.evaluate', {
    expression: expr, returnByValue: true, awaitPromise: true, userGesture: true
  });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 400));
  return r.result.value;
}

const results = [];
function check(name, cond, detail = '') {
  results.push({ name, ok: !!cond, detail });
  console.log((cond ? '  PASS ' : '  FAIL ') + name + (detail ? '  ' + detail : ''));
}

(async () => {
  const url = await connect();
  ws = new WebSocket(url);
  await new Promise(r => { ws.onopen = r; });
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pending.has(d.id)) {
      const p = pending.get(d.id); pending.delete(d.id);
      d.error ? p.rej(new Error(JSON.stringify(d.error))) : p.res(d.result);
    } else if (d.method) events.push(d);
  };

  await send('Runtime.enable');
  await send('Page.enable');
  await send('Log.enable');
  await send('Page.navigate', { url: 'file:///' + file.replace(/\\/g, '/') });
  await sleep(2500);

  // --- 捕获 JS 错误 ---
  const errs = events.filter(e =>
    (e.method === 'Runtime.exceptionThrown') ||
    (e.method === 'Log.entryAdded' && e.params.entry.level === 'error'));
  check('无 JavaScript 运行时错误', errs.length === 0,
        errs.length ? JSON.stringify(errs[0]).slice(0, 300) : '');

  // --- 首屏 KPI 是否已填充 ---
  const kpi = await evaluate(`(() => {
    const g = id => (document.getElementById(id)||{}).textContent||'';
    return {rate:g('k-rate'), pay:g('k-pay'), landed:g('k-landed'), pct:g('k-pct'),
            up1:g('k-up1'), up5:g('k-up5'), dn3:g('k-dn3')};
  })()`);
  check('首屏-当前汇率已渲染', /\d\.\d{4}/.test(kpi.rate), kpi.rate.trim());
  check('首屏-人民币付汇已渲染', /6,743,500/.test(kpi.pay), kpi.pay.trim());
  check('首屏-到厂成本已渲染', /7,204,900/.test(kpi.landed), kpi.landed.trim());
  check('首屏-历史分位已渲染', /%/.test(kpi.pct), kpi.pct.trim());
  check('首屏-+1% 增加额', /67,435/.test(kpi.up1), kpi.up1.trim());
  check('首屏-+5% 增加额', /337,175/.test(kpi.up5), kpi.up5.trim());
  check('首屏--3% 节省额', /202,305/.test(kpi.dn3), kpi.dn3.trim());

  // --- 走势图 SVG 是否绘制 ---
  const chart = await evaluate(`(() => {
    const svg = document.querySelector('#chart svg');
    if (!svg) return {ok:false};
    const path = svg.querySelector('path[stroke="#4a9eff"]');
    return {ok:true, pathLen:(path?path.getAttribute('d').length:0),
            hotspots:svg.querySelectorAll('.hs').length,
            ticks:svg.querySelectorAll('text').length};
  })()`);
  check('走势图 SVG 已绘制', chart.ok && chart.pathLen > 500,
        `pathLen=${chart.pathLen} 热区=${chart.hotspots} 刻度=${chart.ticks}`);
  check('走势图有悬停热区', chart.hotspots > 100, `hotspots=${chart.hotspots}`);

  // --- 表格填充 ---
  const rows = await evaluate(`(() => {
    const c = id => (document.getElementById(id)||{}).querySelectorAll('tbody tr').length;
    return {pay:c('t-pay'), basis:c('t-basis'), landed:c('t-landed'),
            margin:c('t-margin'), tranche:c('t-tranche'), src:c('t-src')};
  })()`);
  check('付款敏感性表 7 行', rows.pay === 7, String(rows.pay));
  check('四口径对照表已填充', rows.basis >= 3, String(rows.basis));
  check('到厂成本表已填充', rows.landed >= 5, String(rows.landed));
  check('毛利敏感性表已填充', rows.margin === 7, String(rows.margin));
  check('分批付款表已填充', rows.tranche === 4, String(rows.tranche));
  check('数据来源表已填充', rows.src >= 5, String(rows.src));

  // --- 实时联动：改金额 ---
  const before = await evaluate(`document.getElementById('k-pay').textContent`);
  await evaluate(`(() => { const e = document.getElementById('in-amount');
    e.value = '2000000'; e.dispatchEvent(new Event('input', {bubbles:true})); return 1; })()`);
  await sleep(300);
  const after = await evaluate(`document.getElementById('k-pay').textContent`);
  check('改金额 2,000,000 后付汇实时翻倍', /13,487,000/.test(after), before.trim() + ' -> ' + after.trim());

  // --- 实时联动：改汇率 ---
  await evaluate(`(() => { const e = document.getElementById('in-bank');
    e.value = '7.0'; e.dispatchEvent(new Event('input', {bubbles:true})); return 1; })()`);
  await sleep(300);
  const k2 = await evaluate(`document.getElementById('k-pay').textContent`);
  check('银行汇率改 7.0 后付汇 = 14,000,000', /14,000,000/.test(k2), k2.trim());

  // --- 实时联动：增值税口径切换影响成本 ---
  const lm1 = await evaluate(`document.getElementById('k-landed').textContent`);
  await evaluate(`(() => { const e = document.getElementById('in-vatmode');
    e.value = 'cost'; e.dispatchEvent(new Event('change', {bubbles:true})); return 1; })()`);
  await sleep(300);
  const lm2 = await evaluate(`document.getElementById('k-landed').textContent`);
  check('增值税改不可抵扣后到厂成本上升', lm1.trim() !== lm2.trim(), lm1.trim() + ' -> ' + lm2.trim());

  // --- 实时联动：改付款比例 ---
  await evaluate(`(() => { const e = document.getElementById('in-p1');
    e.value = '50'; e.dispatchEvent(new Event('input', {bubbles:true})); return 1; })()`);
  await sleep(300);
  const p2v = await evaluate(`document.getElementById('in-p2').value`);
  check('预付款 50% 时尾款自动变 50%', p2v === '50', 'p2=' + p2v);

  // --- 锁定汇率使该批不随情景变动 ---
  await evaluate(`(() => { const e = document.getElementById('in-r1');
    e.value = '6.70'; e.dispatchEvent(new Event('input', {bubbles:true})); return 1; })()`);
  await sleep(300);
  const locked = await evaluate(`(() => {
    const t = document.getElementById('t-tranche');
    const first = t.querySelectorAll('tbody tr')[0];
    const cells = [...first.querySelectorAll('td')].map(x=>x.textContent.trim());
    return {cells, badge: first.innerHTML.includes('已锁')};
  })()`);
  check('锁定预付款汇率后显示“已锁”标记', locked.badge, JSON.stringify(locked.cells.slice(0,6)));

  // --- 毛利：缺少销售价时不臆造 ---
  await evaluate(`(() => { const e = document.getElementById('in-price');
    e.value = ''; e.dispatchEvent(new Event('input', {bubbles:true})); return 1; })()`);
  await sleep(300);
  const noMargin = await evaluate(`(() => {
    return {warn: document.getElementById('margin-warn').style.display,
            kpi: document.getElementById('margin-kpi').children.length,
            tbl: document.getElementById('t-margin').innerHTML.length};
  })()`);
  check('缺销售价时隐藏毛利且提示', noMargin.warn !== 'none' && noMargin.kpi === 0 && noMargin.tbl === 0,
        JSON.stringify(noMargin));

  // --- 恢复销售价，盈亏平衡出现 ---
  await evaluate(`(() => { const e = document.getElementById('in-price');
    e.value = '7600'; e.dispatchEvent(new Event('input', {bubbles:true})); return 1; })()`);
  await sleep(300);
  const be = await evaluate(`document.getElementById('breakeven-box').textContent`);
  check('恢复销售价后输出盈亏平衡汇率', /平衡汇率/.test(be), be.slice(0, 120).replace(/\s+/g, ' '));

  // --- 切换历史窗口 ---
  const w1 = await evaluate(`document.querySelector('#chart svg path[stroke="#4a9eff"]').getAttribute('d').length`);
  await evaluate(`document.querySelectorAll('.tab')[3].click()`);
  await sleep(400);
  const w3 = await evaluate(`document.querySelector('#chart svg path[stroke="#4a9eff"]').getAttribute('d').length`);
  check('切换“全部”历史窗口后图重绘', w1 !== w3, `${w1} -> ${w3}`);

  // --- 布局溢出检查 ---
  // 判定标准：整页不得横向溢出（否则用户被迫左右拖动整个页面）。
  // .panel 内部允许横向滚动（宽表格在窄屏下自动出滚动条），这是刻意设计，
  // 因此只要求：面板内溢出的元素必须是可滚动的（overflow-x 为 auto/scroll），
  // 且该溢出被限制在面板内部、不传导到页面。
  const overflow = await evaluate(`(() => {
    const bad = [];
    document.querySelectorAll('.panel, .kpi, table').forEach(el=>{
      if (el.scrollWidth > el.clientWidth + 3 && el.clientWidth > 0) {
        const ox = getComputedStyle(el).overflowX;
        const scrollable = ox === 'auto' || ox === 'scroll';
        if (!scrollable) bad.push((el.className || el.tagName) + ':' + ox);
      }
    });
    return {bad: bad.slice(0,5), scrollW: document.documentElement.scrollWidth,
            clientW: document.documentElement.clientWidth};
  })()`);
  check('页面无横向溢出（宽表在面板内自行滚动）',
        overflow.bad.length === 0 && overflow.scrollW <= overflow.clientW + 2,
        JSON.stringify(overflow));

  const pass = results.filter(r => r.ok).length, total = results.length;
  console.log(`\n${pass === total ? 'ALL PASS' : (total - pass) + ' FAILED'}  (${pass}/${total})`);
  proc.kill();
  process.exit(pass === total ? 0 : 1);
})().catch(e => { console.error('ERROR', e.message); proc.kill(); process.exit(2); });
