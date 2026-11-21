import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { test } from 'node:test'
import { createRuntime } from '../index.js'
import { fakeContext } from './fake-ctx.js'
import { adapters } from '../src/host/im/platforms/index.js'

// A platform adapter that records sends/edits and lets the test feed inbound
// messages, actions and statuses. `fail` makes send throw once per call queued.
// `quote` says the platform hands back quoted replies, so the host keeps what it
// sent; it is off by default, like most platforms.
const fakeAdapter = ({ buttons = true, quote = false, sendImage, sendFile } = {}) => {
  const sent = []
  const edited = []
  const typed = []
  const fails = []
  const jobs = []
  // Ids keep counting when a test empties `sent`, so a quoted id never names a
  // later message by accident.
  let nextMessage = 0
  const adapter = {
    id: 'fake',
    quote,
    sent,
    edited,
    typed,
    handlers: null,
    async check(fields) {
      if (fields.token === 'bad-token') throw new Error('platform refused the token')
      return { account: { id: 'bot1', name: '@fakebot' } }
    },
    connect(fields, env, handlers) {
      adapter.handlers = handlers
      adapter.env = env
      adapter.connects = (adapter.connects ?? 0) + 1
      handlers.onStatus({ state: 'ready', account: { id: 'bot1', name: '@fakebot' } })
      return {
        send: async (chat, body) => {
          const messageId = String(++nextMessage)
          sent.push({ chat, messageId, ...body })
          jobs.push(body)
          const next = fails.shift()
          if (next !== undefined) throw next
          return { messageId }
        },
        edit: async (chat, messageId, body) => { edited.push({ chat, messageId, ...body }) },
        ...(sendImage && { sendImage: async (chat, image) => {
          await sendImage(image)
          sent.push({ chat, image, messageId: String(++nextMessage) })
        } }),
        ...(sendFile && { sendFile: async (chat, file) => {
          await sendFile(file)
          sent.push({ chat, file, messageId: String(++nextMessage) })
        } }),
        typing: async (chat) => { typed.push(chat) },
        stop: () => { adapter.stopped = (adapter.stopped ?? 0) + 1 },
      }
    },
  }
  adapter.fails = fails
  adapter.jobs = jobs
  adapter.buttons = buttons
  return adapter
}

const TEAM = () => ({
  version: 1,
  mainBotIds: ['a'],
  bots: {
    a: { id: 'a', name: 'Chief', role: 'Boss', sessionId: 'a', createdAt: 1 },
    b: { id: 'b', name: 'Writer', role: 'Write', sessionId: 'b', createdAt: 2 },
  },
  rooms: { r1: { id: 'r1', name: 'Ops', members: ['a', 'b'], mode: 'everyone', admin: 'a', named: true, log: [], seq: 0 } },
  agents: {},
  exchanges: [],
  exchangeTurns: {},
  questions: {},
  prefs: {},
  revision: 0,
})

async function start({ platform = 'telegram', adapter, seed, services = {} } = {}) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-im-'))
  writeFileSync(join(home, 'state.json'), JSON.stringify(seed ?? TEAM()))
  const ctx = fakeContext({ services })
  const prompts = []
  let nextSession = 0
  const agents = new Map()
  const agentOf = id => {
    if (!agents.has(id)) agents.set(id, {
      id,
      session: { id, requestHeader: () => undefined },
      followup(message) { this.lastFollowup = message; this.followed = (this.followed ?? 0) + 1 },
      cancel() { this.cancelled = true },
      inbox: { nextStep: [], nextTurn: [], remove: () => false },
      async whenIdle() {},
    })
    return agents.get(id)
  }
  Object.assign(ctx, {
    llm: { listProviders: () => [] },
    workspaceRegistry: { get: () => undefined, resolveByPath: async () => undefined, create: async () => ({ id: 'w1' }), archiveSession: async () => {} },
    sessionTitle: { rename: async () => {} },
    sessionController: {
      create: async ({ sessionId = `member-${++nextSession}` }) => ({ sessionId }),
      prompt: async (request) => { prompts.push(request); return { ok: true } },
      resolveAgent: async sessionId => ({ agent: agentOf(sessionId) }),
      selectModel: async () => {},
    },
    sessions: { flush: async () => {} },
  })
  const fake = adapter ?? fakeAdapter()
  const real = adapters[platform]
  adapters[platform] = fake
  const rt = createRuntime(ctx, { home })
  const emitEvent = (sessionId, type, data) => {
    for (const listener of ctx.listeners.get('session/event') ?? []) {
      if (listener.length >= 2) listener({ id: sessionId }, { type, data, time: Date.now() })
    }
  }
  const fireApprovals = (request, next) => Promise.all((ctx.listeners.get('approval/request') ?? [])
    .map(listener => listener(request, next)))
  const stop = async () => {
    adapters[platform] = real
    await ctx.dispose()
    rmSync(home, { recursive: true, force: true, maxRetries: 5 })
  }
  const flush = async () => { await delay(10) }
  // The host echoes an IM prompt as a user/message whose source carries the request it
  // came in on; the plugin takes the chat that request belongs to as the turn's origin.
  const imTurn = (sessionId = 'a') => {
    const requestId = prompts.at(-1)?.requestId
    emitEvent(sessionId, 'turn/start', { turn: prompts.length })
    emitEvent(sessionId, 'user/message', { source: { kind: 'user', rpcId: requestId }, content: [{ type: 'text', text: 'from the chat' }] })
  }
  return { ctx, rt, home, fake, prompts, agents, agentOf, emitEvent, fireApprovals, imTurn, stop, flush, platform }
}

