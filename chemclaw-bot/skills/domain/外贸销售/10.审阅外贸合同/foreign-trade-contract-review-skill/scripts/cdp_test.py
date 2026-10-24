"""Drive Chrome over the DevTools protocol to test the report's interactive behaviour.

No playwright needed: uses the built-in websocket client approach with a tiny
CDP client implemented on http.client + socket framing.
"""
import base64
import json
import os
import struct
import subprocess
import sys
import time
import urllib.request

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9444


def ws_connect(url):
    # url like ws://127.0.0.1:9444/devtools/page/XXXX
    assert url.startswith("ws://")
    rest = url[len("ws://"):]
    hostport, path = rest.split("/", 1)
    host, port = hostport.split(":")
    import socket

    s = socket.create_connection((host, int(port)), timeout=30)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    )
    s.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(4096)
    return s


def send(s, payload):
    data = json.dumps(payload).encode()
    header = bytearray([0x81])
    n = len(data)
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", n)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", n)
    mask = os.urandom(4)
    header += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    s.sendall(bytes(header) + masked)


def recv_frame(s):
    def rd(n):
        out = b""
        while len(out) < n:
            chunk = s.recv(n - len(out))
            if not chunk:
                raise ConnectionError("closed")
            out += chunk
        return out

    b1, b2 = rd(2)
    ln = b2 & 0x7F
    if ln == 126:
        ln = struct.unpack(">H", rd(2))[0]
    elif ln == 127:
        ln = struct.unpack(">Q", rd(8))[0]
    payload = rd(ln)
    return payload


class CDP:
    def __init__(self, url):
        self.s = ws_connect(url)
        self.id = 0

    def call(self, method, params=None, timeout=30):
        self.id += 1
        mid = self.id
        send(self.s, {"id": mid, "method": method, "params": params or {}})
        end = time.time() + timeout
        while time.time() < end:
            raw = recv_frame(self.s)
            msg = json.loads(raw)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})
            if msg.get("method") == "Runtime.exceptionThrown":
                print("!! page exception:", json.dumps(msg["params"])[:400])
        raise TimeoutError(method)

    def eval(self, expr, timeout=30):
        r = self.call(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True},
            timeout=timeout,
        )
        if "exceptionDetails" in r:
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:500])
        return r["result"].get("value")


