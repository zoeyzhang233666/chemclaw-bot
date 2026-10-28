import { createElement as h, useEffect, useRef, useState } from 'react'
import { isMainOf } from './sources.js'
import { PlusIcon, ChevronRightIcon, SearchIcon, CheckIcon } from './icons.js'
import { BotAvatar, BotMark, RoomAvatar } from './mark.js'
import { Card, Row, InlineText, SwitchRow } from './bot-settings.js'
import { Segmented } from './motion.js'
import { FolderMenu } from './folder-menu.js'
import { PermissionPicker } from './permission-picker.js'
import { t } from './i18n.js'
import { CategoryMenu, ItemCategory, assignCategory } from './sidebar-categories.js'

export const ROOM_MODES = [
  ['admin', 'Admin leads', 'Plain messages go to the admin, who calls others with @Name.'],
  ['everyone', 'Everyone', 'Every member answers in turn, admin first.'],
]

// Without an admin the host answers as everyone, whatever the stored mode says.
export const shownMode = (room, roster) => (roster.byId[room.admin] ? room.mode : 'everyone')

export function roomSubtitle(room, roster) {
  const admin = roster.byId[room.admin]
  return [t('{count} members', { count: room.members.length }), admin ? t('Admin {name}', { name: admin.name }) : t('No admin')].join(' · ')
}

// The one guard a group keeps: how many Bot turns may answer Bot calls since the
// user last wrote in it, after which the group pauses until the user goes on or
// writes. Empty means the default, three relays per member.
function RelayLimitRow({ room, update }) {
  const [draft, setDraft] = useState(room.relayLimit ?? '')
  useEffect(() => setDraft(room.relayLimit ?? ''), [room.relayLimit])
  const save = () => {
    const text = String(draft).trim()
    if (text === '') {
      if (room.relayLimit !== undefined) update({ relayLimit: null })
      return
    }
    const limit = Number(text)
    if (!Number.isInteger(limit) || limit < 1 || limit > 200 || limit === room.relayLimit) { setDraft(room.relayLimit ?? ''); return }
    update({ relayLimit: limit })
  }
  return h(Row, { label: t('Pause Bot relays after'), hint: t('Counted since your last message in this group.') },
    h('input', {
      className: 'bt-bs-input bt-bs-num', type: 'number', min: 1, max: 200,
      placeholder: String(room.relayLimitDefault ?? ''), value: draft,
      'aria-label': t('Pause Bot relays after'),
      onChange: event => setDraft(event.target.value),
      onBlur: save,
      onKeyDown: event => { if (event.key === 'Enter') { event.preventDefault(); event.currentTarget.blur() } },
    }))
}

// One preset for every member in the group, or each member's own. Turning it on starts
// from DSH's default preset.
function GroupPermission({ room, catalog, update }) {
  if (!catalog?.options?.length) return null
  const shared = room.permission !== undefined
  return h(Card, { title: t('Permissions') },
    h(SwitchRow, {
      label: t('Same for every member'), hint: t("Replaces each member's own permissions in this group."), on: shared,
      onChange: on => update({ permission: on ? catalog.defaultPreset ?? catalog.options[0].value : null }),
    }),
    shared ? h('div', { className: 'bt-set-row bt-bs-row bt-bs-stack bt-gs-perm bt-veil' },
      h(PermissionPicker, { catalog, saved: room.permission, onPick: permission => update({ permission }) })) : null)
}