const FIELDS = { telegram: { token: 'tok-1234' }, dingtalk: { clientId: 'cli-1', clientSecret: 'sec-1234' } }
const add = (s, fields = FIELDS[s.platform]) => s.rt.imEndpoint('im-add', { platform: s.platform, botId: 'a', fields })
const dm = (s, senderId, text, extra = {}) => s.fake.handlers.onMessage({
  chat: { key: `dm-${senderId}`, kind: 'direct', title: senderId }, sender: { id: senderId, name: `User ${senderId}` }, text, ...extra,
})
const gm = (s, senderId, text, { mentioned = true, chat = { key: 'g1', kind: 'group', title: 'Group One' }, ...extra } = {}) => s.fake.handlers.onMessage({
  chat, sender: { id: senderId, name: `User ${senderId}` }, text, mentioned, ...extra,
})

test('two concurrent syncs start exactly one adapter', async (t) => {
  const s = await start()
  t.after(s.stop)
  await add(s)
  const conn = Object.values(s.rt.state.im.connections)[0]
  s.fake.connects = 0
  s.rt.state.im.connections[conn.id].enabled = false
  await s.rt.save()
  await s.flush()
  assert.equal(s.fake.stopped, 1)
  s.rt.state.im.connections[conn.id].enabled = true
  await Promise.all([s.rt.save(), s.rt.save()])
  await s.flush()
  assert.equal(s.fake.connects, 1)
  assert.equal(s.rt.imStatusView()[conn.id].state, 'ready')
})

test('im-update applies only the fields it is given and keeps the rest', async (t) => {
  const s = await start({ platform: 'feishu', adapter: fakeAdapter() })
  t.after(s.stop)
  const conn = await add(s, { domain: 'lark', appId: 'app-1', appSecret: 'sec-1' })
  const one = s.rt.state.im.connections[conn.id]
  assert.deepEqual(one.settings, { domain: 'lark', appId: 'app-1' })
  await s.rt.imEndpoint('im-update', { id: conn.id, fields: { appSecret: 'sec-2' } })
  assert.deepEqual(s.rt.state.im.connections[conn.id].settings, { domain: 'lark', appId: 'app-1' }, 'untouched fields keep their values')
  const view = s.rt.imView().connections.find(entry => entry.id === conn.id)
  assert.deepEqual(view.settings, { domain: 'lark', appId: 'app-1' })
  await s.rt.imEndpoint('im-update', { id: conn.id, fields: { domain: 'feishu' } })
  assert.equal(s.rt.state.im.connections[conn.id].settings.domain, 'feishu')
  assert.equal(s.rt.state.im.connections[conn.id].settings.appId, 'app-1')
})

test('unpaired DM asks once, allow pairs it, next message prompts the Bot', async (t) => {
  const s = await start()
  t.after(s.stop)
  await add(s)
  const [one] = Object.values(s.rt.state.im.connections)
  await dm(s, 'u1', 'hello')
  assert.equal(one.requests.length, 1)
  assert.equal(s.fake.sent.length, 1)
  assert.match(s.fake.sent[0].text, /connection request/)
  assert.equal(s.prompts.length, 0)
  await dm(s, 'u1', 'hello again')
  assert.equal(one.requests.length, 1)
  assert.equal(s.fake.sent.length, 1)
  await s.rt.imEndpoint('im-pair', { id: one.id, senderId: 'u1', allow: true })
  assert.equal(one.paired.length, 1)
  assert.match(s.fake.sent.at(-1).text, /talk to Chief/)
  await dm(s, 'u1', 'do a thing')
  assert.equal(s.prompts.length, 1)
  assert.equal(s.prompts[0].sessionId, 'a')
  assert.equal(s.prompts[0].mode, 'queue')
  assert.match(s.prompts[0].requestId, /^im:telegram:/)
  assert.deepEqual(s.prompts[0].content, [{ type: 'text', text: 'do a thing' }])
})

