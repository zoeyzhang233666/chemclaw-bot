// ChemClaw: a chemical-industry team of long-lived Bots on top of ordinary dsh root Sessions.
// Forked from DS Bot (Apache-2.0); every Bot is one root Session. Roster, rooms, and the
// bot-to-bot exchange log live in one JSON file under DSH_HOME/chemclaw so they survive
// restarts without new Session event types, and stay isolated from a co-installed ds-bot.
import { join } from 'node:path'
import * as diagnostics from './src/host/diagnostics.js'
import * as store from './src/host/store.js'
import * as models from './src/host/models.js'
import * as providers from './src/host/providers.js'
import * as permissions from './src/host/permissions.js'
import * as turns from './src/host/turns.js'
import * as handoffs from './src/host/handoffs.js'
import * as delivery from './src/host/delivery.js'
import * as roster from './src/host/roster.js'
import * as folders from './src/host/folders.js'
import * as agents from './src/host/agents.js'
import * as prompt from './src/host/prompt.js'
import * as timeContext from './src/host/time-context.js'
import * as tools from './src/host/tools.js'
import * as chatIndex from './src/host/chat-index.js'
import * as groups from './src/host/groups.js'
import * as groupStream from './src/host/group-stream.js'
import * as responseTiming from './src/host/response-timing.js'
import * as approvals from './src/host/approvals.js'
import * as resume from './src/host/resume.js'
import * as memory from './src/host/memory.js'
import * as parts from './src/host/parts.js'
import * as images from './src/host/images.js'
import * as browser from './src/host/browser.js'
import * as secrets from './src/host/secrets.js'
import * as connectors from './src/host/connectors.js'
import * as companyConnectors from './src/host/company-connectors.js'
import * as capabilities from './src/host/capabilities.js'
import * as skillRouting from './src/host/skill-routing.js'
import * as scenarios from './src/host/scenarios.js'
import * as publicData from './src/host/public-data.js'
import * as dependencies from './src/host/dependencies.js'
import * as artifactTools from './src/host/artifact-tools.js'
import * as schedules from './src/host/schedules.js'
import * as usage from './src/host/usage.js'
import * as update from './src/host/update.js'
import * as dshUpdate from './src/host/dsh-update.js'
import * as thinking from './src/host/thinking.js'
import * as channel from './src/host/channel.js'
import * as feed from './src/host/feed.js'

export { COLORS } from './src/host/constants.js'

export const name = 'chemclaw-bot'
export const inject = ['llm', 'tools', 'systemPrompt', 'sessionController', 'sessions', 'sessionTitle', 'workspaceRegistry', 'connection']

// Each module's install(rt) registers its listeners, tools, and effects, and puts on `rt`
// the functions other modules call; they call them through `rt` at run time, never during
// install. Listeners run and tools are listed in registration order, so this order holds:
// usage meters model requests after every listener that rewrites them.
const MODULES = [diagnostics, store, models, providers, permissions, turns, handoffs, delivery, roster, folders, agents, prompt, timeContext, skillRouting, tools, chatIndex, groups, groupStream, approvals, resume, memory, parts, images, responseTiming, secrets, connectors, companyConnectors, capabilities, scenarios, schedules, browser, usage, update, dshUpdate, thinking, feed, channel]

export function apply(ctx, config = {}) {
  createRuntime(ctx, config)
}

export function createRuntime(ctx, config = {}) {
  const dshHome = folders.dshHomeOf(process.env.DSH_HOME)
  const home = config.home ?? join(dshHome, 'chemclaw')
  const rt = {
    ctx,
    config,
    dshHome,
    home,
    statePath: join(home, 'state.json'),
    defaults: {
      mainName: config.mainName ?? 'ChemClaw',
      mainRole: config.mainRole ?? '化工主控',
    },
  }
  for (const module of [...MODULES.slice(0, -1), publicData, dependencies, artifactTools, channel]) module.install(rt)
  return rt
}
