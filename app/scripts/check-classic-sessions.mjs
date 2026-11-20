import assert from 'node:assert/strict'
import { setTimeout as sleep } from 'node:timers/promises'

const selection = "JSON.parse(localStorage.getItem('dsh.sessions.current'))?.sessionId"
const classic = "document.querySelector('.bt-classic-settings')"
const transcript = "document.querySelector('[data-conversation-scroll]')?.innerText ?? ''"
const editor = "[...document.querySelectorAll('[role=textbox][contenteditable=true], textarea')].filter(node => !node.closest('.bt-side')).at(-1)"
const visible = marker => `(${transcript}).includes(${JSON.stringify(marker)})`
const sessionRow = id => `[data-row-key="session:${id}"]`
const diagram = title => `([...document.querySelectorAll('[data-genui-diagram]')].find(figure => figure.textContent.includes(${JSON.stringify(title)}))?.querySelector('svg'))`
const svgImage = "document.querySelector('[data-genui-svg] img[alt=\"合成设备剖面\"]')"
const svgReady = `${svgImage}?.complete && ${svgImage}.naturalWidth > 0 && ${svgImage}.src.startsWith('data:image/svg+xml')`
const fits = selector => `(() => {
  const graphic = ${selector};
  if (!graphic) return false;
  const { left, right, width, height } = graphic.getBoundingClientRect();
  const { left: frameLeft, right: frameRight } = graphic.closest('[data-genui]').getBoundingClientRect();
  return width > 100 && height > 30 && left >= frameLeft - 1 && right <= frameRight + 1;
})()`

