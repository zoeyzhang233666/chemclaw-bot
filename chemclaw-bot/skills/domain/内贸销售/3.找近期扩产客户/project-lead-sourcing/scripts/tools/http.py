# -*- coding: utf-8 -*-
"""极简 HTTP 工具（纯标准库）。所有通道适配器都走这里，方便统一超时与编码处理。

注意：本模块**不跟随跳转**，因为要识别"301 跳 https 导致本机不可达"这种情况。
需要跟随时显式传 allow_redirects=True。
"""
import gzip
import io
import re
import ssl
import urllib.error
import urllib.request
import zlib

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124 Safari/537.36')

DEFAULT_HEADERS = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/json,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _opener(allow_redirects=False):
    handlers = [urllib.request.HTTPSHandler(context=_ssl_ctx())]
    if not allow_redirects:
        handlers.insert(0, _NoRedirect)
    return urllib.request.build_opener(*handlers)


def _decompress(raw, encoding):
    enc = (encoding or '').lower()
    try:
        if 'gzip' in enc:
            return gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        if 'deflate' in enc:
            try:
                return zlib.decompress(raw)
            except zlib.error:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
    except Exception:
        return raw
    return raw


def fetch(url, method='GET', data=None, headers=None, timeout=25,
          allow_redirects=False, max_bytes=None, charset=None):
    """抓一个 URL。返回 dict：

    {ok, status, body(bytes|None), text(str|None), headers, final_url, error, note}
    - status 可能是 int 或 'ERR'
    - 3xx 不跟随跳转时，final_url 里放 Location，便于判断"跳 https"
    """
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    out = {'ok': False, 'status': None, 'body': None, 'text': None,
           'headers': {}, 'final_url': url, 'error': None, 'note': ''}
    try:
        with _opener(allow_redirects).open(req, timeout=timeout) as r:
            out['status'] = getattr(r, 'status', 200)
            out['final_url'] = r.geturl()
            raw = r.read() if max_bytes is None else r.read(max_bytes)
            out['headers'] = dict(r.headers)
            raw = _decompress(raw, r.headers.get('Content-Encoding'))
            out['body'] = raw
            ct = (r.headers.get('Content-Type') or '').lower()
            if 'text' in ct or 'json' in ct or 'xml' in ct or 'html' in ct:
                out['text'] = decode(raw, charset or r.headers.get_content_charset())
            out['ok'] = True
    except urllib.error.HTTPError as e:
        out['status'] = e.code
        loc = e.headers.get('Location') if e.headers else None
        if loc:
            out['final_url'] = loc
        if e.code in (301, 302, 303, 307, 308):
            out['note'] = 'redirect->https' if str(loc or '').startswith('https') else 'redirect'
        out['error'] = 'HTTP %s' % e.code
    except Exception as e:
        out['status'] = 'ERR'
        out['error'] = '%s: %s' % (type(e).__name__, e)
    return out


def decode(raw, charset=None):
    """按 charset → utf-8 → gb18030 → latin-1 依次尝试解码。"""
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    cands = [charset] if charset else []
    cands += ['utf-8', 'gb18030', 'big5', 'latin-1']
    seen = set()
    for enc in cands:
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode('utf-8', 'replace')


def strip_tags(html, keep_title=False):
    """粗暴去标签；够用即可。"""
    if not html:
        return ''
    t = re.sub(r'(?is)<script.*?</script>', ' ', html)
    t = re.sub(r'(?is)<style.*?</style>', ' ', t)
    t = re.sub(r'(?s)<[^>]+>', ' ', t)
    t = t.replace('&nbsp;', ' ').replace('&ensp;', ' ').replace('&emsp;', ' ')
    t = re.sub(r'&[a-zA-Z#0-9]{2,8};', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def page_title(html):
    if not html:
        return ''
    m = re.search(r'(?is)<title[^>]*>(.*?)</title>', html)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''


def get_text(url, **kw):
    r = fetch(url, **kw)
    if r['text'] is None and r['body'] is not None:
        r['text'] = decode(r['body'])
    return r