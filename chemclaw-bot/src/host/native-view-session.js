export function isNativeViewSession(rt, agent) {
  const id = agent?.id
  return typeof id === 'string' && agent.session?.id === id
    && agent.session.header?.parentSession === undefined
    && !rt.isBotSession(id) && rt.roomOf(id) === undefined
}

export function nativeViewAvailable(ctx, agent, toolSet) {
  return typeof ctx.tools?.get !== 'function' || ctx.tools.get('show_view', agent, toolSet) !== undefined
}