test('unbound group mention replies unbound and records the chat; binding routes mentions', async (t) => {
  const s = await start()
  t.after(s.stop)
  const conn = await add(s)
  s.rt.state.im.connections[conn.id].paired.push({ id: 'u1', name: 'User u1', at: 1 })
  await s.rt.save()
  await gm(s, 'u1', 'hi all', { mentioned: false })
  assert.equal(s.fake.sent.length, 0)
  assert.equal(s.prompts.length, 0)
  await gm(s, 'u1', '@fakebot hello group')
  assert.equal(s.rt.state.im.connections[conn.id].chats.g1?.kind, 'group')
  assert.equal(s.fake.sent.length, 1)
  assert.match(s.fake.sent[0].text, /not bound/)
  assert.equal(s.prompts.length, 0)
  await s.rt.imEndpoint('im-chat', { id: conn.id, chatKey: 'g1', target: { roomId: 'r1' } })
  // The adapter strips its own mention before the core sees the text.
  await gm(s, 'u1', 'hello group')
  assert.equal(s.prompts.length, 1)
  assert.equal(s.prompts[0].sessionId, 'r1')
  assert.deepEqual(s.prompts[0].content, [{ type: 'text', text: 'hello group' }])
})

test('outbound: assistant text and member lines go out; hidden turns, user and system lines do not', async (t) => {
  const s = await start()
  t.after(s.stop)
  const conn = await add(s)
  const one = s.rt.state.im.connections[conn.id]
  one.paired.push({ id: 'u1', name: 'U1', at: 1 })
  await s.rt.save()
  await dm(s, 'u1', 'hi')
  s.imTurn('a')
  s.fake.sent.length = 0
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'visible reply' }] } })
  assert.equal(s.fake.sent.length, 1)
  assert.equal(s.fake.sent[0].text, 'visible reply')
  s.rt.state.exchangeTurns.a = [7]
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'hidden' }] }, turn: 7 })
  s.emitEvent('a', 'user/message', { source: { kind: 'user' }, content: [{ type: 'text', text: 'user typed' }] })
  assert.equal(s.fake.sent.length, 1)
  one.chats.g1 = { kind: 'group', title: 'G', target: { roomId: 'r1' }, at: 1 }
  await s.rt.save()
  // The group's turn was asked for in its IM chat, so its lines go back there.
  await gm(s, 'u1', 'hello group')
  s.imTurn('r1')
  s.rt.imGroupReply('r1', s.rt.botOf('b'), 'member spoke')
  await s.flush()
  assert.equal(s.fake.sent.length, 2)
  assert.equal(s.fake.sent[1].text, '**Writer**: member spoke')
  assert.equal(s.fake.sent[1].chat.key, 'g1')
})

test('a quoted reply carries the message it answers into the Bot', async (t) => {
  const s = await start({ adapter: fakeAdapter({ quote: true }) })
  t.after(s.stop)
  const conn = await add(s)
  const one = s.rt.state.im.connections[conn.id]
  one.paired.push({ id: 'u1', name: 'U1', at: 1 })
  await s.rt.save()
  await dm(s, 'u1', 'hi')
  s.imTurn('a')
  s.fake.sent.length = 0
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'Project A is done' }] } })
  await s.flush()
  const sentId = s.fake.sent.at(-1)?.messageId
  assert.ok(sentId !== undefined, 'the sent message has an id')
  await dm(s, 'u1', 'ship it', { quote: { ids: [sentId] } })
  assert.equal(s.prompts.length, 2)
  assert.equal(s.prompts[1].content[0].text, 'Replying to an earlier message:\n> Project A is done\n\nship it')
  // The reply can come after a restart, so the message is kept in the runtime file.
  await delay(600)
  const runtime = JSON.parse(readFileSync(join(s.home, 'im', `${conn.id}.json`), 'utf8'))
  assert.ok(runtime.sent['dm-u1'].some(entry => entry.text === 'Project A is done'))
})

test('only the last messages sent to a chat are kept for quoting', async (t) => {
  const s = await start({ adapter: fakeAdapter({ quote: true }) })
  t.after(s.stop)
  const conn = await add(s)
  const one = s.rt.state.im.connections[conn.id]
  one.paired.push({ id: 'u1', name: 'U1', at: 1 })
  await s.rt.save()
  await dm(s, 'u1', 'hi')
  s.imTurn('a')
  s.fake.sent.length = 0
  for (let at = 0; at < 21; at += 1) {
    s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: `Report ${at}` }] } })
  }
  await s.flush()
  await delay(1_200)
  const kept = JSON.parse(readFileSync(join(s.home, 'im', `${conn.id}.json`), 'utf8')).sent['dm-u1']
  assert.equal(kept.length, 20)
  assert.ok(!kept.some(entry => entry.text === 'Report 0'), 'the oldest is dropped')
  assert.ok(kept.some(entry => entry.text === 'Report 20'), 'the newest stays')
})

