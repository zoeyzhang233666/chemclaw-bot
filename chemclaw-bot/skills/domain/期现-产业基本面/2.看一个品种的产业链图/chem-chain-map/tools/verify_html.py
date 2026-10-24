"""HTML 交互与渲染自检：用 Playwright 在 Chromium 中打开生成的图谱，逐项断言。"""
import json
import sys

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

HTML = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
W, H = 1680, 1000


def main():
    res = {"checks": [], "ok": True}

    def chk(name, cond, detail=""):
        res["checks"].append({"name": name, "pass": bool(cond), "detail": detail})
        if not cond:
            res["ok"] = False
        print(("  PASS " if cond else "  FAIL ") + name + (("  " + str(detail)) if detail and not cond else ""))

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb"])
        pg = b.new_page(viewport={"width": W, "height": H})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append("console." + m.type + ": " + m.text) if m.type == "error" else None)
        pg.goto("file:///" + HTML.replace("\\", "/"))
        pg.wait_for_timeout(1400)

        chk("无 JS 运行时错误", not errors, errors[:3])
        chk("window.CHAIN 已暴露", pg.evaluate("!!window.CHAIN") is True)

        # 1 节点/边数量
        counts = pg.evaluate("window.CHAIN.counts()")
        data_n = pg.evaluate("window.CHAIN_DATA.nodes.length")
        data_e = pg.evaluate("window.CHAIN_DATA.relations.length")
        chk("节点渲染数与数据一致 (%d)" % data_n, counts["nodes"] == data_n, counts)
        chk("连线渲染数与数据一致 (%d)" % data_e, counts["edges"] == data_e, counts)

        # 2 覆盖面板
        gtxt = pg.evaluate("(document.querySelector('#gaugeTxt')||{}).textContent")
        chk("覆盖表盘有数值 (%s)" % gtxt, gtxt and "%" in gtxt)
        cov_cards = pg.evaluate("document.querySelectorAll('#covCards .cov-card').length")
        chk("覆盖卡片渲染 (%d)" % cov_cards, cov_cards >= 5, cov_cards)
        scope = pg.evaluate("(document.querySelector('#covScope')||{}).textContent||''")
        chk("覆盖口径说明存在", len(scope) > 40, scope[:60])

        # 3 缩放
        k0 = pg.evaluate("window.CHAIN.state.k")
        pg.click("#btnZoomIn"); pg.wait_for_timeout(220)
        k1 = pg.evaluate("window.CHAIN.state.k")
        chk("放大按钮生效 (%.3f→%.3f)" % (k0, k1), k1 > k0)
        pg.click("#btnZoomOut"); pg.wait_for_timeout(220)
        k2 = pg.evaluate("window.CHAIN.state.k")
        chk("缩小按钮生效 (%.3f→%.3f)" % (k1, k2), k2 < k1)

        # 4 拖拽平移（小图会完整落在视口里，此时 clamp 会锁住平移 → 先放大到超出视口）
        pg.evaluate("window.CHAIN.zoom(2.6)")
        pg.wait_for_timeout(240)
        box = pg.query_selector("#svg").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] - 40
        t0 = pg.evaluate("window.CHAIN.state.tx")
        pg.mouse.move(cx, cy); pg.mouse.down()
        pg.mouse.move(cx - 120, cy - 30, steps=8); pg.mouse.up()
        pg.wait_for_timeout(160)
        t1 = pg.evaluate("window.CHAIN.state.tx")
        chk("画布可拖拽平移 (tx %.1f→%.1f)" % (t0, t1), abs(t1 - t0) > 5)
        pg.click("#btnFit"); pg.wait_for_timeout(260)

        # 5 节点点击 → 侧栏
        first = pg.evaluate("window.CHAIN_DATA.nodes.find(n=>n.node_role==='target')?.id || window.CHAIN_DATA.nodes[0].id")
        pg.evaluate("window.CHAIN.selectNode(%s)" % json.dumps(first))
        pg.wait_for_timeout(320)
        sb = pg.evaluate("document.querySelector('#sbBody').innerText")
        chk("节点侧栏有标题", len(sb) > 120, len(sb))
        chk("侧栏含 CAS 行", "CAS" in sb)
        chk("侧栏含价格区块", ("价格" in sb))
        chk("侧栏含企业区块", ("企业" in sb))
        chk("侧栏含证据区块", ("证据" in sb))

        # 6 上下游高亮
        dim = pg.evaluate("document.querySelectorAll('.node.dim').length")
        up = pg.evaluate("document.querySelectorAll('.node.up').length")
        dn = pg.evaluate("document.querySelectorAll('.node.down').length")
        chk("选中后上下游高亮 (上游%d 下游%d 变暗%d)" % (up, dn, dim), (up + dn) > 0 and dim > 0)

        # 7 点关系线
        rel_id = pg.evaluate("window.CHAIN_DATA.relations[0].id")
        pg.evaluate("window.CHAIN.selectRelation(%s)" % json.dumps(rel_id))
        pg.wait_for_timeout(300)
        sb2 = pg.evaluate("document.querySelector('#sbBody').innerText")
        chk("关系侧栏含工艺", "工艺" in sb2, sb2[:80])
        chk("关系侧栏含单耗", "单耗" in sb2)
        chk("关系侧栏含口径/来源", ("口径" in sb2 or "来源" in sb2 or "计算" in sb2))

        # 8 搜索
        q = pg.evaluate("window.CHAIN_DATA.nodes[3].name.slice(0,2)")
        pg.fill("#search", q); pg.wait_for_timeout(420)
        drop = pg.evaluate("document.querySelectorAll('#searchDrop .sr-item').length")
        filt = pg.evaluate("document.querySelectorAll('.node.filtered').length")
        chk("搜索下拉有结果 (%s → %d 项)" % (q, drop), drop >= 1, drop)
        chk("搜索会过滤画布 (隐藏 %d)" % filt, filt > 0, filt)
        pg.fill("#search", ""); pg.wait_for_timeout(320)

        # 9 关系类型筛选
        chips = pg.query_selector_all("#typeChips .chip")
        chk("关系类型筛选按钮 >= 5 个 (%d)" % len(chips), len(chips) >= 5)
        chips[1].click(); pg.wait_for_timeout(380)
        fe = pg.evaluate("document.querySelectorAll('.edge.filtered').length")
        chk("关系筛选生效 (隐藏边 %d)" % fe, fe > 0, fe)
        chips[0].click(); pg.wait_for_timeout(300)

        # 10 工艺筛选下拉
        opts = pg.evaluate("document.querySelectorAll('#routeSel option').length")
        chk("工艺路线下拉有选项 (%d)" % opts, opts >= 2, opts)

        # 11 价格联动
        ids = pg.evaluate("window.CHAIN_DATA.nodes.filter(n=>n.node_class==='commodity').slice(0,2).map(n=>n.id)")
        pg.evaluate("window.CHAIN.addMulti(%s); window.CHAIN.addMulti(%s);" % (json.dumps(ids[0]), json.dumps(ids[1])))
        pg.wait_for_timeout(380)
        sb3 = pg.evaluate("document.querySelector('#sbBody').innerText")
        chk("价格联动面板出现", ("价格联动" in sb3) or ("联动" in sb3), sb3[:80])

        # 12 层级表兜底
        pg.click("#btnTableMode"); pg.wait_for_timeout(420)
        tm_rows = pg.evaluate("document.querySelectorAll('table.tm tbody tr').length")
        chk("层级表可用 (%d 行)" % tm_rows, tm_rows >= data_n, tm_rows)
        pg.click("#btnTableMode"); pg.wait_for_timeout(260)

        # 13 覆盖面板折叠
        pg.click("#btnCovToggle"); pg.wait_for_timeout(360)
        collapsed = pg.evaluate("document.querySelector('#coverageBar').classList.contains('collapsed')")
        chk("覆盖面板可折叠", collapsed)
        pg.click("#btnCovToggle"); pg.wait_for_timeout(300)

        # 13b 「适应」默认视图：节点必须足够大可读（允许需拖拽）
        pg.click("#btnFit"); pg.wait_for_timeout(320)
        geo_fit = pg.evaluate("""() => {
          const ns=[...document.querySelectorAll('.node')].map(g=>{
            const r=g.getBoundingClientRect(); return {w:r.width,h:r.height};});
          const w=ns.map(n=>n.w);
          return {minW:Math.min(...w), minH:Math.min(...ns.map(n=>n.h)), k:window.CHAIN.state.k};
        }""")
        chk("默认视图节点可读 (minW %.0f)" % geo_fit["minW"], geo_fit["minW"] >= 140, geo_fit)

        # 13c 「总览」视图：所有节点必须完整落在画布内
        pg.click("#btnFitAll"); pg.wait_for_timeout(360)
        geo_all = pg.evaluate("""() => {
          const ns=[...document.querySelectorAll('.node')].map(g=>{
            const r=g.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height};});
          const svg=document.querySelector('#svg').getBoundingClientRect();
          const off=ns.filter(n=>n.x+n.w<svg.x-2||n.x>svg.x+svg.width+2||n.y+n.h<svg.y-2||n.y>svg.y+svg.height+2).length;
          return {outside:off, k:window.CHAIN.state.k};
        }""")
        chk("总览视图全部节点在画布内 (越界 %d)" % geo_all["outside"], geo_all["outside"] == 0, geo_all)
        pg.click("#btnFit"); pg.wait_for_timeout(280)

        # 14 渲染几何：节点互不重叠、不出画布
        geo = pg.evaluate("""() => {
          const ns=[...document.querySelectorAll('.node')].map(g=>{
            const r=g.getBoundingClientRect(); return {id:g.dataset.id,x:r.x,y:r.y,w:r.width,h:r.height};});
          let ov=0;
          for(let i=0;i<ns.length;i++)for(let j=i+1;j<ns.length;j++){
            const a=ns[i],b=ns[j];
            const ox=Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x);
            const oy=Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y);
            if(ox>1&&oy>1)ov++;
          }
          const svg=document.querySelector('#svg').getBoundingClientRect();
          const off=ns.filter(n=>n.x+n.w<svg.x-2||n.x>svg.x+svg.width+2||n.y+n.h<svg.y-2||n.y>svg.y+svg.height+2).length;
          const w=ns.map(n=>n.w);
          return {overlap:ov, outside:off, minW:Math.min(...w), maxW:Math.max(...w), count:ns.length};
        }""")
        chk("屏幕空间节点无重叠 (%d)" % geo["overlap"], geo["overlap"] == 0, geo)
        chk("节点宽度 >= 140px (min %.0f)" % geo["minW"], geo["minW"] >= 140, geo)

        # 15 文字不被裁切（标题宽度 <= 节点宽度）
        clip = pg.evaluate("""() => {
          let bad=0;
          document.querySelectorAll('.node').forEach(g=>{
            const r=g.getBoundingClientRect();
            g.querySelectorAll('text').forEach(t=>{
              const tr=t.getBoundingClientRect();
              if(tr.width>0 && (tr.right>r.right+1.5||tr.left<r.left-1.5)) bad++;
            });
          });
          return bad;
        }""")
        chk("节点文字不溢出 (%d)" % clip, clip == 0, clip)

        # 16 小地图
        mini = pg.evaluate("document.querySelectorAll('#miniNodes rect').length")
        chk("小地图渲染 (%d)" % mini, mini >= data_n, mini)

        # 17 无外部资源引用
        pg2 = b.new_page()
        reqs = []
        pg2.on("request", lambda r: reqs.append(r.url))
        pg2.goto("file:///" + HTML.replace("\\", "/"))
        pg2.wait_for_timeout(900)
        ext = [u for u in reqs if not u.startswith("file://")]
        chk("无外部网络依赖 (%d)" % len(ext), len(ext) == 0, ext[:3])
        pg2.close()

        if OUT:
            pg.screenshot(path=OUT, full_page=False)
            print("screenshot -> " + OUT)
        b.close()

    print(json.dumps({"ok": res["ok"], "passed": sum(1 for c in res["checks"] if c["pass"]),
                      "total": len(res["checks"])}, ensure_ascii=False))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
