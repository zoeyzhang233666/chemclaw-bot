// 用 Edge headless 打开本地 HTML，执行页内 JS 并回收 console/errors/DOM 结果
// 用法: node probe_html.js <page.html>
// 退出码: 0 通过；1 页内报错/图表未渲染
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const CANDIDATES = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
];
const browser = CANDIDATES.find(p => fs.existsSync(p));
const target = process.argv[2];
if (!browser) { console.error('SKIP: 未找到 Edge/Chrome，可跳过本项（页面仍可人工打开检查）'); process.exit(0); }
if (!target || !fs.existsSync(target)) { console.error('用法: node probe_html.js <page.html>'); process.exit(2); }

const tmp = path.join(process.env.TEMP || '/tmp', 'probe_html_' + process.pid);
fs.rmSync(tmp, { recursive: true, force: true });
fs.mkdirSync(tmp, { recursive: true });

const html = fs.readFileSync(target, 'utf8');
const probe = `
<script>
(function(){
  var log = { errors: [], charts: {}, counts: {}, mode: {}, termTip: null, calc: null, dataInjected: false };
  window.onerror = function(m, s, l){ log.errors.push(String(m) + ' @line ' + l); };
  try { log.dataInjected = !!JSON.parse(document.getElementById('DATA').textContent || '{}').meta; } catch(e){ log.errors.push('DATA 解析失败: ' + e.message); }
  ['#chart-inv-price','#chart-basis','#chart-mc','#chart-roll','#chart-basis-defs','#chart-scatter','#calc-out'].forEach(function(s){
    var el = document.querySelector(s);
    log.charts[s] = el ? el.querySelectorAll('svg,circle,rect,tr').length : 'MISSING';
  });
  function n(sel){ return document.querySelectorAll(sel).length; }
  log.counts = { sections: n('section.block'), tables: n('table'), terms: n('[data-term]'), kpi: n('.kpi') };
  var pro = document.querySelector('.pro-only'), beg = document.querySelector('.beginner-only');
  log.mode.beginner = { proHidden: pro ? getComputedStyle(pro).display === 'none' : 'N/A' };
  var btn = document.querySelector('.seg button[data-mode="pro"]');
  if (btn) btn.click();
  log.mode.pro = { beginnerHidden: beg ? getComputedStyle(beg).display === 'none' : 'N/A',
                   proShown: pro ? getComputedStyle(pro).display !== 'none' : 'N/A' };
  var out = document.querySelector('#calc-out');
  log.calc = out ? out.innerText.slice(0, 120).replace(/\\s+/g, ' ') : 'MISSING';
  var t = document.querySelector('[data-term]');
  if (t) { t.dispatchEvent(new MouseEvent('mouseenter')); var tip = document.getElementById('tip');
           log.termTip = tip ? tip.innerText.slice(0, 40) : 'MISSING'; }
  var d = document.createElement('div'); d.id = 'PROBE'; d.textContent = JSON.stringify(log); document.body.appendChild(d);
})();
</script>`;
const copy = path.join(tmp, 'probe.html');
fs.writeFileSync(copy, html.replace('</body>', probe + '</body>'), 'utf8');

const args = ['--headless=new', '--disable-gpu', '--no-sandbox', '--disable-extensions',
  '--user-data-dir=' + path.join(tmp, 'ud'), '--virtual-time-budget=8000', '--dump-dom',
  'file:///' + copy.replace(/\\/g, '/')];
const r = spawnSync(browser, args, { encoding: 'utf8', maxBuffer: 96 * 1024 * 1024 });
const dom = r.stdout || '';
const m = dom.match(/<div id="PROBE">([\s\S]*?)<\/div>/);
if (!m) { console.error('FAIL: 页面脚本未执行完成（无 PROBE 输出）'); process.exit(1); }
const log = JSON.parse(m[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>'));
console.log(JSON.stringify(log, null, 1));

const problems = [];
if (log.errors.length) problems.push('页内报错: ' + log.errors.join(' | '));
if (!log.dataInjected) problems.push('DATA JSON 未注入或无法解析');
Object.keys(log.charts).forEach(k => { if (log.charts[k] === 'MISSING') problems.push('缺少图表容器 ' + k); });
// 图表节点为数字且 > 2 视为已渲染；calc-out 是表格行数
Object.keys(log.charts).forEach(k => {
  const v = log.charts[k];
  if (typeof v === 'number' && v <= 2 && k !== '#calc-out') problems.push('图表未渲染 ' + k + ' (节点数=' + v + ')');
});
if (log.calc === 'MISSING') problems.push('缺少重算输出容器 #calc-out');
if (log.counts.sections < 10) problems.push('区块过少: ' + log.counts.sections);
if (log.mode.beginner.proHidden !== true) problems.push('入门模式下 .pro-only 未被隐藏');
if (log.mode.pro.beginnerHidden !== true) problems.push('专业模式下 .beginner-only 未被隐藏');
if (!log.termTip) problems.push('术语气泡未触发');

if (problems.length) { console.error('\n检查未通过：\n- ' + problems.join('\n- ')); process.exit(1); }
console.error('\n检查通过：无报错，图表与交互正常。');
process.exit(0);