test('question card: buttons answer it, a stranger press is ignored, settled elsewhere edits the card', async (t) => {
  const s = await start()
  t.after(s.stop)
  const conn = await add(s)
  const one = s.rt.state.im.connections[conn.id]
  one.paired.push({ id: 'u1', name: 'U1', at: 1 }, { id: 'u2', name: 'U2', at: 1 })
  await s.rt.save()
  await dm(s, 'u1', 'hi')
  s.imTurn('a')
  s.fake.sent.length = 0
  s.rt.state.questions.a = { id: 'q1', question: 'Which?', options: [{ label: 'yes' }, { label: 'no' }] }
  await s.rt.save()
  await s.flush()
  const card = s.fake.sent.find(entry => entry.buttons !== undefined)
  assert.ok(card, 'question card with buttons')
  assert.match(card.text, /Which\?/)
  await s.fake.handlers.onAction({ chat: { key: 'dm-u2', kind: 'direct', title: 'U2' }, sender: { id: 'u9', name: 'stranger' }, data: 'q:q1:0', messageId: card.messageId ?? 1 })
  assert.ok(s.rt.state.questions.a !== undefined, 'unpaired press does not answer')
  await s.fake.handlers.onAction({ chat: { key: 'dm-u1', kind: 'direct', title: 'U1' }, sender: { id: 'u1', name: 'U1' }, data: 'q:q1:1', messageId: card.messageId ?? 1 })
  assert.ok(s.rt.state.questions.a === undefined, 'paired press answers')
  assert.equal(s.agents.get('a')?.followed, 1)
  await s.flush()
  assert.equal(s.fake.edited.length, 1)
  // Answered on the computer: the question leaves the state, the card edits shut.
  s.rt.state.questions.a = { id: 'q2', question: 'Again?', options: [{ label: 'x' }] }
  await s.rt.save()
  await s.flush()
  delete s.rt.state.questions.a
  await s.rt.save()
  await s.flush()
  assert.equal(s.fake.edited.length, 2)
})

test('numbered reply answers the newest open card on a no-button platform', async (t) => {
  const s = await start({ platform: 'dingtalk', adapter: fakeAdapter({ buttons: false }) })
  t.after(s.stop)
  const conn = await add(s)
  const one = s.rt.state.im.connections[conn.id]
  one.paired.push({ id: 'u1', name: 'U1', at: 1 })
  await s.rt.save()
  await dm(s, 'u1', 'hi')
  s.imTurn('a')
  s.rt.state.questions.a = { id: 'q1', question: 'Pick', options: [{ label: 'x' }, { label: 'y' }] }
  await s.rt.save()
  await s.flush()
  const card = s.fake.sent.at(-1)
  assert.equal(card.buttons, undefined)
  await dm(s, 'u1', '2')
  assert.ok(s.rt.state.questions.a === undefined)
  assert.equal(s.agents.get('a')?.followed, 1)
})

test('a pending secret request sends text without buttons', async (t) => {
  const s = await start()
  t.after(s.stop)
  const conn = await add(s)
  const one = s.rt.state.im.connections[conn.id]
  one.paired.push({ id: 'u1', name: 'U1', at: 1 })
  await s.rt.save()
  await dm(s, 'u1', 'hi')
  s.imTurn('a')
  s.fake.sent.length = 0
  s.rt.state.secretRequests = { a: [{ id: 's1', name: 'MY_KEY', purpose: 'for tests', status: 'pending', askedAt: 1 }] }
  await s.rt.save()
  await s.flush()
  const card = s.fake.sent.at(-1)
  assert.match(card.text, /MY_KEY/)
  assert.equal(card.buttons, undefined)
})

test('/stop calls rt.stopChat for a Bot target', async (t) => {
  const s = await start()
  t.after(s.stop)
  const conn = await add(s)
  const one = s.rt.state.im.connections[conn.id]
  one.paired.push({ id: 'u1', name: 'U1', at: 1 })
  await s.rt.save()
  let called = 0
  s.rt.stopChat = async () => { called += 1; return true }
  await dm(s, 'u1', '/stop')
  assert.equal(called, 1)
  assert.match(s.fake.sent.at(-1).text, /Stopped|已停/)
  await dm(s, 'u1', '/stop@fakebot')
  assert.equal(called, 2)
})

test('im-add keeps secrets out of state, im-remove deletes them and the runtime file', async (t) => {
  const s = await start()
  t.after(s.stop)
  const conn = await add(s)
  const one = s.rt.state.im.connections[conn.id]
  const secretNames = Object.values(one.secrets)
  assert.equal(secretNames.length, 1)
  const saved = JSON.parse((await import('node:fs')).readFileSync(join(s.home, 'secrets.json'), 'utf8'))
  assert.equal(saved.secrets[0].name, secretNames[0])
  assert.deepEqual(saved.secrets[0].scope, [])
  const view = s.rt.imView()
  assert.equal(view.connections[0].id, conn.id)
  assert.ok(!JSON.stringify(view).includes('tok-1234'))
  await s.rt.imEndpoint('im-remove', { id: conn.id })
  assert.equal(s.rt.state.im.connections[conn.id], undefined)
  const after = JSON.parse((await import('node:fs')).readFileSync(join(s.home, 'secrets.json'), 'utf8'))
  assert.equal(after.secrets.length, 0)
  assert.equal(existsSync(join(s.home, 'im', `${conn.id}.json`)), false)
})

