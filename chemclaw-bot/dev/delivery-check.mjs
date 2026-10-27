import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { setTimeout as sleep } from 'node:timers/promises'

const [name, port] = process.argv.slice(2)
if (!/^[a-z0-9-]+$/.test(name) || !/^\d+$/.test(port)) throw new Error('Use an isolated bench name and port')
const home = resolve(import.meta.dirname, '../..', `.dsh-test-${name}`)
const base = `http://127.0.0.1:${port}`
const login = readFileSync(resolve(home, 'web.log'), 'utf8').match(/http:\/\/127\.0\.0\.1:\d+\/\?token=[^\s]+/)[0]
const auth = await fetch(login, { redirect: 'manual' })
const cookie = auth.headers.getSetCookie().map(value => value.split(';')[0]).join('; ')
const api = async (endpoint, payload = {}) => {
  const response = await fetch(`${base}/api/bot`, { method: 'POST', headers: { 'content-type': 'application/json', cookie }, body: JSON.stringify({ endpoint, payload }) })
  const answer = await response.json()
  if (!answer.ok) throw new Error(`${endpoint}: ${answer.error?.message}`)
  return answer.value
}
const saved = () => JSON.parse(readFileSync(resolve(home, 'chemclaw/state.json'), 'utf8'))
const wait = async check => {
  const end = Date.now() + 40_000
  while (Date.now() < end) { if (await check()) return; await sleep(300) }
  throw new Error('The looping mock did not automatically deliver its answer')
}
const view = await api('state')
const chief = view.bots.find(bot => bot.id === view.mainBotId)
await api('update-bot', { id: chief.id, model: view.models.at(-1).ref })
await wait(async () => !Object.keys((await api('state')).activity ?? {}).length)
await api('send', { sessionId: chief.id, text: '长任务 1000 0' })
await wait(() => {
  const task = Object.values(saved().answerRuns?.tasks ?? {}).find(item => item.owner === chief.id && item.steps > 4)
  return task?.phase === 'done' && task.notes.some(note => note.text.includes('自动收敛完成'))
})
const task = Object.values(saved().answerRuns.tasks).find(item => item.owner === chief.id && item.steps > 4)
assert.ok(task.finalSteps <= 3)
assert.ok(Date.now() - task.started < 30_000)
await api('send', { sessionId: chief.id, text: '新问题：你好' })
await wait(() => Object.values(saved().answerRuns.tasks).some(item => item.owner === chief.id && item.id !== task.id && item.started >= task.started && item.notes.length > 0 && item.steps <= 4 && item.finalSteps === undefined))
console.log('delivery-check: looping private task delivered automatically within the shared budget; new input works')
const writer = await api('create-bot', { name: 'Writer', role: 'Research', model: view.models.at(-1).ref })
await wait(async () => !Object.keys((await api('state')).activity ?? {}).length)
const room = await api('create-room', { name: 'Delivery check', members: [chief.id, writer.id], admin: chief.id })
await wait(async () => !Object.keys((await api('state')).activity ?? {}).length)
await api('send', { sessionId: room.id, text: '自动收敛群验收' })
await wait(() => Object.values(saved().answerRuns.tasks).some(item => item.owner === room.id && item.phase === 'done' && item.finalSteps > 0 && item.notes.some(note => note.text.includes('自动收敛完成'))))
await wait(() => saved().rooms[room.id].log.some(line => line.text?.includes('自动收敛完成')))
assert.equal(saved().rooms[room.id].paused?.length ?? 0, 0)
console.log('delivery-check: looping group delivered its final answer without a manual Continue')
