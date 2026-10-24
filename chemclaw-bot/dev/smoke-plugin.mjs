#!/usr/bin/env node
// Structural smoke for chemclaw-bot as a DSH plugin (no write to ~/.dsh).
// Usage: node dev/smoke-plugin.mjs
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const fail = (msg) => { console.error(`FAIL: ${msg}`); process.exitCode = 1 }
const ok = (msg) => console.log(`OK: ${msg}`)

const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))
if (pkg.name !== 'chemclaw-bot') fail(`package name is ${pkg.name}`)
else ok(`package ${pkg.name}@${pkg.version}`)

if (!pkg.keywords?.includes('dsh-plugin')) fail('missing keywords dsh-plugin')
else ok('dsh-plugin keyword')

if (pkg.dsh?.bundle?.patch !== './cordis.patch.yml') fail('dsh.bundle.patch missing')
else ok('dsh.bundle.patch')

const patch = readFileSync(join(root, 'cordis.patch.yml'), 'utf8')
if (!/id:\s*chemclaw\b/.test(patch) || !/name:\s*chemclaw-bot\b/.test(patch)) fail('cordis.patch.yml id/name')
else ok('cordis id chemclaw / name chemclaw-bot')
if (!/chemclaw-bot\/web-search/.test(patch)) fail('web-search mount')
else ok('web-search-auto mount')

const index = readFileSync(join(root, 'index.js'), 'utf8')
if (!/export const name = 'chemclaw-bot'/.test(index)) fail('index export name')
else ok('index.js export name')
if (!/join\(dshHome, 'chemclaw'\)/.test(index)) fail('home dir chemclaw')
else ok('home $DSH_HOME/chemclaw')
if (!/mainName:.*ChemClaw/.test(index) || !/化工主控/.test(index)) fail('mainName/mainRole defaults')
else ok('defaults ChemClaw / 化工主控')

const client = readFileSync(join(root, 'client.js'), 'utf8')
if (!/id: 'chemclaw-bot'/.test(client)) fail('client.js module id stale — run npm run build')
else ok('client.js id chemclaw-bot')

const seedBots = JSON.parse(readFileSync(join(root, 'seed', 'bots.json'), 'utf8'))
const bots = seedBots.bots ?? []
const rooms = seedBots.rooms ?? []
if (bots.length < 20) fail(`expected ~22 bots, got ${bots.length}`)
else ok(`seed bots ${bots.length}`)
if (rooms.length !== 5) fail(`expected 5 rooms, got ${rooms.length}`)
else ok(`seed rooms ${rooms.length}`)

const library = JSON.parse(readFileSync(join(root, 'seed', 'capabilities-library.json'), 'utf8'))
const items = Object.values(library.items ?? {})
const packs = items.filter(i => i.kind === 'pack').length
const mcps = items.filter(i => i.kind === 'mcp').length
if (mcps < 4 || packs < 10) fail(`capabilities thin: mcp=${mcps} pack=${packs}`)
else ok(`capabilities mcp=${mcps} skill=${items.filter(i => i.kind === 'skill').length} pack=${packs}`)

const mcpDir = join(root, 'capabilities', 'mcp')
const mcpFiles = existsSync(mcpDir) ? readdirSync(mcpDir).filter(n => n.endsWith('.json')) : []
if (mcpFiles.length < 4) fail(`capabilities/mcp json count ${mcpFiles.length}`)
else ok(`capabilities/mcp ${mcpFiles.length} files`)

const skillRoot = join(root, 'skills')
if (!existsSync(skillRoot)) fail('skills/ missing')
else {
  let n = 0
  const walk = (d) => {
    for (const name of readdirSync(d)) {
      const p = join(d, name)
      if (statSync(p).isDirectory()) walk(p)
      else if (name === 'SKILL.md') n++
    }
  }
  walk(skillRoot)
  if (n < 20) fail(`SKILL.md count ${n}`)
  else ok(`bundled SKILL.md ${n}`)
}

const seedMod = await import(pathToFileURL(join(root, 'src', 'host', 'chemclaw-seed.js')).href)
if (typeof seedMod.seedChemClawTeam !== 'function') fail('seedChemClawTeam export')
else ok('seedChemClawTeam export')

const roster = readFileSync(join(root, 'src', 'host', 'roster.js'), 'utf8')
if (!/seedChemClawTeam/.test(roster)) fail('roster bootstrap not wired to seed')
else ok('roster bootstrap → chemclaw-seed')

console.log(process.exitCode ? '\nSmoke FAILED' : '\nSmoke PASSED — add this folder in DSH Desktop: Plugins → Add → local path')
console.log(`  ${root}`)
console.log('Or: npm pack && add the resulting .tgz')
