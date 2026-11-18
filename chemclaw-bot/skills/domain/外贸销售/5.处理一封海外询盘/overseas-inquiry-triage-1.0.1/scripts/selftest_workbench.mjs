// selftest_workbench.mjs · 无头浏览器自测（无第三方依赖，直连 Chrome DevTools Protocol）
// 用法：node selftest_workbench.mjs ../示例/询盘审阅板.html [--shots dir]
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const file = process.argv[2];
if (!file) { console.error('用法: node selftest_workbench.mjs <html> [--shots dir]'); process.exit(2); }
const shotsIdx = process.argv.indexOf('--shots');
const shotsDir = shotsIdx > 0 ? process.argv[shotsIdx + 1] : '';
if (shotsDir && !existsSync(shotsDir)) mkdirSync(shotsDir, { recursive: true });

const CANDIDATES = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
];
const browser = CANDIDATES.find(p => existsSync(p));
if (!browser) { console.log('[skip] 未找到 Edge/Chrome，跳过浏览器自测'); process.exit(0); }

const port = 9300 + Math.floor(Math.random() * 400);
const url = pathToFileURL(path.resolve(file)).href;
const child = spawn(browser, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--hide-scrollbars', '--window-size=1680,1100', `--remote-debugging-port=${port}`,
  '--user-data-dir=' + path.join(process.env.TEMP || '/tmp', 'oi-selftest-' + Date.now()),
  url,
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function getWs() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch (e) { /* not up yet */ }
    await sleep(250);
  }
  throw new Error('浏览器调试端口未就绪');
}

let msgId = 0;
function rpc(ws, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++msgId;
    const onMsg = ev => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.id === id) { ws.removeEventListener('message', onMsg); m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result); }
    };
    ws.addEventListener('message', onMsg);
    ws.send(JSON.stringify({ id, method, params }));
    setTimeout(() => { ws.removeEventListener('message', onMsg); reject(new Error('timeout ' + method)); }, 15000);
  });
}

