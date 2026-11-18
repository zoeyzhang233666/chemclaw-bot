'use strict';
/**
 * calibrate.cjs —— 用真实公路里程标定「途经点折线」算法的曲折系数
 *
 * 用法：node scripts/calibrate.cjs
 *
 * 作用：把「已知真实公里数」的线路，分别用 ×1.00 / 1.05 / 1.10 / 1.15 的系数算一遍，
 *      输出平均偏差与相对 RMSE，据此确认 geo.cjs 里的默认 detour_factor 是否仍然合适。
 * 换地区后如果途经点变稀疏/变密，建议重新跑一次；偏差大时优先调 via_points，而不是乱调系数。
 */
const G = require('./lib/geo.cjs');

// 样本：已知真实公路里程（高速主推方案）的线路，途经点按每 100~200 km 一个枢纽排列
const cases = [
  { name: '潍坊→苏州', via: ['潍坊', '日照', '连云港', '淮安', '常州', '苏州'], known: 760 },
  { name: '淄博→苏州', via: ['淄博', '济宁', '徐州', '淮安', '扬州', '苏州'], known: 744 },
  { name: '济宁→苏州', via: ['济宁', '徐州', '淮安', '扬州', '苏州'], known: 707 },
  { name: '临沂→苏州', via: ['临沂', '徐州', '淮安', '扬州', '苏州'], known: 533 },
  { name: '邢台→苏州', via: ['邢台', '邯郸', '济南', '泰安', '临沂', '淮安', '扬州', '苏州'], known: 999 },
  { name: '石家庄→苏州', via: ['石家庄', '德州', '济南', '泰安', '临沂', '淮安', '扬州', '苏州'], known: 1045 },
  { name: '唐山→苏州', via: ['唐山', '沧州', '德州', '济南', '泰安', '临沂', '淮安', '扬州', '苏州'], known: 1126 },
  { name: '南阳→苏州', via: ['南阳', '信阳', '六安', '合肥', '芜湖', '南京', '苏州'], known: 881 },
  { name: '商丘→苏州', via: ['商丘', '徐州', '南京', '苏州'], known: 665 },
  { name: '连云港→苏州', via: ['连云港', '淮安', '扬州', '苏州'], known: 436 },
  { name: '淮安→苏州', via: ['淮安', '扬州', '苏州'], known: 336 },
];

const factors = [1.0, 1.05, 1.1, 1.15];
const head = ['线路'.padEnd(14), '大圆'.padStart(6), '折线'.padStart(6), '实测'.padStart(6)]
  .concat(factors.map((f) => ('x' + f).padStart(6)));
console.log('真实公路里程 vs 途经点折线算法');
console.log(head.join(' '));
console.log('-'.repeat(head.join(' ').length));

const errs = factors.map(() => []);
for (const c of cases) {
  const ch = G.chainDistance(c.via);
  const row = [c.name.padEnd(14), String(Math.round(ch.straightKm)).padStart(6),
    String(Math.round(ch.viaKm)).padStart(6), String(c.known).padStart(6)];
  factors.forEach((f, i) => {
    const v = ch.viaKm * f;
    errs[i].push(((v - c.known) / c.known) * 100);
    row.push(String(Math.round(v)).padStart(6));
  });
  console.log(row.join(' '));
}

const bias = errs.map((xs) => xs.reduce((s, x) => s + x, 0) / xs.length);
const rmse = errs.map((xs) => Math.sqrt(xs.reduce((s, x) => s + x * x, 0) / xs.length));
const bestIdx = bias.map(Math.abs).indexOf(Math.min(...bias.map(Math.abs)));

console.log('');
factors.forEach((f, i) => {
  console.log(`系数 ${f.toFixed(2)}：平均偏差 ${bias[i] >= 0 ? '+' : ''}${bias[i].toFixed(1)}% ｜ 相对 RMSE ${rmse[i].toFixed(1)}%`
    + (i === bestIdx ? '   <== 最接近无偏' : ''));
});
console.log('');
console.log(`建议 detour_factor = ${factors[bestIdx].toFixed(2)}（geo.cjs 当前默认：${G.DEFAULTS.detourFactor}）`);
console.log('提示：某条线路偏差特别大时，通常是 via_points 漏了关键枢纽城市，调系数治不好。');