// A group chat's settings as grouped cards: its name and notice, who answers, its
// members and admin, its permissions, its sidebar place, and deleting it. The user may
// change all of it; the host enforces what Bots may change.
export function GroupSettingsForm({ room, roster, actions, run, onDeleted }) {
  const [adding, setAdding] = useState(false)
  const [confirming, setConfirming] = useState(false)
  useEffect(() => {
    if (!confirming) return undefined
    const timer = setTimeout(() => setConfirming(false), 4000)
    return () => clearTimeout(timer)
  }, [confirming])
  const members = room.members.map(id => roster.byId[id]).filter(Boolean)
  const outside = roster.bots.filter(bot => !room.members.includes(bot.id))
  const admin = roster.byId[room.admin]
  const mode = shownMode(room, roster)
  const modeHint = ROOM_MODES.find(([id]) => id === mode)?.[2] ?? ''
  const update = patch => run(actions.updateRoom(room.id, patch))
  const openBot = (id) => { actions.closeSettings(); actions.openSession(id) }
  const remove = () => {
    if (!confirming) { setConfirming(true); return }
    void Promise.resolve(run(actions.deleteRoom(room.id))).then((done) => { if (done) onDeleted?.() })
  }
  return h('div', { className: 'bt-bs' },
    h('div', { className: 'bt-bs-hero' },
      h(RoomAvatar, { room, roster, size: 64 }),
      h('div', { className: 'bt-bs-who' },
        h('span', { className: 'bt-bs-name' }, room.name),
        h('span', { className: 'bt-bs-sub' }, roomSubtitle(room, roster)))),
    h(Card, { title: t('Profile') },
      h(Row, { label: t('Name'), hint: t('Leave it empty to name the group after its members.') },
        h(InlineText, { label: t('Group name'), value: room.named ? room.name : '', placeholder: t('Name after members'), maxLength: 60, onSave: name => update({ name }) })),
      h(Row, { label: t('Notice'), hint: t('Every member reads it before speaking in this group.'), stack: true },
        h(InlineText, { label: t('Group notice'), value: room.notice, multiline: true, maxLength: 2000, placeholder: t('Shared instructions every member reads before speaking…'), onSave: notice => update({ notice }) }))),
    h(Card, { title: t('Who answers') },
      h('div', { className: 'bt-set-row bt-bs-row bt-bs-stack' },
        h(Segmented, { label: t('Who answers'), value: mode }, ROOM_MODES.map(([id, label]) => h('button', {
          key: id, type: 'button', 'aria-pressed': mode === id, disabled: id === 'admin' && !admin,
          title: id === 'admin' && !admin ? t('Choose an admin first') : undefined,
          onClick: () => { if (mode !== id) void update({ mode: id }) },
        }, t(label)))),
        h('span', { key: mode, className: 'bt-set-hint bt-veil' }, `${t(modeHint)} ${t('@mentions always pick who answers.')}`)),
      h(RelayLimitRow, { room, update })),
    h(Card, { title: t('Working folder') },
      h('div', { className: 'bt-set-row bt-bs-row' },
        h('span', { className: 'bt-set-copy' }, h('span', { className: 'bt-bs-label' }, t('Folder'))),
        h(FolderMenu, { value: room.workDir, group: true, actions, run, onPick: workDir => update({ workDir }) }))),
    h(GroupPermission, { room, catalog: roster.permissions, update }),
    h(Card, { title: t('Members · {count}', { count: members.length }) },
      members.map((member) => {
        const leads = room.admin === member.id
        return h('div', { key: member.id, className: 'bt-set-row bt-bs-row bt-gs-member' },
          h('button', { type: 'button', className: 'bt-gs-who', title: t("Open {name}'s chat", { name: member.name }), onClick: () => openBot(member.id) },
            h(BotAvatar, { bot: member, size: 26, main: isMainOf(roster, member.id), admin: leads, live: false }),
            h('span', { className: 'bt-row-title' }, member.name),
            leads ? h('span', { className: 'bt-tag' }, t('Admin')) : null),
          leads
            ? h('button', { type: 'button', className: 'bt-mini', title: t('Leave the group without an admin'), onClick: () => update({ admin: null }) }, t('Unset'))
            : h('button', { type: 'button', className: 'bt-mini', onClick: () => update({ admin: member.id }) }, t('Make admin')),
          members.length > 2 ? h('button', { type: 'button', className: 'bt-x', 'aria-label': t('Remove {name} from the group', { name: member.name }), title: t('Remove from group'), onClick: () => update({ remove: [member.id] }) }, '×') : null)
      }),
      adding
        ? [...outside.map(bot => h('button', { key: bot.id, type: 'button', className: 'bt-set-row bt-bs-row bt-gs-pick', onClick: () => { setAdding(false); void update({ add: [bot.id] }) } },
            h(BotMark, { bot, size: 22 }),
            h('span', { className: 'bt-set-copy' }, h('span', { className: 'bt-bs-label' }, bot.name)),
            h('span', { className: 'bt-set-hint' }, t('Add')))),
          h('button', { key: 'cancel', type: 'button', className: 'bt-set-row bt-bs-row bt-gs-add', onClick: () => setAdding(false) }, t('Cancel'))]
        : outside.length > 0
          ? h('button', { type: 'button', className: 'bt-set-row bt-bs-row bt-gs-add', onClick: () => setAdding(true) }, h(PlusIcon), t('Add member'))
          : null,
      h('div', { className: 'bt-set-row bt-gs-note' }, h('span', { className: 'bt-set-hint' },
        // The host checks for two members on every change, even a rename.
        members.length < 2 ? t('Add a Bot first: a group chat needs at least two.')
          : admin ? t('{name} leads this group: it can call members with @Name, change the group, and post here.', { name: admin.name })
            : t('No admin yet. An admin can call members with @Name, change the group, and post here.')))),
    h(Card, { title: t('Sidebar') },
      h(Row, { label: t('Sidebar category') }, h(ItemCategory, { item: room, kind: 'room', roster, actions, run })),
      h(SwitchRow, { label: t('Pin'), hint: t('Kept above the other chats.'), on: room.pinned === true, onChange: pinned => run(actions.setFlags(room.id, { pinned })) }),
      h(SwitchRow, { label: t('Hide from sidebar'), hint: t('Search still finds it.'), on: room.hidden === true, onChange: hidden => run(actions.setFlags(room.id, { hidden })) })),
    h(Card, { title: t('Manage') },
      h('button', { type: 'button', className: 'bt-set-row bt-bs-row bt-bs-danger', 'data-confirm': confirming || undefined, onClick: remove },
        h('span', { className: 'bt-set-copy' },
          h('span', { className: 'bt-bs-label' }, confirming ? t('Delete {name}?', { name: room.name }) : t('Delete group')),
          h('span', { className: 'bt-set-hint' }, confirming ? t('Click again to delete. Its history is archived.') : t('Removes the group chat. Its members stay on the team.'))),
        h('span', { className: 'bt-chevron' }, h(ChevronRightIcon)))))
}

