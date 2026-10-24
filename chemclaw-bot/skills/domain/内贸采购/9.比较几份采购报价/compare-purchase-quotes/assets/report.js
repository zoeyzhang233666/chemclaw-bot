/* ================= 采购报价比较 · 交互逻辑 ================= */
(function () {
"use strict";
const P = window.PAYLOAD;
const SUP = ["A", "B", "C"];
const COLOR = { A: "#3b7dd8", B: "#0f8f6b", C: "#c2772b" };
const NAME = { A: "华东石化工业品", B: "恒源新材料供应链", C: "苏南化工贸易" };
const FULL = { A: P.std.A.name, B: P.std.B.name, C: P.std.C.name };

/* ---------- 工具 ---------- */
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const n2 = (x) => (x === null || x === undefined || isNaN(x)) ? "—" : Number(x).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const n0 = (x) => (x === null || x === undefined || isNaN(x)) ? "—" : Math.round(Number(x)).toLocaleString("zh-CN");
const pct = (x, d = 2) => (x === null || isNaN(x)) ? "—" : (100 * x).toFixed(d) + "%";
const esc = (s) => String(s === null || s === undefined ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 2200); }

/* ---------- 状态（L3 用户输入） ---------- */
const BASE = {
  qty: 200, rate: 0.045, freight: 42, unload: 25, insp: 1800, veh: 600,
  acceptC: false, sellerDelivers: false,
  annualVol: 2400, inspBatches: 6, vehTrips: 8, yearDays: 360,
  depositDays: 180, packRefundDays: 10, packUnret: 0.10,
  freightTax: 0.09, svcTax: 0.06, vat: 0.13
};
let S = Object.assign({}, BASE);

/* ---------- 计算引擎（与 Python engine.py 公式一一对应） ---------- */
const STD = {
  A: { purity: 0.9992, costBasis: "excl", freightBy: "buyer", tierLo: 110, price: 6.20, priceHi: 6.17, unitKg: 1000, days: 21.0 },
  B: { purity: 0.9990, costBasis: "excl", freightBy: "buyer", tierLo: 120, price: 4850, priceHi: 4800, days: 46.0 },
  C: { purity: 0.9950, costBasis: "full", freightBy: "seller", tierLo: 0, price: 6300, barrelKg: 220, days: 0.0 }
};
function goodsOf(code, s) {
  const d = STD[code];
  if (code === "A") {
    const p = s.qty >= d.tierLo ? d.priceHi : d.price;
    const incl = p * d.unitKg;
    return { tier: p, incl, basis: incl / (1 + s.vat) };
  }
  if (code === "B") {
    const p = s.qty >= d.tierLo ? d.priceHi : d.price;
    return { tier: p, incl: p * (1 + s.vat), basis: p };
  }
  const incl = d.price / (d.barrelKg / 1000);
  return { tier: d.price, incl, basis: incl / (1 + s.vat) }; // 若确认专票
}
function compute(code, s) {
  s = s || S;
  const d = STD[code];
  const r = s.rate / s.yearDays;
  const g = goodsOf(code, s);
  const goods = d.costBasis === "excl" ? g.basis : (code === "C" ? g.incl : g.basis);
  const pack = 0;
  let freightBase = 0, freightPaid = 0;
  if (d.freightBy === "buyer" && !s.sellerDelivers) {
    freightPaid = s.freight;
    freightBase = s.freight / (1 + s.freightTax);
  }
  const unload = s.unload / (1 + s.svcTax);
  const inspect = (s.insp * s.inspBatches) / s.annualVol / (1 + s.svcTax);
  const vehicle = code === "B" ? (s.veh * s.vehTrips) / s.annualVol / (1 + s.svcTax) : 0;
  const base = goods + pack + freightBase + unload + inspect + vehicle;
  let cap = 0;
  for (let i = 0; i < 40; i++) {
    const nx = (base + cap) * r * d.days;
    if (Math.abs(nx - cap) < 1e-9) { cap = nx; break; }
    cap = nx;
  }
  let deposit = 0;
  if (code === "B") deposit += 300000 * s.rate * (s.depositDays / 360) / s.qty;
  if (code === "C") {
    const barrels = s.qty / 0.22;
    const dep = barrels * 30;
    deposit += dep * (s.packUnret * 1.0 + (1 - s.packUnret) * s.rate * s.packRefundDays / 360) / s.qty;
  }
  const landed = base + cap + deposit;
  return {
    code, tier: g.tier, goodsIncl: g.incl, goods, purity: d.purity,
    goodsPurity: goods / d.purity, pack, freightBase, freightPaid, unload, inspect, vehicle,
    cap, days: d.days, base, deposit, landed, landedPurity: landed / d.purity
  };
}
function computeAll(s) {
  const out = {};
  SUP.forEach(c => out[c] = compute(c, s));
  const elig = SUP.filter(c => c !== "C" || s.acceptC || P.meta.sample_banner === "").map(c => [c, out[c]]);
  const ranked = SUP.filter(c => c !== "C" || s.acceptC).map(c => [c, out[c]]).sort((x, y) => x[1].landed - y[1].landed);
  ranked.forEach(([c], i) => { out[c].rank = i + 1; out[c].gap = out[c].landed - ranked[0][1].landed; });
  SUP.forEach(c => { if (out[c].rank === undefined) { out[c].rank = null; out[c].gap = null; } });
  out._best = ranked[0][0];
  return out;
}

/* ---------- 表格渲染 ---------- */
function th(arr, numIdx) {
  return "<thead><tr>" + arr.map((h, i) => `<th${(numIdx || []).includes(i) ? ' class="num"' : ""}>${h}</th>`).join("") + "</tr></thead>";
}
function cell(v, cls) { return `<td${cls ? ` class="${cls}"` : ""}>${v}</td>`; }

function renderKPIs(R) {
  const A = R.A, B = R.B, C = R.C;
  const best = R._best;
  const spread = A.landed - B.landed;
  const cMult = C.landed / B.landed;
  $("#kpi").innerHTML = `
    <div class="c win"><div class="k">最优（同口径 · 第一名）</div><div class="v">${NAME[best]}</div>
      <div class="n">到厂 <b>${n2(R[best].landed)}</b> 元/吨${R[best].rank ? "" : ""}</div></div>
    <div class="c"><div class="k">A − B 差额（到厂）</div><div class="v">${n0(spread)}</div>
      <div class="n">元/吨 · 200 吨合计约 ${n0(spread * S.qty)} 元</div></div>
    <div class="c warn"><div class="k">C / B 倍数</div><div class="v">${cMult.toFixed(1)}×</div>
      <div class="n">C 按 220 kg/桶折吨后为 ${n0(C.landed)} 元/吨</div></div>
    <div class="c"><div class="k">账期资金成本占比</div><div class="v">${(100 * B.cap / B.landed).toFixed(1)}%</div>
      <div class="n">B 月结 30 天（46 天占用）≈ ${n0(B.cap)} 元/吨</div></div>`;
  $("#verdict").innerHTML = `
    <b>结论</b>：在「净商品量 1 吨、不含税可抵扣、折纯到 100%、含买方运费与卸车费」的同一口径下，
    <b>${NAME[best]}</b> 的参考到厂成本最低，为 <b>${n2(R[best].landed)} 元/吨</b>。
    A 比它高 <b>${n0(spread)} 元/吨</b>（+${(100 * spread / B.landed).toFixed(1)}%），主因是含税出厂价 6,200 元/吨本身更高（含税差 ${n0(A.goodsIncl - B.goodsIncl)} 元/吨）。
    C 因「元/桶」计价且含量仅 99.5%，折吨后 <b>${n0(C.landed)} 元/吨</b>，且若为普通发票还有 13% 进项不可抵扣，<b>不具备可比性</b>，不参与排名。
    <br><b>但请注意</b>：B 的报价当日有效、含 ±3% 价格联动、另需 30 万保证金；A 的报价有效期 5 天、含运交付更省事。因此建议：<b>以 B 为价格锚定，要求 A 降价至同口径水平或提供送货到厂价</b>，再综合供货稳定性决定。`;
  // 顶栏事实
  $("#fQty").textContent = S.qty;
  $("#fRate").textContent = (S.rate * 100).toFixed(1);
  $("#fElig").textContent = S.acceptC ? "3 家（已接受 C 的 99.5%）" : "2 家（C 规格不符，单列）";
  $("#freightHint").textContent = S.sellerDelivers ? "当前为「供应商送货」模式，运费按 0 计" : "假设值，影响 A、B（买方自提）";
}

function renderBars(R) {
  const max = Math.max(...SUP.map(c => R[c].landed));
  $("#bars").innerHTML = SUP.map(c => {
    const w = Math.max(2, 100 * R[c].landed / max);
    const cls = c === "C" ? "x" : c.toLowerCase();
    return `<div class="hbar"><div class="lbl">${NAME[c]} <span class="pill ${c.toLowerCase()}">${c}</span></div>
      <div class="bar"><div class="fill ${cls}" style="width:${w}%"></div></div>
      <div class="val">${n2(R[c].landed)} ${c === "C" ? '<span class="pill hi" style="font-size:10px">不可比</span>' : ""}</div></div>`;
  }).join("");
}

function renderStacks(R) {
  const segs = [
    ["s-goods", "裸价"], ["s-freight", "运费"], ["s-fees", "卸/检/洗"], ["s-cap", "资金"], ["s-dep", "保证金"]
  ];
  $("#stackCards").innerHTML = SUP.map(c => {
    const r = R[c];
    const fees = r.unload + r.inspect + r.vehicle + r.pack;
    const parts = [["s-goods", r.goods], ["s-freight", r.freightBase], ["s-fees", fees], ["s-cap", r.cap], ["s-dep", r.deposit]];
    const tot = parts.reduce((a, b) => a + b[1], 0);
    const bars = parts.filter(p => p[1] > 0.005).map(p => `<span class="${p[0]}" style="width:${100 * p[1] / tot}%" title="${p[0]}"></span>`).join("");
    const legend = parts.map(p => `<div style="display:flex;justify-content:space-between;font-size:12.3px;padding:2px 0;border-bottom:1px dashed #eef2f6">
        <span><i style="display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px" class="${p[0]}"></i>${segs.find(s => s[0] === p[0])[1]}</span>
        <span class="num" style="font-family:var(--mono)">${n2(p[1])}</span></div>`).join("");
    return `<div class="sup ${c === R._best ? "best" : ""}">
      <h4>${NAME[c]} <span class="pill ${c.toLowerCase()}">${c}</span>${c === R._best ? '<span class="badge gold">最优</span>' : ""}${c === "C" ? '<span class="badge red">规格不符</span>' : ""}</h4>
      <div class="role">${P.std[c].name}</div>
      <div class="quote-line">原始报价：${esc(P.raw[c].price)}<br>计价单位：${esc(P.raw[c].unit)} → 统一为元/吨</div>
      <div class="stack" style="margin:8px 0 10px">${bars}</div>${legend}
      <div class="lc"><span class="v">${n2(r.landed)}</span><span class="u">元/吨 · 到厂（折纯 ${n2(r.landedPurity)}）</span></div>
    </div>`;
  }).join("");
}

function renderAttribution(R) {
  const rows = [
    ["裸价（不含税）", r => r.goods, "含税单价 ÷ 1.13 或原不含税价；已含数量阶梯"],
    ["数量阶梯命中", r => r.tier, "A≥110 吨 6.17 元/kg；B≥120 吨 4,800 元/吨"],
    ["运费（到厂，不含税）", r => r.freightBase, "买方自提 42 元/吨含税 ÷ 1.09；C 含运计 0"],
    ["卸车费", r => r.unload, "25 元/吨含税 ÷ 1.06（假设）"],
    ["检验费摊销", r => r.inspect, "1,800 × 6 ÷ 2,400 ÷ 1.06"],
    ["槽车清洗", r => r.vehicle, "600 × 8 ÷ 2,400 ÷ 1.06（仅 B 散装）"],
    ["账期资金成本", r => r.cap, "余额 × 4.5% × 占用天数 ÷ 360"],
    ["保证金/押金占用", r => r.deposit, "B：30 万 × 4.5% × 180/360 ÷ 200；C：铁桶押金"],
    ["到厂成本合计", r => r.landed, "以上各项之和"]
  ];
  let h = th(["成本项", "A 元/吨", "B 元/吨", "C 元/吨", "B − A", "说明"], [1, 2, 3, 4]);
  h += "<tbody>";
  rows.forEach(([lab, fn, note]) => {
    const a = fn(R.A), b = fn(R.B), c = fn(R.C);
    const isTier = lab === "数量阶梯命中";
    h += `<tr${lab === "到厂成本合计" ? ' class="total"' : ""}>
      <td>${lab}</td>
      <td class="num">${isTier ? a.toFixed(2) + " 元/kg" : n2(a)}</td>
      <td class="num">${isTier ? b.toFixed(0) + " 元/吨" : n2(b)}</td>
      <td class="num">${isTier ? "—" : n2(c)}</td>
      <td class="num ${(b - a) > 0 ? "lose" : "win"}">${isTier ? "—" : n2(b - a)}</td>
      <td style="font-size:12px;color:#5b6b78">${note}</td></tr>`;
  });
  h += "</tbody>";
  $("#attribution").innerHTML = h;
}

function renderRaw() {
  const fields = [
    ["产品名称", "product"], ["规格 / 含量", "spec"], ["计价单位", "unit"], ["单价（原文）", "price"],
    ["是否含税 / 税率", "tax"], ["发票类型", "invoice"], ["数量阶梯", "tiers"],
    ["包装形式", "pack"], ["包装费用", "pack_fee"], ["运费承担方与金额", "freight"],
    ["交货方式", "delivery"], ["付款条件", "payment"], ["最小起订量", "moq"],
    ["报价有效期", "validity"], ["质量标准", "quality"], ["产地 / 生产企业", "origin"], ["其他条款", "other"]
  ];
  let h = th(["字段", "供应商 A · PDF", "供应商 B · Excel", "供应商 C · 图片"]);
  h += "<tbody>";
  fields.forEach(([lab, k]) => {
    h += `<tr><td class="k">${lab}</td>` + SUP.map(c => {
      const v = P.raw[c][k];
      const miss = !v;
      return `<td class="${miss ? "warnrow" : ""}" style="${miss ? "background:#fff8e6" : ""}">${miss ? '<span class="pill hi">未注明</span>' : esc(v)}</td>`;
    }).join("") + "</tr>";
  });
  h += `<tr class="grp"><td colspan="4">文件定位</td></tr>`;
  h += `<tr><td class="k">文件名 / 格式</td>` + SUP.map(c => `<td>${esc(P.raw[c].file)}<br><span class="pill">${esc(P.raw[c].fmt)}</span></td>`).join("") + "</tr>";
  h += `<tr><td class="k">原报价位置</td>` + SUP.map(c => `<td>${esc(P.raw[c].loc)}</td>`).join("") + "</tr>";
  h += "</tbody>";
  $("#rawTable").innerHTML = h;
}

function renderPurity() {
  const rows = [
    ["A", "99.92%", "GB/T 4649-2018 聚酯级优等品", "✓ 满足", "✓", "✓", "✓", "允许折纯", ""],
    ["B", "99.90%", "GB/T 4649-2018 聚酯级优等品", "✓ 满足（等于下限）", "✓", "✓", "✓", "允许折纯", ""],
    ["C", "99.50%", "未注明执行标准", "✗ 低于询价规格", "✓", "?", "?", "不允许（单列）", "def"]
  ];
  let h = th(["供应商", "含量", "执行标准", "对询价规格", "①同物质", "②杂质可接受", "③可线性折算", "折纯判断", "折纯后到厂成本"], [8]);
  h += "<tbody>";
  const R = computeAll(S);
  rows.forEach(r => {
    h += `<tr><td><span class="pill ${r[0].toLowerCase()}">${r[0]}</span> ${NAME[r[0]]}</td><td>${r[1]}</td><td>${r[2]}</td>
      <td>${r[7].startsWith("不允许") ? '<span class="pill hi">' + r[3] + "</span>" : '<span class="pill b">' + r[3] + "</span>"}</td>
      <td>${r[4]}</td><td>${r[5]}</td><td>${r[6]}</td><td>${r[7].startsWith("不允许") ? '<b style="color:#c8102e">' + r[7] + "</b>" : '<b style="color:#127a5a">' + r[7] + "</b>"}</td>
      <td class="num">${n2(R[r[0]].landedPurity)}</td></tr>`;
  });
  h += `<tr class="grp"><td colspan="9">折纯公式：折纯成本 = 到厂成本 ÷ 含量。不折纯 = 结算按实物吨，成本按实物吨；折纯 = 把「每吨实际有效成分」的成本摆到同一标尺。</td></tr>`;
  h += "</tbody>";
  $("#purityTable").innerHTML = h;
}

function renderStd(R) {
  const rows = [
    ["原始报价（L1）", c => `<span class="layer raw">原始值</span> ${esc(P.raw[c].price)}`],
    ["原始计价单位", c => esc(P.raw[c].unit)],
    ["计价单位 → 元/吨", c => c === "A" ? "【转换】6.20 × 1000 = 6,200" : c === "B" ? "【转换】已是元/吨" : "【转换】6,300 ÷ 0.220 = 28,636.36"],
    ["税率口径", c => c === "A" ? "含税 · 13% 专票" : c === "B" ? "不含税 · 另开 13% 专票" : '<span class="pill hi">含税 · 税率/票种未注明</span>'],
    ["换算含税单价（元/吨）", c => n2(R[c].goodsIncl)],
    ["不含税裸价（元/吨）", c => `<b>${n2(R[c].goods)}</b>`],
    ["含量（折纯用）", c => pct(R[c].purity)],
    ["折纯后裸价", c => n2(R[c].goodsPurity)],
    ["数量阶梯（当前）", c => c === "A" ? `${R[c].tier.toFixed(2)} 元/kg` : c === "B" ? `${n0(R[c].tier)} 元/吨（不含税）` : "单一价"],
    ["包装形式", c => esc(P.raw[c].pack)],
    ["包装费（单收）", c => "0（已含价内）"],
    ["运费承担", c => c === "C" ? "卖方含运（隐含于价格）" : "买方自提 + 买方运费"],
    ["交货方式", c => esc(P.raw[c].delivery)],
    ["付款条件", c => esc(P.raw[c].payment)],
    ["加权资金占用天数", c => R[c].days + " 天"],
    ["最小起订量", c => `${P.std[c].moq} 吨`],
    ["报价有效期", c => c === "A" ? "5 天" : c === "B" ? '<span class="pill hi">当日有效</span>' : '<span class="pill mid">10 天（缺起始日）</span>'],
    ["质量标准", c => esc(P.raw[c].quality)]
  ];
  let h = th(["统一字段", "供应商 A", "供应商 B", "供应商 C", "口径说明"]);
  h += "<tbody>";
  rows.forEach(([lab, fn], idx) => {
    const note = ["", "", "桶重 220 kg 取自包装规格，需确认", "普票 → 进项不可抵扣", "", "", "", "", "", "", "", "", "", "", "", "", "", ""][idx];
    h += `<tr><td class="k">${lab}</td>` + SUP.map(c => `<td>${fn(c)}</td>`).join("") +
      `<td style="font-size:12px;color:#5b6b78">${note}</td></tr>`;
  });
  h += "</tbody>";
  $("#stdTable").innerHTML = h;
}

function renderCostTable(R) {
  let h = th(["项目（元/吨）", "A 华东石化", "B 恒源", "C 苏南", "口径说明"], [1, 2, 3]);
  const line = (lab, fn, note, cls) => `<tr class="${cls || ""}"><td>${lab}</td>` + SUP.map(c => `<td class="num">${fn(R[c], c)}</td>`).join("") + `<td style="font-size:12px;color:#5b6b78">${note}</td></tr>`;
  h += "<tbody>";
  h += line("① 裸价（不含税）", r => n2(r.goods), "含税 ÷1.13 / 不含税原值 / 普票全额");
  h += line("② 包装费（单收）", r => n2(r.pack), "三家均已含价内");
  h += line("③ 运费（到厂）", (r, c) => c === "C" ? "0（含运）" : n2(r.freightBase), "买方自提 ÷1.09；C 已含运");
  h += line("④ 卸车费", r => n2(r.unload), "假设 25 元/吨 ÷1.06");
  h += line("⑤ 检验费摊销", r => n2(r.inspect), "年 6 批 × 1,800 ÷ 2,400 吨");
  h += line("⑥ 槽车清洗", r => n2(r.vehicle), "仅散装 B：600×8÷2,400");
  h += line("⑦ 账期资金成本", r => `<span style="color:#7b3fb0">${n2(r.cap)}</span>`, "迭代求解，见明细");
  h += line("⑧ 保证金/押金占用", r => n2(r.deposit), "B 保证金；C 铁桶押金");
  h += `<tr class="total"><td>参考到厂成本</td>` + SUP.map(c => `<td class="num">${n2(R[c].landed)}</td>`).join("") + `<td style="font-size:12px">①~⑧ 之和</td></tr>`;
  h += `<tr><td>折纯后到厂成本</td>` + SUP.map(c => `<td class="num">${n2(R[c].landedPurity)}</td>`).join("") + `<td style="font-size:12px">÷ 含量</td></tr>`;
  h += `<tr><td>排名（同口径）</td>` + SUP.map(c => `<td class="num">${R[c].rank ? "#" + R[c].rank : '<span class="pill hi">不参与</span>'}</td>`).join("") + `<td style="font-size:12px">C 规格不符，默认剔除</td></tr>`;
  h += `<tr><td>较最优差额</td>` + SUP.map(c => `<td class="num ${R[c].gap > 0 ? "lose" : "win"}">${R[c].gap === null ? "—" : (R[c].gap > 0 ? "+" : "") + n2(R[c].gap)}</td>`).join("") + `<td style="font-size:12px">元/吨</td></tr>`;
  h += `<tr><td>本次采购金额（${S.qty} 吨）</td>` + SUP.map(c => `<td class="num">${n0(R[c].landed * S.qty)}</td>`).join("") + `<td style="font-size:12px">元（参考）</td></tr>`;
  h += "</tbody>";
  $("#costTable").innerHTML = h;
}

/* ---------- 明细抽屉 ---------- */
function explain(code) {
  const r = compute(code);
  const a = S.qty;
  const rows = [];
  const add = (h, f, res) => `<div class="step"><div class="h">${h}</div><div class="f">${f}</div><div class="r">→ ${res}</div></div>`;
  if (code === "A") {
    rows.push(add("① 数量阶梯判断", `采购量 ${a} 吨 ${a >= 110 ? "≥ 110 吨" : "< 110 吨"} → 单价 ${r.tier.toFixed(2)} 元/公斤`, `单价 ${r.tier.toFixed(2)} 元/kg`));
    rows.push(add("② 计价单位：公斤 → 吨", `${r.tier.toFixed(2)} 元/kg × 1000 kg/t`, `${n2(r.goodsIncl)} 元/吨（含税）`));
    rows.push(add("③ 税费：含税 → 不含税（13% 专票）", `${n2(r.goodsIncl)} ÷ (1 + 13%)`, `${n2(r.goods)} 元/吨（裸价）`));
  } else if (code === "B") {
    rows.push(add("① 数量阶梯判断", `采购量 ${a} 吨 ${a >= 120 ? "≥ 120 吨" : "< 120 吨"} → 不含税单价 ${n0(r.tier)} 元/吨`, `${n0(r.tier)} 元/吨`));
    rows.push(add("② 计价单位", "原文已为元/吨，无需换算", `${n0(r.tier)} 元/吨`));
    rows.push(add("③ 税费：不含税沿用", "原文明确「不含税，另开 13% 专票」→ 裸价 = 原文", `${n2(r.goods)} 元/吨（裸价）`));
    rows.push(add("（参考）含税价", `${n0(r.tier)} × 1.13`, `${n2(r.goodsIncl)} 元/吨（含税）`));
  } else {
    rows.push(add("① 计价单位：桶 → 吨", `6,300 元/桶 ÷ (220 kg ÷ 1000)`, `${n2(r.goodsIncl)} 元/吨（含税到货）`));
    rows.push(add("② 税费：票种未注明（默认普票）", "普票进项不可抵扣 → 全额计入成本", `${n2(r.goods)} 元/吨（成本口径）`));
    rows.push(add("（若确认为专票）", `${n2(r.goodsIncl)} ÷ 1.13`, `${n2(r.goodsIncl / 1.13)} 元/吨（情景 5）`));
  }
  rows.push(add("④ 运费", code === "C" ? "卖方含运，报价已含运输，不另计" : `${n2(r.freightPaid)} 元/吨（含税9%）÷ 1.09`, `${n2(r.freightBase)} 元/吨`));
  rows.push(add("⑤ 卸车费", `25 元/吨（假设，含税6%）÷ 1.06`, `${n2(r.unload)} 元/吨`));
  rows.push(add("⑥ 检验费摊销", `1,800 元/批 × 6 批/年 ÷ 2,400 吨/年 ÷ 1.06`, `${n2(r.inspect)} 元/吨`));
  rows.push(add("⑦ 槽车清洗", code === "B" ? `600 元/车次 × 8 车次/年 ÷ 2,400 吨 ÷ 1.06` : "不适用（吨桶/铁桶交付）", `${n2(r.vehicle)} 元/吨`));
  const base = r.base;
  rows.push(add("⑧ 资金占用（迭代不动点）", `r = ${(S.rate * 100).toFixed(2)}% ÷ 360 = ${(S.rate / S.yearDays).toExponential(4)}\n付款节奏 → 占用 ${r.days} 天\nC_k = (${n2(base)} + C_{k-1}) × r × ${r.days}`, `${n2(r.cap)} 元/吨`));
  if (r.deposit > 0) rows.push(add("⑨ 保证金/押金占用", code === "B" ? `300,000 × ${(S.rate * 100).toFixed(2)}% × 180/360 ÷ ${S.qty}` : `铁桶押金 30 元/桶 × ${(S.qty / 0.22).toFixed(0)} 桶，沉淀比例 ${pct(S.packUnret)}`, `${n2(r.deposit)} 元/吨`));
  rows.push(`<div class="callout ok"><b>参考到厂成本 = ${n2(base)} + ${n2(r.cap)} + ${n2(r.deposit)} = ${n2(r.landed)} 元/吨</b><br>
    折纯后 = ${n2(r.landed)} ÷ ${pct(r.purity)} = <b>${n2(r.landedPurity)} 元/吨</b></div>`);
  return rows.join("");
}

function renderBreakdowns(R) {
  $("#breakdowns").innerHTML = SUP.map(c => `
    <details${c === R._best ? " open" : ""}>
      <summary>${NAME[c]}（${c}）　到厂 ${n2(R[c].landed)} 元/吨　<span class="pill ${c.toLowerCase()}">${P.raw[c].fmt}</span>
        <button class="btn ghost sm" style="float:right" onclick="event.preventDefault();openSrc('${c}')">原报价位置</button></summary>
      <div class="dc">
        <div class="legend"><span><span class="layer raw">原始值</span> 来自报价单</span><span><span class="layer der">转换值</span> 公式计算</span><span><span class="layer asm">假设</span> 买方参数</span></div>
        ${explain(c)}
      </div>
    </details>`).join("");
}

function renderCapTable(R) {
  let h = th(["付款方式（原报价）", "加权资金占用天数", "实际账期", "B 的货款金额（元/吨·含税）", "B 资金成本（元/吨）", "年化 4.5% 下的成本率"], [1, 2, 3, 4, 5]);
  const rate = S.rate;
  const amounts = { "款到发货": 0, "预付 50% + 票到 7 天": 10.5, "月结 30 天（次月 25 日）": 46, "账期 60 天": 60, "账期 90 天": 90, "账期 120 天": 120 };
  h += "<tbody>";
  Object.entries(amounts).forEach(([lab, d]) => {
    const goodsB = 5480.5;
    const cost = goodsB * rate * d / 360;
    h += `<tr${d === 46 ? ' class="bestrow"' : ""}><td>${lab}</td><td class="num">${d}</td><td class="num">${d === 10.5 ? "预付50%+7天" : d === 46 ? "月结30天" : "—"}</td>
      <td class="num">${n2(goodsB)}</td><td class="num">${n2(cost)}</td><td class="num">${(100 * cost / goodsB).toFixed(2)}%</td></tr>`;
  });
  h += "</tbody>";
  $("#capTable").innerHTML = h;
}

/* ---------- 敏感性 ---------- */
function renderSens(R) {
  let h = th(["参数", "取值", "A 到厂", "ΔA", "B 到厂", "ΔB", "C 到厂", "ΔC", "最优"], [2, 3, 4, 5, 6, 7]);
  h += "<tbody>";
  P.sensitivity.forEach(g => {
    g.rows.forEach((row, i) => {
      const best = ["A", "B", "C"].filter(c => (c !== "C" || S.acceptC)).sort((x, y) => row[x] - row[y])[0];
      const fmt = (v, k) => g.key === "rate" ? (100 * v).toFixed(1) + "%" : n0(v);
      const cells = ["A", "B", "C"].map(c => {
        const dv = row["d" + c];
        const cls = Math.abs(dv) < 0.01 ? "" : dv > 0 ? "lose" : "win";
        return `<td class="num">${n2(row[c])}</td><td class="num ${cls}">${Math.abs(dv) < 0.01 ? "—" : (dv > 0 ? "+" : "") + n2(dv)}</td>`;
      }).join("");
      h += `<tr>${i === 0 ? `<td rowspan="${g.rows.length}" style="font-weight:700">${g.label}<br><span style="color:#8c9aa6;font-weight:400;font-size:11.5px">${g.unit}</span></td>` : ""}
        <td class="num">${fmt(row.v, g.key)}</td>${cells}<td>${best ? `<span class="pill ${best.toLowerCase()}">${best}</span>` : "—"}</td></tr>`;
    });
  });
  h += "</tbody>";
  $("#sensTable").innerHTML = h;
}

function renderSweep() {
  const points = P.price_sweep;
  const W = 1000, H = 300, pad = { l: 66, r: 20, t: 16, b: 34 };
  const ys = points.flatMap(p => [p.A, p.B, p.C]);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const xs = points.map(p => p.price);
  const x0 = xs[0], x1 = xs[xs.length - 1];
  const X = v => pad.l + (W - pad.l - pad.r) * (v - x0) / (x1 - x0);
  const Y = v => pad.t + (H - pad.t - pad.b) * (1 - (v - ymin) / (ymax - ymin));
  const path = key => points.map((p, i) => (i ? "L" : "M") + X(p.price).toFixed(1) + "," + Y(p[key]).toFixed(1)).join(" ");
  let svg = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;background:#fff;border:1px solid #e3e9ef;border-radius:10px">`;
  for (let i = 0; i <= 5; i++) {
    const v = ymin + (ymax - ymin) * i / 5;
    svg += `<line x1="${pad.l}" y1="${Y(v)}" x2="${W - pad.r}" y2="${Y(v)}" stroke="#eef2f6"/>
      <text x="${pad.l - 8}" y="${Y(v) + 4}" font-size="11" fill="#8c9aa6" text-anchor="end">${n0(v)}</text>`;
  }
  xs.forEach((v, i) => { if (i % 2 === 0) svg += `<text x="${X(v)}" y="${H - 12}" font-size="11" fill="#8c9aa6" text-anchor="middle">${n0(v)}</text>`; });
  [["A", "#3b7dd8"], ["B", "#0f8f6b"], ["C", "#c2772b"]].forEach(([k, col]) => {
    svg += `<path d="${path(k)}" fill="none" stroke="${col}" stroke-width="2.6"/>`;
  });
  // 市场现货位置
  const spot = P.market.spot_20261016.value;
  svg += `<line x1="${X(spot)}" y1="${pad.t}" x2="${X(spot)}" y2="${H - pad.b}" stroke="#c8102e" stroke-dasharray="5 4"/>
    <text x="${X(spot) + 6}" y="${pad.t + 14}" font-size="11.5" fill="#c8102e">生意社现货 ${n0(spot)} 元/吨（2026-10-16，含税）</text>`;
  const bench = P.market.benchmark_20261019.value;
  svg += `<line x1="${X(bench)}" y1="${pad.t}" x2="${X(bench)}" y2="${H - pad.b}" stroke="#b7791f" stroke-dasharray="3 3"/>
    <text x="${X(bench) + 6}" y="${pad.t + 30}" font-size="11.5" fill="#b7791f">生意社基准价 ${n0(bench)}（10-19）</text>`;
  svg += `<text x="${pad.l}" y="${H - 12}" font-size="11" fill="#8c9aa6">折纯裸价（元/吨，不含税）→</text></svg>`;
  $("#sweepChart").innerHTML = svg;
  let h = th(["折纯裸价（元/吨）", "A 到厂", "B 到厂", "C 到厂", "A−B"], [0, 1, 2, 3, 4]);
  h += "<tbody>";
  points.filter((_, i) => i % 2 === 0).forEach(p => {
    h += `<tr><td class="num">${n0(p.price)}</td><td class="num">${n2(p.A)}</td><td class="num">${n2(p.B)}</td><td class="num">${n2(p.C)}</td><td class="num ${p.A - p.B > 0 ? "lose" : "win"}">${n2(p.A - p.B)}</td></tr>`;
  });
  h += "</tbody>";
  $("#sweepTable").innerHTML = h;
}

function renderScen() {
  const SC = P.scenarios;
  let h = "<thead><tr>" + SC.map(s => `<th>${esc(s.name.replace(/^情景(\d)：/, "S$1 "))}</th>`).join("") + "<th>说明</th></tr></thead>";
  h += "<tbody>";
  ["A", "B", "C"].forEach(c => {
    h += `<tr><td><span class="pill ${c.toLowerCase()}">${c}</span> ${NAME[c]}</td>` +
      SC.map(s => `<td class="num">${n2(s.rows[c].landed)}${s.rows[c].rank ? ` <span class="pill ${s.rows[c].rank === 1 ? "b" : "lo"}">#${s.rows[c].rank}</span>` : ' <span class="pill hi">不参与</span>'}</td>`).join("") +
      `<td style="font-size:12px;color:#5b6b78">${c === "C" ? "C 规格不符，仅情景 4/5 参与" : ""}</td></tr>`;
  });
  h += "</tbody><tbody>";
  SC.forEach(s => { h += `<tr><td colspan="5" style="font-size:12.3px;color:#5b6b78"><b>${esc(s.name)}</b>：${esc(s.note)}</td></tr>`; });
  h += "</tbody>";
  $("#scenTable").innerHTML = h;
}

function renderMarket() {
  const M = P.market_position, pos = M.pos;
  let h = th(["供应商", "折纯含税出厂价（元/吨）", "生意社现货（10-16，含税）", "相对现货", "相对现货 %", "相对基准价（5,966.67）", "判断"], [1, 2, 3, 4, 5]);
  h += "<tbody>";
  SUP.forEach(c => {
    const p = pos[c];
    const pv = p.vs_spot_pct;
    const verdict = pv < -10 ? '<span class="pill hi">显著低于市场，需核实货源/规格</span>'
      : pv < 5 ? '<span class="pill b">处于市场区间内</span>'
        : pv < 15 ? '<span class="pill mid">略高于现货上限（含包装/服务溢价）</span>'
          : '<span class="pill hi">严重偏离市场</span>';
    h += `<tr><td><span class="pill ${c.toLowerCase()}">${c}</span> ${NAME[c]}</td><td class="num">${n2(p.incl_equiv)}</td><td class="num">${n2(M.spot)}</td>
      <td class="num ${p.vs_spot > 0 ? "lose" : "win"}">${p.vs_spot > 0 ? "+" : ""}${n2(p.vs_spot)}</td>
      <td class="num ${p.vs_spot > 0 ? "lose" : "win"}">${p.vs_spot > 0 ? "+" : ""}${p.vs_spot_pct.toFixed(1)}%</td>
      <td class="num">${p.vs_bench > 0 ? "+" : ""}${n2(p.vs_bench)}</td><td>${verdict}</td></tr>`;
  });
  h += `<tr class="grp"><td colspan="7">近 3 个月现货区间：${n0(P.market.recent_low.value)}（${P.market.recent_low.date}）~ ${n0(P.market.recent_high.value)}（${P.market.recent_high.date}），振幅 ${((P.market.recent_high.value / P.market.recent_low.value - 1) * 100).toFixed(0)}%。当前处于冲高回落阶段（09-13 高点 6,625 → 10-16 5,808）。</td></tr>`;
  h += "</tbody>";
  $("#marketTable").innerHTML = h;
}

function renderTraps() {
  const icons = ["🎭", "💸", "🚚", "⏳", "🧪"];
  $("#traps").innerHTML = P.comparison.traps.map((t, i) => `
    <div class="callout ${i === 0 || i === 4 ? "bad" : "warn"}"><b>${icons[i]} 陷阱 ${i + 1}：${t[0]}</b><br>${esc(t[1])}</div>`).join("");
}

function renderIgnored() {
  let h = th(["供应商", "条款项", "原报价原文", "原报价金额", "是否已计入价内", "处理 / 待确认"], [3]);
  h += "<tbody>";
  SUP.forEach(c => {
    const items = Object.entries(P.ignored[c]);
    items.forEach(([k, v], i) => {
      const inPrice = v.in_price === true ? '<span class="pill b">已含</span>' : v.in_price === false ? '<span class="pill mid">另计/不承担</span>' : '<span class="pill">不适用</span>';
      const amt = v.amount === null ? '<span class="pill hi">未提供</span>' : (v.amount === 0 ? "0（明示不收费）" : n2(v.amount));
      const act = v.amount === null ? '<b style="color:#b42318">→ 列入待确认，不按 0 计</b>' : "→ 金额已知";
      h += `<tr>${i === 0 ? `<td rowspan="${items.length}"><span class="pill ${c.toLowerCase()}">${c}</span> ${NAME[c]}</td>` : ""}
        <td>${k}</td><td style="font-size:12.3px">${esc(v.text)}</td><td class="num">${amt}</td><td>${inPrice}</td><td style="font-size:12px">${act}</td></tr>`;
    });
  });
  h += "</tbody>";
  $("#ignoredTable").innerHTML = h;
}

function renderOpen() {
  let h = th(["#", "供应商", "缺失/歧义字段", "问题描述", "对成本或决策的影响", "需要索取的材料", "优先级"]);
  h += "<tbody>";
  P.open_items.sort((a, b) => ({ "高": 0, "中": 1, "低": 2 }[a[5]] - { "高": 0, "中": 1, "低": 2 }[b[5]])).forEach((o, i) => {
    const pr = o[5] === "高" ? "hi" : o[5] === "中" ? "mid" : "lo";
    h += `<tr><td>${i + 1}</td><td><span class="pill ${o[0] === "ALL" ? "" : o[0].toLowerCase()}">${o[0]}</span></td><td><b>${esc(o[1])}</b></td>
      <td>${esc(o[2])}</td><td style="font-size:12.3px">${esc(o[3])}</td><td style="font-size:12.3px">${esc(o[4])}</td>
      <td><span class="pill ${pr}">${o[5]}</span></td></tr>`;
  });
  h += "</tbody>";
  $("#openTable").innerHTML = h;
}

function renderCC() {
  let h = th(["检查项", "检查内容", "结论"]);
  h += "<tbody>";
  P.cross_checks.forEach(c => {
    const good = c[2] === "通过" || c[2].startsWith("通过");
    h += `<tr><td>${c[0]}</td><td>${esc(c[1])}</td><td>${good ? '<span class="pill b">' + c[2] + "</span>" : '<span class="pill mid">' + c[2] + "</span>"}</td></tr>`;
  });
  h += "</tbody>";
  $("#ccTable").innerHTML = h;
}

const PARAMS = [
  ["采购数量", "200 吨", "用户输入", "影响数量阶梯命中；同时决定保证金/押金摊薄", "用户"],
  ["年化资金成本", "4.5%", "用户输入（可选）", "账期资金占用、保证金占用", "用户"],
  ["买方自提运费", "42 元/吨（含税9%）", "假设（物流询价待确认）", "A、B 到厂成本 +38.53 元/吨", "假设"],
  ["到厂卸车费", "25 元/吨（含税6%）", "假设（三家均未明确）", "三家各 +23.58 元/吨", "假设"],
  ["第三方检验费", "1,800 元/批 × 6 批/年", "假设", "摊销 +4.25 元/吨", "假设"],
  ["年采购量", "2,400 吨", "假设（示例采购计划）", "检验费与车辆准备的摊销分母", "假设"],
  ["槽车清洗+置换", "600 元/车次 × 8 车次/年", "假设", "B 散装 +1.89 元/吨", "假设"],
  ["保证金占用天数", "180 天", "假设（待确认）", "B 保证金资金成本", "假设"],
  ["包装押金退回天数", "10 天；不退还比例 10%", "假设（待确认）", "C 押金沉淀成本", "假设"],
  ["年化天数口径", "360 天", "惯例（生意社与银行承兑均常用）", "资金成本折算", "惯例"],
  ["增值税率", "13%", "法定", "价税分离", "法定"],
  ["运输服务税率", "9%", "法定", "运费不含税化", "法定"],
  ["现代服务税率", "6%", "法定", "卸车、检验、清洗不含税化", "法定"],
  ["生意社现货价", "5,808 元/吨（10-16）", "市场数据", "报价市场定位", "市场"],
  ["生意社基准价", "5,966.67 元/吨（10-19）", "市场数据", "报价市场定位、B 联动基准", "市场"]
];
function renderParams() {
  let h = th(["参数", "取值", "性质", "影响的成本项", "来源类别"]);
  h += "<tbody>";
  PARAMS.forEach(p => {
    const cls = p[4] === "假设" ? "asm" : p[4] === "用户" ? "der" : "raw";
    const tag = p[4] === "假设" ? "assumption" : p[4] === "用户" ? "user" : "market";
    h += `<tr><td><b>${p[0]}</b></td><td class="num">${p[1]}</td><td><span class="layer ${cls}">${p[2]}</span></td><td style="font-size:12.3px">${p[3]}</td><td>${p[4]}</td></tr>`;
  });
  h += "</tbody>";
  $("#paramTable").innerHTML = h;
}
function renderSources() {
  const src = [
    ["报价文件 A", "供应商A_华东石化工业品_报价函_20261019.pdf", "PDF · 1 页", "模拟业务样例（采购方制作）"],
    ["报价文件 B", "供应商B_恒源新材料报价明细表_20261019.xlsx", "Excel · 3 工作表", "模拟业务样例（采购方制作）"],
    ["报价文件 C", "供应商C_苏南化工贸易报价单_20261019.png", "PNG · 1080×1760", "模拟业务样例（采购方制作）"],
    ["EG 现货价", P.market.spot_20261016.source + "（10-16：5,808 元/吨；09-13 高点 6,625；07-21 低点 4,835）", "生意社", `<a href="${P.market.spot_20261016.url}" target="_blank" rel="noopener">eg.100ppi.com/futures</a>`],
    ["EG 基准价", P.market.benchmark_20261019.source, "生意社", `<a href="${P.market.benchmark_20261019.url}" target="_blank" rel="noopener">100ppi.com</a>`],
    ["EG 现货报价", "乙二醇商品报价动态（2026-10-19）：聚酯级含量≥99.9% 厂家/贸易商报价 3,595~7,000 元/吨，离散度大，仅作趋势参考", "生意社", `<a href="https://www.100ppi.com/news/detail-20261019-6362576.html" target="_blank" rel="noopener">100ppi.com/news</a>`],
    ["规格标准", "GB/T 4649-2018 工业用乙二醇（聚酯级）", "国家标准", "—"],
    ["采购需求", `${P.meta.product}；数量 200 吨；收货地 ${P.meta.dest}`, "用户需求", "—"]
  ];
  let h = th(["项目", "内容", "类型", "链接/出处"]);
  h += "<tbody>";
  src.forEach(s => { h += `<tr><td>${s[0]}</td><td style="font-size:12.5px">${esc(s[1])}</td><td>${s[2]}</td><td>${s[3]}</td></tr>`; });
  h += "</tbody>";
  $("#sourceTable").innerHTML = h;
}

/* ---------- 抽屉：原报价位置 / 供应商尽调 ---------- */
function openSrc(code) {
  const q = P.raw[code];
  $("#drawerBody").innerHTML = `
    <h3>原报价位置 · ${NAME[code]}</h3>
    <div class="role" style="color:#5b6b78;font-size:12.5px">${esc(q.file)}</div>
    <div class="srcbox"><b>文件：</b>${esc(q.file)}<br><b>格式：</b>${esc(q.fmt)}<br><b>定位：</b>${esc(q.loc)}</div>
    <h3 style="margin-top:18px;font-size:15px">该位置的原文</h3>
    <table class="t" style="border:1px solid #e3e9ef"><tbody>
      ${[["产品名称", "product"], ["规格/含量", "spec"], ["单价（原文）", "price"], ["计价单位", "unit"], ["税率/发票", "tax"], ["数量阶梯", "tiers"], ["包装", "pack"]].map(([l, k]) => `<tr><td class="k">${l}</td><td>${esc(q[k])}</td></tr>`).join("")}
    </tbody></table>
    <div class="callout" style="margin-top:14px"><b>如何回到原文件</b><br>打开 ${esc(q.file)}，按「${esc(q.loc)}」定位到对应段落 / 工作表 / 卡片区域即可核对。</div>
    <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn primary" onclick="openDd('${code}')">进入企业尽调 →</button>
      <button class="btn ghost" onclick="copyText('${esc(FULL[code])}')">复制企业名称</button>
    </div>
    <div class="note">企业尽调为下游场景：核查该供应商的工商存续、股东与实控人、经营范围与危化品资质、司法与失信记录、涉诉风险。本样例中点击后展示「尽调核查清单模板」，不含真实企业数据。</div>`;
  $("#drawer").classList.add("on");
}

/* ---------- 企业尽调清单（内嵌模板，无外部依赖） ---------- */
const DD_ITEMS = [
  ["工商存续", "营业执照状态是否存续、经营范围是否含该品类、注册资本与实缴", "国家企业信用信息公示系统"],
  ["危化品资质", "危险化学品经营许可证 / 安全生产许可证（若为生产商）是否在有效期内", "应急管理部许可证查询"],
  ["生产与货源", "自产还是经销；若经销，一手货源与授权、是否可提供原厂证明", "供应商书面说明 + 授权书"],
  ["股东与实控人", "股权结构是否清晰、是否存在关联交易或空壳特征", "工商股权穿透"],
  ["涉诉与执行", "被执行人、失信、限高、重大买卖合同纠纷", "中国执行信息公开网 / 裁判文书网"],
  ["税务与开票", "是否可开 13% 专票、纳税人资格、历史开票记录", "供应商提供开票信息 + 试单验证"],
  ["质控能力", "是否有 COA、批次可追溯、第三方检测报告；异议处理时效", "索取近 3 批 COA 与检测报告"],
  ["交付与履约", "库区/产能、交付准时率、过往供货记录、是否需保证金", "历史合作记录 + 同行口碑"],
  ["价格合理性", "报价相对市场价（生意社等）的偏离、是否含隐性费用", "本报告的「市场定位」段"],
];
function openDd(code) {
  $("#drawerBody").innerHTML = `
    <h3>企业尽调核查清单 · ${NAME[code]}</h3>
    <div class="role" style="color:#5b6b78;font-size:12.5px">${esc(FULL[code])}（模拟业务样例 · 虚构主体）</div>
    <div class="callout" style="margin-top:12px;background:#fff8e6;border-color:#f0d08a">
      <b>样例声明</b><br>该主体为虚构，下列各项均无真实核查结果，仅展示尽调应覆盖的维度与取证渠道。
    </div>
    <table class="t" style="border:1px solid #e3e9ef;margin-top:12px">
      <thead><tr><th style="width:26%">核查维度</th><th>核查内容</th><th style="width:28%">取证渠道</th></tr></thead>
      <tbody>${DD_ITEMS.map(([a, b, c]) => `<tr><td class="k">${a}</td><td>${b}</td><td style="color:#5b6b78">${c}</td></tr>`).join("")}</tbody>
    </table>
    <div class="note" style="margin-top:12px">与本次比价相关的优先项：${code === "C"
      ? "C 的规格（99.5%）与票种未明 → 优先核实「危化品资质」「质控能力」「税务与开票」三项。"
      : code === "B" ? "B 价格低于市场 6.7% → 优先核实「生产与货源」「交付与履约」「是否含隐性费用」。"
      : "A 价格高于市场 6.2% → 优先核实「价格合理性」中的包装与服务溢价是否成立。"}</div>
    <div style="margin-top:14px"><button class="btn ghost" onclick="openSrc('${code}')">← 返回原报价</button></div>`;
  $("#drawer").classList.add("on");
}
function closeDrawer() { $("#drawer").classList.remove("on"); }

/* ---------- 文件上传与本地抽取 ---------- */
const FIELD_PATTERNS = [
  ["产品名称", /(产品名称|品名|物料名称|商品名称)[：:\s]*([^\n，,；;|]{2,40})/],
  ["规格含量", /(规格|含量|纯度|执行标准)[^：:\n]{0,6}[：:\s]*([^\n，,；;|]{2,60})/],
  ["计价单位", /(计价单位|单位|计量单位)[：:\s]*([^\n，,；;|]{1,20})/],
  ["单价", /(单价|报价|价格)[^：:\n]{0,8}[：:\s]*([0-9,.]+\s*元(?:\s*\/\s*[\u4e00-\u9fa5a-zA-Z]+)?)/],
  ["是否含税", /(含税|不含税|税率\s*1[0-9]%|增值税[专普]用?发票)/],
  ["包装", /(包装(?:形式|方式|规格)?|包装物)[：:\s]*([^\n，,；;|]{2,40})/],
  ["运费", /(运费|运输费用|送货)[：:\s]*([^\n，,；;|]{0,50})/],
  ["付款", /(付款|结算|账期|款到)[^\n]{0,6}[：:\s]*([^\n，,；;|]{2,60})/],
  ["起订量", /(起订量|最小(?:起订|订量)|MOQ)[：:\s]*([^\n，,；;|]{1,30})/],
  ["有效期", /(有效期|有效日期|报价有效)[：:\s]*([^\n，,；;|]{2,40})/],
  ["质量标准", /(质量标准|执行标准|GB\/?T\s*\d+)[^\n]{0,60}/],
  ["交货", /(交货(?:方式|地点|期)?|交付)[：:\s]*([^\n，,；;|]{2,50})/]
];
function extractText(text) {
  const out = [];
  FIELD_PATTERNS.forEach(([name, re]) => {
    const m = text.match(re);
    if (m) out.push({ field: name, value: (m[2] || m[1] || "").trim().slice(0, 60), conf: /含量|纯度/.test(name) ? "需确认" : "高" });
  });
  return out;
}
async function handleFiles(files) {
  const fl = $("#fileList");
  if (!files.length) return;
  fl.innerHTML = "";
  let i = 0;
  for (const f of files) {
    i++;
    $("#prog").style.width = (100 * i / files.length) + "%";
    const row = document.createElement("div"); row.className = "fi";
    const ext = (f.name.split(".").pop() || "").toLowerCase();
    row.innerHTML = `<div class="f"><b>${esc(f.name)}</b> <span class="pill">${esc(ext.toUpperCase())}</span> <span style="color:#8c9aa6">${(f.size / 1024).toFixed(0)} KB</span></div><div class="st">解析中…</div>`;
    fl.appendChild(row);
    let res = { ok: false, text: "", note: "" };
    try {
      if (["txt", "csv"].includes(ext)) {
        res = { ok: true, text: await f.text() };
      } else if (ext === "pdf") {
        const buf = new Uint8Array(await f.arrayBuffer());
        res = { ok: true, text: pdfText(buf), note: "PDF 文本层抽取" };
      } else if (["docx", "xlsx"].includes(ext)) {
        res = { ok: true, text: await officeText(f, ext), note: ext.toUpperCase() + " 文档文本抽取" };
      } else if (["png", "jpg", "jpeg", "webp"].includes(ext)) {
        res = { ok: false, note: "图片报价：浏览器内不做 OCR，需多模态识别或人工录入" };
      } else {
        res = { ok: false, note: "不支持的格式" };
      }
    } catch (e) {
      res = { ok: false, note: "解析失败：" + e.message };
    }
    const fields = res.ok ? extractText(res.text) : [];
    row.querySelector(".st").innerHTML = res.ok
      ? `<span class="badge green">已抽取 ${fields.length} 个字段</span>`
      : `<span class="badge red">${esc(res.note)}</span>`;
    if (res.ok && fields.length) {
      const box = document.createElement("div");
      box.className = "callout warn";
      box.innerHTML = `<b>待确认字段（${esc(f.name)}）</b>：抽取结果必须人工确认后才能进入比较表。` +
        `<table class="t" style="margin-top:6px"><thead><tr><th>字段</th><th>抽取值</th><th>置信度</th><th>确认</th></tr></thead><tbody>` +
        fields.map((x, k) => `<tr><td>${x.field}</td><td>${esc(x.value)}</td><td>${x.conf === "高" ? '<span class="pill b">高</span>' : '<span class="pill mid">需核对</span>'}</td>
          <td><input type="checkbox" class="ck" data-f="${esc(f.name)}" data-i="${k}" ${x.conf === "高" ? "" : ""}></td></tr>`).join("") +
        `</tbody></table><button class="btn ghost sm" style="margin-top:6px" onclick="confirmAll(this)">全部确认并生成统一比价表</button>`;
      $("#liveExtract").appendChild(box);
    } else if (!res.ok) {
      const box = document.createElement("div");
      box.className = "callout bad";
      box.innerHTML = `<b>${esc(f.name)}</b>：${esc(res.note)}。按规则该文件<b>不产生任何默认值</b>，字段全部进入待确认队列；请补录后再参与比价。`;
      $("#liveExtract").appendChild(box);
    }
  }
  $("#prog").style.width = "100%";
  setTimeout(() => $("#prog").style.width = "0", 800);
  toast("已解析 " + files.length + " 份文件，请确认待确认字段");
}
/* 极简 PDF 文本层抽取：解压 FlateDecode 流后抓取 Tj/TJ 字符串 */
function pdfText(bytes) {
  const s = new TextDecoder("latin1").decode(bytes);
  if (!/\/Font/.test(s)) return "";
  const chunks = [];
  const re = /stream\r?\n([\s\S]*?)\r?\nendstream/g;
  let m;
  while ((m = re.exec(s))) {
    const raw = m[1];
    try {
      const bin = Uint8Array.from(raw, c => c.charCodeAt(0) & 0xff);
      const inf = window.pakoInflate ? window.pakoInflate(bin) : null;
      if (inf) chunks.push(inf);
    } catch (e) { }
  }
  let txt = chunks.join("\n");
  // 提取 (…) 与 <…> 字符串
  const out = [];
  const tr = /\(((?:\\.|[^\\)])*)\)\s*Tj|<([0-9A-Fa-f]+)>\s*TJ/g;
  let t;
  while ((t = tr.exec(txt))) out.push(t[1] ? t[1].replace(/\\([()\\])/g, "$1") : "");
  return out.join(" ") || s.replace(/[^\x20-\x7e]/g, " ").slice(0, 4000);
}
async function officeText(f, ext) {
  const buf = await f.arrayBuffer();
  // DOCX/XLSX 均为 zip；用内置 DecompressionStream 解压 zip 里第一段文本
  return extractZipText(buf);
}
async function extractZipText(buf) {
  const dv = new DataView(buf);
  let eocd = -1;
  for (let i = buf.byteLength - 22; i >= 0 && i > buf.byteLength - 66000; i--) {
    if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) return "";
  const n = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const texts = [];
  for (let k = 0; k < n; k++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break;
    const method = dv.getUint16(p + 10, true);
    const csize = dv.getUint32(p + 20, true);
    const nl = dv.getUint16(p + 28, true), el = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true);
    const lho = dv.getUint32(p + 42, true);
    const name = new TextDecoder().decode(new Uint8Array(buf, p + 46, nl));
    p += 46 + nl + el + cl;
    if (!/\.(xml|rels)$/.test(name) || !/(document|sharedStrings|sheet\d+|word)/.test(name)) continue;
    const lh_nl = dv.getUint16(lho + 26, true), lh_el = dv.getUint16(lho + 28, true);
    const start = lho + 30 + lh_nl + lh_el;
    const data = new Uint8Array(buf, start, csize);
    try {
      if (method === 0) texts.push(new TextDecoder().decode(data));
      else if (method === 8) texts.push(await inflateRaw(data));
    } catch (e) { }
  }
  return texts.join("\n").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
}
async function inflateRaw(data) {
  if (!("DecompressionStream" in window)) return "";
  const ds = new DecompressionStream("deflate-raw");
  const stream = new Blob([data]).stream().pipeThrough(ds);
  return await new Response(stream).text();
}
window.confirmAll = function (btn) {
  const t = btn.closest(".callout").querySelectorAll(".ck");
  t.forEach(c => c.checked = true);
  toast("已确认 " + t.length + " 个字段（待确认项置为『已确认』，未提供字段仍保持待确认）");
  btn.textContent = "✔ 已确认，可进入统一比价表";
  btn.disabled = true;
};
window.copyText = function (t) { navigator.clipboard && navigator.clipboard.writeText(t).then(() => toast("已复制：" + t)); };
window.openSrc = openSrc; window.openDd = openDd; window.closeDrawer = closeDrawer;

