// A CDP relay can deliver frame events before/after Page.getFrameTree and across
// Chromium target sessions. Playwright's FrameManager asserts when a child frame is
// attached twice without a detach; do not forward an inconsistent stream to it.
// Diagnostic entries intentionally contain no URLs, browser cookies or frame IDs.
export class CdpFrameGuard {
  #frames = new Map()
  #swapped = new Set()
  #recent = []
  #report

  constructor(report = () => {}) { this.#report = report }

  #record(method, outcome) {
    this.#recent.push({ method, outcome })
    if (this.#recent.length > 12) this.#recent.shift()
  }

  #drop(method, reason) {
    this.#record(method, reason)
    try { this.#report({ method, reason, recent: this.#recent.slice() }) } catch {}
    return false
  }

  // Record the frames Playwright learns while initializing a target. A subsequent
  // Page.frameAttached for the same child must not register it again.
  observeTree(tree) {
    if (!tree) return true
    const frames = new Map()
    const walk = (node, parentId, depth) => {
      const id = node?.frame?.id
      if (typeof id !== 'string' || id.length === 0 || frames.has(id) || depth > 64) return false
      frames.set(id, parentId)
      if (!Array.isArray(node.childFrames)) return true
      return node.childFrames.every(child => walk(child, id, depth + 1))
    }
    if (!walk(tree, null, 0)) return this.#drop('Page.getFrameTree', 'invalid-frame-tree')
    for (const [id, parent] of frames) {
      // An OOPIF subtarget sees itself as a root. Preserve its parent as
      // learned from the original page so a second frame tree cannot erase it.
      const existing = this.#frames.get(id)
      this.#frames.set(id, parent === null && existing !== undefined ? existing : parent)
    }
    this.#record('Page.getFrameTree', 'accepted')
    return true
  }

  accept(method, params = {}) {
    if (method === 'Page.frameAttached') {
      const { frameId, parentFrameId } = params
      if (typeof frameId !== 'string' || !frameId) return this.#drop(method, 'missing-frame-id')
      // A main-frame attach is handled by Playwright as a root-frame transition.
      if (!parentFrameId) {
        this.#frames.set(frameId, null)
        this.#record(method, 'root')
        return true
      }
      if (!this.#frames.has(parentFrameId)) return this.#drop(method, 'unknown-parent')
      if (this.#frames.has(frameId)) {
        // Playwright needs the first remote -> local reattach following an OOPIF
        // swap so it can retire the old frame session. Ordinary duplicates stay blocked.
        if (this.#swapped.delete(frameId) && this.#frames.get(frameId) === parentFrameId) {
          this.#record(method, 'swapped-in')
          return true
        }
        return this.#drop(method, this.#frames.get(frameId) === parentFrameId ? 'duplicate-attach' : 'conflicting-parent')
      }
      this.#frames.set(frameId, parentFrameId)
      this.#record(method, 'accepted')
      return true
    }
    if (method === 'Page.frameNavigated') {
      const { id, parentId } = params.frame ?? {}
      if (typeof id !== 'string' || !id) return this.#drop(method, 'missing-frame-id')
      if (parentId && !this.#frames.has(parentId)) return this.#drop(method, 'unknown-parent')
      // Navigation can establish an existing frame before its attach event arrives.
      this.#frames.set(id, parentId ?? this.#frames.get(id) ?? null)
      this.#record(method, 'accepted')
      return true
    }
    if (method === 'Page.frameDetached') {
      const { frameId, reason } = params
      if (typeof frameId !== 'string' || !frameId) return this.#drop(method, 'missing-frame-id')
      // An OOPIF swap keeps the frame itself but discards its child subtree.
      const removed = new Set([frameId])
      let changed
      do {
        changed = false
        for (const [id, parent] of this.#frames) {
          if (removed.has(parent) && !removed.has(id)) { removed.add(id); changed = true }
        }
      } while (changed)
      for (const id of removed) {
        this.#swapped.delete(id)
        if (reason !== 'swap' || id !== frameId) this.#frames.delete(id)
      }
      if (reason === 'swap') this.#swapped.add(frameId)
      this.#record(method, reason === 'swap' ? 'swap' : 'accepted')
      return true
    }
    return true
  }
}
