import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { apply } from '../index.js'
import { fakeContext } from './fake-ctx.js'

for (const failed of [false, true]) test(`team readiness is ${failed ? 'absent after activation failure' : 'available only while the plugin is active'}`, async t => {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-readiness-'))
  const ctx = fakeContext()
  t.after(async () => { await ctx.dispose(); rmSync(home, { recursive: true, force: true, maxRetries: 5 }) })
  const config = { home, seedTeam: false, companyConnectors: false, updateCheck: false, ...(failed ? { browserPlugin: 'missing' } : {}) }
  if (failed) {
    assert.throws(() => apply(ctx, config), /browser plugin/i)
    assert.equal(ctx.get('chemclawReady'), undefined)
  } else {
    apply(ctx, config)
    assert.equal(await ctx.get('chemclawReady').check(), true)
    await ctx.dispose()
    assert.equal(ctx.get('chemclawReady'), undefined)
  }
})
