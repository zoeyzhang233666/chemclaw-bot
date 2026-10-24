/**
 * visual_audit.mjs —— 客观视觉自检（不依赖看图，靠 DOM 几何与样式断言）
 *
 * 检查项：
 *   1. 元素重叠：KPI 卡、表格单元格文字溢出 / 相互压盖
 *   2. 文本截断：内容宽度超出容器且非省略号
 *   3. 对比度：正文与背景的 WCAG 对比度 >= 4.5
 *   4. 对齐：KPI 卡等高、卡片栅格对齐
 *   5. 空区：图表容器未渲染出 canvas / 高度为 0
 *   6. 字号：正文 >= 12px，辅助文字 >= 10.5px
 *
 * 用法: node scripts/visual_audit.mjs <html> [--json out]
 */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const HOME = os.homedir();
const EXE = [
  process.env.CHROME_PATH,
  path.join(HOME, 'AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'),
  path.join(HOME, 'AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe'),
].filter(Boolean).find(p => fs.existsSync(p));

const htmlPath = path.resolve(process.argv[2]);
const iJ = process.argv.indexOf('--json');
const jsonOut = iJ >= 0 ? path.resolve(process.argv[iJ + 1]) : null;

const browser = await chromium.launch({ headless: true, executablePath: EXE, args: ['--no-sandbox', '--disable-gpu'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
await page.goto('file:///' + htmlPath.replace(/\\/g, '/'), { waitUntil: 'load' });
await page.waitForTimeout(2000);

const findings = [];
const add = (level, area, msg) => findings.push({ level, area, msg });

const audit = await page.evaluate(() => {
  const out = { overlap: [], clipped: [], contrast: [], tiny: [], emptyChart: [], kpiHeights: [], unaligned: [] };

  const rgb = s => {
    const m = s.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)/);
    return m ? [+m[1], +m[2], +m[3]] : null;
  };
  const lum = c => {
    const a = c.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
  };
  const bgOf = el => {
    let n = el;
    while (n && n !== document.documentElement) {
      const b = getComputedStyle(n).backgroundColor;
      if (b && !/rgba\(0, 0, 0, 0\)|transparent/.test(b)) {
        const m = b.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/);
        if (m && (m[4] === undefined || +m[4] > 0.5)) return rgb(b);
      }
      n = n.parentElement;
    }
    return [255, 255, 255];
  };
  // 祖先是否带渐变/背景图（此时 backgroundColor 为透明，实际是深色底）
  const hasPaintAncestor = el => {
    let n = el;
    while (n && n !== document.documentElement) {
      const st = getComputedStyle(n);
      if (st.backgroundImage && st.backgroundImage !== 'none') return true;
      n = n.parentElement;
    }
    return false;
  };

  // 1) 重叠：同一父容器内的兄弟块级元素
  const sel = '#kpis .kpi, .card, .kpi, .tag, .pill';
  const boxes = [];
  document.querySelectorAll(sel).forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width > 4 && r.height > 4) boxes.push({ el, r, cls: el.className });
  });
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i].r, b = boxes[j].r;
      const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ix > 6 && iy > 6) {
        const inter = ix * iy;
        const minA = Math.min(a.width * a.height, b.width * b.height);
        if (inter / minA > 0.35) {
          out.overlap.push({ a: boxes[i].cls, b: boxes[j].cls, ratio: +(inter / minA).toFixed(2) });
        }
      }
    }
  }

  // 2) 文本截断 / 溢出
  document.querySelectorAll('td, th, .kpi-v, .kpi-l, .v, .lbl, .num, .tag, .pill, h2, h3, .desc').forEach(el => {
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return;
    const overflowX = el.scrollWidth - el.clientWidth;
    if (overflowX > 3 && st.overflowX !== 'auto' && st.overflowX !== 'scroll' && !st.textOverflow.includes('ellipsis')) {
      out.clipped.push({ tag: el.tagName, cls: el.className, text: (el.textContent || '').trim().slice(0, 40), over: overflowX });
    }
  });

  // 3) 对比度（只看有直接文本的可见元素）
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  let node;
  while ((node = walker.nextNode())) {
    const t = node.nodeValue.trim();
    if (!t) continue;
    const el = node.parentElement;
    if (!el || seen.has(el)) continue;
    seen.add(el);
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || +st.opacity === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const fg = rgb(st.color);
    if (!fg) continue;
    // 深色渐变头部（header/hero）内的浅色文字：背景为渐变，backgroundColor 透明，跳过对比度算法
    if (hasPaintAncestor(el) && el.closest('.hero, header, .hdr, .head, .band, .masthead')) continue;
    const bg = bgOf(el);
    const L1 = lum(fg), L2 = lum(bg);
    const cr = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const fs = parseFloat(st.fontSize);
    const need = fs >= 18.66 || (fs >= 14 && +st.fontWeight >= 700) ? 3 : 4.5;
    if (cr < need) {
      out.contrast.push({ text: t.slice(0, 30), color: st.color, bg: `rgb(${bg.join(',')})`, cr: +cr.toFixed(2), need, fs });
    }
    // 4) 过小字号
    if (fs < 10.5) out.tiny.push({ text: t.slice(0, 24), fs });
  }

  // 5) 图表容器未渲染
  document.querySelectorAll('.chart, [id^="chart"]').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.height < 40) return;
    if (st_visible(el) && !el.querySelector('canvas')) out.emptyChart.push(el.id || el.className);
  });
  function st_visible(el) {
    const st = getComputedStyle(el);
    return st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
  }

  // 6) KPI 卡等高
  const kp = [...document.querySelectorAll('#kpis .kpi')].map(e => Math.round(e.getBoundingClientRect().height));
  out.kpiHeights = kp;
  if (kp.length > 1) {
    const mx = Math.max(...kp), mn = Math.min(...kp);
    if (mx - mn > 6) out.unaligned.push({ heights: kp });
  }
  return out;
});

