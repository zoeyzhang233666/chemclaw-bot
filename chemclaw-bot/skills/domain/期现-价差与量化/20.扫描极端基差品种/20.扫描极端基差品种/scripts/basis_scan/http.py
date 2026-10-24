# -*- coding: utf-8 -*-
"""http.py — 带「安全检查 cookie」重试 + 磁盘缓存的 HTTP 抓取层

100ppi 家族站点（www / me / futures.100ppi.com）偶尔返回一页 JS 挑战：
    <script>var _0x2 = "<32位hex>"; document.cookie = "HW_CHECK=" + _0x2 ...</script>
处理方式：解析该值，作为 Cookie: HW_CHECK=<值> 重发即可；本模块自动完成并在
进程内记住该 cookie。所有页面落盘到 cache 目录，断点续抓、可复现。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')

_HW = {'cookie': None}
_CHALLENGE = re.compile(r'var\s+_0x2\s*=\s*"([0-9a-f]{16,64})"')


class Http:
    def __init__(self, cache_dir: str | None = None, sleep: float = 0.45,
                 min_sleep: float = 0.25, retries: int = 6, verbose: bool = True):
        self.cache_dir = cache_dir
        self.sleep = sleep
        self.min_sleep = min_sleep
        self.retries = retries
        self.verbose = verbose
        self._last = 0.0
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    # ------------------------------------------------------------------ cache
    def _cache_path(self, url: str) -> str | None:
        if not self.cache_dir:
            return None
        h = hashlib.sha1(url.encode('utf-8')).hexdigest()[:20]
        return os.path.join(self.cache_dir, h + '.txt')

    def _cache_read(self, url: str):
        p = self._cache_path(url)
        if p and os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                return f.read()
        return None

    def _cache_write(self, url: str, text: str) -> None:
        p = self._cache_path(url)
        if p:
            with open(p, 'w', encoding='utf-8') as f:
                f.write(text)

    # ---------------------------------------------------------------- request
    def _throttle(self):
        dt = time.time() - self._last
        if dt < self.sleep:
            time.sleep(self.sleep - dt)
        self._last = time.time()

    def get(self, url: str, referer: str | None = None, use_cache: bool = True,
            force: bool = False) -> str | None:
        if use_cache and not force:
            c = self._cache_read(url)
            if c is not None:
                return c
        last = None
        for i in range(self.retries):
            self._throttle()
            headers = {'User-Agent': UA,
                       'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
                       'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.5'}
            if referer:
                headers['Referer'] = referer
            if _HW['cookie']:
                headers['Cookie'] = 'HW_CHECK=' + _HW['cookie']
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as r:
                    raw = r.read()
                text = raw.decode('utf-8', 'ignore')
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (404, 403, 410):
                    # 404/403 属于确定性结果：不缓存，直接返回 None
                    if self.verbose:
                        print('  [http %s] %s' % (e.code, url), flush=True)
                    return None
                time.sleep(1.0 + i)
                continue
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(0.8 + i * 0.6)
                continue
            m = _CHALLENGE.search(text)
            if m:
                _HW['cookie'] = m.group(1)
                time.sleep(0.5 + 0.2 * i)
                continue
            if not text.strip():
                time.sleep(0.8)
                continue
            self._cache_write(url, text)
            return text
        if self.verbose:
            print('  [http FAIL] %r %s' % (last, url), flush=True)
        return None

    # ------------------------------------------------------------- jsonp api
    def jsonp(self, url: str, use_cache: bool = True, force: bool = False):
        """解析 `var t=([...]);` 形式的 jsonp 返回为 Python 对象。"""
        text = self.get(url, use_cache=use_cache, force=force)
        if not text:
            return None
        m = re.search(r'=\s*\((.*)\)\s*;?\s*$', text, re.S)
        body = (m.group(1) if m else text).strip()
        if body in ('', 'null', '[]'):
            return []
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None


def challenge_cookie() -> str | None:
    return _HW['cookie']
