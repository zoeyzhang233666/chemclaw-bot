import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, realpathSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { isAbsolute, join, relative } from 'node:path'
import { test } from 'node:test'
import { createRuntime } from '../index.js'
import { fakeContext } from './fake-ctx.js'
import { roleCatalog, domainSkills, packageRoot } from '../src/host/catalog-seed.js'
import { parseMcpImport } from '../src/shared/connectors.js'
import { fetchPublic, publicUrl, install as installPublicData } from '../src/host/public-data.js'
import { install as installCompany } from '../src/host/company-connectors.js'
import { ensureSkillLibrary } from '../src/host/catalog-seed.js'
import { ROOM_MAX_MEMBERS } from '../src/host/constants.js'
import { mentionRows } from '../src/client/at-menu.js'
import { indexRoster } from '../src/client/sources.js'

function fixture(t, options = {}) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-integration-'))
  const mounts = []
  let outcome = 'success'
  const ctx = fakeContext({ services: { loader: { import: async () => ({}) } } })
  ctx.plugin = (_plugin, config) => {
    const mount = { config, disposed: false, async dispose() { this.disposed = true }, async await() { if (outcome === 'timeout') return new Promise(() => {}); if (outcome !== 'success') throw new Error(outcome) } }
    mounts.push(mount); return mount
  }
  let session = 0
  const workspaces = new Map()
  Object.assign(ctx, {
    workspaceRegistry: { get: id => workspaces.get(id), resolveByPath: async () => undefined, create: async path => { const item = { id: 'workspace', path }; workspaces.set(item.id, item); return item }, archiveSession: async () => {} },
    llm: { listProviders: () => [], listModels: async () => [] },
    sessionController: { create: async () => ({ sessionId: `s${++session}` }), resolveAgent: async id => ({ agent: { session: { id }, followup() {} } }) },
    sessionTitle: { rename: async () => {} }, sessions: { flush: async () => {} },
  })
  const rt = createRuntime(ctx, { home, diagnosticsFile: false, github: false, connectorTimeoutMs: 15, ...options })
  t.after(async () => { await ctx.dispose(); rmSync(home, { recursive: true, force: true, maxRetries: 5 }) })
  return { rt, ctx, home, mounts, outcome: value => { outcome = value } }
}

test('built-in search status reflects the real plugin inventory rather than assuming installation', async () => {
  const row = { moduleName: 'dsh-free-search', enabled: true, fiberPhase: 'active' }
  const ctx = fakeContext({ services: { pluginManager: { listPlugins: async () => [row] } } })
  const rt = { ctx }
  installPublicData(rt)
  assert.equal((await rt.searchPluginStatus()).state, 'loaded')
  row.enabled = false
  assert.equal((await rt.searchPluginStatus()).state, 'off')
  row.fiberPhase = 'failed'
  assert.equal((await rt.searchPluginStatus()).state, 'error')
  await ctx.dispose()
})

test('50 role and 15 scenario templates resolve complete portable skills', () => {
  assert.equal(roleCatalog.roles.length, 50); assert.equal(roleCatalog.groups.length, 15); assert.equal(domainSkills.length, 108)
  const names = new Set([...domainSkills.map(item => item.id), ...JSON.parse(readFileSync(join(packageRoot, 'seed/supplemental-skills.json'))).map(item => item.id), 'chemclaw-chemistry'])
  for (const role of roleCatalog.roles) { assert.ok(role.description && role.inputs && role.sources && role.limits && role.examples.length); for (const skill of role.skills) assert.ok(names.has(skill), `${role.name}: ${skill}`) }
  for (const skill of domainSkills) { assert.ok(!/^[A-Z]:/.test(skill.sourcePath)); assert.ok(readFileSync(join(packageRoot, skill.sourcePath), 'utf8').length > 500) }
  for (const group of roleCatalog.groups) {
    assert.ok(group.members.includes(group.admin))
    assert.equal(group.members.filter(id => id === 'chemclaw').length, 1)
    assert.notEqual(group.admin, 'chemclaw')
    assert.ok(group.members.length <= ROOM_MAX_MEMBERS)
  }
})

