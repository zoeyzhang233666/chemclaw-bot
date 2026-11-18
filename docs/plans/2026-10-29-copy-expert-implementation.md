# Copy Expert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a「复制专家」entry under「新建 Bot」in the NewChat plus panel that opens a picker (same shell as group-admin pick) and duplicates the chosen Bot via existing `duplicateBot`.

**Architecture:** Extend `NewChat` with a `copy` boolean state (initialized from `mode === 'copy'`), parallel to `group`. Reuse the option list, search, keyboard, and bottom composer chrome. On pick, call `actions.duplicateBot` then `openSession` — same as the context-menu Duplicate path. No host changes.

**Tech Stack:** ChemClaw plugin client (`chemclaw-bot/src/client`), React `h()`, existing `i18n` dictionary, `npm run build` → `client.js`, Node test runner.

**Spec:** [2026-10-29-copy-expert.md](./2026-10-29-copy-expert.md)

## Global Constraints

- Build on DSH plugin APIs only; never patch DSH.
- English is the source string for `t()`; Chinese goes in `DICTIONARY.zh` in `i18n.js`.
- `client.js` is generated: change `src/client/`, then `npm run build`, commit both.
- Do not change `duplicateBot` host behavior.
- Menu order: Create new Bot → **Copy expert** → Create group chat → Add DSH Agent → bots.
- List all bots including Main Bot; keep bottom message composer visible; copy flow ignores its text.
- Right-side hint while copying: `Copy expert` / 复制专家 (not Make admin).

## File map

| File | Responsibility |
|------|----------------|
| `chemclaw-bot/src/client/i18n.js` | New English keys + Chinese: `Copy expert`, `Choose a Bot to copy…` |
| `chemclaw-bot/src/client/new-chat.js` | `copy` mode, menu entry, hint, duplicate on pick |
| `chemclaw-bot/src/client/palette.js` | Optional command → `openNewChat('copy')` |
| `chemclaw-bot/test/copy-expert-entry.test.js` | Source-contract tests for wiring + i18n keys |
| `chemclaw-bot/client.js` | Regenerated bundle |

---

### Task 1: i18n strings + failing contract test

**Files:**
- Modify: `chemclaw-bot/src/client/i18n.js` (near the New group chats block ~1145)
- Create: `chemclaw-bot/test/copy-expert-entry.test.js`

**Interfaces:**
- Produces: `t('Copy expert')` → zh `复制专家`; `t('Choose a Bot to copy…')` → zh `选择要复制的专家…`

- [ ] **Step 1: Write the failing test**

```js
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { DICTIONARY, installLocale, t } from '../src/client/i18n.js'

const client = name => readFileSync(new URL(`../src/client/${name}`, import.meta.url), 'utf8')

test('Copy expert strings exist in Chinese', () => {
  assert.equal(DICTIONARY.zh['Copy expert'], '复制专家')
  assert.equal(DICTIONARY.zh['Choose a Bot to copy…'], '选择要复制的专家…')
})

test('NewChat offers Copy expert under Create new Bot and duplicates on pick', () => {
  const text = client('new-chat.js')
  assert.match(text, /mode === 'copy'/)
  assert.match(text, /setCopy\(true\)/)
  assert.match(text, /label: t\('Copy expert'\)/)
  assert.match(text, /hint: copying \? t\('Copy expert'\)/)
  assert.match(text, /actions\.duplicateBot\(bot\.id\)/)
  // Order: Create new Bot, then Copy expert, then Create group chat
  const createBot = text.indexOf("label: t('Create new Bot')")
  const copyExpert = text.indexOf("label: t('Copy expert')")
  const createGroup = text.indexOf("label: t('Create group chat')")
  assert.ok(createBot >= 0 && copyExpert > createBot && createGroup > copyExpert)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `chemclaw-bot/`):

```sh
node --test test/copy-expert-entry.test.js
```

Expected: FAIL — missing dictionary keys and/or `new-chat.js` patterns.

- [ ] **Step 3: Add i18n entries**

In `i18n.js`, in the `DICTIONARY.zh` object near the New group chats comments:

```js
  'Copy expert': '复制专家',
  'Choose a Bot to copy…': '选择要复制的专家…',
