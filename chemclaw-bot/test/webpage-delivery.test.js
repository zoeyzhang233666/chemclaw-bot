import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fakeContext } from './fake-ctx.js'
import { install as installWebpage } from '../src/host/webpage-tool.js'
import { deliver } from '../runtime/deliver.mjs'

test('model-authored webpage is written unchanged with no template and no fallback', async t => {
  const root = await mkdtemp(join(tmpdir(), 'chemclaw-authored-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  const ctx = fakeContext()
  ctx.sessionController = { resolveAgent: async () => ({ agent: { session: {} } }) }
  installWebpage({ ctx, readOnly: () => false, selfOf: id => id === 'bot' ? id : null,
    sessionFolder: () => root, teamFolder: () => root, defaultTeamFolder: () => root, inData: async () => false })
  const tool = ctx.registeredTools.get('chem_write_webpage')
  const html = '<!doctype html><html><head><style>.custom{display:grid}</style></head><body><main class="custom">乙二醇</main><script>window.owned=true</script></body></html>'
  const exec = { agent: { id: 'bot' } }
  const result = JSON.parse(await tool.execute({ html, filename: '乙二醇看板.html' }, exec))
  assert.equal(await readFile(result.files[0].path, 'utf8'), html)
  assert.match(result.next, /No template or fallback/)
  await assert.rejects(tool.execute({ html, filename: '../escape.html' }, exec), /safe .html filename/)
  await assert.rejects(tool.execute({ html: '', filename: 'empty.html' }, exec), /no template or fallback/)
  await assert.rejects(tool.execute({ html, filename: 'ok.html' }, { agent: { id: 'stranger' } }), /ChemClaw Bot/)
})

test('report renderer rejects HTML instead of generating a fallback page', async t => {
  const root = await mkdtemp(join(tmpdir(), 'chemclaw-nonhtml-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  await assert.rejects(deliver({ title: 'Sample', sections: [] }, root, ['html']), /Unsupported format: html/)
})
