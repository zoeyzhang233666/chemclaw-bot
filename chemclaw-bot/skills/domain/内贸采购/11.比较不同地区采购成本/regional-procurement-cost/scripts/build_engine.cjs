'use strict';
/**
 * build_engine.cjs —— 生成「浏览器内联版」计算引擎 assets/engine.inline.js
 *
 * 为什么要单独生成：HTML 必须是单文件离线、零外链，
 * 所以把 geo.cjs 的纯计算部分（不含 CityCoords 字典的注释乱码风险除外）原样内联，
 * 并把 module.exports 换成 window.RegionCostEngine。
 *
 * 用法：node scripts/build_engine.cjs
 */
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const src = path.join(root, 'scripts', 'lib', 'geo.cjs');
const out = path.join(root, 'scripts', 'assets', 'engine.inline.js');

let code = fs.readFileSync(src, 'utf8');

// 去掉 module.exports 段，改为挂到 window
code = code.replace(/module\.exports\s*=\s*\{[\s\S]*?\};\s*$/m, '');
const tail = `
/* ---- 浏览器挂载 ---- */
(function (root) {
  const api = {
    R_EARTH, CITY_COORDS, PROVINCES, PROVINCE_CAPITAL,
    haversine, normPlace, resolvePlace, chainDistance,
    routeDistance, solveFreight, calculate, DEFAULTS,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.RegionCostEngine = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
`;

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, `/* 自动生成，请勿手改：源文件 scripts/lib/geo.cjs */\n${code}${tail}`, 'utf8');

// 语法自检
// eslint-disable-next-line no-new-func
new Function(fs.readFileSync(out, 'utf8'));
console.log('engine.inline.js 生成完成：', (fs.statSync(out).size / 1024).toFixed(0), 'KB');
