import { genuiFences } from '../shared/genui-fences.js'
import { t } from './i18n.js'
import { installStyles } from './styles.js'

const CODE = '[data-code-block-content]'
const ASSISTANT = '[data-chat-flow-kind="assistant-step"][data-chat-node-key]'
const SURFACE = '[data-genui-surface^="chemclaw-bot/"]'
const OWNED = ':is([data-genui-artifact], [data-genui-panel], .genui-dom-fence, [data-genui-explicit-fence])'
const CSS = `
.bt-genui-source{border:0!important;background:transparent!important;box-shadow:none!important}
.bt-genui-source>:not(.bt-genui-status),.genui-dom-fence-diagnostic:has(+ .bt-genui-source),[data-genui-svg] [role=status]+pre{display:none!important}
.bt-genui-status{color:var(--bt-ink-2);font-size:13px;padding:8px 0}
.bt-genui-status[data-unavailable]{animation:bt-genui-status-show .16s step-end}
@keyframes bt-genui-status-show{from{opacity:0}to{opacity:1}}
`

const sources = new WeakMap()
const candidates = new WeakMap()

export function setGenuiMarkdownSource(root, text, live) {
  if (root) sources.set(root, { text, live })
}

function fencesOf(value, text) {
  const previous = candidates.get(value)
  if (previous?.text === text) return previous.fences
  const fences = [...genuiFences(text)]
  candidates.set(value, { text, fences })
  return fences
}

export function installGenuiPresentation(ctx) {
  const styles = installStyles(CSS, 'genui-presentation')
  const marked = new Map()
  const collect = new Set()

  const clear = block => {
    marked.get(block)?.remove()
    marked.delete(block)
    block.classList.remove('bt-genui-source')
  }
  const viewSnapshot = () => {
    const sessionId = ctx.sessions.list.getSnapshot().ids.find(id => (ctx.sessions.retainInfo(id).getSnapshot().retainedBy.mainView ?? 0) > 0)
    return sessionId === undefined ? undefined : ctx.uiConversation.binding(sessionId).target('chat').getSnapshot()
  }
  const update = (content, readChat) => {
    const block = content.parentElement
    if (!block?.isConnected || block.closest(OWNED)) return
    const body = content.querySelector('pre')?.textContent.trimEnd()
    const surface = block.closest(SURFACE)
    const local = surface && sources.get(surface)
    const row = !surface && block.closest(ASSISTANT)
    if (!body || !local && (!row || row.dataset.chatGroupPart === 'reasoning' || block.closest('[data-tool]'))) {
      if (marked.has(block)) clear(block)
      return
    }
    const node = row && readChat()?.nodes.get(row.dataset.chatNodeKey)
    const protocol = local ? fencesOf(surface, local.text).some(fence => fence.body === body)
      : node?.data?.blocks?.some(item => item.kind === 'text' && fencesOf(item, item.text).some(fence => fence.body === body))
    if (!protocol) {
      if (marked.has(block)) clear(block)
      return
    }
    let status = marked.get(block)
    if (!status) {
      status = document.createElement('div')
      status.className = 'bt-genui-status'
      status.setAttribute('role', 'status')
      marked.set(block, status)
      block.classList.add('bt-genui-source')
    }
    if (status.parentElement !== block) block.append(status)
    const live = local ? local.live : node.data.status === 'running'
    status.toggleAttribute('data-unavailable', !live)
    const label = t(live ? 'Preparing the visual…' : 'The visual could not be displayed.')
    if (status.textContent !== label) status.textContent = label
  }
  const find = node => {
    const element = node instanceof Element ? node : node.parentElement
    if (!element || element.closest('.bt-genui-status')) return
    const parent = element.closest(CODE)
    if (parent) collect.add(parent)
    else element.querySelectorAll(CODE).forEach(content => collect.add(content))
  }
  const flush = () => {
    let chat
    let read = false
    const readChat = () => {
      if (!read) {
        read = true
        try { chat = viewSnapshot() } catch { /* The selected session may be changing. */ }
      }
      return chat
    }
    for (const content of collect) update(content, readChat)
    collect.clear()
  }
  const observer = new MutationObserver(records => {
    let removed = false
    for (const record of records) {
      if (record.type === 'characterData' || record.type === 'attributes' || record.target.closest?.(CODE)) find(record.target)
      else for (const node of record.addedNodes) find(node)
      removed ||= record.removedNodes.length > 0
    }
    if (removed) for (const block of marked.keys()) if (!block.isConnected) clear(block)
    flush()
  })
  find(document.body)
  flush()
  observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['data-streaming', 'data-bt-genui-live'] })
  return () => {
    observer.disconnect()
    for (const block of marked.keys()) clear(block)
    styles.remove()
  }
}
