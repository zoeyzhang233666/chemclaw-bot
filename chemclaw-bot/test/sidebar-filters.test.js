import assert from 'node:assert/strict'
import { test } from 'node:test'
import { build } from 'esbuild'
import { runInNewContext } from 'node:vm'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
const { outputFiles } = await build({
  stdin: { contents: "export { fitShortcuts } from './src/client/sidebar-filters.js'", resolveDir: dirname(dirname(fileURLToPath(import.meta.url))) },
  bundle: true, write: false, format: 'cjs', platform: 'node', external: ['react'], logLevel: 'silent',
})
const module = { exports: {} }
runInNewContext(outputFiles[0].text, { module, exports: module.exports, require: () => ({}) })
const { fitShortcuts } = module.exports
test('shortcuts fit one line and more return as the sidebar grows', () => {
  const widths = [42, 68, 68, 80]
  assert.equal(fitShortcuts(widths, 50), 1)
  assert.equal(fitShortcuts(widths, 120), 2)
  assert.equal(fitShortcuts(widths, 196), 3)
  assert.equal(fitShortcuts(widths, 300), 4)
  assert.equal(fitShortcuts([42, 400, 68], 120), 2)
})
