import { createElement as h, useEffect, useRef, useState } from 'react'
import { call } from './api.js'
import { language, t } from './i18n.js'
import { SearchIcon } from './icons.js'
import { matchingSkills, SKILL_CATEGORIES, skillCategory, skillLabel, isUserSkill } from '../shared/skills.js'
import { SkillInstaller } from './skill-installer.js'
import { skillEmoji, skillExample } from '../shared/skill-presentation.js'
import { SkillEmojiPicker, SKILL_EMOJI_CSS } from './skill-emoji-picker.js'

const recommended = (item, roster) => roster.bots.filter(bot => item.recommendedBots?.includes(bot.templateId))

function SkillDetail({ summary, roster, actions, onClose, onUse, onChanged }) {
  const [item, setItem] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const load = () => call('capability-detail', { name: summary.name }).then(setItem).catch(failure => setError(failure.message))
  useEffect(() => { let active = true; void call('capability-detail', { name: summary.name }).then(value => { if (active) setItem(value) }, failure => { if (active) setError(failure.message) }); return () => { active = false } }, [summary.name])
  const run = async work => { setError(''); setBusy(true); try { await work() } catch (failure) { setError(failure.message) } finally { setBusy(false) } }
  const update = (key, value) => setItem(previous => ({ ...previous, [key]: value }))
  return h('section', { className: 'bt-skill-detail bt-set-card', 'aria-label': t('Skill details'), 'aria-busy': busy },
    h('header', { className: 'bt-skill-section-head' }, h('div', { className: 'bt-skill-heading' }, h('span', { className: 'bt-skill-glyph', 'aria-hidden': true }, skillEmoji(item || summary)), h('div', null, h('span', { className: 'bt-skill-badge' }, t(skillCategory(item || summary))), h('h3', null, skillLabel(item || summary, language())))), h('button', { className: 'bt-soft bt-soft-sm', onClick: onClose }, t('Close'))),
    error ? h('p', { role: 'alert', className: 'bt-error' }, error) : null,
    !item ? h('p', { role: 'status' }, t('Loading…')) : h('div', null,
      editing ? h('form', { className: 'bt-skill-form', onSubmit: event => { event.preventDefault(); void run(async () => {
        await actions.saveCapability({ name: item.name, kind: 'skill', description: item.description, displayName: item.displayName, purpose: item.purpose, category: item.category, emoji: item.emoji ?? '',
          ...(!item.directory ? { content: item.content } : {}) }); setEditing(false); onChanged(); await load()
      }) } },
        [['displayName', 'Display name'], ['purpose', 'What this skill helps with']].map(([key, label]) => h('label', { key }, t(label), h('input', { className: 'bt-input', value: item[key] ?? '', onChange: event => update(key, event.target.value) }))),
        h(SkillEmojiPicker, { item, value: item.emoji ?? '', disabled: busy, onChange: value => update('emoji', value) }),
        h('label', null, t('Category'), h('select', { className: 'bt-input', value: item.category || '我的安装', onChange: event => update('category', event.target.value) }, [...new Set([...SKILL_CATEGORIES, '我的安装', item.category].filter(Boolean))].map(category => h('option', { key: category, value: category }, t(category))))),
        !item.directory ? h('label', null, t('Skill instructions'), h('textarea', { className: 'bt-input bt-input-area', rows: 12, value: item.content, onChange: event => update('content', event.target.value) })) : h('p', { className: 'bt-set-hint' }, t('To update scripts or instructions, reinstall the complete skill folder.')),
        h('div', { className: 'bt-actions' }, h('button', { type: 'button', className: 'bt-soft', onClick: () => { setEditing(false); void load() } }, t('Cancel')), h('button', { className: 'bt-soft', disabled: busy }, t('Save changes')))) : h('div', null,
        h('p', { className: 'bt-skill-purpose' }, item.purpose || item.description),
        h('dl', { className: 'bt-skill-facts' }, [
          ['Inputs', item.inputs || t('Describe your task and attach any relevant files.')],
          ['Deliverables', item.deliverables || t('See the skill instructions for its expected results.')],
          ['Recommended Bots', recommended(item, roster).map(bot => bot.name).join(' · ') || t('Choose any Bot for a one-time use.')],
          ['Dependencies', t(item.dependencies?.message || 'Resources are installed. Script dependencies are checked when the task needs them.')],
        ].map(([label, value]) => h('div', { key: label }, h('dt', null, t(label)), h('dd', null, value)))),
        item.dependencies?.state === 'needs-setup' ? h('button', { className: 'bt-soft', onClick: () => actions.openSettings('connectors') }, t('Set up the analysis environment')) : null,
        h('div', { className: 'bt-expert-example' }, h('span', null, t('Try asking')), h('p', null, skillExample(item, language()))),
        h('details', { className: 'bt-advanced' }, h('summary', null, t('Technical details and files')),
          h('dl', { className: 'bt-skill-facts' }, [['Technical ID', item.name], ['Original name', item.originalName || item.name], ['Version', item.version || item.builtinVersion || '—'], ['Source', item.source?.url || t(item.builtinSource ? 'Built-in' : 'My installation')]].map(([key, value]) => h('div', { key }, h('dt', null, t(key)), h('dd', null, value)))),
          h('pre', { className: 'bt-skill-file-tree' }, (item.files ?? []).map(file => file.path).join('\n')),
          item.dependencies?.manifests?.length ? h('p', null, t('Dependency files: {names}', { names: item.dependencies.manifests.join(' · ') })) : null,
          h('details', null, h('summary', null, t('Skill instructions')), h('pre', { className: 'bt-skill-content' }, item.content))),
        h('footer', { className: 'bt-skill-section-head' }, h('details', { className: 'bt-skill-manage' }, h('summary', null, t('Manage skill')),
          h('button', { className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => setEditing(true) }, t('Edit')),
          item.builtinSource ? h('button', { className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => void run(async () => { await actions.resetSkill(item.name); await load(); onChanged() }) }, t('Restore default instructions')) : null,
          h('button', { className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => setConfirming(true) }, t('Uninstall'))),
          h('button', { className: 'bt-soft bt-skill-primary', disabled: !isUserSkill(item), onClick: () => onUse(item) }, t('Use skill'))),
        !isUserSkill(item) ? h('p', { className: 'bt-set-hint' }, t('The author has disabled manual invocation for this skill.')) : null,
        confirming ? h('div', { className: 'bt-skill-confirm', role: 'alert' },
          h('p', null, t('Uninstall {name}?', { name: skillLabel(item, language()) })), h('p', null, t('Used by: {names}', { names: item.usedBy?.map(bot => bot.name).join(' · ') || t('No Bots') })),
          h('div', { className: 'bt-actions' }, h('button', { className: 'bt-soft', onClick: () => setConfirming(false) }, t('Cancel')), h('button', { className: 'bt-soft', disabled: busy, onClick: () => void run(async () => { await actions.deleteCapability(item.name); onChanged(); onClose() }) }, t('Confirm uninstall')))) : null)))
}

