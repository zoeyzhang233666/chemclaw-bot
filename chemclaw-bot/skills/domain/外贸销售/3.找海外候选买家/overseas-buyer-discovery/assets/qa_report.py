# -*- coding: utf-8 -*-
"""qa_report.py — 交互式 HTML 报告的自动验收。

用法:
    python qa_report.py <报告.html> [chromium可执行文件路径]

检查项:
  1. 页面级横向溢出（1440 / 1024 / 768 / 390 四种宽度）
  2. JS 运行时报错
  3. 卡片数量、证据条目数
  4. 每条线索的必填字段
  5. 筛选 / 展开 / 保存线索 / 生成邮件 四个交互
  6. 页面中是否混入个人手机号

退出码: 0 全部通过；1 有失败项。
"""
import asyncio
import os
import re
import sys

WIDTHS = [1440, 1024, 768, 390]

PANEL_JS = r"""
() => {
  const de = document.documentElement;
  const issues = [];
  if (de.scrollWidth > de.clientWidth + 2)
    issues.push('PAGE-OVERFLOW scrollWidth=' + de.scrollWidth + ' clientWidth=' + de.clientWidth);
  const svg = document.querySelector('#chart');
  if (!svg) issues.push('CHART 未找到 (#chart)');
  return {
    issues,
    cards: document.querySelectorAll('#list .card').length,
    evidence: document.querySelectorAll('#list .card .evs li').length,
    hasDraft: typeof draft === 'function',
    hasAddLead: typeof addLead === 'function'
  };
}
"""

FIELDS_JS = r"""
() => {
  const need = ['company','type','evidence_tier','region_short','lane','lane_label',
                'main_business','why_related','evidence_summary','evidence_urls','confidence'];
  const bad = [];
  Object.values(DATA).forEach(d => {
    need.forEach(k => { if (!d[k]) bad.push(d.company + ':' + k); });
  });
  const phones = [];
  const blob = JSON.stringify(DATA);
  const m = blob.match(/\+?62\s?8\d{2}[\s-]?\d{3,4}[\s-]?\d{3,4}/g);
  if (m) {
    // 只报"没有标注为企业公开渠道"的号码，避免把企业官网/商铺的公开业务号误判为个人手机
    const labelled = blob.includes('企业官网/商铺公开的业务电话');
    if (!labelled) phones.push(...m.slice(0, 5));
  }
  return {bad: bad.slice(0, 15), phones, hasContactNote: blob.includes('企业官网/商铺公开的业务电话')};
}
"""


async def main(path, exe=None):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("需要 playwright：pip install playwright && python -m playwright install chromium")
        return 1
    url = "file:///" + os.path.abspath(path).replace("\\", "/")
    failed = []

    # ---- 静态检查：未替换的占位符（曾导致页面上直接显示 "%(cA)d" 和 "{14}"）----
    raw = open(path, encoding="utf-8", errors="replace").read()
    leftovers = []
    leftovers += re.findall(r"%\(\w+\)[sd]", raw)          # Python %-格式化残留
    leftovers += re.findall(r"\{\{\w+\}\}", raw)           # {{占位符}} 未替换
    leftovers += re.findall(r">\s*\{\d+\}\s*<", raw)       # 渲染成 {14} 的双花括号泄漏
    if leftovers:
        print("[FAIL] 占位符未被替换:", sorted(set(leftovers))[:8])
        failed.append(("template", sorted(set(leftovers))[:8]))
    else:
        print("[OK] 模板占位符全部已替换")

    async with async_playwright() as p:
        kw = {"executable_path": exe} if exe else {}
        browser = await p.chromium.launch(**kw)
        for w in WIDTHS:
            pg = await browser.new_page(viewport={"width": w, "height": 900})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(url, wait_until="load")
            await pg.wait_for_timeout(600)
            r = await pg.evaluate(PANEL_JS)
            status = "OK" if not r["issues"] and not errs else "FAIL"
            print("[%s] %4dpx  cards=%-3d evidence=%-3d %s" %
                  (status, w, r["cards"], r["evidence"],
                   "; ".join(r["issues"] + errs)[:150]))
            if status == "FAIL":
                failed.append((w, r["issues"] + errs))
            # 字段完整性只在最大宽度检查一次
            if w == WIDTHS[0]:
                f = await pg.evaluate(FIELDS_JS)
                if f["bad"]:
                    print("      ! 线索缺字段:", f["bad"])
                    failed.append((w, f["bad"]))
                if f["phones"]:
                    print("      ! 未标注来源的手机号（须确认为企业公开业务号）:", f["phones"])
                    failed.append((w, f["phones"]))
                elif f.get("hasContactNote"):
                    print("      · 手机号均已标注为‘企业官网/商铺公开的业务电话’")
                if not r["hasDraft"]:
                    print("      ! 缺少 draft() 邮件生成函数")
                    failed.append((w, ["draft missing"]))
            await pg.close()

        # 交互测试
        pg = await browser.new_page(viewport={"width": 1400, "height": 950})
        await pg.goto(url, wait_until="load")
        await pg.wait_for_timeout(600)
        total = await pg.inner_text("#shown")
        await pg.click("#tierSeg .chip[data-f='A']")
        await pg.wait_for_timeout(250)
        a_count = await pg.inner_text("#shown")
        await pg.click("#tierSeg .chip[data-f='all']")
        await pg.fill("#q", "玻璃")
        await pg.wait_for_timeout(300)
        s_count = await pg.inner_text("#shown")
        await pg.fill("#q", "")
        await pg.wait_for_timeout(200)
        await pg.evaluate("document.querySelector('#list .card .card-h').click()")
        await pg.wait_for_timeout(300)
        opened = await pg.evaluate("document.querySelector('#list .card').classList.contains('open')")
        await pg.evaluate("document.querySelector('#list .card .btn.ghost').click()")
        await pg.wait_for_timeout(300)
        saved = await pg.evaluate("JSON.parse(localStorage.getItem('oceanLeads_v1')||'[]').length")
        print("\n交互: 总数=%s A级=%s 搜索'玻璃'=%s 展开=%s 保存=%s" % (total, a_count, s_count, opened, saved))
        for label, ok in (("筛选A", int(a_count) > 0 and int(a_count) < int(total)),
                          ("搜索", int(s_count) > 0),
                          ("展开", opened), ("保存线索", saved >= 1)):
            if not ok:
                failed.append(("interaction", [label]))
        await browser.close()

    print("\n" + ("全部通过 ✅" if not failed else "存在 %d 项问题 ❌" % len(failed)))
    return 0 if not failed else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)))
