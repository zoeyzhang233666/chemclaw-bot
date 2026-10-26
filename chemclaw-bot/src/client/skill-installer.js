import { createElement as h, useEffect, useRef, useState } from 'react'
import { hostText, t } from './i18n.js'
import { SKILL_CATEGORIES } from '../shared/skills.js'

const encode = file => new Promise((resolve, reject) => {
  const reader = new FileReader()
  reader.onload = () => resolve(String(reader.result).split(',')[1])
  reader.onerror = () => reject(new Error(t('Could not read this file.')))
  reader.readAsDataURL(file)
})

export function SkillInstaller({ actions, onClose, onInstalled, initialCategory = '' }) {
  const [mode, setMode] = useState('upload')
  const [url, setUrl] = useState('')
  const [preview, setPreview] = useState(null)
  const [choices, setChoices] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [installCategory, setInstallCategory] = useState(SKILL_CATEGORIES.includes(initialCategory) ? initialCategory : '')
  const [dragging, setDragging] = useState(false)
  const [writing, setWriting] = useState({ name: '', displayName: '', purpose: '', category: '我的安装', content: '' })
  const token = useRef(null)
  const mounted = useRef(true)
  const files = useRef(null)
  const folder = useRef(null)
  const panel = useRef(null)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; if (token.current) void actions.cancelSkillImport(token.current).catch(() => {}) } }, [])
  useEffect(() => { if (preview) panel.current?.closest('.bt-settings-scroll')?.scrollTo({ top: 0, behavior: 'instant' }) }, [preview?.token])
  const run = async work => {
    if (busy) return
    setBusy(true); setError('')
    try { await work() } catch (failure) { if (mounted.current) setError(failure.message) }
    finally { if (mounted.current) setBusy(false) }
  }
  const identify = async payload => {
    const value = await actions.previewSkillImport(payload)
    token.current = value.token
    if (!mounted.current) { void actions.cancelSkillImport(value.token); return }
    setPreview(value)
    setChoices(Object.fromEntries(value.candidates.map(item => [item.key, { selected: item.valid && !item.exists, name: item.name, displayName: item.labels?.zh ?? '', purpose: item.purpose || item.description || '', category: installCategory || item.category || '未分类', conflict: 'skip' }])))
  }
  const upload = list => run(async () => {
    const chosen = [...list]
    if (!chosen.length) return
    if (chosen.reduce((sum, file) => sum + file.size, 0) > 100 * 1024 * 1024) throw new Error(t('Choose skill files smaller than 100 MB in total.'))
    if (chosen.length === 1 && /\.zip$/i.test(chosen[0].name)) await identify({ archive: await encode(chosen[0]) })
    else await identify({ files: await Promise.all(chosen.map(async file => ({ path: file.webkitRelativePath || file.name, data: await encode(file) }))) })
  })
  const setChoice = (key, patch) => setChoices(old => ({ ...old, [key]: { ...old[key], ...patch } }))
  const install = () => run(async () => {
    const selections = Object.entries(choices).filter(([, value]) => value.selected).map(([key, value]) => ({ key, ...value }))
    const result = await actions.commitSkillImport(preview.token, selections)
    token.current = null
    onInstalled(result.installed)
  })
  const write = () => run(async () => {
    await actions.saveCapability({ ...writing, kind: 'skill', description: writing.purpose })
    onInstalled([writing.name])
  })
  const back = () => run(async () => {
    await actions.cancelSkillImport(preview.token)
    token.current = null; setPreview(null)
  })
  return h('section', { ref: panel, className: 'bt-skill-wizard bt-set-card', 'aria-label': t('Install a skill'), 'aria-busy': busy },
    h('header', { className: 'bt-skill-section-head' }, h('div', null, h('h3', null, t('Install a skill')), h('p', { className: 'bt-set-hint' }, t(preview ? 'Review the detected skills, then install the ones you need.' : 'Install the whole skill, including its scripts, templates, and reference files.'))),
      h('button', { className: 'bt-soft bt-soft-sm', disabled: busy, onClick: onClose }, t('Close'))),
    h('ol', { className: 'bt-skill-steps', 'aria-label': t('Installation steps') }, ['Choose a source', 'Review skills', 'Install and use'].map((step, index) => h('li', { key: step, 'aria-current': index === (preview ? 1 : 0) ? 'step' : undefined }, h('span', { className: 'bt-skill-step-number', 'aria-hidden': true }, index + 1), h('span', null, t(step))))),
    !preview ? h('div', null,
      h('div', { className: 'bt-skill-sources', role: 'group', 'aria-label': t('Installation source') }, [['upload', 'Upload files'], ['github', 'GitHub link'], ['write', 'Write instructions']].map(([id, label]) => h('button', { key: id, 'aria-pressed': mode === id, disabled: busy, onClick: () => { setMode(id); setError('') } }, t(label)))),
      mode !== 'write' ? h('label', { className: 'bt-skill-group-field' }, h('span', null, t('Install into group')), h('select', { className: 'bt-input', value: installCategory, disabled: busy, onChange: event => setInstallCategory(event.target.value) }, h('option', { value: '' }, t('Detect a group automatically')), [...SKILL_CATEGORIES, '未分类'].map(value => h('option', { key: value, value }, t(value))))) : null,
      mode === 'upload' ? h('div', { className: 'bt-skill-drop', 'data-dragging': dragging || undefined, onDragOver: event => { event.preventDefault(); setDragging(true) }, onDragLeave: () => setDragging(false), onDrop: event => { event.preventDefault(); setDragging(false); if (!busy) void upload(event.dataTransfer.files) } },
        h('svg', { className: 'bt-skill-upload-icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }, h('path', { d: 'M12 16V4m-4 4 4-4 4 4M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4' })),
        h('strong', null, t('Drop a ZIP file here')),
        h('p', null, t('You can also choose SKILL.md or a folder. Folder uploads keep all related files.')),
        h('div', { className: 'bt-actions' },
          h('button', { className: 'bt-soft', disabled: busy, onClick: () => files.current.click() }, t('Choose files')),
          h('button', { className: 'bt-soft', disabled: busy, onClick: () => folder.current.click() }, t('Choose a folder'))),
        h('input', { ref: files, type: 'file', hidden: true, multiple: true, accept: '.zip,.md', onChange: event => { void upload(event.target.files); event.target.value = '' } }),
        h('input', { ref: folder, type: 'file', hidden: true, multiple: true, webkitdirectory: '', onChange: event => { void upload(event.target.files); event.target.value = '' } }),
        h('small', null, t('Up to 100 MB per import. Nothing is executed during installation.'))) : null,
      mode === 'github' ? h('form', { className: 'bt-skill-form', onSubmit: event => { event.preventDefault(); void run(() => identify({ url })) } },
        h('label', null, t('Public GitHub repository or skill folder'), h('input', { className: 'bt-input', value: url, placeholder: 'https://github.com/owner/repository/tree/main/skills/example', onChange: event => setUrl(event.target.value) })),
        h('p', { className: 'bt-set-hint' }, t('Repository, directory, and SKILL.md links are supported. You choose which skills to install.')),
        h('button', { className: 'bt-soft', disabled: busy || !url.trim() }, t('Find skills'))) : null,
      mode === 'write' ? h('form', { className: 'bt-skill-form', onSubmit: event => { event.preventDefault(); void write() } },
        [['displayName', 'Display name', ''], ['name', 'Technical ID', 'my-skill'], ['purpose', 'What this skill helps with', '']].map(([key, label, placeholder]) => h('label', { key }, t(label), h('input', { className: 'bt-input', required: key === 'name', value: writing[key], placeholder, onChange: event => setWriting({ ...writing, [key]: event.target.value }) }))),
        h('label', null, t('Category'), h('select', { className: 'bt-input', value: writing.category, onChange: event => setWriting({ ...writing, category: event.target.value }) }, [...SKILL_CATEGORIES, '我的安装'].map(value => h('option', { key: value, value }, t(value))))),
        h('label', null, t('Skill instructions'), h('textarea', { className: 'bt-input bt-input-area', required: true, rows: 8, value: writing.content, onChange: event => setWriting({ ...writing, content: event.target.value }) })),
        h('button', { className: 'bt-soft', disabled: busy }, t('Save skill'))) : null) : h('div', { className: 'bt-skill-preview' },
      preview.candidates.map(item => {
        const choice = choices[item.key]
        return h('article', { key: item.key, className: 'bt-skill-detected', 'data-invalid': !item.valid || undefined },
          h('label', { className: 'bt-skill-section-head' }, h('strong', null, item.originalName || item.instruction), h('input', { type: 'checkbox', checked: choice.selected, disabled: !item.valid || busy, onChange: event => setChoice(item.key, { selected: event.target.checked }) })),
          !item.valid ? h('p', { role: 'alert' }, hostText(item.error)) : h('div', { className: 'bt-skill-form' },
            h('p', { className: 'bt-set-hint' }, t('{count} files · {size} MB', { count: item.files, size: (item.bytes / 1024 / 1024).toFixed(1) })),
            h('label', null, t('Display name (optional)'), h('input', { className: 'bt-input', value: choice.displayName, placeholder: item.originalName, disabled: busy, onChange: event => setChoice(item.key, { displayName: event.target.value }) })),
            h('label', null, t('Group'), h('select', { className: 'bt-input', value: choice.category, disabled: busy, onChange: event => setChoice(item.key, { category: event.target.value }) }, [...new Set([...SKILL_CATEGORIES, '未分类', choice.category])].map(value => h('option', { key: value, value }, t(value))))),
            h('label', null, t('What this skill helps with'), h('textarea', { className: 'bt-input', rows: 2, value: choice.purpose, disabled: busy, onChange: event => setChoice(item.key, { purpose: event.target.value }) })),
            h('label', null, t('Technical ID'), h('input', { className: 'bt-input', value: choice.name, disabled: busy, onChange: event => setChoice(item.key, { name: event.target.value }) })),
            item.exists ? h('label', null, t('A skill with this ID is already installed'), h('select', { className: 'bt-input', value: choice.conflict, disabled: busy, onChange: event => setChoice(item.key, { conflict: event.target.value }) }, h('option', { value: 'skip' }, t('Skip existing skill')), h('option', { value: 'replace' }, t('Replace after validation'))), h('small', null, t('To keep both, enter a different technical ID.'))) : null))
      }),
      h('div', { className: 'bt-actions' }, h('button', { className: 'bt-soft', disabled: busy, onClick: back }, t('Back')), h('button', { className: 'bt-soft bt-skill-primary', disabled: busy || !Object.values(choices).some(choice => choice.selected), onClick: install }, t('Install selected skills')))),
    busy ? h('p', { role: 'status' }, t('Processing skills…')) : null,
    error ? h('p', { className: 'bt-error', role: 'alert' }, error) : null)
}
