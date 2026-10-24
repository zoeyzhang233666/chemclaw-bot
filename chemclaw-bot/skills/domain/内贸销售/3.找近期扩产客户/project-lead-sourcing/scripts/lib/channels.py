# -*- coding: utf-8 -*-
"""通道探测（方法论第 2 步「探通道」）。

把"本机到底能连上哪些数据源"变成**记录在案的事实**，而不是靠猜：
  b2bctl probe  →  逐条实测 channels.default.json（或自定义注册表），写 channels.json

换电脑、换网络、换国家时**第一步就跑 probe**，后续所有 lane 只使用被证实可用的通道。
"""
import json
import os
import sys

_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

from tools import http  # noqa: E402


def load_registry(path=None):
    if not path:
        path = os.path.join(_SKILL_ROOT, 'channels.default.json')
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


def _probe_post(spec, timeout):
    """巨潮 POST 接口需要特定头才会返回数据，这里单独探测。"""
    url = spec['url']
    body = ('pageNum=1&pageSize=30&column=szse&tabName=fulltext&plate=&stock='
            '&searchkey=%E5%85%AC%E5%91%8A&secid=&category=&trade='
            '&seDate=&sortName=&sortType=&isHLtitle=true').encode()
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': 'http://www.cninfo.com.cn/new/fulltextSearch?notautosubmit=&keyWord=',
        'X-Requested-With': 'XMLHttpRequest',
    }
    r = http.fetch(url, method='POST', data=body, headers=headers, timeout=timeout)
    ok = r['ok'] and (r['text'] or '') and 'announcements' in (r['text'] or '')
    return r, ok, len(r['text'] or '')


def probe(cfg=None, root='.', registry_path=None, timeout=20, out_path=None, log=True):
    """实测所有通道，返回结果 dict 并写 channels.json。"""
    reg = load_registry(registry_path)
    out = {'probed_at': None, 'timeout': timeout, 'channels': [], 'host_tools': reg.get('host_tools', [])}

    import datetime
    out['probed_at'] = datetime.datetime.now().isoformat(timespec='seconds')

    for spec in reg.get('channels', []):
        p = spec.get('probe') or {}
        method = (p.get('method') or 'GET').upper()
        min_len = int(p.get('min_len') or 0)
        contains = p.get('contains')

        if method == 'PROBE_POST':
            r, ok, length = _probe_post(spec, timeout)
        else:
            r = http.fetch(spec['url'], method='GET', timeout=timeout, max_bytes=400000)
            length = len(r['text'] or r['body'] or b'')
            ok = bool(r['ok']) and length >= min_len
            if ok and contains and contains not in (r['text'] or ''):
                ok = False
                r['note'] = 'not_target_page'

        if ok:
            status = '可达'
        elif r['status'] in (301, 302, 303, 307, 308):
            status = '不可达-跳转HTTPS(本机不可达)' if str(r.get('final_url', '')).startswith('https') \
                else '不可达-跳转'
        elif r['status'] in (403, 406, 412, 429):
            status = '不可达-反爬拦截'
        elif r['status'] == 'ERR':
            status = '不可达-连接失败'
        elif r['ok'] and length < min_len:
            status = '不可达-疑似JS渲染/空壳(len=%d)' % length
        elif r.get('note') == 'not_target_page':
            status = '不可达-不是目标页'
        else:
            status = '不可达-HTTP %s' % r['status']

        row = {
            'id': spec.get('id'), 'name': spec.get('name'), 'kind': spec.get('kind'),
            'status': status, 'http_status': r['status'], 'len': length,
            'url': spec['url'], 'note': spec.get('note', ''),
            'adapter': spec.get('adapter'), 'error': r.get('error'),
            'final_url': r.get('final_url'),
            # probe 只证明"这个 URL 能拿到内容"。**可达 ≠ 能解析出项目条目**：
            # JS 渲染的列表页可达、正文也不短，但项目清单是前端注入的，抓不到条目。
            # 只有"列表页"型通道需要再做可解析性实测；结构化 API（公告 JSON）返回的就是数据，
            # 命中 contains 已足以证明可解析，不必再测。
            'parse_verified': False,
            'needs_adapter_test': spec.get('kind') in ('环评', '备案', '招标'),
        }
        out['channels'].append(row)
        if log:
            print('  %-34s %-6s len=%-8s %s' % (status, r['status'], length, spec.get('name')))

    reachable = [c for c in out['channels'] if c['status'] == '可达']
    out['reachable_count'] = len(reachable)
    out['reachable_ids'] = [c['id'] for c in reachable]
    out['usable_count'] = len(reachable)          # 向后兼容旧字段名
    out['usable_ids'] = [c['id'] for c in reachable]
    pending = [c['id'] for c in reachable if c.get('needs_adapter_test')]
    out['needs_adapter_test'] = pending
    out['_semantics'] = ('status=可达 仅表示该 URL 能取到内容，不代表能解析出项目条目。'
                         'needs_adapter_test 里的通道要用对应适配器实测一次（见 references/channels.md）。')

    if out_path is None and cfg is not None:
        out_path = os.path.join(root, cfg['paths']['channels'])
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        if log:
            print('\n可达通道 %d / %d，已写入 %s' % (len(reachable), len(out['channels']), out_path))
            if out.get('needs_adapter_test'):
                print('注意：status=可达 只说明 URL 能取到内容，**不代表能解析出项目条目**。')
                print('      下列通道属列表型，须用适配器实测可解析性：%s'
                      % '、'.join(out['needs_adapter_test']))
                print('      例： python -m tools.eia selftest')
    return out


def summarize(channels_path):
    """读 channels.json，给报告用。"""
    if not os.path.exists(channels_path):
        return None
    try:
        with open(channels_path, encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return None


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    root = os.path.abspath(argv[0]) if argv else '.'
    cfgp = os.path.join(root, 'config.json')
    if os.path.exists(cfgp):
        from lib import common as C
        cfg, root = C.load_config(cfgp)
    else:
        cfg = None
    probe(cfg, root)


if __name__ == '__main__':
    main()