/* ---------- 导出 ---------- */
function exportRows() {
  const R = computeAll(S);
  const rows = [["供应商", "原始报价", "原始单位", "含税单价(元/吨)", "不含税裸价(元/吨)", "含量", "运费(不含税)", "卸车费", "检验费", "槽车清洗", "资金成本", "保证金/押金", "到厂成本(元/吨)", "折纯到厂(元/吨)", "排名"]];
  SUP.forEach(c => {
    const r = R[c];
    rows.push([NAME[c], P.raw[c].price, P.raw[c].unit, r.goodsIncl.toFixed(2), r.goods.toFixed(2), (r.purity * 100).toFixed(2) + "%",
      r.freightBase.toFixed(2), r.unload.toFixed(2), r.inspect.toFixed(2), r.vehicle.toFixed(2), r.cap.toFixed(2), r.deposit.toFixed(2),
      r.landed.toFixed(2), r.landedPurity.toFixed(2), r.rank || "不参与"]);
  });
  return rows;
}
function download(name, content, type) {
  const blob = new Blob([content], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1500);
}
$("#btnExportCsv").onclick = () => {
  const csv = "\ufeff" + exportRows().map(r => r.map(x => `"${String(x).replace(/"/g, '""')}"`).join(",")).join("\n");
  download("乙二醇报价比较_当前参数.csv", csv, "text/csv;charset=utf-8");
  toast("已导出 CSV");
};
$("#btnPrint").onclick = () => window.print();

