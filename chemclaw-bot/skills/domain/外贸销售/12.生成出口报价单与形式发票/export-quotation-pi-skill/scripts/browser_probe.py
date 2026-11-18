#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Headless Chrome harness: optionally run JS in a page, capture screenshots.

Uses the installed Chrome in --headless=new mode over the DevTools protocol via
Node's built-in WebSocket (no third-party packages).

Usage:
  python scripts/browser_probe.py --html build/x.html --shot out.png --wait 1500
  python scripts/browser_probe.py --html x.html --eval-file probe.js --shot out.png
"""
import argparse, base64, json, os, shutil, subprocess, sys, tempfile, time

NODE_CANDIDATES = [
    os.environ.get("QUOTE_NODE"),
    (__import__('shutil').which('node') or 'node'),
    "node",
]
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    shutil.which("chrome") or "",
    shutil.which("msedge") or "",
]

CDP = r"""
const fs = require('fs');
const args = JSON.parse(process.argv[2]);
(async () => {
  const targets = await (await fetch('http://127.0.0.1:' + args.port + '/json')).json();
  const page = targets.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map(); const logs = [];
  const send = (method, params) => new Promise((res, rej) => { const i = ++id; pending.set(i, {res, rej}); ws.send(JSON.stringify({id: i, method, params: params || {}})); });
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); }
    else if (m.method === 'Runtime.consoleAPICalled') logs.push({type: m.params.type, text: m.params.args.map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ')});
    else if (m.method === 'Runtime.exceptionThrown') logs.push({type: 'exception', text: (m.params.exceptionDetails.exception && m.params.exceptionDetails.exception.description) || m.params.exceptionDetails.text});
    else if (m.method === 'Log.entryAdded') logs.push({type: 'log-' + m.params.entry.level, text: m.params.entry.text});
  };
  await new Promise(r => ws.onopen = r);
  await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', {width: args.w, height: args.h, deviceScaleFactor: args.scale || 1, mobile: false});
  await send('Page.navigate', {url: args.url});
  await new Promise(r => setTimeout(r, args.wait || 1500));
  let evalResult = null;
  if (args.evalFile) {
    const r = await send('Runtime.evaluate', {expression: fs.readFileSync(args.evalFile, 'utf8'), awaitPromise: true, returnByValue: true});
    evalResult = r.result ? r.result.value : null;
    if (r.exceptionDetails) evalResult = {error: r.exceptionDetails.text};
    await new Promise(r => setTimeout(r, args.afterEvalWait || 500));
  }
  if (args.shot) {
    const metrics = await send('Page.getLayoutMetrics');
    const full = args.full ? {x: 0, y: 0, width: Math.min(2400, metrics.cssContentSize.width), height: Math.min(9000, metrics.cssContentSize.height), scale: 1}
                           : {x: 0, y: 0, width: args.w, height: args.h, scale: 1};
    const shot = await send('Page.captureScreenshot', {format: 'png', captureBeyondViewport: !!args.full, clip: full});
    fs.writeFileSync(args.shot, Buffer.from(shot.data, 'base64'));
  }
  console.log(JSON.stringify({logs, evalResult}, null, 1));
  ws.close(); process.exit(0);
})().catch(e => { console.error('CDP ERR', e); process.exit(2); });
"""


def first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--shot", default="")
    ap.add_argument("--eval-file", default="")
    ap.add_argument("--wait", type=int, default=1800)
    ap.add_argument("--w", type=int, default=1600)
    ap.add_argument("--h", type=int, default=1100)
    ap.add_argument("--scale", type=float, default=1)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--port", type=int, default=9333)
    ap.add_argument("--hash", default="", help="append '#<hash>' to the file URL")
    a = ap.parse_args()

    node = first_existing(NODE_CANDIDATES) or "node"
    chrome = first_existing(CHROME_CANDIDATES)
    if not chrome:
        sys.exit("no Chrome/Edge found")
    tmp = tempfile.mkdtemp(prefix="cdp-")
    cdp_js = os.path.join(tmp, "cdp.js")
    with open(cdp_js, "w", encoding="utf-8") as f:
        f.write(CDP)
    url = "file:///" + os.path.abspath(a.html).replace("\\", "/")
    if a.hash:
        url += "#" + a.hash
    proc = subprocess.Popen([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                             "--no-first-run", "--no-default-browser-check",
                             "--remote-debugging-port=%d" % a.port, "--user-data-dir=" + os.path.join(tmp, "profile"),
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # wait for devtools
        import urllib.request
        for _ in range(80):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/json/version" % a.port, timeout=0.5)
                break
            except Exception:
                time.sleep(0.15)
        payload = {"port": a.port, "url": url, "shot": os.path.abspath(a.shot) if a.shot else "", "wait": a.wait,
                   "w": a.w, "h": a.h, "scale": a.scale, "full": a.full,
                   "evalFile": os.path.abspath(a.eval_file) if a.eval_file else ""}
        r = subprocess.run([node, cdp_js, json.dumps(payload)], capture_output=True, text=True, encoding="utf-8", timeout=180)
        sys.stdout.write(r.stdout or "")
        sys.stderr.write(r.stderr or "")
        return r.returncode
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