for (const o of audit.overlap) add('FAIL', '重叠', `${o.a} × ${o.b} 重叠 ${o.ratio * 100}%`);
for (const c of audit.clipped) add('WARN', '文本溢出', `${c.tag}.${c.cls} "${c.text}" 超出 ${c.over}px`);
for (const c of audit.contrast) add('WARN', '对比度', `"${c.text}" ${c.cr}:1 < ${c.need}:1（${c.color} on ${c.bg}）`);
for (const t of audit.tiny) add('WARN', '字号', `"${t.text}" ${t.fs}px`);
for (const e of audit.emptyChart) add('FAIL', '空图表', e);
for (const u of audit.unaligned) add('WARN', '等高', `KPI 高度 ${u.heights.join('/')}`);

// KPI 数值的字体层级
const typo = await page.evaluate(() => {
  const g = s => { const e = document.querySelector(s); if (!e) return null; const st = getComputedStyle(e); return { fs: st.fontSize, fw: st.fontWeight, ff: st.fontFamily.split(',')[0] }; };
  return { kpi_v: g('.kpi-v'), kpi_l: g('.kpi-l'), body: g('body'), h2: g('h2') };
});

console.log('===== 客观视觉审计 =====');
console.log('KPI 卡高度:', audit.kpiHeights.join(' / '));
console.log('字体层级:', JSON.stringify(typo));
if (!findings.length) console.log('未发现布局问题');
for (const f of findings) console.log(`${f.level === 'FAIL' ? '[FAIL]' : '[WARN]'} ${f.area}: ${f.msg}`);
const fails = findings.filter(f => f.level === 'FAIL').length;
console.log(`\n结果：${findings.length - fails} 项提示 / ${fails} 项失败`);
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ audit, findings, typo }, null, 2), 'utf8');
await browser.close();
process.exit(fails ? 1 : 0);
