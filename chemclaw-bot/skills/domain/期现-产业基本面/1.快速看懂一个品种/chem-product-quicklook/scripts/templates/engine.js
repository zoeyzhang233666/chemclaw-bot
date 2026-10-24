/* =====================================================================
 * chem-product-quicklook · 交互引擎（模板级，品种无关）
 * 数据全部来自 window.__DATA__，本文件不含任何具体品种内容。
 * 能力：首屏信息卡 / 研究指标框架 / 产业链分层图谱（展开·收起·聚焦·详情）
 *       节点详情抽屉（价格·企业·产能·项目·新闻·指标·来源）/ 下方面板 / 缺口声明
 * ===================================================================== */
(function () {
  "use strict";
  var D = window.__DATA__ || {};
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var num = function (v, d) {
    if (v == null || v === "" || isNaN(+v)) return "—";
    return (+v).toLocaleString("zh-CN", { maximumFractionDigits: d == null ? 2 : d, minimumFractionDigits: 0 });
  };
  var E = function (x) { return esc(x == null ? "—" : x); };
  var gap = function (t) { return '<span class="gapmark">⚠ ' + esc(t || "缺口") + "</span>"; };
  var isGap = function (v) { return v == null || v === "" || /^未查到|^无公开|^缺口|^待核/.test(String(v)); };

  /* ---------------- 数据索引 ---------------- */
  var P = D.product || {};
  var CH = D.chain || { nodes: [], cols: [] };
  var IDX = {};
  (CH.nodes || []).forEach(function (n) { IDX[n.id] = n; });
  var RES = D.research || {};

  function srcMap() {
    var m = {};
    (D.sources || []).forEach(function (s) { m[s.id] = s; });
    return m;
  }
  var SRC = srcMap();
  function srcInline(id) {
    var s = SRC[id];
    if (!s) return "";
    var t = s.org || s.title || id;
    return s.url
      ? '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + E(t) + "</a> · " + E(s.date || "")
      : E(t) + " · " + E(s.date || "");
  }
  function srcCell(ids) {
    if (!ids || !ids.length) return '<span class="src">来源未登记</span>';
    return '<span class="src">' + ids.map(srcInline).join("<br>") + "</span>";
  }
  var LBL = (D.meta && D.meta.labels) || {};
  function L(k) { return LBL[k] || k; }

  /* ---------------- 顶部导航 ---------------- */
  function renderNav() {
    var items = (D.panels || []).map(function (p) { return { id: "panel-" + p.id, name: p.name }; });
    items.splice(0, 0, { id: "sec-hero", name: "核心信息" }, { id: "sec-chain", name: "产业链" });
    items.push({ id: "sec-sources", name: "来源与缺口" });
    $("#navlinks").innerHTML = items.map(function (i) {
      return '<a href="#' + i.id + '">' + E(i.name) + "</a>";
    }).join("");
  }

  /* ---------------- 首屏 ---------------- */
  function renderHero() {
    var tags = [];
    if (P.hasFutures) {
      var f = RES.futures || {};
      tags.push('<span class="pill fut">场内期货：' + E(f.exchange || "") + " " + E((f.contracts || []).map(function (c) { return c.symbol; }).join("/")) + "</span>");
    } else {
      tags.push('<span class="pill nofut">无对应场内期货·不设期现模块</span>');
    }
    if (D.meta && D.meta.data_asof) tags.push('<span class="pill">数据基准：' + E(D.meta.data_asof) + "</span>");
    tags.push('<span class="pill">研究场景：' + E((P.scene || []).join(" · ")) + "</span>");
    $("#eyebrow").innerHTML = tags.join("");

    $("#htitle").innerHTML = E(P.name_cn) + '<span class="en">' + E(P.name_en) + "</span>";
    $("#hsub").innerHTML = E(P.oneliner || "");
    document.title = (D.meta && D.meta.title) || (P.name_cn + " 品种研究入口");

    // 用途切换
    var pb = $("#purposebar");
    pb.innerHTML = '<span>研究目的（切换排序与重点）：</span>' + (D.purposes || []).map(function (x, i) {
      return '<button class="chip' + (i === 0 ? " on" : "") + '" data-purpose="' + esc(x.id) + '">' + E(x.name) + "</button>";
    }).join("");
    pb.addEventListener("click", function (e) {
      var b = e.target.closest(".chip"); if (!b) return;
      $$(".chip", pb).forEach(function (x) { x.classList.remove("on"); });
      b.classList.add("on");
      applyPurpose(b.getAttribute("data-purpose"));
    });

    // 核心信息卡
    var rows = [];
    function prop(k, v, sub, wide) {
      rows.push('<div class="prop' + (wide ? " wide" : "") + '"><div class="k">' + E(k) + '</div><div class="v">' +
        (isGap(v) ? gap(v) : E(v)) + (sub ? '<span class="sub">' + E(sub) + "</span>" : "") + "</div></div>");
    }
    (P.card || []).forEach(function (c) { prop(c.k, c.v, c.sub, c.wide); });
    $("#propgrid").innerHTML = rows.join("");

    var a = [];
    if (P.aliases && P.aliases.length) a.push("<b>别名</b>" + P.aliases.map(esc).join("、"));
    if (P.synonyms_en && P.synonyms_en.length) a.push("<b>英文别名</b>" + P.synonyms_en.map(esc).join("、"));
    if (P.grades && P.grades.length) a.push("<b>主要牌号/等级</b>" + P.grades.map(E).join("；"));
    if (P.packages) a.push("<b>包装/形态</b>" + esc(P.packages));
    $("#aliasrow").innerHTML = a.join("<br>");

    $("#tagrow").innerHTML = [
      (P.cas ? '<span class="tag b">CAS ' + E(P.cas) + "</span>" : ""),
      (P.hs ? '<span class="tag b">HS ' + E((P.hs || []).map(function (h) { return h.code; }).join(" / ")) + "</span>" : ""),
      (P.un ? '<span class="tag">UN ' + E(P.un) + "</span>" : ""),
      (P.uses_cn && P.uses_cn.length ? P.uses_cn.map(function (u) { return '<span class="tag">' + E(u) + "</span>"; }).join("") : "")
    ].join("");

    $("#idconf").innerHTML = "身份置信度：" + E((P.identity_confidence || { level: "—" }).level || "—");
    $("#specpill").innerHTML = "主流规格：" + E(P.main_spec || "—");
    $("#dateline").innerHTML = "事实来源与获取日期见第 04 节 · 基准日 " + E((D.meta && D.meta.data_asof) || "—");

    renderFrame();
  }

  function renderFrame() {
    var fb = $("#framebar");
    var keys = (D.frame || []).slice();
    fb.innerHTML = keys.map(function (f, i) {
      var gapsn = (f.items || []).filter(function (x) { return x.gap; }).length;
      return '<div class="fcard" data-frame="' + i + '">' +
        '<div class="fc-t"><span>' + E(f.name) + '</span><span class="badge-count">' + (f.items || []).length + "</span></div>" +
        '<div class="fc-v">' + E(f.value || "—") + "</div>" +
        '<div class="fc-s">' + E(f.value_note || "") + (gapsn ? ' · <span class="fc-gap">⚠' + gapsn + " 项缺口</span>" : "") + "</div></div>";
    }).join("");
    fb.addEventListener("click", function (e) {
      var c = e.target.closest(".fcard"); if (!c) return;
      var f = D.frame[+c.getAttribute("data-frame")];
      location.hash = "#sec-chain";
      toast("<b>" + esc(f.name) + "</b> 框架含 " + f.items.length + " 项指标，产业链节点中以彩色小标签标注");
      setTimeout(function () { $$(".gnode").forEach(function (n, i) { if (i < 6) flash(n); }); }, 300);
    });
  }

  /* ---------------- 研究指标框架（底部） ---------------- */
  function renderIndicatorPanel() {
    var host = $("#mwall");
    D.panels.forEach(function (p) { host.appendChild(buildPanel(p)); });
  }

  /* ---------------- 产业链图 ---------------- */
  var CHAIN = { hidden: {}, focusSelf: false, purpose: (D.purposes && D.purposes[0] && D.purposes[0].id) || null };

  function nodeKind(n) {
    if (n.is_self || n.kind === "self") return "self";
    if (n.kind) return n.kind;
    return "other";
  }

  function renderChain() {
    var cols = CH.cols || [];
    var host = $("#chain");
    host.style.setProperty("--cols", cols.length || 1);
    var html = cols.map(function (c, ci) {
      var nodes = (CH.nodes || []).filter(function (n) { return n.col === c.id; });
      // 按层级排序 roots first
      nodes.sort(function (a, b) { return (a.level || 0) - (b.level || 0); });
      var items = nodes.filter(function (n) { return !CHAIN.hidden[n.id]; }).map(function (n) { return nodeHTML(n); }).join("");
      return '<div class="chcol" data-col="' + esc(c.id) + '">' +
        '<div class="chcol-head"><span class="idx">' + (ci + 1) + '</span><span class="nm">' + E(c.name) + "</span>" +
        '<span class="cnt">' + nodes.filter(function (n) { return !CHAIN.hidden[n.id]; }).length + "</span>" +
        (nodes.length ? '<span class="tg" data-col-toggle="' + esc(c.id) + '" title="整列展开/收起">⇕</span>' : "") +
        "</div>" + (items || '<div class="src" style="padding:8px 4px">本列节点已全部隐藏</div>') + "</div>";
    }).join("");
    host.innerHTML = html;
    restoreState();
    drawEdges();
  }

  /* 列间连线：把所有相邻列用贝塞尔曲线连起来，让 5 列读作“一张图”而不是 5 摞卡片。
     用 <canvas> 绝对定位覆盖在 #chain 上，pointer-events:none，随展开/收起重绘。 */
  function drawEdges() {
    var host = $("#chain");
    if (!host) return;
    var cv = host.querySelector("canvas.cedge");
    if (!cv) {
      cv = document.createElement("canvas");
      cv.className = "cedge";
      host.appendChild(cv);
    }
    var hr = host.getBoundingClientRect();
    var dpr = window.devicePixelRatio || 1;
    cv.width = Math.max(1, Math.round(hr.width * dpr));
    cv.height = Math.max(1, Math.round(hr.height * dpr));
    cv.style.width = hr.width + "px";
    cv.style.height = hr.height + "px";
    var g = cv.getContext("2d");
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, hr.width, hr.height);

    var colEls = Array.prototype.slice.call(host.querySelectorAll(".chcol"));
    if (colEls.length < 2) return;
    var L = host.scrollLeft, T = host.scrollTop;

    function anchor(el, side) {
      var r = el.getBoundingClientRect();
      return {
        x: (side === "r" ? r.right : r.left) - hr.left + L,
        y: r.top - hr.top + T + r.height / 2
      };
    }

    for (var i = 0; i < colEls.length - 1; i++) {
      var left = colEls[i].querySelectorAll(".gnode");
      var right = colEls[i + 1].querySelectorAll(".gnode");
      if (!left.length || !right.length) continue;
      // 稀疏列（如本品种只有 1 个节点）连到下一列全部节点，形成“漏斗”，视觉上补足空白
      var pairs = [];
      if (left.length === 1) {
        Array.prototype.forEach.call(right, function (rn) { pairs.push([left[0], rn]); });
      } else if (right.length === 1) {
        Array.prototype.forEach.call(left, function (ln) { pairs.push([ln, right[0]]); });
      } else {
        Array.prototype.forEach.call(left, function (ln, k) {
          pairs.push([ln, right[Math.min(k, right.length - 1)]]);
        });
      }
      pairs.forEach(function (p) {
        var a = anchor(p[0], "r"), b = anchor(p[1], "l");
        var dx = Math.max(28, (b.x - a.x) * 0.45);
        g.beginPath();
        g.moveTo(a.x + 3, a.y);
        g.bezierCurveTo(a.x + dx, a.y, b.x - dx, b.y, b.x - 3, b.y);
        g.strokeStyle = "rgba(78,161,255,.30)";
        g.lineWidth = 1.15;
        g.stroke();
        // 终点小圆点，代替箭头（箭头在密集处会糊成一团）
        g.beginPath();
        g.arc(b.x - 2, b.y, 1.9, 0, Math.PI * 2);
        g.fillStyle = "rgba(78,161,255,.55)";
        g.fill();
      });
    }
  }

  function nodeHTML(n) {
    var kids = (n.children || []).filter(function (k) { return !CHAIN.hidden[k.id]; });
    var kind = nodeKind(n);
    var metrics = (n.metrics || []).slice(0, 4);
    var badges = "";
    if (n.has_futures) badges += '<span class="kind-sel fut">期货</span>';
    if (n.cap) badges += '<span class="kind-sel">' + E(n.cap) + "</span>";
    if (n.spot) badges += '<span class="kind-sel">' + E(n.spot) + "</span>";
    metrics.forEach(function (m) { badges += '<span class="kind-sel">' + E(m) + "</span>"; });
    return '<div class="gnode' + (kids.length ? " ghas" : "") + '" data-node="' + esc(n.id) + '" data-kind="' + kind + '">' +
      '<div class="gn-top">' +
      (kids.length ? '<button class="caret" data-care="' + esc(n.id) + '" aria-label="展开或收起">＋</button>' : "") +
      '<span class="gn-t">' + E(n.name) + "</span></div>" +
      '<div class="gn-m">' + E(n.meta || "") + "</div>" +
      (badges ? '<div class="gn-b">' + badges + "</div>" : "") +
      (kids.length ? '<div class="gn-kids">' + kids.map(function (k) {
        return '<div class="gk"><span class="gk-n">' + E(k.name) + "</span>" + (k.cap ? '<span class="gk-r">' + E(k.cap) + "</span>" : "") + "</div>";
      }).join("") + "</div>" : "") +
      "</div>";
  }

  var ST = {}; // 节点状态：expanded / collapsed / focus
  function restoreState() {
    $$(".gnode").forEach(function (el) {
      var id = el.getAttribute("data-node");
      var s = ST[id] || "collapsed";
      el.classList.toggle("expanded", s === "expanded");
      el.classList.toggle("collapsed", s === "collapsed");
      el.classList.toggle("focus", s === "focus");
      var c = $(".caret", el); if (c) c.textContent = s === "expanded" ? "－" : "＋";
    });
    if (CHAIN.focusSelf) applyFocusSelf();
  }

  function setNode(id, s) {
    ST[id] = s;
    var el = $('.gnode[data-node="' + id + '"]');
    if (!el) return;
    el.classList.toggle("expanded", s === "expanded");
    el.classList.toggle("collapsed", s === "collapsed");
    var c = $(".caret", el); if (c) c.textContent = s === "expanded" ? "－" : "＋";
    markCrumb(id);
    // 节点高度因展开/收起变化，连线需要重绘（等过渡结束再算，避免画在旧位置上）
    clearTimeout(window.__edgeT);
    window.__edgeT = setTimeout(drawEdges, 240);
  }

  function allExpand(on) {
    (CH.nodes || []).forEach(function (n) {
      if (on) ST[n.id] = isGapNode(n) && !CHAIN.showGap ? "collapsed" : ((n.children || []).length ? "expanded" : "collapsed");
      else ST[n.id] = "collapsed";
    });
    restoreState();
    toast(on ? "已全部展开（" + (CH.nodes || []).length + " 个节点）" : "已全部收起");
  }
  function isGapNode(n) { return n.gap || /无数据|缺口/.test(n.meta || ""); }

  function applyFocusSelf() {
    var selfn = (CH.nodes || []).filter(function (n) { return n.is_self || n.kind === "self"; })[0];
    if (!selfn) return;
    var keep = {};
    keep[selfn.id] = 1;
    (selfn.children || []).forEach(function (c) { keep[c.id] = 1; });
    (selfn.parents || []).forEach(function (p) { keep[p] = 1; });
    (CH.nodes || []).forEach(function (n) {
      if ((n.children || []).some(function (c) { return c.id === selfn.id; })) keep[n.id] = 1;
    });
    $$(".gnode").forEach(function (el) {
      var id = el.getAttribute("data-node");
      el.style.opacity = keep[id] ? "1" : ".28";
      el.style.filter = keep[id] ? "none" : "grayscale(.7)";
    });
  }
  function clearFocusSelf() {
    $$(".gnode").forEach(function (el) { el.style.opacity = ""; el.style.filter = ""; });
  }

  function flash(el) { el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }

  function markCrumb(id) {
    var n = IDX[id]; if (!n) return;
    var path = [];
    var cur = n;
    while (cur) { path.unshift(cur); cur = IDX[cur.parent]; }
    $("#chaincrumb").innerHTML = '<span>节点面包屑：</span>' + path.map(function (x, i) {
      return (i ? " › " : "") + '<span class="c" data-go="' + esc(x.id) + '">' + E(x.name) + "</span>";
    }).join("");
  }

  /* ---------------- 抽屉 ---------------- */
  var DR = { node: null, tab: "overview" };
  var TABS = [
    { id: "overview", name: "概览与要点" },
    { id: "price", name: "价格/指标" },
    { id: "who", name: "企业与产能" },
    { id: "proj", name: "项目与新闻" },
    { id: "src", name: "来源与口径" }
  ];

  function openNode(id) {
    var n = IDX[id]; if (!n) return;
    DR.node = n; DR.tab = "overview";
    $$(".gnode").forEach(function (el) { el.classList.toggle("sel", el.getAttribute("data-node") === id); });
    $("#dr-kind").textContent = LABEL_KIND(nodeKind(n)) + (n.is_self ? " · 本研究品种" : "") + (n.level ? " · 第 " + (n.level + 1) + " 层" : "");
    $("#dr-title").innerHTML = E(n.name) + (n.name_en ? ' <span class="src">' + E(n.name_en) + "</span>" : "");
    $("#dr-sub").innerHTML = E(n.summary || n.meta || "");
    $("#dr-tabs").innerHTML = TABS.map(function (t) {
      var cnt = tabCount(n, t.id);
      return '<button data-tab="' + t.id + '"' + (t.id === "overview" ? ' class="on"' : "") + ">" + t.name + (cnt ? ' <span class="src">(' + cnt + ")</span>" : "") + "</button>";
    }).join("");
    $("#drawer").classList.add("show");
    $("#drawer").setAttribute("aria-hidden", "false");
    $("#overlay").classList.add("show");
    markCrumb(id);
    renderDrawerBody();
    setTimeout(function () { renderMiniChart(); }, 60);
  }
  function closeDrawer() {
    $("#drawer").classList.remove("show");
    $("#drawer").setAttribute("aria-hidden", "true");
    $("#overlay").classList.remove("show");
    $$(".gnode").forEach(function (el) { el.classList.remove("sel"); });
  }
  function LABEL_KIND(k) {
    return { upstream: "上游原料/能源", process: "生产工艺", self: "研究品种", downstream: "下游产品", enduse: "终端消费", other: "相关节点" }[k] || "节点";
  }
  function tabCount(n, tab) {
    var r = n.research || {};
    if (tab === "price") return ((r.prices || []).length + (r.indicators || []).length);
    if (tab === "who") return (r.companies || []).length;
    if (tab === "proj") return ((r.projects || []).length + (r.news || []).length);
    if (tab === "src") return (r.sources || n.src || []).length;
    return 0;
  }

  function renderDrawerBody() {
    var n = DR.node, r = n.research || {}, b = $("#dr-body");
    if (DR.tab === "overview") {
      var h = "";
      h += '<div class="kv">';
      h += '<div>节点类型</div><div>' + LABEL_KIND(nodeKind(n)) + "</div>";
      if (n.meta) h += "<div>关键数据</div><div>" + E(n.meta) + "</div>";
      if (n.role) h += "<div>在链条中的位置</div><div>" + E(n.role) + "</div>";
      if (n.spot_spec) h += "<div>主流规格</div><div>" + E(n.spot_spec) + "</div>";
      if (n.cap_note) h += "<div>产能口径</div><div>" + E(n.cap_note) + "</div>";
      if (r.share) h += "<div>消费占比</div><div>" + E(r.share) + "</div>";
      if (r.single_use) h += "<div>单耗/系数</div><div>" + E(r.single_use) + "</div>";
      h += "</div>";
      if (n.summary) h = "<h4>一句话定位</h4><p>" + E(n.summary) + "</p>" + h;
      (r.points || []).length && (h += "<h4>研究要点</h4><ul style='padding-left:18px;color:var(--txt-2)'>" +
        r.points.map(function (p) { return "<li>" + E(p) + "</li>"; }).join("") + "</ul>");
      (r.actions || []).length && (h += "<h4>深入场景</h4><div class='actions'>" + r.actions.map(function (a) {
        return '<div class="actcard" data-act="' + esc(a.id) + '"><span class="a1">' + E(a.name) + '</span><span class="a2">' + E(a.desc || "") + "</span></div>";
      }).join("") + "</div>");
      if ((n.children || []).length) {
        h += "<h4>子节点（" + n.children.length + "）</h4><div>";
        h += n.children.map(function (c) {
          return '<div class="gk" style="padding:5px 0;border-bottom:1px solid var(--line)"><span class="gk-n" style="cursor:pointer;color:var(--acc)" data-jump="' + esc(c.id) + '">' + E(c.name) +
            "</span><span class='gk-r'>" + E(c.cap || c.meta || "") + "</span></div>";
        }).join("");
        h += "</div>";
      }
      if ((n.parents || []).length) {
        h += "<h4>上游指向</h4><div>" + n.parents.map(function (p) {
          return '<span class="c" data-jump="' + esc(p) + '" style="cursor:pointer;border:1px solid var(--line-2);border-radius:6px;padding:1px 8px;margin:0 6px 6px 0;display:inline-block">' + E((IDX[p] || {}).name || p) + "</span>";
        }).join("") + "</div>";
      }
      b.innerHTML = h;
    }

    if (DR.tab === "price") {
      var v = "";
      if ((r.spot || []).length) {
        v += "<h4>价格锚点（六项口径）</h4>";
        v += '<div class="tablebox"><table class="mini-t"><thead><tr><th>指标</th><th>数值</th><th>单位</th><th>规格</th><th>地区</th><th>含税</th><th>日期</th></tr></thead><tbody>';
        r.spot.forEach(function (s) {
          v += "<tr><td>" + E(s.name) + '</td><td class="num">' + (isGap(s.value) ? gap(s.value) : E(s.value)) + "</td><td>" + E(s.unit) +
            "</td><td>" + E(s.spec) + "</td><td>" + E(s.region) + "</td><td>" + E(s.tax) + '</td><td class="num">' + E(s.date) + "</td></tr>";
        });
        v += "</tbody></table></div>";
        // 只有拿到真实价格序列（r.series）才画曲线。
        // 绝不生成随机/示意曲线——那会让读者把假数据当真。
        if ((r.series || []).length >= 8) {
          v += "<h4>价格走势（实测序列）</h4>";
          v += '<div id="minichart" class="mini"></div>';
          v += '<div class="src">' + E(r.series_note || "序列由原始日线计算，可回溯复算。") + "</div>";
        } else {
          v += '<div class="gapcard" style="margin-top:10px"><div class="g1">未取得可绘制的价格序列</div>' +
               '<div class="g2">' + E(r.price_gap || "本节点只有点位报价，没有连续序列，故不绘制走势图；补齐日度序列后可自动生成。") + "</div></div>";
        }
      } else if (r.price_gap) {
        v += '<div class="gapcard"><div class="g1">价格数据未取得</div><div class="g2">' + E(r.price_gap) + "</div></div>";
      }
      if ((r.indicators || []).length) {
        v += "<h4>需跟踪指标</h4><div class='tablebox'><table class='mini-t'><thead><tr><th>指标</th><th>口径/频次</th><th>为什么看</th></tr></thead><tbody>";
        r.indicators.forEach(function (i) {
          v += "<tr><td>" + E(i.name) + '</td><td class="src">' + E(i.caliber || "") + "</td><td>" + E(i.why || "") + "</td></tr>";
        });
        v += "</tbody></table></div>";
      }
      if (!v) v = '<div class="src">该节点暂无价格或指标记录（属“未覆盖”而非“无意义”）。</div>';
      b.innerHTML = v;
    }

    if (DR.tab === "who") {
      var w = "";
      if ((r.companies || []).length) {
        w += '<div class="tablebox"><table class="mini-t"><thead><tr><th>企业</th><th>基地/地区</th><th>产能</th><th>工艺/备注</th></tr></thead><tbody>';
        r.companies.slice().sort(function (a, c) { return (c.cap || 0) - (a.cap || 0); }).forEach(function (c) {
          w += "<tr><td>" + E(c.name) + '</td><td class="src">' + E(c.site) + '</td><td class="num">' + (c.cap ? num(c.cap) + " " + E(c.unit || "") : gap("未公开")) +
            '</td><td class="src">' + E(c.note || "") + "</td></tr>";
        });
        w += "</tbody></table></div>";
        w += '<p class="src" style="margin-top:8px">口径：' + E(r.company_caliber || "各企业合计名义产能，含在建未投产部分已单列；以公开披露或行业统计为准。") + "</p>";
      } else if (r.companies_gap) {
        w += '<div class="gapcard"><div class="g1">企业与产能未覆盖</div><div class="g2">' + E(r.companies_gap) + "</div></div>";
      }
      if ((r.cap_structure || []).length) {
        w += "<h4>产能结构</h4><div class='tablebox'><table class='mini-t'><thead><tr><th>口径</th><th>数值</th><th>占比</th><th>时点</th></tr></thead><tbody>";
        r.cap_structure.forEach(function (s) {
          w += "<tr><td>" + E(s.name) + '</td><td class="num">' + E(s.value) + "</td><td class='num'>" + E(s.share) + '</td><td class="num">' + E(s.date) + "</td></tr>";
        });
        w += "</tbody></table></div>";
      }
      b.innerHTML = w || '<div class="src">暂无企业与产能记录。</div>';
    }

    if (DR.tab === "proj") {
      var pj = "";
      if ((r.projects || []).length) {
        pj += "<h4>在建/规划项目</h4><div class='tablebox'><table class='mini-t'><thead><tr><th>项目</th><th>产能</th><th>状态</th><th>时间</th><th>地区</th></tr></thead><tbody>";
        r.projects.forEach(function (p) {
          pj += "<tr><td>" + E(p.name) + '</td><td class="num">' + E(p.cap) + "</td><td>" + E(p.status) + '</td><td class="num">' + E(p.when) + '</td><td class="src">' + E(p.region || "") + "</td></tr>";
        });
        pj += "</tbody></table></div>";
      }
      if ((r.news || []).length) {
        pj += "<h4>产业新闻</h4>";
        r.news.forEach(function (nw) {
          pj += '<div style="padding:8px 0;border-bottom:1px solid var(--line)"><div><b>' + E(nw.title) + '</b></div><div class="src">' +
            E(nw.date) + " · " + E(nw.org || "") + " · 影响：" + E(nw.impact || "待评估") + "</div></div>";
        });
      }
      if (!pj) pj = '<div class="gapcard"><div class="g1">项目与新闻未纳入本页</div><div class="g2">品种入门页只保留结构性事件；动态事件请进入“项目跟踪 / 资讯聚合”场景。</div></div>';
      b.innerHTML = pj;
    }

    if (DR.tab === "src") {
      var ids = (r.sources || n.src || []);
      var ss = "";
      ss += "<h4>本节点来源</h4>";
      ss += ids.length ? '<div class="tablebox"><table class="mini-t"><thead><tr><th>来源</th><th>日期</th><th>用途</th></tr></thead><tbody>' +
        ids.map(function (id) {
          var s = SRC[id] || { org: id };
          return "<tr><td>" + (s.url ? '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + E(s.title || s.org) + "</a>" : E(s.title || s.org)) +
            '</td><td class="num">' + E(s.date || "") + '</td><td class="src">' + E(s.use || "") + "</td></tr>";
        }).join("") + "</tbody></table></div>" : '<div class="src">未登记来源</div>';
      if (r.gaps && r.gaps.length) {
        ss += "<h4>本节点数据缺口</h4>" + r.gaps.map(function (g) { return '<div class="gapcard"><div class="g2">' + E(g) + "</div></div>"; }).join("");
      }
      b.innerHTML = ss;
    }

    // 事件绑定
    $$("[data-jump]", b).forEach(function (el) {
      el.addEventListener("click", function () {
        var id = el.getAttribute("data-jump");
        // 展开父节点并滚动
        var p = IDX[id];
        if (p && p.parent) setNode(p.parent, "expanded");
        openNode(id);
        var t = $('.gnode[data-node="' + id + '"]');
        if (t) { t.scrollIntoView({ block: "center", behavior: "smooth" }); flash(t); }
      });
    });
    $$("[data-act]", b).forEach(function (el) {
      el.addEventListener("click", function () { scene(el.getAttribute("data-act"), n); });
    });
  }

  function renderMiniChart() {
    var host = $("#minichart"); if (!host || typeof echarts === "undefined") return;
    var r = DR.node.research || {};
    var series = r.series || [];
    // 没有真实序列就不画：宁可空着，也不生成示意曲线
    if (series.length < 8) { host.style.display = "none"; return; }
    var xs = series.map(function (p) { return p[0]; });
    var ys = series.map(function (p) { return p[1]; });
    var c = echarts.init(host, null, { renderer: "canvas" });
    c.setOption({
      grid: { left: 52, right: 12, top: 14, bottom: 26 },
      xAxis: {
        type: "category", data: xs, boundaryGap: false,
        axisLabel: { color: "#8598b3", fontSize: 10 }, axisLine: { lineStyle: { color: "#28405d" } }
      },
      yAxis: {
        type: "value", scale: true, axisLabel: { color: "#8598b3", fontSize: 10 },
        splitLine: { lineStyle: { color: "#16263a" } }
      },
      series: [{
        type: "line", data: ys, smooth: false, symbol: "none",
        lineStyle: { color: "#4ea1ff", width: 1.6 },
        areaStyle: { color: "rgba(78,161,255,.12)" }
      }],
      tooltip: { trigger: "axis" }
    });
    window.addEventListener("resize", function () { c.resize(); });
  }

  function toast(html) {
    var t = $("#toast"); t.innerHTML = html; t.classList.add("show");
    clearTimeout(t.__h); t.__h = setTimeout(function () { t.classList.remove("show"); }, 2400);
  }

  /* ---------------- 深入场景（本地可用的“接口”） ---------------- */
  function scene(actId, node) {
    var sc = (D.scenes || {})[actId];
    var name = (node && node.name) || (IDX[actId] && IDX[actId].name) || "本品种";
    if (!sc) { toast("场景 <b>" + esc(actId) + "</b> 未在本页登记"); return; }
    var msg = sc.template ? sc.template.replace(/\{node\}/g, name).replace(/\{product\}/g, P.name_cn || "") : sc.name;
    toast("已生成研究任务：<b>" + esc(msg) + "</b><br><span style='color:var(--txt-3)'>复制去对应技能/数据源执行：" + esc((sc.skill || "")) + "</span>");
  }

  /* ---------------- 下方面板 ---------------- */
  function buildPanel(p) {
    var wrap = document.createElement("div");
    wrap.className = "mpanel";
    wrap.id = "panel-" + p.id;
    var h = "";
    if (p.note) h += '<p class="src" style="margin:0 0 12px">' + E(p.note) + "</p>";
    h += (p.body || []).map(renderBlock).join("");
    wrap.innerHTML = h;
    return wrap;
  }

  function renderBlock(b) {
    var t = b.type || "text";
    if (t === "text") return "<div class='card'><h3>" + E(b.title || "") + "</h3>" + (b.lead ? "<p class='lead'>" + E(b.lead) + "</p>" : "") +
      (b.html ? b.html : "") + (b.src ? "<p class='src'>来源：" + srcInline(b.src[0]) + "</p>" : "") + "</div>";
    if (t === "cards") {
      return "<div class='grid" + (b.cols || 2) + "'>" + (b.items || []).map(function (it) {
        return "<div class='card'><h3>" + E(it.title) + "</h3>" + (it.lead ? "<p class='lead'>" + E(it.lead) + "</p>" : "") +
          (it.lines || []).map(function (l) { return "<div style='font-size:12.9px;padding:3px 0;border-bottom:1px solid var(--line)'><b>" + E(l.k) + "</b>　" + (isGap(l.v) ? gap(l.v) : E(l.v)) + (l.sub ? "<div class='src'>" + E(l.sub) + "</div>" : "") + "</div>"; }).join("") +
          (it.src ? "<p class='src' style='margin:8px 0 0'>来源：" + (it.src || []).map(function (s) { return srcInline(s); }).join(" · ") + "</p>" : "") +
          "</div>";
      }).join("") + "</div>";
    }
    if (t === "table") {
      return "<div class='tablebox'><table class='data'>" + (b.caption ? "<caption>" + E(b.caption) + "</caption>" : "") +
        "<thead><tr>" + (b.columns || []).map(function (c) { return "<th>" + E(c.k || c) + "</th>"; }).join("") + "</tr></thead><tbody>" +
        (b.rows || []).map(function (r) {
          return "<tr>" + (b.columns || []).map(function (c) {
            var key = c.k || c, v = r[key];
            if (key === "src" || (c.type === "src")) return "<td>" + srcCell(r.src || r.srcs) + "</td>";
            if (c.type === "num") return "<td class='num'>" + (isGap(v) ? gap(v) : E(v)) + "</td>";
            return "<td>" + (isGap(v) ? gap(v) : E(v)) + "</td>";
          }).join("") + "</tr>";
        }).join("") + "</tbody></table></div>";
    }
    if (t === "routes") {
      return (b.items || []).map(function (r, i) {
        return "<div class='route " + (r.active === false ? "conv" : "") + "' data-route='" + i + "'>" +
          "<div class='route-h'><span class='rh-t'>" + E(r.name) + "</span><span class='rh-sub'>" + E(r.brief || "") + "</span>" +
          "<span class='rh-meta'>" + (r.share ? '<span class="pill">产能占比 ' + E(r.share) + "</span>" : "") +
          (r.status ? '<span class="pill ' + (/示范|中试|试验/.test(r.status) ? "warn" : "ok") + '">' + E(r.status) + "</span>" : "") +
          '<span class="caret" style="width:22px;height:22px">＋</span></span></div>' +
          "<div class='route-body'>" +
          ((r.steps || []).length ? "<div class='steps'>" + r.steps.map(function (s) {
            return "<div class='step'><div class='s1'>" + E(s.name) + "</div><div class='s2'>" + E(s.note || "") + "</div></div>";
          }).join("") + "</div>" : "") +
          ((r.params || []).length ? "<div class='params'>" + r.params.map(function (x) {
            return "<div class='param'><div class='p1'>" + E(x.k) + "</div><div class='p2'>" + E(x.v) + "</div><div class='p3'>" + E(x.note || "") + "</div></div>";
          }).join("") + "</div>" : "") +
          (r.body ? "<p style='font-size:13px;color:var(--txt-2)'>" + E(r.body) + "</p>" : "") +
          (r.src ? "<p class='src'>来源：" + r.src.map(function (s) { return srcInline(s); }).join(" · ") + "</p>" : "") +
          "</div></div>";
      }).join("");
    }
    if (t === "companies") {
      var max = Math.max.apply(null, (b.items || []).map(function (c) { return c.cap || 0; }).concat([1]));
      return "<div class='tablebox'><table class='data'><caption>" + E(b.caption || "") + "</caption><thead><tr><th>#</th><th>企业</th><th>基地/地区</th><th>公开产能</th><th>工艺</th><th>占比</th><th>来源</th></tr></thead><tbody>" +
        (b.items || []).map(function (c, i) {
          var pct = b.total ? (c.cap / b.total * 100) : 0;
          return "<tr><td class='num'>" + (i + 1) + "</td><td><b>" + E(c.name) + "</b></td><td class='src'>" + E(c.site) + "</td>" +
            "<td class='num'>" + (c.cap ? num(c.cap) + " " + E(c.unit || b.unit || "万吨") : gap("未公开")) + "</td><td>" + E(c.process || "") + "</td>" +
            "<td><div class='bar' title='" + pct.toFixed(1) + "%'><i style='width:" + Math.min(100, c.cap / max * 100).toFixed(1) + "%'></i></div><span class='num' style='font-size:11px;color:var(--txt-3)'>" + (b.total ? pct.toFixed(1) + "%" : "") + "</span></td>" +
            "<td>" + srcCell(c.src) + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }
    if (t === "regions") {
      return "<div class='regions'>" + (b.items || []).map(function (r) {
        return "<div class='region'><h4>" + E(r.name) + "<span class='src'>" + E(r.share || "") + "</span></h4>" +
          "<div class='r1'>" + E(r.scope || "") + "</div>" +
          "<div class='r2'>" + E(r.value || "—") + "<small>" + E(r.unit || "") + "</small></div>" +
          "<div class='r3'>" + E(r.note || "") + "</div>" +
          (r.mix ? "<div class='rbar'>" + r.mix.map(function (m) { return "<i style='width:" + m.p + "%;background:" + m.c + "' title='" + E(m.n) + " " + m.p + "%'></i>"; }).join("") + "</div>" : "") +
          "</div>";
      }).join("") + "</div>" + (b.src ? "<p class='src'>来源：" + b.src.map(function (s) { return srcInline(s); }).join(" · ") + "</p>" : "");
    }
    if (t === "indicators") {
      return (b.groups || []).map(function (g, gi) {
        return "<h4 style='font-size:13px;color:var(--txt-3);margin:14px 0 8px;text-transform:uppercase'>" + E(g.name) + (g.src ? "　<span class='src'>来源:" + srcInline(g.src[0]) + "</span>" : "") + "</h4>" +
          (g.items || []).map(function (it, ii) {
            return "<div class='ind' data-ind='" + gi + "-" + ii + "'><div class='ind-h'><span class='ih-t'>" + E(it.name) + "</span>" +
              "<span class='ih-c'>" + E(it.caliber || "") + "</span>" +
              "<span class='ih-r'>" + (it.freq ? "<span class='pill'>" + E(it.freq) + "</span>" : "") +
              "<span class='imp " + (/高/.test(it.importance) ? "hi" : /中/.test(it.importance) ? "mid" : "lo") + "'>影响" + E(it.importance || "—") + "</span></span></div>" +
              "<div class='ind-b'><ul>" + (it.points || []).map(function (p) { return "<li>" + E(p) + "</li>"; }).join("") + "</ul>" +
              (it.src ? "<p class='src'>来源：" + it.src.map(function (s) { return srcInline(s); }).join(" · ") + "</p>" : "") + "</div></div>";
          }).join("");
      }).join("");
    }
    if (t === "logic") {
      return "<div class='logic'>" + (b.items || []).map(function (lc) {
        return "<div class='lchain'><h4>" + E(lc.name) + "</h4><div class='ls'>" + E(lc.sub || "") + "</div>" +
          (lc.steps || []).map(function (s, i) { return "<div class='lstep'><span class='ln'>" + (i + 1) + "</span><div>" + s + "</div></div>"; }).join("") +
          (lc.src ? "<p class='src'>依据：" + srcInline(lc.src[0]) + "</p>" : "") + "</div>";
      }).join("") + "</div>";
    }
    if (t === "futures") {
      return "<div class='grid2'>" + (b.items || []).map(function (f) {
        return "<div class='card'><h3>" + E(f.title) + "</h3>" + (f.lead ? "<p class='lead'>" + E(f.lead) + "</p>" : "") +
          "<div class='kv'>" + f.rows.map(function (r) { return "<div>" + E(r.k) + "</div><div>" + (isGap(r.v) ? gap(r.v) : E(r.v)) + "</div>"; }).join("") + "</div>" +
          (f.src ? "<p class='src' style='margin-top:8px'>来源：" + f.src.map(function (s) { return srcInline(s); }).join(" · ") + "</p>" : "") + "</div>";
      }).join("") + "</div>";
    }
    if (t === "gapnote") {
      return "<div style='border:1px dashed rgba(245,165,36,.45);border-radius:12px;padding:16px 18px;background:rgba(245,165,36,.05)'>" +
        "<b style='color:#fcd34d'>" + E(b.title) + "</b><p style='color:var(--txt-2);margin:6px 0 0'>" + E(b.text) + "</p></div>";
    }
    return "";
  }

  function bindPanels() {
    var tabs = $("#mtab"), wall = $("#mwall");
    tabs.innerHTML = D.panels.map(function (p, i) {
      return '<button data-panel="' + esc(p.id) + '"' + (i === 0 ? ' class="on"' : "") + '><span class="n">' + ("0" + (i + 1)).slice(-2) + "</span>" + E(p.name) + "</button>";
    }).join("");
    tabs.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      switchPanel(b.getAttribute("data-panel"));
    });
    wall.addEventListener("click", function (e) {
      var rh = e.target.closest(".route-h");
      if (rh) { rh.parentElement.classList.toggle("open"); var c = $(".caret", rh); if (c) c.textContent = rh.parentElement.classList.contains("open") ? "－" : "＋"; }
      var ih = e.target.closest(".ind-h");
      if (ih) ih.parentElement.classList.toggle("open");
    });
    switchPanel(D.panels[0] && D.panels[0].id);
  }
  function switchPanel(id) {
    $$("#mtab button").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-panel") === id); });
    $$(".mpanel").forEach(function (p) { p.classList.toggle("on", p.id === "panel-" + id); });
    if (location.hash.indexOf("#panel-") !== 0) history.replaceState(null, "", "#panel-" + id);
  }

  /* ---------------- 来源与缺口 ---------------- */
  function renderSources() {
    var sl = $("#srclist");
    sl.innerHTML = (D.sources || []).map(function (s) {
      var t = s.url ? '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + E(s.title || s.org) + "</a>" : "<b>" + E(s.title || s.org) + "</b>";
      return "<li>" + t + ' <span class="src">' + E(s.org || "") + " · " + E(s.date || "") + (s.type ? " · " + E(s.type) : "") + (s.use ? " · " + E(s.use) : "") + "</span></li>";
    }).join("");
    $("#gaps").innerHTML = (D.gaps || []).map(function (g) {
      return '<div class="gapcard"><div class="g1">' + E(g.area) + '</div><div class="g2">' + E(g.desc) + '</div><div class="g3">处理：' + E(g.how || "留空并标注缺口，不以推测填充") + "</div></div>";
    }).join("");
    $("#caveats").innerHTML = (D.caveats || []).map(function (c) { return "<div style='font-size:12.8px;padding:6px 0;border-bottom:1px solid var(--line)'>" + E(c) + "</div>"; }).join("");
    $("#footnote").innerHTML = E((D.meta && D.meta.footnote) || "");
    $("#builtby").innerHTML = "生成器：chem-product-quicklook · 生成日期 " + E((D.meta && D.meta.generated) || "") + " · 数据基准 " + E((D.meta && D.meta.data_asof) || "");
    $("#chainlegend").innerHTML = [
      ["#4ea1ff", "工艺/装置路径"], ["#a78bfa", "本品种或期货"], ["#22d3b2", "上游原料"], ["#f5a524", "下游需求"], ["#6d829d", "终端/关联"]
    ].map(function (x) { return '<span><i style="background:' + x[0] + '"></i>' + x[1] + "</span>"; }).join("") +
      '<span>子节点指示灯：绿点表示该节点可展开</span>';
  }

  /* ---------------- 交互绑定 ---------------- */
  function bindChain() {
    var host = $("#chain");
    host.addEventListener("click", function (e) {
      var caret = e.target.closest(".caret");
      var colTg = e.target.closest("[data-col-toggle]");
      if (colTg) {
        var col = colTg.getAttribute("data-col-toggle");
        var nodes = (CH.nodes || []).filter(function (n) { return n.col === col && (n.children || []).length; });
        var anyCollapsed = nodes.some(function (n) { return ST[n.id] !== "expanded"; });
        nodes.forEach(function (n) { ST[n.id] = anyCollapsed ? "expanded" : "collapsed"; });
        restoreState(); toast((anyCollapsed ? "展开" : "收起") + "「" + ($(".chcol[data-col='" + col + "'] .nm") || {}).textContent + "」列全部节点");
        return;
      }
      if (caret) {
        e.stopPropagation();
        var id = caret.getAttribute("data-care");
        setNode(id, ST[id] === "expanded" ? "collapsed" : "expanded");
        return;
      }
      var g = e.target.closest(".gnode");
      if (g) openNode(g.getAttribute("data-node"));
    });
    host.addEventListener("dblclick", function (e) {
      var g = e.target.closest(".gnode"); if (!g) return;
      var id = g.getAttribute("data-node");
      openNode(id);
    });
    $("#chaincrumb").addEventListener("click", function (e) {
      var t = e.target.closest("[data-go]"); if (!t) return;
      openNode(t.getAttribute("data-go"));
      var el = $('.gnode[data-node="' + t.getAttribute("data-go") + '"]');
      if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
    });

    $("#btn-expand-all").addEventListener("click", function () { CHAIN.showGap = true; allExpand(true); });
    $("#btn-collapse-all").addEventListener("click", function () { allExpand(false); });
    $("#btn-expand-chain").addEventListener("click", function () {
      (CH.nodes || []).forEach(function (n) { ST[n.id] = "expanded"; });
      restoreState(); toast("已展开全部层级，拖动横向查看各列");
    });
    $("#btn-reset-chain").addEventListener("click", function () {
      CHAIN.hidden = {}; CHAIN.focusSelf = false; CHAIN.showGap = false;
      $("#chk-hide-gap").checked = false; $("#chk-focus-self").checked = false;
      (CH.nodes || []).forEach(function (n) { delete ST[n.id]; });
      renderChain(); clearFocusSelf(); toast("拓扑已重置");
    });
    $("#btn-uncollapse-link").addEventListener("click", function () {
      // 展开与当前选中节点相连的所有父/子节点
      var sel = $(".gnode.sel"); var id = sel ? sel.getAttribute("data-node") : (DR.node && DR.node.id);
      if (!id) { toast("先在图中点选一个节点"); return; }
      var n = IDX[id]; if (!n) return;
      if (n.parent) ST[n.parent] = "expanded";
      (n.parents || []).forEach(function (p) { var pp = IDX[p]; if (pp && pp.parent) ST[pp.parent] = "expanded"; });
      (n.children || []).forEach(function (c) { ST[c.id] = (ST[c.id] === "collapsed" ? "collapsed" : "expanded"); });
      ST[id] = "expanded"; restoreState(); toast("已展开与「" + esc(n.name) + "」相连的节点");
    });
    $("#chk-hide-gap").addEventListener("change", function () {
      CHAIN.showGap = !this.checked;
      (CH.nodes || []).forEach(function (n) {
        if (!CHAIN.showGap && isGapNode(n)) CHAIN.hidden[n.id] = true; else delete CHAIN.hidden[n.id];
      });
      renderChain();
    });
    $("#chk-focus-self").addEventListener("change", function () {
      CHAIN.focusSelf = this.checked;
      if (this.checked) applyFocusSelf(); else clearFocusSelf();
    });

    $("#dr-close").addEventListener("click", closeDrawer);
    $("#overlay").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDrawer();
      if (e.key === "e" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); ($$(".gnode").every(function (g) { return g.classList.contains("expanded"); }) ? allExpand(false) : (CHAIN.showGap = true, allExpand(true))); }
    });
    $("#dr-tabs").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      DR.tab = b.getAttribute("data-tab");
      $$("#dr-tabs button").forEach(function (x) { x.classList.toggle("on", x === b); });
      renderDrawerBody();
      if (DR.tab === "price") setTimeout(renderMiniChart, 40);
    });
  }

  function applyPurpose(pid) {
    CHAIN.purpose = pid;
    var pr = (D.purposes || []).filter(function (p) { return p.id === pid; })[0] || {};
    if (pr.panel) switchPanel(pr.panel);
    if ((pr.emphasize || []).length) {
      $$(".gnode").forEach(function (el) {
        var n = IDX[el.getAttribute("data-node")];
        var hit = n && (pr.emphasize.indexOf(n.id) >= 0 || pr.emphasize.indexOf(n.kind) >= 0);
        el.style.borderColor = hit ? "rgba(34,211,178,.75)" : "";
        el.style.background = hit ? "rgba(34,211,178,.07)" : "";
      });
    }
    $$(".ind").forEach(function (el) {
      var d = el.getAttribute("data-ind");
      el.style.outline = (pr.highlight_indicators || []).indexOf(d) >= 0 ? "1px solid rgba(34,211,178,.6)" : "";
    });
    toast("研究重点已切换到：<b>" + esc(pr.name || pid) + "</b>");
  }

  /* ---------------- 启动 ---------------- */
  function boot() {
    renderNav(); renderHero(); renderIndicatorPanel(); bindPanels(); renderChain(); bindChain();
    renderSources();
    // 默认：本品种节点展开一次，便于首屏阅读
    (CH.nodes || []).forEach(function (n) {
      if ((n.is_self || n.kind === "self") && (n.children || []).length) ST[n.id] = "expanded";
      if (n.default_open && (n.children || []).length) ST[n.id] = "expanded";
    });
    restoreState();
    if (location.hash && location.hash.indexOf("#panel-") === 0) switchPanel(location.hash.slice(7));
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
