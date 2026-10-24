import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import ExcelJS from 'exceljs'
import pptxgen from 'pptxgenjs'
import { Document, Packer, Paragraph, HeadingLevel, Table, TableRow, TableCell } from 'docx'
import { PDFDocument, rgb } from 'pdf-lib'
import fontkit from '@pdf-lib/fontkit'

const require = createRequire(import.meta.url)
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]))
const json = value => JSON.stringify(value).replaceAll('<', '\\u003c').replaceAll('\u2028', '\\u2028')
const tableData = table => [table.columns, ...table.rows].map(row => row.map(value => String(value ?? '')))

export function htmlReport(report) {
  const echarts = readFileSync(require.resolve('echarts/dist/echarts.min.js'), 'utf8').replace(/<\/script/gi, '<\\/script')
  const financial = report.sections?.some(section => section.chart?.engine === 'lightweight')
  const lightweight = financial ? readFileSync(join(dirname(fileURLToPath(import.meta.resolve('lightweight-charts'))), 'lightweight-charts.standalone.production.js'), 'utf8').replace(/<\/script/gi, '<\\/script') : ''
  const libraries = ['echarts', 'zrender', ...(financial ? ['lightweight-charts'] : [])].map(name => { const folder = dirname(require.resolve(name + '/package.json')); const candidates = ['LICENSE', 'LICENSE.txt', 'LICENSE.md']; const file = candidates.map(item => join(folder, item)).find(item => { try { return readFileSync(item).length > 0 } catch { return false } }); return name + '\n' + (file ? readFileSync(file, 'utf8') : 'See package license'); }).join('\n\n');
  const sections = (report.sections ?? []).map((section, i) => `<section><h2>${escape(section.title)}</h2><p>${escape(section.text).replaceAll('\n', '<br>')}</p>${section.chart ? `<div class="chart" id="chart-${i}" role="img" aria-label="${escape(section.title)}"></div>` : ''}${section.table ? `<div class="table-wrap"><table><thead><tr>${section.table.columns.map(column => `<th>${escape(column)}</th>`).join('')}</tr></thead><tbody>${section.table.rows.map(row => `<tr>${row.map(cell => `<td>${escape(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}</section>`).join('')
  return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(report.title)}</title><style>
:root{font-family:"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif;color:#183049;background:#f5f4ef}*{box-sizing:border-box}body{margin:0}main{max-width:1240px;margin:auto;padding:clamp(16px,4vw,52px)}header{border-bottom:3px solid #1677c8;padding:24px 0}h1{font-size:clamp(26px,4vw,40px);line-height:1.35;overflow-wrap:anywhere}h2{font-size:21px;line-height:1.5;overflow-wrap:anywhere}p,li{line-height:1.85;overflow-wrap:anywhere}section{margin:24px 0;padding:24px;background:white;border:1px solid #d9e1e5;border-radius:12px;min-width:0}.chart{width:100%;height:440px;min-width:0}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;line-height:1.6;padding:10px;border-bottom:1px solid #dce4eb;overflow-wrap:anywhere}th{background:#eef5fa}nav{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}button,input{font:inherit;padding:8px 12px;border:1px solid #b9c8d4;border-radius:6px;background:white}a{color:#076dad}footer{font-size:13px}@media(max-width:600px){section{padding:14px}.chart{height:360px}}@media print{body{background:white}main{padding:0;max-width:none}nav{display:none}section{break-inside:avoid;border:0;padding:12px 0}.chart{height:360px}thead{display:table-header-group}tr{break-inside:avoid}h1,h2{break-after:avoid}a{word-break:break-all}}
</style><main><header><small>ChemClaw · ${escape(report.asOf ?? '时间范围待确认')}</small><h1>${escape(report.title)}</h1><p>${escape(report.summary)}</p></header><nav><input id="filter" aria-label="筛选表格" placeholder="筛选表格中的文字"><button onclick="window.print()">打印 / 保存 PDF</button><button id="download">查看 / 导出数据 JSON</button></nav>${sections}<footer><h2>数据来源与限制</h2><ul>${(report.sources ?? []).map(source => `<li>${escape(source.label ?? source)}${source.url && /^https?:\/\//.test(source.url) ? ` · <a href="${escape(source.url)}" target="_blank" rel="noreferrer">来源</a>` : ''} ${escape(source.date ?? '')}</li>`).join('')}</ul><p>${escape(report.limitations ?? '缺失数据明确保留，不构造替代数字；研究结论需结合业务条件复核。')}</p>${financial ? '<p>Financial charts by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView Lightweight Charts™</a>.</p>' : ''}<details><summary>Open-source licenses</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${escape(libraries)}</pre></details></footer></main><script>${echarts}</script>${financial ? `<script>${lightweight}</script>` : ''}<script>
const report=${json(report)};const charts=[];
report.sections?.forEach((section,i)=>{const spec=section.chart;if(!spec)return;const element=document.getElementById('chart-'+i);if(spec.engine==='lightweight'){const chart=LightweightCharts.createChart(element,{autoSize:true,layout:{attributionLogo:true},...spec.options});chart.addSeries(LightweightCharts.LineSeries,spec.seriesOptions??{}).setData(spec.data??[]);chart.timeScale().fitContent();return}const chart=echarts.init(element,null,{renderer:'svg'});if(spec.geoJSON)echarts.registerMap(spec.mapName??'region',spec.geoJSON);chart.setOption({animation:false,tooltip:{trigger:'axis'},legend:{type:'scroll',top:0},grid:{left:70,right:30,top:65,bottom:75,containLabel:true},dataZoom:[{type:'inside'},{type:'slider',bottom:8}],...spec.option});charts.push(chart);new ResizeObserver(()=>chart.resize()).observe(element)});
addEventListener('beforeprint',()=>charts.forEach(chart=>chart.resize()));addEventListener('afterprint',()=>charts.forEach(chart=>chart.resize()));document.getElementById('filter').oninput=event=>document.querySelectorAll('tbody tr').forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(event.target.value.toLowerCase()));document.getElementById('download').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));a.download='chemclaw-report-data.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
</script></html>`
}

export async function deliver(report, output, formats = ['html']) {
  mkdirSync(output, { recursive: true })
  const base = String(report.filename ?? 'ChemClaw-report').replace(/[<>:"/\\|?*\x00-\x1f]/g, '-').slice(0, 100)
  const files = []
  const save = (extension, value) => { const path = join(output, `${base}.${extension}`); writeFileSync(path, value); files.push(path) }
  for (const format of formats) {
    if (format === 'html') save('html', htmlReport(report))
    else if (format === 'xlsx') {
      const book = new ExcelJS.Workbook(); book.creator = 'ChemClaw'
      for (const [i, section] of (report.sections ?? []).entries()) {
        const sheet = book.addWorksheet(`${i + 1}-${section.title ?? 'Analysis'}`.replace(/[\\/*?:\[\]]/g, '-').slice(0, 31))
        sheet.views = [{ state: 'frozen', ySplit: 1 }]
        const data = section.table ? [section.table.columns, ...section.table.rows] : [['内容'], [section.text ?? '']]
        sheet.addRows(data); sheet.getRow(1).font = { bold: true, color: { argb: 'FF126CAC' } }
        sheet.columns.forEach(column => { column.width = 28; column.alignment = { vertical: 'top', wrapText: true } })
        if (section.table) sheet.autoFilter = { from: { row: 1, column: 1 }, to: { row: data.length, column: data[0].length } }
      }
      const sources = book.addWorksheet('数据来源'); sources.addRows([['来源', 'URL', '日期'], ...(report.sources ?? []).map(source => [source.label ?? source, source.url ?? '', source.date ?? ''])]); sources.columns.forEach(column => { column.width = 48 })
      save('xlsx', Buffer.from(await book.xlsx.writeBuffer()))
    } else if (format === 'pptx') {
      const deck = new pptxgen(); deck.layout = 'LAYOUT_WIDE'; deck.author = 'ChemClaw'; deck.title = report.title; deck.lang = 'zh-CN'
      let number = 0
      const page = title => {
        const slide = deck.addSlide(); slide.background = { color: 'F5F4EF' }
        slide.addText(title, { x: 0.6, y: 0.45, w: 12.1, h: 0.9, fontSize: 26, bold: true, color: '126CAC', fontFace: 'Microsoft YaHei', fit: 'shrink' })
        slide.addText(`ChemClaw · ${++number} · ${report.asOf ?? ''}`, { x: 0.6, y: 7.05, w: 12, h: 0.2, fontSize: 10, color: '647789' })
        return slide
      }
      for (const section of [{ title: report.title, text: report.summary }, ...(report.sections ?? [])]) {
        if (section.text || (!section.table && !section.chart)) page(section.title).addText(section.text ?? '', { x: 0.6, y: 1.65, w: 12, h: 4.9, fontSize: 18, color: '183049', fontFace: 'Microsoft YaHei', valign: 'top', fit: 'shrink' })
        if (section.table) {
          const [header, ...rows] = tableData(section.table)
          for (let start = 0; start < Math.max(rows.length, 1); start += 7) page(section.title).addTable([header, ...rows.slice(start, start + 7)], { x: 0.6, y: 1.6, w: 12, fontSize: 12, fontFace: 'Microsoft YaHei', border: { color: 'D9E1E5', pt: 1 }, autoPage: false, margin: 6, rowH: 0.48 })
        }
        if (section.chart) {
          const spec = section.chart
          const series = spec.engine === 'lightweight' ? [{ name: section.title, labels: (spec.data ?? []).map(row => row.time), values: (spec.data ?? []).map(row => row.value) }] : (spec.option?.series ?? []).filter(item => ['line', 'bar'].includes(item.type)).map(item => ({ name: item.name ?? section.title, labels: spec.option.xAxis?.data ?? [], values: item.data }))
          const slide = page(section.title)
          if (series.length) slide.addChart(deck.ChartType.line, series, { x: 0.6, y: 1.6, w: 12, h: 4.9, showLegend: true, showTitle: false, catAxisLabelFontFace: 'Microsoft YaHei', valAxisLabelFontFace: 'Microsoft YaHei', showValue: false })
          else slide.addText('交互图表与地图请查看同名 HTML；此处可补充业务结论。', { x: 0.6, y: 1.6, w: 12, h: 4, fontSize: 20 })
        }
      }
      page('数据来源与限制').addText([...(report.sources ?? []).map(item => `${item.label ?? item} ${item.url ?? ''} ${item.date ?? ''}`), report.limitations ?? ''].join('\n'), { x: 0.6, y: 1.6, w: 12, h: 5, fontSize: 14, fit: 'shrink' })
      save('pptx', await deck.write({ outputType: 'nodebuffer' }))
    } else if (format === 'docx') {
      const children = [new Paragraph({ text: report.title, heading: HeadingLevel.TITLE }), new Paragraph(report.summary ?? '')]
      for (const section of report.sections ?? []) {
        children.push(new Paragraph({ text: section.title, heading: HeadingLevel.HEADING_1 }), new Paragraph(section.text ?? ''))
        if (section.table) children.push(new Table({ rows: tableData(section.table).map(row => new TableRow({ children: row.map(text => new TableCell({ children: [new Paragraph(text)] })) })) }))
      }
      children.push(new Paragraph({ text: '数据来源与限制', heading: HeadingLevel.HEADING_1 }), ...(report.sources ?? []).map(source => new Paragraph(`${source.label ?? source} ${source.url ?? ''} ${source.date ?? ''}`)))
      save('docx', await Packer.toBuffer(new Document({ sections: [{ children }] })))
    } else if (format === 'pdf') {
      const doc = await PDFDocument.create(); doc.registerFontkit(fontkit)
      const font = await doc.embedFont(readFileSync(new URL('./fonts/NotoSansSC-Regular.otf', import.meta.url)), { subset: false })
      let page, y
      const newPage = () => { page = doc.addPage([595, 842]); y = 790 }
      newPage()
      const paragraph = (text, size = 11) => {
        let line = ''
        const flush = () => { if (y < 50) newPage(); page.drawText(line, { x: 40, y, size, font, color: rgb(0.09, 0.19, 0.29) }); y -= size * 1.7; line = '' }
        for (const char of String(text ?? '')) { if (char === '\n') { flush(); continue } if (font.widthOfTextAtSize(line + char, size) > 510) flush(); line += char }
        if (line) flush()
        y -= 8
      }
      paragraph(report.title, 20); paragraph(report.summary)
      for (const section of report.sections ?? []) { paragraph(section.title, 15); paragraph(section.text); if (section.chart) paragraph('交互图表请查看同名 HTML 报告。'); if (section.table) for (const row of tableData(section.table)) paragraph(row.join(' | '), 10) }
      paragraph('数据来源与限制', 15); for (const source of report.sources ?? []) paragraph(`${source.label ?? source} ${source.url ?? ''} ${source.date ?? ''}`, 10)
      save('pdf', Buffer.from(await doc.save()))
    } else throw new Error(`Unsupported format: ${format}`)
  }
  return files
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [input, output, formats = 'html'] = process.argv.slice(2)
  if (!input || !output) throw new Error('Usage: node deliver.mjs report.json output-folder html,xlsx,pptx,docx,pdf')
  const files = await deliver(JSON.parse(readFileSync(input, 'utf8')), resolve(output), formats.split(','))
  console.log(JSON.stringify({ files: files.map(path => ({ path, description: 'ChemClaw research deliverable' })), next: 'Verify files, then call DSH present with these paths.' }, null, 2))
}
