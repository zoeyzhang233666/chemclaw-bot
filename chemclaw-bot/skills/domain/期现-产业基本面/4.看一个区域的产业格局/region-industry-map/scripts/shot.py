#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Chrome DevTools Protocol 截图（比 --screenshot 稳定：后者在本环境会挂住）。

用法:
  python shot.py <html> <out.png> [--w 1600] [--h 2600] [--full]

依赖：只要求 Chrome/Edge + Python 标准库（自带极简 WebSocket 客户端）。
"""
import argparse
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

CHROME_CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
]


def find_browser():
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit('找不到 Chrome/Edge')


class WS:
    """够用的 WebSocket 客户端（只处理 CDP 的文本帧）。"""

    def __init__(self, url):
        # ws://127.0.0.1:PORT/devtools/page/XXX
        assert url.startswith('ws://')
        rest = url[5:]
        hostport, path = rest.split('/', 1)
        host, port = hostport.split(':')
        self.s = socket.create_connection((host, int(port)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ('GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\n'
               'Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n'
               'Sec-WebSocket-Version: 13\r\n\r\n' % (path, hostport, key))
        self.s.sendall(req.encode())
        buf = b''
        while b'\r\n\r\n' not in buf:
            buf += self.s.recv(4096)
        self.buf = buf.split(b'\r\n\r\n', 1)[1]
        self.mid = 0

    def send(self, obj):
        data = json.dumps(obj).encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126)
            hdr += struct.pack('>H', n)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack('>Q', n)
        mask = os.urandom(4)
        hdr += mask
        self.s.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError('closed')
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        while True:
            b0, b1 = self._read(2)
            op = b0 & 0x0f
            ln = b1 & 0x7f
            if ln == 126:
                ln = struct.unpack('>H', self._read(2))[0]
            elif ln == 127:
                ln = struct.unpack('>Q', self._read(8))[0]
            payload = self._read(ln)
            if op == 1:
                return json.loads(payload.decode())
            if op == 8:
                raise ConnectionError('ws closed')

    def call(self, method, **params):
        self.mid += 1
        mid = self.mid
        self.send({'id': mid, 'method': method, 'params': params})
        while True:
            msg = self.recv()
            if msg.get('id') == mid:
                if 'error' in msg:
                    raise RuntimeError('%s -> %s' % (method, msg['error']))
                return msg.get('result', {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html')
    ap.add_argument('png')
    ap.add_argument('--w', type=int, default=1600)
    ap.add_argument('--h', type=int, default=2600)
    ap.add_argument('--full', action='store_true', help='整页截图')
    ap.add_argument('--wait', type=int, default=6000, help='渲染等待毫秒')
    a = ap.parse_args()

    exe = find_browser()
    prof = tempfile.mkdtemp(prefix='shot_')
    port = 9515
    proc = subprocess.Popen(
        [exe, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
         '--allow-file-access-from-files', '--remote-debugging-port=%d' % port,
         '--user-data-dir=' + prof, 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(100):
            try:
                import urllib.request
                with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2) as r:
                    tabs = json.loads(r.read().decode())
                for t in tabs:
                    if t.get('type') == 'page':
                        ws_url = t['webSocketDebuggerUrl']
                        break
                if ws_url:
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not ws_url:
            raise SystemExit('无法连接 DevTools')

        ws = WS(ws_url)
        ws.call('Page.enable')
        ws.call('Emulation.setDeviceMetricsOverride', width=a.w, height=a.h,
                deviceScaleFactor=1, mobile=False)
        url = 'file:///' + os.path.abspath(a.html).replace('\\', '/')
        ws.call('Page.navigate', url=url)
        time.sleep(a.wait / 1000.0)
        params = {'format': 'png'}
        if a.full:
            params['captureBeyondViewport'] = True
            m = ws.call('Page.getLayoutMetrics')
            cs = m.get('cssContentSize') or m.get('contentSize')
            params['clip'] = {'x': 0, 'y': 0, 'width': a.w,
                              'height': min(cs['height'], 20000), 'scale': 1}
        res = ws.call('Page.captureScreenshot', **params)
        data = base64.b64decode(res['data'])
        os.makedirs(os.path.dirname(os.path.abspath(a.png)) or '.', exist_ok=True)
        with open(a.png, 'wb') as f:
            f.write(data)
        print('SHOT →', a.png, '(%.0f KB)' % (len(data) / 1024))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        shutil.rmtree(prof, ignore_errors=True)


if __name__ == '__main__':
    main()
