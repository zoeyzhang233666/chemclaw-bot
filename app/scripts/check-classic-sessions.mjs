import assert from 'node:assert/strict'
import { setTimeout as sleep } from 'node:timers/promises'

const selection = "JSON.parse(localStorage.getItem('dsh.sessions.current'))?.sessionId"
const classic = "document.querySelector('.bt-classic-settings')"
const transcript = "document.querySelector('[data-conversation-scroll]')?.innerText ?? ''"
const editor = "[...document.querySelectorAll('[role=textbox][contenteditable=true], textarea')].filter(node => !node.closest('.bt-side')).at(-1)"
const visible = marker => `(${transcript}).includes(${JSON.stringify(marker)})`
const sessionRow = id => `[data-row-key="session:${id}"]`

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
    if (selector === sessionRow(id) && !await evaluate(`Boolean(document.querySelector(${JSON.stringify(selector)}))`)) {
      await evaluate(`document.querySelectorAll('[data-row-key^="overflow:"][aria-expanded=false]').forEach(button => button.click())`)
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
  const history = id => evaluate(session('events', { address: { kind: 'session', sessionId: id }, maxMessages: 30 })).then(JSON.stringify)
  return { evaluate, until, bot, session, current, click, show, send, waitRunning, history }
}

export async function checkClassicSessions(cdp) {
  const { evaluate, until, bot, session, current, click, show, send, waitRunning, history } = windowChecks(cdp)
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
  console.log('check-packed: Classic Session isolation, background streams, and explicit team history passed')
  return { id: b, marker: bText, other: aText }
}

export async function checkClassicRestart(cdp, { id, marker, other }) {
  const { evaluate, until, history } = windowChecks(cdp)
  await until(classic, 'restored Classic mode')
  await until(`${selection} === ${JSON.stringify(id)} && ${visible(`收到：${marker}`)}`, 'restored native selection and reply')
  await until("document.querySelector('[data-classic-native-view]')?.innerText.includes('测试合计')", 'restored native card')
  assert.equal(await evaluate(visible(other)), false)
  assert.ok((await history(id)).includes(marker))
  console.log('check-packed: Classic mode restored its native Session after app restart')
}
