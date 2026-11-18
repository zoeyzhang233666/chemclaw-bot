/* ===================================================================
   企业产能分布研究报告 — 交互逻辑（零依赖原生 JS）
   所有数值来自 payload.agg（由 Python Aggregator 预计算）；
   前端不自行做跨口径相加，只做展示与筛选。
   =================================================================== */
(function () {
  "use strict";
  var P = JSON.parse(document.getElementById("payload").textContent);
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var ROUTE_COL = { carbide: "#ff7a45", ethylene: "#2fb4ff", mixed: "#b084ff", unknown: "#7d8ea6" };
  var ROUTE_NAME = { carbide: "电石法", ethylene: "乙烯法", mixed: "电石+乙烯", unknown: "未核实" };
  var STATUS_CLS = { running: "run", idle: "idle", maintenance: "maint", unknown: "unk", shutdown: "unk" };
  var STAGE_COL = {
    planned: "#5a6a7d", filed: "#8a7bd4", eia: "#c99a2e", construction: "#2f80c7",
    commissioning: "#2ba3d8", rampup: "#33d69f", operating: "#1e7b52",
    suspended: "#8a6a12", cancelled: "#7d3a3a"
  };

  // ---------- 全局筛选状态 ----------
  var S = {
    basis: "design",
    group: "", province: "", route: "", region: "", status: "",
    q: ""
  };

  var plantById = {};
  P.plants.forEach(function (p) { plantById[p.id] = p; });
  var groupById = {};
  P.groups.forEach(function (g) { groupById[g.id] = g; });

  function fmt(n, d) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    d = d === undefined ? 1 : d;
    return Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function pct(n, d) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    d = d === undefined ? 1 : d;
    return (Number(n) * 100).toFixed(d) + "%";
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function routeTag(r) {
    return '<span class="tag ' + ({ carbide: "c", ethylene: "e", mixed: "m", unknown: "u" }[r] || "u") + '">' +
      (ROUTE_NAME[r] || r) + "</span>";
  }
  function confTag(c) { return '<span class="tag ' + c + '">' + c + "</span>"; }

  // ---------- 当前口径与筛选后的装置 ----------
  function currentUnits(opts) {
    opts = opts || {};
    var agg = P.agg[S.basis];
    var allowed = agg ? agg.unit_ids : [];
    var set = {};
    allowed.forEach(function (u) { set[u] = 1; });
    return P.units.filter(function (u) {
      if (!set[u.uid]) return false;
      if (opts.ignoreGroup !== true && S.group && u.group_id !== S.group) return false;
      if (S.province && u.province !== S.province) return false;
      if (S.route && u.route !== S.route) return false;
      if (S.region && u.region !== S.region) return false;
      if (S.status && u.status !== S.status) return false;
      if (S.q) {
        var hay = (u.plant + u.entity + u.group + u.product + u.province + u.city + u.grade_class).toLowerCase();
        if (hay.indexOf(S.q.toLowerCase()) < 0) return false;
      }
      return true;
    });
  }

  // ===================================================================
  // 地图：SVG 中国省份 + 产能气泡
  // ===================================================================
  var MAP = { W: 1000, H: 690, lonMin: 72, lonMax: 136, latMin: 17, latMax: 54 };
  function proj(lat, lon) {
    var x = (lon - MAP.lonMin) / (MAP.lonMax - MAP.lonMin) * MAP.W;
    var y = (MAP.latMax - lat) / (MAP.latMax - MAP.latMin) * MAP.H;
    return [x, y];
  }

  function drawMap() {
    var svg = $("#map");
    if (!svg) return;
    var units = currentUnits();
    // 按基地聚合
    var agg = {};
    units.forEach(function (u) {
      var k = u.plant_id;
      if (!agg[k]) {
        var pl = plantById[k];
        agg[k] = { id: k, name: u.plant, lat: pl ? pl.lat : null, lon: pl ? pl.lon : null,
          entity: u.entity, group: u.group, group_id: u.group_id, province: u.province, city: u.city,
          cap: 0, routes: {}, products: {}, n: 0, precision: pl ? pl.precision : "city" };
      }
      if (u.capacity) agg[k].cap += u.capacity;
      agg[k].routes[u.route] = (agg[k].routes[u.route] || 0) + (u.capacity || 0);
      agg[k].products[u.product] = 1;
      agg[k].n++;
    });
    var list = Object.keys(agg).map(function (k) { return agg[k]; })
      .filter(function (p) { return p.lat != null && p.lon != null && p.cap > 0; });
    var maxCap = Math.max.apply(null, list.map(function (p) { return p.cap; }).concat([1]));

    // 省份汇总
    var provCap = {};
    list.forEach(function (p) { provCap[p.province] = (provCap[p.province] || 0) + p.cap; });
    var maxProv = Math.max.apply(null, Object.keys(provCap).map(function (k) { return provCap[k]; }).concat([1]));

    var parts = [];
    parts.push('<defs>');
    parts.push('<linearGradient id="gGrid" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#0b1728"/><stop offset="100%" stop-color="#071120"/></linearGradient>');
    parts.push('<radialGradient id="gGlow"><stop offset="0%" stop-color="#2fb4ff" stop-opacity=".55"/><stop offset="100%" stop-color="#2fb4ff" stop-opacity="0"/></radialGradient>');
    parts.push('</defs>');
    parts.push('<rect width="' + MAP.W + '" height="' + MAP.H + '" fill="url(#gGrid)" rx="10"/>');
    // 经纬网格
    for (var lo = 75; lo <= 135; lo += 10) {
      var xx = proj(0, lo)[0];
      parts.push('<line x1="' + xx + '" y1="0" x2="' + xx + '" y2="' + MAP.H + '" stroke="#14243c" stroke-width="1"/>');
      parts.push('<text x="' + (xx + 3) + '" y="' + (MAP.H - 6) + '" fill="#22405f" font-size="10">' + lo + '°E</text>');
    }
    for (var la = 20; la <= 50; la += 10) {
      var yy = proj(la, 0)[1];
      parts.push('<line x1="0" y1="' + yy + '" x2="' + MAP.W + '" y2="' + yy + '" stroke="#14243c" stroke-width="1"/>');
      parts.push('<text x="4" y="' + (yy - 4) + '" fill="#22405f" font-size="10">' + la + '°N</text>');
    }
    // 省界
    Object.keys(P.geo.provinces).forEach(function (prov) {
      var poly = P.geo.provinces[prov];
      var pts = poly.map(function (c) { var q = proj(c[1], c[0]); return q[0].toFixed(1) + "," + q[1].toFixed(1); }).join(" ");
      var v = provCap[prov] || 0;
      var fillOp = v > 0 ? (0.10 + 0.42 * (v / maxProv)) : 0.03;
      var isSel = S.province === prov;
      parts.push('<polygon points="' + pts + '" fill="rgba(47,128,199,' + fillOp.toFixed(3) + ')" stroke="' +
        (isSel ? "#6cd0ff" : "#24486f") + '" stroke-width="' + (isSel ? 1.8 : 0.8) + '" data-prov="' + esc(prov) + '" class="prov"/>');
    });
    // 省名（有产能的）
    Object.keys(P.geo.prov_center).forEach(function (prov) {
      var v = provCap[prov] || 0;
      if (!v) return;
      var c = P.geo.prov_center[prov];
      var q = proj(c[0], c[1]);
      var share = v / (list.reduce(function (a, b) { return a + b.cap; }, 0) || 1);
      parts.push('<text x="' + q[0] + '" y="' + (q[1] - 16) + '" fill="#7fa6cf" font-size="10.5" text-anchor="middle" pointer-events="none" opacity=".9">' +
        esc(prov.replace(/省|维吾尔自治区|回族自治区|壮族自治区|自治区|市/g, "")) + "</text>");
    });
    // 气泡
    list.sort(function (a, b) { return b.cap - a.cap; });
    list.forEach(function (p) {
      var q = proj(p.lat, p.lon);
      var r = 4 + 26 * Math.sqrt(p.cap / maxCap);
      var mainRoute = Object.keys(p.routes).sort(function (a, b) { return p.routes[b] - p.routes[a]; })[0] || "unknown";
      var col = ROUTE_COL[mainRoute] || ROUTE_COL.unknown;
      var gid = "bub_" + p.id;
      parts.push('<g class="bub" data-plant="' + esc(p.id) + '" style="cursor:pointer">');
      parts.push('<circle cx="' + q[0].toFixed(1) + '" cy="' + q[1].toFixed(1) + '" r="' + (r * 1.75).toFixed(1) + '" fill="' + col + '" opacity="0.10"/>');
      parts.push('<circle cx="' + q[0].toFixed(1) + '" cy="' + q[1].toFixed(1) + '" r="' + r.toFixed(1) +
        '" fill="' + col + '" fill-opacity="0.30" stroke="' + col + '" stroke-width="1.6"/>');
      parts.push('<circle cx="' + (q[0] - r * 0.28).toFixed(1) + '" cy="' + (q[1] - r * 0.30).toFixed(1) + '" r="' + (r * 0.36).toFixed(1) + '" fill="#ffffff" opacity="0.20"/>');
      if (r > 11) {
        parts.push('<text x="' + q[0].toFixed(1) + '" y="' + (q[1] + 3.4).toFixed(1) + '" fill="#fff" font-size="' + Math.min(11, r * 0.72).toFixed(1) +
          '" text-anchor="middle" font-weight="700" pointer-events="none">' + Math.round(p.cap) + "</text>");
      }
      parts.push("</g>");
    });
    svg.setAttribute("viewBox", "0 0 " + MAP.W + " " + MAP.H);
    svg.innerHTML = parts.join("");

    // 交互
    $$("#map .prov").forEach(function (el) {
      el.addEventListener("click", function () {
        var prov = el.getAttribute("data-prov");
        S.province = (S.province === prov) ? "" : prov;
        syncFilterUI();
        refreshAll();
      });
      el.addEventListener("mousemove", function (e) {
        var prov = el.getAttribute("data-prov");
        var v = provCap[prov] || 0;
        showTip(e, "<b>" + esc(prov) + "</b><div class='m'>当前筛选下产能 " + fmt(v) + " 万吨/年" +
          (v ? "（" + pct(v / (list.reduce(function (a, b) { return a + b.cap; }, 0) || 1)) + "）" : "") +
          "</div><div class='m'>点击" + (S.province === prov ? "取消" : "筛选") + "该省</div>");
      });
      el.addEventListener("mouseleave", hideTip);
    });
    $$("#map .bub").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.stopPropagation();
        openPlant(el.getAttribute("data-plant"));
      });
      el.addEventListener("mousemove", function (e) {
        var p = agg[el.getAttribute("data-plant")];
        var rt = Object.keys(p.routes).map(function (k) { return ROUTE_NAME[k] + " " + fmt(p.routes[k], 0); }).join(" / ");
        showTip(e, "<b>" + esc(p.name) + "</b><div class='m'>" + esc(p.entity) + "</div>" +
          "<div class='m'>" + esc(p.province + " " + p.city) + "</div>" +
          "<div style='margin-top:4px;color:#9fd6ff;font-family:var(--mono)'>" + fmt(p.cap) + " 万吨/年</div>" +
          "<div class='m'>" + rt + " · " + p.n + " 条装置记录</div>" +
          "<div class='m'>点击查看企业 / 基地 / 装置 / 来源</div>");
      });
      el.addEventListener("mouseleave", hideTip);
    });
  }

  function showTip(e, html) {
    var tip = $("#maptip");
    if (!tip) return;
    tip.innerHTML = html;
    tip.style.display = "block";
    var wrap = $("#mapwrap").getBoundingClientRect();
    var x = e.clientX - wrap.left + 16, y = e.clientY - wrap.top + 14;
    if (x + 300 > wrap.width) x = wrap.width - 310;
    if (y + 130 > wrap.height) y = Math.max(6, y - 140);
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }
  function hideTip() { var t = $("#maptip"); if (t) t.style.display = "none"; }

  // ===================================================================
  // 图表
  // ===================================================================
  function bars(el, items, opts) {
    if (!items.length) { el.innerHTML = '<div class="empty">当前筛选下无数据</div>'; return; }
    var max = Math.max.apply(null, items.map(function (i) { return i.v; }).concat([1]));
    var total = items.reduce(function (a, b) { return a + b.v; }, 0);
    var h = items.map(function (it) {
      var w = Math.max(1.5, 100 * it.v / max);
      var cls = it.cls || "pk";
      return '<div class="bar-row" data-k="' + esc(it.k) + '" data-kind="' + (opts.kind || "") + '">' +
        '<div class="lab">' + (it.bold ? "<b>" + esc(it.label) + "</b>" : esc(it.label)) + "</div>" +
        '<div class="bar-track"><div class="bar-fill ' + cls + '" style="width:' + w.toFixed(1) + '%"></div></div>' +
        '<div class="bar-val">' + fmt(it.v) + "<small>" + pct(it.v / (total || 1)) + "</small></div></div>";
    }).join("");
    el.innerHTML = '<div class="bars">' + h + "</div>";
    if (opts.onClick) {
      $$(".bar-row", el).forEach(function (row) {
        row.addEventListener("click", function () { opts.onClick(row.getAttribute("data-k")); });
      });
    }
  }

  // 环形图（SVG）
  function donut(el, items, opts) {
    var total = items.reduce(function (a, b) { return a + b.v; }, 0);
    if (!total) { el.innerHTML = '<div class="empty">无数据</div>'; return; }
    var R = 74, r = 46, cx = 86, cy = 86, a0 = -Math.PI / 2;
    var paths = [];
    items.forEach(function (it) {
      var a1 = a0 + 2 * Math.PI * (it.v / total);
      var large = (a1 - a0) > Math.PI ? 1 : 0;
      var x0 = cx + R * Math.cos(a0), y0 = cy + R * Math.sin(a0);
      var x1 = cx + R * Math.cos(a1), y1 = cy + R * Math.sin(a1);
      var xi0 = cx + r * Math.cos(a1), yi0 = cy + r * Math.sin(a1);
      var xi1 = cx + r * Math.cos(a0), yi1 = cy + r * Math.sin(a0);
      paths.push('<path d="M' + x0.toFixed(2) + ' ' + y0.toFixed(2) + ' A' + R + ' ' + R + ' 0 ' + large + ' 1 ' + x1.toFixed(2) + ' ' + y1.toFixed(2) +
        ' L' + xi0.toFixed(2) + ' ' + yi0.toFixed(2) + ' A' + r + ' ' + r + ' 0 ' + large + ' 0 ' + xi1.toFixed(2) + ' ' + yi1.toFixed(2) + ' Z" fill="' +
        it.color + '" opacity=".88" stroke="#0b1626" stroke-width="1.5"/>');
      a0 = a1;
    });
    var legend = items.map(function (it) {
      return '<div class="row"><span class="dotl" style="background:' + it.color + '"></span>' +
        '<span style="flex:1">' + esc(it.label) + '</span><span class="mono" style="color:#dfe9f7">' + fmt(it.v) + '</span>' +
        '<span class="mono" style="color:#6f88a8;margin-left:6px">' + pct(it.v / total) + "</span></div>";
    }).join("");
    el.innerHTML = '<div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap">' +
      '<svg width="176" height="176" viewBox="0 0 172 172">' + paths.join("") +
      '<text x="86" y="80" text-anchor="middle" fill="#8aa6c4" font-size="11">合计</text>' +
      '<text x="86" y="101" text-anchor="middle" fill="#e8eef8" font-size="17" font-weight="700">' + fmt(total, 0) + "</text>" +
      '<text x="86" y="116" text-anchor="middle" fill="#6f88a8" font-size="9.5">万吨/年</text></svg>' +
      '<div style="flex:1;min-width:210px;font-size:12px;color:#a9bcd6">' + legend + "</div></div>";
  }

  // 堆叠时间轴（SVG 柱）
  function yearChart(el) {
    var yrs = Object.keys(P.by_year);
    if (!yrs.length) { el.innerHTML = '<div class="empty">无项目数据</div>'; return; }
    var maxV = 1;
    yrs.forEach(function (y) {
      var d = P.by_year[y];
      maxV = Math.max(maxV, d.gross, d.carbide + d.ethylene);
    });
    var W = 760, H = 210, pad = 34, bw = Math.min(64, (W - pad * 2) / yrs.length * 0.62);
    var parts = ['<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto">'];
    for (var i = 0; i <= 4; i++) {
      var y = 12 + (H - 58) * i / 4;
      parts.push('<line x1="' + pad + '" y1="' + y + '" x2="' + (W - 10) + '" y2="' + y + '" stroke="#16273e"/>');
      parts.push('<text x="' + (pad - 6) + '" y="' + (y + 3.5) + '" text-anchor="end" fill="#4d6480" font-size="9.5">' +
        fmt(maxV * (1 - i / 4), 0) + "</text>");
    }
    var step = (W - pad * 2) / yrs.length;
    yrs.forEach(function (yr, i) {
      var d = P.by_year[yr];
      var cx = pad + step * (i + 0.5);
      var hC = (d.carbide / maxV) * (H - 58);
      var hE = (d.ethylene / maxV) * (H - 58);
      var base = H - 46;
      if (hC > 0.5) parts.push('<rect x="' + (cx - bw / 2) + '" y="' + (base - hC) + '" width="' + bw + '" height="' + hC +
        '" fill="#ff7a45" opacity=".85" rx="2"><title>' + yr + " 电石法 " + fmt(d.carbide) + "</title></rect>");
      if (hE > 0.5) parts.push('<rect x="' + (cx - bw / 2) + '" y="' + (base - hC - hE) + '" width="' + bw + '" height="' + hE +
        '" fill="#2fb4ff" opacity=".85" rx="2"><title>' + yr + " 乙烯法 " + fmt(d.ethylene) + "</title></rect>");
      var tot = d.gross;
      parts.push('<text x="' + cx + '" y="' + (base - hC - hE - 6) + '" text-anchor="middle" fill="#cfe0f4" font-size="10.5" font-weight="600">' +
        (tot ? fmt(tot, 0) : "—") + "</text>");
      parts.push('<text x="' + cx + '" y="' + (base + 15) + '" text-anchor="middle" fill="#7f97b3" font-size="11">' + esc(yr) + "</text>");
      parts.push('<text x="' + cx + '" y="' + (base + 29) + '" text-anchor="middle" fill="#4d6480" font-size="9.5">' + d.count + " 项</text>");
    });
    parts.push("</svg>");
    el.innerHTML = parts.join("");
  }

  // ===================================================================
  // 表格
  // ===================================================================
  function renderGroupTable() {
    var units = currentUnits();
    var cap = {};
    units.forEach(function (u) {
      var k = u.group_id || "__none__";
      cap[k] = (cap[k] || 0) + (u.capacity || 0);
    });
    var total = Object.keys(cap).reduce(function (a, k) { return a + cap[k]; }, 0);
    var rows = [];
    P.groups.forEach(function (g) {
      var v = cap[g.id] || 0;
      if (!v) return;
      var routes = {};
      units.filter(function (u) { return u.group_id === g.id; }).forEach(function (u) {
        routes[u.route] = (routes[u.route] || 0) + (u.capacity || 0);
      });
      rows.push({
        id: g.id, name: g.short, full: g.name, ctrl: g.controller, type: g.type,
        cap: v, share: v / (total || 1), ents: g.entities.length, plants: g.plant_ids.length,
        provs: g.provinces.join("、"), routes: routes
      });
    });
    rows.sort(function (a, b) { return b.cap - a.cap; });
    var html = rows.map(function (r, i) {
      var rt = Object.keys(r.routes).sort(function (a, b) { return r.routes[b] - r.routes[a]; })
        .map(function (k) { return routeTag(k) + ' <span class="mono muted">' + fmt(r.routes[k], 0) + "</span>"; }).join(" ");
      return '<tr data-group="' + esc(r.id) + '">' +
        '<td class="num">' + (i + 1) + "</td>" +
        "<td><b>" + esc(r.name) + "</b><div class='small muted'>" + esc(r.full) + "</div></td>" +
        "<td class='small'>" + esc(r.ctrl) + "<div class='muted'>" + esc(r.type) + "</div></td>" +
        '<td class="num">' + fmt(r.cap) + "</td>" +
        '<td class="num">' + pct(r.share) + "</td>" +
        '<td class="num">' + r.ents + "</td>" +
        '<td class="num">' + r.plants + "</td>" +
        "<td class='small'>" + esc(r.provs) + "</td>" +
        "<td>" + rt + "</td></tr>";
    }).join("");
    $("#tb-group").innerHTML = html || '<tr><td colspan="9" class="empty">无数据</td></tr>';
    $$("#tb-group tr[data-group]").forEach(function (tr) {
      tr.addEventListener("click", function () { openGroup(tr.getAttribute("data-group")); });
    });
    $("#group-count").textContent = rows.length;
  }

  function renderUnitTable() {
    var units = currentUnits().slice().sort(function (a, b) {
      return (b.capacity || 0) - (a.capacity || 0);
    });
    var html = units.map(function (u) {
      return "<tr data-unit='" + esc(u.uid) + "' data-plant='" + esc(u.plant_id) + "'>" +
        "<td class='small mono'>" + esc(u.uid) + "</td>" +
        "<td><b>" + esc(u.plant) + "</b><div class='small muted'>" + esc(u.entity) + "</div></td>" +
        "<td class='small nowrap'>" + esc(u.province) + "<div class='muted'>" + esc(u.city) + "</div></td>" +
        "<td>" + esc(u.product) + "<div class='small muted'>" + esc(u.grade_class) + "</div></td>" +
        "<td>" + routeTag(u.route) + "</td>" +
        '<td class="num">' + fmt(u.capacity) + "</td>" +
        '<td class="small">' + esc(u.basis_label) + "</td>" +
        '<td class="num">' + (u.start_year || "—") + "</td>" +
        "<td><span class='tag " + (STATUS_CLS[u.status] || "unk") + "'>" + esc(u.status_label) + "</span></td>" +
        "<td class='small'><a href='" + esc(u.source_url || "#") + "' target='_blank' rel='noopener'>" + esc(u.source_id) + "</a> " +
        confTag(u.confidence) + "</td></tr>";
    }).join("");
    $("#tb-unit").innerHTML = html || '<tr><td colspan="10" class="empty">无数据</td></tr>';
    $$("#tb-unit tr[data-unit]").forEach(function (tr) {
      tr.addEventListener("click", function () { openPlant(tr.getAttribute("data-plant")); });
    });
    $("#unit-count").textContent = units.length;
    var sum = units.reduce(function (a, b) { return a + (b.capacity || 0); }, 0);
    $("#unit-sum").textContent = fmt(sum);
    $("#unit-basis").textContent = (P.agg[S.basis] || {}).basis_label || "";
  }

  function renderProjTable() {
    var list = P.projects.filter(function (p) {
      if (S.region && p.region !== S.region) return false;
      if (S.province && p.province !== S.province) return false;
      if (S.route && p.route !== S.route) return false;
      if (S.group && P.groups.some(function (g) { return g.short === S.group || g.id === S.group; })) {
        var g = groupById[S.group];
        if (g && p.group !== g.short) return false;
      }
      if (S.q) {
        var hay = (p.name + p.entity + p.group + p.city + p.note).toLowerCase();
        if (hay.indexOf(S.q.toLowerCase()) < 0) return false;
      }
      return true;
    });
    list.sort(function (a, b) { return (a.expected_year || 9999) - (b.expected_year || 9999); });
    var html = list.map(function (p) {
      return "<tr data-proj='" + esc(p.id) + "'>" +
        "<td class='small'>" + esc(p.name) + "<div class='muted'>" + esc(p.entity) + "</div></td>" +
        "<td class='small nowrap'>" + esc(p.province) + "<div class='muted'>" + esc(p.city) + "</div></td>" +
        "<td>" + routeTag(p.route) + "</td>" +
        '<td class="num">' + fmt(p.capacity) + "</td>" +
        "<td><span class='tag' style='background:" + (STAGE_COL[p.stage] || "#444") + "22;border:1px solid " +
        (STAGE_COL[p.stage] || "#444") + ";color:" + (STAGE_COL[p.stage] || "#ccc") + "'>" + esc(p.stage_label) + "</span></td>" +
        '<td class="small nowrap">' + esc(p.expected_period || (p.expected_year || "未定")) + "</td>" +
        '<td class="num">' + (p.retired != null ? fmt(p.retired) : "—") + "</td>" +
        '<td class="num">' + (p.net != null ? fmt(p.net) : "—") + "</td>" +
        "<td class='small'>" + (p.source_ids || []).map(function (s) { return "<span class='mono'>" + esc(s) + "</span>"; }).join(" ") +
        " " + confTag(p.confidence) + "</td></tr>";
    }).join("");
    $("#tb-proj").innerHTML = html || '<tr><td colspan="9" class="empty">无数据</td></tr>';
    $$("#tb-proj tr[data-proj]").forEach(function (tr) {
      tr.addEventListener("click", function () { openProject(tr.getAttribute("data-proj")); });
    });
  }

  // ===================================================================
  // 抽屉
  // ===================================================================
  function openDrawer(html) {
    $("#drawer-body").innerHTML = html;
    $("#drawer").classList.add("on");
    $("#overlay").classList.add("on");
  }
  function closeDrawer() {
    $("#drawer").classList.remove("on");
    $("#overlay").classList.remove("on");
  }

  function unitRow(u) {
    return '<div class="uitem"><div class="u1">' + esc(u.product) + " · " + esc(u.grade_class) + " " + routeTag(u.route) + "</div>" +
      '<div class="u2">' + fmt(u.capacity) + " 万吨/年</div>" +
      '<div class="u3">' + esc(u.basis_label) + " · " + (u.start_year ? "投产 " + u.start_year : "投产年份未知") +
      " · <span class='tag " + (STATUS_CLS[u.status] || "unk") + "'>" + esc(u.status_label) + "</span>" +
      (u.status_note ? " " + esc(u.status_note) : "") + "</div>" +
      '<div class="u3">原文表述：' + esc(u.capacity_note || "—") + "</div>" +
      '<div class="u3">来源 <a href="' + esc(u.source_url || "#") + '" target="_blank" rel="noopener">' + esc(u.source_id) +
      "</a> " + esc(u.source_title) + " " + confTag(u.confidence) + "</div></div>";
  }

  function openGroup(gid) {
    var g = groupById[gid];
    if (!g) return;
    var units = currentUnits().filter(function (u) { return u.group_id === gid; });
    var cap = units.reduce(function (a, b) { return a + (b.capacity || 0); }, 0);
    var total = (P.agg[S.basis] || {}).total || 1;
    var byPlant = {};
    units.forEach(function (u) {
      if (!byPlant[u.plant_id]) byPlant[u.plant_id] = { name: u.plant, prov: u.province, city: u.city, cap: 0, us: [] };
      byPlant[u.plant_id].cap += (u.capacity || 0);
      byPlant[u.plant_id].us.push(u);
    });
    var h = '<div class="subsec"><h4>集团概况</h4><dl class="kv">' +
      "<dt>集团全称</dt><dd>" + esc(g.name) + "</dd>" +
      "<dt>实际控制人</dt><dd>" + esc(g.controller || "—") + "</dd>" +
      "<dt>集团性质</dt><dd>" + esc(g.type || "—") + "</dd>" +
      "<dt>样本产能</dt><dd class='mono' style='color:#9fd6ff'>" + fmt(cap) + " 万吨/年（占样本 " + pct(cap / total) + "）</dd>" +
      "<dt>下属法人</dt><dd>" + g.entities.length + " 家 · 基地 " + Object.keys(byPlant).length + " 个</dd>" +
      "</dl>" + (g.note ? '<div class="callout info" style="margin-top:10px">' + esc(g.note) + "</div>" : "") + "</div>";

    h += '<div class="subsec"><h4>企业 → 集团 关系</h4>';
    g.entities.forEach(function (e) {
      var eCap = units.filter(function (u) { return u.entity === e.name; })
        .reduce(function (a, b) { return a + (b.capacity || 0); }, 0);
      h += '<div class="plantcard"><div class="ph"><b>' + esc(e.name) + "</b>" +
        (e.stock ? "<span class='tag e'>" + esc(e.stock) + "</span>" : "") +
        (e.ownership ? "<span class='small muted'>" + esc(e.ownership) + "</span>" : "") +
        "<span class='mono' style='margin-left:auto;color:#9fd6ff'>" + fmt(eCap) + " 万吨/年</span></div>" +
        "<div class='small muted'>法人类型：" + esc(e.type) + (e.code ? " · 统一社会信用代码 " + esc(e.code) : "") + "</div>" +
        (e.verified_by ? "<div class='small muted'>核验依据：" + esc(e.verified_by) + "</div>" : "") + "</div>";
    });
    h += "</div>";

    h += '<div class="subsec"><h4>生产基地与装置</h4>';
    Object.keys(byPlant).sort(function (a, b) { return byPlant[b].cap - byPlant[a].cap; }).forEach(function (pid) {
      var p = byPlant[pid];
      h += '<div class="plantcard"><div class="ph"><b>' + esc(p.name) + "</b>" +
        "<span class='small muted'>" + esc(p.prov + " " + p.city) + "</span>" +
        "<span class='mono' style='margin-left:auto;color:#9fd6ff'>" + fmt(p.cap) + " 万吨/年</span></div>" +
        '<div class="units">' + p.us.map(unitRow).join("") + "</div></div>";
    });
    h += "</div>";
    openDrawer(h);
  }

  function openPlant(pid) {
    var p = plantById[pid];
    if (!p) return;
    var units = P.units.filter(function (u) { return u.plant_id === pid; });
    var capByBasis = {};
    units.forEach(function (u) { capByBasis[u.basis] = (capByBasis[u.basis] || 0) + (u.capacity || 0); });
    var g = groupById[p.group_id];
    var h = '<div class="subsec"><h4>基地信息</h4><dl class="kv">' +
      "<dt>基地名称</dt><dd>" + esc(p.name_full) + "</dd>" +
      "<dt>运营法人</dt><dd>" + esc(p.entity) + "</dd>" +
      "<dt>所属集团</dt><dd>" + esc(p.group) + (g ? "（" + esc(g.controller) + "）" : "") + "</dd>" +
      "<dt>位置</dt><dd>" + esc(p.location) + "</dd>" +
      "<dt>园区/地址</dt><dd>" + esc(p.park || p.address || "—") + "</dd>" +
      "<dt>坐标精度</dt><dd>" + esc({ plant: "厂址级", city: "城市级", province: "省中心" }[p.precision] || p.precision) +
      "（" + (p.lat != null ? p.lat.toFixed(3) + ", " + p.lon.toFixed(3) : "未知") + "）</dd>" +
      "<dt>产能（各口径）</dt><dd>" + Object.keys(capByBasis).map(function (k) {
        return '<span class="mono">' + fmt(capByBasis[k]) + "</span> " +
          (P.units.filter(function (u) { return u.basis === k; }).length >= 0 ? "" : "") +
          ' <span class="small muted">' + k + "</span>";
      }).join(" &nbsp;|&nbsp; ") + "</dd></dl></div>";

    h += '<div class="subsec"><h4>装置明细（' + units.length + " 条）</h4>" +
      units.map(unitRow).join("") + "</div>";

    // 集团其他同类厂
    if (p.group_id) {
      var sib = P.plants.filter(function (x) { return x.group_id === p.group_id && x.id !== pid; });
      if (sib.length) {
        h += '<div class="subsec"><h4>同集团其他基地（产能不重复计入）</h4>' +
          sib.map(function (s) {
            return "<div class='small' style='padding:3px 0;border-bottom:1px dashed #16273c'>" +
              esc(s.name) + " <span class='muted'>" + esc(s.province + s.city) + "</span></div>";
          }).join("") + "</div>";
      }
    }
    openDrawer(h);
  }

  function openProject(pid) {
    var p = null;
    P.projects.forEach(function (x) { if (x.id === pid) p = x; });
    if (!p) return;
    var tl = (p.timeline || []).map(function (t) {
      return '<div class="it past"><div class="d">' + esc(t.date || "") + "</div><div class='e'>" + esc(t.event || "") + "</div>" +
        (t.note ? "<div class='n'>" + esc(t.note) + "</div>" : "") + "</div>";
    }).join("");
    var srcs = (p.source_ids || []).map(function (sid) {
      var s = null;
      P.sources.forEach(function (x) { if (x.id === sid) s = x; });
      return s ? "<div class='small' style='padding:4px 0;border-bottom:1px dashed #16273c'>" +
        "<span class='mono'>" + esc(s.id) + "</span> " + confTag(s.confidence) +
        " <a href='" + esc(s.url) + "' target='_blank' rel='noopener'>" + esc(s.title) + "</a>" +
        "<div class='muted'>" + esc(s.org) + " · " + esc(s.date) + "</div></div>" : "";
    }).join("");
    var h = '<div class="subsec"><h4>项目信息</h4><dl class="kv">' +
      "<dt>项目名称</dt><dd>" + esc(p.name) + "</dd>" +
      "<dt>建设单位</dt><dd>" + esc(p.entity) + "</dd>" +
      "<dt>所属集团</dt><dd>" + esc(p.group) + "</dd>" +
      "<dt>地点</dt><dd>" + esc(p.province + " " + p.city) + "</dd>" +
      "<dt>工艺路线</dt><dd>" + routeTag(p.route) + "</dd>" +
      "<dt>规模</dt><dd class='mono' style='color:#9fd6ff'>" + fmt(p.capacity) + " 万吨/年</dd>" +
      "<dt>原文表述</dt><dd>" + esc(p.capacity_note || "—") + "</dd>" +
      "<dt>建设阶段</dt><dd>" + esc(p.stage_label) + "</dd>" +
      "<dt>预计投产</dt><dd>" + esc(p.expected_period || (p.expected_year || "未定")) + "</dd>" +
      "<dt>置换退出</dt><dd>" + (p.retired != null ? fmt(p.retired) + " 万吨/年" : "未披露/无") +
      (p.replacement_note ? " · " + esc(p.replacement_note) : "") + "</dd>" +
      "<dt>净新增</dt><dd class='mono'>" + (p.net != null ? fmt(p.net) + " 万吨/年" : "无法确认") + "</dd>" +
      "<dt>投资额</dt><dd>" + esc(p.capex || "—") + "</dd>" +
      "<dt>可信度</dt><dd>" + confTag(p.confidence) + "</dd></dl>" +
      (p.note ? '<div class="callout info" style="margin-top:10px">' + esc(p.note) + "</div>" : "") + "</div>";
    if (tl) h += '<div class="subsec"><h4>进展时间线</h4><div class="tl">' + tl + "</div></div>";
    if (srcs) h += '<div class="subsec"><h4>来源</h4>' + srcs + "</div>";
    openDrawer(h);
  }

  // ===================================================================
  // 刷新
  // ===================================================================
  function refreshAll() {
    var agg = P.agg[S.basis];
    if (!agg) { return; }
    drawMap();
    renderGroupTable();
    renderUnitTable();
    renderProjTable();
    renderRegionStack();

    // 省份条形
    var units = currentUnits();
    var pv = {};
    units.forEach(function (u) { pv[u.province] = (pv[u.province] || 0) + (u.capacity || 0); });
    var items = Object.keys(pv).map(function (k) { return { k: k, label: k, v: pv[k] }; })
      .sort(function (a, b) { return b.v - a.v; });
    bars($("#bar-prov"), items, {
      kind: "prov", onClick: function (k) { S.province = (S.province === k ? "" : k); syncFilterUI(); refreshAll(); }
    });

    // 集团条形
    var gv = {};
    units.forEach(function (u) { if (u.group_id) gv[u.group_id] = (gv[u.group_id] || 0) + (u.capacity || 0); });
    var gItems = Object.keys(gv).map(function (k) {
      var g = groupById[k];
      return { k: k, label: (g ? g.short : k) + "（" + (g ? g.entities.length : 0) + "家法人）", v: gv[k], bold: true };
    }).sort(function (a, b) { return b.v - a.v; }).slice(0, 12);
    bars($("#bar-group"), gItems, { kind: "group", onClick: function (k) { openGroup(k); } });

    // 工艺环形
    var rv = {};
    units.forEach(function (u) { rv[u.route] = (rv[u.route] || 0) + (u.capacity || 0); });
    donut($("#donut-route"), Object.keys(rv).sort(function (a, b) { return rv[b] - rv[a]; }).map(function (k) {
      return { label: ROUTE_NAME[k] || k, v: rv[k], color: ROUTE_COL[k] };
    }));

    // 区域条形
    var regv = {};
    units.forEach(function (u) { regv[u.region] = (regv[u.region] || 0) + (u.capacity || 0); });
    bars($("#bar-region"), Object.keys(regv).map(function (k) { return { k: k, label: k, v: regv[k] }; })
      .sort(function (a, b) { return b.v - a.v; }), {
      kind: "region", onClick: function (k) { S.region = (S.region === k ? "" : k); syncFilterUI(); refreshAll(); }
    });

    // 产品等级
    var gr = {};
    units.forEach(function (u) { gr[u.grade_class || "未分级"] = (gr[u.grade_class || "未分级"] || 0) + (u.capacity || 0); });
    bars($("#bar-grade"), Object.keys(gr).map(function (k) { return { k: k, label: k, v: gr[k], cls: "g" }; })
      .sort(function (a, b) { return b.v - a.v; }), {});

    // KPI 重算（当前筛选）
    var tot = units.reduce(function (a, b) { return a + (b.capacity || 0); }, 0);
    var gCount = Object.keys(gv).length;
    var vals = Object.keys(gv).map(function (k) { return gv[k]; }).sort(function (a, b) { return b - a; });
    var cr5 = vals.slice(0, 5).reduce(function (a, b) { return a + b; }, 0) / (tot || 1);
    var hhi = vals.reduce(function (a, b) { return a + Math.pow(b / (tot || 1) * 100, 2); }, 0);
    var sol = rv.carbide || 0, eth = rv.ethylene || 0;
    setText("#kpi-cap", fmt(tot));
    setText("#kpi-cap-d", "口径：" + (agg.basis_label || BASIS_NAME[S.basis]) + " · " + units.length + " 条装置记录");
    setText("#kpi-ents", P.groups.length + " / " + P.groups.reduce(function (a, g) { return a + g.entities.length; }, 0));
    setText("#kpi-ents-d", "样本集团数 / 法人主体数（不随筛选变化）");
    setText("#kpi-cr5", pct(cr5));
    setText("#kpi-cr5-d", "HHI " + fmt(hhi, 0) + " · " + concLabel(hhi));
    setText("#kpi-route", sol && eth ? fmt(sol / (sol + eth) * 100, 1) + "%" : (sol ? "100%" : "—"));
    setText("#kpi-route-d", "电石法 " + fmt(sol, 0) + " / 乙烯法 " + fmt(eth, 0) + " 万吨（未计未核实）");
    var covTxt = "—";
    setText("#kpi-cov", P.meta.coverage || "—");
    setText("#kpi-cov-d", P.meta.coverage_note || "样本合计 ≠ 全国总产能");

    var chips = [];
    if (S.group) chips.push("集团 " + (groupById[S.group] ? groupById[S.group].short : S.group));
    if (S.province) chips.push("省份 " + S.province);
    if (S.route) chips.push("工艺 " + ROUTE_NAME[S.route]);
    if (S.region) chips.push("区域 " + S.region);
    if (S.status) chips.push("状态 " + S.status);
    if (S.q) chips.push("检索 " + S.q);
    $("#active-filters").innerHTML = chips.length ?
      chips.map(function (c) { return "<span class='chip on'>" + esc(c) + "</span>"; }).join(" ") :
      "<span class='small muted'>未设置筛选 · 显示全部样本</span>";
  }

  var BASIS_NAME = { design: "设计产能", effective: "有效产能", approved: "核定产能", actual: "实际产量" };
  function concLabel(h) {
    if (h < 1000) return "分散";
    if (h < 1800) return "中度集中";
    return "高度集中";
  }
  function setText(sel, t) { var e = $(sel); if (e) e.textContent = t; }

  function syncFilterUI() {
    var sel = $("#f-group");
    if (sel) sel.value = S.group || "";
    var sel2 = $("#f-prov");
    if (sel2) sel2.value = S.province || "";
    var sel3 = $("#f-route");
    if (sel3) sel3.value = S.route || "";
    var sel4 = $("#f-status");
    if (sel4) sel4.value = S.status || "";
    $$(".seg button[data-basis]").forEach(function (b) {
      b.classList.toggle("on", b.getAttribute("data-basis") === S.basis);
    });
  }

  // ===================================================================
  // 图表补充：地区占比（堆叠）
  // ===================================================================
  function renderRegionStack() {
    var units = currentUnits();
    var provs = {};
    units.forEach(function (u) {
      if (!provs[u.province]) provs[u.province] = { cap: 0, routes: {} };
      provs[u.province].cap += (u.capacity || 0);
      provs[u.province].routes[u.route] = (provs[u.province].routes[u.route] || 0) + (u.capacity || 0);
    });
    var keys = Object.keys(provs).sort(function (a, b) { return provs[b].cap - provs[a].cap; });
    var maxV = Math.max.apply(null, keys.map(function (k) { return provs[k].cap; }).concat([1]));
    var html = keys.map(function (k) {
      var d = provs[k];
      var segs = Object.keys(d.routes).sort(function (a, b) { return d.routes[b] - d.routes[a]; }).map(function (r) {
        return '<div style="width:' + (100 * d.routes[r] / d.cap).toFixed(2) + "%;background:" + ROUTE_COL[r] +
          '" title="' + ROUTE_NAME[r] + " " + fmt(d.routes[r]) + '"></div>';
      }).join("");
      return '<div class="bar-row" data-prov-bar="' + esc(k) + '">' +
        '<div class="lab">' + esc(k) + "</div>" +
        '<div class="bar-track" style="display:flex;overflow:hidden;height:21px;background:#0c1929">' + segs + "</div>" +
        '<div class="bar-val">' + fmt(d.cap) + "</div></div>";
    }).join("");
    $("#stack-prov").innerHTML = keys.length ? '<div class="bars">' + html + "</div>" :
      '<div class="empty">无数据</div>';
    $$("#stack-prov .bar-row").forEach(function (r) {
      r.addEventListener("click", function () {
        var k = r.getAttribute("data-prov-bar");
        S.province = (S.province === k ? "" : k); syncFilterUI(); refreshAll();
      });
    });
  }

  // ===================================================================
  // 初始化
  // ===================================================================
  function init() {
    // 筛选下拉
    var gsel = $("#f-group");
    P.groups.slice().sort(function (a, b) { return a.short.localeCompare(b.short, "zh"); }).forEach(function (g) {
      var o = document.createElement("option");
      o.value = g.id; o.textContent = g.short + "（" + g.entities.length + " 家法人）";
      gsel.appendChild(o);
    });
    var psel = $("#f-prov");
    var provs = Array.from(new Set(P.plants.map(function (p) { return p.province; }))).sort();
    provs.forEach(function (p) {
      var o = document.createElement("option"); o.value = p; o.textContent = p; psel.appendChild(o);
    });
    gsel.addEventListener("change", function () { S.group = gsel.value; refreshAll(); });
    psel.addEventListener("change", function () { S.province = psel.value; refreshAll(); });
    $("#f-route").addEventListener("change", function () { S.route = this.value; refreshAll(); });
    $("#f-status").addEventListener("change", function () { S.status = this.value; refreshAll(); });
    var q = $("#f-q");
    var t = null;
    q.addEventListener("input", function () {
      clearTimeout(t);
      t = setTimeout(function () { S.q = q.value.trim(); refreshAll(); }, 220);
    });
    $("#f-reset").addEventListener("click", function () {
      S.group = S.province = S.route = S.region = S.status = S.q = "";
      q.value = ""; syncFilterUI(); refreshAll();
    });
    $$(".seg button[data-basis]").forEach(function (b) {
      b.addEventListener("click", function () {
        var b2 = b.getAttribute("data-basis");
        if (!P.agg[b2]) { alert("该口径在本样本中没有数据（未采集到有效产能/实际产量）。"); return; }
        S.basis = b2; syncFilterUI(); refreshAll();
      });
    });
    // 标签页
    $$(".tab").forEach(function (tb) {
      tb.addEventListener("click", function () {
        var id = tb.getAttribute("data-tab");
        $$(".tab").forEach(function (x) { x.classList.toggle("on", x === tb); });
        $$(".tab-page").forEach(function (pg) { pg.classList.toggle("hide", pg.id !== "tab-" + id); });
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    });
    $("#overlay").addEventListener("click", closeDrawer);
    $("#drawer-x").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrawer(); });

    // 流水线卡片
    var pipe = $("#pipe");
    if (pipe) {
      var order = ["planned", "filed", "eia", "construction", "commissioning", "rampup"];
      pipe.innerHTML = order.filter(function (k) { return P.pipeline[k]; }).map(function (k) {
        var d = P.pipeline[k];
        return '<div class="pcol"><div class="w" style="width:100%;background:' + STAGE_COL[k] + '"></div>' +
          '<div class="t">' + esc(d.label) + "<span class='mono'>" + d.count + " 项</span></div>" +
          '<div class="n" style="color:' + STAGE_COL[k] + '">' + (d.gross ? fmt(d.gross, 0) : "—") + "</div>" +
          '<div class="s">万吨/年（毛）' + (d.retired ? " · 置换退出 " + fmt(d.retired, 0) : "") + "</div>" +
          '<div class="s">净增 ' + (d.net != null ? fmt(d.net, 0) : "待确认") + " 万吨/年</div></div>";
      }).join("");
    }
    yearChart($("#year-chart"));
    refreshAll();
    // 来源表
    var st = $("#tb-src");
    if (st) {
      st.innerHTML = P.sources.map(function (s) {
        return "<tr><td class='mono'>" + esc(s.id) + "</td><td>" + esc(s.type) + "</td>" +
          "<td><a href='" + esc(s.url) + "' target='_blank' rel='noopener'>" + esc(s.title) + "</a></td>" +
          "<td class='small'>" + esc(s.org) + "</td><td class='small mono'>" + esc(s.date) + "</td>" +
          "<td>" + confTag(s.confidence) + "</td></tr>";
      }).join("");
    }
    // 缺口表
    var gt = $("#tb-gap");
    if (gt) {
      gt.innerHTML = P.gaps.map(function (g) {
        return "<tr><td class='mono'>" + esc(g.id) + "</td><td>" + esc(g.item) + "</td>" +
          "<td class='small'>" + esc(g.affects) + "</td><td class='small'>" + esc(g.status) + "</td>" +
          "<td class='small'>" + esc(g.how_to_fill) + "</td><td>" + esc(g.priority) + "</td></tr>";
      }).join("");
    }
    // 口径对比表
    var bt = $("#tb-bench");
    if (bt) {
      bt.innerHTML = P.benchmarks.map(function (b) {
        return "<tr><td class='mono'>" + esc(b.id) + "</td><td>" + esc(b.metric) + "</td>" +
          "<td class='num'>" + fmt(b.value, 0) + "</td><td class='small'>" + esc(b.unit) + "</td>" +
          "<td class='small mono'>" + esc(b.year) + "</td><td class='small'>" + esc(b.source_org || "") + "</td>" +
          "<td>" + confTag(b.confidence) + "</td><td class='small'>" + esc(b.definition || b.note || "") + "</td></tr>";
      }).join("");
    }
    // 校验表（若有）
    if (P.checks && P.checks.length && $("#tb-check")) {
      $("#tb-check").innerHTML = P.checks.map(function (c) {
        var col = { ERROR: "#ff5c5c", WARN: "#ffb020", INFO: "#59a5ff" }[c.severity] || "#888";
        return "<tr><td class='mono'>" + esc(c.rule) + "</td><td><span class='tag' style='color:" + col +
          ";border:1px solid " + col + "22;background:" + col + "18'>" + esc(c.severity) + "</span></td>" +
          "<td class='small'>" + esc(c.subject) + "</td><td class='small'>" + esc(c.message) + "</td>" +
          "<td class='small muted'>" + esc(c.fix || "") + "</td></tr>";
      }).join("");
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
