const integer = value => Number.isSafeInteger(value) && value >= 0

// GenUI owns recognition and rendering. This service owns only ChemClaw's
// durable message identities and the lifetime of their prompt routes.
export function createGenuiSurfaces(report = () => {}) {
  const surfaces = new Set()
  const adapters = new Map()
  let active = true
  const mount = (entry, adapter) => {
    let live = true
    const sendPrompt = async text => {
      if (!active || !live || !surfaces.has(entry) || !entry.root.isConnected
        || entry.root.getAttribute('data-genui-surface') !== entry.source) throw new Error('This GenUI message is no longer active.')
      try { await entry.sendPrompt(text) } catch (error) { report(error); throw error }
    }
    let release
    try { release = adapter.mount({ ...entry, sendPrompt }) } catch (error) { report(error) }
    entry.mounts.set(adapter, () => { live = false; release?.() })
  }
  const drop = entry => {
    surfaces.delete(entry)
    for (const release of entry.mounts.values()) release()
    entry.mounts.clear()
  }
  return {
    registerSidechatSurfaceAdapter(adapter) {
      if (!active || typeof adapter?.id !== 'string' || typeof adapter.mount !== 'function') return () => {}
      if (adapters.has(adapter.id)) throw new Error(`GenUI adapter already registered: ${adapter.id}`)
      const registration = { adapter }
      adapters.set(adapter.id, registration)
      for (const entry of surfaces) mount(entry, adapter)
      return () => {
        if (adapters.get(adapter.id) !== registration) return
        adapters.delete(adapter.id)
        for (const entry of surfaces) { entry.mounts.get(adapter)?.(); entry.mounts.delete(adapter) }
      }
    },
    add(surface) {
      if (!active || !integer(surface.eventSeq) || !integer(surface.contentBlockIndex)
        || typeof surface.threadId !== 'string' || !surface.threadId || !surface.root
        || surface.root.getAttribute('data-genui-surface') !== surface.source
        || typeof surface.text !== 'string' || typeof surface.sendPrompt !== 'function') return () => {}
      const entry = { ...surface, mounts: new Map() }
      surfaces.add(entry)
      for (const { adapter } of adapters.values()) mount(entry, adapter)
      return () => drop(entry)
    },
    dispose() {
      active = false
      for (const entry of surfaces) drop(entry)
      adapters.clear()
    },
  }
}

export function assistantTextBlocks(blocks = []) {
  return blocks.flatMap((block, contentBlockIndex) => block.kind === 'text' && block.text.trim()
    ? [{ text: block.text, contentBlockIndex }] : [])
}
