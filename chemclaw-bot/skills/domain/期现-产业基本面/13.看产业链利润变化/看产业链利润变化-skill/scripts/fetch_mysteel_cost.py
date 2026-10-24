# -*- coding: utf-8 -*-
"""抓取【隆众资讯/我的钢铁网】"中国PVC电石法企业生产成本周数据分析" 系列，
提取 全国/西北/山东 的周度成本与毛利，形成可复核的第三方口径基准。

口径（文章原文说明）：
  生产成本 = 外采电石PVC企业每生产1吨PVC的 原材料+助剂+设备折旧+人工水电 合计
  样本 = 国内60家PVC生产企业及厂区，覆盖率81%；工作日每周五15:00前发布
  => 这是"含制造成本"的口径，可用于校验“理论制造利润”的量级，但它仍不是企业净利润。
"""
import os
import re
import json
import gzip
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(os.path.dirname(HERE), 'raw')
os.makedirs(RAW, exist_ok=True)
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
LIST_URLS = [
    'https://www.mysteel.com/oilchem/article/3yb4pa/',
    'https://www.mysteel.com/oilchem/article/3yb4pa/2.html?keyWord=',
    'https://www.mysteel.com/oilchem/article/3yb4pa/3.html?keyWord=',
    'https://www.mysteel.com/oilchem/article/3yb4pa/4.html?keyWord=',
    'https://www.mysteel.com/oilchem/article/3yb4pa/index.html',
]


UAS = [
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
     '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
     '(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0'),
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
     '(KHTML, like Gecko) Version/17.4 Safari/605.1.15'),
]
UA = UAS[0]


def get(url, tries=5):
    """带退避的重试；被反爬拦截（页面过短）也视为失败。"""
    for i in range(tries):
        ua = UAS[i % len(UAS)]
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                url, headers={'User-Agent': ua, 'Accept-Encoding': 'gzip',
                              'Accept': 'text/html,application/xhtml+xml',
                              'Accept-Language': 'zh-CN,zh;q=0.9',
                              'Referer': 'https://www.mysteel.com/'}), timeout=30)
            b = r.read()
            if r.headers.get('Content-Encoding') == 'gzip':
                try:
                    b = gzip.decompress(b)
                except Exception:
                    pass
            t = b.decode('utf-8', 'replace')
            if len(t) > 20000:
                return t
        except Exception:
            pass
        time.sleep(3 + 4 * i)
    raise RuntimeError('fetch blocked: ' + url)


def parse_article(html):
    txt = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', html)
    txt = re.sub(r'(?s)<[^>]+>', ' ', txt)
    txt = re.sub(r'&nbsp;', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    out = {'raw_len': len(txt)}

    def num(pat):
        m = re.search(pat, txt)
        return float(m.group(1)) if m else None

    out['date_cut'] = None
    m = re.search(r'截至(20\d\d年\d\d月\d\d日)', txt)
    if m:
        out['date_cut'] = m.group(1).replace('年', '-').replace('月', '-').replace('日', '')
    # 全国成本：优先“成本在/成本环比…在 N元/吨”，退化为 N元/吨 出现在环比重提及处
    out['cost_nat'] = num(r'成本[^。]{0,40}?(?:在|为|至)\s*([0-9]{4}(?:\.[0-9]+)?)元/吨')
    if out['cost_nat'] is None:
        out['cost_nat'] = num(r'全国电石法PVC[^。]{0,60}?([0-9]{4}(?:\.[0-9]+)?)元/吨')
    out['cost_nat_chg_pct'] = num(r'环比(?:上期|上周|上周同期)?[^。]{0,10}?([-+−]?[0-9.]+)%')
    # 区域成本
    out['cost_nw'] = num(r'西北地区周均[^。]{0,24}?([0-9]{4}(?:\.[0-9]+)?)元/吨')
    out['cost_sd'] = num(r'山东地区(?:外采电石)?周均[^。]{0,30}?([0-9]{4}(?:\.[0-9]+)?)元/吨')
    # 利润（先区域，再全国，避免“利润-472”被环比重述捕获）
    out['profit_nw'] = num(r'西北地区周均毛利在\s*([-−]?[0-9]{1,4}(?:\.[0-9]+)?)元/吨')
    out['profit_sd'] = num(r'山东地区外采电石周均毛利在\s*([-−]?[0-9]{1,4}(?:\.[0-9]+)?)元/吨')
    out['profit_nat'] = num(r'全国电石法PVC企业周均(?:利润|毛利)\s*([-−]?[0-9]{1,4}(?:\.[0-9]+)?)元/吨')
    if out['profit_nat'] is None:
        out['profit_nat'] = num(r'全国电石法PVC[^。]{0,24}?(?:平均)?(?:利润|毛利)[^。]{0,12}?([-−]?[0-9]{1,4}(?:\.[0-9]+)?)元/吨')
    out['profit_chg'] = num(r'利润环比[^。]{0,14}?([-−]?[0-9.]+)元/吨')
    return out


def collect(extra=None):
    links = {}
    for u in LIST_URLS:
        try:
            t = get(u)
        except Exception as e:
            print('  [LIST FAIL]', u, repr(e)[:80])
            continue
        n0 = len(links)
        for m in re.finditer(r'href="([^"]*oilchem/a/(\d+)/[0-9A-F]+\.html)"[^>]*>([^<]{0,90})', t):
            href, a, nm = m.group(1), m.group(2), m.group(3)
            d = re.search(r'（(\d{8})）', nm)
            if d and ('电石法企业生产成本' in nm):
                key = d.group(1)
                if not href.startswith('http'):
                    href = 'https://www.mysteel.com' + href
                links[key] = href
        print('  [LIST] %s +%d' % (u[-32:], len(links) - n0))
        time.sleep(1.2)
    for d, h in (extra or {}).items():
        links.setdefault(d, h)
    print('found %d weekly cost articles' % len(links))
    rows = []
    for d in sorted(links):
        try:
            html = get(links[d])
            with open(os.path.join(RAW, 'mysteel_art_%s.html' % d), 'w', encoding='utf-8') as f:
                f.write(html)
            info = parse_article(html)
        except Exception as e:
            print('  [FAIL]', d, repr(e)[:80])
            continue
        info['article_date'] = d
        info['url'] = links[d]
        rows.append(info)
        print('  %s cost_nat=%s nw=%s sd=%s profit=%s nw=%s' % (
            d, info['cost_nat'], info['cost_nw'], info['cost_sd'],
            info['profit_nat'], info['profit_nw']))
        time.sleep(0.4)
    json.dump(rows, open(os.path.join(RAW, 'mysteel_pvc_cost_weekly.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return rows


if __name__ == '__main__':
    import sys
    extra = {}
    for kv in sys.argv[1:]:
        d, u = kv.split(',', 1)
        extra[d] = u
    collect(extra)
