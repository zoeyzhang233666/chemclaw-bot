// Synthetic fixtures for protocol/renderer validation, never business evidence.
export const GENUI_EXAMPLES = {
  timeline: { title: 'Synthetic project milestones', items: [{ type: 'timeline', items: [
    { title: 'Requirements', time: '2026-10-01', desc: 'Scope agreed' },
    { title: 'Pilot', time: '2026-10-15', desc: 'Pilot complete' },
    { title: 'Delivery', time: '2026-10-29', desc: 'Ready for review' },
  ] }] },
  form: { title: 'Synthetic local records', items: [
    { type: 'input', id: 'search', label: 'Filter records', placeholder: 'Search locally' },
    { type: 'table', columns: ['Company', 'Volume'], rows: [['Alpha', 30], ['Beta', 10], ['Gamma', 20]], filter: 'search', export: true },
    { type: 'input', id: 'note', label: 'Owner note' },
    { type: 'submit', action: 'review', label: 'Send review', groups: ['note'] },
  ] },
  flow: { title: 'Synthetic process', items: [{ type: 'mermaid', code: 'graph LR\nA[Requirements]-->B[Pilot]\nB-->C[Delivery]' }] },
  plot: { title: 'Synthetic function', items: [{ type: 'plot', title: 'Cost sensitivity', xMin: 0, xMax: 10, series: [{ expr: 'a*x', label: 'Cost', params: [{ name: 'a', value: 2, min: 1, max: 5 }] }] }] },
  panel: { title: 'Synthetic native panel', panel: true, items: [{ type: 'timeline', items: [{ title: 'Native panel ready', time: '2026-10-29' }] }] },
}
export const genuiExampleText = kind => `Synthetic renderer verification.\n\n\`\`\`dsh-ui\n${JSON.stringify(GENUI_EXAMPLES[kind])}\n\`\`\``
