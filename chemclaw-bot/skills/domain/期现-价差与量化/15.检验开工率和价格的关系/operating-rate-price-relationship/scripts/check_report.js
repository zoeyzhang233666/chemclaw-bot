const fs = require('fs');
const file = process.argv[2] || 'output/报告.html';
const h = fs.readFileSync(file, 'utf8');
const tag = 'const D=';
const start = h.indexOf(tag) + tag.length;
let depth = 0, inStr = false, esc = false, end = -1;
for (let i = start; i < h.length; i++) {
  const c = h[i];
  if (inStr) {
    if (esc) esc = false;
    else if (c === '\\') esc = true;
    else if (c === '"') inStr = false;
    continue;
  }
  if (c === '"') { inStr = true; continue; }
  if (c === '{' || c === '[') depth++;
  else if (c === '}' || c === ']') { depth--; if (depth === 0) { end = i + 1; break; } }
}
if (end < 0) { console.log('FAIL: payload not closed'); process.exit(1); }
const obj = h.slice(start, end);
let d;
try { d = JSON.parse(obj); } catch (e) { console.log('FAIL parse:', e.message); process.exit(1); }
console.log('payload OK');
console.log('series:', d.series.length, '| n_used:', d.n_used, '| min_n_eff:', d.min_n_eff);
console.log('groups:', Object.keys(d.groups).map(k => k + ':' + d.groups[k].length).join(' '));
console.log('f4:', d.series.map(s => s.f4).join(', '));
const mal = obj.match(/\d-\d{6}/g);
console.log('malformed number tokens:', mal ? mal.length : 0);
// syntax-check the render script
const sTag = '<script>';
const jsStart = h.indexOf(sTag) + sTag.length;
const jsEnd = h.lastIndexOf('</script>');
const body = h.slice(start + obj.length, jsEnd);
try { new Function('D', 'document', 'window', body); console.log('render JS: syntax OK'); }
catch (e) { console.log('render JS issue:', e.message); }
console.log('bytes:', h.length);
