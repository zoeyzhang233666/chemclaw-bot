// Runs the Host in Electron's Node mode and owns its lifetime.
// Follows DeepSeek Harness apps/desktop/src/host-process.ts (MIT); see NOTICE.
import { spawn } from 'node:child_process'
import { dirname, join } from 'node:path'
import { pathToFileURL } from 'node:url'

const STDERR_TAIL_CHARS = 8 * 1024

// The web server prints its launch URL, and the launch token in it opens the Host.
const redact = (text) => text.replace(/([?&]token=)[^&\s]+/gu, '$1<hidden>')

// The engine's own report of a failure is on the Host's stderr; the error box
// gets its tail with the message so the real cause reaches the user.
export const withLogTail = (message, stderr) => {
  const tail = redact(stderr.trim())
  return tail === '' ? message : `${message}:\n${tail}`
}

// A fatal IPC message may arrive before stderr has flushed. Reuse the
// upstream redaction/formatting while preserving the Host's structured
// diagnostic needed to identify a Playwright frame assertion. Earlier warnings
// on stderr must not hide the cause sent over IPC.
export const withFatalDiagnostic = (message, stderr, diagnostic) => {
  const detail = typeof diagnostic === 'string' ? diagnostic.trim() : ''
  const tail = stderr.trim()
  return withLogTail(message, [tail.slice(-STDERR_TAIL_CHARS), detail && !tail.includes(detail) ? detail.slice(-STDERR_TAIL_CHARS) : ''].filter(Boolean).join('\n'))
}

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
  #startupTimer
  #messageListeners = new Set()

  /**
   * @param {{ entry: string, cwd: string, env: NodeJS.ProcessEnv, pnpm: string, startupTimeoutMs?: number, onFailure: (error: Error) => void }} options
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
      this.#startupTimer = setTimeout(() => {
        this.#fail(new Error(withLogTail('The DSH Host did not become ready within the startup deadline. Restart ChemClaw to try again.', this.#stderr)), reject)
        void this.stop().catch(error => { console.error(error) })
      }, this.#options.startupTimeoutMs ?? 120_000)
      this.#startupTimer.unref?.()
      child.stdout.setEncoding('utf8')
      child.stderr.setEncoding('utf8')
      child.stdout.on('data', (chunk) => { process.stdout.write(redact(chunk)) })
      child.stderr.on('data', (chunk) => {
        process.stderr.write(redact(chunk))
        this.#stderr = (this.#stderr + chunk).slice(-STDERR_TAIL_CHARS)
      })
      child.on('message', (message) => {
        if (this.#failed || this.#stopping) return
        for (const listener of this.#messageListeners) listener(message)
        if (message?.type === 'ready' || message?.type === 'checked') clearTimeout(this.#startupTimer)
        if (message?.type === 'ready') resolve({ url: message.url, injections: message.injections })
        else if (message?.type === 'checked') resolve({ unreadable: message.unreadable })
        else if (message?.type === 'fatal') this.#fail(new Error(withFatalDiagnostic(message.message, this.#stderr, message.diagnostic)), reject)
      })
      child.once('error', (error) => { this.#fail(error, reject) })
      this.#exit = new Promise((done) => {
        child.once('close', (code) => {
          this.#fail(new Error(withLogTail(`The DSH Host stopped (exit ${String(code)})`, this.#stderr)), reject)
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
    clearTimeout(this.#startupTimer)
    if (child.connected) child.send({ type: 'shutdown' }, (error) => { if (error) console.error(error) })
    if (!await settlesWithin(this.#exit, 10_000)) child.kill()
    if (!await settlesWithin(this.#exit, 5_000)) child.kill('SIGKILL')
    this.#child = undefined
  }

  #fail(error, reject) {
    clearTimeout(this.#startupTimer)
    reject(error)
    if (this.#failed || this.#stopping) return
    this.#failed = true
    this.#options.onFailure(error)
  }
}
