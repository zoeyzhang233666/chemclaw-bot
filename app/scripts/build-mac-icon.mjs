// Render the macOS-only warm-paper icon from SVG at build time.
// This leaves the existing Windows .ico and cross-platform icon.png untouched.
import { spawnSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptPath = fileURLToPath(import.meta.url)
const assets = join(dirname(scriptPath), '..', 'assets')
const source = join(assets, 'icon-mac.svg')
const destination = join(assets, 'icon-mac.png')

if (process.versions.electron) {
  const { app, BrowserWindow } = await import('electron')
  app.whenReady().then(async () => {
    const page = new BrowserWindow({ show: false })
    try {
      await page.loadURL('data:text/html,<!doctype html><title>ChemClaw Mac icon</title>')
      const svg = readFileSync(source, 'utf8')
      const draw = async (sourceSvg) => {
        const image = new Image()
        image.src = 'data:image/svg+xml,' + encodeURIComponent(sourceSvg)
        await image.decode()
        const canvas = document.createElement('canvas')
        canvas.width = 1024
        canvas.height = 1024
        canvas.getContext('2d').drawImage(image, 0, 0, 1024, 1024)
        return canvas.toDataURL('image/png').split(',')[1]
      }
      const data = await page.webContents.executeJavaScript('(' + draw.toString() + ')(' + JSON.stringify(svg) + ')')
      writeFileSync(destination, Buffer.from(data, 'base64'))
      console.log('mac icon: wrote assets/icon-mac.png (1024x1024)')
    } finally {
      page.destroy()
    }
  }).then(() => app.exit(0)).catch((error) => {
    console.error(error)
    app.exit(1)
  })
} else if (process.platform === 'darwin') {
  const { ELECTRON_RUN_AS_NODE: _runAsNode, ...env } = process.env
  const electron = createRequire(import.meta.url)('electron')
  const result = spawnSync(electron, [scriptPath], { stdio: 'inherit', env, timeout: 60_000 })
  if (result.error) console.error(result.error)
  if (result.status !== 0) process.exit(result.status ?? 1)
} else {
  // Windows and Linux keep their existing icon resources; do not spawn Electron.
  console.log('mac icon: skipped on ' + process.platform)
}
