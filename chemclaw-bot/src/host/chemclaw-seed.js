// First-run ChemClaw team: capabilities library, specialty Bots, and preset rooms.
// Loaded only when the roster is empty (no Main Bot yet). Secrets stay out of the package.
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const packageRoot = join(here, '..', '..')
const seedDir = join(packageRoot, 'seed')

const MAIN_KICKOFF = `你刚被设为用户的化工主控 ChemClaw。用一两句短消息打招呼：说明你会统筹化工 Bot 团队（潜客/寻源/行情/尽调/交付/质询等），用户可随时找你拍板。

然后用一两句说明首次配置：
1) 对话上方有「只需填 Key」卡片：粘贴 CHEM_DATA_HUB（芯化和云数据中台）和 CHEM_BIZ_SCOPE（业务范围）。MCP 地址已预置，不要把密钥写进聊天；也可用 request_secret，勿用 ask_user/show_view 收密钥。
2) 五个预置群聊已建好（客户开发 / 采购寻源 / 期现研究 / 进出口 / 交付工坊）。

最后用一个短问题问用户：想先做哪类化工任务（找客户、寻源、行情、尽调、还是做 PPT/表格）？用中文写。`

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function loadSeed() {
  const botsPath = join(seedDir, 'bots.json')
  const libraryPath = join(seedDir, 'capabilities-library.json')
  if (!existsSync(botsPath) || !existsSync(libraryPath)) {
    throw new Error(`ChemClaw seed missing under ${seedDir}`)
  }
  const botsSeed = readJson(botsPath)
  const library = readJson(libraryPath)
  const routings = existsSync(join(seedDir, 'routings.json')) ? readJson(join(seedDir, 'routings.json')) : {}
  return { botsSeed, library, routings }
}

function skillPathHint(item) {
  if (!item?.sourcePath) return ''
  const abs = join(packageRoot, item.sourcePath.replace(/\\/g, '/'))
  return existsSync(abs) ? `\n\n完整 skill 文件（插件内）：\`${abs}\`` : `\n\n完整 skill 相对路径：\`${item.sourcePath}\``
}

function enrichSkillContent(item) {
  if (item.kind !== 'skill') return item
  const hint = skillPathHint(item)
  if (!hint) return item
  if (String(item.content ?? '').includes('完整 skill')) return item
  return { ...item, content: `${item.content ?? ''}${hint}` }
}

function sortCapabilities(items) {
  const entries = Object.values(items)
  const mcp = entries.filter(i => i.kind === 'mcp')
  const skill = entries.filter(i => i.kind === 'skill')
  const pack = entries.filter(i => i.kind === 'pack')
  return [...mcp, ...skill, ...pack]
}

