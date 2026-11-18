# -*- coding: utf-8 -*-
"""无图像渲染检查：用几何测量代替肉眼。
检查：横向溢出、文字被裁、空区块、状态色一致性、窄列、交互（展开/筛选/搜索/抽屉）。
用法: python qa_html.py report.html [--json out.json]
退出码：0 = PASS，1 = 有硬性 issue。需要 playwright（可选依赖）。
"""
import sys, os, json, io

if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    print("[skip] 未安装 playwright，跳过渲染 QA：pip install playwright && playwright install chromium")
    sys.exit(0)

src = sys.argv[1]
outj = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None

MEASURE_JS = r"""
() => {
  const issues = [];
  const vw = window.innerWidth;
  const docW = document.documentElement.clientWidth;
  if (document.documentElement.scrollWidth > docW + 2)
    issues.push({t:'hscroll', msg:`页面横向溢出 ${document.documentElement.scrollWidth} > ${docW}`});

  const SCROLLER = '.drawer, .matrix-wrap, .msg-body, .nav-links, [style*="overflow-x:auto"], [style*="overflow-x: auto"]';
  const bad = [];
  document.querySelectorAll('body *').forEach(el=>{
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    const cs = getComputedStyle(el);
    if (cs.position === 'fixed' || cs.display === 'none' || cs.visibility === 'hidden') return;
    if (cs.transform && cs.transform !== 'none') return;
    // 若任一祖先允许横向滚动，则该元素是“容器内滚动内容”，不算页面溢出
    let p = el.parentElement, scrollable = false;
    while (p && p !== document.body) {
      const pc = getComputedStyle(p);
      if ((pc.overflowX === 'auto' || pc.overflowX === 'scroll' || pc.overflow === 'auto' || pc.overflow === 'scroll') && p.scrollWidth > p.clientWidth + 2) { scrollable = true; break; }
      p = p.parentElement;
    }
    if (scrollable) return;
    if (el.closest(SCROLLER)) return;
    if (r.left < -3 || r.right > vw + 3)
      bad.push({tag: el.tagName + '.' + String(el.className||'').slice(0,36), l: Math.round(r.left), r: Math.round(r.right)});
  });
  if (bad.length) issues.push({t:'overflow-x', msg:`${bad.length} 个元素越出视口`, sample: bad.slice(0,6)});

  const clipped = [];
  document.querySelectorAll('.t, .q, .fact, .zh, .en, .nm, .v, .txt, .finding, .impact, .act, .cell').forEach(el=>{
    const cs = getComputedStyle(el);
    if (cs.overflow === 'hidden' && el.scrollHeight > el.clientHeight + 3 && el.clientHeight > 0)
      clipped.push({cls: String(el.className||'').slice(0,24), text: (el.textContent||'').trim().slice(0,32)});
  });
  if (clipped.length) issues.push({t:'clipped-text', msg:`${clipped.length} 处文字被裁`, sample: clipped.slice(0,6)});

  [...document.querySelectorAll('section[id]')].forEach(s=>{
    if (s.getBoundingClientRect().height < 60) issues.push({t:'empty-section', msg:`${s.id} 高度异常`});
  });

  const counts = {
    chk: document.querySelectorAll('.chk').length,
    srcPill: document.querySelectorAll('.src-pill').length,
    matrixRows: document.querySelectorAll('table.matrix tbody tr').length,
    req: document.querySelectorAll('.req-item').length,
    msgTab: document.querySelectorAll('.msg-tab').length,
    tl: document.querySelectorAll('.tl-item').length,
    donut: document.querySelectorAll('.donut svg circle').length,
    score: document.querySelectorAll('.score-cell').length,
    concl: document.querySelectorAll('.concl-col li').length
  };
  issues.push({t:'content', msg:'关键元素计数', data: counts});

  let chipBad = 0;
  document.querySelectorAll('.chk').forEach(c=>{
    const st = [...c.classList].find(x=>x.startsWith('is-'));
    if (!st) return;
    const cs = c.querySelectorAll('.chk-head .chip');
    const last = cs[cs.length-1];
    if (last && !last.classList.contains(st.slice(3))) chipBad++;
  });
  if (chipBad) issues.push({t:'state-consistency', msg:`状态与 chip 不一致 ${chipBad} 处`});

  const narrow = [];
  document.querySelectorAll('table.tbl th, table.matrix th').forEach(th=>{
    const w = th.getBoundingClientRect().width;
    if (w > 0 && w < 36) narrow.push({w: Math.round(w), text: th.textContent.trim().slice(0,14)});
  });
  if (narrow.length) issues.push({t:'narrow-col', msg:`${narrow.length} 个表头过窄`, sample: narrow.slice(0,5)});
  return {issues};
}
"""