// A new group chat from Settings: its admin first, then the other members, then a name
// if the member names will not do.
export function NewGroupForm({ roster, actions, run, onCreated, onCancel }) {
  const frame = useRef(null)
  useEffect(() => { frame.current?.scrollIntoView({ block: 'start' }); frame.current?.focus({ preventScroll: true }) }, [])
  const [admin, setAdmin] = useState(null)
  const [members, setMembers] = useState([])
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [adminQuery, setAdminQuery] = useState('')
  const [memberQuery, setMemberQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const toggle = id => setMembers(list => (list.includes(id) ? list.filter(item => item !== id) : [...list, id]))
  const pickAdmin = (id) => { setAdmin(id); setMembers(list => list.filter(item => item !== id)) }
  const create = async () => {
    if (busy || admin === null || members.length === 0) return
    setBusy(true)
    let room
    const done = await run(actions.createRoom([admin, ...members], { admin, greet: true, ...(name.trim() ? { name: name.trim() } : {}) }).then(async (value) => {
      room = value
      if (category) await assignCategory(actions, 'room', room.id, category).catch(error => actions.reportError(error, 'sidebar'))
    }))
    if (done && room) onCreated(room)
    else setBusy(false)
  }
  const chip = (bot, on, onClick, role) => h('button', {
    key: bot.id, type: 'button', role, className: 'bt-ng-chip', 'aria-checked': on, onClick, disabled: busy, title: bot.name,
  }, h(BotAvatar, { bot, size: 30, badge: false, live: false }), h('span', { className: 'bt-ng-name' }, bot.name),
  h('span', { className: 'bt-ng-check', 'aria-hidden': true }, on ? h(CheckIcon) : null))
  const matches = query => bot => `${bot.name} ${bot.role ?? ''}`.toLowerCase().includes(query.trim().toLowerCase())
  const admins = roster.bots.filter(matches(adminQuery))
  const candidates = roster.bots.filter(bot => bot.id !== admin).filter(matches(memberQuery))
  const search = (label, value, onChange, disabled) => h('label', { className: 'bt-ng-search' }, h(SearchIcon),
    h('input', { value, disabled, 'aria-label': label, placeholder: t('Search experts'), onChange: event => onChange(event.target.value) }))
  return h('div', { ref: frame, className: 'bt-set-card bt-ng', role: 'group', 'aria-label': t('Create group chat'), tabIndex: -1 },
    h('header', { className: 'bt-ng-header' }, h('h3', null, t('Create group chat')), h('p', null, t('Choose an admin and members, then name your group.'))),
    h('div', { className: 'bt-ng-body' },
      h('div', { className: 'bt-ng-roster' },
        h('section', { className: 'bt-ng-section' },
          h('h4', null, h('span', { className: 'bt-ng-step-no' }, '1'), t('Choose the group admin')),
          search(t('Search group admin'), adminQuery, setAdminQuery, busy),
          h('div', { className: 'bt-ng-picks', role: 'radiogroup', 'aria-label': t('Group admin') },
            admins.map(bot => chip(bot, admin === bot.id, () => pickAdmin(bot.id), 'radio')),
            admins.length === 0 ? h('span', { className: 'bt-ng-empty' }, t('No matching experts.')) : null)),
        h('section', { className: 'bt-ng-section' },
          h('h4', null, h('span', { className: 'bt-ng-step-no' }, '2'), t('Members'), h('span', { className: 'bt-tag' }, t('{count} selected', { count: members.length }))),
          search(t('Search group members'), memberQuery, setMemberQuery, busy || admin === null),
          h('div', { className: 'bt-ng-picks', role: 'group', 'aria-label': t('Members') },
            admin === null ? h('span', { className: 'bt-ng-empty' }, t('Choose an admin first'))
              : candidates.map(bot => chip(bot, members.includes(bot.id), () => toggle(bot.id), 'checkbox')),
            admin !== null && candidates.length === 0 ? h('span', { className: 'bt-ng-empty' }, t('No matching experts.')) : null))),
      h('div', { className: 'bt-ng-fields' },
        h('label', null, h('span', null, t('Group name')),
          h('input', { className: 'bt-input bt-ng-input', value: name, disabled: busy, maxLength: 60, 'aria-label': t('Group name'), placeholder: t('Name after members'), onChange: event => setName(event.target.value) })),
        h('div', null, h('span', null, t('Sidebar category')), h(CategoryMenu, { roster, actions, kinds: ['room'], picker: true, value: category, disabled: busy, onPick: (_kind, id) => setCategory(id) })))),
    h('div', { className: 'bt-task-foot bt-ng-footer' },
      h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: onCancel }, t('Cancel')),
      h('button', { type: 'button', className: 'bt-send bt-soft-sm', disabled: busy || admin === null || members.length === 0, onClick: () => void create() }, t('Create group chat'))))
}