def main():
    html = os.path.abspath(sys.argv[1])
    profile = os.path.join(os.path.dirname(html), "..", "tmp_cdp")
    proc = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            f"--user-data-dir={os.path.abspath(profile)}",
            f"--remote-debugging-port={PORT}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    target = None
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=2) as r:
                tabs = json.load(r)
            pages = [t for t in tabs if t.get("type") == "page"]
            if pages:
                target = pages[0]
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not target:
        proc.kill()
        sys.exit("could not attach to chrome")

    cdp = CDP(target["webSocketDebuggerUrl"])
    cdp.call("Runtime.enable")
    cdp.call("Log.enable")
    cdp.call("Page.enable")

    url = "file:///" + html.replace("\\", "/")
    cdp.call("Page.navigate", {"url": url})
    time.sleep(3.5)

    results = []

    def check(name, expr, expect=None):
        try:
            v = cdp.eval(expr)
        except Exception as e:
            results.append((name, "ERROR", str(e)[:160]))
            return None
        ok = True
        if expect is not None:
            if callable(expect):
                ok = expect(v)
            else:
                ok = v == expect
        results.append((name, "OK" if ok else "FAIL", repr(v)[:160]))
        return v

    check("title", "document.title")
    check("issue cards", "document.querySelectorAll('.icard').length", 38)
    check("risk markers", "document.querySelectorAll('.risk-marker').length")
    check("has-risk blocks", "document.querySelectorAll('[data-bid].has-risk').length")
    check("category chips", "document.querySelectorAll('[data-cat]').length", 8)
    check("severity chips", "document.querySelectorAll('[data-sev]').length", 4)
    check("status options", "document.querySelectorAll('#statusfilter option').length", 6)
    check("exec wrapper", "document.querySelectorAll('.exec-block').length", 1)
    check("cards hidden by default", "document.querySelectorAll('.icard.open').length", 0)

    # open one card
    cdp.eval("document.querySelector('[data-toggle=\"R-01\"]').click()")
    check("R-01 opened", "document.querySelector('#card-R-01').classList.contains('open')", True)
    check("R-01 has quote", "document.querySelectorAll('#card-R-01 .quote-box').length", 2)
    check("R-01 confirm items", "document.querySelectorAll('#card-R-01 .confirm-list li').length", 4)

    # click a jump button -> should highlight the contract block
    cdp.eval("document.querySelector('#card-R-01 [data-jump]').click()")
    time.sleep(0.7)
    check(
        "jump highlights block",
        "!!document.querySelector('[data-bid=\"p-article-6-payment-059\"]') && document.querySelector('[data-bid=\"p-article-6-payment-059\"]').classList.contains('active-highlight')",
        True,
    )

    # click a risk marker in the contract -> should open the matching card
    cdp.eval(
        "document.querySelector('[data-bid=\"p-article-6-payment-067\"] .risk-marker[data-issue=\"R-02\"]').click()"
    )
    time.sleep(0.6)
    check("marker opens R-02", "document.querySelector('#card-R-02').classList.contains('open')", True)

    # filter by category
    cdp.eval("document.querySelector('[data-cat=\"payment\"]').click()")
    time.sleep(0.3)
    check("payment filter count", "document.querySelectorAll('.icard').length", 5)
    check("count label", "document.getElementById('rp-count').textContent.trim()", "5 / 38 条")

    # severity filter within category
    cdp.eval("document.querySelector('[data-sev=\"high\"]').click()")
    time.sleep(0.3)
    check("payment+high count", "document.querySelectorAll('.icard').length", 3)

    # reset + search
    cdp.eval("document.querySelector('[data-cat=\"__all__\"]').click()")
    cdp.eval("document.querySelector('[data-sev=\"__all__\"]').click()")
    cdp.eval(
        "var s=document.getElementById('search'); s.value='Form E'; s.dispatchEvent(new Event('input'))"
    )
    time.sleep(0.3)
    check("search 'Form E'", "document.querySelectorAll('.icard').length", lambda v: v >= 1)
    cdp.eval(
        "var s=document.getElementById('search'); s.value=''; s.dispatchEvent(new Event('input'))"
    )
    time.sleep(0.2)
    check("search cleared", "document.querySelectorAll('.icard').length", 38)

    # tracking persists to localStorage
    cdp.eval("document.querySelector('[data-toggle=\"R-05\"]').click()")
    cdp.eval(
        "var el=document.querySelector('#card-R-05 [data-f=\"owner\"]'); el.value='ZHANG-WU'; el.dispatchEvent(new Event('input',{bubbles:true}))"
    )
    cdp.eval(
        "var el=document.querySelector('#card-R-05 [data-f=\"status\"]'); el.value='处理中'; el.dispatchEvent(new Event('change'))"
    )
    time.sleep(0.4)
    check(
        "localStorage saved",
        "(function(){var o=JSON.parse(localStorage.getItem('ftc-review:ZJSA-2026-0417-SIM')||'{}'); return o['R-05'] ? o['R-05'].owner : 'NO-RECORD';})()",
        "ZHANG-WU",
    )
    check(
        "status tag updated",
        "document.querySelector('#card-R-05 .icard-meta .tag[class*=st-]').textContent",
        "处理中",
    )

    # status filter picks it up
    cdp.eval(
        "var s=document.getElementById('statusfilter'); s.value='处理中'; s.dispatchEvent(new Event('change'))"
    )
    time.sleep(0.3)
    check("status filter count", "document.querySelectorAll('.icard').length", 1)
    cdp.eval(
        "var s=document.getElementById('statusfilter'); s.value='__all__'; s.dispatchEvent(new Event('change'))"
    )

    # overview
    cdp.eval("document.getElementById('btn-overview').click()")
    time.sleep(0.4)
    check("overview visible", "document.getElementById('view-overview').classList.contains('show')", True)
    check("overview rows", "document.querySelectorAll('#ov-table tbody tr').length", 38)
    check("overview meta filled", "document.getElementById('ov-meta').textContent.includes('重质纯碱')", True)

    # jump from overview back into split view
    cdp.eval("document.querySelector('[data-goto=\"R-20\"]').click()")
    time.sleep(0.8)
    check("overview goto returns to split", "document.getElementById('view-split').style.display", "")
    check("R-20 active", "document.querySelector('#card-R-20').classList.contains('open')", True)

    # layout sanity: two panes side by side, non-zero width
    cdp.eval("document.getElementById('btn-split').click()")
    time.sleep(0.3)
    v = cdp.eval(
        "[document.querySelector('.pane-left').getBoundingClientRect().width,"
        " document.querySelector('.pane-right').getBoundingClientRect().width,"
        " window.innerWidth]"
    )
    print("pane widths (left,right,viewport):", v)
    check(
        "both panes have width",
        "document.querySelector('.pane-left').getBoundingClientRect().width>300 && document.querySelector('.pane-right').getBoundingClientRect().width>300",
        True,
    )
    check(
        "no horizontal overflow of paper",
        "document.querySelector('.paper').getBoundingClientRect().right <= document.querySelector('.pane-left').getBoundingClientRect().right+2",
        True,
    )

    print("\n=== results ===")
    fails = 0
    for name, status, detail in results:
        if status != "OK":
            fails += 1
        print(f"{status:5s} {name:34s} {detail}")
    print(f"\n{len(results)} checks, {fails} failed")

    cdp.call("Browser.close")
    proc.wait(timeout=10)


if __name__ == "__main__":
    main()