```

(English keys are the defaults via `t()`; only zh needs dictionary entries. Place them next to `'Make admin'` / `'Choose the group admin'` for discoverability.)

- [ ] **Step 4: Re-run — i18n test should pass; NewChat wiring still fails**

```sh
node --test test/copy-expert-entry.test.js
```

Expected: first test PASS; second FAIL on `new-chat.js` matches.

- [ ] **Step 5: Commit**

```bash
git add chemclaw-bot/src/client/i18n.js chemclaw-bot/test/copy-expert-entry.test.js
git commit -m "$(cat <<'EOF'
Add Copy expert i18n and a failing NewChat contract test.

EOF
)"
```

(On Windows PowerShell, use a here-string or `-m` with two `-m` flags if heredoc is unavailable.)

---

### Task 2: NewChat `copy` mode

**Files:**
- Modify: `chemclaw-bot/src/client/new-chat.js`
- Test: `chemclaw-bot/test/copy-expert-entry.test.js` (from Task 1)

**Interfaces:**
- Consumes: `actions.duplicateBot(id)`, `actions.openSession(id)`, `actions.closeOverlay()`, `t('Copy expert')`, `t('Choose a Bot to copy…')`, `DuplicateIcon`
- Produces: `mode === 'copy'` or in-panel `setCopy(true)` enters picker; picking a bot duplicates and opens the copy

- [ ] **Step 1: Import DuplicateIcon**

Change the icons import:

```js
import { PlusIcon, PeopleIcon, ArrowUpIcon, DuplicateIcon } from './icons.js'
```

- [ ] **Step 2: Add `copy` state**

Next to `group` state:

```js
  const [group, setGroup] = useState(mode === 'group')
  const [copy, setCopy] = useState(mode === 'copy')
