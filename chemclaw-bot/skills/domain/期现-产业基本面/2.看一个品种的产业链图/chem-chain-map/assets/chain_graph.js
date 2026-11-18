/* chain_graph.js — 产业链图谱交互运行时
 * 约定：坐标全部来自 window.CHAIN_DATA.layout（Python 端 chain_layout.py 预算），
 *       本文件只负责绘制、交互与派生查询，不再自行推算行列，确保与校验端一致。
 * 暴露 window.CHAIN 供自动化测试与外部脚本调用。
 */
(function () {
  "use strict";

  var D = window.CHAIN_DATA || {};
  var LAY = D.layout || { canvas: { w: 1000, h: 600 }, nodes: [], edges: [], columns: [] };
  var NODES = D.nodes || [];
  var RELS = D.relations || [];
  var SRC = {};
  (D.sources || []).forEach(function (s) { SRC[s.id] = s; });
  var NODE_BY_ID = {};
  NODES.forEach(function (n) { NODE_BY_ID[n.id] = n; });
  var BOX = {};
  (LAY.nodes || []).forEach(function (b) { BOX[b.id] = b; });

  var SVGNS = "http://www.w3.org/2000/svg";
  var state = {
    k: 1, tx: 0, ty: 0,
    selected: null,
    selectedList: [],
    hovered: null,
    related: {},
    relFilter: "",
    routeFilter: "",
    typeFilter: "",
    tableMode: false,
    sbOpen: true,
    activeTab: "node",
    covCollapsed: false
  };

  // ---------------------------------------------------------------- 工具
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }
  function sv(tag, attrs) {
    var e = document.createElementNS(SVGNS, tag);
    if (attrs) for (var k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    return e;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function fmt(v, d) {
    if (v == null || v === "") return "—";
    if (typeof v !== "number") return String(v);
    var s = d == null ? 2 : d;
    return v.toFixed(s).replace(/\.?0+$/, "");
  }
  function val(v) {
    return v == null || v === "" ? "—" : String(v);
  }
  function pct(a, b) { return b ? (a / b * 100) : 0; }

  var TYPE_META = D.relTypeMeta || {};
  function typeZh(t) { return (TYPE_META[t] || {}).zh || t || "关系"; }
  function typeColor(t) { return (TYPE_META[t] || {}).color || "#8899aa"; }
  var QS = D.quantStatusZh || {};
  function quantZh(s) { return QS[s] || s || "—"; }

  // ---------------------------------------------------------------- 视图变换
  var viewport = document.getElementById("viewport");
  var svg = document.getElementById("svg");
  var wrap = document.getElementById("canvasWrap");
  var CW = LAY.canvas ? LAY.canvas.w : 1600;
  var CH = LAY.canvas ? LAY.canvas.h : 800;

  function applyView() {
    viewport.setAttribute("transform",
      "translate(" + state.tx + "," + state.ty + ") scale(" + state.k + ")");
    updateMinimapView();
    var z = document.getElementById("zoomLevel");
    if (z) z.textContent = Math.round(state.k * 100) + "%";
  }
  var MIN_READABLE_K = 0.74;    // 可读下限：低于此值文字会糊
  var FIT_PAD = 22;
  // 「适应」：整图完整落在视口内；只有当缩放低于可读下限时才改用可读比例（此时可横向拖拽）
  function fit() {
    var r = svg.getBoundingClientRect();
    if (!r.width || !r.height) return;
    var kAll = Math.min((r.width - FIT_PAD * 2) / CW, (r.height - FIT_PAD * 2) / CH);
    if (kAll >= MIN_READABLE_K) {
      state.k = Math.min(kAll, 2.2);
      state.tx = (r.width - CW * state.k) / 2;
      state.ty = (r.height - CH * state.k) / 2;
    } else {
      state.k = MIN_READABLE_K;
      // 聚焦目标品种列，其余部分可拖拽查看
      var focus = (LAY.columns || []).filter(function (c) {
        return (D.nodes || []).some(function (n) { return n.column === c.col && n.node_role === "target"; });
      })[0];
      var fx = focus ? focus.label_x : CW / 2;
      state.tx = r.width / 2 - fx * state.k;
      state.ty = (r.height - CH * state.k) / 2;
    }
    clampView();
    applyView();
  }
  function clampView() {
    var r = svg.getBoundingClientRect();
    if (!r.width) return;
    var w = CW * state.k, h = CH * state.k;
    if (w <= r.width) state.tx = (r.width - w) / 2;
    else state.tx = Math.min(FIT_PAD * 0.5, Math.max(r.width - w - FIT_PAD * 0.5, state.tx));
    if (h <= r.height) state.ty = (r.height - h) / 2;
    else state.ty = Math.min(FIT_PAD * 0.5, Math.max(r.height - h - FIT_PAD * 0.5, state.ty));
  }
  function fitAll() {                            // 「总览」：强制缩到全部可见
    var r = svg.getBoundingClientRect();
    var k = Math.min((r.width - 36) / CW, (r.height - 36) / CH);
    state.k = Math.max(0.12, Math.min(k, 2.2));
    state.tx = (r.width - CW * state.k) / 2;
    state.ty = (r.height - CH * state.k) / 2;
    applyView();
  }
  function zoomAt(factor, cx, cy) {
    var r = svg.getBoundingClientRect();
    if (cx == null) { cx = r.width / 2; cy = r.height / 2; }
    var k2 = Math.max(0.12, Math.min(4, state.k * factor));
    var scale = k2 / state.k;
    state.tx = cx - (cx - state.tx) * scale;
    state.ty = cy - (cy - state.ty) * scale;
    state.k = k2;
    clampView();
    applyView();
  }

  // ---------------------------------------------------------------- 绘制：泳道
  function drawLanes() {
    var g = document.getElementById("laneLayer");
    g.innerHTML = "";
    (LAY.columns || []).forEach(function (c, i) {
      var colMeta = (D.columns || []).filter(function (x) { return x.col === c.col; })[0] || {};
      var band = sv("rect", {
        x: c.x - 12, y: 6, width: c.w + 24, height: CH - 12,
        rx: 14, class: "lane-band" + (i % 2 ? " odd" : "")
      });
      g.appendChild(band);
      var t = sv("text", {
        x: c.label_x, y: 26, class: "lane-title", "text-anchor": "middle"
      });
      t.textContent = colMeta.label || ("第 " + c.col + " 列");
      g.appendChild(t);
      var sub = sv("text", {
        x: c.label_x, y: 42, class: "lane-sub", "text-anchor": "middle"
      });
      var cnt = (LAY.nodes || []).filter(function (b) {
        var n = NODE_BY_ID[b.id];
        return n && n.column === c.col;
      }).length;
      sub.textContent = cnt + " 个节点";
      g.appendChild(sub);
    });
  }

  // ---------------------------------------------------------------- 绘制：箭头
  function drawDefs() {
    var defs = document.getElementById("defs");
    defs.innerHTML = "";
    var types = {};
    RELS.forEach(function (r) { types[r.relation_type] = typeColor(r.relation_type); });
    Object.keys(types).forEach(function (t) {
      var m = sv("marker", {
        id: "arw-" + t, viewBox: "0 0 10 10", refX: "9", refY: "5",
        markerWidth: "6.5", markerHeight: "6.5", orient: "auto-start-reverse"
      });
      m.appendChild(sv("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: types[t] }));
      defs.appendChild(m);
    });
    var m2 = sv("marker", {
      id: "arw-dim", viewBox: "0 0 10 10", refX: "9", refY: "5",
      markerWidth: "6.5", markerHeight: "6.5", orient: "auto-start-reverse"
    });
    m2.appendChild(sv("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#5a677d" }));
    defs.appendChild(m2);
  }

  // ---------------------------------------------------------------- 绘制：边
  var EDGE_ELS = {};
  function drawEdges() {
    var g = document.getElementById("edgeLayer");
    g.innerHTML = "";
    EDGE_ELS = {};
    (LAY.edges || []).forEach(function (e) {
      var rel = RELS.filter(function (r) { return r.id === e.id; })[0] || {};
      var typ = rel.relation_type || "conversion";
      var p = sv("path", {
        d: e.d, class: "edge", "data-id": e.id, "data-type": typ,
        stroke: typeColor(typ),
        "stroke-dasharray": dashFor(rel, typ),
        "marker-end": "url(#arw-" + typ + ")"
      });
      if (rel.relation_type === "substitution") p.setAttribute("marker-start", "url(#arw-" + typ + ")");
      p.addEventListener("click", function (ev) {
        ev.stopPropagation(); selectRelation(e.id);
      });
      p.addEventListener("mouseenter", function () {
        p.classList.add("edge-hi");
        showTip(ev0(ev0), rel, e);
      });
      p.addEventListener("mouseleave", function () {
        p.classList.remove("edge-hi"); hideTip();
      });
      g.appendChild(p);
      EDGE_ELS[e.id] = p;
    });
  }
  function ev0(e) { return e; }
  function dashFor(rel, typ) {
    if (typ === "substitution") return "7 5";
    if (typ === "blend" || typ === "processing") return "2 4";
    if (typ === "byproduct") return "10 4";
    if (typ === "route_option") return "5 4";
    return null;
  }

  // 标签：只在缩放足够大或高亮时显示，避免糊成一片
  function drawLabels() {
    var g = document.getElementById("labelLayer");
    g.innerHTML = "";
    (LAY.edges || []).forEach(function (e) {
      var rel = RELS.filter(function (r) { return r.id === e.id; })[0] || {};
      var q = rel.quant || {};
      var txt = q.from_per_to != null ? (fmt(q.from_per_to, 3) + " t/t") : "";
      if (!txt) return;
      var t = sv("text", {
        x: e.label_x, y: e.label_y - 3, class: "edge-label", "text-anchor": "middle",
        "data-for": e.id
      });
      t.textContent = txt;
      g.appendChild(t);
    });
  }

  // ---------------------------------------------------------------- 绘制：节点
  var NODE_ELS = {};
  function nodeClass(n) { return "node k-" + (n.node_class || "commodity") + " role-" + (n.node_role || "x"); }
  function drawNodes() {
    var g = document.getElementById("nodeLayer");
    g.innerHTML = "";
    NODE_ELS = {};
    (LAY.nodes || []).forEach(function (b) {
      var n = NODE_BY_ID[b.id];
      if (!n) return;
      var grp = sv("g", { class: nodeClass(n), "data-id": n.id, transform: "translate(" + b.x + "," + b.y + ")" });
      grp.appendChild(sv("rect", { class: "node-bg", x: 0, y: 0, width: b.w, height: b.h, rx: 11 }));
      grp.appendChild(sv("rect", { class: "node-strip", x: 0, y: 0, width: 4.5, height: b.h, rx: 2 }));

      var title = n.name || n.id;
      var maxCh = Math.floor((b.w - 34) / 12.5);
      if (title.length > maxCh) {
        var cut = title.slice(0, maxCh - 1) + "…";
        grp.appendChild(mkText(13, 10, 22, cut, "node-title"));
        // 悬停走原生 title
        grp.appendChild(sv("title")).textContent = title;
      } else {
        grp.appendChild(mkText(13, 10, 22, title, "node-title"));
      }
      var sub = (n.cas && n.cas.value) ? ("CAS " + n.cas.value)
        : (n.node_class === "material" ? "材料" : n.node_class === "application" ? "终端应用" : "化学品");
      grp.appendChild(mkText(10.5, 10.5, 38, sub, "node-sub"));

      var flags = n.missing_flags || [];
      if (flags.length) {
        grp.appendChild(mkText(9.5, b.w - 10, b.h - 7, "⚠ " + flags.length, "node-flag"));
        var tt = sv("title");
        tt.textContent = "缺口：" + flags.join("、");
        grp.appendChild(tt);
      } else {
        grp.appendChild(mkText(9.5, b.w - 10, b.h - 7, "✓", "node-ok"));
      }

      grp.addEventListener("click", function (ev) {
        ev.stopPropagation();
        if (ev.ctrlKey || ev.metaKey || ev.shiftKey) addMulti(n.id);
        else selectNode(n.id);
      });
      grp.addEventListener("mouseenter", function () { state.hovered = n.id; highlightPath(n.id); });
      grp.addEventListener("mouseleave", function () { state.hovered = null; highlightPath(state.selected); });
      g.appendChild(grp);
      NODE_ELS[n.id] = grp;
    });
  }
  function mkText(size, x, y, txt, cls) {
    var t = sv("text", { x: x, y: y, class: cls, "font-size": size });
    t.textContent = txt;
    return t;
  }

  // ---------------------------------------------------------------- 上下游高亮
  function ancestors(id, seen, out) {
    seen = seen || {}; out = out || {};
    RELS.forEach(function (r) {
      if (r.to === id && r.relation_type !== "substitution" && !seen[r.from]) {
        seen[r.from] = 1; out[r.from] = 1;
        ancestors(r.from, seen, out);
      }
    });
    return out;
  }
  function descendants(id, seen, out) {
    seen = seen || {}; out = out || {};
    RELS.forEach(function (r) {
      if (r.from === id && r.relation_type !== "substitution" && !seen[r.to]) {
        seen[r.to] = 1; out[r.to] = 1;
        descendants(r.to, seen, out);
      }
    });
    return out;
  }
  function highlightPath(id) {
    Object.keys(NODE_ELS).forEach(function (k) {
      NODE_ELS[k].classList.remove("up", "down", "selected", "dim");
    });
    Object.keys(EDGE_ELS).forEach(function (k) {
      EDGE_ELS[k].classList.remove("up", "down", "edge-hi", "dim");
    });
    if (!id) return;
    var up = ancestors(id, {}, {});
    var dn = descendants(id, {}, {});
    state.related = { up: up, down: dn };
    Object.keys(NODE_ELS).forEach(function (k) {
      if (k === id) NODE_ELS[k].classList.add("selected");
      else if (up[k]) NODE_ELS[k].classList.add("up");
      else if (dn[k]) NODE_ELS[k].classList.add("down");
      else NODE_ELS[k].classList.add("dim");
    });
    RELS.forEach(function (r) {
      var p = EDGE_ELS[r.id];
      if (!p) return;
      if (r.from === id || r.to === id || (up[r.from] && up[r.to]) || (dn[r.from] && dn[r.to])) {
        p.classList.add(up[r.from] !== undefined || r.from === id ? "up" : "down");
      } else p.classList.add("dim");
    });
  }

  // ---------------------------------------------------------------- 侧栏
  function sbShow(tab) {
    state.sbOpen = true;
    document.getElementById("sidebar").classList.add("open");
    document.getElementById("sbOpen").classList.remove("show");
    document.querySelectorAll(".sb-tab").forEach(function (b) {
      b.classList.toggle("active", b.dataset.tab === tab);
    });
    state.activeTab = tab;
  }
  function sbHide() {
    state.sbOpen = false;
    document.getElementById("sidebar").classList.remove("open");
    document.getElementById("sbOpen").classList.add("show");
  }

  function priceSeriesFor(nodeId) {
    var ps = (D.prices && D.prices.series) || [];
    return ps.filter(function (s) { return s.node_id === nodeId; })[0] || null;
  }
  function entsFor(nodeId) {
    return (D.enterprises || []).filter(function (e) {
      return (e.nodes || []).indexOf(nodeId) >= 0 || e.node_id === nodeId;
    });
  }
  function projsFor(nodeId) {
    return (D.projects || []).filter(function (p) {
      return (p.node_ids || []).indexOf(nodeId) >= 0 || p.node_id === nodeId;
    });
  }
  function eventsFor(nodeId) {
    return (D.events || []).filter(function (e) {
      return (e.node_ids || []).indexOf(nodeId) >= 0 || e.node_id === nodeId;
    });
  }
  function relsFor(nodeId) {
    return RELS.filter(function (r) { return r.from === nodeId || r.to === nodeId; });
  }

  function sparkline(series, w, h) {
    if (!series || !series.points || !series.points.length) {
      return '<div class="no-data">该节点暂无公开价格序列（已登记为价格缺口，不做估算）</div>';
    }
    var pts = series.points;
    var vs = pts.map(function (p) { return p.price; });
    var mn = Math.min.apply(null, vs), mx = Math.max.apply(null, vs);
    var span = (mx - mn) || 1;
    var dx = w / Math.max(1, pts.length - 1);
    var d = pts.map(function (p, i) {
      return (i ? "L" : "M") + (i * dx).toFixed(1) + " " + (h - (p.price - mn) / span * (h - 8) - 4).toFixed(1);
    }).join(" ");
    var area = d + " L " + w + " " + h + " L 0 " + h + " Z";
    var last = pts[pts.length - 1];
    var first = pts[0];
    var chg = first.price ? (last.price - first.price) / first.price * 100 : 0;
    var cls = chg > 0 ? "up" : chg < 0 ? "dn" : "fl";
    var html = '<svg class="spark" viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none">' +
      '<path class="spark-area" d="' + area + '"></path>' +
      '<path class="spark-line" d="' + d + '"></path></svg>' +
      '<div class="spark-meta">' +
      '<span class="spark-last">' + fmt(last.price, 2) + '</span>' +
      '<span class="spark-unit">' + esc(series.unit || "") + '</span>' +
      '<span class="spark-chg ' + cls + '">' + (chg >= 0 ? "+" : "") + chg.toFixed(2) + '%</span>' +
      '<span class="spark-date">' + esc(last.date) + '</span></div>';
    html += '<table class="mini-tbl"><thead><tr><th>日期</th><th>价格</th></tr></thead><tbody>' +
      pts.slice().reverse().map(function (p) {
        return "<tr><td>" + esc(p.date) + "</td><td>" + fmt(p.price, 2) + "</td></tr>";
      }).join("") + "</tbody></table>";
    if (series.basis) html += '<div class="src-note">口径：' + esc(series.basis) + '</div>';
    if (series.source_id && SRC[series.source_id]) html += srcChip(series.source_id);
    return html;
  }

  function srcChip(sid) {
    var s = SRC[sid] || {};
    var tier = s.evidence_tier || s.tier || "?";
    return '<span class="src-chip tier-' + esc(tier) + '" title="' + esc((s.title || "") + " " + (s.url || "")) +
      '">' + esc(sid) + " · " + esc(tier) + "级</span>";
  }

  function renderNode(nid) {
    var n = NODE_BY_ID[nid];
    if (!n) return;
    var ev = n.evidence || [];
    var h = [];
    h.push('<div class="sb-title">' + esc(n.name) + "</div>");
    h.push('<div class="sb-badges">' +
      '<span class="bd bd-' + esc(n.node_class) + '">' +
      ({ commodity: "化学品", material: "材料", application: "终端应用" }[n.node_class] || n.node_class) + "</span>" +
      '<span class="bd">' + esc(n.stage || ("第 " + n.column + " 列")) + "</span>" +
      (n.segment ? '<span class="bd">' + esc(n.segment) + "</span>" : "") +
      "</div>");
    h.push('<table class="kv">');
    h.push('<tr><th>CAS</th><td>' + esc((n.cas && n.cas.value) || "不适用") +
      ((n.cas && n.cas.status) ? ' <span class="tiny">[' + esc(n.cas.status) + "]</span>" : "") + "</td></tr>");
    if (n.hs_code) h.push("<tr><th>HS 编码</th><td>" + esc(n.hs_code) + "</td></tr>");
    if (n.aliases && n.aliases.length) h.push("<tr><th>常见名称</th><td>" + esc(n.aliases.join(" / ")) + "</td></tr>");
    if (n.specs && n.specs.length) h.push("<tr><th>规格</th><td>" + esc(n.specs.join("；")) + "</td></tr>");
    h.push("<tr><th>计量单位</th><td>" + esc(n.unit || "—") + "</td></tr>");
    if (n.missing_flags && n.missing_flags.length)
      h.push('<tr><th>缺口标记</th><td><span class="warn">' + esc(n.missing_flags.join("、")) + "</span></td></tr>");
    h.push("</table>");
    if (n.notes) h.push('<div class="sb-note">' + esc(n.notes) + "</div>");

    // 价格
    h.push('<div class="sb-sec">价格走势</div>');
    h.push('<div class="spark-wrap">' + sparkline(priceSeriesFor(nid), 300, 70) + "</div>");

    // 企业 / 产能
    var es = entsFor(nid);
    h.push('<div class="sb-sec">主要企业与公开产能（' + es.length + "）</div>");
    if (es.length) {
      h.push('<table class="grid"><thead><tr><th>企业</th><th>产能</th><th>地区</th><th>来源</th></tr></thead><tbody>');
      es.forEach(function (e) {
        h.push("<tr><td>" + esc(e.name) + "</td><td>" + val(e.capacity) + " " + esc(e.capacity_unit || "") +
          "</td><td>" + val(e.region) + "</td><td>" + (e.source_id ? srcChip(e.source_id) : "—") + "</td></tr>");
      });
      h.push("</tbody></table>");
      var tot = es.reduce(function (a, e) { return a + (typeof e.capacity === "number" ? e.capacity : 0); }, 0);
      if (tot) h.push('<div class="src-note">已核验产能合计：' + fmt(tot, 1) + " " + esc(es[0].capacity_unit || "") + "（仅统计有来源的条目）</div>");
    } else h.push('<div class="no-data">暂无已核验的企业产能条目</div>');

    // 项目
    var ps2 = projsFor(nid);
    h.push('<div class="sb-sec">相关公开项目（' + ps2.length + "）</div>");
    if (ps2.length) {
      ps2.forEach(function (p) {
        h.push('<div class="proj"><div class="proj-t">' + esc(p.name) + "</div>" +
          '<div class="proj-m">' + esc(p.company || "") + " · " + esc(p.region || "") +
          " · " + esc(p.capacity || "") + " · " + esc(p.status || "") + " " + (p.source_id ? srcChip(p.source_id) : "") + "</div></div>");
      });
    } else h.push('<div class="no-data">暂无公开项目记录</div>');

    // 事件
    var evs = eventsFor(nid);
    h.push('<div class="sb-sec">产业事件（' + evs.length + "）</div>");
    if (evs.length) {
      evs.forEach(function (e) {
        h.push('<div class="event"><span class="ev-date">' + esc(e.date || "") + "</span>" +
          '<span class="ev-t">' + esc(e.title || e.summary || "") + "</span>" +
          (e.source_id ? srcChip(e.source_id) : "") + "</div>");
      });
    } else h.push('<div class="no-data">暂无事件记录</div>');

    // 关系
    var rs = relsFor(nid);
    h.push('<div class="sb-sec">产业链关系（' + rs.length + "）</div>");
    h.push('<ul class="rel-list">');
    rs.forEach(function (r) {
      var other = r.from === nid ? r.to : r.from;
      var dirw = r.from === nid ? "下游" : "上游";
      var on = NODE_BY_ID[other] ? NODE_BY_ID[other].name : other;
      h.push('<li class="rel-item" data-rel="' + esc(r.id) + '"><span class="rt" style="color:' +
        typeColor(r.relation_type) + '">' + esc(typeZh(r.relation_type)) + "</span>" +
        '<span class="rd">' + dirw + " · " + esc(on) + "</span></li>");
    });
    h.push("</ul>");

    // 证据
    h.push('<div class="sb-sec">节点证据（' + ev.length + "）</div>");
    if (ev.length) {
      ev.forEach(function (sid) {
        var s = SRC[sid];
        if (!s) { h.push('<div class="src-line">' + esc(sid) + "（来源表未登记）</div>"); return; }
        h.push('<div class="src-line">' + srcChip(sid) + " " + esc(s.title || "") +
          (s.url ? ' <a href="' + esc(s.url) + '" target="_blank" rel="noopener">链接</a>' : "") +
          (s.date ? ' <span class="tiny">' + esc(s.date) + "</span>" : "") +
          (s.key_quote ? '<div class="quote">“' + esc(s.key_quote) + '”</div>' : "") + "</div>");
      });
    } else h.push('<div class="no-data">该节点未登记证据（属缺口，须补齐后才能用于结论）</div>');

    document.getElementById("sbBody").innerHTML = h.join("");
    bindRelItems();
  }

  function bindRelItems() {
    document.querySelectorAll(".rel-item").forEach(function (li) {
      li.addEventListener("click", function () { selectRelation(li.dataset.rel); });
    });
  }

  function renderRelation(rid) {
    var r = RELS.filter(function (x) { return x.id === rid; })[0];
    if (!r) return;
    var q = r.quant || {};
    var a = NODE_BY_ID[r.from] || { name: r.from }, b = NODE_BY_ID[r.to] || { name: r.to };
    var h = [];
    h.push('<div class="sb-title">' + esc(typeZh(r.relation_type)) + "：" + esc(a.name) + " → " + esc(b.name) + "</div>");
    h.push('<div class="sb-badges"><span class="bd" style="border-color:' + typeColor(r.relation_type) +
      ';color:' + typeColor(r.relation_type) + '">' + esc(typeZh(r.relation_type)) + "</span>" +
      '<span class="bd">' + esc(r.id) + "</span>" +
      (r.family ? '<span class="bd">' + esc(r.family) + "</span>" : "") +
      (r.typical ? '<span class="bd">主流路线</span>' : '<span class="bd">并列路线</span>') + "</div>");
    h.push('<table class="kv">');
    h.push("<tr><th>工艺</th><td>" + val(r.process) + "</td></tr>");
    h.push("<tr><th>单耗</th><td>" + (q.from_per_to != null ? "<b>" + fmt(q.from_per_to, 3) + "</b> " + esc(q.from_unit || "") : '<span class="warn">缺口</span>') + "</td></tr>");
    if (q.from_per_to_range) h.push("<tr><th>常见区间</th><td>" + q.from_per_to_range[0] + " ~ " + q.from_per_to_range[1] + "</td></tr>");
    if (q.yield != null) h.push("<tr><th>收率</th><td>" + fmt(q.yield, 3) + "</td></tr>");
    h.push("<tr><th>量化状态</th><td>" + esc(quantZh(r.quant_status)) + "</td></tr>");
    h.push("<tr><th>口径</th><td>" + val(q.basis) + "</td></tr>");
    if (q.range_note) h.push("<tr><th>区间说明</th><td>" + esc(q.range_note) + "</td></tr>");
    if (q.basis_grade) h.push("<tr><th>口径等级</th><td>" + esc(q.basis_grade) + "</td></tr>");
    h.push("</table>");
    if (r.notes) h.push('<div class="sb-note">' + esc(r.notes) + "</div>");

    // 单耗来源与计算式
    h.push('<div class="sb-sec">单耗来源与计算口径</div>');
    h.push('<div class="formula">' + (q.from_per_to != null
      ? "1 t " + esc(b.name) + " × " + fmt(q.from_per_to, 3) + " t/" + "t = " + fmt(q.from_per_to, 3) + " t " + esc(a.name)
      : "未取得公开口径 → 登记为缺口，不估算") + "</div>");
    var ev = r.evidence || [];
    if (ev.length) {
      ev.forEach(function (sid) {
        var s = SRC[sid] || {};
        h.push('<div class="src-line">' + srcChip(sid) + " " + esc(s.title || "") +
          (s.url ? ' <a href="' + esc(s.url) + '" target="_blank" rel="noopener">链接</a>' : "") +
          (s.key_quote ? '<div class="quote">“' + esc(s.key_quote) + '”</div>' : "") + "</div>");
      });
    } else h.push('<div class="no-data">该关系未登记证据（缺口）</div>');

    // 端点跳转
    h.push('<div class="sb-sec">端点</div>');
    h.push('<div class="rel-ends">' +
      '<span class="end" data-node="' + esc(r.from) + '">↑ ' + esc(a.name) + "</span>" +
      '<span class="end" data-node="' + esc(r.to) + '">↓ ' + esc(b.name) + "</span></div>");

    h.push('<div class="sb-sec">可追溯性</div>');
    h.push('<div class="src-note">关系 ID ' + esc(r.id) + "；证据 " + ev.length + " 条；" +
      (r.quant_status === "missing" ? "量化缺口已显式登记，未用推算值填充。" : "量化口径见上表。") + "</div>");

    document.getElementById("sbBody").innerHTML = h.join("");
    document.querySelectorAll(".end").forEach(function (s) {
      s.addEventListener("click", function () { selectNode(s.dataset.node); });
    });
  }

  // ---------------------------------------------------------------- 价格联动
  function renderLinkage() {
    var ids = state.selectedList;
    var h = [];
    if (ids.length < 2) {
      h.push('<div class="sb-title">价格联动研究</div>');
      h.push('<div class="sb-note">按住 <b>Ctrl/⌘</b> 依次点击两个节点（或勾选后点“价格联动”），' +
        "这里会并排给出两条价格序列、区间统计与相关性。缺口序列会明确标注，不做插值。</div>");
      h.push('<div class="sb-sec">当前已选</div>');
      h.push('<div class="chips">' + (ids.length ? ids.map(function (i) {
        return '<span class="chip-sel">' + esc((NODE_BY_ID[i] || {}).name || i) + "</span>";
      }).join("") : '<span class="no-data">尚未选择</span>') + "</div>");
      document.getElementById("sbBody").innerHTML = h.join("");
      return;
    }
    var A = ids[0], B = ids[1];
    var na = NODE_BY_ID[A] || {}, nb = NODE_BY_ID[B] || {};
    var pa = priceSeriesFor(A), pb = priceSeriesFor(B);
    h.push('<div class="sb-title">' + esc(na.name) + " × " + esc(nb.name) + "</div>");
    h.push('<div class="sb-badges"><span class="bd">价格联动</span><span class="bd">' + ids.length + " 个节点</span></div>");

    var rows = [];
    [[A, na, pa, "①"], [B, nb, pb, "②"]].forEach(function (t) {
      var id = t[0], n = t[1], p = t[2], tag = t[3];
      h.push('<div class="sb-sec">' + tag + " " + esc(n.name) + "（" + esc(n.stage || "") + "）</div>");
      h.push('<div class="spark-wrap">' + sparkline(p, 300, 64) + "</div>");
      if (p && p.points && p.points.length) {
        var vs = p.points.map(function (x) { return x.price; });
        rows.push({ id: id, name: n.name, pts: p.points, unit: p.unit });
        h.push('<table class="kv"><tr><th>区间高/低</th><td>' + fmt(Math.max.apply(null, vs), 2) + " / " +
          fmt(Math.min.apply(null, vs), 2) + " " + esc(p.unit || "") + "</td></tr>" +
          "<tr><th>样本点</th><td>" + vs.length + " 个</td></tr></table>");
      } else {
        rows.push({ id: id, name: n.name, pts: null, unit: null });
      }
    });

    if (rows.length === 2 && rows[0].pts && rows[1].pts) {
      // 按日期对齐求相关性
      var ma = {}, mb = {};
      rows[0].pts.forEach(function (p) { ma[p.date] = p.price; });
      rows[1].pts.forEach(function (p) { mb[p.date] = p.price; });
      var common = Object.keys(ma).filter(function (d) { return mb[d] != null; }).sort();
      h.push('<div class="sb-sec">对齐与相关性</div>');
      if (common.length >= 4) {
        var xs = common.map(function (d) { return Math.log(ma[d]); });
        var ys = common.map(function (d) { return Math.log(mb[d]); });
        var mx = xs.reduce(function (a, b) { return a + b; }, 0) / xs.length;
        var my = ys.reduce(function (a, b) { return a + b; }, 0) / ys.length;
        var cov = 0, vx = 0, vy = 0;
        for (var i = 0; i < xs.length; i++) {
          cov += (xs[i] - mx) * (ys[i] - my); vx += Math.pow(xs[i] - mx, 2); vy += Math.pow(ys[i] - my, 2);
        }
        var corr = (vx && vy) ? cov / Math.sqrt(vx * vy) : 0;
        var el2 = Math.pow(ys[ys.length - 1] / ys[0], 1 / Math.max(1, common.length - 1)) - 1;
        h.push('<table class="kv">' +
          "<tr><th>共同交易日</th><td>" + common.length + " 个（" + common[0] + " ~ " + common[common.length - 1] + "）</td></tr>" +
          "<tr><th>对数价格相关系数</th><td><b>" + corr.toFixed(3) + "</b></td></tr>" +
          '<tr><th>估算弹性</th><td>' + (vx ? (cov / vx).toFixed(3) : "—") + "</td></tr>" +
          "<tr><th>口径说明</th><td>仅在共同交易日上计算；样本量 " + common.length +
          " 点，<b>不足以判定因果关系</b>，只能作为方向性参考。</td></tr></table>");
        h.push('<div class="src-note">本页不生成价差/价差率结论，也不做跨规格、跨区域的价格拼接；' +
          "如需价差研究请使用同一口径的现货序列。</div>");
      } else {
        h.push('<div class="no-data">共同交易日不足 4 个，无法计算相关性。</div>');
      }
    }

    h.push('<div class="sb-sec">缺口说明</div>');
    var missing = [];
    if (!pa) missing.push(na.name + "：无价格序列");
    // 保持简洁
    h.push('<div class="src-note">' + (missing.length ? missing.join("；") + "，已按缺口登记。" :
      "两条序列均有公开数据；如需更长历史请按 sources 中的入口自行补充，本图不回溯补值。") + "</div>");

    document.getElementById("sbBody").innerHTML = h.join("");
  }

  // ---------------------------------------------------------------- 选中逻辑
  function selectNode(id) {
    state.selected = id;
    highlightPath(id);
    renderNode(id);
    sbShow("node");
    updateSelbar();
  }
  function addMulti(id) {
    var i = state.selectedList.indexOf(id);
    if (i >= 0) state.selectedList.splice(i, 1);
    else {
      state.selectedList.push(id);
      if (state.selectedList.length > 2) state.selectedList.shift();
    }
    state.selected = id;
    highlightPath(id);
    if (state.selectedList.length === 2) {
      renderLinkage(); sbShow("link");
    } else {
      renderNode(id); sbShow("node");
    }
    updateSelbar();
  }
  function selectRelation(id) {
    renderRelation(id);
    sbShow("rel");
    var rel = RELS.filter(function (r) { return r.id === id; })[0];
    if (rel) highlightPath(rel.from);
  }
  function updateSelbar() {
    var c = document.getElementById("selChips");
    var ids = state.selectedList.slice();
    if (state.selected && ids.indexOf(state.selected) < 0) ids.push(state.selected);
    c.innerHTML = ids.map(function (i) {
      var n = NODE_BY_ID[i] || {};
      return '<span class="chip-sel" data-id="' + esc(i) + '">' + esc(n.name || i) +
        ' <b class="x">×</b></span>';
    }).join("");
    c.querySelectorAll(".x").forEach(function (x) {
      x.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var id = x.parentNode.dataset.id;
        state.selectedList = state.selectedList.filter(function (z) { return z !== id; });
        updateSelbar();
      });
    });
  }

  // ---------------------------------------------------------------- 悬停提示
  var tipEl = null;
  function showTip(ev, rel, e) {
    if (!tipEl) {
      tipEl = el("div", "tip");
      document.body.appendChild(tipEl);
    }
    var q = rel.quant || {};
    tipEl.innerHTML = "<b>" + esc(typeZh(rel.relation_type)) + "</b> " +
      esc((NODE_BY_ID[rel.from] || {}).name) + " → " + esc((NODE_BY_ID[rel.to] || {}).name) +
      "<br>" + (q.from_per_to != null ? "单耗 " + fmt(q.from_per_to, 3) + " " + esc(q.from_unit || "") : '<span class="warn">单耗缺口</span>') +
      (rel.process ? "<br>" + esc(rel.process) : "");
    tipEl.style.display = "block";
    // 用鼠标位置，避免在 mouseenter 里拿不到坐标
    document.addEventListener("mousemove", moveTip);
  }
  function moveTip(e) {
    if (!tipEl || tipEl.style.display !== "block") return;
    tipEl.style.left = (e.clientX + 14) + "px";
    tipEl.style.top = (e.clientY + 14) + "px";
  }
  function hideTip() { if (tipEl) tipEl.style.display = "none"; }

  // ---------------------------------------------------------------- 覆盖面板
  function renderCoverage() {
    var cov = D.coverage || {};
    var ov = cov.overall || {};
    var rate = ov.rate || 0;
    var C = 2 * Math.PI * 50;
    var fg = document.getElementById("gaugeFg");
    fg.setAttribute("stroke-dasharray", C);
    fg.setAttribute("stroke-dashoffset", C * (1 - rate / 100));
    fg.setAttribute("class", "gauge-fg " + (rate >= 90 ? "good" : rate >= 70 ? "mid" : "bad"));
    document.getElementById("gaugeTxt").textContent = rate.toFixed(1) + "%";
    document.getElementById("gaugeNote").innerHTML =
      "按开工前冻结的核心清单计算：<b>" + (ov.passed || 0) + "/" + (ov.total || 0) + "</b> 项达标";

    var cards = [];
    function card(k, v, s) {
      return '<div class="cov-card"><div class="k">' + k + '</div><div class="v">' +
        v + (s ? "<small>" + s + "</small>" : "") + "</div></div>";
    }
    var nodesC = cov.nodes || {}, relsC = cov.relations || {};
    cards.push(card("核心节点", (nodesC.passed || 0) + "/" + (nodesC.total || 0),
      (nodesC.rate != null ? nodesC.rate.toFixed(0) + "%" : "")));
    cards.push(card("核心关系", (relsC.passed || 0) + "/" + (relsC.total || 0),
      (relsC.rate != null ? relsC.rate.toFixed(0) + "%" : "")));
    var byP = nodesC.by_priority || {};
    var pTxt = Object.keys(byP).sort().map(function (p) {
      return p + " " + byP[p].passed + "/" + byP[p].total;
    }).join("  ");
    cards.push(card("节点优先级", pTxt || "—", ""));
    var gaps = (D.nodes || []).reduce(function (a, n) { return a + ((n.missing_flags || []).length ? 1 : 0); }, 0);
    cards.push(card("带缺口标记节点", gaps, "/ " + (D.nodes || []).length));
    cards.push(card("价格序列", ((D.prices && D.prices.series) || []).length, "条"));
    cards.push(card("证据来源", (D.sources || []).length, "条"));
    document.getElementById("covCards").innerHTML = cards.join("");

    // 缺口列表
    var fail = [];
    (nodesC.detail || []).forEach(function (d) {
      if (!d.pass) fail.push('<div class="gap-i">节点 ' + esc(d.core_id || "") + " " + esc(d.label || "") +
        "：缺 " + esc((d.failed || []).join("/")) + "</div>");
    });
    (relsC.detail || []).forEach(function (d) {
      if (!d.pass) fail.push('<div class="gap-i">关系 ' + esc(d.core_id || "") + " " + esc(d.label || "") +
        "：" + esc((d.failed || []).join("/")) + "</div>");
    });
    document.getElementById("covGaps").innerHTML =
      '<div class="gap-h">未达标项（' + fail.length + "）：</div>" +
      (fail.length ? fail.slice(0, 8).join("") : '<div class="gap-i ok">全部达标</div>') +
      (fail.length > 8 ? '<div class="gap-i">… 其余 ' + (fail.length - 8) + " 项见 Excel 报告页</div>" : "");

    var core = D.core && D.core.meta ? D.core.meta : {};
    document.getElementById("covScope").innerHTML =
      "<b>计算口径：</b>" + esc(core.scope_statement || "覆盖完整度仅对预先冻结的核心节点/关系清单有效，不代表产业链全部可能节点。") +
      (core.frozen_at ? "<br><b>清单冻结时间：</b>" + esc(core.frozen_at) : "");
  }

  // ---------------------------------------------------------------- 工具条
  function renderToolbar() {
    var types = {};
    RELS.forEach(function (r) { types[r.relation_type] = (types[r.relation_type] || 0) + 1; });
    var chips = document.getElementById("typeChips");
    chips.innerHTML = "";
    var all = el("button", "chip active", "全部关系");
    all.addEventListener("click", function () {
      state.typeFilter = "";
      document.querySelectorAll("#typeChips .chip").forEach(function (c) { c.classList.remove("active"); });
      all.classList.add("active");
      applyFilters();
    });
    chips.appendChild(all);
    Object.keys(types).forEach(function (t) {
      var b = el("button", "chip", typeZh(t) + " " + types[t]);
      b.style.borderColor = typeColor(t);
      b.addEventListener("click", function () {
        var on = state.typeFilter === t;
        document.querySelectorAll("#typeChips .chip").forEach(function (c) { c.classList.remove("active"); });
        if (on) { state.typeFilter = ""; all.classList.add("active"); }
        else { state.typeFilter = t; b.classList.add("active"); }
        applyFilters();
      });
      chips.appendChild(b);
    });

    // 关系类型下拉与工艺下拉
    var rs = document.getElementById("relSel");
    Object.keys(types).forEach(function (t) {
      var o = document.createElement("option");
      o.value = t; o.textContent = typeZh(t) + "（" + types[t] + "）";
      rs.appendChild(o);
    });
    rs.addEventListener("change", function () { state.typeFilter = rs.value; applyFilters(); });

    var routeSel = document.getElementById("routeSel");
    var families = {};
    RELS.forEach(function (r) { if (r.family) families[r.family] = 1; });
    Object.keys(families).forEach(function (f) {
      var o = document.createElement("option");
      o.value = f; o.textContent = f;
      routeSel.appendChild(o);
    });
    routeSel.addEventListener("change", function () { state.routeFilter = routeSel.value; applyFilters(); });
  }

  // ---------------------------------------------------------------- 筛选
  function applyFilters() {
    var t = state.typeFilter, fam = state.routeFilter, q = (document.getElementById("search").value || "").trim().toLowerCase();
    var keepNodes = {}, keepEdges = {};
    (LAY.edges || []).forEach(function (e) {
      var r = RELS.filter(function (x) { return x.id === e.id; })[0] || {};
      var okT = !t || r.relation_type === t;
      var okF = !fam || r.family === fam;
      if (okT && okF) { keepEdges[e.id] = 1; keepNodes[r.from] = 1; keepNodes[r.to] = 1; }
    });
    if (q) {
      var hit = {};
      NODES.forEach(function (n) {
        var hay = (n.name + " " + (n.aliases || []).join(" ") + " " + ((n.cas || {}).value || " ")).toLowerCase();
        if (hay.indexOf(q) >= 0) hit[n.id] = 1;
      });
      keepNodes = hit;
      keepEdges = {};
      (LAY.edges || []).forEach(function (e) {
        if (hit[e.from] || hit[e.to]) keepEdges[e.id] = 1;
      });
    }
    // 替代边没有方向，两端都要保留
    Object.keys(NODE_ELS).forEach(function (id) {
      var on = !Object.keys(keepNodes).length ? true : !!keepNodes[id];
      if (Object.keys(keepNodes).length) NODE_ELS[id].classList.toggle("filtered", !on);
      else NODE_ELS[id].classList.remove("filtered");
    });
    Object.keys(EDGE_ELS).forEach(function (id) {
      var on = !Object.keys(keepEdges).length ? true : !!keepEdges[id];
      if (Object.keys(keepEdges).length) EDGE_ELS[id].classList.toggle("filtered", !on);
      else EDGE_ELS[id].classList.remove("filtered");
    });
    document.getElementById("hint").textContent =
      (t || fam || q) ? ("筛选中：显示 " + Object.keys(keepEdges).length + " 条关系 / " + Object.keys(keepNodes).length + " 个节点（点“重置”清除）") :
        "滚轮缩放 · 拖拽平移 · 双击空白处复位";
  }

  // ---------------------------------------------------------------- 搜索
  function bindSearch() {
    var inp = document.getElementById("search");
    var drop = document.getElementById("searchDrop");
    inp.addEventListener("input", function () {
      var q = inp.value.trim().toLowerCase();
      applyFilters();
      if (!q) { drop.style.display = "none"; return; }
      var hits = NODES.filter(function (n) {
        return (n.name + " " + (n.aliases || []).join(" ") + " " + ((n.cas || {}).value || " ")).toLowerCase().indexOf(q) >= 0;
      }).slice(0, 8);
      drop.innerHTML = hits.length ? hits.map(function (n) {
        return '<div class="sr-item" data-id="' + esc(n.id) + '"><span class="sr-n">' + esc(n.name) +
          '</span><span class="meta">' + esc((n.cas && n.cas.value) || n.stage || "") + "</span></div>";
      }).join("") : '<div class="sr-item empty">无匹配节点</div>';
      drop.style.display = "block";
      drop.querySelectorAll(".sr-item[data-id]").forEach(function (it) {
        it.addEventListener("click", function () {
          selectNode(it.dataset.id);
          focusNode(it.dataset.id);
          drop.style.display = "none";
        });
      });
    });
    inp.addEventListener("blur", function () { setTimeout(function () { drop.style.display = "none"; }, 160); });
  }

  function focusNode(id) {
    var b = BOX[id];
    if (!b) return;
    var r = svg.getBoundingClientRect();
    state.k = Math.max(state.k, 0.85);
    state.tx = r.width / 2 - (b.x + b.w / 2) * state.k;
    state.ty = r.height / 2 - (b.y + b.h / 2) * state.k;
    applyView();
  }

  // ---------------------------------------------------------------- 缩放/平移
  function bindPanZoom() {
    var dragging = false, sx = 0, sy = 0, ox = 0, oy = 0;
    wrap.addEventListener("mousedown", function (e) {
      if (e.button !== 0) return;
      var t = e.target;
      if (t && t.closest && (t.closest(".node") || t.closest(".minimap-wrap") ||
          t.closest(".canvas-legend") || t.closest(".hint"))) return;
      dragging = true; sx = e.clientX; sy = e.clientY; ox = state.tx; oy = state.ty;
      svg.style.cursor = "grabbing";
      e.preventDefault();
    });
    window.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      state.tx = ox + (e.clientX - sx);
      state.ty = oy + (e.clientY - sy);
      clampView();
      applyView();
    });
    window.addEventListener("mouseup", function () { dragging = false; svg.style.cursor = "grab"; });
    svg.addEventListener("wheel", function (e) {
      e.preventDefault();
      var r = svg.getBoundingClientRect();
      zoomAt(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });
    svg.addEventListener("dblclick", function (e) {
      if (e.target.closest(".node")) return;
      fitAll();
    });
    svg.addEventListener("click", function (e) {
      if (e.target.closest(".node") || e.target.closest(".edge")) return;
    });
    document.getElementById("btnZoomIn").addEventListener("click", function () { zoomAt(1.2); });
    document.getElementById("btnZoomOut").addEventListener("click", function () { zoomAt(1 / 1.2); });
    document.getElementById("btnFit").addEventListener("click", fit);
    var bAll = document.getElementById("btnFitAll");
    if (bAll) bAll.addEventListener("click", fitAll);
    document.getElementById("btnReset").addEventListener("click", function () {
      state.typeFilter = ""; state.routeFilter = "";
      document.getElementById("search").value = "";
      document.getElementById("relSel").value = "";
      document.getElementById("routeSel").value = "";
      document.querySelectorAll("#typeChips .chip").forEach(function (c, i) { c.classList.toggle("active", i === 0); });
      applyFilters(); fit();
    });
  }

  // ---------------------------------------------------------------- 小地图
  function drawMinimap() {
    var g = document.getElementById("miniNodes");
    g.innerHTML = "";
    var sx = 1000 / CW, sy = 320 / CH;
    (LAY.nodes || []).forEach(function (b) {
      var n = NODE_BY_ID[b.id] || {};
      var r = sv("rect", {
        x: b.x * sx, y: b.y * sy, width: Math.max(2, b.w * sx), height: Math.max(2, b.h * sy),
        rx: 1, class: "mini-n mini-" + (n.node_class || "commodity")
      });
      r.addEventListener("click", function () { focusNode(b.id); });
      g.appendChild(r);
    });
  }
  function updateMinimapView() {
    var r = svg.getBoundingClientRect();
    if (!r.width) return;
    var sx = 1000 / CW, sy = 320 / CH;
    var vx = -state.tx / state.k, vy = -state.ty / state.k;
    var vw = r.width / state.k, vh = r.height / state.k;
    var rect = document.getElementById("miniView");
    rect.setAttribute("x", vx * sx);
    rect.setAttribute("y", vy * sy);
    rect.setAttribute("width", Math.max(4, vw * sx));
    rect.setAttribute("height", Math.max(4, vh * sy));
  }

  // ---------------------------------------------------------------- 图例
  function drawLegend() {
    var types = {};
    RELS.forEach(function (r) { types[r.relation_type] = 1; });
    var h = Object.keys(types).map(function (t) {
      return '<span class="lg"><i style="background:' + typeColor(t) + '"></i>' + esc(typeZh(t)) + "</span>";
    }).join("");
    h += '<span class="lg"><i class="lg-solid"></i>化学品</span>' +
      '<span class="lg"><i class="lg-mat"></i>材料</span>' +
      '<span class="lg"><i class="lg-app"></i>终端应用</span>';
    document.getElementById("legend").innerHTML = h;
  }

  // ---------------------------------------------------------------- 层级关系表（兜底）
  function renderTableMode() {
    var wrapT = document.getElementById("tmScroll");
    var cols = (LAY.columns || []).slice().sort(function (a, b) { return a.col - b.col; });
    var h = [];
    var byCol = {};
    NODES.forEach(function (n) { (byCol[n.column] = byCol[n.column] || []).push(n); });
    h.push('<table class="tm"><thead><tr><th>层级（列）</th><th>节点</th><th>类别</th><th>CAS</th>' +
      "<th>上游</th><th>下游</th><th>缺口</th><th>证据</th></tr></thead><tbody>");
    cols.forEach(function (c) {
      var ns = byCol[c.col] || [];
      if (!ns.length) return;
      var meta = (D.columns || []).filter(function (x) { return x.col === c.col; })[0] || {};
      ns.sort(function (a, b) { return (a.node_role || "").localeCompare(b.node_role || ""); });
      ns.forEach(function (n, i) {
        var ups = RELS.filter(function (r) { return r.to === n.id; }).map(function (r) {
          return (NODE_BY_ID[r.from] || {}).name + "（" + typeZh(r.relation_type) + "）";
        });
        var dns = RELS.filter(function (r) { return r.from === n.id; }).map(function (r) {
          return (NODE_BY_ID[r.to] || {}).name + "（" + typeZh(r.relation_type) + "）";
        });
        h.push("<tr data-node=\"" + esc(n.id) + "\">" +
          (i === 0 ? '<td rowspan="' + ns.length + '" class="tm-col"><b>第 ' + c.col + " 列</b><br>" +
            esc(meta.label || "") + "</td>" : "") +
          '<td class="tm-node">' + esc(n.name) + "</td>" +
          "<td>" + esc({ commodity: "化学品", material: "材料", application: "终端应用" }[n.node_class] || n.node_class) + "</td>" +
          "<td>" + esc((n.cas && n.cas.value) || "不适用") + "</td>" +
          "<td>" + esc(ups.join("；") || "—") + "</td>" +
          "<td>" + esc(dns.join("；") || "—") + "</td>" +
          "<td>" + esc((n.missing_flags || []).join("、") || "—") + "</td>" +
          "<td>" + (n.evidence || []).map(function (s) { return srcChip(s); }).join(" ") + "</td></tr>");
      });
    });
    h.push("</tbody></table>");
    wrapT.innerHTML = h.join("");
    wrapT.querySelectorAll("tr[data-node]").forEach(function (tr) {
      tr.addEventListener("click", function () {
        selectNode(tr.dataset.node);
        if (!state.tableMode) focusNode(tr.dataset.node);
      });
    });
    var st = D.layoutStatus || {};
    document.getElementById("tmNote").innerHTML = st.ok
      ? "布局自检通过（重叠 " + (st.counts.overlap || 0) + " · 穿线 " + (st.counts.edge_through_node || 0) +
        " · 越界 " + (st.counts.outside || 0) + "）。本表与图谱同一数据源，可随时切换。"
      : '<span class="warn">布局自检未通过（' + JSON.stringify(st.counts || {}) +
        "），已自动降级为本表视图；节点与证据一条未丢。</span>";
  }
  function setTableMode(on) {
    state.tableMode = !!on;
    document.getElementById("tableMode").classList.toggle("show", state.tableMode);
    document.getElementById("btnTableMode").classList.toggle("active", state.tableMode);
    if (state.tableMode) document.getElementById("tableMode").scrollIntoView({ behavior: "smooth" });
  }

  // ---------------------------------------------------------------- 头部 / 页脚
  function renderHead() {
    var m = D.chain || {};
    var sub = [];
    if (m.product) sub.push("品种：" + m.product);
    if (m.chain_id) sub.push("chain_id " + m.chain_id);
    sub.push("向上 " + (m.up_layers != null ? m.up_layers : 2) + " 层 / 向下 " + (m.down_layers != null ? m.down_layers : 2) + " 层");
    document.getElementById("docSub").textContent = sub.join(" · ");
    document.getElementById("stamp").innerHTML =
      "生成时间 " + esc(D.generated_at || "") + "<br>" +
      "节点 " + NODES.length + " · 关系 " + RELS.length + " · 来源 " + (D.sources || []).length +
      "<br>离线单文件，无外链依赖";
    document.getElementById("foot").innerHTML =
      "数据口径：单耗与收率均标注化学计量/工业级/配方比等级；缺口一律登记不估算。" +
      " 覆盖完整度仅对预先冻结的核心清单有效，不代表该产业链全部可能节点与关系。";
  }

  // ---------------------------------------------------------------- 事件绑定
  function bindUI() {
    document.querySelectorAll(".sb-tab").forEach(function (b) {
      b.addEventListener("click", function () {
        var t = b.dataset.tab;
        sbShow(t);
        if (t === "node" && state.selected) renderNode(state.selected);
        else if (t === "rel") {
          var first = RELS[0];
          if (state.selected) {
            var rs = relsFor(state.selected);
            if (rs.length) renderRelation(rs[0].id);
            else if (first) renderRelation(first.id);
          } else if (first) renderRelation(first.id);
        } else renderLinkage();
      });
    });
    document.getElementById("sbClose").addEventListener("click", sbHide);
    document.getElementById("sbOpen").addEventListener("click", function () { sbShow(state.activeTab); });
    document.getElementById("btnTableMode").addEventListener("click", function () { setTableMode(!state.tableMode); });
    document.getElementById("btnCovToggle").addEventListener("click", function () {
      state.covCollapsed = !state.covCollapsed;
      document.getElementById("coverageBar").classList.toggle("collapsed", state.covCollapsed);
      setTimeout(fit, 240);
    });
    document.getElementById("btnPriceLink").addEventListener("click", function () {
      if (state.selectedList.length < 2) {
        // 若只选了一个，提示如何选第二个
        renderLinkage(); sbShow("link");
        return;
      }
      renderLinkage(); sbShow("link");
    });
    document.getElementById("relSel").addEventListener("change", function () {
      state.typeFilter = this.value; applyFilters();
    });
    document.getElementById("routeSel").addEventListener("change", function () {
      state.routeFilter = this.value; applyFilters();
    });
  }

  // ---------------------------------------------------------------- 初始化
  function init() {
    drawDefs();
    drawLanes();
    drawEdges();
    drawLabels();
    drawNodes();
    drawMinimap();
    drawLegend();
    renderCoverage();
    renderToolbar();
    renderTableMode();
    bindSearch();
    bindPanZoom();
    bindUI();
    renderHead();
    sbShow("node");
    // 默认子视图
    var firstNode = NODES.filter(function (n) { return n.node_role === "target"; })[0] || NODES[0];
    if (firstNode) { renderNode(firstNode.id); state.selected = firstNode.id; highlightPath(firstNode.id); }
    updateSelbar();
    setTimeout(fit, 60);
    window.addEventListener("resize", function () { setTimeout(fit, 80); });
    applyFilters();

    // 布局失败 → 主动降级
    if (D.layoutStatus && !D.layoutStatus.ok) {
      setTableMode(true);
      document.getElementById("tmNote").insertAdjacentHTML("beforeend",
        '<div class="warn">已自动切换到层级表：图谱仍可查看，但请先修复布局问题。</div>');
    }
  }

  // ---------------------------------------------------------------- 对外 API
  window.CHAIN = {
    selectNode: selectNode,
    selectRelation: selectRelation,
    addMulti: addMulti,
    setTableMode: setTableMode,
    fit: fit,
    fitAll: fitAll,
    zoom: zoomAt,
    focusNode: focusNode,
    state: state,
    counts: function () {
      return {
        nodes: Object.keys(NODE_ELS).length,
        edges: Object.keys(EDGE_ELS).length,
        dimmed: document.querySelectorAll(".node.dim").length,
        filtered: document.querySelectorAll(".node.filtered").length,
        filteredEdges: document.querySelectorAll(".edge.filtered").length
      };
    }
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
