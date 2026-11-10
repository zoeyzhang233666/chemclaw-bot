// The Host and its sessions outlive a renderer. Reload only the authenticated
// window, and ask before continuing a repeated crash loop.
export function watchRenderer({ contents, available, reload, ask, report = console.error, now = Date.now }) {
  let broken = false
  let generation = 0
  let pending
  let attempts = []

  const recover = () => {
    if (!broken || !available()) return Promise.resolve()
    if (pending) return pending
    const started = generation
    let again = false
    pending = (async () => {
      attempts = attempts.filter(time => now() - time < 60_000)
      if (attempts.length >= 2) {
        if (!await ask()) return
        if (!available()) return
        attempts = []
      }
      attempts.push(now())
      await reload()
      broken = generation !== started
      again = broken
    })().catch(error => { report(error) }).finally(() => {
      pending = undefined
      if (again && available()) void recover()
    })
    return pending
  }

  contents.on('render-process-gone', (_event, details) => {
    if (!available() || details?.reason === 'clean-exit') return
    broken = true
    generation += 1
    void recover()
  })
  return { recover }
}
