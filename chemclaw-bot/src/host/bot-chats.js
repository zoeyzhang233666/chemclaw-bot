// Private multi-chat: each Bot owns chats[]; Session ownership is keyed by sessionId.
// activeChatId is UI focus only — execution and part rotation use ownerOf(sessionId).
import { copyFile, readdir } from 'node:fs/promises'
import { join } from 'node:path'
import { randomBytes } from 'node:crypto'

const TITLE_MAX = 80
const FILLER = /^(?:please|pls|ok|okay|hello|hi|hey|嗯+|啊+|呃+|请?(?:帮我|帮忙)|麻烦|请问|你好)[,，\s]*/iu

function newChatId() {
  return `chat_${randomBytes(6).toString('hex')}`
}

function defaultTitle(bot) {
  return typeof bot?.name === 'string' && bot.name.trim() ? bot.name.trim().slice(0, TITLE_MAX) : 'Chat'
}

export function heuristicTitle(text) {
  const raw = String(text ?? '').replace(/\s+/g, ' ').trim()
  if (!raw) return undefined
  let line = raw.split(/[\n。！？!?]/u)[0]?.trim() ?? raw
  for (;;) {
    const next = line.replace(FILLER, '').trim()
    if (next === line) break
    line = next
  }
  if (!line) line = raw.slice(0, TITLE_MAX)
  if (line.length > TITLE_MAX) {
    const cut = line.slice(0, TITLE_MAX)
    const at = Math.max(cut.lastIndexOf(' '), cut.lastIndexOf('，'), cut.lastIndexOf(','))
    line = (at > 24 ? cut.slice(0, at) : cut).trim()
  }
  return line || undefined
}

export function seedChatFromBot(bot) {
  const now = Date.now()
  return {
    id: bot.id,
    title: defaultTitle(bot),
    titleSource: 'default',
    createdAt: bot.createdAt ?? now,
    updatedAt: now,
    sessionId: bot.sessionId ?? bot.id,
    segments: Array.isArray(bot.segments) ? bot.segments.map(segment => ({ ...segment })) : [],
  }
}

export function ensureBotChats(bot) {
  if (Array.isArray(bot.chats) && bot.chats.length > 0) {
    if (bot.activeChatId === undefined || !bot.chats.some(chat => chat.id === bot.activeChatId)) {
      bot.activeChatId = bot.chats.find(chat => chat.archived !== true)?.id ?? bot.chats[0].id
      return true
    }
    return false
  }
  bot.chats = [seedChatFromBot(bot)]
  bot.activeChatId = bot.chats[0].id
  return true
}

export function activeChat(bot) {
  if (!Array.isArray(bot?.chats) || bot.chats.length === 0) return undefined
  return bot.chats.find(chat => chat.id === bot.activeChatId) ?? bot.chats.find(chat => chat.archived !== true) ?? bot.chats[0]
}

export function chatById(bot, chatId) {
  if (!Array.isArray(bot?.chats)) return undefined
  return bot.chats.find(chat => chat.id === chatId)
}

export function chatBySession(bot, sessionId) {
  if (!Array.isArray(bot?.chats)) return undefined
  for (const chat of bot.chats) {
    if (chat.sessionId === sessionId) return chat
    if ((chat.segments ?? []).some(segment => segment.sessionId === sessionId)) return chat
  }
  return undefined
}

export function syncMirror(bot) {
  const chat = activeChat(bot)
  if (chat === undefined) return
  if (chat.sessionId !== undefined) bot.sessionId = chat.sessionId
  else delete bot.sessionId
  bot.segments = Array.isArray(chat.segments) ? chat.segments.map(segment => ({ ...segment })) : []
}

