/**
 * js_check.js — 校验生成的 HTML 里的内联 JS 语法与关键结构
 * 用法： node scripts/js_check.js report.html
 *
 * 做三件事：
 *   1) 抽出所有 <script> 内容，逐个做语法检查（new Function）。
 *   2) 检查页面是否引用了任何外部资源（必须为零 —— 要求离线可开）。
 *   3) 检查关键 DOM 锚点是否都在（切换按钮、图表容器）。
 */
const fs = require('fs');

const file = process.argv[2];
if (!file) { console.error('usage: node js_check.js <report.html>'); process.exit(2); }
const html = fs.readFileSync(file, 'utf8');

let fail = 0;
const say = (ok, msg) => { console.log((ok ? '  PASS  ' : '  FAIL  ') + msg); if (!ok) fail++; };

// ---- 1. 抽出 script ----
const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
say(scripts.length >= 2, `内联 script 段数 = ${scripts.length}（期望 ≥ 2：数据段 + 逻辑段）`);

// ---- 2. 语法检查 ----
scripts.forEach((code, i) => {
  // 数据段可能只是 `const DATA = {...};` —— 语法一样能检查
  try {
    new Function(code);
    say(true, `script[${i}] 语法通过（${code.length} 字符）`);
  } catch (e) {
    say(false, `script[${i}] 语法错误: ${e.message}`);
  }
});

// ---- 3. 零外部依赖 ----
const ext = [
  ...[...html.matchAll(/<script[^>]*\bsrc\s*=\s*["']([^"']+)["']/g)].map(m => m[1]),
  ...[...html.matchAll(/<link[^>]*\bhref\s*=\s*["']([^"']+)["']/g)].map(m => m[1]),
  ...[...html.matchAll(/@import\s+url\(\s*["']?([^"')]+)/g)].map(m => m[1]),
  ...[...html.matchAll(/(?:src|href)\s*=\s*["'](https?:\/\/[^"']+)["']/g)].map(m => m[1]),
].filter(u => !u.startsWith('data:') && !u.startsWith('#'));
say(ext.length === 0, `外部资源引用数 = ${ext.length}（必须为 0 才能离线打开）` +
  (ext.length ? ' → ' + ext.slice(0, 5).join(', ') : ''));

// ---- 4. 关键锚点 ----
const anchors = [
  ['#segDir', '方向切换容器'],
  ['data-dir="AB"', 'A/B 按钮'],
  ['data-dir="BA"', 'B/A 按钮'],
  ['#segWin', '窗口切换容器'],
  ['#kpis', '首屏 KPI 区'],
  ['#chartMain', '主曲线容器'],
  ['#chartHist', '分布图容器'],
  ['#chartPrice', '两边价格容器'],
  ['#chartRoll', '滚动分位容器'],
  ['#chartRegime', '结构漂移容器'],
  ['#extremes', '极端阶段容器'],
  ['#conclusion', '结论容器'],
  ['/*__DATA__*/', '数据占位符（应已被替换掉）'],
];
anchors.forEach(([needle, name]) => {
  const found = html.includes(needle);
  if (needle === '/*__DATA__*/') {
    say(!found, `${name} 已替换（未替换会导致页面空白）`);
  } else {
    say(found, `${name} 存在`);
  }
});

// ---- 5. 数据是否已注入 ----
const m = html.match(/const DATA = (\{[\s\S]*?\});\s*\n<\/script>/);
if (m) {
  try {
    const d = JSON.parse(m[1]);
    const okAB = d.AB && d.AB.current && d.AB.current.ratio != null;
    const okBA = d.BA && d.BA.current && d.BA.current.ratio != null;
    say(okAB, `数据注入 AB：当前比价 = ${okAB ? d.AB.current.ratio.toFixed(4) : '缺失'}`);
    say(okBA, `数据注入 BA：当前比价 = ${okBA ? d.BA.current.ratio.toFixed(4) : '缺失'}`);
    if (okAB && okBA) {
      const prod = d.AB.current.ratio * d.BA.current.ratio;
      say(Math.abs(prod - 1) < 1e-9, `方向互逆性：AB × BA = ${prod.toFixed(12)}（应为 1）`);
    }
    const sl = d.AB.series ? d.AB.series.length : 0;
    say(sl > 1000, `AB 序列点数 = ${sl}`);
    const ev = d.events ? d.events.length : 0;
    say(ev > 0, `产业事件条数 = ${ev}`);
  } catch (e) {
    say(false, '数据段不是合法 JSON: ' + e.message);
  }
} else {
  say(false, '未能定位 const DATA = {...} 数据段');
}

// ---- 6. 禁止出现的措辞（红线） ----
// 注意：红线清单本身会以否定形式提到这些词（"不给目标价""不因为…就断定必然回归"），
// 所以要排除掉位于否定语境中的命中，只抓真正的建议性表述。
const banned = [
  '预计回归', '将回归均值', '建议做多', '建议做空', '建议做扩', '建议做缩',
  '目标价', '必然回归', '一定会回归', '稳赚',
];
const NEG = ['不给', '不做', '不说', '不是', '不因', '不把', '不提供', '不得', '不能', '不要', '禁止', '无', '不'];
const realHits = [];
banned.forEach(w => {
  let idx = 0;
  while ((idx = html.indexOf(w, idx)) !== -1) {
    const before = html.slice(Math.max(0, idx - 14), idx);
    if (!NEG.some(n => before.includes(n))) realHits.push(w + ' @' + idx);
    idx += w.length;
  }
});
say(realHits.length === 0, `红线措辞扫描：命中 ${realHits.length} 个` +
  (realHits.length ? ' → ' + realHits.slice(0, 6).join('、') : '（否定式说明不计）'));

console.log(fail === 0 ? '\nJS CHECK: ALL PASS' : `\nJS CHECK: ${fail} FAILED`);
process.exit(fail === 0 ? 0 : 4);