test('fresh bootstrap creates all 50 Bots and 15 groups once; simultaneous requests preserve custom instructions', async t => {
  const { rt } = fixture(t, { companyConnectors: false })
  await rt.bootstrap()
  assert.equal(Object.keys(rt.state.bots).length, 50); assert.equal(Object.keys(rt.state.rooms).length, 15)
  const first = rt.state.bots[rt.state.mainBotIds[0]]
  assert.equal(first.name, 'ChemClaw'); assert.equal(first.avatar.shape, 'lobster')
  const [a, b] = await Promise.all([rt.activateScenario({ id: 'scene-1', kind: 'group' }), rt.activateScenario({ id: 'scene-1', kind: 'group' })])
  assert.equal(a.id, b.id); assert.equal(Object.keys(rt.state.rooms).length, 15)
  const expert = rt.state.bots[a.admin]; expert.instructions = 'User-customized instructions'
  await rt.activateScenario({ id: expert.templateId, kind: 'role' })
  assert.equal(expert.instructions, 'User-customized instructions')
  const ids = Object.keys(rt.state.bots)
  await Promise.all([rt.bootstrap(), rt.bootstrap()])
  assert.deepEqual(Object.keys(rt.state.bots), ids)
  assert.equal(new Set(Object.values(rt.state.bots).map(item => `${item.avatar.shape}:${item.color}`)).size, 50)
  assert.ok(Object.values(rt.state.rooms).every(room => !room.avatar))
  assert.ok(!Object.values(rt.state.bots).some(bot => /^lobster-\d+$/.test(bot.avatar?.shape ?? '')))
  assert.match(a.notice, /交付/)
  assert.equal(expert.templateId, roleCatalog.groups[0].admin)
  for (const room of Object.values(rt.state.rooms)) {
    assert.equal(room.members.filter(id => id === first.id).length, 1)
    assert.notEqual(room.admin, first.id)
    assert.equal(room.mode, 'admin')
    assert.match(room.notice, /主控：ChemClaw/)
    assert.equal(room.templateVersion, roleCatalog.version)
  }
  assert.equal(Object.values(rt.state.capabilities.items).filter(item => item.kind === 'skill').length, 118)
  assert.equal(rt.state.capabilities.items['guizang-ppt-skill'].category, '通用办公')
  assert.equal(rt.state.capabilities.items['chemclaw-presentations'].category, '通用办公')
  for (const skill of Object.values(rt.state.capabilities.items).filter(item => item.kind === 'skill')) {
    assert.match(skill.labels.zh, /[\u4e00-\u9fff]/)
    assert.match(skill.purpose, /[\u4e00-\u9fff]/, skill.name)
    assert.match(skill.deliverables, /[\u4e00-\u9fff]/, skill.name)
  }
})

test('upgrading a coordinator-only or partial team preserves conversations, edits and deleted presets', async t => {
  const { rt } = fixture(t, { companyConnectors: false, seedTeam: false })
  await rt.bootstrap()
  const main = rt.state.bots[rt.state.mainBotIds[0]]
  main.instructions = 'My coordinator instructions'
  const old = await rt.createBot({ name: '下游客户开发', role: '内贸销售', instructions: 'My sales instructions', color: 'green', avatar: { shape: 'lobster' } })
  old.templateId = 'role-1-1'; old.templateVersion = 1
  const customized = await rt.createBot({ name: '我的专属顾问', role: '自定义', instructions: 'Keep me', color: '#123456', avatar: { shape: 'kitty' } })
  customized.templateId = 'role-2-1'; customized.templateVersion = 1
  rt.state.templateBindings = { 'role-1-1': old.id, 'role-2-1': customized.id, 'role-8-1': 'previously-deleted' }
  rt.config.seedTeam = true
  await rt.save()
  await rt.bootstrap()
  assert.equal(rt.state.mainBotIds[0], main.id)
  assert.equal(main.instructions, 'My coordinator instructions')
  assert.equal(rt.state.templateBindings['role-1-1'], old.id)
  assert.equal(old.name, '下游客户开发专家')
  assert.equal(old.instructions, 'My sales instructions')
  assert.equal(customized.name, '我的专属顾问')
  assert.equal(customized.avatar.shape, 'kitty')
  assert.equal(customized.color, '#123456')
  assert.equal(rt.state.bots['previously-deleted'], undefined)
  assert.equal(Object.values(rt.state.bots).some(bot => bot.templateId === 'role-8-1'), false)
  const ids = Object.keys(rt.state.bots)
  await rt.bootstrap()
  assert.deepEqual(Object.keys(rt.state.bots), ids)
})

