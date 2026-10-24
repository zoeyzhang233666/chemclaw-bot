# -*- coding: utf-8 -*-
"""cdp.py —— 极简 Chrome DevTools Protocol 客户端（仅用标准库，RFC6455 手写）

避免依赖 websocket-client / playwright 的浏览器下载。
"""
import base64, json, os, socket, struct, sys


class WS:
    def __init__(self, url, timeout=30):
        assert url.startswith('ws://')
        rest = url[5:]
        hostport, path = rest.split('/', 1)
        host, port = hostport.split(':')
        self.s = socket.create_connection((host, int(port)), timeout=timeout)
        self.s.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ('GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
               'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (path, hostport, key))
        self.s.sendall(req.encode())
        buf = b''
        while b'\r\n\r\n' not in buf:
            buf += self.s.recv(4096)
        if b'101' not in buf.split(b'\r\n')[0]:
            raise RuntimeError('WebSocket 握手失败：%s' % buf[:200])
        self.buf = buf.split(b'\r\n\r\n', 1)[1]

    def _recv(self, n):
        while len(self.buf) < n:
            d = self.s.recv(65536)
            if not d:
                raise RuntimeError('连接关闭')
            self.buf += d
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text):
        data = text.encode('utf-8')
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126); hdr += struct.pack('>H', n)
        else:
            hdr.append(0x80 | 127); hdr += struct.pack('>Q', n)
        mask = os.urandom(4)
        hdr += mask
        self.s.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        while True:
            b1, b2 = self._recv(2)
            op = b1 & 0x0F
            ln = b2 & 0x7F
            if ln == 126:
                ln = struct.unpack('>H', self._recv(2))[0]
            elif ln == 127:
                ln = struct.unpack('>Q', self._recv(8))[0]
            masked = b2 & 0x80
            mask = self._recv(4) if masked else None
            payload = self._recv(ln)
            if masked:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if op == 0x8:
                raise RuntimeError('websocket closed')
            if op == 0x9:      # ping → pong
                continue
            if op == 0x1:
                return payload.decode('utf-8', 'ignore')


class CDP:
    def __init__(self, ws_url):
        self.ws = WS(ws_url)
        self.i = 0

    def send(self, method, **params):
        self.i += 1
        self.ws.send(json.dumps({'id': self.i, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == self.i:
                if 'error' in msg:
                    raise RuntimeError('%s → %s' % (method, msg['error']))
                return msg.get('result', {})

    def eval(self, expr):
        r = self.send('Runtime.evaluate', expression=expr, returnByValue=True)
        if 'exceptionDetails' in r:
            d = r['exceptionDetails']
            raise RuntimeError(d.get('text', '') + ' ' + str(d.get('exception', {}).get('description', ''))[:200])
        return r.get('result', {}).get('value')
