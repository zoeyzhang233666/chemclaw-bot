"""
qa_render.py — 真浏览器渲染校验（可选步骤，静态检查通过后再跑）。

用途：把 check_html.py 看不到的东西查出来 —— 图表真的画出来了吗、有没有文字溢出、
点击按钮抽屉会不会打开、页面有没有 JS 报错。

实现：直接驱动本机已安装的 Edge/Chrome（--headless=new + DevTools Protocol），
      不依赖 Playwright / Selenium，不需要联网，不需要额外 pip 包
      （只用 websocket-client；缺失时自动退化到 --screenshot 方式）。

  python qa_render.py out/xxx.html [--outdir out/qa] [--width 1680]
  python qa_render.py out/xxx.html --click "#partnerTable .linkbtn"      # 测抽屉

输出 JSON：{ok, charts:[...], errors:[...], clicks:[...], shots:[...]}
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

PROBE = r"""
(() => {
  const out = {title: document.title, pageH: document.body.scrollHeight, vw: document.documentElement.clientWidth,
               charts: [], errors: window.__errs || [], overflowing: [], placeholderLeaks: []};
  document.querySelectorAll('.chart').forEach(el => {
    const cv = el.querySelector('canvas');
    let px = null;
    if (cv) { try { const d = cv.getContext('2d').getImageData(0,0,Math.min(cv.width,400),Math.min(cv.height,400)).data;
      px = 0; for (let i=3;i<d.length;i+=4*37) if (d[i]>8) px++; } catch(e){ px = 'err'; } }
    out.charts.push({id: el.id, w: el.clientWidth, h: el.clientHeight, hasCanvas: !!cv, ink: px});
  });
  const vw = document.documentElement.clientWidth;
  document.querySelectorAll('section,.panel,.card,.kpi,table').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.right > vw + 2) out.overflowing.push(el.id || el.className);
  });
  const txt = document.body.innerText;
  ['undefined','NaN','__DATA__','[object Object]'].forEach(t => {
    if (txt.indexOf(t) >= 0) out.placeholderLeaks.push(t);
  });
  out.kpi = Array.from(document.querySelectorAll('.kpi .big')).map(e => e.innerText);
  return out;
})()
"""


def _stray_browsers(exe):
    """Headless runs can leave zombie children holding the debug port; clear only ours."""
    if not exe:
        return
    name = os.path.splitext(os.path.basename(exe))[0]
    try:
        if sys.platform.startswith("win"):
            subprocess.run(["taskkill", "/F", "/IM", name + ".exe", "/T"],
                           capture_output=True, timeout=30)
    except Exception:
        pass


def find_browser(explicit=None):
    if explicit and os.path.exists(explicit):
        return explicit
    return next((p for p in BROWSERS if os.path.exists(p)), None)


def run(exe, url, outdir, width, height, clicks):
    try:
        import websocket  # noqa: F401
    except ImportError:
        return fallback_screenshot(exe, url, outdir, width)
    # fall back to a free port if the previous run left one behind
    for port in (9511, 9512, 9513, 9514, 9515):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/json" % port, timeout=1)
            continue  # occupied
        except Exception:
            break
    else:
        port = 9516
    if port != 9511:
        _stray_browsers(exe)
    # throw-away profile in the OS temp dir: never pollute the deliverable folder
    prof = os.path.join(tempfile.mkdtemp(prefix="ccm_qa_"), "profile")
    os.makedirs(prof, exist_ok=True)
    logf = open(os.path.join(outdir, "_browser.log"), "wb")
    proc = subprocess.Popen(
        [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
         "--remote-debugging-port=%d" % port, "--remote-allow-origins=*",
         "--user-data-dir=" + prof, "--window-size=%d,%d" % (width, height), "about:blank"],
        stdout=logf, stderr=logf)
    try:
        import websocket
        import threading
        tabs, t0 = None, time.time()
        ws = card = None

        def connect():
            nonlocal tabs, ws, card
            for _ in range(60):
                try:
                    tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/json" % port, timeout=2).read())
                    if tabs:
                        break
                except Exception:
                    time.sleep(0.4)
            if not tabs:
                return
            # Chrome puts extension background pages first; attach to a real page target
            page = next((t for t in tabs if t.get("type") == "page"), tabs[0])
            ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=60)
            card = {"t": time.time(), "alive": True}

            def watchdog():
                while card["alive"]:
                    time.sleep(2)
                    if time.time() - card["t"] > 60:
                        try:
                            ws.shutdown()
                        except Exception:
                            pass
                        return
            threading.Thread(target=watchdog, daemon=True).start()

        def later():
            time.sleep(150)
            try:
                ws.shutdown()
            except Exception:
                pass

        threading.Thread(target=later, daemon=True).start()
        threading.Thread(target=connect, daemon=True).start()
        t_end = time.time() + 45
        while ws is None and time.time() < t_end:
            time.sleep(0.3)
        if ws is None:
            raise RuntimeError("DevTools 未就绪（端口 %d）" % port)
        state = {"n": 0, "session": None, "msgs": []}

        def send(method, params=None):
            state["n"] += 1
            mid = state["n"]
            msg = {"id": mid, "method": method, "params": params or {}}
            if state["session"] and not method.startswith("Target."):
                msg["sessionId"] = state["session"]
            if card:
                card["t"] = time.time()
            ws.send(json.dumps(msg))
            while True:
                m = json.loads(ws.recv())
                if card:
                    card["t"] = time.time()
                if m.get("method") in ("Runtime.exceptionThrown", "Runtime.consoleAPICalled"):
                    state["msgs"].append(m)
                if m.get("id") == mid:
                    return m.get("result") or {}

        send("Page.enable")
        send("Runtime.enable")
        # navigate the tab we are already attached to, and never persist the debug profile
        # (a leftover user-data-dir makes a fresh headless run come up empty, which wedges CDP)
        send("Emulation.setDeviceMetricsOverride",
             {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
        send("Page.navigate", {"url": url})
        time.sleep(4)
        ws_ok = ""
        for _ in range(20):
            ws_ok = (send("Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
                     .get("result", {}).get("value", "") or "")
            if ws_ok.startswith("file:") or ws_ok.startswith("http"):
                break
            time.sleep(0.5)
        if not (ws_ok.startswith("file:") or ws_ok.startswith("http")):
            raise RuntimeError("未能导航到目标页：%s" % ws_ok)
        # scroll once so lazy charts size correctly
        h = send("Runtime.evaluate", {"expression": "document.body.scrollHeight", "returnByValue": True})["result"]["value"]
        for y in range(0, int(h), 900):
            send("Runtime.evaluate", {"expression": "window.scrollTo(0,%d)" % y})
            time.sleep(0.25)
        send("Runtime.evaluate", {"expression": "window.scrollTo(0,0)"})
        time.sleep(0.4)
        probe = json.loads(send("Runtime.evaluate", {"expression": "JSON.stringify(%s)" % PROBE,
                                                     "returnByValue": True})["result"]["value"])
        # screenshots
        shots = []
        for i, y in enumerate(range(0, int(h), height)):
            send("Runtime.evaluate", {"expression": "window.scrollTo(0,%d)" % y})
            time.sleep(0.4)
            p = os.path.join(outdir, "shot_%02d.png" % i)
            r = send("Page.captureScreenshot", {"format": "png"})
            open(p, "wb").write(base64.b64decode(r["data"]))
            shots.append(p)
        click_res = []
        for sel in clicks:
            r = send("Runtime.evaluate", {"expression":
                     "(()=>{const e=document.querySelector(%s);if(!e)return 'NOTFOUND';e.click();return 'OK';})()"
                     % json.dumps(sel), "returnByValue": True})["result"].get("value")
            time.sleep(0.8)
            opened = send("Runtime.evaluate", {"expression":
                          "document.getElementById('drawer').classList.contains('on')", "returnByValue": True}
                          )["result"].get("value")
            p = os.path.join(outdir, "click_%s.png" % sel.replace("#", "").replace(".", "_").replace(" ", "")[:30])
            rr = send("Page.captureScreenshot", {"format": "png"})
            open(p, "wb").write(base64.b64decode(rr["data"]))
            click_res.append({"selector": sel, "found": r, "drawer_open": opened, "shot": p})
        errs = []
        for m in state["msgs"]:
            if m.get("method") == "Runtime.exceptionThrown":
                d = m["params"]["exceptionDetails"]
                errs.append("JS异常: " + (d.get("text") or "") + " " + str(d.get("exception", {}).get("description", ""))[:200])
            elif m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] == "error":
                errs.append("console.error")
        ws.close()
        return {"ok": True, "probe": probe, "errors": errs, "clicks": click_res, "shots": shots}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()
        _stray_browsers(exe)
        try:
            logf.close()
        except Exception:
            pass
        try:
            shutil.rmtree(os.path.dirname(prof), ignore_errors=True)
        except Exception:
            pass


def fallback_screenshot(exe, url, outdir, width):
    p = os.path.join(outdir, "shot_00.png")
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--screenshot=" + p, "--window-size=%d,4000" % width, url],
                   capture_output=True, timeout=120)
    return {"ok": os.path.exists(p), "probe": None, "shots": [p] if os.path.exists(p) else [],
            "errors": [], "clicks": [], "note": "未安装 websocket-client，仅生成整页截图"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--width", type=int, default=1680)
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--click", action="append", default=[])
    ap.add_argument("--browser", default="")
    a = ap.parse_args()
    exe = find_browser(a.browser)
    if not exe:
        print(json.dumps({"ok": False, "reason": "未找到 Edge/Chrome，跳过浏览器校验"}, ensure_ascii=False))
        return 0
    html = os.path.abspath(a.html)
    outdir = a.outdir or os.path.join(os.path.dirname(html), "qa")
    os.makedirs(outdir, exist_ok=True)
    url = "file:///" + html.replace("\\", "/").replace("#", "%23")
    res = run(exe, url, outdir, a.width, a.height, a.click)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
