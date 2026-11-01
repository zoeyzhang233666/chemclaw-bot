// Check ChemClaw's registration boundary, not just the existence of bundled SKILL.md files.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install } from '../src/host/office-skills.js'

test('ChemClaw Office install actually registers an invocable DSH skill provider', async () => {
  let registry
  const rt = { ctx: {
    inject(services, onReady) {
      assert.ok(Object.hasOwn(services, 'skills'))
      onReady({ skills: {
        registerProvider(factory) { registry = factory(); return () => {} },
      } })
    },
  } }
  install(rt)
  assert.equal(registry?.name, 'chemclaw-office')
  const items = await registry.list()
  assert.deepEqual(items.map(item => item.name), ['office', 'office-tools'])
  assert.ok(items.every(item => item.invocation.modelInvocable && item.invocation.userInvocable))
  const loaded = await registry.get(items.find(item => item.name === 'office-tools'))
  assert.match(loaded.content, /Office tools/)
  assert.match(loaded.content, /officeTools/)
  assert.ok(loaded.resourceBase?.path?.includes('src/office/skills/office-tools'))
})
