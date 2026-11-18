// Confirm the ChemClaw.cmd / packaged plugin copy includes the group latency fixes.
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const app = join(dirname(fileURLToPath(import.meta.url)), '..')
const plugin = join(app, 'node_modules', 'chemclaw-bot')
assert.ok(existsSync(plugin), 'chemclaw-bot must be installed under app/node_modules (run 启动 ChemClaw.cmd or launch --sync-only)')

const groupStream = readFileSync(join(plugin, 'src/host/group-stream.js'), 'utf8')
assert.match(groupStream, /commitRoomDraft/, 'sticky draft commit missing')
assert.match(groupStream, /draft\.held/, 'held draft flag missing')
assert.doesNotMatch(groupStream, /drafts\.delete\(session\.id\)/, 'must not clear drafts on assistant/message alone')

const groups = readFileSync(join(plugin, 'src/host/groups.js'), 'utf8')
assert.match(groups, /warmRoom/, 'warmRoom missing')
assert.match(groups, /warmRoomsIdle/, 'warmRoomsIdle missing')
assert.match(groups, /pendingBriefs/, 'pendingBriefs missing')
assert.match(groups, /commitRoomDraft/, 'postInRound must commit drafts')

const channel = readFileSync(join(plugin, 'src/host/channel.js'), 'utf8')
assert.match(channel, /warm-room/, 'warm-room channel missing')
assert.match(channel, /roomDrafts/, 'room-progress drafts missing')

const client = readFileSync(join(plugin, 'client.js'), 'utf8')
assert.match(client, /warmRoom/, 'client warmRoom missing')
assert.match(client, /posted\.has/, 'client must filter draft duplicates after commit')

console.log('Group latency fix present in app/node_modules/chemclaw-bot (ChemClaw.cmd and packaged exe share this plugin path).')
