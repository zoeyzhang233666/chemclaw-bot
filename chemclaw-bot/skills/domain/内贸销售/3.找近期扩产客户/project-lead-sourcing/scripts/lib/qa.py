# -*- coding: utf-8 -*-
"""链接抽检闸门（链接 QA）。

对线索里的 `来源` URL 抽样实测可达性，产出 `_qa_report.json`。
纯标准库实现（urllib + threading），不依赖 PowerShell，换电脑/换 agent 都能跑。

判定口径：
  可达(PDF)                   PDF 返回 200（只验可达，不解析内容）
  可达且主体一致               HTML 200 且正文/标题里能找到公司名关键词
  可达但正文未含主体名           HTML 200 但没匹配上（可能是编码、壳页或跳转），建议人工复核
  坏链-仅HTTPS(本环境不可达)    301/302 跳 https —— 本沙箱只放行明文 http
  反爬拦截-建议人工复核         403/406/412/429
  坏链-404                    404/410
  抓取失败:<原因>              超时、DNS、连接被重置等
"""
import json
import os
import re
import ssl
import sys
import threading
import urllib.error
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124 Safari/537.36')

# 聚合型公告站：优先抽检非它来源，样本更多样
AGGREGATOR_HINTS = ('cninfo.com.cn',)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """不让 urllib 自动跟随跳转，这样才能识别"跳 https 导致不可达"。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _opener():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ctx))


def _company_key(name):
    return re.sub(r'(股份有限公司|有限责任公司|有限公司|集团|股份|公司)', '', name or '')


def _classify(url, rec, timeout):
    """抓一条 URL 并给出判定。返回 dict。"""
    out = {'url': url, 'company': rec.get('公司', ''), 'status': '', 'verdict': '', 'title': ''}
    is_pdf = url.lower().endswith('.pdf')
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'})
    if is_pdf:
        req.get_method = lambda: 'HEAD'
    try:
        with _opener().open(req, timeout=timeout) as r:
            out['status'] = str(getattr(r, 'status', 200) or 200)
            if is_pdf:
                out['verdict'] = '可达(PDF)'
                return out
            raw = r.read(400000)
            charset = r.headers.get_content_charset()
            for enc in ([charset] if charset else []) + ['utf-8', 'gb18030', 'latin-1']:
                if not enc:
                    continue
                try:
                    html = raw.decode(enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                html = raw.decode('utf-8', 'replace')
            m = re.search(r'(?is)<title[^>]*>(.*?)</title>', html)
            out['title'] = re.sub(r'\s+', ' ', m.group(1)).strip()[:120] if m else ''
            key = _company_key(rec.get('公司', ''))
            if key and (key in html or key in out['title']):
                out['verdict'] = '可达且主体一致'
            else:
                out['verdict'] = '可达但正文未含主体名'
            return out
    except urllib.error.HTTPError as e:
        out['status'] = str(e.code)
        if e.code in (301, 302, 303, 307, 308):
            loc = e.headers.get('Location', '') or ''
            out['verdict'] = ('跳转-需人工复核' if loc.startswith('http://')
                              else '坏链-仅HTTPS(本环境不可达)')
            out['title'] = loc[:120]
        elif e.code in (403, 406, 412, 429):
            out['verdict'] = '反爬拦截-建议人工复核'
        elif e.code in (404, 410):
            out['verdict'] = '坏链-404'
        else:
            out['verdict'] = 'HTTP-%d' % e.code
        return out
    except Exception as e:
        out['verdict'] = '抓取失败:%s' % type(e).__name__
        return out


def sample_and_check(cfg, leads, out_path, timeout=25, workers=8, log=True):
    """抽样并实测。返回报告 dict 并写入 out_path。"""
    qa_cfg = cfg.get('qa', {})
    min_sample = int(qa_cfg.get('min_sample', 40))
    max_total = int(qa_cfg.get('max_total', 70))

    by_url = {}
    for r in leads:
        u = (r.get('来源') or '').strip()
        if u and u != '未核实' and u.lower().startswith(('http://', 'https://')):
            by_url.setdefault(u, r)

    agg, other = [], []
    for u in by_url:
        (agg if any(h in u for h in AGGREGATOR_HINTS) else other).append(u)

    # 优先非聚合站（样本更多样），不足再用聚合站补足，总数不超过 max_total
    sample = other + agg
    if len(sample) > max_total:
        sample = other[:max_total]
        if len(sample) < max_total:
            sample += agg[:max_total - len(sample)]
    sample = sample[:max(max_total, min_sample)]

    if log:
        print('唯一来源 %d 个（聚合站 %d / 其它 %d），共抽检 %d 条'
              % (len(by_url), len(agg), len(other), len(sample)))

    results, lock = [], threading.Lock()
    queue = list(sample)

    def worker():
        while True:
            with lock:
                if not queue:
                    return
                u = queue.pop(0)
            res = _classify(u, by_url[u], timeout)
            with lock:
                results.append(res)

    threads = [threading.Thread(target=worker, daemon=True)
               for _ in range(max(1, min(workers, len(queue) or 1)))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    order = {u: i for i, u in enumerate(sample)}
    results.sort(key=lambda r: order.get(r['url'], 999))

    tally = {}
    for r in results:
        tally[r['verdict']] = tally.get(r['verdict'], 0) + 1
    broken = [r for r in results if r['verdict'].startswith('坏链')
              or r['verdict'].startswith('抓取失败')]

    report = {
        'unique_sources': len(by_url),
        'sampled': len(results),
        'aggregator_sources': len(agg),
        'other_sources': len(other),
        'tally': tally,
        'broken_count': len(broken),
        'results': results,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    if log:
        for r in results:
            print('  %-28s %-40s %s' % (r['verdict'], (r['status'] or '-'), r['url'][:90]))
        print('\n抽检结论汇总：%s' % tally)
        if broken:
            print('坏链/失败 %d 条：' % len(broken))
            for r in broken:
                print('   %s  %s' % (r['verdict'], r['url']))
        print('已写入 %s' % out_path)
    return report


def main(argv=None):
    """独立运行：python -m lib.qa <project_dir>"""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if here not in sys.path:
        sys.path.insert(0, here)
    from lib import common as C
    argv = argv or sys.argv[1:]
    root = os.path.abspath(argv[0]) if argv else '.'
    cfg, root = C.load_config(os.path.join(root, 'config.json'))
    with open(os.path.join(root, cfg['paths']['leads']), encoding='utf-8-sig') as f:
        leads = json.load(f)
    out = os.path.join(root, cfg['paths']['qa_report'])
    sample_and_check(cfg, leads, out)


if __name__ == '__main__':
    main()