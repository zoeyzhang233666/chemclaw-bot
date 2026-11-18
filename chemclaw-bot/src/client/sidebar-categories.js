import { createElement as h, Fragment, useState } from 'react'
import { createPortal } from 'react-dom'
import { CheckIcon, PencilIcon, PlusIcon, SlidersIcon, TrashIcon } from './icons.js'
import { Caret, useAnchoredMenu } from './model-menu.js'
import { botCategoryId, roomCategoryId, sidebarCategories, expertCategoryId, categoryFallback, canDeleteCategory, deleteSidebarCategory, SPECIALISTS_CATEGORY, ROOMS_CATEGORY } from '../shared/sidebar-prefs.js'
import { hostText, t } from './i18n.js'

export function categoryLabel(category) {
  return category.name === SPECIALISTS_CATEGORY ? t('Specialist Bots')
    : category.name === ROOMS_CATEGORY ? t('Other groups') : category.name
}

export function assignCategory(actions, kind, id, category) {
  return actions.setPrefs({ sidebar: { categoryAssignments: { [`${kind}:${id}`]: category || null } } })
}

function CategoryEditor({ kind, category, roster, actions, onSaved, onCancel }) {
  const [name, setName] = useState(category ? categoryLabel(category) : '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const trimmed = kind === 'bot' ? expertCategoryId(name.trim()) : name.trim()
  const duplicate = sidebarCategories(roster, kind).some(item => item.id !== category?.id && categoryLabel(item).toLocaleLowerCase() === trimmed.toLocaleLowerCase())
  const save = async event => {
    event.preventDefault()
    if (!trimmed || busy || duplicate) return
    setBusy(true)
    setError('')
    const next = { id: category?.id ?? `custom:${crypto.randomUUID()}`, kind, name: trimmed }
    const categories = [...(roster.prefs?.sidebar?.categories ?? []).filter(item => item.id !== next.id), next]
    try {
      const prefs = await actions.setPrefs({ sidebar: { categories } })
      if (!prefs?.sidebar?.categories?.some(category => category.id === next.id && category.name === next.name && category.kind === next.kind)) {
        throw new Error(t('The category was not saved. Restart ChemClaw to load the updated plugin, then try again.'))
      }
      onSaved(next)
    } catch (failure) {
      setError(hostText(failure.message ?? String(failure)))
      setBusy(false)
    }
  }
  return h('form', { className: 'bt-category-editor', onSubmit: event => void save(event) },
    h('label', null, h('span', null, category ? t('Rename category') : t('New category')),
      h('input', { autoFocus: true, className: 'bt-input', value: name, maxLength: 64, 'aria-label': t('Category name'), disabled: busy, onChange: event => setName(event.target.value) })),
    duplicate ? h('span', { className: 'bt-note bt-danger' }, t('A category with this name already exists.')) : null,
    error ? h('span', { className: 'bt-note bt-danger', role: 'alert' }, error) : null,
    h('div', { className: 'bt-category-editor-actions' },
      h('button', { type: 'button', disabled: busy, onClick: onCancel }, t('Cancel')),
      h('button', { type: 'submit', disabled: busy || !trimmed || duplicate }, t('Save'))))
}

function CategoryDelete({ category, roster, actions, onDeleted, onCancel }) {
  const { kind, id } = category
  const fallback = categoryFallback(kind)
  const choices = sidebarCategories(roster, kind).filter(item => item.id !== id)
  if (!choices.some(item => item.id === fallback)) choices.push({ id: fallback, kind, name: fallback })
  const [target, setTarget] = useState(fallback)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const sidebar = roster.prefs?.sidebar ?? {}
  const items = kind === 'bot' ? roster.bots : roster.rooms
  const count = items.filter(item => (kind === 'bot' ? botCategoryId(item, sidebar) : roomCategoryId(item, sidebar)) === id).length
  const remove = async event => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const prefs = await actions.setPrefs({ sidebar: deleteSidebarCategory(roster, category, target) })
      if (!prefs?.sidebar?.deletedCategories?.includes(id)) throw new Error(t('The category was not deleted. Restart ChemClaw to load the updated plugin, then try again.'))
      onDeleted({ kind, id, targetId: target })
    } catch (failure) {
      setError(hostText(failure.message ?? String(failure)))
      setBusy(false)
    }
  }
  return h('form', { className: 'bt-category-editor', onSubmit: event => void remove(event) },
    h('strong', { className: 'bt-category-delete-name' }, categoryLabel(category)),
    h('p', { className: 'bt-category-delete-hint' }, t('Only the category is removed. Experts and chats are kept.')),
    count > 0 ? h('label', null, h('span', null, t('Move contents to')),
      h('select', { className: 'bt-select', 'aria-label': t('Move contents to'), value: target, disabled: busy, onChange: event => setTarget(event.target.value) },
        choices.map(item => h('option', { key: item.id, value: item.id }, categoryLabel(item))))) : null,
    error ? h('span', { className: 'bt-note bt-danger', role: 'alert' }, error) : null,
    h('div', { className: 'bt-category-editor-actions' },
      h('button', { type: 'button', disabled: busy, onClick: onCancel }, t('Cancel')),
      h('button', { type: 'submit', className: 'bt-danger', disabled: busy }, t('Delete category'))))
}

