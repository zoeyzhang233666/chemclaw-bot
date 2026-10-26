import { createElement as h } from 'react'

/** APIHub brand mark: hollow cloud outline (chem-cloud Apihub). */
export function ApiHubMark() {
  return h('svg', {
    width: 24, height: 24, viewBox: '0 0 32 32', fill: 'none', 'aria-hidden': true,
    stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round',
  }, h('path', {
    d: 'M8.5 23.5h15.2c2.9 0 5.3-2.2 5.3-5.1 0-2.7-2-4.9-4.6-5.2-.6-3.8-3.9-6.7-7.9-6.7-3.2 0-6 1.9-7.3 4.6C6.6 11.4 4 14 4 17.2c0 3.5 2.7 6.3 4.5 6.3Z',
  }))
}

/** Generic cloud used for Chemical Data Hub and public research cards. */
export function CloudMark() {
  return h('svg', { width: 24, height: 24, viewBox: '0 0 32 32', fill: 'none', 'aria-hidden': true }, h('path', { d: 'M9 25a7 7 0 0 1-1-13.9A8.5 8.5 0 0 1 24 10a7.5 7.5 0 0 1-1 15H9Z', fill: 'currentColor', opacity: .16 }), h('path', { d: 'M9 25a7 7 0 0 1-1-13.9A8.5 8.5 0 0 1 24 10a7.5 7.5 0 0 1-1 15H9Z', stroke: 'currentColor', strokeWidth: 1.8 }), h('path', { d: 'M11 18h10M16 13v10', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' }))
}

export function ChemistryMark() {
  return h('svg', { width: 24, height: 24, viewBox: '0 0 32 32', fill: 'none', 'aria-hidden': true }, h('path', { d: 'm16 4 10.4 6v12L16 28 5.6 22V10L16 4Z', stroke: 'currentColor', strokeWidth: 1.8 }), h('path', { d: 'm8 12 8 4 8-4M16 16v9', stroke: 'currentColor', strokeWidth: 1.6 }), ...[[16, 4], [26.4, 22], [5.6, 22], [16, 16]].map(([cx, cy], i) => h('circle', { key: i, cx, cy, r: 2.8, fill: 'currentColor' })))
}
