// 通过 CDP 打开报告页面，执行运行时自检：JS 报错、关键元素填充、筛选/抽屉交互
const http = require('http');

function get(path) {
  return new Promise((res, rej) => {
    http.get({ host: '127.0.0.1', port: 9333, path }, r => {
      let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d)));
    }).on('error', rej);
  });
}

(async () => {
  const targets = await get('/json/list');
  let page = targets.find(t => t.type === 'page');
  if (!page) throw new Error('no page target');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  const send = (method, params) => new Promise((res, rej) => {
    const mid = ++id; pending.set(mid, { res, rej });
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
  const logs = [];
  ws.addEventListener('message', ev => {
    const o = JSON.parse(ev.data);
    if (o.id && pending.has(o.id)) {
      const p = pending.get(o.id); pending.delete(o.id);
      o.error ? p.rej(new Error(JSON.stringify(o.error))) : p.res(o.result);
    } else if (o.method === 'Runtime.consoleAPICalled') {
      logs.push('[console.' + o.params.type + '] ' + o.params.args.map(a => a.value || a.description).join(' '));
    } else if (o.method === 'Runtime.exceptionThrown') {
      logs.push('[EXCEPTION] ' + (o.params.exceptionDetails.exception?.description || o.params.exceptionDetails.text));
    }
  });
  await new Promise(r => ws.addEventListener('open', r));
  await send('Runtime.enable');
  await send('Page.enable');

  const url = process.argv[2];
  await send('Page.navigate', { url });
  await new Promise(r => setTimeout(r, 4000));

  const evalJs = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) return { error: r.exceptionDetails.exception?.description || r.exceptionDetails.text };
    return r.result.value;
  };

  const checks = await evalJs(`(() => {
    const q = s => document.querySelector(s);
    const txt = s => { const e=q(s); return e ? e.textContent.trim().slice(0,80) : null; };
    return {
      title: document.title,
      kpiCap: txt('#kpi-cap'), kpiCapD: txt('#kpi-cap-d'),
      kpiEnts: txt('#kpi-ents'), kpiCr5: txt('#kpi-cr5'), kpiCr5D: txt('#kpi-cr5-d'),
      kpiRoute: txt('#kpi-route'), kpiCov: txt('#kpi-cov'),
      groupRows: document.querySelectorAll('#tb-group tr[data-group]').length,
      unitRows: document.querySelectorAll('#tb-unit tr[data-unit]').length,
      projRows: document.querySelectorAll('#tb-proj tr[data-proj]').length,
      srcRows: document.querySelectorAll('#tb-src tr').length,
      gapRows: document.querySelectorAll('#tb-gap tr').length,
      benchRows: document.querySelectorAll('#tb-bench tr').length,
      checkRows: document.querySelectorAll('#tb-check tr').length,
      mapBubbles: document.querySelectorAll('#map .bub').length,
      mapProvs: document.querySelectorAll('#map .prov').length,
      barRows: document.querySelectorAll('#bar-group .bar-row').length,
      provRows: document.querySelectorAll('#stack-prov .bar-row').length,
      donutPaths: document.querySelectorAll('#donut-route path').length,
      pipeCols: document.querySelectorAll('#pipe .pcol').length,
      yearChart: document.querySelectorAll('#year-chart svg').length,
      regionRows: document.querySelectorAll('#bar-region .bar-row').length,
      gradeRows: document.querySelectorAll('#bar-grade .bar-row').length,
    };
  })()`);
  console.log('=== 初始渲染 ===');
  console.log(JSON.stringify(checks, null, 1));

  // 交互测试：切口径 -> 筛省 -> 开抽屉
  const inter = await evalJs(`(async () => {
    const out = {};
    const $ = s => document.querySelector(s);
    // 1) 切到 approved 口径
    const b = document.querySelector('.seg button[data-basis="approved"]');
    if (b) { b.click(); }
    await new Promise(r=>setTimeout(r,400));
    out.afterApproved = { cap: $('#kpi-cap').textContent.trim(), units: $('#unit-count').textContent.trim() };
    // 回到 design
    document.querySelector('.seg button[data-basis="design"]').click();
    await new Promise(r=>setTimeout(r,400));
    // 2) 省份筛选
    const sel = $('#f-prov');
    sel.value = '内蒙古自治区';
    sel.dispatchEvent(new Event('change'));
    await new Promise(r=>setTimeout(r,500));
    out.afterProvFilter = { cap: $('#kpi-cap').textContent.trim(), units: $('#unit-count').textContent.trim(),
                            filters: $('#active-filters').textContent.trim().slice(0,60) };
    // 3) 重置
    $('#f-reset').click();
    await new Promise(r=>setTimeout(r,500));
    out.afterReset = { cap: $('#kpi-cap').textContent.trim() };
    // 4) 打开集团抽屉
    const gr = document.querySelector('#tb-group tr[data-group]');
    gr.click();
    await new Promise(r=>setTimeout(r,300));
    out.drawerOpen = $('#drawer').classList.contains('on');
    out.drawerLen = $('#drawer-body').textContent.length;
    out.drawerSnippet = $('#drawer-body').textContent.replace(/\\s+/g,' ').slice(0,120);
    $('#drawer-x').click();
    // 5) 打开基地抽屉（地图气泡）
    const bub = document.querySelector('#map .bub');
    if (bub) { bub.dispatchEvent(new MouseEvent('click',{bubbles:true})); await new Promise(r=>setTimeout(r,300)); }
    out.plantDrawerOpen = $('#drawer').classList.contains('on');
    out.plantDrawerLen = $('#drawer-body').textContent.length;
    out.plantSnippet = $('#drawer-body').textContent.replace(/\\s+/g,' ').slice(0,120);
    $('#drawer-x').click();
    // 6) 项目抽屉
    const pr = document.querySelector('#tb-proj tr[data-proj]');
    if (pr) { pr.click(); await new Promise(r=>setTimeout(r,300)); }
    out.projDrawerLen = $('#drawer-body').textContent.length;
    out.hasTimeline = !!document.querySelector('#drawer-body .tl');
    $('#drawer-x').click();
    // 7) 标签页切换
    const tabs = [...document.querySelectorAll('.tab')];
    out.tabCount = tabs.length;
    tabs[2].click(); await new Promise(r=>setTimeout(r,150));
    out.tab3Visible = !$('#tab-company').classList.contains('hide');
    return out;
  })()`);
  console.log('\n=== 交互测试 ===');
  console.log(JSON.stringify(inter, null, 1));

  console.log('\n=== 控制台/异常 ===');
  console.log(logs.length ? logs.join('\n') : '(无错误)');
  ws.close();
  process.exit(0);
})().catch(e => { console.error('ERR', e); process.exit(1); });