test('a deleted Bot target gets the unbound reply', async (t) => {
  const s = await start()
  t.after(s.stop)
  const conn = await add(s)
  const one = s.rt.state.im.connections[conn.id]
  one.paired.push({ id: 'u1', name: 'U1', at: 1 })
  one.botId = 'gone'
  await s.rt.save()
  s.fake.sent.length = 0
  await dm(s, 'u1', 'hi')
  s.imTurn('a')
  assert.match(s.fake.sent.at(-1).text, /not bound|还没绑定/)
  assert.equal(s.prompts.length, 0)
})

test('a weixin QR login creates the connection paired with the scanning owner', async (t) => {
  const s = await start({ platform: 'weixin', adapter: {
    ...fakeAdapter(),
    id: 'weixin',
    async loginStart() { return { loginId: 'l1', qr: 'weixin://qr/abc', expiresAt: Date.now() + 60_000 } },
    async loginWait() {
      this.waits = (this.waits ?? 0) + 1
      if (this.waits < 2) return { status: 'waiting' }
      return {
        status: 'done',
        connection: { settings: { baseUrl: 'http://ilink/' }, secrets: { token: 'wx-tok' }, account: { id: 'bot-9', name: 'wxbot' } },
        owner: { id: 'owner-1', name: 'Fei' },
      }
    },
  } })
  t.after(s.stop)
  const login = await s.rt.imEndpoint('im-login-start', { platform: 'weixin', botId: 'a' })
  assert.equal(login.qr, 'weixin://qr/abc')
  const waiting = await s.rt.imEndpoint('im-login-wait', { platform: 'weixin', botId: 'a', loginId: 'l1' })
  assert.deepEqual(waiting, { status: 'waiting' })
  const done = await s.rt.imEndpoint('im-login-wait', { platform: 'weixin', botId: 'a', loginId: 'l1' })
  assert.equal(done.status, 'done')
  const conn = s.rt.state.im.connections[done.id]
  assert.ok(conn, 'connection created on confirm')
  assert.equal(conn.platform, 'weixin')
  assert.deepEqual(conn.paired, [{ id: 'owner-1', name: 'Fei', at: conn.paired[0].at }])
  assert.equal(conn.chats['owner-1'].kind, 'direct')
  assert.equal(conn.secrets.token, `IM_WEIXIN_${conn.id.slice(3, 9).toUpperCase()}_TOKEN`, 'the token is stored as a secret')
  assert.equal(s.rt.secretValue(conn.secrets.token), 'wx-tok')
  assert.equal(conn.settings.baseUrl, 'http://ilink/')
})

const pairedConn = async (s) => {
  const conn = await add(s)
  const one = s.rt.state.im.connections[conn.id]
  one.paired.push({ id: 'u1', name: 'U1', at: 1 })
  await s.rt.save()
  return { conn, one }
}

const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yVJ8AAAAASUVORK5CYII=', 'base64')

test('an accepted display view sends one image only to its IM origin, with an ordered fallback on rejection', async (t) => {
  let rejected = false
  const s = await start({ adapter: fakeAdapter({ sendImage: () => {
    if (rejected) throw Object.assign(new Error('upload rejected'), { permanent: true })
  } }) })
  t.after(s.stop)
  const { one } = await pairedConn(s)
  one.paired.push({ id: 'u2', name: 'U2', at: 1 })
  one.chats['dm-u2'] = { kind: 'direct', title: 'U2', at: 1 }
  await s.rt.save()
  s.rt.renderImViewImage = async () => ({ data: PNG, name: 'card.png', mediaType: 'image/png' })
  const show = (title, view = { type: 'metric', label: 'Close', value: 952 }, more = {}) => s.ctx.registeredTools.get('show_view')
    .execute({ title, view, ...more }, { agent: { id: 'a' } })
  await show('Desktop only')
  await dm(s, 'u1', 'show a chart')
  s.imTurn()
  s.fake.sent.length = 0
  await show('Team only', undefined, { audience: 'team' })
  await show('Malformed', { type: 'chart' })
  await show('Weekly results')
  await show('Weekly results')
  await s.flush()
  assert.deepEqual(s.fake.sent.map(entry => [entry.chat.key, entry.image?.mediaType]), [['dm-u1', 'image/png']])

  rejected = true
  await dm(s, 'u1', 'show it again')
  s.imTurn()
  s.fake.sent.length = 0
  await show('Weekly results')
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'The report is ready.' }] } })
  await s.flush()
  assert.deepEqual(s.fake.sent.map(entry => entry.text), [
    'Weekly results\n• Close  952\nOpen ChemClaw to see the full view.',
    'The report is ready.',
  ])
})

