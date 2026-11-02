// A clean-installed ChemClaw must create and inspect real Word/PPT/Excel files
// using the shipped interpreters and the shipped compiled Office CLI.
// Never invoke "node", "python", pip or npm from PATH.
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const PYTHON_CREATE = String.raw`from pathlib import Path
import sys, json
from docx import Document
from pptx import Presentation
from pptx.util import Inches
from openpyxl import Workbook, load_workbook

root = Path(sys.argv[1])
document = Document()
document.add_heading("ChemClaw 甲醇市场简报", 0)
document.add_paragraph("Sample data only, not live prices")
table = document.add_table(rows=2, cols=2)
table.cell(0, 0).text = "产品"
table.cell(0, 1).text = "价格"
table.cell(1, 0).text = "甲醇"
table.cell(1, 1).text = "2400"
document.save(root / "test.docx")

presentation = Presentation()
for label in ["封面", "市场数据", "结论"]:
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    shape = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1))
    shape.text = label
presentation.save(root / "test.pptx")

workbook = Workbook()
sheet = workbook.active
sheet["A2"], sheet["B2"] = "甲醇", 2400
sheet["A3"], sheet["B3"] = "乙二醇", 4500
sheet["A4"], sheet["B4"] = "合计", "=SUM(B2:B3)"
workbook.save(root / "test.xlsx")
reopened = load_workbook(root / "test.xlsx")
assert reopened.active["B4"].value == "=SUM(B2:B3)"
print(json.dumps({"docx": True, "pptxSlides": len(presentation.slides), "excelFormula": reopened.active["B4"].value}))
`

function paths(resources, platform) {
  const base = join(resources, 'primary-runtime', 'dependencies')
  return {
    node: join(base, 'node', 'bin', platform === 'win32' ? 'node.exe' : 'node'),
    python: join(base, 'python', ...(platform === 'win32' ? ['python.exe'] : ['bin', 'python3'])),
    cli: join(resources, 'app.asar.unpacked', 'node_modules', 'chemclaw-bot', 'office.js'),
    converter: join(resources, 'office-converter', 'node_modules', '@deepseek-ai', 'libreoffice-kit', 'lib', 'cli.js'),
  }
}

export function checkOfficeFiles(resources, {
  platform = process.platform,
  run = spawnSync,
  makeTemp = () => mkdtempSync(join(tmpdir(), 'chemclaw-installed-office-')),
  cleanup = root => rmSync(root, { recursive: true, force: true }),
} = {}) {
  const { node, python, cli, converter } = paths(resources, platform)
  for (const file of [node, python, cli, converter]) {
    if (!existsSync(file)) throw new Error('Installed Office payload missing ' + file)
  }
  const work = makeTemp()
  try {
    const cmd = (exe, args) => {
      const response = run(exe, args, { encoding: 'utf8', windowsHide: true, timeout: 120_000,
        env: { ...process.env, PYTHONPATH: '', PYTHONHOME: '', PYTHONNOUSERSITE: '1' } })
      if (response.error || response.status !== 0) {
        throw new Error('Installed Office command failed: ' + exe + ' ' + args.slice(0, 3).join(' ') +
          '; stderr: ' + String(response.stderr || response.error?.message || response.stdout).slice(0, 1400))
      }
      return String(response.stdout || '')
    }
    const created = JSON.parse(cmd(python, ['-I', '-B', '-c', PYTHON_CREATE, work]).trim())
    assert.equal(created.pptxSlides, 3)
    assert.equal(created.excelFormula, '=SUM(B2:B3)')
    const inspect = (format, action, file) => {
      const result = JSON.parse(cmd(node, [cli, format, action, join(work, file), '--json']))
      assert.equal(result.ok, true, format + ' ' + action + ': ' + JSON.stringify(result))
      return result.data
    }
    inspect('docx', 'read', 'test.docx')
    inspect('pptx', 'inventory', 'test.pptx')
    const excel = inspect('xlsx', 'inventory', 'test.xlsx')
    assert.equal(excel.sheets?.[0]?.formulas, 1)
    // Exercise the exact standalone CLI used by Office skills and the right
    // sidebar conversion chain. A working Python and Office inventory alone
    // cannot prove libreoffice-kit's JS packages and native engine are shipped.
    cmd(node, [converter, 'convert', '--input', join(work, 'test.pptx'), '--output', join(work, 'preview.pdf')])
    const pdf = readFileSync(join(work, 'preview.pdf'))
    assert.ok(pdf.length > 1000 && pdf.subarray(0, 5).toString() === '%PDF-', 'Bundled Office converter did not render a real PDF')
    // The sidebar invokes the Host's JS API, not the standalone CLI. Run that
    // same API from the packaged Electron Node executable, rooted in app.asar.
    // A missing JS dependency or worker failure must block the installer even
    // when the independently staged CLI succeeds.
    if (platform === 'win32') {
      const electron = join(dirname(resources), 'ChemClaw.exe')
      const program = String.raw`const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
(async () => {
  const app = createRequire(path.join(process.argv[1], 'package.json'));
  const kit = await import(pathToFileURL(app.resolve('@deepseek-ai/libreoffice-kit')).href);
  const converter = await kit.createConverter();
  try {
    await converter.render({ inputPath: process.argv[2], outputPath: process.argv[3] });
    console.log('PACKED_HOST_OFFICE_OK ' + converter.backend);
  } finally { await converter.dispose(); }
})().catch(e => { console.error('PACKED_HOST_OFFICE_FAILED', e.stack || e, e.cause); process.exitCode = 1 })`
      const embedded = run(electron, ['-e', program, join(resources, 'app.asar'), join(work, 'test.pptx'), join(work, 'host-preview.pdf')], {
        encoding: 'utf8', windowsHide: true, timeout: 120_000,
        env: { ...process.env, ELECTRON_RUN_AS_NODE: '1', PYTHONPATH: '', PYTHONHOME: '', NODE_PATH: '' },
      })
      if (embedded.error || embedded.status !== 0) {
        throw new Error('Packaged Electron Host Office converter failed: ' +
          String(embedded.stderr || embedded.stdout || embedded.error?.message).slice(0, 5000))
      }
      const hostPdf = readFileSync(join(work, 'host-preview.pdf'))
      assert.ok(hostPdf.length > 1000 && hostPdf.subarray(0, 5).toString() === '%PDF-', 'The packaged Host did not render a PDF')
      console.log(String(embedded.stdout).trim())
    }
    for (const file of ['test.docx', 'test.pptx', 'test.xlsx']) {
      const result = JSON.parse(cmd(node, [cli, 'check', join(work, file), '--json']))
      assert.equal(result.ok, true, 'OOXML check ' + file + ': ' + JSON.stringify(result))
      assert.deepEqual(result.data.findings, [], 'OOXML findings in ' + file)
    }
    console.log('office-e2e: bundled Node/Python/Office CLI created and validated DOCX/PPTX/XLSX; standalone LibreOffice Kit converted a PPTX into a real PDF')
    return { ok: true, paths: { node, python, cli }, files: 3 }
  } finally { cleanup(work) }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const resources = process.argv[2]
  if (!resources) throw new Error('Usage: node scripts/check-office-e2e.mjs <installed resources directory>')
  checkOfficeFiles(resolve(resources))
}
