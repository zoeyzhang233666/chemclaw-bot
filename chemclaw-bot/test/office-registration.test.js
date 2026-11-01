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


test('ChemClaw exposes a read-only Office runtime diagnostics tool', async () => {
  let tool
  const rt = { ctx: {
    inject() {},
    tools: {
      register(definition) { tool = definition; return () => {} },
    },
  } }
  install(rt)
  assert.equal(tool?.name, 'chem_office_runtime_status')
  const result = JSON.parse(await tool.execute({}))
  assert.equal(typeof result.payloadComplete, 'boolean')
  assert.equal(typeof result.nativeToolRegistration, 'string')
  assert.ok(result.python && result.node && result.overlay)
})
