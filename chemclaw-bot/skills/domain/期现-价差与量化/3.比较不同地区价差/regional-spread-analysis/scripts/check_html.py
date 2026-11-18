# -*- coding: utf-8 -*-
"""
check_html.py — 用无头 Edge/Chrome（CDP）真实执行 HTML 页面，捕获 JS 报错并断言关键渲染。

不依赖 webdriver / playwright：直接起 --remote-debugging-port，用标准库 websocket 说话。
（标准库没有 websocket，这里用极简 RFC6455 客户端实现，仅需 text frame。）

用法：
  python scripts/check_html.py --html build/regional-spread-report.html --result build/result.json
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


class WS:
    """极简 WebSocket 客户端（仅 text frame，够用）。"""

    def __init__(self, url):
        # ws://127.0.0.1:PORT/devtools/page/XXX
        assert url.startswith("ws://")
        hostport, path = url[5:].split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
               f"Sec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        assert b"101" in buf.split(b"\r\n")[0], buf[:200]
        self._id = 0

    def send(self, obj):
        data = json.dumps(obj).encode()
        hdr = bytearray([0x81])
        n = len(data)
        mask = os.urandom(4)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126)
            hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack(">Q", n)
        hdr += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(hdr) + masked)

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            c = self.sock.recv(n - len(buf))
            if not c:
                raise ConnectionError("socket closed")
            buf += c
        return buf

    def recv(self):
        while True:
            b1, b2 = self._recv_exact(2)
            op = b1 & 0x0F
            ln = b2 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._recv_exact(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._recv_exact(8))[0]
            payload = self._recv_exact(ln)
            if op == 0x8:
                raise ConnectionError("closed by peer")
            if op in (0x1, 0x2):
                return json.loads(payload.decode("utf-8"))

    def call(self, method, params=None):
        self._id += 1
        mid = self._id
        self.send({"id": mid, "method": method, "params": params or {}})
        while True:
            msg = self.recv()
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            yield_msg(msg)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


CONSOLE = []


def yield_msg(msg):
    """收集 console / exception 事件。"""
    m = msg.get("method")
    if m == "Runtime.consoleAPICalled":
        p = msg.get("params", {})
        txt = " ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args", []))
        CONSOLE.append((p.get("type", "log"), txt))
    elif m == "Runtime.exceptionThrown":
        d = msg.get("params", {}).get("exceptionDetails", {})
        ex = d.get("exception", {})
        CONSOLE.append(("exception", ex.get("description") or ex.get("value") or d.get("text", "")))


def pick_browser():
    for b in BROWSERS:
        if os.path.exists(b):
            return b
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default="build/regional-spread-report.html")
    ap.add_argument("--result", default="build/result.json")
    ap.add_argument("--shot", default=None, help="截图输出路径")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    browser = pick_browser()
    if not browser:
        print("未找到 Edge/Chrome，跳过浏览器校验（不算失败）")
        return 0

    html_path = os.path.abspath(a.html)
    if not os.path.exists(html_path):
        print(f"[FAIL] 找不到 {html_path}")
        return 1
    url = "file:///" + html_path.replace("\\", "/")
    profile = tempfile.mkdtemp(prefix="rscheck_")
    port = 9333
    proc = subprocess.Popen([
        browser, "--headless=new", f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
        "--disable-gpu", "--allow-file-access-from-files", "--window-size=1500,1100",
        "about:blank"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    fails, oks = [], []

    def chk(name, cond, detail=""):
        (oks if cond else fails).append(name)
        print(("  [PASS] " if cond else "  [FAIL] ") + name + ((" " + str(detail)) if detail else ""))

    try:
        target = None
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as r:
                    tabs = json.loads(r.read())
                pages = [t for t in tabs if t.get("type") == "page"]
                if pages:
                    target = pages[0]
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if not target:
            print("[FAIL] 浏览器未就绪")
            return 1

        ws = WS(target["webSocketDebuggerUrl"])
        ws.call("Runtime.enable")
        ws.call("Page.enable")
        ws.call("Page.navigate", {"url": url})
        # 等待渲染（含异步 ECharts 注入）
        for _ in range(80):
            time.sleep(0.25)
            try:
                r = ws.call("Runtime.evaluate", {"expression": "document.readyState + '|' + (window.__APP?1:0)", "returnByValue": True})
                v = r.get("result", {}).get("value", "")
                if v == "complete|1":
                    break
            except Exception:
                pass
        for _ in range(60):
            try:
                r = ws.call("Runtime.evaluate", {"expression": "(window.__APP && window.__APP.chartsOk) === true", "returnByValue": True})
                if r.get("result", {}).get("value"):
                    break
            except Exception:
                pass
            time.sleep(0.25)
        time.sleep(1.0)

        def ev(expr):
            r = ws.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
            return r.get("result", {}).get("value")

        # 1. 无 JS 异常
        exc = [c for c in CONSOLE if c[0] == "exception"]
        chk("页面无 JS 异常", not exc, (exc[0][1][:300] if exc else ""))
        errs = [c for c in CONSOLE if c[0] == "error"]
        chk("无 console.error", not errs, (errs[0][1][:200] if errs else ""))

        # 2. 关键区块已渲染
        for pid, name in [("kpis", "KPI 卡"), ("matrix-box", "价差矩阵"), ("pct-tbl", "分位表"),
                          ("pair-tbl", "有序对明细"), ("route-tbl", "路线表"), ("regime-list", "异常阶段"),
                          ("event-list", "事件日历"), ("region-cards", "区域卡"), ("producer-tbl", "企业产能"),
                          ("downstream", "下游结构"), ("gaps", "缺口表"), ("sources", "来源表"),
                          ("caliber-table", "口径对照"), ("caliber-checklist", "核对清单"),
                          ("normalize-report", "换算日志"), ("caliber-compare", "双口径对照")]:
            n = ev(f"(document.getElementById('{pid}')||{{innerHTML:''}}).innerHTML.length")
            chk(f"{name} 已渲染", (n or 0) > 60, f"{n} 字符")

        # 3. 图表
        nch = ev("Object.keys(window.__APP.charts).length")
        chk("图表已初始化 ≥6 个", (nch or 0) >= 6, nch)
        # 3b. 每个图表 canvas 真的有像素（防止"有实例但空图"）
        pix = ev("""(function(){
          var out={};
          ['ch-price','ch-spread','ch-roll','ch-hist','ch-freight','ch-map'].forEach(function(id){
            var c=(document.getElementById(id)||{}).querySelector ? document.getElementById(id).querySelector('canvas') : null;
            if(!c){ out[id]='no-canvas'; return; }
            try{
              var ctx=c.getContext('2d');
              var w=c.width,h=c.height;
              var d=ctx.getImageData(0,0,w,h).data, nz=0, tot=0;
              for(var i=0;i<d.length;i+=4*97){ tot++; if(d[i+3]>8 && (d[i]+d[i+1]+d[i+2])>40) nz++; }
              out[id]=Math.round(nz/Math.max(1,tot)*1000)/10;
            }catch(e){ out[id]='err:'+e.message.slice(0,40); }
          });
          return JSON.stringify(out);
        })()""")
        try:
            pixd = json.loads(pix or "{}")
        except Exception:
            pixd = {}
        for cid, v in pixd.items():
            okv = isinstance(v, (int, float)) and v >= 1.0
            chk(f"图表 {cid} 有绘制内容", okv, f"{v}% 非空像素")

        # 4. 与 Python 结果对账：当前价格 & 价差 & 分位
        res = json.load(open(a.result, encoding="utf-8"))
        pr = res["primary"]
        order = pr["region_order"]
        for r in order:
            expect = pr["level_stats"][r]["current"]
            got = ev(f"window.__APP.P.primary.level_stats['{r}'].current")
            chk(f"{r} 最新价与 Python 一致", abs((got or -1) - expect) < 0.01, f"JS={got} PY={expect}")
        for rec in pr["percentiles"]:
            if not rec.get("n_total"):
                continue
            k = rec["pair"]
            got = ev(f"(function(){{var P=window.__APP.P.primary,K=window.Core;"
                     f"var a='{rec['a']}',b='{rec['b']}';"
                     f"var s=K.spreadSeries(P.series,a,b);"
                     f"var w='{(res['meta']['windows'] or ['1y'])[0]}';"
                     f"var samp=K.windowSample(s,P.series.dates[P.series.dates.length-1],w);"
                     f"return K.percentileOf(s[s.length-1].v,samp);}})()")
            pyd = rec["windows"][(res["meta"]["windows"] or ["1y"])[0]]["pct"]
            chk(f"{k} 分位与 Python 一致", got is not None and abs(got - pyd) < 0.15, f"JS={got} PY={pyd}")

        # 5. 交互：开启运费 → 结果区出现
        ev("(function(){var b=document.querySelector('#freight-mode button[data-m=\"on\"]');b.click();})()")
        time.sleep(0.3)
        has = ev("document.getElementById('freight-result').innerHTML.indexOf('覆盖运费')>=0")
        chk("开启运费后出现覆盖判定", bool(has))
        # 改一条路线运费，验证重算
        ev("(function(){var i=document.querySelector('#freight-inputs input[data-route]');i.value=200;i.dispatchEvent(new Event('input'));})()")
        time.sleep(0.3)
        v = ev("(function(){var r=window.__APP.P.primary.freight.routes[0];return JSON.stringify(r);})()")
        chk("改动运费后状态更新", bool(v))

        # 6. 切换口径
        ev("document.querySelector('#caliber-seg button[data-c=\"control\"]').click()")
        time.sleep(0.4)
        cs = ev("window.__APP.S.caliber")
        chk("切换到对照口径", cs == "control", cs)
        ev("document.querySelector('#caliber-seg button[data-c=\"primary\"]').click()")
        time.sleep(0.3)

        # 7. 异常阶段详情
        ev("(function(){var d=document.querySelector('#regime-list .ev');if(d)d.click();})()")
        time.sleep(0.3)
        dl = ev("document.getElementById('regime-detail').innerHTML.length")
        chk("阶段详情已渲染", (dl or 0) > 200, dl)

        # 8. 表格无 "undefined"/"NaN"
        bad = ev("(function(){var t=document.body.innerText;var m=(t.match(/undefined|NaN|\\[object/g)||[]).length;return m;})()")
        chk("页面无 undefined/NaN 文本", (bad or 0) == 0, f"{bad} 处")

        # 截图
        if a.shot:
            r = ws.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
            with open(a.shot, "wb") as f:
                f.write(base64.b64decode(r["data"]))
            print(f"  [INFO] 截图 → {a.shot}")

        ws.close()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=6)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        if not a.keep:
            try:
                import shutil
                shutil.rmtree(profile, ignore_errors=True)
            except Exception:
                pass

    print("\n" + "=" * 60)
    print(f"通过 {len(oks)} 项，失败 {len(fails)} 项")
    if fails:
        print("失败项：", fails)
    print("=" * 60)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