function windowChecks(cdp) {
  const evaluate = async expression => {
    const { result, exceptionDetails } = await cdp.call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (exceptionDetails) throw new Error(exceptionDetails.exception?.description ?? exceptionDetails.text)
    return result.value
  }
  const until = async (expression, label) => {
    console.log(`check-classic: waiting for ${label}`)
    const end = Date.now() + 40_000
    while (Date.now() < end) {
      if (await evaluate(`(async () => Boolean(${expression}))()`)) return
      await sleep(150)
    }
    throw new Error(`Timed out waiting for ${label}`)
  }
  const json = (path, body) => `fetch(${JSON.stringify(path)}, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: ${JSON.stringify(JSON.stringify(body))}
  }).then(r => r.json()).then(r => {
    const result = r.result ?? r
    if (!result.ok) throw new Error(result.error.message)
    return result.value
  })`
  const bot = (endpoint, payload = {}) => json('/api/bot', { endpoint, payload })
  const session = (method, request) => json(`/api/session/${method}`, {
    type: 'client-request', rpcId: crypto.randomUUID(),
    method: `session/${method}`, payload: { args: { [method === 'list' ? '_request' : 'request']: request } },
  })
  const current = () => evaluate(selection)
  const click = async selector => {
    await until(`document.querySelector(${JSON.stringify(selector)})`, selector)
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`)
  }
  const show = async (id, selector = sessionRow(id)) => {
    if (selector === sessionRow(id)) {
      await until(`(() => {
        if (document.querySelector(${JSON.stringify(selector)})) return true;
        document.querySelectorAll('[data-row-key^="workspace:"][aria-expanded=false], button[data-row-key^="overflow:"][aria-expanded=false]').forEach(row => row.click());
        return false;
      })()`, `reveal Classic history for ${id}`)
    }
    await click(selector)
    await until(`${selection} === ${JSON.stringify(id)}`, `selection of ${id}`)
  }
  const send = async message => {
    await until(editor, 'the active composer')
    await evaluate(`${editor}.focus()`)
    await cdp.call('Input.insertText', { text: message })
    await sleep(100)
    for (const type of ['keyDown', 'keyUp']) {
      await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    }
  }
  const running = id => `${session('state', { sessionId: id })}.then(value => value.running)`
  const waitRunning = (id, active) => until(`await (${running(id)}) === ${active}`, `${id} running=${active}`)
  const history = (id, maxMessages = 30) => evaluate(session('events', { address: { kind: 'session', sessionId: id }, maxMessages })).then(JSON.stringify)
  return { evaluate, until, bot, session, current, click, show, send, waitRunning, history }
}

export async function checkClassicSessions(cdp) {
  const { evaluate, until, bot, session, current, click, show, send, waitRunning, history } = windowChecks(cdp)
  const preview = async (graphic, inline = false) => {
    const modal = "document.querySelector('.bt-genui-preview[open]')"
    const copy = `${modal}?.querySelector('.bt-genui-preview-stage > div')?.shadowRoot?.firstElementChild`
    const footer = `${graphic}.closest('[data-genui-artifact]')?.querySelector('[data-genui-export]')`
    const control = `${footer}?.querySelector('.bt-genui-enlarge')`
    await until(`${control}?.nextElementSibling?.getAttribute('aria-haspopup') === 'menu'`, 'the vector preview control to the left of download')
    assert.ok(await evaluate(`${control}.getBoundingClientRect().top >= ${graphic}.getBoundingClientRect().bottom`))
    await evaluate(inline ? `${graphic}.click()` : `${control}.click()`)
    await until(copy, 'the original vector in a modal')
    assert.ok(await evaluate(`(() => {
      const original = ${graphic};
      const cloned = ${copy};
      return original.localName === cloned.localName && (original.src ? original.src === cloned.src
        : original.getAttribute('viewBox') === cloned.getAttribute('viewBox') && cloned.querySelector('marker')
          && cloned.querySelector('[data-bt-diagram-labels]')?.textContent === original.querySelector('[data-bt-diagram-labels]')?.textContent);
    })()`))
    const initial = await evaluate(`${copy}.getBoundingClientRect().width`)
    await evaluate(`${modal}.querySelector('button:nth-last-child(2)').click()`)
    await until(`${copy}?.getBoundingClientRect().width > ${initial} * 1.4`, 'vector scaling without changing the source')
    for (const type of ['keyDown', 'keyUp']) {
      await cdp.call('Input.dispatchKeyEvent', { type, key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
    }
    await until(`!${modal} && document.activeElement === ${control}`, 'Escape closes the modal and restores focus')
  }
  const checkDiagramNode = async graphic => {
    const node = `${graphic}.querySelector('[role=button][aria-label="生产与开工"]')`
    await until(node, 'an interactive GenUI diagram node')
    await until(`${graphic}.lastElementChild.getAttribute('display') === 'none' && ${graphic}.querySelector('[data-bt-diagram-node]')`, 'business diagram colors and a hidden software legend')
    await until(`${graphic}.querySelector('path[marker-end][stroke-linejoin=round]') && ${graphic}.querySelector('[data-bt-diagram-labels]')?.textContent === '待核验'`, 'rounded connectors and collision-adjusted edge labels')
    assert.ok(await evaluate(`(() => {
      const graphic = ${graphic};
      const label = graphic.querySelector('[data-bt-diagram-labels] rect').getBBox();
      return [...graphic.querySelectorAll('g[role=button]')].every(node => {
        const box = node.firstElementChild.firstElementChild.getBBox();
        return box.x + box.width <= label.x || label.x + label.width <= box.x || box.y + box.height <= label.y || label.y + label.height <= box.y;
      });
    })()`))
    await evaluate(`${node}.dispatchEvent(new MouseEvent('click', { bubbles: true }))`)
    await until(`${node}.getAttribute('aria-pressed') === 'true' && ${graphic}.parentElement.querySelector('[aria-live=polite]')?.textContent.includes('区分设计产能和实际开工')`, 'inline diagram node details')
    assert.equal(await evaluate("Boolean(document.querySelector('.bt-genui-preview[open]'))"), false)
  }
  const checkFencePresentation = async id => {
    const rawVisible = `[...document.querySelectorAll('[data-code-block-content] pre')].some(node =>
      /合成成因矢量图|合成损坏图|viewBox/u.test(node.textContent) && node.getBoundingClientRect().height > 0)`
    await send('GenUI check streamed SVG')
    await until(`${visible('先显示行情成因。')} && document.querySelector('.bt-genui-status:not([data-unavailable])')`, 'streaming SVG shows a compact status alongside prose')
    assert.equal(await evaluate(rawVisible), false)
    await until("document.querySelector('[data-genui-svg] img[alt=合成成因矢量图]')?.naturalWidth > 0", 'SVG alias repaired by the host and rendered')
    await waitRunning(id, false)
    const width = await evaluate("document.querySelector('[data-genui-svg] img[alt=合成成因矢量图]').getBoundingClientRect().width")
    assert.ok(width > 0 && width <= 220, 'a simple SVG stays compact inline')
    assert.equal(await evaluate(rawVisible), false)
    assert.equal(await evaluate(visible('const readableExample = 2')), true)
    await send('GenUI check broken SVG')
    await until(`${visible('图形失败时保留正文。')} && ${diagram('合成恢复流程')}`, 'rejected SVG stays out of the reply, and flow recovers automatically')
    await waitRunning(id, false)
    assert.equal(await evaluate(rawVisible), false)
    assert.equal(await evaluate(visible('<chatml_chart_demo>')), false)
    assert.equal(await evaluate("[...document.querySelectorAll('.bt-genui-status[data-unavailable]:not([hidden])')].some(node => node.getClientRects().length > 0)"), false)
  }
  const checkCapacity = async id => {
    await send('查询合成产能分布')
    await until(`${visible('合成产能正文')} && [...document.querySelectorAll('.bt-widget-metric')].some(node => node.textContent.includes('沿海产能')) && document.querySelector('.bt-chart-svg .bt-chart-mark')`, 'native capacity metrics, bar chart and ordinary text')
    await waitRunning(id, false)
    assert.equal((await history(id)).includes('The answer is still missing these inline views: metric'), false)
  }
  const checkSpotHistory = async id => {
    await send('纯碱最近一个月现货价格')
    await until(`${visible('合成现货正文')} && [...document.querySelectorAll('.bt-widget-metric')].some(node => node.textContent.includes('合成轻质现货均价')) && [...document.querySelectorAll('.bt-chart-svg .bt-chart-line')].some(node => (node.getAttribute('d').match(/L/g) ?? []).length === 2)`, 'native spot metric and plotted three-point line')
    await waitRunning(id, false)
    assert.equal(await evaluate(visible('错误的报价关系图')), false)
  }
  const checkMarketFollowup = async id => {
    await send('甲醇价格')
    await until(`${visible('合成甲醇正文')} && [...document.querySelectorAll('.bt-widget-metric')].some(node => node.textContent.includes('合成甲醇最新均价')) && ${visible('合成甲醇均价走势')}`, 'bare methanol lookup has both the native metric and native line')
    await waitRunning(id, false)
    await send('沥青产量')
    await until(`${visible('合成沥青当月总产量')} && ${visible('合成集团产量')} && ${visible('合成地区产量')} && ${visible('分集团明细')}`, 'production metric and separate comparison charts alongside detail')
    await waitRunning(id, false)
    const detail = "Array.from(document.querySelectorAll('.bt-widget-table-details')).find(node => node.querySelector('summary').textContent === '分集团明细')"
    assert.ok(await evaluate(`(() => {
      const metric = [...document.querySelectorAll('.bt-widget-metric')].find(node => node.textContent.includes('合成沥青当月总产量'));
      const detail = ${detail};
      return Boolean(metric && detail && !detail.open && (metric.compareDocumentPosition(detail) & Node.DOCUMENT_POSITION_FOLLOWING));
    })()`), 'the native production overview precedes detailed rows')
    await evaluate(`${detail}.querySelector('summary').click()`)
    await until(`${detail}.open && ${detail}.querySelector('tbody').textContent.includes('100')`, 'production evidence rows can be opened')
    await send('解释合成沥青传导机制')
    await until(`[...document.querySelectorAll('[data-genui-diagram] svg')].filter(svg => svg.querySelector('title')?.textContent === '合成沥青传导修复图').some(svg => !svg.closest('figure').querySelector('.bt-genui-diagram-fallback') && new Set([...svg.querySelectorAll('g[role=button]')].map(node => { const box = node.getBBox(); return box.x + ',' + box.y })).size === 4)`, 'overlapping source coordinates render as four separately placed nodes')
    await waitRunning(id, false)
  }
  const checkSemanticVisuals = async id => {
    const graph = label => `[...document.querySelectorAll('svg[data-chemclaw-flow]')].find(node => node.textContent.includes(${JSON.stringify(label)}))`
    await send('解释伊美关系如何影响原油价格')
    const mechanism = graph('预期可供数量下降')
    await until(`${mechanism}?.querySelectorAll('[data-shared]').length === 2`, 'a price chart does not satisfy an explicit mechanism question')
    await waitRunning(id, false)
    assert.ok(await evaluate(`(() => {
      const row = [...document.querySelectorAll('.bt-metric-row')].find(node => node.textContent.includes('示例运费'));
      const top = row?.firstElementChild.getBoundingClientRect().top;
      return row?.children.length === 3 && [...row.children].every(node => Math.abs(node.getBoundingClientRect().top - top) < 2);
    })()`), 'consecutive metric cards occupy a single wide row')
    const zoom = `(${mechanism}).closest('figure').querySelector('.bt-genui-enlarge')`
    await until(zoom, 'the native relationship diagram exposes vector preview')
    await evaluate(`${zoom}.click()`)
    await until("document.querySelector('.bt-genui-preview[open] .bt-genui-preview-stage > div')?.shadowRoot?.querySelector('svg[data-chemclaw-flow] [data-shared]')", 'native shared routes remain vectors in the preview')
    await evaluate("document.querySelector('.bt-genui-preview[open]').close()")
    await send('沥青库存')
    await until(`${visible('合成最新库存')} && [...document.querySelectorAll('.bt-view')].some(node => node.textContent.includes('合成最新库存') && node.querySelector('.bt-chart-line'))`, 'a table-only inventory response recovers a metric and a native trend')
    await waitRunning(id, false)
    await send('沥青产业链')
    await until(`${graph('装置加工')}?.querySelectorAll('[data-shared]').length === 2`, 'unsolicited Mermaid is replaced with a connected SVG')
    await waitRunning(id, false)
    assert.equal(await evaluate(visible('subgraph UP')), false)
    await send('合成多路径关系图')
    const dense = graph('待验证旁路')
    await until(`${dense}?.querySelectorAll('.bt-flow-edge-label').length === 7`, 'dense diagram shows all seven edge labels')
    assert.ok(await evaluate(`(() => {
      const svg = ${dense};
      const labels = [...svg.querySelectorAll('.bt-flow-edge-label rect')].map(node => node.getBoundingClientRect());
      const cards = [...svg.querySelectorAll('.bt-flow-step rect')].map(node => node.getBoundingClientRect());
      const overlaps = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
      return labels.every((box, i) => [...labels.slice(0, i), ...cards].every(peer => !overlaps(box, peer)))
        && Boolean([...svg.querySelectorAll('.bt-flow-connection path')].find(node => node.getAttribute('d').includes(' Q ')));
    })()`), 'native labels avoid one another and card boxes, and elbows are rounded')
    await waitRunning(id, false)
    await send('合成价格走势及事件窗口')
    await until(`${visible('合成窗口最新价')} && ${visible('合成报价事件窗口')} && [...document.querySelectorAll('.bt-view')].some(node => node.textContent.includes('合成窗口最新价') && node.querySelector('.bt-chart-line'))`, 'event-window SVG accompanies the native metric and overview line')
    await waitRunning(id, false)
  }
  const roster = await evaluate(bot('state'))
  const expert = roster.bots.find(item => item.id === roster.mainBotId)
  const expertSession = expert.sessionId
  const room = await evaluate(bot('create-room', {
    name: 'Isolation fixture', members: [expert.id, roster.bots.find(item => item.id !== expert.id).id], admin: expert.id,
  }))
  const owned = state => new Set([
    ...state.bots.flatMap(item => [item.id, item.sessionId, ...item.parts]),
    ...state.rooms.flatMap(item => [item.id, ...item.parts]),
    ...state.agents.flatMap(item => item.sessions),
  ])
  const assertNative = async id => assert.ok(id && !owned(await evaluate(bot('state'))).has(id), `Expected a native Session, got ${id}`)
  const enterClassic = async () => {
    await click('button.bt-connect-foot')
    await until(classic, 'Classic mode')
    await assertNative(await current())
  }
  const create = async () => {
    const before = cdp.sessionCreates.length
    await click('button[class$=_newSession]')
    const end = Date.now() + 40_000
    while (cdp.sessionCreates.length === before && Date.now() < end) await sleep(100)
    assert.ok(cdp.sessionCreates.length > before, 'Native New Session did not answer')
    const { body } = await cdp.call('Network.getResponseBody', { requestId: cdp.sessionCreates[before] })
    const result = JSON.parse(body).result
    assert.equal(result.ok, true, result.error?.message)
    const id = result.value.sessionId
    await until(`${selection} === ${JSON.stringify(id)}`, `the created Session ${id}`)
    await assertNative(id)
    return id
  }
  const sendClassic = async (id, marker) => {
    await send(marker)
    await until(visible(`收到：${marker}`), `native reply to ${marker}`)
    await waitRunning(id, false)
    assert.equal(await current(), id)
    assert.ok((await history(id)).includes(marker), `Missing durable turn in ${id}`)
  }
  const aText = 'isolation-158-alpha'
  const bText = 'isolation-158-bravo'
  const expertText = 'isolation-158-slow-expert'
  const roomText = 'isolation-158-slow-room'
  const expertReply = 'isolation-158-expert-output'
  const roomReply = 'isolation-158-room-output'

  await show(expertSession, `[data-bot-id="${expert.id}"]`)
  await send(expertText)
  await until(visible(expertReply), 'expert streaming')
  await enterClassic()
  const a = await create()
  await sendClassic(a, aText)
  await waitRunning(expertSession, false)
  assert.equal(await current(), a)
  assert.ok((await history(expertSession)).includes(expertReply))
  assert.ok(!(await history(a)).includes(expertReply))
  assert.equal(await evaluate(visible(expertReply)), false)

  const b = await create()
  assert.notEqual(b, a, 'New Session B reused the sent Session A')
  await sendClassic(b, bText)
  assert.equal(await evaluate(visible(aText)), false)
  assert.ok(!(await history(b)).includes(aText))
  assert.ok(!(await history(a)).includes(bText))

  // The blank room is a valid workspace member, so a named native create would
  // reuse it on the old code. It must stay blank while DSH mints another ID.
  const createRequest = { workspaceId: roster.workspaceId, sessionId: room.id }
  const roomBlank = (await evaluate(session('list', {}))).items.find(item => item.sessionId === room.id)?.blank
  assert.equal(roomBlank, true)
  await assertNative((await evaluate(session('create', createRequest))).sessionId)

  await click('.bt-return')
  await show(room.id, `[data-room-id="${room.id}"]`)
  await send(roomText)
  await until(visible(roomReply), 'group member streaming')
  await enterClassic()
  assert.equal(await current(), b)
  await waitRunning(room.id, false)
  assert.equal(await current(), b)
  assert.ok((await history(room.id)).includes(roomReply))
  assert.equal(await evaluate(visible(roomReply)), false)
  assert.ok(!(await history(b)).includes(roomReply))
  const fromRoom = await create()
  assert.notEqual(fromRoom, b)
  await sendClassic(fromRoom, 'isolation-158-from-room')
  assert.ok(!(await history(fromRoom)).includes(roomReply))
  await send(`上下文里有 ${bText}`)
  await until(visible(`上下文里没有「${bText}」。`), 'the model cannot see the other native Session’s context')
  await waitRunning(fromRoom, false)

  // Explicit history navigation and submission keep their original destinations.
  await show(expertSession)
  await until(visible(expertReply), 'existing expert history in Classic mode')
  await send('isolation-158-expert-followup')
  await until(visible('收到：isolation-158-expert-followup'), 'expert continuation in Classic mode')
  assert.equal(await current(), expertSession)
  assert.ok((await history(expertSession)).includes('isolation-158-expert-followup'))
  await show(room.id)
  await until(visible(roomText), 'existing group history in Classic mode')
  await send('isolation-158-room-followup')
  await until(visible('isolation-158-room-followup'), 'group continuation in Classic mode')
  await waitRunning(room.id, false)
  assert.equal(await current(), room.id)
  assert.ok((await history(room.id)).includes('isolation-158-room-followup'))
  await show(a)
  await until(visible(`收到：${aText}`), 'reopened native Session A')
  assert.equal(await evaluate(visible(bText)), false)
  await show(b)
  await until(visible(`收到：${bText}`), 'reopened native Session B')
  assert.equal(await evaluate(visible(aText)), false)
  const paused = new Set()
  const unobserve = cdp.observe('Fetch.requestPaused', ({ request, requestId }) => {
    if (request.postData && JSON.parse(request.postData).endpoint === 'state') paused.add(requestId)
    else void cdp.call('Fetch.continueRequest', { requestId }).catch(() => {})
  })
  await cdp.call('Fetch.enable', { patterns: [{ urlPattern: '*/api/bot' }] })
  try {
    await evaluate('window.beforeClassicReload = true')
    await cdp.call('Page.reload')
    await until(`!window.beforeClassicReload && ${classic} && ${visible(bText)}`, 'Classic Session B with delayed roster')
    const deadline = Date.now() + 5000
    while (paused.size === 0 && Date.now() < deadline) await sleep(100)
    assert.ok(paused.size > 0, 'Expected a roster request to be held during reload')
    await click('.bt-return')
    await click('button.bt-connect-foot')
    await until(classic, 'Classic mode before the roster responds')
    assert.equal(await current(), b)
    await evaluate("localStorage.removeItem('chemclaw-bot:agent-sessions')")
  } finally {
    unobserve()
    await cdp.call('Fetch.disable')
  }
  await until("localStorage.getItem('chemclaw-bot:agent-sessions') !== null", 'the delayed roster to be applied')
  // Give the sidebar fallback time to run after the delayed roster arrives.
  await sleep(650)
  assert.equal(await current(), b)
  assert.equal(await evaluate(visible(bText)), true)
  const card = "document.querySelector('[data-classic-native-view]')"
  await send('classic-native-ready')
  await until(`${card}?.innerText.includes('测试合计') && ${visible('经典正文结论：测试回答结束。')}`, 'native card and final Markdown together')
  await waitRunning(b, false)
  assert.equal(await current(), b)
  assert.equal(await evaluate(visible('经典正文开头：以下是测试结果。')), true)
  assert.ok((await history(b)).includes('list_bots'), 'missing the ordinary DSH tool call')
  assert.equal(await evaluate(`${card}.querySelector('pre, details') !== null`), false)
  assert.equal(await evaluate(`${card}.innerText.includes('show_view · call_')`), false)
  assert.equal(await evaluate(`${card}.innerText.includes('Inspect')`), false)
  const process = "[...document.querySelectorAll('button[data-turn-process]')].at(-1)"
  const turn = await evaluate(`${process}.dataset.turnProcess`)
  await evaluate(`${process}.click()`)
  const toolGroups = `[data-chat-turn="${turn}"] button[data-process-activity][aria-expanded=false]`
  await until(`${visible('list_bots')} || document.querySelector(${JSON.stringify(toolGroups)})`, 'tool groups available')
  await evaluate(`document.querySelectorAll(${JSON.stringify(toolGroups)}).forEach(button => button.click())`)
  await until(visible('list_bots'), 'ordinary DSH tool row expands in work details')
  assert.equal(await evaluate("document.querySelectorAll('[data-classic-native-view]').length"), 1)
  await evaluate(`${process}.click()`)
  const slider = `${card}.querySelector('input[type=range]')`
  await evaluate(`(() => {
    const input = ${slider}
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '4')
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })()`)
  await until(`${card}.innerText.includes('12')`, 'local calculator recalculation')
  await send('classic-native-invalid')
  await until(`${visible('原生图卡未能显示。')} || ${visible('The native card could not be displayed.')}`, 'a rejected card has a readable status')
  await waitRunning(b, false)
  assert.equal(await evaluate("document.querySelectorAll('[data-classic-native-view]').length"), 1)
  assert.equal(await current(), b)
  await send('GenUI check timeline')
  await until(`${visible('Synthetic renderer verification.')} && ${visible('Pilot complete')}`, 'GenUI timeline and ordinary Markdown together')
  await waitRunning(b, false)
  assert.equal(await current(), b)
  await send('GenUI check bundled skill')
  await until(visible('Bundled GenUI skill loaded.'), 'the registered upstream GenUI skill can be loaded by DSH')
  await waitRunning(b, false)
  await checkCapacity(b)
  await checkSpotHistory(b)
  await checkFencePresentation(b)
  await send('GenUI check marketstats')
  const metrics = "[...document.querySelectorAll('[data-genui]')].find(node => node.innerText.includes('Synthetic market metrics'))"
  await until(`${metrics}?.querySelectorAll('[class$="_statValue"]').length === 4`, 'GenUI market metrics in Classic')
  const metricsFit = `(() => {
    const metrics = ${metrics};
    return [...metrics.querySelectorAll('[class$="_statValue"]')].every(node =>
      getComputedStyle(node).whiteSpace === 'nowrap' && node.scrollWidth <= node.clientWidth + 1);
  })()`
  await until(metricsFit, 'four intact market figures in Classic')
  await cdp.call('Emulation.setDeviceMetricsOverride', { width: 780, height: 860, deviceScaleFactor: 1, mobile: false })
  try { await until(metricsFit, 'market figures stay intact in a narrow window') }
  finally { await cdp.call('Emulation.clearDeviceMetricsOverride') }
  await waitRunning(b, false)
  const supply = diagram('合成供应链流程')
  await send('梳理合成供应链')
  await until(`${supply}?.textContent.includes('库存变化') && ${visible('流程图正文：库存环节仍待核验。')}`, 'automatic GenUI diagram and Markdown in a Classic Session')
  await waitRunning(b, false)
  await checkDiagramNode(supply)
  await preview(supply)
  await send('解释合成设备剖面结构')
  await until(`${svgReady} && ${visible('剖面正文')}`, 'automatic GenUI SVG image and text in Classic')
  await waitRunning(b, false)
  await preview(svgImage, true)
  await send('为什么合成分布会是这样？')
  await until(`${diagram('合成分布成因图')} && ${visible('合成原因正文')}`, 'semantic follow-up adds a GenUI diagram after an unrelated tab')
  await waitRunning(b, false)
  await send('我想知道合成产业链结构')
  await until("[...document.querySelectorAll('svg[data-chemclaw-flow] title')].some(node => node.textContent === '合成产业链结构图')", 'Mermaid validation redirects to native SVG')
  assert.equal(await evaluate("Boolean(document.querySelector('[data-genui] svg[id^=mermaid]'))"), false)
  await waitRunning(b, false)
  await send('旧版流程调用验收')
  await until(`${visible('原生流程备用渲染已交付')} && document.querySelector('svg[data-chemclaw-flow]')`, 'legacy show_view flow remains available as a fallback')
  await waitRunning(b, false)
  await cdp.call('Emulation.setDeviceMetricsOverride', { width: 560, height: 860, deviceScaleFactor: 1, mobile: false })
  try {
    await until(`${fits(supply)} && ${fits(svgImage)}`, 'both original GenUI components fit a narrow Classic reply')
  } finally { await cdp.call('Emulation.clearDeviceMetricsOverride') }
  const marketSession = await create()
  await checkMarketFollowup(marketSession)
  await checkSemanticVisuals(marketSession)
  await show(b)
  await click('.bt-return')
  await show(expertSession, `[data-bot-id="${expert.id}"]`)
  await checkCapacity(expertSession)
  await checkSpotHistory(expertSession)
  await checkMarketFollowup(expertSession)
  await checkSemanticVisuals(expertSession)
  await checkFencePresentation(expertSession)
  await send('GenUI check marketstats')
  await until(`${metrics}?.closest('.bt-rich-reply')`, 'expert GenUI outside the speech bubble')
  assert.equal(await evaluate(`Boolean(${metrics}.closest('.bt-bubble'))`), false)
  await waitRunning(expertSession, false)
  await send('梳理合成供应链')
  await until(`${supply}?.closest('.bt-rich-reply') && ${visible('流程图正文')}`, 'GenUI diagram outside the expert text bubble')
  await waitRunning(expertSession, false)
  await checkDiagramNode(supply)
  await preview(supply)
  await send('解释合成设备剖面结构')
  await until(`${svgReady} && ${svgImage}?.closest('.bt-rich-reply') && ${visible('剖面正文')}`, 'GenUI SVG image outside the expert text bubble')
  await waitRunning(expertSession, false)
  await preview(svgImage, true)
  await cdp.call('Emulation.setDeviceMetricsOverride', { width: 560, height: 860, deviceScaleFactor: 1, mobile: false })
  try { await until(`${fits(supply)} && ${fits(svgImage)}`, 'both original GenUI components fit a narrow expert reply') }
  finally { await cdp.call('Emulation.clearDeviceMetricsOverride') }
  const legacy = "document.querySelector('iframe[title=\"旧版 SVG 样例\"]')"
  await send('视图旧SVG')
  await until(`${legacy}?.srcdoc.includes('<svg')`, 'legacy sandboxed SVG in the expert reply')
  await waitRunning(expertSession, false)
  await enterClassic()
  assert.equal(await current(), b)
  await show(expertSession)
  await until(`${supply} && ${svgReady} && ${legacy}?.srcdoc.includes('<svg')`, 'GenUI diagrams, SVG images and legacy SVG replay in Classic expert history')
  assert.equal(await evaluate(visible('流程图正文：库存环节仍待核验。')), true)
  await click('.bt-return')
  await show(room.id, `[data-room-id="${room.id}"]`)
  await send('展示合成流程图')
  await until(`${supply}?.textContent.includes('库存变化')`, 'committed GenUI diagram in the expert group reply')
  await waitRunning(room.id, false)
  await send('解释合成设备剖面结构')
  await until(svgReady, 'committed GenUI SVG in the expert group reply')
  await waitRunning(room.id, false)
  await enterClassic()
  await show(room.id)
  await until(`${supply}?.textContent.includes('库存变化') && ${svgReady}`, 'both committed group GenUI components replay in Classic')
  await show(b)
  console.log('check-packed: Classic Session isolation, background streams, and explicit team history passed')
  return { id: b, marker: bText, other: aText }
}

export async function checkClassicRestart(cdp, { id, marker, other }) {
  const { evaluate, until, history } = windowChecks(cdp)
  await until(classic, 'restored Classic mode')
  await until(`${selection} === ${JSON.stringify(id)} && ${visible(`收到：${marker}`)}`, 'restored native selection and reply')
  await until("document.querySelector('[data-classic-native-view]')?.innerText.includes('测试合计')", 'restored native card')
  await until(`${diagram('合成供应链流程')} && ${svgReady}`, 'restored GenUI diagram and SVG')
  assert.equal(await evaluate(visible(other)), false)
  assert.ok((await history(id, 100)).includes(marker))
  console.log('check-packed: Classic mode restored its native Session after app restart')
}
