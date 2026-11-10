import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { parse } from 'yaml'
import { DebugLogger } from 'builder-util'
import { doMergeConfigs, validateConfiguration } from 'app-builder-lib/out/util/config/config.js'

test('the DMG installer is valid for the pinned builder and preserves ad-hoc signing and ZIP compatibility', async () => {
  const base = parse(readFileSync(new URL('../electron-builder.yml', import.meta.url), 'utf8'))
  const preview = parse(readFileSync(new URL('../electron-builder.mac-dmg.yml', import.meta.url), 'utf8'))
  const config = doMergeConfigs([base, preview])
  delete config.extends
  await validateConfiguration(config, new DebugLogger(false))
  assert.equal(config.appId, base.appId)
  assert.deepEqual(config.mac.target, ['dmg', 'zip'])
  assert.equal(config.mac.identity, '-')
  assert.equal(config.mac.hardenedRuntime, false)
  assert.equal(config.mac.notarize, false)
  assert.equal(config.dmg.contents.find(item => item.type === 'link').path, '/Applications')
})