test('IM uploads workspace pictures once and sends repeated prose once per turn even with a desktop code fence', async (t) => {
  const workspace = mkdtempSync(join(tmpdir(), 'chemclaw-im-workspace-'))
  t.after(() => rmSync(workspace, { recursive: true, force: true }))
  writeFileSync(join(workspace, 'plot.png'), PNG)
  const s = await start({ adapter: fakeAdapter({ sendImage: () => {} }) })
  t.after(s.stop)
  s.rt.ctx.sessionController.inspect = async () => ({ meta: { cwd: workspace } })
  await pairedConn(s)
  await dm(s, 'u1', 'send an image')
  s.imTurn()
  s.fake.sent.length = 0
  const statement = 'Here is the requested report with the latest reading and a chart.'
  const say = value => s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: value }] } })
  say(statement)
  say(statement + '\n\nOne extra observation.\n\n' + '```dsh-ui\n{"items":[{"type":"html"}]}\n```')
  say('![Plot](plot.png)')
  s.emitEvent('a', 'deliverables/presented', { files: [{ path: join(workspace, 'plot.png') }] })
  for (let index = 0; index < 40 && !s.fake.sent.find(entry => entry.image); index++) await s.flush()
  await s.flush()
  assert.deepEqual(s.fake.sent.filter(entry => entry.text).map(entry => entry.text), [
    statement, 'One extra observation.', 'Image unavailable here. Open ChemClaw to view it.',
  ])
  assert.deepEqual(s.fake.sent.filter(entry => entry.image).map(entry => entry.image.data), [PNG])
  await dm(s, 'u1', 'reply again')
  s.imTurn()
  say(statement)
  assert.equal(s.fake.sent.filter(entry => entry.text === statement).length, 2)
})

test('IM sends real SVG and HTML attachments only to the originating chat', async (t) => {
  const workspace = mkdtempSync(join(tmpdir(), 'chemclaw-im-documents-'))
  const outside = mkdtempSync(join(tmpdir(), 'chemclaw-im-outside-'))
  t.after(() => {
    rmSync(workspace, { recursive: true, force: true })
    rmSync(outside, { recursive: true, force: true })
  })
  const svg = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><text>原图</text></svg>')
  const html = Buffer.from('<!doctype html>\n<p>原始报告</p>\n')
  writeFileSync(join(workspace, '趋势 图.svg'), svg)
  writeFileSync(join(workspace, '报告.html'), html)
  writeFileSync(join(workspace, '拒收.htm'), html)
  writeFileSync(join(outside, '报告.html'), Buffer.from('outside'))
  const s = await start({ adapter: fakeAdapter({ sendFile: file => {
    if (file.name === '拒收.htm') throw Object.assign(new Error('rejected'), { permanent: true })
  } }) })
  t.after(s.stop)
  s.rt.ctx.sessionController.inspect = async () => ({ meta: { cwd: workspace } })
  const { one } = await pairedConn(s)
  one.paired.push({ id: 'u2', name: 'U2', at: 1 })
  one.chats['dm-u2'] = { kind: 'direct', title: 'U2', at: 1 }
  await s.rt.save()
  const present = (...paths) => s.emitEvent('a', 'deliverables/presented', { files: paths.map(path => ({ path })) })
  present(join(workspace, '趋势 图.svg'))
  await dm(s, 'u1', 'send an SVG and HTML file')
  s.imTurn()
  s.fake.sent.length = 0
  present(join(workspace, '趋势 图.svg'), join(outside, '报告.html'))
  s.emitEvent('a', 'assistant/message', { message: { content: [{
    type: 'text', text: '[趋势图](<./趋势 图.svg>) 和 [交互报告](./报告.html)\n\n`拒收.htm` 是一个引用。',
  }] } })
  present(join(workspace, '拒收.htm'))
  for (let index = 0; index < 40 && !s.fake.sent.some(entry => entry.text?.startsWith('拒收.htm\n')); index++) await s.flush()
  assert.deepEqual(s.fake.sent.filter(entry => entry.file).map(entry => [entry.chat.key, entry.file.name, entry.file.data]), [
    ['dm-u1', '趋势 图.svg', svg], ['dm-u1', '报告.html', html],
  ])
  assert.ok(s.fake.sent.every(entry => entry.chat.key === 'dm-u1'))
  assert.ok(s.fake.sent.some(entry => entry.text?.startsWith('报告.html\nFile unavailable')))
  assert.ok(s.fake.sent.some(entry => entry.text?.startsWith('拒收.htm\nFile unavailable')))
})