test('connector imports canonicalize services and never forward a stored credential to a changed URL', async t => {
  const { rt } = fixture(t)
  await rt.load(); await rt.loadSecrets()
  const entry = (url, token = 'synthetic-credential') => ({ type: 'http', url, headers: { Authorization: `Bearer ${token}` } })
  await rt.connectorEndpoint('connector-import', { json: { mcpServers: { alias: entry('https://datahub.chem-cloud.cn/mcp') } } })
  assert.equal(rt.state.customConnectors.alias, undefined)
  assert.equal(rt.connectorOwns('alias', 'https://datahub.chem-cloud.cn/mcp'), true)
  await assert.rejects(rt.connectorEndpoint('connector-import', { json: { mcpServers: { a: entry('https://datahub.chem-cloud.cn/mcp'), b: entry('https://datahub.chem-cloud.cn/mcp') } } }), /only once/)
  await rt.connectorEndpoint('connector-import', { json: { mcpServers: { custom: entry('https://example.invalid/mcp') } } })
  await assert.rejects(rt.connectorEndpoint('connector-import', { json: { mcpServers: { custom: entry('https://other.invalid/mcp') } } }), /cannot be replaced/)
  assert.equal(rt.state.customConnectors.custom.url, 'https://example.invalid/mcp')
})

test('upgrading legacy preset groups only appends the chief and preserves custom names, notices and admins', async t => {
  const { rt } = fixture(t, { companyConnectors: false, seedTeam: false })
  await rt.bootstrap()
  const def = roleCatalog.groups[0]
  const bots = []
  rt.state.templateBindings = {}
  for (const id of def.previousMembers) {
    const role = roleCatalog.roles.find(item => item.id === id)
    const bot = await rt.createBot({ name: role.previousNames[0], pickModel: true })
    bot.templateId = id
    rt.state.templateBindings[id] = bot.id
    bots.push(bot)
  }
  const room = await rt.createRoom({ name: def.previousNames[0], members: bots.map(bot => bot.id), admin: bots[0].id, notice: def.previousNotices[0] })
  room.templateId = def.id
  rt.state.templateBindings[def.id] = room.id
  const custom = await rt.createRoom({ name: '项目复盘小组', members: bots.map(bot => bot.id), admin: bots[1].id, notice: 'My custom notice' })
  custom.templateId = 'scene-2'
  rt.state.templateBindings['scene-2'] = custom.id
  const keptMembers = [...custom.members]
  rt.config.seedTeam = true
  await rt.save()
  await rt.bootstrap()
  assert.equal(rt.state.templateBindings[def.id], room.id)
  assert.equal(room.name, def.name)
  const chief = rt.state.mainBotIds[0]
  assert.deepEqual(room.members, [...bots.map(bot => bot.id), chief])
  assert.match(room.notice, /下游客户开发专家/)
  assert.equal(custom.name, '项目复盘小组')
  assert.equal(custom.notice, 'My custom notice')
  assert.deepEqual(custom.members, [...keptMembers, chief])
  assert.equal(custom.admin, bots[1].id)
  assert.equal(Object.keys(rt.state.rooms).length, 15)
})

async function version3Team(t) {
  const host = fixture(t, { companyConnectors: false })
  const { rt } = host
  await rt.bootstrap()
  const chief = rt.state.templateBindings.chemclaw
  for (const room of Object.values(rt.state.rooms)) {
    room.members = room.members.filter(id => id !== chief)
    room.templateVersion = 3
    room.templateDefaults.members = [...room.members]
    room.notice = `Generated version 3 notice: ${room.id}`
    room.templateDefaults.notice = room.notice
  }
  rt.state.presetTeamVersion = 3
  return { ...host, chief }
}