/* 导出 Excel（无外部依赖：构造 Excel 2003 XML Spreadsheet） */
$("#btnExportXlsx").onclick = () => {
  const R = computeAll(S);
  const rowXml = (cells, style) => "<Row>" + cells.map(c => `<Cell${style ? ` ss:StyleID="${style}"` : ""}><Data ss:Type="${typeof c === "number" ? "Number" : "String"}">${String(c).replace(/&/g, "&amp;").replace(/</g, "&lt;")}</Data></Cell>`).join("") + "</Row>";
  let body = "";
  body += rowXml(["乙二醇采购报价比较（当前参数快照）", "", "", "", ""], "h");
  body += rowXml(["采购数量(吨)", S.qty, "年化资金成本", (S.rate * 100).toFixed(2) + "%", "生成时间 " + new Date().toLocaleString("zh-CN")]);
  body += rowXml([], "");
  exportRows().forEach((r, i) => { body += rowXml(r.map((v, j) => j > 1 && j !== 14 && isNaN(v) === false && v !== "" ? (isNaN(parseFloat(v)) ? v : parseFloat(v)) : v), i === 0 ? "h" : ""); });
  body += rowXml([], "");
  body += rowXml(["明细：裸价 / 运费 / 卸车 / 检验 / 清洗 / 资金 / 保证金 / 到厂 / 折纯"], "h");
  SUP.forEach(c => {
    const r = R[c];
    body += rowXml([NAME[c], "裸价", r.goods.toFixed(2), "运费", r.freightBase.toFixed(2), "卸车", r.unload.toFixed(2), "检验", r.inspect.toFixed(2), "清洗", r.vehicle.toFixed(2), "资金", r.cap.toFixed(2), "保证金", r.deposit.toFixed(2), "到厂", r.landed.toFixed(2)]);
  });
  const xml = `<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
  <Styles><Style ss:ID="h"><Font ss:Bold="1" ss:Color="#FFFFFF"/><Interior ss:Color="#0D2B45" ss:Pattern="Solid"/></Style></Styles>
  <Worksheet ss:Name="比较结果"><Table>${body}</Table></Worksheet></Workbook>`;
  download("乙二醇报价比较_当前参数.xls", xml, "application/vnd.ms-excel");
  toast("已导出 Excel（当前参数快照）");
};