test('reply origin: an IM turn answers its own chat, and only that chat', async (t) => {
  const s = await start()
  t.after(s.stop)
  const { one } = await pairedConn(s)
  // A second paired chat of the same Bot, which this turn did not come from.
  one.paired.push({ id: 'u2', name: 'U2', at: 1 })
  one.chats['dm-u2'] = { kind: 'direct', title: 'U2', at: 1 }
  await s.rt.save()
  await dm(s, 'u1', 'hi')
  s.imTurn('a')
  s.fake.sent.length = 0
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'only for u1' }] } })
  await s.flush()
  assert.deepEqual(s.fake.sent.map(entry => entry.chat.key), ['dm-u1'])
})

test('reply origin: a Web turn does not reach IM', async (t) => {
  const s = await start()
  t.after(s.stop)
  await pairedConn(s)
  s.emitEvent('a', 'user/message', { source: { kind: 'web' }, content: [{ type: 'text', text: 'typed in the browser' }] })
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'answer to the browser' }] } })
  await s.flush()
  assert.equal(s.fake.sent.length, 0)
})

test('reply origin: a peer Bot message and a scheduled task do not reach IM', async (t) => {
  const s = await start()
  t.after(s.stop)
  await pairedConn(s)
  for (const source of [{ kind: 'peer', from: 'b' }, { kind: 'schedule', taskId: 't1' }]) {
    s.emitEvent('a', 'user/message', { source, content: [{ type: 'text', text: 'work for you' }] })
    s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'internal reply' }] } })
    await s.flush()
  }
  assert.equal(s.fake.sent.length, 0)
})

test('reply origin: the turn ending stops later output from going out', async (t) => {
  const s = await start()
  t.after(s.stop)
  await pairedConn(s)
  await dm(s, 'u1', 'hi')
  s.imTurn('a')
  s.emitEvent('a', 'turn/end', {})
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'late' }] } })
  await s.flush()
  assert.equal(s.fake.sent.length, 0)
})

test('reply origin: a consumed IM rpcId is ignored without withdrawing or claiming an origin', async (t) => {
  const s = await start()
  t.after(s.stop)
  await pairedConn(s)
  await dm(s, 'u1', 'hi')
  const source = { kind: 'user', rpcId: s.prompts.at(-1).requestId }
  s.imTurn('a')
  s.emitEvent('a', 'user/message', { source })
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'reply' }] } })
  await s.flush()
  assert.deepEqual(s.fake.sent.map(entry => [entry.chat.key, entry.text]), [['dm-u1', 'reply']])

  s.emitEvent('a', 'turn/end', {})
  s.emitEvent('a', 'turn/start', {})
  s.emitEvent('a', 'user/message', { source })
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'not a new IM request' }] } })
  await s.flush()
  assert.equal(s.fake.sent.length, 1, 'a duplicate cannot claim a later turn')

  await dm(s, 'u1', 'next')
  s.emitEvent('a', 'user/message', { source: { kind: 'user', rpcId: s.prompts.at(-1).requestId } })
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'next reply' }] } })
  await s.flush()
  assert.deepEqual(s.fake.sent.map(entry => entry.text), ['reply', 'next reply'], 'a duplicate does not poison a later claim')
})

test('reply origin: unpairing the chat stops a running turn from replying', async (t) => {
  const s = await start()
  t.after(s.stop)
  const { one } = await pairedConn(s)
  await dm(s, 'u1', 'hi')
  s.imTurn('a')
  s.fake.sent.length = 0
  await s.rt.imEndpoint('im-unpair', { id: one.id, senderId: 'u1' })
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'still there?' }] } })
  await s.flush()
  assert.equal(s.fake.sent.length, 0)
})

test('mixed IM chats cannot reclaim the same turn, and the next turn starts clean', async t => {
  const s = await start()
  t.after(s.stop)
  const { conn } = await pairedConn(s)
  s.rt.state.im.connections[conn.id].paired.push({ id: 'u2', name: 'U2', at: 1 })
  await dm(s, 'u1', 'first')
  s.imTurn('a')
  await dm(s, 'u2', 'second')
  s.emitEvent('a', 'user/message', { source: { kind: 'user', rpcId: s.prompts.at(-1).requestId } })
  await dm(s, 'u1', 'third')
  s.emitEvent('a', 'user/message', { source: { kind: 'user', rpcId: s.prompts.at(-1).requestId } })
  s.fake.sent.length = 0
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'mixed' }] } })
  await s.flush()
  assert.equal(s.fake.sent.length, 0)
  await dm(s, 'u1', 'fresh')
  s.imTurn('a')
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'clean' }] } })
  await s.flush()
  assert.deepEqual(s.fake.sent.map(x => [x.chat.key, x.text]), [['dm-u1', 'clean']])
})

