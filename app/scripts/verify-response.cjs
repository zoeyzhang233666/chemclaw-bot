const { app } = require('electron')
// Wait outside ESM evaluation: Electron waits for the entry module before ready.
app.whenReady().then(() => import('../../chemclaw-bot/dev/latency.mjs')).catch(error => {
  console.error(error)
  app.exit(1)
})
