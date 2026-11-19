import { createElement as h } from 'react'
import { DeliveredView } from './widget-cell.js'
import { classicNativeViewState } from './classic-view-protocol.js'

// DSH keeps tool-call metadata and the full execution trace in its own
// trajectory view. The user-facing answer should show only the native card,
// never a call ID, raw JSON arguments or a developer Inspect button.
// This keyed slot applies to show_view alone; all other tools retain their
// original DSH tool rows, including input/output inspection and disclosure.
export function ClassicShowView({ phase, block }) {
  const state = classicNativeViewState(phase, block)
  // Avoid flashing an empty technical row while the call is preparing.
  if (state.status === 'pending') return null
  if (state.status === 'ready') {
    return h('div', { className: 'bt-classic-native-view', 'data-classic-native-view': 'ready' },
      h('div', { className: 'bt-q-inline' },
        h(DeliveredView, { title: state.title, view: state.view })))
  }
  // A rejected or invalid card must never replace the ordinary text reply.
  return h('div', {
    className: 'bt-classic-native-view bt-classic-view-feedback',
    'data-classic-native-view': state.status,
    role: 'status',
  }, '交互式内容暂时无法展示，文字回答仍然保留。')
}
