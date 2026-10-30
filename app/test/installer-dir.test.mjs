import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const script = readFileSync(new URL('../build/installer.nsh', import.meta.url), 'utf8')

// Static checks: Windows NSIS compilation and an actual read-only install path
// still need to be verified on the Windows packaging job and a real machine.
test('Windows installer checks the destination before installation without elevation', () => {
  assert.match(script, /!macro customInstallMode[\s\S]*?\$isForceCurrentInstall "1"/)
  assert.match(script, /!macro customPageAfterChangeDir/)
  assert.match(script, /!ifdef allowToChangeInstallationDirectory/)
  assert.match(script, /\$\{if\} \$\{isUpdated\}[\s\S]*?Abort/)
  assert.match(script, /GetTempFileName \$R2 "\$chemCheckTarget"/)
  assert.match(script, /Delete "\$R2"/)
  assert.match(script, /MessageBox MB_OK\|MB_ICONEXCLAMATION/)
  assert.match(script, /SendMessage \$HWNDPARENT 0x408 -1 0/)
  assert.match(script, /LangString chemInstDirNotWritable \$\{LANG_SIMPCHINESE\}/)
  assert.match(script, /LangString chemInstDirNotWritable \$\{LANG_ENGLISH\}/)
})
