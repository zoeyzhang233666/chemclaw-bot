/* ===================================================================
   chem-supplier-qualification · assets/report.js
   交互：证照筛选/搜索、详情抽屉、索证清单勾选、草稿复制、
         核验记录保存（localStorage + 下载）、打印。
   无外部依赖；数据由 window.QC_DATA 注入。
   =================================================================== */
(function () {
  'use strict';
  var D = window.QC_DATA || {};
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  function toast(msg) {
    var t = $('#toast'); if (!t) return;
    t.textContent = msg; t.classList.add('on');
    clearTimeout(toast._h); toast._h = setTimeout(function () { t.classList.remove('on'); }, 2200);
  }

  /* ---------------- 侧栏滚动高亮 ---------------- */
  var links = $$('#side a[href^="#"]');
  var targets = links.map(function (a) { return $(a.getAttribute('href')); }).filter(Boolean);
  function spy() {
    var y = window.scrollY + 90, cur = null;
    targets.forEach(function (t) { if (t.offsetTop <= y) cur = t.id; });
    links.forEach(function (a) { a.classList.toggle('on', a.getAttribute('href') === '#' + cur); });
  }
  window.addEventListener('scroll', spy, { passive: true }); spy();

  /* ---------------- 证照筛选 ---------------- */
  var state = { st: 'all', cov: 'all', q: '' };
  var cards = $$('.cert');

  function applyFilter() {
    var n = 0;
    cards.forEach(function (c) {
      var okSt = state.st === 'all' || c.dataset.state === state.st;
      var okCov = state.cov === 'all' || (c.dataset.cov || '') === state.cov;
      var okQ = !state.q || (c.dataset.q || '').indexOf(state.q) >= 0;
      var show = okSt && okCov && okQ;
      c.style.display = show ? '' : 'none';
      if (show) n++;
    });
    var cnt = $('#certCount'); if (cnt) cnt.textContent = n;
    var emp = $('#certEmpty'); if (emp) emp.style.display = n ? 'none' : '';
    $$('.fchip').forEach(function (b) {
      b.classList.toggle('on',
        (b.dataset.f === 'st' && b.dataset.v === state.st) ||
        (b.dataset.f === 'cov' && b.dataset.v === state.cov));
    });
  }
  $$('.fchip').forEach(function (b) {
    b.addEventListener('click', function () {
      var f = b.dataset.f, v = b.dataset.v;
      if (f === 'st') state.st = (state.st === v && v !== 'all') ? 'all' : v;
      if (f === 'cov') state.cov = (state.cov === v && v !== 'all') ? 'all' : v;
      applyFilter();
    });
  });
  var si = $('#certSearch');
  if (si) si.addEventListener('input', function () { state.q = si.value.trim().toLowerCase(); applyFilter(); });

  /* ---------------- 抽屉 ---------------- */
  var drawer = $('#drawer'), scrim = $('#scrim'), dkBody = $('#dkBody');
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function openCert(id) {
    var c = (D.certs || []).filter(function (x) { return x.id === id; })[0];
    if (!c) return;
    $('#dkTitle').textContent = c.name || '证照详情';
    $('#dkSub').textContent = (c.no ? '编号 ' + c.no + ' · ' : '') + (c.issuer || '') + (c.evidence_id ? ' · 证据 ' + c.evidence_id : '');
    var h = '';
    if (c.scan) {
      h += '<div class="scan"><a href="' + esc(c.scan) + '" target="_blank" rel="noopener"><img src="' + esc(c.scan) + '" alt="证照扫描件"></a>' +
           '<div class="cap">' + esc(c.scan_caption || '扫描件（点击查看原图）') + '</div></div>';
    } else {
      h += '<div class="note">本证照未取得扫描件/原件影像，状态与字段以公开来源与说明为准。</div>';
    }
    var rows = [
      ['证照类型', c.type], ['证书编号', c.no], ['发证机关', c.issuer],
      ['发证日期', c.valid_from || c.issue_date], ['有效期至', c.valid_to || '—'],
      ['核验状态', (c.state_label || '') + (c.expiry_label ? '｜' + c.expiry_label : '')],
      ['应否具备', c.need_label], ['覆盖本采购', c.cover_label],
      ['字段来源', c.field_source], ['公开状态', c.public_state],
      ['公开来源', c.evidence_id ? ('证据 ' + c.evidence_id) : '—']
    ];
    h += '<table class="t"><tbody>' + rows.map(function (r) {
      return '<tr><td class="k">' + esc(r[0]) + '</td><td>' + esc(r[1] == null || r[1] === '' ? '—' : r[1]) + '</td></tr>';
    }).join('') + '</tbody></table>';
    if (c.scope) h += '<h4 style="margin:16px 0 4px;font-size:13px;color:var(--deep)">许可/核准范围（证载）</h4><div class="note">' +
      esc(c.scope).replace(/\n/g, '<br>') + '</div>';
    if (c.coverage) h += '<h4 style="margin:16px 0 4px;font-size:13px;color:var(--deep)">范围覆盖比对</h4><div class="note">' +
      esc(c.coverage).replace(/\n/g, '<br>') + '</div>';
    if (c.discrepancies && c.discrepancies.length) {
      h += '<h4 style="margin:16px 0 4px;font-size:13px;color:var(--bad)">已发现的信息不一致 / 疑点</h4><ul style="margin:0;padding-left:18px;font-size:12.6px">' +
        c.discrepancies.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul>';
    }
    if (c.note) h += '<h4 style="margin:16px 0 4px;font-size:13px;color:var(--deep)">核验说明与缺口</h4><div class="note">' +
      esc(c.note).replace(/\n/g, '<br>') + '</div>';
    if (c.crosscheck && c.crosscheck.length) {
      h += '<h4 style="margin:16px 0 4px;font-size:13px;color:var(--deep)">交叉核验记录</h4><div class="note">' +
        c.crosscheck.map(function (x) { return '· ' + esc(x); }).join('<br>') + '</div>';
    }
    if (c.url) h += '<p style="margin-top:14px"><a href="' + esc(c.url) + '" target="_blank" rel="noopener">打开公开来源 ↗</a></p>';
    dkBody.innerHTML = h;
    drawer.classList.add('open'); scrim.classList.add('on'); drawer.setAttribute('aria-hidden', 'false');
  }
  function closeDrawer() { drawer.classList.remove('open'); scrim.classList.remove('on'); drawer.setAttribute('aria-hidden', 'true'); }
  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-cert],[data-act]') : null;
    if (!t) return;
    if (t.dataset.cert) { e.preventDefault(); openCert(t.dataset.cert); return; }
    var act = t.dataset.act;
    if (act === 'close-drawer') closeDrawer();
    if (act === 'print') window.print();
    if (act === 'save') saveRecord();
    if (act === 'copy') {
      var sel = t.dataset.copy; var el = $(sel);
      if (!el) return;
      var txt = el.innerText;
      if (navigator.clipboard) navigator.clipboard.writeText(txt).then(function () { toast('已复制到剪贴板'); },
        function () { toast('复制失败，请手动选择文本'); });
      else toast('当前环境不支持剪贴板');
    }
  });
  if (scrim) scrim.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDrawer(); });

  /* ---------------- 索证清单进度 ---------------- */
  var KEY = 'qc-cl-' + ((D.meta || {}).record_id || 'default');
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (err) { saved = {}; }
  var boxes = $$('.cl input[type=checkbox]');
  function syncProg() {
    var done = boxes.filter(function (b) { return b.checked; }).length;
    var bar = $('#clProg'); if (bar) bar.style.width = (boxes.length ? done * 100 / boxes.length : 0) + '%';
    var lab = $('#clProgTxt'); if (lab) lab.textContent = done + ' / ' + boxes.length + ' 项';
    boxes.forEach(function (b) {
      var li = b.closest('li'); if (li) li.classList.toggle('done', b.checked);
      saved[b.dataset.k] = b.checked;
    });
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (err) { }
  }
  boxes.forEach(function (b) { if (saved[b.dataset.k]) b.checked = true; b.addEventListener('change', syncProg); });
  if (boxes.length) syncProg();

  /* ---------------- 保存核验记录 ---------------- */
  function saveRecord() {
    var rec = {
      record_id: (D.meta || {}).record_id, saved_at: new Date().toISOString(),
      as_of: (D.meta || {}).as_of, subject: (D.subject || {}).name,
      certs: (D.certs || []).map(function (c) { return { id: c.id, name: c.name, no: c.no, state: c.state, valid_to: c.valid_to }; }),
      checklist: saved
    };
    try { localStorage.setItem('qc-record-' + rec.record_id, JSON.stringify(rec)); } catch (err) { }
    var blob = new Blob([JSON.stringify(rec, null, 2)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '核验记录_' + (rec.record_id || 'record') + '_' + rec.saved_at.slice(0, 10) + '.json';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1500);
    toast('核验记录已保存（浏览器本地 + JSON 下载）');
  }
})();