function instructionsFor(botDef, routings, qualityPolicy) {
  const routes = routings[botDef.id] ?? []
  const routeLines = routes.length
    ? routes.map(r => `- 触发「${(r.triggers ?? []).join(' / ')}」→ 场景 ${r.scene}${r.skill ? `，优先 skill \`${r.skill}\`` : ''}${r.mcp ? `，MCP ${r.mcp.join(',')}` : ''}${r.handoff ? `，可交接 ${(r.handoff ?? []).join('、')}` : ''}`).join('\n')
    : '- 按角色与已挂载 pack 响应；不确定时请示 ChemClaw。'
  const policy = (qualityPolicy ?? []).map(line => `- ${line}`).join('\n')
  return [
    `你是 ChemClaw 团队的「${botDef.name}」（角色：${botDef.role}）。`,
    '',
    '## 质量政策',
    policy || '- 禁止编造价格与企业事实；缺口标 gap。',
    '',
    '## 场景路由（L1 优先）',
    routeLines,
    '',
    '## 协作',
    '- 业务事实以 MCP / 公开数据 + domain skill 契约为准。',
    '- 跟流程不跟像素：examples 仅参考；版式可优于示例，字段与溯源必须满足契约。',
    '- 重要交付前可请质询官压测；大单可请流程参谋拆解。',
  ].join('\n')
}

/**
 * Seed an empty ChemClaw roster: library → specialty Bots → rooms → main kickoff.
 * @param {any} rt runtime from createRuntime
 */
export async function seedChemClawTeam(rt) {
  const { botsSeed, library, routings } = loadSeed()
  const qualityPolicy = botsSeed.qualityPolicy ?? []
  const botDefs = (botsSeed.bots ?? []).filter(b => !b.main)
  const mainDef = (botsSeed.bots ?? []).find(b => b.main) ?? { name: rt.defaults.mainName, role: rt.defaults.mainRole, packs: ['pack-mcp-core', 'pack-process'] }

  // 1) Capabilities library (MCP → skills → packs)
  for (const raw of sortCapabilities(library.items ?? {})) {
    const item = enrichSkillContent(raw)
    try {
      await rt.capabilitySave({
        name: item.name,
        kind: item.kind,
        description: item.description ?? '',
        ...(item.kind === 'mcp' ? {
          transport: item.transport,
          url: item.url,
          command: item.command,
          args: item.args,
          env: item.env,
          headers: item.headers,
        } : {}),
        ...(item.kind === 'skill' ? { content: item.content ?? '' } : {}),
        ...(item.kind === 'pack' ? { items: item.items ?? [] } : {}),
      }, { ui: true })
    } catch (error) {
      rt.warn?.('chemclaw-bot: capability %s not saved: %s', item.name, error)
    }
  }

  // 2) Main Bot
  const main = await rt.createBot({
    name: mainDef.name ?? rt.defaults.mainName,
    role: mainDef.role ?? rt.defaults.mainRole,
    main: true,
    color: mainDef.color ?? 'deepseek',
    avatar: { shape: 'whale' },
    pickModel: true,
    instructions: instructionsFor({ ...mainDef, id: mainDef.id ?? 'chemclaw' }, routings, qualityPolicy),
  })
  main.capabilities = [...(mainDef.packs ?? [])]
  if (main.kickoff) {
    main.kickoff = { ...main.kickoff, text: `${MAIN_KICKOFF}\nWhere your instructions say otherwise, follow them.` }
  }
  await rt.save()

  // 3) Specialty Bots (no greeting spam)
  const byName = new Map([[main.name, main]])
  for (const def of botDefs) {
    try {
      const bot = await rt.createBot({
        name: def.name,
        role: def.role ?? '',
        color: def.color,
        instructions: instructionsFor(def, routings, qualityPolicy),
        brief: `ChemClaw 专岗：${def.name}。按挂载的 domain/process skills 与 MCP 工作；不要编造业务事实。`,
        createdBy: main.id,
      })
      bot.capabilities = [...(def.packs ?? [])]
      rt.dropKickoff?.(bot.id)
      byName.set(bot.name, bot)
      await rt.save()
    } catch (error) {
      rt.warn?.('chemclaw-bot: Bot %s not created: %s', def.name, error)
    }
  }

  // 4) Preset rooms
  for (const room of botsSeed.rooms ?? []) {
    const members = (room.members ?? []).map(name => byName.get(name)?.id).filter(Boolean)
    const adminId = byName.get(room.admin)?.id ?? main.id
    if (members.length < 2) {
      rt.warn?.('chemclaw-bot: room %s skipped (need ≥2 members)', room.name)
      continue
    }
    if (!members.includes(adminId)) members.unshift(adminId)
    try {
      await rt.createRoom({
        name: room.name,
        members,
        notice: room.notice,
        mode: 'admin',
        admin: adminId,
        createdBy: main.id,
      })
    } catch (error) {
      rt.warn?.('chemclaw-bot: room %s not created: %s', room.name, error)
    }
  }

  rt.scheduleCapabilitiesReconcile?.()
  return main
}
