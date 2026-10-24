// 用无头浏览器加载报告：捕获 JS 错误、校验关键 DOM 与交互，可选截图。
// 用法: node check_html.js <file.html> [out.png]
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const html = path.resolve(process.argv[2]);
const shot = process.argv[3] ? path.resolve(process.argv[3]) : null;
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const port = 9333 + Math.floor(Math.random() * 400);
const sleep = ms => new Promise(r => setTimeout(r, ms));

function bail(msg) { console.log('RESULT: FAIL\n' + msg); process.exit(1); }

(async () => {
  if (!fs.existsSync(html)) bail('文件不存在: ' + html);
  const proc = spawn(EDGE, [
    '--headless=new', `--remote-debugging-port=${port}`,
    '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--allow-file-access-from-files', '--window-size=1500,1200',
    `--user-data-dir=${path.join(os.tmpdir(), 'mf-edge-' + Date.now())}`,
    'about:blank'
  ], { stdio: 'ignore' });

  let targets = null;
  for (let i = 0; i < 80; i++) {
    await sleep(300);
    try {
      targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      if (targets.length) break;
    } catch (e) { /* 等启动 */ }
  }
  if (!targets) { proc.kill(); bail('浏览器未启动'); }

  const page = targets.find(t => t.type === 'page') || targets[0];
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  const errors = [], logs = [];
  let id = 0;
  const pending = new Map();
  const send = (method, params = {}) => new Promise(res => {
    const mid = ++id; pending.set(mid, res);
    ws.send(JSON.stringify({ id: mid, method, params }));
  });

  await new Promise(r => ws.addEventListener('open', r));
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); return; }
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails;
      errors.push((d.exception && (d.exception.description || d.exception.value)) || d.text);
    }
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error')
      logs.push(m.params.args.map(a => a.value || a.description || '').join(' '));
    if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error')
      logs.push('[log] ' + m.params.entry.text);
  });

  await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable');
  await send('Page.navigate', { url: 'file:///' + html.replace(/\\/g, '/') });
  await sleep(3000);

  async function evaluate(expr, label) {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (!r) bail(`${label}: 无返回（页面可能已崩溃）`);
    if (r.exceptionDetails) bail(`${label}: 求值异常 -> ${JSON.stringify(r.exceptionDetails).slice(0, 500)}`);
    const v = r.result && r.result.value;
    if (v === undefined || v === null) bail(`${label}: 返回 undefined (type=${r.result && r.result.type})`);
    return v;
  }

  const probeRaw = await evaluate(`JSON.stringify({
    svgCount: document.querySelectorAll('svg').length,
    kpis: document.getElementById('kpis').children.length,
    changeRows: document.getElementById('tChange').querySelectorAll('tbody tr').length,
    pctRows: document.getElementById('tPct').querySelectorAll('tbody tr').length,
    cmpRows: document.getElementById('tComparable').querySelectorAll('tbody tr').length,
    evRows: document.getElementById('tEvents').querySelectorAll('tbody tr').length,
    storyRows: document.getElementById('tStory').querySelectorAll('tbody tr').length,
    decRows: document.getElementById('tDecomp').querySelectorAll('tbody tr').length,
    dailyRows: document.getElementById('tDaily').querySelectorAll('tbody tr').length,
    tsRows: document.getElementById('tTS').querySelectorAll('tbody tr').length,
    srcRows: document.getElementById('tSources').querySelectorAll('tbody tr').length,
    flowSteps: document.getElementById('flow').children.length,
    conclusions: document.getElementById('conclusions').querySelectorAll('li').length,
    limits: document.getElementById('limits').querySelectorAll('li').length,
    whLen: document.getElementById('whBox').innerHTML.length,
    clickLen: document.getElementById('clickPanel').innerHTML.length,
    pairOptions: document.getElementById('selPair').options.length,
    anchorOptions: document.getElementById('selAnchor').options.length,
    title: document.getElementById('hTitle').textContent,
    bodyText: document.body.innerText.length,
    domTables: document.querySelectorAll('table').length,
    hasDisclaim: document.body.innerText.includes('不构成任何交易建议') || document.body.innerText.includes('不含任何交易建议')
  })`);
  const p = JSON.parse(probeRaw);
  console.log('=== 探测 ===');
  console.log(probeRaw);

  const expect = {
    svgCount: 7, kpis: 4, changeRows: 5, pctRows: 4, cmpRows: 7, evRows: 16,
    storyRows: 5, decRows: 3, dailyRows: 10, tsRows: 5, srcRows: 5, flowSteps: 4,
    conclusions: 6, limits: 6, domTables: 12
  };
  const bad = [];
  for (const k in expect) if (p[k] !== expect[k]) bad.push(`${k}: 期望 ${expect[k]} 实际 ${p[k]}`);
  if (!(p.whLen > 100)) bad.push('仓单区块为空');
  if (!(p.clickLen > 200)) bad.push('联动面板为空');
  if (!(p.pairOptions > 5)) bad.push('月份组合下拉过少: ' + p.pairOptions);
  if (!(p.bodyText > 5000)) bad.push('正文过短: ' + p.bodyText);
  if (!p.hasDisclaim) bad.push('缺少免责声明');

  const interRaw = await evaluate(`(function(){
    const out={};
    const sel=document.getElementById('selPair');
    if(sel.options.length>1){ sel.selectedIndex=1; sel.dispatchEvent(new Event('change'));
      out.spreadPathsAfterSwitch=document.getElementById('chSpread').querySelectorAll('svg path').length; }
    const sl=document.getElementById('tsSlider'); sl.value=String(Math.floor(sl.max*0.5));
    sl.dispatchEvent(new Event('input'));
    out.tsRowsAfterSlider=document.getElementById('tTS').querySelectorAll('tbody tr').length;
    out.tsHint=document.getElementById('tsHint').textContent;
    document.querySelectorAll('#segOrder button')[1].click();
    out.pairHint=document.getElementById('pairHint').textContent;
    document.querySelectorAll('#segPrice button')[1].click();
    out.settleNote=document.getElementById('pairHint').textContent.includes('仅含收盘价');
    const domCol=document.getElementById('tDaily').querySelectorAll('tbody tr td:last-child');
    out.dailyDomains=[...domCol].map(td=>td.textContent).slice(0,4);
    return JSON.stringify(out);
  })()`);
  const it = JSON.parse(interRaw);
  console.log('=== 交互 ===');
  console.log(interRaw);
  if (!(it.spreadPathsAfterSwitch > 1)) bad.push('切换月份组合后图未重绘');
  if (!(it.tsRowsAfterSlider > 1)) bad.push('拖动时间轴后期限结构表未更新');
  if (!it.settleNote) bad.push('切到结算价时缺少口径提示');
  if (!it.dailyDomains.some(x => x.includes('相抵') || x.includes('不显著'))) bad.push('逐日主导列未按净效果判定');

  console.log('=== JS 错误 ===');
  console.log(errors.length ? errors.join('\n---\n') : '无');
  console.log('=== console/网络错误 ===');
  console.log(logs.length ? logs.join('\n') : '无');
  if (errors.length) bad.push(`JS 异常 ${errors.length} 条`);

  if (shot) {
    const cap = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    if (cap && cap.data) { fs.writeFileSync(shot, Buffer.from(cap.data, 'base64')); console.log('截图 ->', shot); }
    else bad.push('截图失败');
  }

  ws.close(); proc.kill();
  if (bad.length) bail('校验未通过:\n - ' + bad.join('\n - '));
  console.log('RESULT: PASS');
})();
