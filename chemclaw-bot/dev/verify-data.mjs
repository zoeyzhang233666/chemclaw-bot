import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const folder = resolve('../chemclaw/verification')
mkdirSync(folder, { recursive: true })
const python = resolve('../.dsh-test-live/runtime/python/Scripts/python.exe')
for (const args of [{ market: 'domestic', symbol: 'M0', start: '2026-10-01' }, { market: 'foreign', symbol: 'CL', start: '2026-10-01' }]) {
  const data = JSON.parse(execFileSync(python, [resolve('runtime/futures.py'), JSON.stringify(args)], { encoding: 'utf8', timeout: 120000, windowsHide: true }))
  writeFileSync(resolve(folder, `${args.market}-futures.json`), JSON.stringify(data, null, 2))
  console.log(JSON.stringify({ market: args.market, symbol: args.symbol, rows: data.data?.length, asOf: data.asOf, error: data.error }))
}
let session
const endpoint = 'https://huagongshe.com/mcp'
const rpc = async (method, params, id) => {
  const response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream', ...(session ? { 'Mcp-Session-Id': session } : {}) }, body: JSON.stringify({ jsonrpc: '2.0', ...(id ? { id } : {}), method, params }), signal: AbortSignal.timeout(30000) })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  session = response.headers.get('mcp-session-id') ?? session
  const text = await response.text()
  if (!text) return
  return text.startsWith('event:') || text.startsWith('data:') ? JSON.parse(text.split('\n').find(line => line.startsWith('data:')).slice(5)) : JSON.parse(text)
}
try {
  await rpc('initialize', { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'ChemClaw verification', version: '0.2.0' } }, 1)
  await rpc('notifications/initialized', {})
  const list = await rpc('tools/list', {}, 2)
  const tools = list.result?.tools ?? []
  writeFileSync(resolve(folder, 'huagongshe-tools.json'), JSON.stringify(tools, null, 2))
  console.log(JSON.stringify({ service: 'huagongshe', anonymous: true, tools: tools.map(tool => tool.name) }))
  const search = tools.find(tool => tool.name === 'search_chemistry_data')
  if (search) console.log(JSON.stringify({ searchSchema: search.inputSchema }))
  for (const [name, args] of [['search_chemistry_data', { q: 'methanol', mode: 'exact', page_size: 3 }], ['render_molecule_svg', { smiles: 'CO', width: 400, height: 300 }]]) {
    const result = await rpc('tools/call', { name, arguments: args }, 3)
    writeFileSync(resolve(folder, `huagongshe-${name}.json`), JSON.stringify(result, null, 2))
    if (result.error || result.result?.isError) throw new Error(`${name}: public query failed`)
    console.log(JSON.stringify({ service: 'huagongshe', tool: name, success: true }))
  }
} catch (error) { writeFileSync(resolve(folder, 'huagongshe-status.json'), JSON.stringify({ state: 'error', error: error.message })); console.log(JSON.stringify({ service: 'huagongshe', error: error.message })) }
