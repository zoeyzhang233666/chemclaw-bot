import { mkdir, realpath } from 'node:fs/promises'
import { join } from 'node:path'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { randomUUID } from 'node:crypto'
import { normalizeXlsxForPreview } from '../../runtime/normalize-xlsx.mjs'

export function install(rt) {
  rt.ctx.tools.register(defineTool({
    name: 'chem_deliver',
    description: 'Generate self-contained HTML, XLSX, editable PPTX, DOCX or text/table PDF from a report JSON. Runs bundled libraries without shell or Python. Inspect the results, then call present with the returned files. This helper is optional; richer custom layouts are welcome.',
    parameters: { report: { type: 'string', required: true, description: 'JSON: title, summary, asOf, filename, sections[{title,text,table:{columns,rows},chart:{option}}], sources[{label,url,date}], limitations' }, formats: { type: 'string', required: true, description: 'Comma-separated html,xlsx,pptx,docx,pdf' } },
    output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
    execute: async (args, exec) => {
      if (rt.readOnly()) throw new Error(rt.readOnly())
      if (!rt.selfOf(exec.agent?.id)) throw new Error('Use this tool from a ChemClaw Bot')
      const report = JSON.parse(args.report)
      if (!report || typeof report.title !== 'string' || !Array.isArray(report.sections) || report.sections.length > 100) throw new Error('Provide a report title and up to 100 sections')
      const formats = [...new Set(args.formats.split(',').map(value => value.trim()))]
      if (!formats.length || formats.some(value => !['html', 'xlsx', 'pptx', 'docx', 'pdf'].includes(value))) throw new Error('Choose html,xlsx,pptx,docx,pdf')
      exec.signal?.throwIfAborted()
      const resolved = await rt.ctx.sessionController.resolveAgent(exec.agent.id)
      const folder = rt.sessionFolder(resolved.agent?.session) ?? rt.teamFolder() ?? rt.defaultTeamFolder()
      const root = await realpath(folder)
      if (await rt.inData(root)) throw new Error('Choose a workspace outside ChemClaw data')
      const output = join(root, `ChemClaw-${Date.now()}-${randomUUID().slice(0, 8)}`)
      await mkdir(output)
      const { deliver } = await import('../../runtime/deliver.mjs')
      const paths = await deliver(report, output, formats)
      for (const path of paths) {
        if (path.toLowerCase().endsWith('.xlsx')) await normalizeXlsxForPreview(path)
      }
      return JSON.stringify({ files: paths.map(path => ({ path, description: report.title })), next: 'Inspect rendering and calculations, then call present with these files.' })
    },
  }))
}
