// Rasterize the approved Finder guide at 1x and Retina resolution.
// Icons and labels come from native Finder items; never embed them in the background.
// Run from app/: node scripts/render-dmg-background.mjs
import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = fileURLToPath(import.meta.url)
const root = join(dirname(here), '..')
const svg = readFileSync(join(root, 'build', 'dmg-background.svg'), 'utf8')
const jobs = [
  { width: 540, height: 380, file: 'dmg-background.png' },
  { width: 1080, height: 760, file: 'dmg-background@2x.png' },
]

if (process.versions.electron) {
  const { app, BrowserWindow } = await import('electron')
  app.whenReady().then(async () => {
    const window = new BrowserWindow({ show: false, webPreferences: { sandbox: true, nodeIntegration: false } })
    try {
      await window.loadURL('data:text/html;charset=UTF-8,<!doctype html><title>DMG background</title>')
      const render = async (vector, targets) => {
        const image = new Image()
        image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(vector)
        await image.decode()
        return targets.map(({ width, height }) => {
          const canvas = document.createElement('canvas')
          canvas.width = width
          canvas.height = height
          canvas.getContext('2d').drawImage(image, 0, 0, width, height)
          return canvas.toDataURL('image/png').split(',')[1]
        })
      }
      const code = '(' + render.toString() + ')(' + JSON.stringify(svg) + ',' + JSON.stringify(jobs) + ')'
      const images = await window.webContents.executeJavaScript(code, true)
      for (const [index, job] of jobs.entries()) {
        const png = Buffer.from(images[index], 'base64')
        // Verify generated image sizes so Finder can't accidentally open an oversized window.
        if (png.subarray(1, 4).toString('ascii') !== 'PNG' ||
            png.readUInt32BE(16) !== job.width || png.readUInt32BE(20) !== job.height) {
          throw new Error('Invalid PNG size for ' + job.file)
        }
        writeFileSync(join(root, 'build', job.file), png)
        console.log('DMG: rendered ' + job.file + ' (' + job.width + 'x' + job.height + ')')
      }
    } finally { window.destroy() }
    app.exit(0)
  }).catch(error => { console.error(error); app.exit(1) })
} else {
  // Re-enter the app's pinned Electron process, as scripts/icon.mjs does.
  const electron = createRequire(import.meta.url)('electron')
  const { ELECTRON_RUN_AS_NODE: _unused, ...env } = process.env
  const result = spawnSync(electron, [here], { stdio: 'inherit', env })
  if (result.error) throw result.error
  process.exit(result.status ?? 1)
}
