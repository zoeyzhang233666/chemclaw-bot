import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { apply } from './legacy-runtime.js'
import { fakeContext } from './fake-ctx.js'
import { deleteSidebarCategory, botCategoryId } from '../src/shared/sidebar-prefs.js'

test('category names, assignments and explicit collapse persist through the public prefs endpoint and restart', async t => {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-categories-'))
  t.after(() => rmSync(home, { recursive: true, force: true, maxRetries: 5 }))
  writeFileSync(join(home, 'state.json'), JSON.stringify({
    version: 1, mainBotIds: ['main'], revision: 1,
    bots: { main: { id: 'main', name: 'Chief', createdAt: 1 }, expert: { id: 'expert', name: 'Expert', createdAt: 2 } },
    rooms: {}, exchanges: [], exchangeTurns: {}, questions: {},
  }))
  const start = async () => {
    const ctx = fakeContext()
    const routes = {}
    const register = ctx.connection.fetch.register
    ctx.connection.fetch.register = options => { routes[options.path] = options; return register(options) }
    apply(ctx, { home })
    const call = async (endpoint, payload = {}) => {
      const response = await routes['/api/bot'].fetch(new Request('http://localhost/api/bot', {
        method: 'POST', body: JSON.stringify({ endpoint, payload }),
      }))
      return response.json()
    }
    await call('state')
    return { ctx, call }
  }
  const first = await start()
  const category = { id: 'custom:business', kind: 'bot', name: 'New business' }
  try {
    const saved = await first.call('set-prefs', { sidebar: { categories: [category], categoryAssignments: { 'bot:expert': category.id } } })
    assert.equal(saved.ok, true)
    const state = await first.call('state')
    assert.equal(state.value.prefs.sidebar.collapsed, undefined)
    await first.call('set-prefs', { sidebar: { categories: [{ ...category, name: 'Renamed business' }], collapsed: [category.id] } })
  } finally { await first.ctx.dispose() }
  const second = await start()
  try {
    const state = await second.call('state')
    assert.deepEqual(state.value.prefs.sidebar.categories, [{ ...category, name: 'Renamed business' }])
    assert.equal(state.value.prefs.sidebar.categoryAssignments['bot:expert'], category.id)
    assert.deepEqual(state.value.prefs.sidebar.collapsed, [category.id])
    const disk = JSON.parse(readFileSync(join(home, 'state.json'), 'utf8'))
    assert.equal(disk.bots.expert.name, 'Expert')
    const deleted = await second.call('set-prefs', { sidebar: deleteSidebarCategory(state.value, { ...category, name: 'Renamed business' }) })
    assert.ok(deleted.value.sidebar.deletedCategories.includes(category.id))
  } finally { await second.ctx.dispose() }
  const third = await start()
  try {
    const state = await third.call('state')
    assert.ok(state.value.bots.some(bot => bot.id === 'expert'))
    assert.equal(botCategoryId(state.value.bots.find(bot => bot.id === 'expert'), state.value.prefs.sidebar), '通用交付')
    assert.ok(!state.value.prefs.sidebar.categories.some(item => item.id === category.id))
    assert.ok(state.value.prefs.sidebar.deletedCategories.includes(category.id))
  } finally { await third.ctx.dispose() }
})
