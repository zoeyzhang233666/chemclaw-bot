/* =====================================================================
   chem-import-dossier · assets/report.js
   纯原生 JS，无依赖。数据由 render_html.py 注入 window.DOSSIER。
   功能：侧栏定位 / 表格筛选排序 / 缺口勾选与进度 / 来源抽屉 /
        导出清单 / 保存本地进度 / 打印
   ===================================================================== */
(function () {
  "use strict";
  var D = window.DOSSIER || {};
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var LS_KEY = "dossier:" + (D.meta && D.meta.record_id || "x");

  /* ---------------- 顶部滚动进度 ---------------- */
  var sb = $(".scrollbar");
  function onScroll() {
    var h = document.documentElement;
    var p = h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight);
    if (sb) sb.style.width = (p * 100).toFixed(2) + "%";
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------------- 侧栏高亮 ---------------- */
  var links = $$(".side a[href^='#']");
  var secs = links.map(function (a) { return document.getElementById(a.getAttribute("href").slice(1)); }).filter(Boolean);
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) {
          a.classList.toggle("on", a.getAttribute("href") === "#" + e.target.id);
        });
      });
    }, { rootMargin: "-64px 0px -72% 0px", threshold: 0 });
    secs.forEach(function (s) { io.observe(s); });
  }

  /* ---------------- 通用筛选 + 排序 ---------------- */
  function initTable(tw) {
    var table = $("table.t", tw);
    if (!table) return;
    var tbody = $("tbody", table);
    var chips = $$(".fchip", tw);
    var input = $(".search input", tw);
    var state = { filter: "all", q: "" };

    function rows() { return $$("tr", tbody); }
    function apply() {
      var n = 0;
      rows().forEach(function (tr) {
        var okF = state.filter === "all" || (tr.dataset.rowkey || "").split(" ").indexOf(state.filter) >= 0;
        var okQ = !state.q || (tr.dataset.search || "").indexOf(state.q) >= 0;
        var show = okF && okQ;
        tr.style.display = show ? "" : "none";
        if (show) n++;
      });
      rows().forEach(function (tr) {
        if (tr.dataset.search === undefined) tr.dataset.search = tr.textContent.toLowerCase().replace(/\s+/g, " ");
      });
      var cnt = $("#count-" + tw.dataset.tw);
      if (cnt) cnt.textContent = n + " / " + rows().length;
      tw.dispatchEvent(new CustomEvent("rows", { detail: n }));
    }
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        chips.forEach(function (x) { x.classList.remove("on"); });
        c.classList.add("on");
        state.filter = c.dataset.filter || "all";
        apply();
      });
    });
    if (input) {
      input.addEventListener("input", function () {
        state.q = input.value.trim().toLowerCase();
        apply();
      });
    }
    // 排序
    $$("th.s", table).forEach(function (th, i) {
      th.addEventListener("click", function () {
        var asc = !th.classList.contains("asc");
        $$("th.s", table).forEach(function (x) { x.classList.remove("asc", "desc"); });
        th.classList.add(asc ? "asc" : "desc");
        var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
        rows().sort(function (a, b) {
          var av = (a.children[idx] || {}).textContent || "";
          var bv = (b.children[idx] || {}).textContent || "";
          // 数字优先
          var an = parseFloat(av.replace(/[^\d.\-]/g, "")), bn = parseFloat(bv.replace(/[^\d.\-]/g, ""));
          var cmp = (!isNaN(an) && !isNaN(bn) && /^\s*[\d.,%+-]+/.test(av)) ? an - bn : av.localeCompare(bv, "zh");
          return asc ? cmp : -cmp;
        }).forEach(function (r) { tbody.appendChild(r); });
      });
    });
    apply();
  }
  $$("[data-tw]").forEach(initTable);

  /* ---------------- 缺口勾选 ---------------- */
  var checks = $$("input[type=checkbox][data-gap]");
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch (e) { saved = {}; }

  function updGaps() {
    var done = 0, total = 0, p0done = 0, p0total = 0;
    checks.forEach(function (c) {
      total++;
      if (c.checked) done++;
      if (c.dataset.pri === "P0") { p0total++; if (c.checked) p0done++; }
      c.closest(".gap").classList.toggle("done", c.checked);
    });
    var pc = total ? Math.round(done / total * 100) : 0;
    var el = $("#gappct"); if (el) el.textContent = pc + "%";
    var bar = $("#gapbar"); if (bar) { bar.style.width = pc + "%"; }
    var dn = $("#gapdone"); if (dn) dn.textContent = done + "/" + total;
    var p0 = $("#p0done"); if (p0) {
      p0.textContent = p0done + "/" + p0total;
      p0.className = p0done === p0total ? "kv" : "kv";
    }
    try {
      var o = {}; checks.forEach(function (c) { o[c.dataset.gap] = c.checked; });
      localStorage.setItem(LS_KEY, JSON.stringify(o));
    } catch (e) { /* 隐私模式忽略 */ }
  }
  checks.forEach(function (c) {
    if (saved[c.dataset.gap]) c.checked = true;
    c.addEventListener("change", updGaps);
  });
  if (checks.length) updGaps();

  /* 每个分区的"标记完成" */
  $$("[data-markall]").forEach(function (b) {
    b.addEventListener("click", function () {
      var box = document.getElementById(b.dataset.markall);
      var all = $$("input[type=checkbox]", box);
      var to = !all.every(function (c) { return c.checked; });
      all.forEach(function (c) { c.checked = to; });
      updGaps();
      toast(to ? "已标记为已完成" : "已取消完成标记");
    });
  });

  /* ---------------- 来源抽屉 ---------------- */
  var dg = $("#drawer"), bg = $("#drawer-bg");
  var SRC = {};
  (D.sources || []).forEach(function (s) { SRC[s.id] = s; });

  function openSrc(id) {
    var s = SRC[id];
    if (!s) return;
    var tier = s.tier || "C";
    var html = "";
    html += '<div class="kv">';
    html += '<div class="k">来源编号</div><div><b class="mono">' + esc(s.id) + '</b> <span class="tier ' + tier + '">' + tier + '级</span></div>';
    html += '<div class="k">文件类型</div><div>' + esc(s.kind || "") + '</div>';
    html += '<div class="k">发布机关</div><div>' + esc(s.publisher || "") + '</div>';
    html += '<div class="k">日期</div><div>' + esc(s.date || "") + '</div>';
    html += '<div class="k">效力状态</div><div>' + badgeEff(s.effective) + '</div>';
    html += '<div class="k">查询日期</div><div class="mono">' + esc(s.accessed || "") + '</div>';
    html += '</div>';
    html += '<h4>标题</h4><div>' + esc(s.title || "") + '</div>';
    html += '<h4>原文链接</h4><div><a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.url) + '</a></div>';
    html += '<h4>支撑了哪条结论</h4><div>' + esc(s.supports || "—") + '</div>';
    if (tier === "C") {
      html += '<h4>使用提示</h4><div style="color:#8a5a2a">C 级来源为行业数据库/商业平台，仅作交叉参考；不可作为唯一依据。' +
        (s.effective === "未核实" ? " 本来源标注为" + esc(s.effective) + "，须由官方渠道复核。" : "") + '</div>';
    }
    if (s.effective === "部分替代") {
      html += '<h4>时效提示</h4><div style="color:#a3311f">该文件部分条款已被更新法规覆盖，引用时须以新法为准。</div>';
    }
    $("#drawer-title").textContent = s.id + " · " + (s.kind || "来源");
    $("#drawer-body").innerHTML = html;
    dg.classList.add("on"); bg.classList.add("on");
    dg.setAttribute("aria-hidden", "false");
  }
  function closeDrawer() {
    dg.classList.remove("on"); bg.classList.remove("on");
    dg.setAttribute("aria-hidden", "true");
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-src]");
    if (t) { e.preventDefault(); openSrc(t.dataset.src); }
  });
  if (bg) bg.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrawer(); });
  if ($("#drawer-close")) $("#drawer-close").addEventListener("click", closeDrawer);

  /* ---------------- Toast ---------------- */
  var toastEl = $("#toast");
  var toastT;
  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("on");
    clearTimeout(toastT);
    toastT = setTimeout(function () { toastEl.classList.remove("on"); }, 2200);
  }
  window.__toast = toast;

  /* ---------------- 导出英文索取清单 ---------------- */
  function buildRequestText() {
    var R = D.supplier_request_en || {};
    var L = [];
    L.push(R.title || "Documentation Request");
    L.push("");
    L.push(R.intro || "");
    L.push("");
    L.push("----------------------------------------------------------------");
    (R.items || []).forEach(function (it) {
      L.push(it.no + ". " + it.doc);
      L.push("   Detail : " + it.detail);
      L.push("   Timing : " + it.due);
      L.push("");
    });
    L.push("----------------------------------------------------------------");
    L.push(R.closing || "");
    L.push("");
    L.push("[Reference] Dossier " + (D.meta && D.meta.record_id || "") + " / as of " + (D.as_of || ""));
    L.push("[Sources in this dossier]");
    (D.sources || []).forEach(function (s) { L.push("  " + s.id + " | " + s.title + " | " + s.publisher + " | " + (s.effective || "")); });
    return L.join("\n");
  }
  function download(name, text, mime) {
    var blob = new Blob([text], { type: (mime || "text/plain") + ";charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 400);
  }
  window.__exportRequest = function () {
    var n = (D.meta && D.meta.record_id || "dossier") + "_Supplier_Document_Request.txt";
    download(n, buildRequestText());
    toast("已导出英文索取清单");
  };
  window.__copyRequest = function () {
    var t = buildRequestText();
    var done = function () { toast("英文索取清单已复制到剪贴板"); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t).then(done, function () { fallbackCopy(t, done); });
    } else { fallbackCopy(t, done); }
  };
  function fallbackCopy(t, cb) {
    var ta = document.createElement("textarea");
    ta.value = t; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); cb(); } catch (e) { toast("复制失败，请手动选择文本"); }
    ta.remove();
  }
  window.__print = function () { window.print(); };
  window.__resetProgress = function () {
    try { localStorage.removeItem(LS_KEY); } catch (e) {}
    checks.forEach(function (c) { c.checked = false; });
    updGaps();
    toast("已清空本地完成标记");
  };

  /* ---------------- 小工具 ---------------- */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function badgeEff(v) {
    var map = { "现行有效": "ok", "部分替代": "warn", "已废止": "bad", "未核实": "gray", "供交叉核对": "info", "行业参考": "gray" };
    return '<span class="badge ' + (map[v] || "gray") + '">' + esc(v || "未标注") + '</span>';
  }

  /* 关键指标 hover 提示 */
  $$("[data-tip]").forEach(function (el) {
    el.addEventListener("mouseenter", function () { el.title = el.dataset.tip; });
  });
})();