/* ---------- 交互绑定 ---------- */
function bindRange(rId, nId, key, scale) {
  const r = $("#" + rId), n = $("#" + nId);
  const upd = (v) => {
    v = Number(v);
    if (isNaN(v) || v < 0) return;
    S[key] = scale ? v / scale : v;
    r.value = scale ? v * scale : v; n.value = v;
    render();
  };
  r.addEventListener("input", () => upd(r.value));
  n.addEventListener("input", () => upd(n.value));
}
bindRange("rQty", "nQty", "qty", 0);
bindRange("rRate", "nRate", "rate", 100);
$("#nFreight").addEventListener("input", e => { S.freight = Math.max(0, Number(e.target.value) || 0); render(); });
$("#nUnload").addEventListener("input", e => { S.unload = Math.max(0, Number(e.target.value) || 0); render(); });
$("#nInsp").addEventListener("input", e => { S.insp = Math.max(0, Number(e.target.value) || 0); render(); });
$("#nVeh").addEventListener("input", e => { S.veh = Math.max(0, Number(e.target.value) || 0); render(); });
$$("#segFreight button").forEach(b => b.onclick = () => {
  $$("#segFreight button").forEach(x => x.classList.remove("on")); b.classList.add("on");
  if (b.dataset.v === "0") { S.sellerDelivers = true; } else { S.sellerDelivers = false; S.freight = Number(b.dataset.v); $("#nFreight").value = S.freight; }
  render();
});
$$("#segC button").forEach(b => b.onclick = () => {
  $$("#segC button").forEach(x => x.classList.remove("on")); b.classList.add("on");
  S.acceptC = b.dataset.v === "1"; render();
});
$("#btnReset").onclick = () => {
  S = Object.assign({}, BASE);
  $("#rQty").value = 200; $("#nQty").value = 200; $("#rRate").value = 4.5; $("#nRate").value = 4.5;
  $("#nFreight").value = 42; $("#nUnload").value = 25; $("#nInsp").value = 1800; $("#nVeh").value = 600;
  $$("#segFreight button").forEach((b, i) => b.classList.toggle("on", i === 0));
  $$("#segC button").forEach((b, i) => b.classList.toggle("on", i === 0));
  render(); toast("已恢复基准参数");
};
const drop = $("#drop"), fi = $("#fileInput");
drop.onclick = () => fi.click();
fi.onchange = () => handleFiles(fi.files);
["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("hot"); }));
["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("hot"); }));
drop.addEventListener("drop", e => handleFiles(e.dataTransfer.files));
$$("#tabs a").forEach(a => a.addEventListener("click", () => {
  $$("#tabs a").forEach(x => x.classList.remove("on")); a.classList.add("on");
}));

/* ---------- 渲染入口 ---------- */
function safe(fn, name) {
  try { fn(); } catch (e) { console.warn("[render:" + name + "] " + e.message); }
}
function render() {
  const R = computeAll(S);
  safe(() => renderKPIs(R), "kpi"); safe(() => renderBars(R), "bars"); safe(() => renderStacks(R), "stacks");
  safe(() => renderAttribution(R), "attr"); safe(renderPurity, "purity"); safe(() => renderStd(R), "std");
  safe(() => renderCostTable(R), "cost"); safe(() => renderBreakdowns(R), "bd"); safe(() => renderCapTable(R), "cap");
  safe(() => renderSens(R), "sens"); safe(renderSweep, "sweep"); safe(renderScen, "scen"); safe(renderMarket, "market");
}

/* 静态区块 */
renderRaw(); renderTraps(); renderIgnored(); renderOpen(); renderCC(); renderParams(); renderSources();
render();
// 校验：浏览器引擎与 Python 引擎结果对比（同一参数下应完全一致）
(function verify() {
  const py = P.result;
  const Rv = computeAll(Object.assign({}, BASE, { acceptC: false }));
  const chk = ["A", "B", "C"].map(c => ({ c, py: +py[c].landed.toFixed(4), js: +Rv[c].landed.toFixed(4), d: +Math.abs(py[c].landed - Rv[c].landed).toFixed(6) }));
  window.__verify = { check: chk, maxDiff: Math.max(...chk.map(x => x.d)), pass: Math.max(...chk.map(x => x.d)) < 0.01 };
  console.log("[verify] python vs js landed:", chk);
})();
})();