test('version 4 adds the renamed chief once to all existing presets, preserving custom groups and settings', async t => {
  const { rt, chief } = await version3Team(t)
  const rooms = Object.values(rt.state.rooms)
  const custom = rooms[0]
  const extra = rt.state.templateBindings['role-8-2']
  custom.members = [...custom.members.slice(1), extra]
  custom.admin = extra
  custom.name = 'My project team'
  custom.notice = 'My project instructions'
  custom.mode = 'everyone'
  custom.workDir = '/project'
  custom.permission = 'workspace-write'
  custom.sessions = { [extra]: 'existing-group-session' }
  custom.log = [{ who: 'You', text: 'Keep the history', seq: 1 }]
  custom.seq = 1
  rooms[1].admin = null
  rooms[2].members.push(chief)
  const chiefBot = rt.botOf(chief)
  chiefBot.name = '化工总协调'
  chiefBot.instructions = 'My coordinator instructions'
  chiefBot.avatar = { image: 'my-avatar' }
  chiefBot.model = { provider: 'mock', model: 'mock-model' }
  const keptChief = structuredClone(chiefBot)
  const personal = await rt.createRoom({ name: 'Personal room', members: custom.members.slice(0, 2), admin: custom.members[0], notice: 'Private instructions' })
  const keptPersonal = structuredClone(personal)
  const snapshots = rooms.map(room => structuredClone(room))
  await rt.save()
  await Promise.all([rt.bootstrap(), rt.bootstrap()])
  assert.equal(Object.keys(rt.state.bots).length, 50)
  assert.equal(Object.keys(rt.state.rooms).length, 16)
  for (let i = 0; i < rooms.length; i++) {
    const room = rooms[i]
    const before = snapshots[i]
    assert.deepEqual(room.members, [...new Set([...before.members, chief])])
    for (const key of ['id', 'name', 'admin', 'mode', 'workDir', 'permission', 'sessions', 'log', 'seq']) assert.deepEqual(room[key], before[key], `${room.name}: ${key}`)
    assert.equal(room.templateVersion, 4)
    if (room === custom) assert.equal(room.notice, before.notice)
    else assert.match(room.notice, /主控：化工总协调/)
  }
  assert.match(rooms[1].notice, /负责人：未设置/)
  assert.deepEqual(personal, keptPersonal)
  for (const key of ['id', 'name', 'instructions', 'avatar', 'model']) assert.deepEqual(chiefBot[key], keptChief[key])
  const roster = indexRoster({ bots: Object.values(rt.state.bots), rooms })
  for (const room of rooms) assert.deepEqual(mentionRows(roster, room.id, '化工总协调').map(row => row.text), ['@化工总协调 '])
  await rt.ensurePresetTeam()
  assert.deepEqual(custom.members, [...snapshots[0].members, chief])
})

test('full and deleted presets are skipped; later removal and freed space survive activation and restart', async t => {
  const { rt, ctx, home, chief } = await version3Team(t)
  const rooms = Object.values(rt.state.rooms)
  const full = rooms[0]
  full.members = Object.keys(rt.state.bots).filter(id => id !== chief).slice(0, ROOM_MAX_MEMBERS)
  const fullMembers = [...full.members]
  const removed = rooms[1]
  const deleted = rooms[2]
  delete rt.state.rooms[deleted.id]
  const warnings = []
  const warn = rt.warn
  rt.warn = (...args) => { warnings.push(args.join(' ')); warn(...args) }
  await rt.save()
  await rt.bootstrap()
  assert.deepEqual(full.members, fullMembers)
  assert.equal(full.templateVersion, 4)
  assert.match(warnings.join('\n'), /full preset group/)
  assert.equal(rt.roomOf(deleted.id), undefined)
  assert.equal(Object.values(rt.state.rooms).some(room => room.templateId === deleted.templateId), false)
  assert.equal(rt.state.templateBindings[deleted.templateId], deleted.id)
  await rt.updateRoom(removed.id, { remove: [chief] })
  await rt.updateRoom(full.id, { remove: [fullMembers.at(-1)] })
  await rt.activateScenario({ id: removed.templateId, kind: 'group' })
  await rt.activateScenario({ id: full.templateId, kind: 'group' })
  assert.equal(removed.members.includes(chief), false)
  assert.equal(full.members.includes(chief), false)
  await ctx.dispose()
  const restarted = fixture(t, { home, companyConnectors: false })
  await restarted.rt.bootstrap()
  assert.equal(restarted.rt.roomOf(removed.id).members.includes(chief), false)
  assert.equal(restarted.rt.roomOf(full.id).members.includes(chief), false)
  assert.equal(restarted.rt.roomOf(deleted.id), undefined)
})

