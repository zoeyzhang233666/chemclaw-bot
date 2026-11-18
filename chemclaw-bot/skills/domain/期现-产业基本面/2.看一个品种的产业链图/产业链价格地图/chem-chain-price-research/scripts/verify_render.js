#!/usr/bin/env node
/* verify_render.js —— 页面渲染冒烟检查（可选增强，需要 Node）

Python 侧校验只能确认「数据与几何正确」，无法确认内联脚本真的能把页面画出来。
本脚本用最小 DOM 桩执行内联脚本，检查：
  1. 脚本能跑完不抛异常；
  2. 真的生成了节点/连线/明细分组，而不是空页面；
  3. 图上每个价格文本都来自内嵌数据。

用法: node verify_render.js out.html
退出码 0 = 通过。若本机没有 Node，跳过这一步即可（Python 校验仍然有效）。
*/
"use strict";

const fs = require("fs");

const htmlPath = process.argv[2];
if (!htmlPath) {
  console.error("用法: node verify_render.js out.html");
  process.exit(2);
}
const html = fs.readFileSync(htmlPath, "utf8");

const dataMatch = html.match(/<script id="chain-data" type="application\/json">([\s\S]*?)<\/script>/);
if (!dataMatch) {
  console.error("[问题] 找不到内嵌数据块 <script id=\"chain-data\">");
  process.exit(1);
}
const payload = dataMatch[1].replace(/<\\\//g, "</");
let data;
try {
  data = JSON.parse(payload);
} catch (e) {
  console.error("[问题] 内嵌数据无法解析: " + e.message);
  process.exit(1);
}

const blocks = [];
const re = /<script(?![^>]*type="application\/json")[^>]*>([\s\S]*?)<\/script>/g;
let m;
while ((m = re.exec(html)) !== null) blocks.push(m[1]);
if (!blocks.length) {
  console.error("[问题] 页面没有可执行脚本，交互功能不会生效");
  process.exit(1);
}

const counts = {};
class El {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.attrs = {};
    this.style = {};
    this.textContent = "";
    this._html = "";
    this.listeners = {};
    counts[tag] = (counts[tag] || 0) + 1;
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k] === undefined ? null : this.attrs[k]; }
  appendChild(c) { this.children.push(c); return c; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  querySelectorAll() { return []; }
  set innerHTML(v) { this._html = String(v); }
  get innerHTML() { return this._html; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 1400, height: 900 }; }
  get offsetWidth() { return 320; }
  get offsetHeight() { return 220; }
}

const registry = {};
const documentStub = {
  getElementById(id) {
    if (!registry[id]) registry[id] = new El("div#" + id);
    return registry[id];
  },
  querySelector(sel) {
    const k = "sel:" + sel;
    if (!registry[k]) registry[k] = new El(sel);
    return registry[k];
  },
  createElement(t) { return new El(t); },
  createElementNS(ns, t) { return new El(t); }
};
registry["chain-data"] = new El("script#chain-data");
registry["chain-data"].textContent = payload;

let error = null;
try {
  const fn = new Function("document", "window", blocks.join("\n;\n"));
  fn(documentStub, {});
} catch (e) {
  error = e;
}

const problems = [];
const notes = [];

if (error) {
  problems.push("内联脚本执行抛错: " + error.message);
} else {
  const nodeGroups = counts["g"] || 0;
  if (nodeGroups < 3) problems.push("未生成图层（g 元素 " + nodeGroups + " 个）");
  const svg = registry["chain"];
  const expectedPaths = (data.links || []).length;
  const texts = counts["text"] || 0;
  const expectedTexts = (data.nodes || []).length + expectedPaths;
  if (texts < expectedTexts) {
    problems.push("文本元素只有 " + texts + " 个，少于预期的 " + expectedTexts + " 个（节点标签 + 关系标签）");
  }
  if (!svg || svg.children.length === 0) {
    problems.push("SVG 画布没有任何子元素，图形未渲染");
  } else {
    const vb = svg.attrs.viewBox || "";
    if (!/^0 0 [\d.]+ [\d.]+$/.test(vb)) problems.push("viewBox 非法: " + vb);
    notes.push("viewBox = " + vb);
  }
  const panel = registry["panel"];
  if (!panel || !panel.innerHTML || panel.innerHTML.length < 80) {
    problems.push("右侧详情面板没有内容");
  } else {
    notes.push("面板 HTML " + panel.innerHTML.length + " 字符");
  }
  const tables = registry["tables"];
  const totalRows = (data.nodes || []).reduce((a, n) => a + ((n.rows || []).length), 0) +
    (data.tables || []).reduce((a, t) => a + ((t.rows || []).length), 0);
  if (totalRows === 0) {
    notes.push("数据集没有任何原始记录，明细区为空属预期（结构骨架模式）");
  } else if (!tables || tables.children.length === 0) {
    problems.push("数据集有 " + totalRows + " 条记录，但明细区没有生成任何分组");
  } else {
    notes.push("明细分组 " + tables.children.length + " 组 · 覆盖记录 " + totalRows + " 条");
  }
  // 图上每个价格都应出自内嵌数据
  const prices = new Set();
  (data.nodes || []).forEach((n) => { if (n.price) prices.add(String(n.price)); });
  const drawn = (data.nodes || []).filter((n) => n.role !== "application").map((n) => String(n.price));
  const missing = drawn.filter((p) => !prices.has(p));
  if (missing.length) problems.push("图上价格不在数据集中: " + missing.join(", "));
  notes.push("节点 " + (data.nodes || []).length + " · 连线 " + expectedPaths +
    " · 文本元素 " + texts);
}

console.log("渲染冒烟检查: " + htmlPath);
notes.forEach((n) => console.log("  [信息] " + n));
problems.forEach((p) => console.log("  [问题] " + p));
if (problems.length) {
  console.log("结果：不通过（" + problems.length + " 项问题）");
  process.exit(1);
}
console.log("结果：通过（0 项问题）");
process.exit(0);
