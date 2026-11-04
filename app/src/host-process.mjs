// Runs the Host in Electron's Node mode and owns its lifetime.
// Follows DeepSeek Harness apps/desktop/src/host-process.ts (MIT); see NOTICE.
import { spawn } from 'node:child_process'
import { dirname, join } from 'node:path'
import { pathToFileURL } from 'node:url'

const STDERR_TAIL_CHARS = 8 * 1024

// The web server prints its launch URL, and the launch token in it opens the Host.
const redact = (text) => text.replace(/([?&]token=)[^&\s]+/gu, '$1<hidden>')

const settlesWithin = (promise, ms) => new Promise((resolve) => {
  const timer = setTimeout(() => { resolve(false) }, ms)
  void promise.then(() => { clearTimeout(timer); resolve(true) })
})

export class HostProcess {
  #options
  #child
  #ready
  #exit
  #stderr = ''
  #stopping = false
  #failed = false
  #messageListeners = new Set()

  /**
   * @param {{ entry: string, cwd: string, env: NodeJS.ProcessEnv, pnpm: string, onFailure: (error: Error) => void }} options
   *   `onFailure` receives the first unexpected failure, also after the Host was ready.
   */
  constructor(options) { this.#options = options }

  /**
   * @returns {Promise<{ url: string, injections: unknown[] } | { unreadable: string[] }>} the Host's launch URL
   *   and index injections; for the first-run check, the Sessions it cannot read
   */
  start() {
    this.#ready ??= new Promise((resolve, reject) => {
      const { entry, cwd, env, pnpm } = this.#options
      // Install the Office package-resolution hook before ESM DSH bundles load.
      // Its no-op path leaves profiles without the bundled converter unchanged.
      const preload = join(dirname(entry), 'office-kit-loader.mjs')
      const child = spawn(process.execPath, ['--import', pathToFileURL(preload).href, '--expose-internals', entry, pnpm], {
        cwd, env: { ...env, ELECTRON_RUN_AS_NODE: '1' }, stdio: ['ignore', 'pipe', 'pipe', 'ipc'],
      })
      this.#child = child
      child.stdout.setEncoding('utf8')
      child.stderr.setEncoding('utf8')
      child.stdout.on('data', (chunk) => { process.stdout.write(redact(chunk)) })
      child.stderr.on('data', (chunk) => {
        process.stderr.write(redact(chunk))
        this.#stderr = (this.#stderr + chunk).slice(-STDERR_TAIL_CHARS)
      })
      child.on('message', (message) => {
        for (const listener of this.#messageListeners) listener(message)
        if (message?.type === 'ready') resolve({ url: message.url, injections: message.injections })
        else if (message?.type === 'checked') resolve({ unreadable: message.unreadable })
        else if (message?.type === 'fatal') {
          // The IPC fatal message can arrive before the close event. Preserve the
          // stack for browser-crash detection even when stderr has not flushed.
          const detail = this.#stderr.trim() || (typeof message.diagnostic === 'string' ? message.diagnostic : '')
          const tail = redact(detail.slice(-STDERR_TAIL_CHARS))
          this.#fail(new Error(tail ? `${message.message}\n${tail}` : message.message), reject)
        }
      })
      child.once('error', (error) => { this.#fail(error, reject) })
      this.#exit = new Promise((done) => {
        child.once('close', (code) => {
          const tail = redact(this.#stderr.trim())
          this.#fail(new Error(`The DSH Host stopped (exit ${String(code)})${tail === '' ? '' : `:\n${tail}`}`), reject)
          done()
        })
      })
    })
    return this.#ready
  }

  onMessage(listener) { this.#messageListeners.add(listener); return () => this.#messageListeners.delete(listener) }

  send(message) {
    if (!this.#child?.connected) return false
    this.#child.send(message, () => {})
    return true
  }

  /** Ask the Host to shut down, then end it if it does not exit in time. */
  async stop() {
    const child = this.#child
    if (child === undefined) return
    this.#stopping = true
    if (child.connected) child.send({ type: 'shutdown' }, (error) => { if (error) console.error(error) })
    if (!await settlesWithin(this.#exit, 10_000)) child.kill()
    if (!await settlesWithin(this.#exit, 5_000)) child.kill('SIGKILL')
    this.#child = undefined
  }

  #fail(error, reject) {
    reject(error)
    if (this.#failed || this.#stopping) return
    this.#failed = true
    this.#options.onFailure(error)
  }
}
