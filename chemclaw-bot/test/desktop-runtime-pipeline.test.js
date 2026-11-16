import assert from 'node:assert/strict'
import { test } from 'node:test'
import { Context } from '@deepseek-ai/cordis'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import Tools, { defineTool } from '@deepseek-ai/dsh-tools'
import { install } from '../src/host/desktop-runtime.js'

const NativeExecutor = await import('@deepseek-ai/dsh-tool-executor-native').catch(error => {
  if (error?.code === 'ERR_MODULE_NOT_FOUND') return undefined
  throw error
})

test('the real DSH tool pipeline reports an ordinary Agent probe as a tool error before dispatch', async t => {
  const ctx = new Context()
  t.after(() => ctx.fiber.dispose())
  await ctx.plugin(SystemPrompt)
  await ctx.plugin(Tools)
  if (NativeExecutor) await ctx.plugin(NativeExecutor)
  let calls = 0
  ctx.tools.register(defineTool({
    name: 'bash', description: 'A shell stub that never starts a process.',
    parameters: { command: { type: 'string', required: true } },
    output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
    execute: () => { calls++; return 'static check passed' },
  }))
  const executable = '/Applications/ChemClaw.app/Contents/MacOS/ChemClaw'
  install({ ctx }, { env: { DS_BOT_APP: '1' }, executable })
  const execute = async command => {
    const signal = new AbortController().signal
    if (typeof ctx.tools.selectExecutor !== 'function') {
      return ctx.tools.execute({ signal, callId: 'check', name: 'bash', arguments: { command } })
    }
    const batch = await ctx.tools.execute({ signal, calls: [{ id: 'check', name: 'bash', arguments: JSON.stringify({ command }) }] })
    return batch.results[0].result
  }
  const blocked = await execute(`"${executable}" -e "process._linkedBinding('electron_browser_app')"`)
  assert.equal(blocked.isError, true)
  assert.match(blocked.error.message, /browser rendering was not verified/)
  assert.equal(calls, 0, 'the ordinary tool body never ran')
  const allowed = await execute('node --check page.js')
  assert.equal(allowed.isError, false)
  assert.equal(calls, 1)
})
