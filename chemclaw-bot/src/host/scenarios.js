import { defineTool } from '@deepseek-ai/dsh-tools'
import { domainSkills, ensureSkillLibrary, roleCatalog, roleInstructions } from './catalog-seed.js'
import { ROOM_MAX_MEMBERS } from './constants.js'

const CHIEF_MEMBERSHIP_VERSION = 4

export function install(rt) {
  let queue = Promise.resolve()
  const bindings = () => (rt.state.templateBindings ??= {})
  const roomFor = def => rt.roomOf(bindings()[def.id]) ?? Object.values(rt.state.rooms).find(item => item.templateId === def.id || (!item.templateId && [def.name, ...(def.previousNames ?? [])].includes(item.name)))
  const noticeFor = (def, bots, adminId) => {
    const admin = adminId === undefined ? bots.find(bot => bot.templateId === def.admin) : bots.find(bot => bot.id === adminId)
    const chief = bots.find(bot => bot.templateId === 'chemclaw')
    return [
      def.description,
      `负责人：${admin?.name ?? '未设置'}`,
      chief ? `主控：${chief.name}，按需协调跨领域任务、处理结论分歧与验收；日常由本群负责人组织，不逐条监听或自动复核。需要时可 @${chief.name}。` : '',
      `分工：${bots.map(bot => `${bot.name}：${roleCatalog.roles.find(item => item.id === bot.templateId)?.description ?? bot.role}`).join('\n')}`,
      `交付：${def.deliverables}`,
      `示例：${def.examples[0]}`,
    ].filter(Boolean).join('\n')
  }
  const enqueue = work => {
    const result = queue.then(work)
    queue = result.catch(() => {})
    return result
  }
  async function describe(item, def, kind) {
    const previous = item.templateDefaults
    const patch = {}
    if (kind === 'role') {
      const instructions = roleInstructions(def)
      const oldSuffix = '业务主控可用 activate_scenario 启用场景与专家；不要手工重复创建内置角色。'
      const newSuffix = '专业 Bot 与协作群已预设，按团队名单协作，不要重复创建内置角色。'
      const oldInstructions = [def.name, ...(def.previousNames ?? [])].map(name => roleInstructions({ ...def, name }).replace(newSuffix, oldSuffix))
      if ((previous?.instructions === item.instructions || oldInstructions.includes(item.instructions)) && item.instructions !== instructions) patch.instructions = instructions
    }
    if ((previous ? item.name === previous.name : def.previousNames?.includes(item.name)) && item.name !== def.name) patch.name = def.name
    const stockShape = shape => !shape || ['lobster', 'whale'].includes(shape) || /^lobster-\d+$/.test(shape)
    const originalLook = previous
      ? JSON.stringify(item.avatar) === JSON.stringify(previous.avatar) && item.color === previous.color
      : !item.avatar?.image && stockShape(item.avatar?.shape) && !String(item.color).startsWith('#')
    // Variant lobster shapes from older catalogs also count as stock looks to remint.
    const remintLook = originalLook || (!item.avatar?.image && /^lobster-\d+$/.test(item.avatar?.shape ?? ''))
    if (kind === 'role' && remintLook) Object.assign(patch, { avatar: def.avatar, color: def.color })
    if (kind === 'role' && Object.keys(patch).length) await rt.updateBot(item.id, patch)
    if (kind === 'group') {
      if (patch.name) await rt.updateRoom(item.id, { name: patch.name })
      // Groups show a cluster of member marks; drop any leftover single-shape avatar.
      delete item.avatar
      if (remintLook && def.color) item.color = def.color
    }
    Object.assign(item, { templateId: def.id, templateVersion: roleCatalog.version, templateDefaults: { name: def.name, color: def.color, ...(kind === 'role' ? { avatar: def.avatar, instructions: roleInstructions(def) } : {}) }, templateInfo: { category: def.category, description: def.description, examples: def.examples, inputs: def.inputs, deliverables: def.deliverables, sources: def.sources, limits: def.limits } })
  }
  async function role(id) {
    const def = roleCatalog.roles.find(item => item.id === id)
    if (!def) throw new Error('Unknown role template')
    let bot = rt.botOf(bindings()[id]) ?? Object.values(rt.state.bots).find(item => item.templateId === id || (!item.templateId && [def.name, ...(def.previousNames ?? [])].includes(item.name)))
    if (def.main) bot ??= Object.values(rt.state.bots).find(item => rt.isMain(item.id))
    if (!bot) {
      bot = await rt.createBot({ name: def.name, role: def.category, color: def.color, avatar: def.avatar, instructions: roleInstructions(def), brief: def.description, pickModel: true, createdBy: rt.state.mainBotIds[0] })
      bot.capabilities = [...def.skills, 'chemclaw-delivery', 'chemclaw-research-process']
      bot.templateId = id
      bot.templateVersion = roleCatalog.version
      rt.dropKickoff(bot.id)
    }
    await describe(bot, def, 'role')
    bindings()[id] = bot.id
    await rt.save()
    rt.scheduleCapabilitiesReconcile?.()
    return bot
  }
  async function group(id) {
    const def = roleCatalog.groups.find(item => item.id === id)
    if (!def) throw new Error('Unknown scenario template')
    let room = roomFor(def)
    const bots = []
    for (const member of def.members) {
      const bot = rt.botOf(bindings()[member])
      if (!bot && room && bindings()[member]) continue
      bots.push(bot ?? await role(member))
    }
    const admin = bots.find(bot => bot.templateId === def.admin)
    if (room) {
      const previous = room.templateDefaults
      const previousMembers = previous?.members ?? def.previousMembers?.map(template => bindings()[template])
      const sameMembers = previousMembers && JSON.stringify([...room.members].sort()) === JSON.stringify([...previousMembers].sort())
      const patch = {}
      // This upgrade only appends the chief, even to customized teams. The room's
      // version also records a full room's skipped attempt so later removals stick.
      if ((room.templateVersion ?? 0) < CHIEF_MEMBERSHIP_VERSION) {
        const chief = bots.find(bot => bot.templateId === 'chemclaw')
        if (chief && !room.members.includes(chief.id)) {
          if (room.members.length < ROOM_MAX_MEMBERS) patch.add = [chief.id]
          else rt.warn('chemclaw-bot: cannot add %s to full preset group "%s" (%s); add it manually after making room', chief.name, room.name, room.id)
        }
      } else if (sameMembers && room.admin === admin?.id) patch.members = bots.map(bot => bot.id)
      const members = [...(patch.members ?? room.members), ...(patch.add ?? [])].map(rt.botOf).filter(Boolean)
      const managedNotice = room.notice === previous?.notice || def.previousNotices?.includes(room.notice)
      if (managedNotice) patch.notice = noticeFor(def, members, room.admin)
      if (Object.keys(patch).length) await rt.updateRoom(room.id, patch)
      await describe(room, def, 'group')
      Object.assign(room.templateDefaults, { members: bots.map(bot => bot.id), notice: managedNotice ? room.notice : noticeFor(def, bots) })
      bindings()[id] = room.id
      await rt.save()
      return room
    }
    room = await rt.createRoom({ name: def.name, members: bots.map(bot => bot.id), admin: admin.id, mode: 'admin', notice: noticeFor(def, bots), createdBy: rt.state.mainBotIds[0] })
    await describe(room, def, 'group')
    if (def.color) room.color = def.color
    Object.assign(room.templateDefaults, { members: bots.map(bot => bot.id), notice: noticeFor(def, bots) })
    bindings()[id] = room.id
    await rt.save()
    return room
  }
  rt.ensurePresetTeam = () => enqueue(async () => {
    if (rt.state.presetTeamVersion >= roleCatalog.version) return
    await ensureSkillLibrary(rt)
    // A recorded but deleted template is a user choice, not a missing first-run preset.
    for (const def of roleCatalog.roles) if (!bindings()[def.id] || rt.botOf(bindings()[def.id])) await role(def.id)
    for (const def of roleCatalog.groups) {
      if (bindings()[def.id] && !rt.roomOf(bindings()[def.id])) continue
      if (!roomFor(def) && def.members.some(id => bindings()[id] && !rt.botOf(bindings()[id]))) continue
      await group(def.id)
    }
    rt.state.presetTeamVersion = roleCatalog.version
    await rt.save()
  })
  rt.presetTeamCurrent = () => rt.state.presetTeamVersion >= roleCatalog.version
  rt.activateScenario = async ({ id, kind = 'role' }) => {
    if (!['role', 'group'].includes(kind)) throw new Error('Choose role or group')
    await rt.load()
    if (rt.readOnly()) throw new Error(rt.readOnly())
    await rt.bootstrap()
    return enqueue(() => kind === 'role' ? role(id) : group(id))
  }
  rt.scenarioCatalog = () => ({ ...roleCatalog, skills: domainSkills, bindings: rt.state.templateBindings ?? {} })
  const output = { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] }
  rt.ctx.tools.register(defineTool({ name: 'list_scenarios', description: 'List built-in ChemClaw expert roles and collaborative business scenarios.', parameters: {}, output, execute: async () => JSON.stringify(roleCatalog) }))
  rt.ctx.tools.register(defineTool({ name: 'activate_scenario', description: 'Activate a built-in ChemClaw role or scenario once. Main Bots only; returns its ID for messaging.', parameters: { id: { type: 'string', required: true }, kind: { type: 'string', required: true, enum: ['role', 'group'] } }, output, execute: async (args, exec) => {
    if (!rt.isMain(rt.selfOf(exec.agent?.id))) throw new Error('Only a Main Bot may activate team templates')
    const item = await rt.activateScenario(args)
    return JSON.stringify({ id: item.id, name: item.name })
  } }))
}
