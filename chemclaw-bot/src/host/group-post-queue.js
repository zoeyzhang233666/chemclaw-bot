// Serialize a member's in-round step messages until durable room persistence
// has completed. A failed post poisons the lane: later queued messages must not
// be exposed as successful replies or silently skip the failed sequence.
export function createOrderedGroupPostQueue(post) {
  if (typeof post !== 'function') throw new TypeError('A group post callback is required')
  let tail = Promise.resolve()
  let closed = false

  function enqueue(value) {
    if (closed) {
      const rejected = Promise.reject(new Error('The group reply lane is closed'))
      void rejected.catch(() => {})
      return rejected
    }
    // A rejection remains on tail, so the next callback is never invoked after
    // a failed commit. Even callers that do not await say() must not create an
    // unhandled rejection: close() / drain() still observe the original failure.
    tail = tail.then(() => post(value))
    void tail.catch(() => {})
    return tail
  }

  const drain = () => tail
  const close = () => {
    closed = true
    return tail
  }
  return { enqueue, drain, close }
}

/**
 * Legacy bridge for round replies. Do not publish success into the transient
 * round result (or clear the visible draft) before the required state save.
 * This is NOT a Ledger writer: the complete P0 cutover must replace append.
 */
export async function publishSavedGroupReply({ room, round, member, visible, duration, append, save, commitDraft }) {
  if (!visible) return false
  if (typeof append !== 'function' || typeof save !== 'function') {
    throw new TypeError('Group reply requires append and required save callbacks')
  }
  await append(room, { who: member.name, botId: member.id, text: visible })
  await save({ required: true })
  commitDraft?.()
  round.replies.push({
    botId: member.id, name: member.name, color: member.color,
    text: visible, time: Date.now(),
    ...(duration === undefined ? {} : { duration }),
  })
  return true
}