INTERACT_JS = r"""
() => {
  const out = {};
  const el = document.querySelector('.chk');
  const id = el.dataset.id;
  const wasOpen = el.classList.contains('open');
  el.querySelector('.chk-head').click();
  out.toggle_ok = document.querySelector('.chk[data-id="' + id + '"]').classList.contains('open') !== wasOpen;

  const total = document.querySelectorAll('.chk').length;
  const btn = document.querySelectorAll('.filters button')[0];
  btn.click();
  out.after_filter = document.querySelectorAll('.chk').length;
  btn.click();
  out.after_restore = document.querySelectorAll('.chk').length;
  out.restore_ok = out.after_restore === total;

  const inp = document.getElementById('q');
  inp.value = 'NIB';
  inp.dispatchEvent(new Event('input'));
  return new Promise(res => setTimeout(() => {
    out.search = document.querySelectorAll('.chk').length;
    inp.value = '';
    inp.dispatchEvent(new Event('input'));
    setTimeout(() => {
      out.after_clear = document.querySelectorAll('.chk').length;
      const pill = document.querySelector('.src-pill');
      if (pill) { pill.click(); out.drawer = document.querySelector('#drawer').classList.contains('on'); }
      res(out);
    }, 240);
  }, 280));
}
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    res = {}
    for w, h, label in ((1440, 1000, "desktop"), (820, 1000, "tablet"), (390, 844, "mobile")):
        pg = b.new_page(viewport={"width": w, "height": h})
        errs = []
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        pg.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        pg.goto("file:///" + os.path.abspath(src).replace("\\", "/"))
        pg.wait_for_timeout(750)
        issues = pg.evaluate(MEASURE_JS)["issues"]
        inter = pg.evaluate(INTERACT_JS)
        need = ("toggle_ok", "restore_ok", "search", "after_clear", "drawer")
        if not all(inter.get(k) for k in need):
            issues.append({"t": "interaction-fail", "msg": "交互异常", "data": inter})
        else:
            issues.append({"t": "interaction", "msg": "交互测试通过", "data": inter})
        issues.append({"t": "console", "msg": "console errors", "data": errs})
        res[label] = {"issues": issues, "width": w}
        pg.close()
    b.close()

FAIL = {"hscroll", "overflow-x", "clipped-text", "empty-section", "state-consistency",
        "narrow-col", "interaction-fail"}
ok = True
for label, blob in res.items():
    print(f"\n===== {label} ({blob['width']}px) =====")
    for it in blob["issues"]:
        t = it["t"]
        hard = t in FAIL or (t == "console" and it["data"])
        if hard:
            ok = False
        print(f"{'X ' if hard else '  '}[{t}] {it['msg']}")
        if "sample" in it:
            print("     ", it["sample"])
        if "data" in it:
            print("     ", json.dumps(it["data"], ensure_ascii=False)[:500])

if outj:
    with open(outj, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

print("\nRESULT:", "PASS" if ok else "ISSUES")
sys.exit(0 if ok else 1)
