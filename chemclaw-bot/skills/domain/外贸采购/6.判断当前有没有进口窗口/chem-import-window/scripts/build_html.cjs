#!/usr/bin/env node
/**
 * build_html.cjs — 把 case.json + 计算引擎 + ECharts 内联成**单文件离线** HTML
 *
 * 用法：node scripts/build_html.cjs <case.json> <out.html>
 * 特点：不请求任何外部资源、不嵌入任何历史序列以外的数据；所有数字都来自 case.json。
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const CASE_PATH = process.argv[2];
const OUT = process.argv[3];

if (!CASE_PATH || !OUT) {
  console.error('用法: node scripts/build_html.cjs <case.json> <out.html>');
  process.exit(2);
}

const CASE = JSON.parse(fs.readFileSync(CASE_PATH, 'utf8'));

// 内联的 JS 源码绝不能包含 </script（会提前闭合标签，把脚本劈成两半）
function safeJs(src, name) {
  if (/<\/script/i.test(src)) {
    console.error(name + ' 中含有 </script>，会破坏内联，请改写为 <\\/script>');
    process.exit(7);
  }
  return src;
}
const ENGINE = safeJs(fs.readFileSync(path.join(ROOT, 'scripts/lib/import-window-engine.js'), 'utf8'), 'engine');
const ECHARTS = safeJs(fs.readFileSync(path.join(ROOT, 'scripts/assets/echarts.min.js'), 'utf8'), 'echarts');
let TPL = fs.readFileSync(path.join(ROOT, 'scripts/assets/template.html'), 'utf8');

// ---- 校验最小字段，缺失即中止（不生成半成品）
const REQUIRED = ['meta', 'product', 'quote', 'domestic', 'fx', 'tax', 'params'];
REQUIRED.forEach((k) => {
  if (!CASE[k]) { console.error('缺少必需字段: ' + k); process.exit(3); }
});

// ---- 安全内联：JSON 里不能出现 </script>
function jsonForScript(obj) {
  return JSON.stringify(obj)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

const product = CASE.product || {};
const req = CASE.request || {};
const title = CASE.meta.title || (product.name_cn || '商品') + ' 进口窗口';

const repl = {
  __TITLE__: esc(title),
  __PRODUCT__: esc(product.name_cn || CASE.meta.title),
  __PRODUCT_NAME__: JSON.stringify(product.name_cn || '').slice(1, -1),
  __ORIGIN__: JSON.stringify(req.origin || '').slice(1, -1),
  __DEST__: esc(req.destination || '中国'),
  __GENERATED__: esc(CASE.meta.generated_at || ''),
  __VERSION__: esc(CASE.meta.engine_version || '1.0.0'),
  __DISCLAIMER__: esc(CASE.meta.disclaimer || ''),
  __ECHARTS__: ECHARTS,
  __ENGINE__: ENGINE,
  __DATA__: jsonForScript(CASE)
};

let TPL2 = TPL;
// 只检查模板自身的占位符（ECharts 源码里含 ___EC__xxx___ 之类内部标记，不能误判）
const tplPlaceholders = Array.from(new Set(TPL.match(/__[A-Z][A-Z0-9_]*__/g) || []));
const missingKeys = tplPlaceholders.filter((k) => !(k in repl));
if (missingKeys.length) {
  console.error('模板中存在未提供值的占位符: ' + missingKeys.join(', '));
  process.exit(6);
}
Object.keys(repl).forEach((k) => {
  TPL2 = TPL2.split(k).join(repl[k]);          // 只作用于模板
});
const html = TPL2;

// ---- 自检：模板占位符必须全部替换、不得有外部资源引用
const leftovers = tplPlaceholders.filter((k) => html.indexOf(k) >= 0);
if (leftovers.length) {
  console.error('未替换的占位符: ' + leftovers.join(', '));
  process.exit(4);
}
const external = [];
const extRe = /(?:src|href)\s*=\s*["'](https?:)?\/\//gi;
let m;
while ((m = extRe.exec(html))) external.push(m[0]);
if (external.length) {
  console.error('发现外部资源引用: ' + external.slice(0, 5).join(' | '));
  process.exit(5);
}

fs.mkdirSync(path.dirname(path.resolve(OUT)), { recursive: true });
fs.writeFileSync(OUT, html, 'utf8');
const kb = (Buffer.byteLength(html, 'utf8') / 1024).toFixed(0);
console.log('OK  ' + OUT + '  ' + kb + ' KB');
