# -*- coding: utf-8 -*-
"""环评（EIA）公示适配器。

环评公示是**非上市企业**项目线索的主渠道（上市公司有公告，非上市只能靠环评）。
但各地生态环境局站点形态差异极大，本模块提供两种可复用的抓取模式：

  模式 A：静态列表 + 分页（以泉州市生态环境局为代表）
      栏目页 index.html / index_1.html / index_2.html …，链接形如
      `./YYYYMM/tYYYYMMDD_NNNNNNN.htm`，正文是静态 HTML，能直接读到
      「项目名称 / 建设地点 / 建设单位 / 项目概况 / 主要原辅材料」。

  模式 B：自定义列表页（以铜陵市 ASP 平台为代表）
      交给调用方传 selector 正则。

命令行：
  python -m tools.eia quanzhou --col nzchpspyjgk --pages 6
  python -m tools.eia quanzhou --col hpslqkgk --pages 6 --grep 纯碱|硅|玻璃
  python -m tools.eia page <url>
"""
import argparse
import os
import re
import sys
import urllib.parse

_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

from tools import http  # noqa: E402

# 泉州市生态环境局 三个栏目
QUANZHOU_BASE = 'http://sthjj.quanzhou.gov.cn/hjgl/hbsp/%s/'
QUANZHOU_COLS = {
    'hpslqkgk': '受理公示',
    'nzchpspyjgk': '拟审批公示',
    'zchpspjdgk': '审批决定公示',
}
# 铜陵市生态环境局 ASP 平台（安徽口径）
TONGLING_LIST = 'http://218.22.184.155:8231/work_List_Search.aspx?LCJD=1&lcjd1=1'


def list_quanzhou(col='nzchpspyjgk', pages=6, grep=None, timeout=25):
    """模式 A：泉州市局环评列表。返回 [{title, url, date}]。"""
    base = QUANZHOU_BASE % col
    seen, out = set(), []
    for p in range(0, pages):
        url = base + ('index.html' if p == 0 else 'index_%d.html' % p)
        r = http.fetch(url, timeout=timeout, max_bytes=600000)
        html = r['text']
        if not html:
            url = url.replace('.html', '.htm')
            r = http.fetch(url, timeout=timeout, max_bytes=600000)
            html = r['text']
        if not html:
            continue
        for m in re.finditer(r'(?is)<a[^>]+href="([^"]*t\d{8}_\d+\.htm)"[^>]*>(.*?)</a>', html):
            href, inner = m.group(1), m.group(2)
            title = http.strip_tags(inner)
            if len(title) < 5:
                continue
            full = urllib.parse.urljoin(url, href)
            if full in seen:
                continue
            seen.add(full)
            dm = re.search(r'/t(\d{4})(\d{2})(\d{2})_', full)
            date = '%s-%s-%s' % dm.groups() if dm else ''
            if grep and not re.search(grep, title):
                continue
            out.append({'title': title, 'url': full, 'date': date})
    return out


def list_tongling(grep=None, timeout=25):
    """模式 B：铜陵市局 ASP 列表。链接与标题形态随站点而变，这里做通用提取。"""
    r = http.fetch(TONGLING_LIST, timeout=timeout, max_bytes=800000)
    html = r['text'] or ''
    out = []
    for m in re.finditer(r'(?is)<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html):
        href, inner = m.group(1), m.group(2)
        title = http.strip_tags(inner)
        if len(title) < 6 or 'Show' not in href and 'show' not in href:
            continue
        full = urllib.parse.urljoin(TONGLING_LIST, href)
        if grep and not re.search(grep, title):
            continue
        out.append({'title': title, 'url': full, 'date': ''})
    return out


def read_page(url, timeout=25, keywords=None):
    """读一个环评详情页，返回 {url, title, text, hits}。

    hits 是关键词命中数——**用来做"正文闸门"**：只有正文里真的出现本产品名/学名，
    才认为该产品进入其工序，否则不要收录。
    """
    r = http.fetch(url, timeout=timeout, max_bytes=800000)
    html = r['text'] or ''
    text = http.strip_tags(html)
    hits = {}
    for k in (keywords or []):
        hits[k] = len(re.findall(re.escape(k), text))
    return {'url': url, 'title': http.page_title(html), 'text': text, 'hits': hits,
            'len': len(text)}


def main():
    ap = argparse.ArgumentParser(description='环评公示抓取')
    sub = ap.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('quanzhou')
    q.add_argument('--col', default='nzchpspyjgk', choices=list(QUANZHOU_COLS))
    q.add_argument('--pages', type=int, default=6)
    q.add_argument('--grep', default=None)
    t = sub.add_parser('tongling')
    t.add_argument('--grep', default=None)
    p = sub.add_parser('page')
    p.add_argument('url')
    p.add_argument('--keywords', default='', help='逗号分隔，做正文闸门')
    st = sub.add_parser('selftest', help='可解析性实测：逐个 EIA 通道报告能抽出多少条项目')
    st.add_argument('--pages', type=int, default=1)
    a = ap.parse_args()
    if a.cmd == 'selftest':
        print('EIA 通道可解析性实测（probe 只证明"可达"，这里证明"能拿到条目"）\n')
        for col, label in QUANZHOU_COLS.items():
            try:
                rows = list_quanzhou(col, pages=a.pages)
                print('  %-44s %-18s %d 条' % ('泉州市局 · ' + label,
                                               '可解析' if rows else '可达但抽不到条目', len(rows)))
                for r in rows[:2]:
                    print('        e.g. %s %s' % (r['date'], r['title'][:58]))
            except Exception as e:
                print('  %-44s 抓取失败 %s' % ('泉州市局 · ' + label, e))
        try:
            rows = list_tongling()
            print('  %-44s %-18s %d 条' % ('铜陵市局 · ASP 平台',
                                           '可解析' if rows else '可达但抽不到条目', len(rows)))
            for r in rows[:2]:
                print('        e.g. %s' % r['title'][:58])
        except Exception as e:
            print('  %-44s 抓取失败 %s' % ('铜陵市局 · ASP 平台', e))
        print('\n其余省/市级站点未注册适配器：它们即使 status=可达，也可能是 JS 渲染的列表页')
        print('（HTML 里有大量导航文字，但项目清单由前端注入，抓不到条目——用长度或关键词')
        print('都判别不出来，只能跑适配器）。')
        print('要新增站点，照 list_quanzhou 的模式写一个函数，并登记进 channels.default.json。')
        return
    if a.cmd == 'quanzhou':
        rows = list_quanzhou(a.col, pages=a.pages, grep=a.grep)
        for r in rows:
            print('%s | %s | %s' % (r['date'], r['title'], r['url']))
        print('共 %d 条（栏目 %s = %s）' % (len(rows), a.col, QUANZHOU_COLS[a.col]))
    elif a.cmd == 'tongling':
        rows = list_tongling(grep=a.grep)
        for r in rows:
            print('%s | %s' % (r['title'], r['url']))
        print('共 %d 条' % len(rows))
    else:
        kws = [x.strip() for x in a.keywords.split(',') if x.strip()]
        info = read_page(a.url, keywords=kws)
        print('TITLE:', info['title'])
        print('LEN  :', info['len'])
        for k, v in info['hits'].items():
            print('  %s -> %d 次' % (k, v))
        print('---- 正文前 1500 字 ----')
        print(info['text'][:1500])


if __name__ == '__main__':
    main()