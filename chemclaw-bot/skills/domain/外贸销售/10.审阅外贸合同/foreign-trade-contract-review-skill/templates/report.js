/* ============================================================
   外贸合同审阅报告 — 交互脚本
   Foreign Trade Contract Review Report — interaction layer

   Data is injected by build_report.py as window.__REVIEW__.
   Edits (owner / status / note) are persisted in localStorage and
   can be exported to CSV or JSON for legal review.
   ============================================================ */
(function () {
  "use strict";

  var DATA = window.__REVIEW__ || { issues: [], categories: [], severities: [], meta: {} };
  var STORE_KEY = "ftc-review:" + (DATA.meta.contract_no || "default");

  var state = {
    category: "__all__",
    severity: "__all__",
    status: "__all__",
    query: "",
    view: "split",
    activeIssue: null,
    open: {}
  };

  var edits = load();

  /* ---------------- storage ---------------- */
  function load() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function save() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(edits));
      return true;
    } catch (e) {
      // localStorage is unavailable in some private/embedded contexts.
      // The report stays fully usable; state simply will not persist.
      if (!save._warned) {
        save._warned = true;
        if (typeof console !== "undefined") {
          console.warn("localStorage unavailable; annotations will not persist:", e);
        }
      }
      return false;
    }
  }

  function editOf(id) {
    if (!edits[id]) edits[id] = { owner: "", status: "待处理", note: "" };
    return edits[id];
  }

  /* ---------------- helpers ---------------- */
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function catMeta(key) {
    for (var i = 0; i < DATA.categories.length; i++) {
      if (DATA.categories[i].key === key) return DATA.categories[i];
    }
    return { key: key, label: key, color: "#64748b" };
  }

  function sevMeta(key) {
    for (var i = 0; i < DATA.severities.length; i++) {
      if (DATA.severities[i].key === key) return DATA.severities[i];
    }
    return { key: key, label: key, color: "#64748b" };
  }

  function statusOf(id) {
    var e = edits[id];
    return (e && e.status) ? e.status : "待处理";
  }

  function statusClass(s) {
    if (s === "已解决") return "st-done";
    if (s === "处理中") return "st-progress";
    if (s === "需法务确认") return "st-pending";
    return "st-open";
  }

  var STATUSES = ["待处理", "处理中", "需法务确认", "已解决", "不适用"];

  function toast(msg) {
    var t = $("#toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._t);
    t._t = setTimeout(function () { t.classList.remove("show"); }, 2200);
  }

  /* ---------------- filtering ---------------- */
  function matches(issue) {
    if (state.category !== "__all__" && issue.category !== state.category) return false;
    if (state.severity !== "__all__" && issue.severity !== state.severity) return false;
    if (state.status !== "__all__" && statusOf(issue.id) !== state.status) return false;
    if (state.query) {
      var q = state.query.toLowerCase();
      var hay = [
        issue.id, issue.title, issue.title_en, issue.clause_title,
        issue.finding, issue.finding_en, issue.consequence, issue.consequence_en,
        (issue.confirm || []).join(" "),
        (issue.anchors || []).map(function (a) { return a.quote + " " + a.clause; }).join(" ")
      ].join(" ").toLowerCase();
      if (hay.indexOf(q) === -1) return false;
    }
    return true;
  }

  /* ---------------- render: contract markers ---------------- */
  function decorateContract() {
    var riskByBlock = {};
    DATA.issues.forEach(function (iss) {
      (iss.anchors || []).forEach(function (a) {
        if (!a.block) return;
        if (!riskByBlock[a.block]) riskByBlock[a.block] = [];
        riskByBlock[a.block].push(iss);
      });
    });

    Object.keys(riskByBlock).forEach(function (bid) {
      var el = document.querySelector('[data-bid="' + bid + '"]');
      if (!el) return;
      var list = riskByBlock[bid];
      var worst = "low";
      if (list.some(function (i) { return i.severity === "high"; })) worst = "high";
      else if (list.some(function (i) { return i.severity === "medium"; })) worst = "medium";

      el.classList.add("has-risk", "sev-" + worst);
      el.setAttribute("data-risks", list.map(function (i) { return i.id; }).join(","));

      var holder = el;
      if (el.tagName === "TABLE") {
        holder = el.parentNode;
        holder.classList.add("has-risk", "sev-" + worst);
        holder.setAttribute("data-bid", bid);
      }

      list.forEach(function (iss, idx) {
        var m = document.createElement("span");
        m.className = "risk-marker sev-" + iss.severity;
        m.textContent = String(iss.seq);
        m.title = iss.id + " · " + iss.title;
        m.setAttribute("data-issue", iss.id);
        m.addEventListener("click", function (ev) {
          ev.stopPropagation();
          focusIssue(iss.id, true);
        });
        holder.appendChild(m);
      });
    });

    $$("[data-bid].has-risk").forEach(function (el) {
      el.addEventListener("click", function (ev) {
        if (ev.target.classList && ev.target.classList.contains("risk-marker")) return;
        var ids = (el.getAttribute("data-risks") || "").split(",").filter(Boolean);
        if (!ids.length) return;
        focusIssue(ids[0], false);
      });
    });

    // wrap exec columns in a two-up block
    var cols = $$(".b-p.exec-col");
    if (cols.length >= 2) {
      var wrap = document.createElement("div");
      wrap.className = "exec-block";
      cols[0].parentNode.insertBefore(wrap, cols[0]);
      cols.forEach(function (c) { wrap.appendChild(c); });
    }
  }

  /* ---------------- render: issue cards ---------------- */
  function renderCards() {
    var host = $("#cards");
    var shown = DATA.issues.filter(matches);
    $("#rp-count").textContent = shown.length + " / " + DATA.issues.length + " 条";

    if (!shown.length) {
      host.innerHTML = '<div class="empty-state">没有符合当前筛选条件的风险条目。<br>请调整主题、等级或状态筛选。</div>';
      return;
    }

    var html = shown.map(function (iss) {
      var e = editOf(iss.id);
      var isOpen = state.open[iss.id];
      var cat = catMeta(iss.category);
      var st = statusOf(iss.id);

      var anchors = (iss.anchors || []).map(function (a) {
        return '<div class="quote-box">' +
          '<div class="qloc"><span>' + esc(a.clause || "") + '</span>' +
          '<button class="jump-btn" data-jump="' + esc(a.block) + '">定位原文 ↓</button></div>' +
          '<div class="qtext">' + esc(a.quote || "") + '</div></div>';
      }).join("");

      var confirms = (iss.confirm || []).map(function (c) {
        return "<li>" + esc(c) + "</li>";
      }).join("");

      var refs = (iss.legal_refs || []).map(function (r) {
        return '<div class="legal-chip"><span class="llabel">' + esc(r.label) +
          '</span><span class="lnote">' + esc(r.note) + "</span></div>";
      }).join("");

      var statusOpts = STATUSES.map(function (s) {
        return '<option value="' + esc(s) + '"' + (s === st ? " selected" : "") + ">" + esc(s) + "</option>";
      }).join("");

      return '<article class="icard' + (isOpen ? " open" : "") + '" id="card-' + esc(iss.id) + '" data-issue="' + esc(iss.id) + '">' +
        '<div class="icard-head" data-toggle="' + esc(iss.id) + '">' +
          '<div class="sevbar sev-' + esc(iss.severity) + '"></div>' +
          '<div class="icard-head-main">' +
            '<div class="icard-title-row">' +
              '<span class="iid">' + esc(iss.id) + "</span>" +
              '<span class="icard-title">' + esc(iss.title) + "</span>" +
            "</div>" +
            '<div class="icard-meta">' +
              '<span class="tag sev-' + esc(iss.severity) + '">' + esc(sevMeta(iss.severity).label) + "</span>" +
              '<span class="tag cat" style="border-left:3px solid ' + esc(cat.color) + '">' + esc(cat.label) + "</span>" +
              (iss.category === "missing" ? '<span class="tag missing">缺失条款</span>' : "") +
              '<span class="tag ' + statusClass(st) + '">' + esc(st) + "</span>" +
              (e.owner ? '<span style="color:#475569">· 负责人 ' + esc(e.owner) + "</span>" : "") +
              "<span>· " + esc(iss.clause_title || "") + "</span>" +
            "</div>" +
          "</div>" +
          '<span class="chev">▶</span>' +
        "</div>" +
        '<div class="icard-body">' +
          '<div class="isec"><div class="isec-label q"><span class="bar"></span>合同原文位置 / Contract text</div>' +
            '<div class="isec-body">' + (anchors || '<p style="color:#94a3b8">（本条为条款缺失事项，无对应原文，见下方说明）</p>') + "</div></div>" +

          '<div class="isec"><div class="isec-label f"><span class="bar"></span>问题说明 / Finding</div>' +
            '<div class="isec-body"><p>' + esc(iss.finding) + "</p>" +
            (iss.finding_en ? '<div class="en">' + esc(iss.finding_en) + "</div>" : "") + "</div></div>" +

          '<div class="isec"><div class="isec-label c"><span class="bar"></span>潜在商务后果 / Commercial consequence</div>' +
            '<div class="consequence">' + esc(iss.consequence) +
            (iss.consequence_en ? '<div class="en">' + esc(iss.consequence_en) + "</div>" : "") + "</div></div>" +

          '<div class="isec"><div class="isec-label t"><span class="bar"></span>需要进一步确认 / To be confirmed</div>' +
            '<ul class="confirm-list">' + confirms + "</ul></div>" +

          (refs ? '<div class="isec"><div class="isec-label l"><span class="bar"></span>相关法律与规则（需律师复核）/ Legal refs</div>' +
            '<div class="isec-body">' + refs + "</div></div>" : "") +

          (iss.suggested_wording ? '<div class="isec"><div class="isec-label w"><span class="bar"></span>建议修改措辞（草案）/ Suggested wording</div>' +
            '<div class="suggest">' + esc(iss.suggested_wording) + "</div></div>" : "") +

          '<div class="track">' +
            '<div class="field"><label>负责人 / Owner</label>' +
              '<input data-f="owner" data-id="' + esc(iss.id) + '" value="' + esc(e.owner) + '" placeholder="填写跟进负责人"></div>' +
            '<div class="field"><label>处理状态 / Status</label>' +
              '<select data-f="status" data-id="' + esc(iss.id) + '">' + statusOpts + "</select></div>" +
            '<div class="field track-full"><label>备注 / Note</label>' +
              '<textarea data-f="note" data-id="' + esc(iss.id) + '" rows="2" placeholder="记录与客户、法务的沟通结论">' + esc(e.note) + "</textarea></div>" +
          "</div>" +
        "</div>" +
      "</article>";
    }).join("");

    host.innerHTML = html;
    bindCardEvents(host);
  }

  function bindCardEvents(host) {
    $$("[data-toggle]", host).forEach(function (el) {
      el.addEventListener("click", function (ev) {
        if (ev.target.closest && ev.target.closest("[data-jump]")) return;
        var id = el.getAttribute("data-toggle");
        var card = $("#card-" + id);
        card.classList.toggle("open");
        state.open[id] = card.classList.contains("open");
      });
    });

    $$("[data-jump]", host).forEach(function (el) {
      el.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var bid = el.getAttribute("data-jump");
        scrollToBlock(bid);
      });
    });

    $$("[data-f]", host).forEach(function (el) {
      var evt = el.tagName === "SELECT" ? "change" : "input";
      el.addEventListener(evt, function () {
        var id = el.getAttribute("data-id");
        var f = el.getAttribute("data-f");
        var e = editOf(id);
        e[f] = el.value;
        save();
        if (f === "status") {
          var card = $("#card-" + id);
          var tag = card.querySelector(".icard-meta .tag[class*='st-']");
          if (tag) { tag.className = "tag " + statusClass(el.value); tag.textContent = el.value; }
          if (state.status !== "__all__") renderCards();
        }
      });
    });
  }

  /* ---------------- locate ---------------- */
  function scrollToBlock(bid) {
    var el = document.querySelector('[data-bid="' + bid + '"]');
    if (!el) {
      toast("未在合同文本中找到该位置");
      return;
    }
    $$(".active-highlight").forEach(function (n) { n.classList.remove("active-highlight"); });
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    void el.offsetWidth;
    el.classList.add("active-highlight");
    setTimeout(function () { el.classList.remove("active-highlight"); }, 2600);
  }

  function focusIssue(id, fromContract) {
    if (state.view === "overview") switchView("split");
    state.activeIssue = id;
    state.open[id] = true;
    renderCards();

    var card = $("#card-" + id);
    if (card) {
      if (!card.classList.contains("open")) card.classList.add("open");
      card.scrollIntoView({ behavior: "smooth", block: "start" });
      $$(".icard.active").forEach(function (n) { n.classList.remove("active"); });
      card.classList.add("active");
    }

    if (!fromContract) {
      var iss = DATA.issues.filter(function (i) { return i.id === id; })[0];
      if (iss && iss.anchors && iss.anchors.length) scrollToBlock(iss.anchors[0].block);
    }
  }

  /* ---------------- filters ---------------- */
  function renderChips() {
    var host = $("#chips");
    var counts = {};
    DATA.issues.forEach(function (i) { counts[i.category] = (counts[i.category] || 0) + 1; });

    var html = '<button class="chip' + (state.category === "__all__" ? " active" : "") +
      '" data-cat="__all__">全部主题<span class="cnt">' + DATA.issues.length + "</span></button>";

    html += DATA.categories.map(function (c) {
      return '<button class="chip' + (state.category === c.key ? " active" : "") + '" data-cat="' + c.key + '">' +
        '<span class="swatch" style="background:' + c.color + '"></span>' + esc(c.label) +
        '<span class="cnt">' + (counts[c.key] || 0) + "</span></button>";
    }).join("");

    host.innerHTML = html;
    $$("[data-cat]", host).forEach(function (el) {
      el.addEventListener("click", function () {
        state.category = el.getAttribute("data-cat");
        renderChips();
        renderCards();
        renderVisibility();
      });
    });
  }

  function renderSevChips() {
    var host = $("#sevchips");
    var counts = { high: 0, medium: 0, low: 0 };
    DATA.issues.forEach(function (i) { counts[i.severity]++; });

    var html = '<button class="chip' + (state.severity === "__all__" ? " active" : "") +
      '" data-sev="__all__">全部等级</button>' +
      DATA.severities.map(function (s) {
        return '<button class="chip' + (state.severity === s.key ? " active" : "") + '" data-sev="' + s.key + '">' +
          '<span class="swatch" style="background:' + s.color + '"></span>' + esc(s.label) +
          '<span class="cnt">' + counts[s.key] + "</span></button>";
      }).join("");

    host.innerHTML = html;
    $$("[data-sev]", host).forEach(function (el) {
      el.addEventListener("click", function () {
        state.severity = el.getAttribute("data-sev");
        renderSevChips();
        renderCards();
      });
    });
  }

  function renderStatusFilter() {
    var sel = $("#statusfilter");
    var counts = {};
    DATA.issues.forEach(function (i) {
      var s = statusOf(i.id);
      counts[s] = (counts[s] || 0) + 1;
    });
    sel.innerHTML = '<option value="__all__">全部状态 (' + DATA.issues.length + ")</option>" +
      STATUSES.map(function (s) {
        return '<option value="' + esc(s) + '">' + esc(s) + " (" + (counts[s] || 0) + ")</option>";
      }).join("");
    sel.value = state.status;
  }

  /* ---------------- overview ---------------- */
  function renderOverview() {
    var m = DATA.meta;
    var byCat = {}, bySev = { high: 0, medium: 0, low: 0 };
    DATA.issues.forEach(function (i) {
      byCat[i.category] = (byCat[i.category] || 0) + 1;
      bySev[i.severity]++;
    });

    var maxCat = Math.max.apply(null, Object.keys(byCat).map(function (k) { return byCat[k]; }).concat([1]));

    $("#ov-meta").innerHTML = '<dl class="ov-kv">' +
      "<dt>合同编号</dt><dd>" + esc(m.contract_no) + "</dd>" +
      "<dt>合同日期</dt><dd>" + esc(m.contract_date) + "</dd>" +
      "<dt>我方身份</dt><dd>" + esc(m.our_role_cn) + "</dd>" +
      "<dt>交易对手</dt><dd>印尼买方 (buyer)</dd>" +
      "<dt>产品</dt><dd>" + esc(m.product_cn) + "<br><span style='color:#94a3b8'>" + esc(m.product) + "</span></dd>" +
      "<dt>HS 编码</dt><dd>" + esc(m.hs_code) + "</dd>" +
      "<dt>贸易术语</dt><dd>" + esc(m.trade_term) + "</dd>" +
      "<dt>合同金额</dt><dd>" + esc(m.amount) + "</dd>" +
      "<dt>数量</dt><dd>" + esc(m.quantity) + "</dd>" +
      "<dt>审阅日期</dt><dd>" + esc(m.review_date) + "</dd>" +
      "</dl>";

    // severity bars
    var total = DATA.issues.length || 1;
    $("#ov-sev").innerHTML = DATA.severities.map(function (s) {
      var n = bySev[s.key] || 0;
      var pct = Math.round(n / total * 100);
      return '<div class="bar-row"><span>' + esc(s.label) + "</span>" +
        '<div class="bar-track"><div class="bar-fill sev-' + s.key + '" style="width:' + pct + '%"></div></div>' +
        '<span class="bar-num">' + n + "</span></div>";
    }).join("");

    // category bars
    $("#ov-cat").innerHTML = DATA.categories.map(function (c) {
      var n = byCat[c.key] || 0;
      var pct = Math.round(n / maxCat * 100);
      return '<div class="bar-row"><span>' + esc(c.label) + "</span>" +
        '<div class="bar-track"><div class="bar-fill" style="width:' + pct + "%;background:" + c.color + '"></div></div>' +
        '<span class="bar-num">' + n + "</span></div>";
    }).join("");

    // summary table
    var rows = DATA.issues.map(function (i) {
      var st = statusOf(i.id);
      return "<tr>" +
        '<td class="clickable" data-goto="' + esc(i.id) + '">' + esc(i.id) + "</td>" +
        "<td>" + esc(i.clause_title || "") + "</td>" +
        "<td>" + esc(i.title) + "</td>" +
        '<td><span class="tag sev-' + esc(i.severity) + '">' + esc(sevMeta(i.severity).label) + "</span></td>" +
        "<td>" + esc(catMeta(i.category).label) + "</td>" +
        '<td><span class="tag ' + statusClass(st) + '">' + esc(st) + "</span></td>" +
        "</tr>";
    }).join("");

    $("#ov-table").innerHTML =
      "<thead><tr><th>编号</th><th>条款</th><th>问题</th><th>等级</th><th>主题</th><th>状态</th></tr></thead>" +
      "<tbody>" + rows + "</tbody>";

    $$("[data-goto]", $("#ov-table")).forEach(function (el) {
      el.addEventListener("click", function () { focusIssue(el.getAttribute("data-goto"), false); });
    });
  }

  function renderVisibility() {
    // dim contract blocks that have no risk in the current category
    var activeCat = state.category;
    if (activeCat === "__all__") {
      $$("[data-bid]").forEach(function (el) { el.style.opacity = ""; });
      return;
    }
    var keep = {};
    DATA.issues.forEach(function (i) {
      if (i.category !== activeCat) return;
      (i.anchors || []).forEach(function (a) {
        var el = document.querySelector('[data-bid="' + a.block + '"]');
        if (el) {
          var p = el.parentNode;
          keep[a.block] = true;
        }
      });
    });
    $$("[data-bid]").forEach(function (el) {
      el.style.opacity = keep[el.getAttribute("data-bid")] ? "1" : "0.38";
    });
  }

  /* ---------------- export ---------------- */
  function rowsForExport() {
    var rows = [["编号", "主题", "风险等级", "问题类型", "条款", "合同原文位置", "合同原文引用",
      "问题说明", "潜在商务后果", "需要确认事项", "建议措辞", "负责人", "处理状态", "备注"]];
    DATA.issues.forEach(function (i) {
      var e = editOf(i.id);
      var cat = catMeta(i.category);
      var sev = sevMeta(i.severity);
      var anchors = (i.anchors || []).map(function (a) { return a.clause || ""; }).join(" | ");
      var quotes = (i.anchors || []).map(function (a) { return "[" + (a.clause || "") + "] " + (a.quote || ""); }).join("\n");
      var confirms = (i.confirm || []).map(function (c, n) { return (n + 1) + ". " + c; }).join("\n");
      rows.push([
        i.id, cat.label, sev.label, issueTypeLabel(i.issue_type), i.clause_title || "",
        anchors, quotes, i.finding, i.consequence, confirms,
        i.suggested_wording || "", e.owner || "", statusOf(i.id), e.note || ""
      ]);
    });
    return rows;
  }

  function issueTypeLabel(key) {
    var map = { ambiguous: "表述不清", unilateral: "单方有利", conflict: "内部冲突", missing: "条款缺失",
      unbalanced: "权利义务失衡", unenforceable: "可能不可执行", commercial: "商业不合理" };
    return map[key] || key;
  }

  function download(filename, text, mime) {
    var blob = new Blob(["\ufeff" + text], { type: (mime || "text/plain") + ";charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
  }

  function exportCSV() {
    var rows = rowsForExport();
    var csv = rows.map(function (r) {
      return r.map(function (c) {
        var s = String(c == null ? "" : c).replace(/"/g, '""');
        return '"' + s + '"';
      }).join(",");
    }).join("\r\n");
    download("外贸合同审阅清单_" + DATA.meta.contract_no + ".csv", csv, "text/csv");
    toast("已导出 CSV（可用 Excel 打开）");
  }

  function exportJSON() {
    var payload = {
      meta: DATA.meta,
      exported_at: new Date().toISOString(),
      edits: edits,
      issues: DATA.issues.map(function (i) {
        return { id: i.id, category: i.category, severity: i.severity, status: statusOf(i.id),
          owner: editOf(i.id).owner, note: editOf(i.id).note };
      })
    };
    download("外贸合同审阅状态_" + DATA.meta.contract_no + ".json", JSON.stringify(payload, null, 2), "application/json");
    toast("已导出处理状态 JSON");
  }

  /* ---------------- views ---------------- */
  function switchView(v) {
    state.view = v;
    $("#view-split").style.display = v === "split" ? "" : "none";
    $("#view-overview").classList.toggle("show", v === "overview");
    $("#btn-split").classList.toggle("primary", v === "split");
    $("#btn-overview").classList.toggle("primary", v === "overview");
    if (v === "overview") renderOverview();
  }

  /* ---------------- init ---------------- */
  function init() {
    DATA.issues.forEach(function (i) { editOf(i.id); });

    decorateContract();
    renderChips();
    renderSevChips();
    renderStatusFilter();
    renderCards();

    $("#btn-split").addEventListener("click", function () { switchView("split"); });
    $("#btn-overview").addEventListener("click", function () { switchView("overview"); });
    $("#btn-export").addEventListener("click", exportCSV);
    $("#btn-export-json").addEventListener("click", exportJSON);
    $("#btn-print").addEventListener("click", function () { window.print(); });

    $("#statusfilter").addEventListener("change", function (e) {
      state.status = e.target.value;
      renderCards();
    });

    var q = $("#search");
    q.addEventListener("input", function (e) {
      state.query = e.target.value.trim();
      renderCards();
    });

    $("#btn-help").addEventListener("click", function () { $("#modal-mask").classList.add("show"); });
    $("#modal-close").addEventListener("click", function () { $("#modal-mask").classList.remove("show"); });
    $("#modal-mask").addEventListener("click", function (e) {
      if (e.target.id === "modal-mask") $("#modal-mask").classList.remove("show");
    });

    $$("[data-badge]").forEach(function (el) {
      el.addEventListener("click", function () { focusIssue(el.getAttribute("data-badge"), true); });
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") $("#modal-mask").classList.remove("show");
      if (e.key === "/" && document.activeElement !== q) {
        e.preventDefault();
        q.focus();
      }
    });

    switchView("split");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
