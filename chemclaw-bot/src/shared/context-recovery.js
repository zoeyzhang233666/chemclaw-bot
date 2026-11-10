export const CONTEXT_RECOVERY_LIMIT = 2
export const CONTEXT_RECOVERY_NOTICE = 'Automatic context recovery stopped after repeated failures. Your history is preserved. Change the model or send a message to retry.'

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value)
export const validContextRecovery = value => object(value)
  && Number.isInteger(value.attempts) && value.attempts >= 0 && value.attempts <= CONTEXT_RECOVERY_LIMIT + 1
  && typeof value.blocked === 'boolean' && value.blocked === (value.attempts > CONTEXT_RECOVERY_LIMIT)
  && (value.userMessageId === undefined || typeof value.userMessageId === 'string')

export function contextRecoveryNotice(bot, room) {
  return bot?.contextRecovery?.blocked || Object.values(room?.contextRecovery ?? {}).some(record => record.blocked)
    ? CONTEXT_RECOVERY_NOTICE : ''
}
