# -*- coding: utf-8 -*-
"""截图与结构校验：python _shot.py <html路径> <输出目录> [shot配置json]

做法：用 chrome --remote-debugging-port 起一个 headless 浏览器（必须带 --no-sandbox），
通过 CDP 注入 JS 做 DOM 计数/交互校验，并截取若干视口。
不依赖 playwright，只用标准库 + websocket-client。
"""
import base64, json, os, subprocess, sys, time, urllib.request
import websocket

CHROME = (__import__('os').environ.get('CHROME_EXE') or __import__('shutil').which('chrome') or __import__('shutil').which('msedge') or str(__import__('pathlib').Path(__import__('os').environ.get('ProgramFiles(x86)', '')) / 'Microsoft/Edge/Application/msedge.exe'))
PORT = 9331

CHECKS = [
    ("股权树研究主体节点", "!!document.querySelector('.own .node.target')"),
    ("地图标记数", "document.querySelectorAll('svg.cn .marker').length"),
    ("基地卡片数", "document.querySelectorAll('.plant').length"),
    ("时间线条目数", "document.querySelectorAll('.tl .item').length"),
    ("产品卡片数", "document.querySelectorAll('.prod-card').length"),
    ("数据表数量", "document.querySelectorAll('table.dt').length"),
    ("等级徽章数", "document.querySelectorAll('.gA,.gB,.gC,.gD,.gNA').length"),
    ("筛选总表存在", "!!document.getElementById('idx_tbl')"),
    ("筛选下拉数", "document.querySelectorAll('select[data-f=\"idx\"]').length"),
    ("证据抽屉可打开(E05含483,676.92)",
     "(function(){openEv('E05');var ok=document.getElementById('evPanel').classList.contains('open')&&"
     "document.getElementById('evBody').innerHTML.indexOf('483,676.92')>0;closeEv();return ok})()"),
    ("产品下拉筛选命中",
     "(function(){var bar=document.getElementById('idx_bar');var sel=null;"
     "bar.querySelectorAll('select').forEach(function(x){if(x.getAttribute('data-k')==='prod')sel=x});"
     "sel.value=sel.options[1].value;applyF('idx','prod',sel.value,sel);"
     "var vis=0;document.querySelectorAll('tbody tr[data-f=\"idx\"]').forEach(function(r){"
     "if(!r.classList.contains('hide'))vis++});resetF('idx');return sel.options[1].value+' -> '+vis+' 行'})()"),
    ("关键词筛选命中(溴素)",
     "(function(){var q=document.getElementById('idx_q');q.value='溴素';applyF('idx','kw',q.value,q);"
     "var vis=0;document.querySelectorAll('tbody tr[data-f=\"idx\"]').forEach(function(r){"
     "if(!r.classList.contains('hide'))vis++});resetF('idx');return vis+' 行'})()"),
    ("地图点选联动", "(function(){var p=document.querySelectorAll('.plant')[0];"
                  "pickPlant(p.getAttribute('data-plant'));return p.classList.contains('active')})()"),
]


def main():
    html_path = sys.argv[1]
    outdir = sys.argv[2]
    cfgp = sys.argv[3] if len(sys.argv) > 3 else None
    shots = json.load(open(cfgp, encoding="utf-8-sig")) if cfgp else [{"name": "top", "y": 0, "h": 1500, "w": 1400}]
    url = "file:///" + html_path.replace("\\", "/")
    profile = os.path.join(outdir, "_cdp_profile")
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                             "--no-first-run", "--no-sandbox", "--disable-crash-reporter",
                             "--remote-debugging-port=%d" % PORT, "--window-size=1400,1000",
                             "--user-data-dir=" + profile, "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(60):
            try:
                data = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json/version" % PORT, timeout=2))
                ws_url = data["webSocketDebuggerUrl"]
                break
            except Exception:
                time.sleep(0.4)
        if not ws_url:
            print("cannot reach devtools")
            return 2
        ws = websocket.create_connection(ws_url, timeout=60, max_size=200 * 1024 * 1024)
        mid = [0]

        def send(method, params=None, session=None):
            mid[0] += 1
            msg = {"id": mid[0], "method": method, "params": params or {}}
            if session:
                msg["sessionId"] = session
            ws.send(json.dumps(msg))
            while True:
                r = json.loads(ws.recv())
                if r.get("id") == mid[0]:
                    if "error" in r:
                        raise RuntimeError(r["error"])
                    return r.get("result", {})

        tid = send("Target.createTarget", {"url": "about:blank"})["targetId"]
        s = send("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        send("Page.enable", {}, s)
        send("Runtime.enable", {}, s)
        send("Emulation.setDeviceMetricsOverride",
             {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, s)
        send("Page.navigate", {"url": url}, s)
        time.sleep(3.0)

        info = send("Runtime.evaluate", {"expression":
                    "JSON.stringify({title:document.title,height:document.body.scrollHeight,"
                    "width:document.body.scrollWidth,viewport:window.innerWidth,"
                    "cards:document.querySelectorAll('.card').length,evidence:Object.keys(EV||{}).length})",
                    "returnByValue": True}, s)["result"]["value"]
        print("PAGE", info)
        bad = 0
        for label, expr in CHECKS:
            v = send("Runtime.evaluate", {"expression": expr, "returnByValue": True}, s).get("result", {})
            val = v.get("value", v.get("description"))
            print("CHECK %-34s %s" % (label, val))
            if val in (False, 0, None, -1):
                bad += 1
        print("CHECK_FAILED", bad)
        for sh in shots:
            w, h = sh.get("w", 1400), sh.get("h", 1000)
            send("Emulation.setDeviceMetricsOverride",
                 {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False}, s)
            if sh.get("sel"):
                send("Runtime.evaluate", {"expression":
                     "var e=document.querySelector('%s'); if(e) e.scrollIntoView({block:'start'});" % sh["sel"]}, s)
            elif sh.get("click"):
                send("Runtime.evaluate", {"expression": sh["click"]}, s)
            else:
                send("Runtime.evaluate", {"expression": "window.scrollTo(0,%d)" % sh.get("y", 0)}, s)
            time.sleep(0.7)
            r = send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, s)
            p = os.path.join(outdir, "shot_%s.png" % sh["name"])
            with open(p, "wb") as f:
                f.write(base64.b64decode(r["data"]))
            print("SAVED", p, os.path.getsize(p))
        ws.close()
        return 0
    finally:
        proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