export const GROUP_SETTINGS_CSS = `
.bt-set-card.bt-ng{display:block;flex:none;min-width:0;overflow:hidden;outline:none;animation:bt-veil-in .2s ease-out}
.bt-ng-header{padding:20px 20px 0;border-top:0!important}
.bt-ng-header h3{margin:0;font-size:17px;line-height:24px;font-weight:600}
.bt-ng-header p{margin:6px 0 0;font-size:12px;line-height:19px;color:var(--bt-ink-2)}
.bt-ng>.bt-ng-body{padding:20px;border-top:0}
.bt-ng-roster{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr));gap:16px}
.bt-ng-section{display:flex;flex-direction:column;gap:10px;min-width:0;padding:12px;border:1px solid var(--bt-line);border-radius:10px;background:var(--bt-main)}
.bt-ng-section h4{display:flex;align-items:center;gap:7px;margin:0;font-size:13px;line-height:22px;font-weight:600}
.bt-ng-section h4 .bt-tag{margin-left:auto}
.bt-ng-step-no{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:var(--bt-bubble);color:var(--bt-ink-2);font-size:11px;flex:none}
.bt-ng-search{display:flex;align-items:center;gap:7px;min-width:0;padding:7px 9px;border:1px solid var(--bt-line-2);border-radius:8px;color:var(--bt-ink-2);background:var(--bt-card)}
.bt-ng-search svg{width:15px;height:15px;flex:none}
.bt-ng-search input{min-width:0;width:100%;border:0;outline:none;background:none;color:var(--bt-ink);font:inherit;font-size:12px;line-height:18px}
.bt-ng-picks{display:flex;flex-direction:column;gap:4px;height:clamp(200px,32vh,300px);overflow-y:auto;min-width:0;scrollbar-width:thin;padding-right:3px}
.bt-ng-chip{display:flex;align-items:center;gap:9px;flex:none;min-width:0;width:100%;height:44px;padding:5px 8px;border-radius:8px;border:1px solid transparent;background:none;color:var(--bt-ink);font:inherit;font-size:13px;text-align:left;cursor:pointer;transition:background-color .12s ease,color .12s ease,border-color .12s ease}
.bt-ng-chip:hover{background:var(--bt-hover);color:var(--bt-ink)}
.bt-ng-chip[aria-checked=true]{background:var(--bt-bubble);border-color:var(--bt-line-2);color:var(--bt-ink)}
.bt-ng-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt-ng-check{display:inline-flex;align-items:center;justify-content:center;flex:none;width:16px;height:16px;border:1px solid var(--bt-line-2);border-radius:4px;box-sizing:border-box}
.bt-ng-chip[role=radio] .bt-ng-check{border-radius:50%}
.bt-ng-chip[aria-checked=true] .bt-ng-check{color:var(--bt-accent);border-color:var(--bt-accent)}
.bt-ng-check svg{width:12px;height:12px}
.bt-ng-empty{margin:auto;padding:16px;color:var(--bt-ink-2);font-size:12px;line-height:20px;text-align:center}
.bt-ng-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(220px,100%),1fr));gap:16px;margin-top:20px}
.bt-ng-fields>label,.bt-ng-fields>div{display:flex;flex-direction:column;gap:8px;min-width:0;font-size:13px;font-weight:500}
.bt-ng-fields .bt-input{height:36px;min-width:0;font-weight:400}
.bt-ng-fields .bt-side-filter{width:100%;min-height:36px;justify-content:space-between;font-weight:400}
.bt-ng-footer{display:flex;align-items:center;justify-content:flex-end;gap:10px;padding:14px 20px;background:var(--bt-card)}
@media (max-width:600px){.bt-ng-header{padding:16px 16px 0}.bt-ng>.bt-ng-body{padding:16px}.bt-ng-footer{padding:12px 16px}}
@media (prefers-reduced-motion:reduce){.bt-ng{animation:none}}
.bt-gs-member{gap:8px}
.bt-gs-who{flex:1;display:flex;align-items:center;gap:8px;min-width:0;padding:0;border:0;background:none;color:inherit;font:inherit;text-align:left;cursor:pointer}
.bt-gs-who .bt-row-title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt-gs-who:hover .bt-row-title{text-decoration:underline;text-underline-offset:2px}
.bt-gs-add{gap:8px;color:var(--bt-ink-2)}
.bt-gs-pick{gap:10px;animation:bt-rise .16s ease-out}
.bt-bs-stack .bt-seg{align-self:stretch}
.bt-gs-perm .bt-seg button{flex:auto;white-space:nowrap}
@media (prefers-reduced-motion:reduce){.bt-gs-pick{animation:none}}
`