const results = [];
function check(name, ok, detail = '') { results.push({ name, ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'} · ${name}${detail ? ' · ' + detail : ''}`); }

try {
  const wsUrl = await getWs();
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  await rpc(ws, 'Runtime.enable');
  await rpc(ws, 'Page.enable');
  await sleep(1200);

  const evalJS = async (expr) => {
    const r = await rpc(ws, 'Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' ' + JSON.stringify(r.exceptionDetails.exception || {}));
    return r.result.value;
  };

  const ready = await evalJS('!!window.__TRIAGE_READY__');
  check('页面初始化完成', ready);

  const counts = await evalJS(`(()=>{
    const t = s => document.querySelectorAll(s).length;
    return {fields:document.querySelectorAll('.f[data-k]').length, cats:t('.cat'), lines:t('.ln'), questions:document.querySelectorAll('#questions .q').length, snips:t('.snip-tab'),
            phs:t('.phitem'), tabs:t('.tab'), scenes:t('.scene'), traps:t('#traps .finding, #traps .empty'),
            bodyLen:(document.querySelector('#replyBody')||{}).value?.length||0};
  })()`);
  check('字段条目渲染', counts.fields >= 60, `字段 ${counts.fields} 条 / 分类 ${counts.cats}`);
  check('左栏原文行渲染', counts.lines > 20, `${counts.lines} 行`);
  check('素材分块标签', counts.snips >= 1, `${counts.snips} 块`);
  check('待确认问题渲染', counts.questions >= 1 && counts.questions <= 6, `${counts.questions} 条（≤6）`);
  check('占位符清单渲染', counts.phs >= 5, `${counts.phs} 个`);
  check('回复正文非空', counts.bodyLen > 600, `${counts.bodyLen} chars`);
  check('歧义陷阱区渲染', counts.traps >= 1, `${counts.traps} 个提示块`);
  check('下一步场景卡片', counts.scenes >= 4, `${counts.scenes} 张`);

  await evalJS(`document.querySelectorAll('.tab').forEach(t=>{ if(t.dataset.tab==='reply') t.click(); })`);
  const text = await evalJS('document.body.innerText');
  const priceHit = /(\$\s?\d|USD\s?\d|Rp\.?\s?\d)/i.test(text);
  check('页面无写死价格', !priceHit, priceHit ? '命中价格样式' : '');
  const badTerms = /(成单概率|成交概率|真实性评分|可信度\s*[:：]?\s*\d)/.test(text);
  check('页面无真实性/成交概率评分', !badTerms);
  const hasPh = /‹[A-Z0-9_]+›/.test(text);
  check('占位符可见', hasPh);

  // 点击字段 → 左栏高亮定位
  const loc = await evalJS(`(()=>{
    const ok = new Set(Object.entries(window.__INQUIRY_FIELDS__||{}).filter(([k,v])=>v&&v.quote&&v.source_id).map(([k])=>k));
    const first = Array.from(document.querySelectorAll('.f')).find(el=>ok.has(el.dataset.k));
    if (!first) return {ok:false};
    first.click();
    return {ok:true, lines: document.querySelectorAll('.ln.hl').length, key:first.dataset.k};
  })()`);
  check('点击字段可定位原文', loc.ok && loc.lines >= 1, `高亮 ${loc.lines} 行 (${loc.key})`);

  // 修正字段
  const fix = await evalJS(`(()=>{
    const segs = document.querySelectorAll('#filterSeg button'); segs[1].click();
    const before = window.__INQUIRY_STATE__.fields;
    const el = document.querySelector('.f[data-k="payment"]'); if(!el) return {ok:false};
    el.click();
    const ta = document.querySelector('[data-ta="payment"]');
    ta.value = 'L/C at sight, irrevocable';
    document.querySelector('[data-save="payment"]').click();
    const f = window.__INQUIRY_STATE__.fields;
    return {ok: f.payment === 'L/C at sight, irrevocable', status: (document.querySelector('.f[data-k="payment"]')||{}).className};
  })()`);
  check('字段可修正', fix.ok, fix.status || '');

  // 标记客户已确认 → 问题减少 + 闸门
  const gate = await evalJS(`(()=>{
    const qs0 = document.querySelectorAll('.q').length;
    document.querySelectorAll('.tab').forEach(t=>{ if(t.dataset.tab==='questions') t.click(); });
    const btn = document.querySelector('[data-qdone]');
    const key = btn ? btn.dataset.qdone : '';
    if (btn) btn.click();
    const qs1 = document.querySelectorAll('#questions .q').length;
    document.querySelectorAll('.tab').forEach(t=>{ if(t.dataset.tab==='gaps') t.click(); });
    const gateText = (document.querySelector('#gatebar')||{}).innerText||'';
    return {qs0, qs1, key, checked: !!window.__INQUIRY_STATE__.checked[key], gateText};
  })()`);
  check('标记"客户已答"后问题减少', gate.qs1 <= gate.qs0 && gate.checked, `${gate.qs0} → ${gate.qs1} (${gate.key})`);
  check('缺口页有报价闸门', /LOCKED|OPEN/.test(gate.gateText));

  // 回复生成：重新生成（切换语气）
  const regen = await evalJS(`(()=>{
    document.querySelectorAll('.tab').forEach(t=>{ if(t.dataset.tab==='reply') t.click(); });
    const tone = document.querySelector('#selTone');
    tone.value = 'formal'; tone.dispatchEvent(new Event('change'));
    document.querySelector('#btnRegen').click();
    const v = document.querySelector('#replyBody').value;
    return {len:v.length, formal:/We thank you for|Yours faithfully/.test(v), ph:(v.match(/‹[A-Z0-9_]+›/g)||[]).length};
  })()`);
  check('切换语气后重新生成', regen.formal && regen.ph >= 3, `formal=${regen.formal} · 占位符 ${regen.ph}`);

  // 承诺扫描：粘贴一句违规文本
  const scan = await evalJS(`(()=>{
    const ta = document.querySelector('#replyBody');
    ta.value = ta.value + '\\nWe can supply 300 MT immediately and deliver within 20 days.';
    ta.dispatchEvent(new Event('input'));
    const chip = document.querySelector('#scanChip').innerText;
    const price = document.querySelector('#priceChip').innerText;
    return {chip, price};
  })()`);
  check('承诺扫描能抓到违规句', /承诺扫描 : [1-9]/.test(scan.chip), scan.chip);
  check('价格扫描计数存在', /价格痕迹 : \d/.test(scan.price), scan.price);

  // 恢复正文，填入占位符
  const fill = await evalJS(`(()=>{
    document.querySelector('#btnRegen').click();
    const inputs = Array.from(document.querySelectorAll('[data-ph]'));
    inputs.slice(0,3).forEach(i=>{ i.value = 'DEMO_VALUE'; i.dispatchEvent(new Event('input')); });
    return {filled: inputs.slice(0,3).filter(i=>i.value).length, total: inputs.length};
  })()`);
  check('占位符可填写', fill.filled === 3, `${fill.filled}/${fill.total}`);

  // 润色通道：新增承诺必须被拒绝
  const polish = await evalJS(`(()=>{
    document.querySelectorAll('.tab').forEach(t=>{ if(t.dataset.tab==='polish') t.click(); });
    const out1 = document.querySelector('#polishOut');
    document.querySelector('#polishIn').value = 'Dear Sir, Please kindly note that we are happy to quote. Thank you for your inquiry.';
    document.querySelector('#btnPolish').click();
    const clean = {text: document.querySelector('#polishOut').innerText, checks: document.querySelector('#polishChecks').innerText};
    document.querySelector('#polishIn').value = 'Dear Sir, We can supply 300 MT immediately and deliver within 15 days.';
    document.querySelector('#btnPolish').click();
    const risky = {text: document.querySelector('#polishOut').innerText, checks: document.querySelector('#polishChecks').innerText};
    return {clean, risky};
  })()`);
  check('润色正常稿：只改语言并列出改动', /Please note/.test(polish.clean.text) && /新增承诺检查：无/.test(polish.clean.checks),
        (polish.clean.checks||'').split('\n')[0]);
  check('润色违规稿：拒绝新增承诺', /检测到新增承诺|拒绝输出/.test(polish.risky.text) && !/detected/.test(polish.risky.checks),
        (polish.risky.checks||'').split('\n')[0]);

  // 交接 JSON
  const hand = await evalJS(`(()=>{
    document.querySelectorAll('.tab').forEach(t=>{ if(t.dataset.tab==='next') t.click(); });
    const v = document.querySelector('#handoff').value;
    let ok = true; try { JSON.parse(v); } catch(e){ ok = false; }
    return {ok, len: v.length, hasPrice: /"price":/.test(v)};
  })()`);
  check('交接 JSON 合法', hand.ok, `${hand.len} chars`);
  check('交接 JSON 不含价格字段', !hand.hasPrice);

  // ---- 布局回归：窄窗口下左栏不许把右侧字段区压到下面看不见 ----
  // 曾经的 bug：断点 1180px 偏高 + 单栏时左栏 max-height 未重置，笔记本小窗口里
  // 原始询盘占满整屏，字段区被顶到屏幕外，用户表现为"字段被原始询盘挡住了"。
  const layout = [];
  await evalJS(`document.querySelectorAll('.tab').forEach(x=>{ if(x.dataset.tab==='review') x.click(); })`);
  await sleep(250);
  for (const [w, h] of [[1440, 900], [1100, 760], [1024, 768], [900, 700]]) {
    await rpc(ws, 'Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: false });
    await sleep(300);
    const m = await evalJS(`(()=>{
      const src = document.querySelector('#source');
      const srcCard = document.querySelector('.src-col') || document.querySelector('.sticky-card');
      const fieldCard = document.querySelector('#fields').closest('.card');
      if(!src||!srcCard||!fieldCard) return {err:'缺元素'};
      const s = src.getBoundingClientRect(), f = fieldCard.getBoundingClientRect();
      // 双栏 = 字段卡片在左栏右边；单栏 = 字段卡片在下面，此时左栏必须让出高度
      const sideBySide = f.left >= s.right - 2;
      const srcFits = srcCard.getBoundingClientRect().height <= innerHeight + 1;
      // 字段区起点必须能在滚动范围内到达（不许被永久顶出文档可视范围）
      const fieldReachable = f.top < s.top + src.clientHeight + 400;
      const lastLine = src.querySelector('.ln:last-of-type');
      src.scrollTop = src.scrollHeight;
      const lr = lastLine ? lastLine.getBoundingClientRect() : null;
      const lastVisible = lr ? lr.bottom <= s.bottom + 1 && lr.top >= s.top - 1 : false;
      return {sideBySide, srcFits, fieldReachable, lastVisible, winH: innerHeight,
              srcCardH: Math.round(srcCard.getBoundingClientRect().height), fieldTop: Math.round(f.top)};
    })()`);
    layout.push({ w, h, ...m });
  }
  await rpc(ws, 'Emulation.clearDeviceMetricsOverride', {});
  check('窄窗口：字段区不被原始询盘压到下方',
        layout.every(m => !m.err && m.fieldReachable), 
        layout.map(m => `${m.w}px:${m.err||(m.fieldReachable?'ok':'压住了')}`).join(' · '));
  check('窄窗口：左栏高度不超过视口且可滚到底',
        layout.every(m => !m.err && m.srcFits && m.lastVisible),
        layout.map(m => `${m.w}px:${m.err||(m.srcFits&&m.lastVisible?'ok':'超高')}`).join(' · '));
  check('1024/1100 宽仍保持左右双栏',
        layout.filter(m => m.w === 1024 || m.w === 1100).length === 2 &&
        layout.filter(m => m.w === 1024 || m.w === 1100).every(m => m.sideBySide),
        layout.map(m => `${m.w}px:${m.err ? '?' : (m.sideBySide ? '双栏' : '单栏')}`).join(' · '));
  check('≤960 宽降级为单栏且字段区仍在左栏下方可见',
        layout.filter(m => m.w <= 960).every(m => !m.err && !m.sideBySide && m.fieldReachable),
        layout.filter(m => m.w <= 960).map(m => `${m.w}px:${m.err ? '?' : (m.sideBySide ? '双栏' : '单栏')}`).join(' · '));

  // 截图（供人工目检）
  if (shotsDir) {
    const tabs = ['review', 'gaps', 'questions', 'reply', 'polish', 'next'];
    for (const t of tabs) {
      await evalJS(`document.querySelectorAll('.tab').forEach(x=>{ if(x.dataset.tab==='${t}') x.click(); })`);
      await sleep(350);
      const shot = await rpc(ws, 'Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
      writeFileSync(path.join(shotsDir, `tab_${t}.png`), Buffer.from(shot.data, 'base64'));
    }
    console.log('[shots] ' + shotsDir);
  }

  ws.close();
} catch (e) {
  check('自测执行', false, e.message);
} finally {
  child.kill();
}

const fails = results.filter(r => !r.ok).length;
console.log(`\n${results.length - fails}/${results.length} 通过`);
process.exit(fails ? 1 : 0);