test('a Web question answer cannot inherit a previous IM destination', async t => {
  const s = await start()
  t.after(s.stop)
  await pairedConn(s)
  await dm(s, 'u1', 'first')
  s.imTurn('a')
  s.emitEvent('a', 'turn/end', {})
  s.emitEvent('a', 'turn/start', {})
  s.emitEvent('a', 'user/message', { source: { kind: 'user-question-reply', callId: 'c1', outcome: 'answered' } })
  s.fake.sent.length = 0
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'private answer' }] } })
  await s.flush()
  assert.equal(s.fake.sent.length, 0)
})

// QQ splits a reply into several posts and remembers, by job, which of them went
// out; that only holds if Try again hands the adapter back the same job.
test('a failed add keeps the network reason under "fetch failed"', async (t) => {
  // #1120: the outlet printed only error.message, so a DNS failure read as
  // "im-add: fetch failed" and the user could not tell it from a bad token.
  const adapter = fakeAdapter()
  adapter.check = async () => {
    throw Object.assign(new TypeError('fetch failed'), {
      cause: Object.assign(new Error('getaddrinfo ENOTFOUND api.telegram.org'), { code: 'ENOTFOUND' }),
    })
  }
  const s = await start({ adapter })
  t.after(s.stop)
  await assert.rejects(() => add(s), error => {
    assert.match(error.message, /fetch failed: getaddrinfo ENOTFOUND api\.telegram\.org/)
    return true
  })
})

test('a failed add does not echo the token back', async (t) => {
  const adapter = fakeAdapter()
  adapter.check = async () => {
    throw Object.assign(new TypeError('fetch failed'), {
      cause: new Error('connect ECONNREFUSED https://api.telegram.org/bottok-1234/getMe'),
    })
  }
  const s = await start({ adapter })
  t.after(s.stop)
  await assert.rejects(() => add(s), error => {
    assert.match(error.message, /ECONNREFUSED/)
    assert.ok(!error.message.includes('tok-1234'), 'the token is redacted')
    return true
  })
})

test('a failed update keeps the network reason and redacts a secret as it appears in a URL', async (t) => {
  const adapter = fakeAdapter()
  const s = await start({ adapter })
  t.after(s.stop)
  const conn = await add(s)
  adapter.check = async () => {
    throw Object.assign(new TypeError('fetch failed'), {
      cause: new Error('connect ECONNREFUSED https://api.telegram.org/botnew%2Btok%2F1/getMe'),
    })
  }
  await assert.rejects(() => s.rt.imEndpoint('im-update', { id: conn.id, fields: { token: 'new+tok/1' } }), error => {
    assert.match(error.message, /fetch failed: connect ECONNREFUSED/)
    assert.ok(!error.message.includes('new%2Btok%2F1'), 'the encoded token is redacted')
    return true
  })
})



test('desktop input and unowned results withhold the rest of an IM turn', async (t) => {
  const s = await start()
  t.after(s.stop)
  const { one } = await pairedConn(s)
  one.paired.push({ id: 'u2', name: 'U2', at: 1 })
  await s.rt.save()
  await dm(s, 'u1', 'first question')
  s.imTurn()
  s.fake.sent.length = 0
  s.emitEvent('a', 'turn/end', { turn: 1 })
  await dm(s, 'u2', 'next question')
  s.imTurn()
  s.emitEvent('a', 'user/message', { source: { kind: 'tool-jobs' }, content: [{ type: 'text', text: 'earlier job result' }] })
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'private background result' }] } })
  assert.equal(s.fake.sent.length, 0)

  s.emitEvent('a', 'turn/end', { turn: 2 })
  await dm(s, 'u2', 'next turn')
  s.imTurn()
  s.emitEvent('a', 'user/message', { source: { kind: 'user' }, content: [{ type: 'text', text: 'only for desktop' }] })
  s.emitEvent('a', 'assistant/message', { message: { content: [{ type: 'text', text: 'private desktop reply' }] } })
  assert.equal(s.fake.sent.length, 0)
})

test('only a saved reply within the IM group turn reaches its platform chat', async (t) => {
  const s = await start()
  t.after(s.stop)
  const { conn, one } = await pairedConn(s)
  one.chats.g1 = { kind: 'group', title: 'Group One', at: 1 }
  await s.rt.imEndpoint('im-chat', { id: conn.id, chatKey: 'g1', target: { roomId: 'r1' } })
  await gm(s, 'u1', 'hello')
  s.imTurn('r1')
  s.rt.imGroupReply('r1', s.rt.botOf('b'), 'inside the round')
  s.emitEvent('r1', 'turn/end', { turn: 1 })
  s.rt.imGroupReply('r1', s.rt.botOf('b'), 'late result')
  assert.deepEqual(s.fake.sent.map(({ chat, text }) => [chat.key, text]), [['g1', '**Writer**: inside the round']])
})