// Category identity stays stable when its display name changes, so manual order,
// collapsed state and assignments keep pointing at the same category.
export function CategoryMenu({ roster, actions, kinds, selected, onPick, onCreated, onDeleted, manage = false, picker = false, value, disabled = false }) {
  const { isOpen, shownPlace, leaving, button, menu, open, close } = useAnchoredMenu()
  const [editing, setEditing] = useState(null)
  const categories = kinds.flatMap(kind => sidebarCategories(roster, kind))
  const chosen = categories.find(category => category.id === value)
  const pick = (kind, id) => { onPick(kind, id); close() }
  const editable = !roster.readOnly
  return h(Fragment, null,
    h('button', {
      ref: button, type: 'button', className: 'bt-side-filter', disabled,
      'aria-haspopup': editing ? 'dialog' : 'menu', 'aria-expanded': isOpen,
      'aria-label': picker ? t('Sidebar category') : manage ? t('Manage categories') : t('Filter categories'),
      onClick: () => { if (isOpen) close(); else { setEditing(null); open() } },
    }, picker ? null : h(SlidersIcon), h('span', null, picker ? chosen ? categoryLabel(chosen) : t('Uncategorized') : manage ? t('Manage categories') : t('Filter')), h(Caret)),
    shownPlace ? createPortal(h('div', {
      ref: menu, className: 'bt-menu bt-model-menu bt-category-menu', style: shownPlace,
      role: editing ? 'dialog' : 'menu', 'aria-label': editing?.remove ? t('Delete category') : editing ? t('Edit category') : t('Filter categories'), 'data-leaving': leaving || undefined,
      inert: leaving || undefined, 'aria-hidden': leaving || undefined,
    }, editing?.remove ? h(CategoryDelete, {
      category: editing.category, roster, actions, onCancel: () => setEditing(null),
      onDeleted: result => {
        setEditing(null)
        if (onDeleted) { onDeleted(result); close() }
        else if (!picker || value === result.id) pick(result.kind, result.targetId)
        else close()
      },
    }) : editing ? h(CategoryEditor, {
      key: editing.category?.id ?? editing.kind, ...editing, roster, actions,
      onCancel: () => setEditing(null),
      onSaved: category => {
        const created = !editing.category
        setEditing(null)
        if (created && onCreated) { onCreated(category); close() }
        else if (picker || created) pick(category.kind, category.id)
      },
    }) : h(Fragment, null,
      !picker ? h('button', { type: 'button', role: 'menuitemradio', 'aria-checked': !selected, onClick: () => pick(null, null) },
        h('span', { className: 'bt-menu-label' }, t('All')), h('span', { className: 'bt-model-tick', 'aria-hidden': true }, !selected ? h(CheckIcon) : null)) : null,
      kinds.map(kind => h(Fragment, { key: kind },
        h('div', { className: 'bt-model-group', role: 'presentation' }, kind === 'bot' ? t('Expert categories') : t('Group categories')),
        !picker && kinds.length > 1 ? h('button', { type: 'button', role: 'menuitemradio', 'aria-checked': selected?.kind === kind && !selected?.id, onClick: () => pick(kind, null) },
          h('span', { className: 'bt-menu-label' }, kind === 'bot' ? t('All experts') : t('All expert groups')),
          h('span', { className: 'bt-model-tick', 'aria-hidden': true }, selected?.kind === kind && !selected?.id ? h(CheckIcon) : null)) : null,
        categories.filter(category => category.kind === kind).map(category => {
          const checked = picker ? value === category.id : selected?.kind === kind && selected?.id === category.id
          return h('div', { key: category.id, className: 'bt-category-menu-row', role: 'presentation' },
            h('button', { type: 'button', role: 'menuitemradio', 'aria-checked': checked, onClick: () => pick(kind, category.id) },
              h('span', { className: 'bt-menu-label' }, categoryLabel(category)), h('span', { className: 'bt-model-tick', 'aria-hidden': true }, checked ? h(CheckIcon) : null)),
            editable ? h('button', { type: 'button', className: 'bt-category-rename', role: 'menuitem', 'aria-label': t('Rename category {name}', { name: categoryLabel(category) }), title: t('Rename category'), onClick: () => setEditing({ kind, category }) }, h(PencilIcon)) : null,
            editable ? h('button', { type: 'button', className: 'bt-category-remove', role: 'menuitem', disabled: !canDeleteCategory(category), 'aria-label': t('Delete category {name}', { name: categoryLabel(category) }), title: canDeleteCategory(category) ? t('Delete category') : t('The default category is kept for unassigned conversations.'), onClick: () => setEditing({ kind, category, remove: true }) }, h(TrashIcon)) : null)
        }),
        editable ? h('button', { type: 'button', role: 'menuitem', className: 'bt-category-add', onClick: () => setEditing({ kind }) }, h(PlusIcon), h('span', { className: 'bt-menu-label' }, kind === 'bot' ? t('New expert category') : t('New group category'))) : null)))), document.body) : null)
}

export function ItemCategory({ item, kind, roster, actions, run }) {
  const sidebar = roster.prefs?.sidebar ?? {}
  const value = kind === 'bot' ? botCategoryId(item, sidebar) : roomCategoryId(item, sidebar)
  return h(CategoryMenu, { roster, actions, kinds: [kind], picker: true, value, disabled: Boolean(roster.readOnly), onPick: (_kind, id) => run(assignCategory(actions, kind, item.id, id)) })
}
