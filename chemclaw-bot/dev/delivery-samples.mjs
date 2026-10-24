import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { deliver } from '../runtime/deliver.mjs'

const output = resolve(process.argv[2] ?? '../chemclaw/verification/deliverables')
const report = {
  title: 'ChemClaw 交付验收：行情、基差与区域分布（模拟数据）', filename: '验收样例 sample',
  summary: '这是界面验收数据，不能用于业务判断。所有价格与区域均为模拟数据。', asOf: '2026-10-22',
  sections: [
    { title: '价格趋势：中文长标题、图例、缩放与打印验收', text: '模拟现货与期货序列；交付时须保留实际规格、地区、税费与来源。',
      table: { columns: ['日期', '现货（模拟）', '期货（模拟）', '基差（模拟）'], rows: [['2026-10-20', 2100, 2050, 50], ['2026-10-21', 2120, 2060, 60], ['2026-10-22', 2130, 2070, 60]] },
      chart: { option: { xAxis: { type: 'category', data: ['10-20', '10-21', '10-22'] }, yAxis: { type: 'value' }, series: [{ name: '现货（模拟）', type: 'line', data: [2100, 2120, 2130] }, { name: '期货（模拟）', type: 'line', data: [2050, 2060, 2070] }] } } },
    { title: '金融时间序列（模拟数据）', chart: { engine: 'lightweight', data: [{ time: '2026-10-20', value: 2050 }, { time: '2026-10-21', value: 2060 }, { time: '2026-10-22', value: 2070 }] } },
    { title: '区域分布：原创示意网格（非行政地图）', text: '虚构区域用于测试离线地图渲染；没有实际企业和坐标，不能用于业务走访。',
      chart: { geoJSON: { type: 'FeatureCollection', features: [
        { type: 'Feature', properties: { name: '示意区域 A' }, geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] } },
        { type: 'Feature', properties: { name: '示意区域 B' }, geometry: { type: 'Polygon', coordinates: [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]] } },
      ] }, mapName: 'demo', option: { tooltip: { trigger: 'item' }, legend: { show: false }, dataZoom: [], visualMap: { min: 0, max: 10, left: 0, bottom: 0 }, series: [{ type: 'map', map: 'demo', roam: true, label: { show: true }, data: [{ name: '示意区域 A', value: 3 }, { name: '示意区域 B', value: 8 }] }] } } },
  ], sources: [{ label: 'ChemClaw 原创模拟验收数据，无业务事实', date: '2026-10-22' }], limitations: '仅用于交付与界面验收。',
}
mkdirSync(output, { recursive: true })
writeFileSync(resolve(output, '../sample-report.json'), JSON.stringify(report, null, 2))
console.log(await deliver(report, output, ['html', 'xlsx', 'pptx', 'docx', 'pdf']))