export function SkillLibrary({ roster, actions, selectedId }) {
  const region = useRef(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [installing, setInstalling] = useState(false)
  const [detail, setDetail] = useState(() => roster.capabilities.find(item => item.name === selectedId) ?? null)
  const [message, setMessage] = useState('')
  useEffect(() => {
    if (!detail && !installing) return
    const scroller = region.current?.closest('.bt-settings-scroll')
    if (scroller) scroller.scrollTo({ top: 0, behavior: 'instant' })
  }, [detail?.name, installing])
  const use = item => { void actions.useSkill(item.name).catch(failure => actions.reportError(failure)) }
  const skills = (roster.capabilities ?? []).filter(item => item.kind === 'skill')
  const groups = [...new Set([...SKILL_CATEGORIES, ...skills.map(skillCategory)])].filter(value => value !== '我的安装' && skills.some(item => skillCategory(item) === value))
  const items = matchingSkills(roster.capabilities ?? [], query, category, language()).sort((a, b) => skillLabel(a, language()).localeCompare(skillLabel(b, language()), language(), { numeric: true }))
  return h('section', { className: 'bt-expert-library bt-skill-library', ref: region },
    h('header', { className: 'bt-skill-section-head' }, h('p', { className: 'bt-library-intro' }, t('Find a skill for the work you want to do.')),
      h('button', { className: 'bt-soft bt-skill-primary', onClick: () => { setInstalling(!installing); setDetail(null) } }, t('Install a skill'))),
    message ? h('p', { role: 'status', className: 'bt-skill-success' }, message) : null,
    installing ? h(SkillInstaller, { actions, initialCategory: category, onClose: () => setInstalling(false), onInstalled: names => { setInstalling(false); setMessage(t('{count} skills installed. Choose a skill to use it.', { count: names.length })); setCategory('我的安装') } }) : null,
    detail ? h(SkillDetail, { key: detail.name, summary: detail, roster, actions, onClose: () => setDetail(null), onUse: use, onChanged: () => setMessage('') }) : null,
    h('div', { className: 'bt-catalog-search' }, h(SearchIcon), h('input', { value: query, onChange: event => setQuery(event.target.value), placeholder: t('Search tasks, skills, or keywords'), 'aria-label': t('Search tasks, skills, or keywords') })),
    h('div', { className: 'bt-catalog-categories', role: 'group', 'aria-label': t('Category') }, ['', ...groups, '我的安装'].map(value => h('button', { key: value, 'aria-pressed': category === value, onClick: () => setCategory(value) }, value ? t(value) : t('All skills'), h('span', { className: 'bt-skill-group-count' }, value === '我的安装' ? skills.filter(item => !item.builtinSource).length : value ? skills.filter(item => skillCategory(item) === value).length : skills.length)))),
    h('p', { className: 'bt-set-hint', role: 'status' }, t('{count} skills found', { count: items.length })),
    h('div', { className: 'bt-expert-grid' }, items.map(item => h('article', { className: 'bt-expert-card bt-skill-card', key: item.name },
      h('header', null, h('span', { className: 'bt-skill-glyph', 'aria-hidden': true }, skillEmoji(item)), h('div', null, h('h3', null, skillLabel(item, language())), h('span', { className: 'bt-skill-badge' }, t(skillCategory(item))))),
      h('p', { className: 'bt-expert-description bt-skill-clamp' }, item.purpose || item.description),
      h('div', { className: 'bt-expert-example' }, h('span', null, t('Try asking')), h('p', null, skillExample(item, language()))),
      h('footer', null, h('span', { className: 'bt-set-hint' }, t(item.builtinSource ? 'Built-in' : 'My installation')),
        h('div', { className: 'bt-actions' }, h('button', { className: 'bt-soft bt-soft-sm', onClick: () => { setDetail(item); setInstalling(false) } }, t('View details')),
          h('button', { className: 'bt-soft bt-soft-sm bt-skill-primary', disabled: !isUserSkill(item), title: !isUserSkill(item) ? t('Manual invocation is disabled') : undefined, onClick: () => use(item) }, t('Use skill'))))))),
    !items.length ? h('div', { className: 'bt-skill-empty' }, h('h3', null, t('No matching skills')), h('p', null, t('Try another keyword or category, or install your own skill.'))) : null)
}

export const SKILL_CSS = `
.bt-skill-library{gap:18px}.bt-skill-section-head{display:flex;align-items:center;justify-content:space-between;gap:16px}.bt-skill-section-head h3{font-size:17px;margin:0 0 7px}.bt-skill-section-head p{margin:0}.bt-skill-section-head>.bt-soft{flex-shrink:0}.bt-skill-library .bt-library-intro{font-size:13px;color:var(--bt-ink-2);font-weight:400}.bt-skill-primary{color:var(--bt-accent)!important;border:1px solid color-mix(in srgb,var(--bt-accent) 22%,var(--bt-line))!important;background:color-mix(in srgb,var(--bt-accent) 6%,var(--bt-card))!important}.bt-skill-glyph{width:44px;height:44px;display:grid;place-items:center;border-radius:12px;background:var(--bt-bubble);font-family:"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif;font-size:26px;line-height:1;flex-shrink:0}.bt-skill-heading{display:flex;align-items:center;gap:12px;min-width:0}.bt-skill-heading h3{overflow-wrap:anywhere}.bt-skill-form .bt-skill-icon-field{grid-column:1/-1}.bt-skill-badge{display:inline-block;font-size:11px;color:var(--bt-ink-3)}.bt-skill-card{gap:12px}.bt-skill-card header>div{flex:1}.bt-skill-card h3{font-size:15px!important}.bt-skill-clamp{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.bt-skill-card footer .bt-actions{gap:6px}.bt-skill-wizard,.bt-skill-detail{padding:20px;display:flex;flex-direction:column;gap:18px;overflow:visible}.bt-skill-detail{scroll-margin-top:12px}.bt-skill-detail>div{display:flex;flex-direction:column;gap:18px}.bt-skill-detail>div>div{display:flex;flex-direction:column;gap:18px}.bt-skill-purpose{line-height:1.8;color:var(--bt-ink-2);font-size:13px;margin:0}.bt-skill-form{display:flex;flex-direction:column;gap:14px;margin-top:16px}.bt-skill-form label{display:flex;flex-direction:column;gap:8px;font-size:12px;color:var(--bt-ink-2)}.bt-skill-form .bt-input{box-sizing:border-box;width:100%;max-width:none;font:inherit}.bt-skill-form textarea{resize:vertical;line-height:1.7}.bt-skill-form small{color:var(--bt-ink-3);line-height:1.6}.bt-skill-steps{display:flex;list-style:none;padding:0;margin:0;gap:20px;counter-reset:step;font-size:11px;color:var(--bt-ink-3)}.bt-skill-steps li::before{counter-increment:step;content:counter(step);display:inline-grid;place-items:center;margin-right:6px;width:20px;height:20px;border-radius:50%;background:var(--bt-bubble)}.bt-skill-steps [aria-current=step]{color:var(--bt-accent)}.bt-skill-drop{border:1px dashed var(--bt-line-2);border-radius:16px;padding:28px 20px;text-align:center;margin-top:16px;background:var(--bt-main)}.bt-skill-drop p,.bt-skill-drop small{font-size:12px;line-height:1.8;color:var(--bt-ink-3)}.bt-skill-drop .bt-actions{justify-content:center;margin:18px 0}.bt-skill-facts{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:0;font-size:12px;line-height:1.8}.bt-skill-facts dt{color:var(--bt-ink-3);margin-bottom:4px}.bt-skill-facts dd{margin:0;overflow-wrap:anywhere}.bt-skill-preview{display:flex;flex-direction:column;gap:14px}.bt-skill-detected{border:1px solid var(--bt-line);border-radius:12px;padding:16px}.bt-skill-detected[data-invalid=true]{border-color:var(--bt-danger)}.bt-skill-file-tree,.bt-skill-content{overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;max-height:300px;font:11px/1.7 ui-monospace,Consolas,monospace}.bt-skill-file-tree{white-space:pre}.bt-skill-manage{font-size:12px}.bt-skill-manage summary{cursor:pointer;color:var(--bt-ink-3)}.bt-skill-manage[open] .bt-soft{margin:12px 6px 0 0}.bt-skill-confirm{padding:16px;border:1px solid var(--bt-danger);border-radius:12px;font-size:12px}.bt-skill-empty{text-align:center;padding:40px 20px;color:var(--bt-ink-3)}.bt-skill-success{padding:12px 16px;border:1px solid var(--bt-line);border-radius:10px;color:var(--bt-green);font-size:12px}.bt-skill-tabs{margin-bottom:20px}.bt-skill-use-error{color:var(--bt-danger);font-size:12px}
@media(max-width:760px){.bt-skill-section-head{align-items:flex-start;flex-wrap:wrap}.bt-skill-wizard,.bt-skill-detail{padding:16px}.bt-skill-facts{grid-template-columns:1fr}.bt-skill-steps{gap:8px;flex-wrap:wrap}.bt-skill-card footer{flex-wrap:wrap}}
` + `
.bt-skill-group-count{display:inline-block;margin-left:6px;color:var(--bt-ink-3);font-size:10px;font-variant-numeric:tabular-nums}.bt-skill-wizard{gap:22px;padding:24px;background:var(--bt-card);border:1px solid var(--bt-line-2);box-shadow:0 4px 16px color-mix(in srgb,var(--bt-ink) 3%,transparent)}.bt-skill-wizard>.bt-skill-section-head{align-items:flex-start}.bt-skill-wizard>.bt-skill-section-head h3{font-size:18px}.bt-skill-wizard>.bt-skill-section-head p{font-size:12px;line-height:1.8;max-width:440px}.bt-skill-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.bt-skill-steps li{display:flex;align-items:center;gap:9px;padding:11px 12px;background:var(--bt-main);border:1px solid var(--bt-line);border-radius:10px;font-size:12px;line-height:1.5}.bt-skill-steps li::before{display:none;content:none}.bt-skill-step-number{display:grid;place-items:center;width:23px;height:23px;border-radius:999px;background:var(--bt-bubble);flex-shrink:0;font-size:11px;font-weight:600}.bt-skill-steps [aria-current=step]{color:var(--bt-accent);border-color:color-mix(in srgb,var(--bt-accent) 25%,var(--bt-line));background:color-mix(in srgb,var(--bt-accent) 4%,var(--bt-card))}.bt-skill-steps [aria-current=step] .bt-skill-step-number{color:var(--bt-card);background:var(--bt-accent)}.bt-skill-sources{display:flex;gap:5px;padding:5px;border:1px solid var(--bt-line);border-radius:12px;background:var(--bt-main)}.bt-skill-sources button{font:inherit;font-size:12px;line-height:1.5;padding:9px 15px;border:1px solid transparent;border-radius:8px;background:transparent;color:var(--bt-ink-3);cursor:pointer;flex:1}.bt-skill-sources button[aria-pressed=true]{background:var(--bt-card);border-color:var(--bt-line);color:var(--bt-ink);box-shadow:0 1px 3px color-mix(in srgb,var(--bt-ink) 5%,transparent)}.bt-skill-group-field{display:flex;align-items:center;justify-content:space-between;gap:14px;margin:18px 0;color:var(--bt-ink-2);font-size:12px}.bt-skill-group-field .bt-input{width:220px;max-width:65%;box-sizing:border-box;font:inherit}.bt-skill-upload-icon{display:block;width:32px;height:32px;margin:0 auto 16px;color:var(--bt-accent)}.bt-skill-drop{padding:30px 22px;margin-top:0;transition:border-color .15s,background .15s}.bt-skill-drop strong{font-size:14px;color:var(--bt-ink)}.bt-skill-drop p{margin:10px auto 0;max-width:360px}.bt-skill-drop small{font-size:11px}.bt-skill-drop[data-dragging]{border-color:var(--bt-accent);background:var(--bt-bubble)}.bt-skill-detected>.bt-skill-section-head strong{font-size:14px}.bt-skill-detected .bt-skill-form{display:grid;grid-template-columns:1fr 1fr;gap:15px}.bt-skill-detected .bt-skill-form>p,.bt-skill-detected .bt-skill-form>label:has(textarea){grid-column:1/-1}.bt-skill-wizard button:focus-visible,.bt-skill-wizard input:focus-visible,.bt-skill-wizard select:focus-visible{outline:2px solid var(--bt-accent);outline-offset:2px}
@media(max-width:760px){.bt-skill-wizard{padding:16px;gap:18px}.bt-skill-steps{gap:6px}.bt-skill-steps li{padding:8px 7px;gap:6px;font-size:11px}.bt-skill-sources button{padding:8px 7px}.bt-skill-detected .bt-skill-form{grid-template-columns:1fr}.bt-skill-group-field{flex-wrap:wrap}.bt-skill-group-field .bt-input{width:100%;max-width:none}}
` + SKILL_EMOJI_CSS
