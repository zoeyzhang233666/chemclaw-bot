'use strict';
/**
 * build_html.cjs —— 生成单文件、离线、零外链的交互式 HTML 报告
 *
 * 用法：
 *   node scripts/build_html.cjs <案例目录>        # 例：examples/01-soda-ash-su-zhou
 *   node scripts/build_html.cjs <案例目录> --out dist/x.html
 *
 * 依赖：scripts/assets/template.html、scripts/assets/engine.inline.js（先跑 build_engine.cjs）、
 *      scripts/assets/echarts.min.js
 */
const fs = require('fs');
const path = require('path');
const { buildModel } = require('./lib/model.cjs');

const root = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
const caseDir = args[0] ? path.resolve(args[0]) : path.join(root, 'examples', '01-soda-ash-su-zhou');
const outIdx = args.indexOf('--out');
const outFile = outIdx >= 0 ? path.resolve(args[outIdx + 1]) : path.join(caseDir, 'output', 'index.html');

function read(p) {
  if (!fs.existsSync(p)) throw new Error('缺少文件：' + p);
  return fs.readFileSync(p, 'utf8');
}

const tpl = read(path.join(root, 'scripts', 'assets', 'template.html'));
const engine = read(path.join(root, 'scripts', 'assets', 'engine.inline.js'));
const echarts = read(path.join(root, 'scripts', 'assets', 'echarts.min.js'));

const researchPath = path.join(caseDir, 'data', 'research.json');
const doc = JSON.parse(read(researchPath));
const model = buildModel(doc, {});

// ---- 标题 ----
const prod = (doc.request && doc.request.product) || (doc.product && doc.product.name) || '产品';
const regions = (doc.regions || []).map((r) => r.name).join('、');
const dest = (doc.request && doc.request.receipt_address) || (doc.destination && doc.destination.city) || '';
const title = `${prod} · 区域采购成本比较（${regions} → ${dest}）`;

// ---- 安全嵌入 JSON（防止 </script> 提前闭合） ----
function jsonForScript(obj) {
  return JSON.stringify(obj)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}

// ---- 安全嵌入 JS（防止 </script>） ----
function jsForInline(code) {
  return code.replace(/<\/script/gi, '<\\/script');
}

let html = tpl
  .replace('__TITLE__', title.replace(/</g, '&lt;'))
  .replace('__MODEL_JSON__', jsonForScript(model))
  .replace('__ENGINE_JS__', jsForInline(engine))
  .replace('__ECHARTS_JS__', jsForInline(echarts));

// 模板里 __TITLE__ 出现两次（<title> 和 h1），全部替换
html = html.split('__TITLE__').join(title.replace(/</g, '&lt;'));

fs.mkdirSync(path.dirname(outFile), { recursive: true });
fs.writeFileSync(outFile, html, 'utf8');

const kb = (fs.statSync(outFile).size / 1024).toFixed(0);
console.log(`[build_html] ${path.relative(root, outFile)}  ${kb} KB`);
console.log(`[build_html] 区域 ${model.regions.length} 个 / 线路 ${model.routes.length} 条 / 缺口 ${(model.gaps || []).length} 项 / 历史 ${model.history.available ? '有' : '无'}`);
