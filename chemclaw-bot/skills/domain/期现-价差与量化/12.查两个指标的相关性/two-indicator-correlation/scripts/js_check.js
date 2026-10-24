// 用 Node 在无浏览器环境下跑一遍页面里的统计内核，验证 JS 端与 Python 端结果一致。
const fs = require('fs');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'docs', 'correlation-report.html'), 'utf8');
const m = html.match(/const PAYLOAD = ([\s\S]*?);\r?\nconst S =/);
const PAYLOAD = JSON.parse(m[1]);
const S = PAYLOAD.series, D = PAYLOAD.dates;

// 把页面脚本里的统计函数抽出来（不含 DOM 部分）
const script = html.split('<script>')[1].split('</script>')[0];
const start = script.indexOf('const num = v =>');
const end = script.indexOf('/* ---------------- 状态');
const statsCode = script.slice(start, end).replace(/const PAYLOAD = \{[^}]*\}/, '');
const fn = new Function('PAYLOAD', statsCode + `
  return {pearson,spearman,corrStats,transform,linreg,detrendSeries,partial,winsor,dropExtreme,autocorr,tPval};
`);
const K = fn(PAYLOAD);

function runSample(xk, yk, xf, yf, from, to) {
  const a = D.indexOf(from), b = D.indexOf(to);
  const x = K.transform(S[xk], xf).slice(a, b + 1);
  const y = K.transform(S[yk], yf).slice(a, b + 1);
  const st = K.corrStats(x, y);
  const sp = K.spearman(x, y);
  return { r: st.r, n: st.n, p: st.p, ci_lo: st.ci_lo, ci_hi: st.ci_hi, sp };
}
const cases = [
  ['inventory_total', 'spot_taicang', 'level', 'level'],
  ['inventory_total', 'spot_taicang', 'level', 'pct'],
  ['inventory_total', 'spot_taicang', 'change', 'pct'],
  ['inventory_total', 'spot_taicang', 'change', 'change'],
  ['inventory_ec', 'spot_taicang', 'level', 'level'],
];
const out = {};
for (const c of cases) out[c.join('|')] = runSample(c[0], c[1], c[2], c[3], D[0], D[D.length - 1]);
console.log(JSON.stringify(out, null, 1));
fs.writeFileSync(path.join(__dirname, 'js_results.json'), JSON.stringify(out, null, 1));