```

- [ ] **Step 3: Wire pick / openBot for copy**

Add helper and branch at the start of `openBot` (before `choosingAdmin`):

```js
  const copyBot = bot => run(async () => {
    const next = await actions.duplicateBot(bot.id)
    actions.openSession(next.id)
    close()
  })
  const openBot = bot => run(async () => {
    if (copy) { await copyBot(bot); return }
    if (choosingAdmin) { chooseAdmin(bot); return }
    // ...existing body unchanged
```

Note: `copyBot` already uses `run`; calling it from inside `openBot`'s `run` would nest busy. Prefer:

```js
  const openBot = bot => {
    if (copy) {
      void run(async () => {
        const next = await actions.duplicateBot(bot.id)
        actions.openSession(next.id)
        close()
      })
      return
    }
    void run(async () => {
      if (choosingAdmin) { chooseAdmin(bot); return }
      if (group || picked.length > 0) { pick(bot); return }
      if (bot.hidden) await actions.setFlags(bot.id, { hidden: false })
      if (message.trim()) await actions.send(bot.id, message.trim())
      actions.openSession(bot.id)
      close()
    })
  }
```

- [ ] **Step 4: Initial options — insert Copy expert under Create new Bot**

Replace the options block that currently pushes Create new Bot then Create group chat:

```js
  if (!group && !copy && picked.length === 0 && mode !== 'search' && wanted === '') {
    options.push({ key: 'new', icon: h(PlusIcon), label: t('Create new Bot'), run: createBot })
    options.push({ key: 'copy', icon: h(DuplicateIcon), label: t('Copy expert'), run: () => { setCopy(true); setCursor(0); inputRef.current?.focus() } })
    options.push({ key: 'group', icon: h(PeopleIcon), label: t('Create group chat'), run: () => { setGroup(true); setCursor(0); inputRef.current?.focus() } })
    if ((roster.agents ?? []).length === 0 && actions.addAgent) {
      options.push({ key: 'agent', icon: h(FishLogo, { size: 16 }), label: t('Add DSH Agent'), run: () => run(async () => { await actions.addAgent(); close() }) })
    }
  }
```

- [ ] **Step 5: Bot row hints and create-from-query**

When building bot options:

```js
  const copying = copy
  for (const bot of matches) {
    options.push({
      key: bot.id,
      bot,
      label: bot.name,
      hint: copying ? t('Copy expert')
        : choosingAdmin ? t('Make admin')
        : group || picked.length > 0 ? t('Add to group chat')
        : undefined,
      run: () => openBot(bot),
    })
  }
  if (wanted !== '' && !exact && mode !== 'search' && !copy) {
    options.push({ key: 'create', icon: h(PlusIcon), label: t('Create new Bot “{name}”', { name: query.trim() }), run: createBot })
  }
```

(`!copy` on the create-from-query row avoids offering「新建 Bot」while picking a bot to duplicate.)

- [ ] **Step 6: Placeholder and sendMessage guard**

Search input placeholder — extend the ternary:

```js
placeholder: mode === 'search' ? t('Search Bots…')
  : copy ? t('Choose a Bot to copy…')
  : choosingAdmin ? t('Choose the group admin')
  : group ? t('Who to chat with…')
  : t('Start a chat with…'),
```

In `sendMessage`, no-op when copying (composer stays visible but unused):

```js
  const sendMessage = () => run(async () => {
    if (copy) return
    // ...existing body
  })
```

- [ ] **Step 7: Run contract test**

```sh
node --test test/copy-expert-entry.test.js
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add chemclaw-bot/src/client/new-chat.js chemclaw-bot/test/copy-expert-entry.test.js
git commit -m "$(cat <<'EOF'
Add Copy expert mode to the NewChat plus panel.

EOF
)"
```

---

### Task 3: Command palette entry + rebuild client

**Files:**
- Modify: `chemclaw-bot/src/client/palette.js`
- Modify: `chemclaw-bot/test/copy-expert-entry.test.js` (add palette assertion)
- Modify: `chemclaw-bot/client.js` (generated)

**Interfaces:**
- Consumes: `actions.openNewChat('copy')`, `DuplicateIcon`, `t('Copy expert')`

- [ ] **Step 1: Extend the contract test**

Append:

```js
test('palette can open Copy expert picker', () => {
  const text = client('palette.js')
  assert.match(text, /openNewChat\('copy'\)/)
  assert.match(text, /t\('Copy expert'\)/)
})
```

Run — expect FAIL.

- [ ] **Step 2: Update palette imports and commands**

Import `DuplicateIcon` alongside existing icons. In the `commands` array, after Create Bot:

```js
    { key: 'cmd:bot', icon: h(PlusIcon), title: t('Create Bot'), run: () => actions.openNewChat('create') },
    { key: 'cmd:copy', icon: h(DuplicateIcon), title: t('Copy expert'), run: () => actions.openNewChat('copy') },
    { key: 'cmd:group', icon: h(PeopleIcon), title: t('Create group chat'), run: () => actions.openNewChat('group') },
```

- [ ] **Step 3: Run contract test**

```sh
node --test test/copy-expert-entry.test.js
```

Expected: PASS.

- [ ] **Step 4: Build client bundle**

```sh
npm run build
node scripts/build-client.mjs --check
```

Expected: build succeeds; `--check` clean.

- [ ] **Step 5: Full gate**

```sh
npm test
npm run lint
```

Expected: all pass. (If unrelated dirty workspace files fail tests, run only this feature’s tests plus the standard client stale check that `npm test` includes.)

- [ ] **Step 6: Manual smoke (when a DSH UI is available)**

1. Sidebar `+` → list shows 新建 Bot, **复制专家**, 新建群聊…
2. Click 复制专家 → list of all bots; hover shows **复制专家** on the right
3. Click a bot → new copy opens (same as right-click 复制一份)
4. Escape closes; composer remains visible during copy mode but Enter does not duplicate

- [ ] **Step 7: Commit**

```bash
git add chemclaw-bot/src/client/palette.js chemclaw-bot/src/client/new-chat.js chemclaw-bot/src/client/i18n.js chemclaw-bot/client.js chemclaw-bot/test/copy-expert-entry.test.js
git commit -m "$(cat <<'EOF'
Wire Copy expert through the command palette and rebuild client.js.

EOF
)"
```

---

## Spec coverage checklist

| Spec rule | Task |
|-----------|------|
| Menu under 新建 Bot | Task 2 Step 4 |
| DuplicateIcon | Task 2 Step 1 |
| `mode: 'copy'` / in-panel enter | Task 2 Steps 2–4; Task 3 palette |
| All bots including Main | Task 2 (uses `roster.bots` / `matches` unchanged) |
| Hint 复制专家 | Task 2 Step 5; Task 1 i18n |
| `duplicateBot` + openSession | Task 2 Step 3 |
| Bottom composer kept; unused | Task 2 Step 6 |
| No host change | Global / no host files in plan |
| i18n zh | Task 1 |
| build client.js | Task 3 |

## Self-review notes

- No TBD placeholders in steps.
- `openBot` busy nesting called out explicitly — implement with single `run` as in Step 3.
- Hint variable named `copying` in the test regex (`hint: copying ? t('Copy expert')`) — implementation must use that identifier or update the test to match the final source.
