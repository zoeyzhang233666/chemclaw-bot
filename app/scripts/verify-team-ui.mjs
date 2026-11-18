import assert from 'node:assert/strict'
import { app } from 'electron'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { setTimeout as delay } from 'node:timers/promises'

if (!process.env.DS_BOT_HOME?.includes('.dsh-test-') || !process.env.DS_BOT_SHELL_DATA?.includes('.dsh-test-')) throw new Error('Use an isolated .dsh-test- home')
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
app.setAppPath(resolve(root, 'app'))
const out = resolve(root, 'chemclaw/verification')
mkdirSync(out, { recursive: true })
let checked = false
let exitCode = 0
app.once('will-quit', () => app.exit(exitCode))
const timeout = setTimeout(() => { console.error('Team UI verification timed out'); exitCode = 1; app.quit() }, 120_000)
app.on('browser-window-created', (_event, window) => {
  window.webContents.on('did-finish-load', async () => {
    if (checked || !/^http:\/\/127\.0\.0\.1:\d+\//u.test(window.webContents.getURL())) return
    checked = true
    const run = expression => window.webContents.executeJavaScript(expression, true)
    const waitFor = async expression => {
      const deadline = Date.now() + 40_000
      while (Date.now() < deadline) { if (await run(expression)) return; await delay(300) }
      throw new Error(`UI condition timed out: ${expression}`)
    }
    const shot = async name => { await delay(650); writeFileSync(resolve(out, `team-${name}.png`), (await window.webContents.capturePage()).toPNG()) }
    try {
      await waitFor(`document.querySelectorAll('[data-room-id]').length === 15 && document.querySelectorAll('[data-bot-id]').length === 50`)
      // This keyless test profile may show the host's optional model sign-in dialog.
      await delay(1200)
      window.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Escape' })
      window.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Escape' })
      await delay(250)
      const state = await run(`fetch('api/bot',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({endpoint:'state'})}).then(r=>r.json()).then(r=>({bots:r.value.bots.length,rooms:r.value.rooms.length,icons:new Set([...r.value.bots,...r.value.rooms].map(i=>i.avatar.shape+':'+i.color)).size}))`)
      assert.deepEqual(state, { bots: 50, rooms: 15, icons: 65 })
      assert.ok(window.isVisible())
      await shot('home')
      await run(`document.querySelector('.bt-side>button').click()`)
      await waitFor(`document.querySelectorAll('.bt-expert-card').length===50`)
      assert.equal(await run(`document.querySelector('.bt-settings').textContent.includes('启用并打开')`), false)
      await shot('bots')
      await run(`Array.from(document.querySelectorAll('.bt-catalog-categories button')).find(b=>b.textContent==='内贸采购').click()`)
      await waitFor(`document.querySelectorAll('.bt-expert-card').length===6`)
      await run(`document.querySelectorAll('.bt-settings-item')[3].click()`)
      await waitFor(`document.querySelectorAll('.bt-expert-card').length===15`)
      await shot('groups')
      await run(`document.querySelector('.bt-settings-close').click()`)
      await delay(250)
      await run(`Array.from(document.querySelectorAll('[data-room-id]')).find(b=>b.textContent.includes('期现价差研究群')).click()`)
      await waitFor(`document.querySelector('.bt-pill-name')?.textContent==='期现价差研究群'`)
      await run(`document.querySelector('.bt-pill').click()`)
      await waitFor(`!!document.querySelector('.bt-panel:not([data-leaving])')`)
      await shot('details')
      await run(`document.querySelector('[data-bt-right-sidebar]').click()`)
      await waitFor(`!document.querySelector('.bt-panel')`)
      await shot('workspace')
      const chatWidth = await run(`document.querySelector('[class*="_centerCol"]').getBoundingClientRect().width`)
      assert.ok(chatWidth >= 420, `chat collapsed to ${chatWidth}px`)
      await run(`document.querySelector('.bt-pill').click()`)
      await waitFor(`!!document.querySelector('.bt-panel:not([data-leaving])')`)
      await delay(650)
      const restored = await run(`document.querySelector('[class*="_centerCol"]').getBoundingClientRect().width`)
      assert.ok(restored >= 420, `chat did not recover: ${restored}px`)
      window.setSize(720, 860)
      await delay(900)
      const narrow = await run(`({width:document.querySelector('[class*="_centerCol"]').getBoundingClientRect().width, overflow:document.documentElement.scrollWidth>innerWidth, viewport:innerWidth, columns:Array.from(document.querySelectorAll('[class*="_centerCol"]')).map(e=>({left:e.getBoundingClientRect().left,width:e.getBoundingClientRect().width,margin:getComputedStyle(e).marginRight,inline:e.style.cssText}))})`)
      console.log('Narrow layout:', JSON.stringify(narrow))
      assert.ok(narrow.width >= 400, `narrow chat collapsed to ${narrow.width}px`)
      assert.equal(narrow.overflow, false)
      await shot('narrow')
      console.log('Team UI passed: 50 Bots, 15 groups, 65 distinct avatars, category filter, panel switching and narrow layout')
    } catch (error) {
      console.error(error)
      await shot('failure').catch(() => {})
      exitCode = 1
    } finally { clearTimeout(timeout); app.quit() }
  })
})
await import('../src/main.mjs')