test('a deleted preset specialist stays deleted while its existing group receives the chief', async t => {
  const { rt, chief } = await version3Team(t)
  const room = rt.roomOf(rt.state.templateBindings['scene-1'])
  const specialist = rt.state.templateBindings['role-1-2']
  await rt.deleteBot(specialist)
  const members = [...room.members]
  await rt.save()
  await rt.bootstrap()
  assert.deepEqual(room.members, [...members, chief])
  assert.equal(rt.botOf(specialist), undefined)
  assert.equal(Object.values(rt.state.bots).some(bot => bot.templateId === 'role-1-2'), false)
})

test('legacy credentials migrate out of shell scope; public chemistry guards block private tools and disconnection is visible', async t => {
  const { rt, ctx } = fixture(t, { companyConnectors: false })
  await rt.load(); await rt.loadSecrets()
  await rt.secretEndpoint('secret-set', { name: 'CHEM_DATA_HUB', value: 'synthetic-legacy-key', scope: ['*'] })
  rt.config.companyConnectors = true
  const count = ctx.listeners.get('tools/execute')?.length ?? 0
  installCompany(rt)
  // Saved credentials restore automatically, without visiting the connectors page.
  for (let i = 0; i < 100 && rt.connectorStatus('chem-data-hub').state !== 'ready'; i++) await new Promise(resolve => setTimeout(resolve, 10))
  assert.equal(rt.connectorStatus('chem-data-hub').state, 'ready')
  assert.deepEqual(rt.secretsView().find(item => item.name === 'CHEM_DATA_HUB').scope, [])
  const guard = ctx.guards.at(-1)
  assert.match(guard({ name: 'mcp__huagongshe__save_chemical' }), /disabled/)
  assert.match(guard({ name: 'mcp__huagongshe__search_chemistry_data', args: { mode: 'similarity' } }), /authorized/)
  assert.equal(guard({ name: 'mcp__huagongshe__get_chemical' }), undefined)
  const middleware = ctx.listeners.get('tools/execute')[count]
  const exec = { name: 'mcp__chem-data-hub__lookup' }
  await assert.rejects(middleware(exec, async () => { throw new Error('connection lost') }), /connection lost/)
  assert.equal(rt.connectorStatus('chem-data-hub').state, 'error')
  await middleware(exec, async () => ({ value: 'recovered' }))
  assert.equal(rt.connectorStatus('chem-data-hub').state, 'ready')
})

test('built-in skill refresh preserves user edits', async t => {
  const { rt } = fixture(t, { companyConnectors: false })
  await rt.bootstrap()
  const skill = rt.state.capabilities.items['chemclaw-delivery']
  assert.equal(skill.builtinSource, 'chemclaw')
  skill.content = 'Custom delivery instructions'
  await ensureSkillLibrary(rt)
  assert.equal(rt.state.capabilities.items['chemclaw-delivery'].content, 'Custom delivery instructions')
})

test('MCP import validates before saving and does not echo malformed authentication', () => {
  const doc = { mcpServers: { 'chem-data-hub': { type: 'http', url: 'https://datahub.chem-cloud.cn/mcp', headers: { Authorization: 'Bearer synthetic-test-token' } } } }
  assert.equal(parseMcpImport(doc)[0].token, 'synthetic-test-token')
  assert.throws(() => parseMcpImport('{ "Authorization":"synthetic-test-token"'), error => !error.message.includes('synthetic-test-token'))
  doc.mcpServers['chem-data-hub'].url = 'http://example.invalid/mcp'
  assert.throws(() => parseMcpImport(doc), /HTTPS/)
})

test('MCP import accepts HTTPS url-only Cursor JSON and skips stdio command servers', () => {
  const mixed = {
    mcpServers: {
      'qcc-company': { url: 'https://agent.qcc.com/mcp/company/stream', headers: { Authorization: 'Bearer synthetic-qcc-token' } },
      'qcc-document-mcp': { command: 'npx', args: ['-y', 'qcc-document-mcp'], env: { QCC_DOCUMENT_AUTHORIZATION: 'Bearer synthetic-qcc-token' } },
    },
  }
  const imported = parseMcpImport(mixed)
  assert.equal(imported.length, 1)
  assert.equal(imported[0].id, 'qcc-company')
  assert.equal(imported[0].token, 'synthetic-qcc-token')
  assert.deepEqual(imported.skipped, ['qcc-document-mcp'])
  assert.throws(() => parseMcpImport({
    mcpServers: { local: { command: 'npx', args: ['-y', 'qcc-document-mcp'] } },
  }), /Stdio MCP \(command\) is not supported: local/)
})

