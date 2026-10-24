import { createUserMessage } from '@deepseek-ai/dsh-llm'
import { renderSkillContent } from '@deepseek-ai/dsh-skill'

const topics = ['产业链', '利润', '成本', '行情', '供应商', '客户', '尽调', '基差', '月差', '回测', 'ppt', 'excel', '物性', '结构', '文献', '质量', 'coa', '区域', '海外', '采购', '销售', '装置', '供需', '产能']

export function selectTaskSkill(text, items) {
  const query = text.toLowerCase()
  if (/刚才|本轮|这次|上面/.test(query) && /用过|用到|用了|调用|加载/.test(query) && /skill|技能|mcp|api|搜索|工具/.test(query)) return undefined
  if (!/研究|分析|查询|核验|筛选|开发|找客户|找供应商|画|制作|生成|报告|全景|产业链|行情|基差|月差|回测/.test(query)) return undefined
  const ranked = items.map((item, index) => {
    const title = (item.description ?? '').toLowerCase()
    let score = topics.reduce((sum, word) => sum + (query.includes(word) && title.includes(word) ? word.length : 0), 0)
    if (/画|全景|图/.test(query) && /图/.test(title)) score += 2
    if (/产业链/.test(query) && !/利润|成本/.test(query) && /产业链图/.test(title)) score += 2
    return { item, score, index }
  }).filter(entry => entry.score > 0).sort((a, b) => b.score - a.score || a.index - b.index)
  return ranked[0]?.item.name
}

export function install(rt) {
  const loaded = new WeakMap()
  rt.ctx.on('agent/pre-step', async ({ agent, signal, turn }, next) => {
    const decision = await next()
    if (decision.kind === 'reject' || signal.aborted || !rt.isBotSession(agent.id)) return decision
    const skills = rt.ctx.get?.('skills')
    if (!skills) return decision
    const incoming = decision.messages.filter(message => message.role === 'user'
      && (message.source?.kind === 'user' || message.source?.role === 'room'))
    const owner = rt.groupOwners.get(agent.id)
    const task = owner && incoming.some(message => message.source?.role === 'room')
      ? [...(rt.roomOf(owner.roomId)?.log ?? [])].reverse().find(line => line.who === 'User')?.text
      : incoming.map(message => message.content.filter(block => block.type === 'text').map(block => block.text).join('\n')).join('\n')
    if (!task) return decision
    const bot = rt.botOf(rt.selfOf(agent.id))
    if (!bot) return decision
    const items = [...rt.expandCapabilities(bot.capabilities)].map(name => rt.state.capabilities.items[name])
      .filter(item => item?.kind === 'skill' && !['chemclaw-delivery', 'chemclaw-research-process'].includes(item.name))
    const name = selectTaskSkill(task, items)
    const previous = loaded.get(agent)
    if (!name || (previous && previous.turn === turn && previous.names.has(name))) return decision
    const skill = await skills.get(name, { scope: agent, cwd: await rt.ctx.get('workingDirectory').ensure(agent, signal), signal })
    if (!skill || !skill.invocation.modelInvocable) return decision
    const used = previous && previous.turn === turn ? previous.names : new Set()
    used.add(name); loaded.set(agent, { turn, names: used })
    return {
      ...decision,
      messages: [...decision.messages, createUserMessage({
        source: { kind: 'chemclaw-skill-routing', name, form: 'instructions' },
        content: [{ type: 'text', text: `ChemClaw automatically loaded the task-matched skill below through the skill registry. Follow these actual instructions; no additional skill call is needed for this same skill. Other skills and referenced resources remain available on demand.\n${renderSkillContent(skill)}` }],
      })],
    }
  })
}
