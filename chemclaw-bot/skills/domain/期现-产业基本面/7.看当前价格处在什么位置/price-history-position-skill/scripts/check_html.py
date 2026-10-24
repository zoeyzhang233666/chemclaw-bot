# -*- coding: utf-8 -*-
"""HTML 无人值守验收：JS 报错、KPI、三图真出像素、交互、CSV 导出、三档宽度横向溢出。

用法：python scripts/check_html.py "out/xxx.html"
退出码 0 = 全通过。
"""
import json
import os
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "out/report.html"
SHOTS = os.path.join(os.path.dirname(os.path.abspath(OUT)) or ".", "shots")
os.makedirs(SHOTS, exist_ok=True)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("缺少 playwright，跳过 HTML 验收（pip install playwright && playwright install chromium）")
    sys.exit(0)

fails = []
logs = []


def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        pg.goto("file:///" + os.path.abspath(OUT).replace("\\", "/"))
        pg.wait_for_timeout(2600)

        if errs:
            fails.append("JS 报错: %s" % errs[:5])

        # KPI 卡
        n_kpi = pg.locator(".kpi").count()
        logs.append("KPI 卡 = %d" % n_kpi)
        if n_kpi < 4:
            fails.append("KPI 卡不足 4 个")

        # 各图是否画出像素
        for cid in ("priceChart", "seasonChart", "seasonIdxChart"):
            cnt = pg.evaluate("""(id)=>{const d=document.getElementById(id);
                if(!d) return -1; const c=d.querySelector('canvas'); if(!c) return -2;
                const x=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
                let n=0; for(let i=3;i<x.length;i+=4) if(x[i]) n++;
                return n;}""", cid)
            logs.append("%s 非透明像素 = %s" % (cid, cnt))
            if not isinstance(cnt, int) or cnt < 3000:
                fails.append("%s 未画出（像素 %s）" % (cid, cnt))

        # 表格行数
        rows = pg.locator("table tbody tr").count()
        logs.append("表格总行 = %d" % rows)
        if rows < 20:
            fails.append("表格内容过少")

        # 首屏关键文案
        txt = pg.inner_text("body")
        for kw in ("经验分位", "口径变更", "数据缺口", "元/吨", "华东"):
            if kw not in txt:
                fails.append("缺少关键文案：%s" % kw)

        pg.screenshot(path=os.path.join(SHOTS, "full.png"), full_page=True)
        pg.screenshot(path=os.path.join(SHOTS, "top.png"))

        # 交互 1：切 3 年
        pg.click("#winSeg button[data-w='1095']")
        pg.wait_for_timeout(700)
        pg.screenshot(path=os.path.join(SHOTS, "win3y.png"))

        # 交互 2：三者对比
        pg.click("#serSeg button[data-s='ALL']")
        pg.wait_for_timeout(900)
        layers = pg.evaluate("()=>{const c=window.__CH__.price; return c? Object.keys(c.getOption().series).length : -1;}")
        logs.append("ALL 模式 series 数 = %s" % layers)
        if not isinstance(layers, int) or layers < 2:
            fails.append("三者对比未生效")
        pg.screenshot(path=os.path.join(SHOTS, "compare.png"))

        # 交互 3：分位带 + 异常点
        pg.click("#serSeg button[data-s='S1']")
        pg.click("#btnBand")
        pg.click("#btnAnom")
        pg.wait_for_timeout(800)
        pg.screenshot(path=os.path.join(SHOTS, "band_anom.png"))

        # 交互 4：CSV 导出
        try:
            with pg.expect_download(timeout=6000) as dl:
                pg.click("#btnCsv")
            path = dl.value.path()
            sz = os.path.getsize(path) if path else 0
            logs.append("CSV 导出字节 = %d" % sz)
            if sz < 5000:
                fails.append("CSV 导出内容过小")
        except Exception as e:
            fails.append("CSV 导出失败: %s" % type(e).__name__)

        # 横向溢出三档（每档都让图表 resize 完成后再量，否则 ECharts 的旧尺寸会把页面撑宽）
        for w in (1600, 1280, 420):
            pg.set_viewport_size({"width": w, "height": 900})
            pg.wait_for_timeout(900)
            pg.evaluate("()=>{Object.keys(window.__CH__||{}).forEach(k=>window.__CH__[k].resize());}")
            pg.wait_for_timeout(900)
            ov = pg.evaluate("()=>document.documentElement.scrollWidth - document.documentElement.clientWidth")
            logs.append("宽 %d 横向溢出 = %d" % (w, ov))
            if ov > 3:
                fails.append("宽 %d 出现横向溢出 %dpx" % (w, ov))
            if w == 420:
                pg.screenshot(path=os.path.join(SHOTS, "mobile.png"), full_page=True)
        b.close()


run()
report = "\n".join(logs) + "\n\nFAIL=%d\n" % len(fails) + "\n".join("  [FAIL] " + f for f in fails)
rep_path = os.path.join(os.path.dirname(os.path.abspath(OUT)) or ".", "qa_html.txt")
open(rep_path, "w", encoding="utf-8").write(report)
print(report)
sys.exit(0 if not fails else 1)
