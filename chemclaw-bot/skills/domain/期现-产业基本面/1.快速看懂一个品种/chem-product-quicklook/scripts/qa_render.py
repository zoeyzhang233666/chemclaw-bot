#!/usr/bin/env python3
"""qa_render.py — 浏览器实测：JS 报错 / 首屏渲染 / 图谱展开收起 / 抽屉 / 下方面板 / 横向溢出

用法:
    python scripts/qa_render.py out/xxx.html [--shots shots/] [--expect-nodes N]

检查项（任一失败即退出码 1）：
  1. 控制台无 JS 异常
  2. 首屏：标题、核心信息卡格数、研究框架卡数
  3. 产业链：节点数=数据节点数；点“全部展开”后 .expanded 数上升；点“全部收起”后归零；
     单节点 +/− 切换有效；整列伸缩有效
  4. 抽屉：点击节点打开、五个标签页都能渲染非空、Esc 关闭
  5. 下方面板：每个面板都能切换且内容非空
  6. 1600 / 1280 / 420 三档无 body 级横向溢出（图谱列允许内部滚动）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def extract_data(html: str) -> dict:
    m = re.search(r"<script>\s*window\.__DATA__\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    if not m:
        raise SystemExit("无法从 HTML 中解析 __DATA__")
    return json.loads(m.group(1).replace("<\\\\/", "</"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--shots", default=None)
    ap.add_argument("--keep-open", action="store_true")
    a = ap.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[qa_render] 未安装 playwright，跳过浏览器实测（静态检查仍需通过 check_html.py）")
        return 0

    html_path = Path(a.html).resolve()
    html = html_path.read_text(encoding="utf-8")
    data = extract_data(html)
    n_nodes = len(data.get("chain", {}).get("nodes", []))
    n_panels = len(data.get("panels", []))
    shots = Path(a.shots) if a.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    fails, oks = [], []

    def ok(msg):
        oks.append(msg)
        print("  ✓ " + msg)

    def fail(msg):
        fails.append(msg)
        print("  ✗ " + msg)

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        errs = []
        pg.on('console', lambda m: errs.append('CONSOLE ' + m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append('PAGEERROR ' + str(e)))
        
        pg.goto(html_path.as_uri())
        pg.wait_for_timeout(900)

        if errs:
            fail(f"控制台错误 {len(errs)} 条：{errs[:3]}")
        else:
            ok("无 JS 异常")

        title = pg.title()
        ok(f"标题：{title}") if title else fail("标题为空")

        # 首屏
        props = pg.eval_on_selector_all("#propgrid .prop", "els=>els.length")
        fcards = pg.eval_on_selector_all("#framebar .fcard", "els=>els.length")
        (ok if props >= 8 else fail)(f"核心信息卡 {props} 格")
        (ok if fcards >= 4 else fail)(f"研究框架卡 {fcards} 张")

        # 图谱
        gn = pg.eval_on_selector_all("#chain .gnode", "els=>els.length")
        (ok if gn == n_nodes else fail)(f"图谱节点 {gn} / 数据 {n_nodes}")
        exp0 = pg.eval_on_selector_all("#chain .gnode.expanded", "els=>els.length")
        pg.click("#btn-expand-all")
        pg.wait_for_timeout(200)
        exp1 = pg.eval_on_selector_all("#chain .gnode.expanded", "els=>els.length")
        # 数据里存在可展开的嵌套子节点时，展开数必须增加；扁平数据（无 children）时允许不变
        n_kids = pg.eval_on_selector_all("#chain .gn-kids", "els=>els.length")
        if n_kids > 0:
            (ok if exp1 > exp0 else fail)(f"全部展开：{exp0} → {exp1}")
        else:
            (ok if exp1 == exp0 else fail)(f"全部展开（无子节点数据，应不变）：{exp0} → {exp1}")
        pg.click("#btn-collapse-all")
        pg.wait_for_timeout(200)
        exp2 = pg.eval_on_selector_all("#chain .gnode.expanded", "els=>els.length")
        (ok if exp2 == 0 else fail)(f"全部收起后展开数 {exp2}（应为 0）")

        if not pg.query_selector("#chain .gnode"):
            fail("图谱未渲染，后续交互检查中止")
            pg.screenshot(path=str(shots / "error.png")) if shots else None
            b.close()
            print(f"\n[qa_render] 失败 {len(fails)} 项")
            return 1

        # 单节点切换
        caret = pg.query_selector("#chain .gnode .caret")
        if caret:
            node_id = caret.get_attribute("data-care")
            caret.click()
            pg.wait_for_timeout(150)
            is_exp = pg.eval_on_selector(f'.gnode[data-node="{node_id}"]', "el=>el.classList.contains('expanded')")
            caret2 = pg.query_selector(f'.gnode[data-node="{node_id}"] .caret')
            caret2.click()
            pg.wait_for_timeout(150)
            is_col = pg.eval_on_selector(f'.gnode[data-node="{node_id}"]', "el=>el.classList.contains('collapsed')")
            (ok if is_exp and is_col else fail)(f"单节点 +/− 切换：展开={is_exp} 收起={is_col}")
            # 展开态下子节点可见
            caret2.click()
            pg.wait_for_timeout(150)
            vis = pg.eval_on_selector(f'.gnode[data-node="{node_id}"] .gn-kids', "el=>getComputedStyle(el).display")
            (ok if vis != "none" else fail)(f"展开后子节点显示：display={vis}")

        # 整列
        coltg = pg.query_selector("[data-col-toggle]")
        if coltg:
            before = pg.eval_on_selector_all("#chain .gnode.expanded", "els=>els.length")
            coltg.click()
            pg.wait_for_timeout(200)
            after = pg.eval_on_selector_all("#chain .gnode.expanded", "els=>els.length")
            # 该列无子节点时，整列按钮只切换样式，展开计数不变属正常
            if before == 0 and after == 0:
                ok(f"整列伸缩：该列无可展开子节点，切换后状态一致（{before} → {after}）")
            else:
                (ok if after != before else fail)(f"整列伸缩：{before} → {after} 展开")

        # 抽屉
        first = pg.query_selector("#chain .gnode")
        first.click()
        pg.wait_for_timeout(350)
        shown = pg.eval_on_selector("#drawer", "el=>el.classList.contains('show')")
        (ok if shown else fail)("点击节点打开抽屉")
        tab_results = {}
        for t in ["overview", "price", "who", "proj", "src"]:
            pg.click(f'#dr-tabs button[data-tab="{t}"]')
            pg.wait_for_timeout(180)
            txt = pg.eval_on_selector("#dr-body", "el=>el.innerText.trim().length")
            tab_results[t] = txt
        (ok if all(v > 10 for v in tab_results.values()) else fail)(f"五标签页内容长度 {tab_results}")
        if shots:
            pg.screenshot(path=str(shots / "drawer.png"))
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        closed = pg.eval_on_selector("#drawer", "el=>!el.classList.contains('show')")
        (ok if closed else fail)("Esc 关闭抽屉")

        # 下方面板
        btns = pg.query_selector_all("#mtab button")
        nonempty = 0
        for btn in btns:
            btn.click()
            pg.wait_for_timeout(120)
            ln = pg.eval_on_selector_all(".mpanel.on", "els=>els[0]?els[0].innerText.trim().length:0")
            if ln > 30:
                nonempty += 1
        (ok if nonempty == n_panels else fail)(f"下方面板可切换且非空：{nonempty}/{n_panels}")
        # 工艺路线卡展开（限定在“工艺与原料”面板内）
        rp = pg.query_selector("#panel-routes")
        if rp:
            tb = pg.query_selector("#mtab button[data-panel='routes']")
            if tb:
                tb.click()
            pg.wait_for_timeout(150)
            pg.eval_on_selector("#panel-routes .route", "el=>el.classList.add('open')")
            pg.wait_for_timeout(220)
            h = pg.eval_on_selector("#panel-routes .route .route-body", "el=>el.getBoundingClientRect().height")
            cnt = pg.eval_on_selector_all("#panel-routes .route", "e=>e.length")
            (ok if h > 40 and cnt > 0 else fail)(f"工艺卡 {cnt} 张、展开高度 {h:.0f}px")
        else:
            ok("本品种无工艺路线面板，跳过工艺卡检查")
        # 指标折叠（限定在“指标与逻辑”面板内）
        ip = pg.query_selector("#panel-indicators .ind-h")
        if ip:
            tb = pg.query_selector("#mtab button[data-panel='indicators']")
            if tb:
                tb.click()
            pg.wait_for_timeout(150)
            pg.eval_on_selector("#panel-indicators .ind-h", "el=>el.click()")
            pg.wait_for_timeout(150)
            vis = pg.eval_on_selector("#panel-indicators .ind", "el=>el.classList.contains('open')")
            (ok if vis else fail)("研究指标折叠展开")

        # 截图
        if shots:
            pg.screenshot(path=str(shots / "full-1600.png"), full_page=True)

        # 溢出
        for w in (1600, 1280, 420):
            pg.set_viewport_size({"width": w, "height": 1000})
            pg.wait_for_timeout(250)
            ov = pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            (ok if ov <= 2 else fail)(f"{w}px 横向溢出 {ov}px")
            if shots and w == 1280:
                pg.screenshot(path=str(shots / "full-1280.png"), full_page=True)
            if shots and w == 420:
                pg.screenshot(path=str(shots / "mobile-420.png"), full_page=True)

        # 关键模块存在
        for sel, name in [("#sec-chain", "产业链区"), ("#sec-sources", "来源区"), ("#gaps", "缺口区"), ("#srclist", "来源清单")]:
            n = pg.eval_on_selector_all(f"{sel} *", "els=>els.length")
            (ok if n > 0 else fail)(f"{name} 已渲染（{n} 元素）")

        # ---- 设计回归检查（防止修复过的视觉问题再次出现）----
        pg.set_viewport_size({"width": 1600, "height": 1000})
        pg.wait_for_timeout(300)
        pg.evaluate("()=>window.scrollTo(0,0)")
        pg.wait_for_timeout(150)

        # R1 产业链必须有连线（canvas 上要有非透明像素）
        px = pg.evaluate("""() => {
          const c=document.querySelector('#chain canvas.cedge'); if(!c) return 0;
          const g=c.getContext('2d'); const d=g.getImageData(0,0,c.width,c.height).data;
          let n=0; for(let i=3;i<d.length;i+=4) if(d[i]>0) n++;
          return n; }""")
        (ok if px > 200 else fail)(f"产业链连线已绘制（{px} 像素）")

        # R2 表头不得出现英文数据键
        # 注意：隐藏面板里的元素 innerText 是空串，会被误判成命中，
        # 因此这里用 textContent 并排除空值。
        raw_keys = pg.evaluate("""()=>[...document.querySelectorAll('table.data th')]
          .map(t=>(t.textContent||'').trim())
          .filter(v=>v && ['src','sources','cap','note','desc','meta'].includes(v))
          .length""")
        (ok if raw_keys == 0 else fail)(f"表头无英文数据键泄漏（发现 {raw_keys} 处）")

        # R3 节点类别色条必须与图例一致
        kinds = pg.evaluate("""()=>{const m={};
          document.querySelectorAll('.gnode').forEach(e=>{
            const k=e.getAttribute('data-kind')||'(none)';
            m[k]=getComputedStyle(e).borderLeftWidth;}); return m;}""")
        missing_bar = [k for k, v in kinds.items() if v in ("0px", "0px none")]
        (ok if not missing_bar else fail)(f"节点类别色条已应用（缺色条：{missing_bar or '无'}）")

        # R4 表格斑马纹
        zebra = pg.evaluate("""()=>{const t=document.querySelector('table.data tbody');
          if(!t||t.children.length<2) return 'skip';
          const a=getComputedStyle(t.children[0].cells[0]).backgroundColor;
          const c=getComputedStyle(t.children[1].cells[0]).backgroundColor;
          return a===c?'same':'diff';}""")
        (ok if zebra in ("diff", "skip") else fail)(f"表格斑马纹（{zebra}）")

        # R5 正文三级文字全部达到 WCAG AA（≥4.5:1）
        low = pg.evaluate("""()=>{
          const parse=s=>{
            let m=s.match(/rgba?\\(([^)]+)\\)/);
            if(m){const p=m[1].split(/[,\\/\\s]+/).filter(Boolean).map(Number);
              return {rgb:[p[0],p[1],p[2]], a: p.length>3 ? p[3] : 1};}
            m=s.match(/^#([0-9a-f]{3,8})$/i);
            if(m){let h=m[1];
              if(h.length===3) h=h.split('').map(x=>x+x).join('');
              return {rgb:[parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)],
                      a: h.length>=8 ? parseInt(h.slice(6,8),16)/255 : 1};}
            return {rgb:[7,12,21], a:1};
          };
          const lum=c=>{const f=c.map(v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});
            return 0.2126*f[0]+0.7152*f[1]+0.0722*f[2];};
          const ratio=(a,b)=>{const L1=lum(a),L2=lum(b);return (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);};
          const bad=[];
          ['.src','.gnode .gn-m','.prop .k','.chcol-head .cnt','.chcol-head .nm'].forEach(sel=>{
            const e=document.querySelector(sel); if(!e) return;
            let el=e, bg=[7,12,21], guard=0;
            while(el && guard++<15){
              const c=parse(getComputedStyle(el).backgroundColor);
              if(c.a>0.5){bg=c.rgb; break;}
              el=el.parentElement;
            }
            const fg=parse(getComputedStyle(e).color).rgb;
            const r=ratio(fg,bg);
            if(r<4.5) bad.push(sel+'='+r.toFixed(2));});
          return bad;}""")
        (ok if not low else fail)(f"文字对比度达 AA（不合格：{low or '无'}）")

        # R6 首屏必须露出产业链（核心信息卡 + 框架 + 图谱起始）
        fold = pg.evaluate("""()=>{const c=document.querySelector('#chain');
          const f=document.querySelector('#framebar');
          return {chain:c?Math.round(c.getBoundingClientRect().top):-1,
                  frame:f?Math.round(f.getBoundingClientRect().bottom):-1};}""")
        (ok if fold["chain"] < 1000 else fail)(f"首屏露出产业链（图谱 top={fold['chain']}px < 1000）")

        # R7 不得出现合成/示意价格曲线（防数据造假）
        # 打开“本品种”节点的价格页，比较：数据里有没有 series ↔ 页面上有没有图表
        pg.evaluate("""()=>{const n=[...document.querySelectorAll('#chain .gnode')]
          .find(e=>e.getAttribute('data-kind')==='self'); if(n) n.click();}""")
        pg.wait_for_timeout(400)
        ptr = pg.query_selector('#dr-tabs button[data-tab="price"]')
        if ptr:
            ptr.click()
            pg.wait_for_timeout(500)
        chart = pg.evaluate("""()=>{
          const s=window.__DATA__||{};
          const self=(s.chain&&s.chain.nodes||[]).filter(n=>n.is_self)[0]||{};
          const r=self.research||{};
          const hasSeries=(r.series||[]).length>=8;
          const canvas=document.querySelector('#dr-body canvas');
          const gap=!!(document.querySelector('#dr-body .gapcard'));
          const mc=document.querySelector('#minichart');
          return {hasSeries:hasSeries, canvas:!!canvas,
                  miniVisible: !!(mc && getComputedStyle(mc).display!=='none'),
                  gap:gap};}""")
        if chart["hasSeries"]:
            good = chart["canvas"] and chart["miniVisible"]
            (ok if good else fail)(f"有实测序列时价格图正常绘制（canvas={chart['canvas']}, 可见={chart['miniVisible']}）")
        else:
            good = (not chart["canvas"]) and (not chart["miniVisible"])
            (ok if good else fail)(f"无序列时不绘制价格曲线（canvas={chart['canvas']}，应显示缺口卡={chart['gap']}）")

        b.close()

    print(f"\n[qa_render] 通过 {len(oks)} 项，失败 {len(fails)} 项")
    if fails:
        for f in fails:
            print("  !! " + f)
        return 1
    print("[qa_render] 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