test('connector success, authentication failure, retry, timeout, replacement and disconnect keep credentials out of ordinary state', async t => {
  const f = fixture(t)
  await f.rt.load(); await f.rt.loadSecrets()
  const key = 'synthetic-test-credential'
  await f.rt.connectorEndpoint('connector-connect', { id: 'chem-data-hub', token: key })
  const company = () => f.rt.connectorsView().find(item => item.id === 'chem-data-hub')
  assert.equal(company().state, 'ready')
  assert.deepEqual(f.rt.secretsView().find(item => item.name === 'CHEM_DATA_HUB').scope, [])
  assert.ok(!JSON.stringify(f.rt.state).includes(key)); assert.ok(!JSON.stringify(company()).includes(key))
  f.outcome('401 unauthorized'); await f.rt.connectorEndpoint('connector-retry', { id: 'chem-data-hub' }); assert.equal(company().state, 'error'); assert.match(company().error, /401/)
  f.outcome('timeout'); await f.rt.connectorEndpoint('connector-retry', { id: 'chem-data-hub' }); assert.match(company().error, /timed out/)
  f.outcome('success'); await f.rt.connectorEndpoint('connector-connect', { id: 'chem-data-hub', token: 'replacement-test-credential' }); assert.equal(company().state, 'ready')
  await f.rt.connectorEndpoint('connector-disconnect', { id: 'chem-data-hub' }); assert.equal(company().state, 'off'); assert.equal(f.rt.secretValue('CHEM_DATA_HUB'), undefined)
  assert.ok(f.mounts.filter(item => item.config.serverName === 'chem-data-hub').every(item => item.disposed))
})

test('public adapters keep provenance and reject unavailable responses instead of inventing data', async () => {
  const url = publicUrl('pubchem', 'methanol')
  assert.match(url, /methanol/)
  const result = await fetchPublic(url, { fetch: async () => ({ ok: true, text: async () => '{"CID":887}' }) })
  assert.equal(result.source, url); assert.equal(result.data.CID, 887); assert.ok(result.retrievedAt)
  await assert.rejects(fetchPublic(url, { fetch: async () => ({ ok: false, status: 503 }) }), /No substitute/)
})

test('six business deliverable pipelines use bundled libraries inside the Bot workspace', async t => {
  const { rt, ctx } = fixture(t, { companyConnectors: false })
  await rt.bootstrap()
  const agent = { id: rt.chatOf(rt.state.mainBotIds[0]) }
  for (const [title, formats] of [['客户开发', 'html,xlsx'], ['供应商尽调', 'html,docx'], ['行情分析', 'html,xlsx'], ['基差研究', 'html,xlsx'], ['生产辅助', 'html,pdf'], ['PPT制作', 'html,pptx']]) {
    const report = { title: `${title}工具链验收（模拟数据）`, sections: [{ title: '测试证据链', table: { columns: ['字段', '内容'], rows: [['来源', 'mock，不代表业务事实']] } }], sources: [{ label: '原创验收数据' }], limitations: '仅验证交付，不验证研究质量' }
    const result = JSON.parse(await ctx.registeredTools.get('chem_deliver').execute({ report: JSON.stringify(report), formats }, { agent, signal: AbortSignal.timeout(60000) }))
    assert.equal(result.files.length, 2)
    // Windows CI often mixes 8.3 short paths (RUNNER~1) with long ones (runneradmin);
    // native realpath expands both to the same form.
    const expand = path => (realpathSync.native ?? realpathSync)(path)
    const roots = [...new Set([rt.teamFolder(), rt.defaultTeamFolder(), rt.home].filter(Boolean))].map(expand)
    for (const file of result.files) {
      const abs = expand(file.path)
      assert.ok(roots.some((root) => {
        const rel = relative(root, abs)
        return rel === '' || (!rel.startsWith('..') && !isAbsolute(rel))
      }), `${abs} is outside ${roots.join(' | ')}`)
      assert.ok(readFileSync(file.path).length > 100)
    }
    assert.match(result.next, /present/)
  }
  await assert.rejects(ctx.registeredTools.get('chem_deliver').execute({ report: '{}', formats: 'html' }, { agent: { id: 'unrelated-session' } }), /ChemClaw Bot/)
})
