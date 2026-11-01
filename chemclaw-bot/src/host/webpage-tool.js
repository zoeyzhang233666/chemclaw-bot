import { mkdir, realpath, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'
import { defineTool } from '@deepseek-ai/dsh-tools'

// This is only a file writer. The model authors the complete HTML itself;
// no theme, section, chart, CSS, JSON conversion or fallback is applied.
export function install(rt) {
  rt.ctx.tools.register(defineTool({
    name: 'chem_write_webpage',
    description: 'Save your own complete HTML/CSS/JS webpage without any fixed design template or fallback. Use visual references in Skills only as inspiration. Preview the actual file and fix errors before calling present.',
    parameters: {
      filename: { type: 'string', required: true, description: 'One safe filename ending in .html, e.g. 乙二醇基差研究.html (no directories)' },
      html: { type: 'string', required: true, description: 'The entire model-authored HTML source, with original styles, scripts, charts and layout. Stored unchanged as UTF-8.' },
    },
    output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
    execute: async (args, exec) => {
      if (rt.readOnly()) throw new Error(rt.readOnly())
      if (!rt.selfOf(exec.agent?.id)) throw new Error('Use this tool from a ChemClaw Bot')
      if (typeof args.html !== 'string' || !args.html.trim()) throw new Error('Provide original HTML; there is no template or fallback')
      const name = String(args.filename ?? '')
      if (!name || name.length > 120 || !/\.html$/i.test(name)
        || /[\\/:*?"<>|\x00-\x1f]/.test(name)
        || /[. ]$/.test(name)
        || /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\./i.test(name)) {
        throw new Error('Provide one safe .html filename without a path')
      }
      exec.signal?.throwIfAborted()
      const resolved = await rt.ctx.sessionController.resolveAgent(exec.agent.id)
      const folder = rt.sessionFolder(resolved.agent?.session) ?? rt.teamFolder() ?? rt.defaultTeamFolder()
      const root = await realpath(folder)
      if (await rt.inData(root)) throw new Error('Choose a workspace outside ChemClaw data')
      const output = join(root, `ChemClaw-${Date.now()}-${randomUUID().slice(0, 8)}`)
      await mkdir(output)
      const path = join(output, name)
      await writeFile(path, args.html, { encoding: 'utf8', flag: 'wx' })
      return JSON.stringify({
        files: [{ path, description: 'Original model-authored HTML webpage' }],
        next: 'Inspect this authored page in a real browser and verify data marks, layout and interactions. Then call present. No template or fallback will be generated.',
      })
    },
  }))
}