export function install(rt) {
  const { ctx, state, home, statePath } = rt

  async function backupBeforeMultichat() {
    if (!home || !statePath) throw new Error('Cannot back up Bot team state: home path missing')
    let names = []
    try {
      names = await readdir(home)
    } catch (error) {
      if (error?.code === 'ENOENT') return
      throw error
    }
    if (names.some(name => name.startsWith('state.json.pre-multichat-'))) return
    const backup = join(home, `state.json.pre-multichat-${Date.now()}`)
    try {
      await copyFile(statePath, backup)
    } catch (error) {
      // No prior file: nothing destructive to preserve.
      if (error?.code === 'ENOENT') return
      throw Object.assign(
        new Error(`Could not back up state before multi-chat migration: ${error.message ?? error}`),
        { cause: error, code: error.code },
      )
    }
  }

  function needsChatMigration() {
    return Object.values(state.bots).some(bot => !Array.isArray(bot.chats) || bot.chats.length === 0)
  }

  function migrateChats() {
    let migrated = false
    for (const bot of Object.values(state.bots)) {
      if (ensureBotChats(bot)) migrated = true
      syncMirror(bot)
    }
    return { migrated }
  }

  // sessionId → { kind:'private', botId, chatId } | { kind:'room', roomId, botId }
  // past private segments also carry chatId so rotation never consults activeChatId.
  const sessionOwners = new Map()

  function rebuildSessionOwners() {
    sessionOwners.clear()
    for (const bot of Object.values(state.bots)) {
      if (!Array.isArray(bot.chats) || bot.chats.length === 0) {
        // Pre-migration: index the legacy tip without mutating disk-facing chats[].
        for (const segment of bot.segments ?? []) {
          sessionOwners.set(segment.sessionId, { kind: 'private', botId: bot.id, chatId: bot.id, past: true })
        }
        sessionOwners.set(bot.sessionId ?? bot.id, { kind: 'private', botId: bot.id, chatId: bot.id })
        continue
      }
      for (const chat of bot.chats) {
        for (const segment of chat.segments ?? []) {
          sessionOwners.set(segment.sessionId, { kind: 'private', botId: bot.id, chatId: chat.id, past: true })
        }
        if (chat.sessionId !== undefined) {
          sessionOwners.set(chat.sessionId, { kind: 'private', botId: bot.id, chatId: chat.id })
        }
      }
    }
    for (const room of Object.values(state.rooms)) {
      for (const [botId, segments] of Object.entries(room.segments ?? {})) {
        for (const segment of segments) {
          sessionOwners.set(segment.sessionId, { kind: 'room', roomId: room.id, botId, past: true })
        }
      }
      for (const [botId, sessionId] of Object.entries(room.sessions ?? {})) {
        sessionOwners.set(sessionId, { kind: 'room', roomId: room.id, botId })
      }
    }
  }

  function ownerOf(sessionId) {
    if (sessionId === undefined || sessionId === null) return undefined
    return sessionOwners.get(sessionId)
  }

  function tipOfChat(bot, chatId) {
    const chat = chatById(bot, chatId)
    return chat?.sessionId ?? (chat?.id === bot.id ? bot.id : undefined)
  }

  // UI / default private tip only — never use for group routing or background completion.
  // Soft ensure: never seed chats[] while a failed pre-multichat backup blocks writes.
  function ensureChats(bot) {
    if (rt.blockMultichatWrites) return false
    return ensureBotChats(bot)
  }

  function chatOf(botId) {
    const bot = rt.botOf(botId)
    if (bot === undefined) return botId
    ensureChats(bot)
    const chat = activeChat(bot)
    return chat?.sessionId ?? bot.sessionId ?? botId
  }

  async function createBotChat(botId, { title } = {}) {
    const bot = rt.botOf(botId)
    if (bot === undefined) throw new Error('Unknown Bot')
    assertMultichatWritable()
    ensureChats(bot)
    const id = await rt.createSession(title?.trim() || `${bot.name} chat`)
    const now = Date.now()
    const chat = {
      id: newChatId(),
      title: (typeof title === 'string' && title.trim() ? title.trim().slice(0, TITLE_MAX) : 'New chat'),
      titleSource: typeof title === 'string' && title.trim() ? 'user' : 'default',
      createdAt: now,
      updatedAt: now,
      sessionId: id,
      segments: [],
    }
    bot.chats.push(chat)
    bot.activeChatId = chat.id
    syncMirror(bot)
    rt.indexSessions?.()
    await rt.save()
    rt.capabilitiesStateSaved?.()
    return { botId: bot.id, activeChatId: bot.activeChatId, chat: publicChat(bot, chat) }
  }

  async function openBotChat(botId, chatId) {
    const bot = rt.botOf(botId)
    if (bot === undefined) throw new Error('Unknown Bot')
    assertMultichatWritable()
    ensureChats(bot)
    const chat = chatById(bot, chatId)
    if (chat === undefined) throw new Error('Unknown chat')
    if (chat.archived === true) delete chat.archived
    bot.activeChatId = chat.id
    chat.updatedAt = Date.now()
    syncMirror(bot)
    await rt.save()
    return { botId: bot.id, activeChatId: bot.activeChatId, chat: publicChat(bot, chat) }
  }

  async function renameBotChat(botId, chatId, title) {
    const bot = rt.botOf(botId)
    if (bot === undefined) throw new Error('Unknown Bot')
    assertMultichatWritable()
    const chat = chatById(bot, chatId)
    if (chat === undefined) throw new Error('Unknown chat')
    const next = String(title ?? '').trim().slice(0, TITLE_MAX)
    if (!next) throw new Error('Title required')
    chat.title = next
    chat.titleSource = 'user'
    chat.updatedAt = Date.now()
    await rt.save()
    return { botId: bot.id, chat: publicChat(bot, chat) }
  }

  function chatSessionIds(chat) {
    return [chat.sessionId, ...(chat.segments ?? []).map(segment => segment.sessionId)].filter(Boolean)
  }

  function teamBlocksArchive(sessionId) {
    const works = Object.values(state.works ?? {})
    for (const work of works) {
      if (work?.captainSessionId === sessionId || work?.sessionId === sessionId) {
        if (work?.status === 'running' || work?.status === 'waiting' || work?.active === true) {
          return 'This chat still captains an agent team that cannot be safely ended yet'
        }
      }
    }
    return undefined
  }

  function chatBusyReason(chat) {
    for (const sessionId of chatSessionIds(chat)) {
      const team = teamBlocksArchive(sessionId)
      if (team) return team
      if (rt.live?.get(sessionId)?.turn !== undefined) return 'This chat is still running'
      if (rt.turnsView?.()?.[sessionId] !== undefined) return 'This chat is still running'
      const approvals = rt.approvalsView?.() ?? []
      const list = Array.isArray(approvals) ? approvals : Object.values(approvals)
      if (list.some(entry => entry?.sessionId === sessionId)) {
        return 'This chat has a pending approval'
      }
      if (state.questions?.[sessionId] !== undefined) return 'This chat is waiting for input'
      if (state.views?.[sessionId] !== undefined) return 'This chat is waiting for input'
      const waiting = rt.waitingView?.()
      if (waiting?.[sessionId] !== undefined) return 'This chat is waiting for input'
    }
    return undefined
  }

  async function archiveBotChat(botId, chatId) {
    const bot = rt.botOf(botId)
    if (bot === undefined) throw new Error('Unknown Bot')
    assertMultichatWritable()
    ensureChats(bot)
    const chat = chatById(bot, chatId)
    if (chat === undefined) throw new Error('Unknown chat')
    const open = bot.chats.filter(entry => entry.archived !== true)
    if (open.length <= 1 && chat.archived !== true) {
      throw new Error('A Bot needs at least one open chat')
    }
    const blocked = chatBusyReason(chat)
    if (blocked) throw new Error(blocked)
    chat.archived = true
    chat.updatedAt = Date.now()
    if (bot.activeChatId === chat.id) {
      bot.activeChatId = bot.chats.find(entry => entry.archived !== true)?.id ?? bot.chats[0].id
      syncMirror(bot)
    }
    rt.indexSessions?.()
    await rt.save()
    return { botId: bot.id, activeChatId: bot.activeChatId, chat: publicChat(bot, chat) }
  }

  async function deleteBotChat(botId, chatId) {
    const bot = rt.botOf(botId)
    if (bot === undefined) throw new Error('Unknown Bot')
    assertMultichatWritable()
    ensureChats(bot)
    const chat = chatById(bot, chatId)
    if (chat === undefined) throw new Error('Unknown chat')
    if (chat.id === bot.id) throw new Error('The original chat cannot be deleted')
    const blocked = chatBusyReason(chat)
    if (blocked) throw new Error(blocked)
    const tip = chat.sessionId
    const segments = [...(chat.segments ?? [])]
    bot.chats = bot.chats.filter(entry => entry.id !== chatId)
    if (bot.activeChatId === chatId) {
      bot.activeChatId = bot.chats.find(entry => entry.archived !== true)?.id ?? bot.chats[0].id
      syncMirror(bot)
    }
    rt.indexSessions?.()
    await rt.save()
    if (tip) {
      void ctx.workspaceRegistry.archiveSession(tip, { stopActivity: true }).catch(() => {})
      for (const segment of segments) {
        void ctx.workspaceRegistry.archiveSession(segment.sessionId, { stopActivity: true }).catch(() => {})
      }
    }
    return { botId: bot.id, activeChatId: bot.activeChatId }
  }

  // Anchor for read_own_chat / briefs: private callers stay on their Chat; group
  // callers use the original migrated Chat (id === bot.id), never activeChatId.
  function ownChatAnchor(botId, askingId) {
    const bot = rt.botOf(botId)
    if (bot === undefined) return undefined
    ensureChats(bot)
    if (askingId !== undefined) {
      const owned = ownerOf(askingId)
      if (owned?.kind === 'private' && owned.botId === botId) return askingId
      if (owned?.kind === 'room' && owned.botId === botId) {
        const seed = chatById(bot, bot.id) ?? bot.chats[0]
        return seed?.sessionId ?? bot.id
      }
    }
    return chatOf(botId)
  }

  function chatStatus(sessionId) {
    const work = rt.workView?.()?.[sessionId] ?? rt.workView?.()
    const turns = rt.turnsView?.()?.[sessionId]
    const waiting = rt.waitingView?.()?.[sessionId]
    const approvals = Object.values(rt.approvalsView?.() ?? {}).some(entry => entry?.sessionId === sessionId)
    return {
      running: Boolean(turns) || Boolean(work?.tool) || Boolean(work?.running),
      needsInput: Boolean(waiting) || approvals,
      unread: false,
    }
  }

  function publicChat(bot, chat) {
    const tip = chat.sessionId ?? (chat.id === bot.id ? bot.id : undefined)
    const status = tip ? chatStatus(tip) : { running: false, needsInput: false, unread: false }
    return {
      id: chat.id,
      title: chat.title,
      titleSource: chat.titleSource ?? 'default',
      createdAt: chat.createdAt,
      updatedAt: chat.updatedAt,
      archived: chat.archived === true,
      sessionId: tip,
      parts: (chat.segments ?? []).map(segment => segment.sessionId),
      ...status,
    }
  }

  function listBotChats(botId) {
    const bot = rt.botOf(botId)
    if (bot === undefined) throw new Error('Unknown Bot')
    assertMultichatWritable()
    ensureChats(bot)
    return {
      botId: bot.id,
      activeChatId: bot.activeChatId,
      chats: bot.chats.map(chat => publicChat(bot, chat)),
    }
  }

  function ownersView(botId) {
    const bot = rt.botOf(botId)
    if (bot === undefined) throw new Error('Unknown Bot')
    ensureChats(bot)
    return {
      botId: bot.id,
      activeChatId: bot.activeChatId,
      chats: (bot.chats ?? []).map(chat => ({
        id: chat.id,
        sessionId: chat.sessionId ?? (chat.id === bot.id ? bot.id : undefined),
        archived: chat.archived === true,
        owner: ownerOf(chat.sessionId ?? (chat.id === bot.id ? bot.id : undefined)),
      })),
    }
  }

  function applyAutoTitle(botId, sessionId, userText) {
    const bot = rt.botOf(botId)
    if (bot === undefined) return
    const chat = chatBySession(bot, sessionId)
    if (chat === undefined || chat.titleSource === 'user') return
    if (chat.titleSource === 'auto' && chat.title && chat.title !== 'New chat' && chat.title !== defaultTitle(bot)) return
    const title = heuristicTitle(userText)
    if (!title) return
    chat.title = title
    chat.titleSource = 'auto'
    chat.updatedAt = Date.now()
  }

  // Hook called from store.load after adopt, before the migrated state is saved.
  // When needsBackup is set, disk still holds the pre-migration file; backup must
  // succeed before chats[] is written into memory for save.
  async function afterAdoptMigrate({ needsBackup = false } = {}) {
    if (needsBackup) {
      try {
        await rt.backupBeforeMultichat()
      } catch (error) {
        rt.blockMultichatWrites = true
        throw error
      }
    }
    const result = migrateChats()
    rt.blockMultichatWrites = false
    rebuildSessionOwners()
    return result
  }

  function assertMultichatWritable() {
    if (rt.blockMultichatWrites || needsChatMigration()) {
      throw new Error('Multi-chat migration is blocked until state.json can be backed up')
    }
  }

  Object.assign(rt, {
    sessionOwners,
    ownerOf,
    rebuildSessionOwners,
    needsChatMigration,
    migrateChats,
    backupBeforeMultichat,
    afterAdoptMigrate,
    ensureBotChats: ensureChats,
    chatBusyReason,
    activeChat,
    chatById,
    chatBySession,
    syncMirror,
    tipOfChat,
    createBotChat,
    openBotChat,
    renameBotChat,
    archiveBotChat,
    deleteBotChat,
    listBotChats,
    ownersView,
    publicChat,
    applyAutoTitle,
    heuristicTitle,
    ownChatAnchor,
  })
  // Replace the single-tip chatOf from store with the active-chat tip resolver.
  rt.chatOf = chatOf

  // First private-user turn: derive a short title for that Chat only (never activeChatId).
  ctx.on?.('agent/pre-step', async ({ agent }, next) => {
    try {
      const owned = ownerOf(agent?.id)
      if (owned?.kind === 'private') {
        const bot = rt.botOf(owned.botId)
        const chat = chatById(bot, owned.chatId)
        if (chat && chat.titleSource !== 'user' && (chat.titleSource !== 'auto' || chat.title === 'New chat' || chat.title === defaultTitle(bot))) {
          const messages = agent?.session?.deriveMessages?.() ?? []
          const last = [...messages].reverse().find(message => message.role === 'user')
          const text = typeof last?.content === 'string'
            ? last.content
            : Array.isArray(last?.content)
              ? last.content.map(block => block?.text ?? '').join(' ')
              : ''
          if (text.trim()) {
            const before = chat.title
            applyAutoTitle(owned.botId, agent.id, text)
            if (chat.title !== before) void rt.save?.().catch(() => {})
          }
        }
      }
    } catch {
      // Title is best-effort; never block the turn.
    }
    return next()
  })
}
