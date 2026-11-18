/* ================================================================== app.js
 * 通用化工品供应格局报告 · 交互脚本（产品无关）
 * 所有产品差异来自 DATA（由 build_all.py 注入），本文件不出现任何产品名。
 * 功能：标签页、企业抽屉、项目抽屉、企业表筛选排序。
 * ================================================================== */
(function () {
  "use strict";
  const DATA = window.DATA || {};
  const META = DATA.meta || {};
  const PRODUCT = META.product || {};
  const YEAR = (META.scope && META.scope.base_year) || "";
  const MISSING = "数据缺口";

  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const nz = (v) => (v == null ? 0 : Number(String(v).replace(/[^\d.\-]/g, "")) || 0);

  /* ---------------------------------------------------------------- 提示条 */
  let toastTimer = null;
  function toast(msg) {
    const t = $("#toast");
    if (!t) return;
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
  }

  /* ---------------------------------------------------------------- 标签页 */
  function activateTab(id) {
    $$(".tab-btn").forEach((b) => {
      const on = b.dataset.tab === id;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    $$(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + id));
    if (history.replaceState) history.replaceState(null, "", "#tab-" + id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  $$(".tab-btn").forEach((b) => b.addEventListener("click", () => activateTab(b.dataset.tab)));
  if (location.hash && location.hash.indexOf("#tab-") === 0) {
    const id = location.hash.slice(5);
    if ($("#tab-" + id)) activateTab(id);
  }

  /* ---------------------------------------------------------------- 抽屉 */
  const overlay = $("#drawerOverlay");
  const drawer = $("#drawer");
  function openDrawer(kind, id) {
    if (!drawer) return;
    const wrap = kind === "project" ? $("#drawerPrj") : $("#drawerCo");
    if (!wrap) return;
    if ($("#drawerCo")) $("#drawerCo").hidden = kind === "project";
    if ($("#drawerPrj")) $("#drawerPrj").hidden = kind !== "project";
    const attr = kind === "project" ? "project" : "company";
    let found = false;
    $$(".drawer-card", wrap).forEach((c) => {
      const hit = c.dataset[attr] === String(id);
      c.style.display = hit ? "" : "none";
      if (hit) found = true;
    });
    const eyebrow = $("#drawerEyebrow");
    const title = $("#drawerTitle");
    const sub = $("#drawerSub");
    if (kind === "project") {
      const p = (DATA.projects || []).find((x) => String(x.id) === String(id));
      if (eyebrow) eyebrow.textContent = "PROJECT SUPPLY CHANGE";
      if (title) title.textContent = p ? p.name : "项目";
      if (sub) sub.textContent = p ? [p.company_id, p.province, p.date].filter(Boolean).join(" · ") : "";
    } else {
      const c = (DATA.companies || []).find((x) => String(x.id) === String(id));
      if (eyebrow) eyebrow.textContent = "COMPANY DUE DILIGENCE";
      if (title) title.textContent = c ? c.name : "企业";
      if (sub) sub.textContent = c
        ? [(c.code || "未上市/未披露"), (c.provinces || []).join("、")].filter(Boolean).join(" · ") : "";
    }
    if (!found) toast("该条目缺少明细数据");
    drawer.classList.add("open");
    if (overlay) overlay.classList.add("show");
    drawer.setAttribute("aria-hidden", "false");
    drawer.scrollTop = 0;
  }
  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove("open");
    if (overlay) overlay.classList.remove("show");
    drawer.setAttribute("aria-hidden", "true");
  }
  const closeBtn = $("#drawerClose");
  if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
  if (overlay) overlay.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

  function bindCards() {
    $$("[data-company]").forEach((el) => {
      if (el.dataset.bound) return;
      el.dataset.bound = "1";
      const go = (e) => {
        if (e.type === "keydown" && e.key !== "Enter" && e.key !== " ") return;
        if (e.type === "keydown") e.preventDefault();
        openDrawer("company", el.dataset.company);
      };
      el.addEventListener("click", go);
      el.addEventListener("keydown", go);
    });
    $$("[data-project]").forEach((el) => {
      if (el.dataset.bound) return;
      el.dataset.bound = "1";
      const go = (e) => {
        if (e.type === "keydown" && e.key !== "Enter" && e.key !== " ") return;
        if (e.type === "keydown") e.preventDefault();
        openDrawer("project", el.dataset.project);
      };
      el.addEventListener("click", go);
      el.addEventListener("keydown", go);
    });
  }
  bindCards();

  /* ---------------------------------------------------------------- 企业表 */
  function sortRows(mode) {
    const tbody = $("#companyTable tbody");
    if (!tbody) return;
    const rows = $$("tr[data-company]", tbody);
    const key = (tr) => {
      const tds = tr.children;
      if (mode === "name") return tds[0].textContent.trim();
      if (mode === "share") return -nz(tds[6] ? tds[6].textContent : 0);
      return -nz(tds[4] ? tds[4].textContent : 0);
    };
    rows.sort((a, b) => {
      const ka = key(a), kb = key(b);
      return (typeof ka === "string") ? ka.localeCompare(kb, "zh-CN") : ka - kb;
    });
    rows.forEach((r) => tbody.appendChild(r));
  }
  const search = $("#coSearch");
  const sortSel = $("#coSort");
  function filterRows() {
    const q = ((search && search.value) || "").trim().toLowerCase();
    const tbody = $("#companyTable tbody");
    if (!tbody) return;
    let shown = 0;
    $$("tr[data-company]", tbody).forEach((tr) => {
      const hit = !q || tr.textContent.toLowerCase().indexOf(q) >= 0;
      tr.style.display = hit ? "" : "none";
      if (hit) shown += 1;
    });
    const cnt = $("#coCount");
    if (cnt) cnt.textContent = "显示 " + shown + " / " + (DATA.companies || []).length + " 家";
  }
  if (search) search.addEventListener("input", filterRows);
  if (sortSel) sortSel.addEventListener("change", () => { sortRows(sortSel.value); filterRows(); });
  filterRows();

  document.documentElement.classList.add("js-ready");
  console.log("[chem-supply-map] ready ·", (PRODUCT.short || PRODUCT.name || ""), YEAR,
    "· companies", (DATA.companies || []).length, "· projects", (DATA.projects || []).length);
})();
