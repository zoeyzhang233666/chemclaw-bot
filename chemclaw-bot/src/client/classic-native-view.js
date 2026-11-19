import { createElement as h } from 'react'
import { DeliveredView } from './widget-cell.js'
import { classicNativeViewState } from './classic-view-protocol.js'

// Native DSH's tool-call tree stays in charge of ALL tool events, status and
// inspection. Only the show_view wire name gets the original ChemClaw renderer.
// All other tool names retain DSH's complete, expandable tool rows.
export function ClassicShowView({ phase, block, callId, inspect }) {
  const state = classicNativeViewState(phase, block)
  const details = h('details', { className: 'bt-classic-view-details' },
    h('summary', null, 'show_view · ', callId),
    h('pre', null, typeof block?.argsRaw === 'string' ? block.argsRaw : JSON.stringify(block?.args?.value?.('view') ?? {}, null, 2)),
    state.status !== 'ready' && state.reply ? h('p', null, state.reply) : null,
    inspect ? h('button', { type: 'button', onClick: inspect }, 'Inspect') : null)
  return h('div', { className: 'bt-classic-native-view', 'data-classic-native-view': state.status },
    state.status === 'ready'
      ? h('div', { className: 'bt-q-inline' }, h(DeliveredView, { title: state.title, view: state.view }))
      : h('div', { className: 'bt-classic-view-feedback', role: 'status' },
        state.status === 'pending' ? 'Preparing view…' : 'View was not displayed. The text answer is preserved.'),
    details)
}
