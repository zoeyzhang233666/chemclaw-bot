# -*- coding: utf-8 -*-
"""
采集脚本 B（稳健版）：ChemicalBook「价格报告」明细（省级 × 日度，真实厂家报价）

要点：
  - 断点续采：列表与明细分别落盘（data_raw/cb_list_*.json / data_raw/cb_rows_*.jsonl），
    中断后可继续，不需要从头再来。
  - 该站有明显速率限制：连续请求会返回 1.7KB 的拦截页，故采用「单并发 + 随机间隔 + 退避」。
  - 失败不伪造：失败的报告记录进 data_raw/cb_failed_*.json，供后续补采或登记为数据缺口。

输出：
  data_raw/cb_list_<key>.json   报告目录（id / 标题 / 日期 / url）
  data_raw/cb_rows_<key>.jsonl  逐行报价（date / location / maker / spec / price / unit / report_id）
  data_raw/chembook_panel.json  汇总面板
"""
import gzip
import json
import os
import random
import re
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'data_raw')
os.makedirs(RAW, exist_ok=True)

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

PRODUCTS = {
    'soda': {'cb': 'CB9853672', 'name': '纯碱（碳酸钠）'},
    'methanol': {'cb': 'CB7854099', 'name': '甲醇'},
}
MAX_PAGES = int(os.environ.get('CB_MAX_PAGES', '41'))


def fetch(url, tries=8):
    last = ''
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml',
                'Accept-Encoding': 'gzip', 'Accept-Language': 'zh-CN,zh;q=0.9',
                'Connection': 'close',
            })
            with urllib.request.urlopen(req, timeout=40) as r:
                b = r.read()
                if (r.headers.get('Content-Encoding') or '').lower() == 'gzip':
                    b = gzip.decompress(b)
            t = b.decode('utf-8', 'ignore')
            if len(t) < 5000:
                last = 'blocked'
                time.sleep(8 + random.random() * 10)
                continue
            return t
        except Exception as ex:
            last = str(ex)[:90]
            time.sleep(6 + random.random() * 8)
    raise RuntimeError('fetch failed %s (%s)' % (url, last))


PACE = lambda: time.sleep(3.0 + random.random() * 4.0)


ARCH_RE = re.compile(r'/PriceInfo_(\d+)\.htm">\s*([^<]{4,60})<')


def get_list(cb, key):
    path = os.path.join(RAW, 'cb_list_%s.json' % key)
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))
    out, seen = [], set()
    for p in range(1, MAX_PAGES + 1):
        url = ('https://www.chemicalbook.com/PriceInfoAll_%s.htm' % cb) if p == 1 else \
              ('https://www.chemicalbook.com/PriceInfoAll_%s_%d.htm' % (cb, p))
        try:
            t = fetch(url)
        except Exception as ex:
            print('  page %d fail: %s' % (p, ex))
            PACE()
            continue
        new = 0
        for rid, title in ARCH_RE.findall(t):
            rid = rid.strip()
            if rid in seen:
                continue
            seen.add(rid)
            m = re.match(r'(\d+)月(\d+)日\s+(\S+?)最新价格', title.strip())
            out.append({'id': rid, 'title': re.sub(r'\s+', ' ', title).strip(),
                        'md': '%02d-%02d' % (int(m.group(1)), int(m.group(2))) if m else None,
                        'url': 'https://www.chemicalbook.com/PriceInfo_%s.htm' % rid})
            new += 1
        print('  page %d -> %d new (total %d)' % (p, new, len(out)), flush=True)
        json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if new == 0:
            break
        PACE()
    return out


# 单元格带 style 属性（如 <td style="width: 100px;">），属性必须可选匹配
TD = r'<td[^>]*>\s*([^<]*?)\s*</td>'
ROW_RE = re.compile(
    r'<tr>\s*' + TD + r'\s*' + TD + r'\s*' + TD + r'\s*' + TD + r'\s*' + TD + r'\s*' + TD + r'\s*</tr>',
    re.S)


def parse(t):
    pub = re.search(r'发布日期[:：]\s*([\d/]+\s[\d:]+)', t)
    rows = []
    for m in ROW_RE.finditer(t):
        try:
            price = float(m.group(5).replace(',', ''))
        except Exception:
            continue
        rows.append({'date': m.group(1),
                     'location': re.sub(r'\s+', '', m.group(2)),
                     'maker': re.sub(r'\s+', ' ', m.group(3)).strip(),
                     'spec': re.sub(r'\s+', ' ', m.group(4)).strip(),
                     'price': price, 'unit': m.group(6).strip()})
    return (pub.group(1).strip() if pub else ''), rows


def main():
    only = sys.argv[1:] or list(PRODUCTS)
    for key in only:
        meta = PRODUCTS[key]
        print('==', key, meta['cb'], flush=True)
        reps = get_list(meta['cb'], key)
        rows_path = os.path.join(RAW, 'cb_rows_%s.jsonl' % key)
        done = set()
        if os.path.exists(rows_path):
            for line in open(rows_path, encoding='utf-8'):
                try:
                    done.add(json.loads(line)['report_id'])
                except Exception:
                    pass
        fail_path = os.path.join(RAW, 'cb_failed_%s.json' % key)
        failed = json.load(open(fail_path, encoding='utf-8')) if os.path.exists(fail_path) else []
        fh = open(rows_path, 'a', encoding='utf-8')
        for i, r in enumerate(reps):
            if r['id'] in done:
                continue
            try:
                pub, rows = parse(fetch(r['url']))
            except Exception as ex:
                print('   fail', r['id'], ex, flush=True)
                failed.append({'id': r['id'], 'title': r['title'], 'error': str(ex)[:120]})
                json.dump(failed, open(fail_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                PACE()
                continue
            for row in rows:
                row.update({'product': meta['name'], 'report_id': r['id'], 'published': pub,
                            'product_key': key})
                fh.write(json.dumps(row, ensure_ascii=False) + '\n')
            fh.flush()
            done.add(r['id'])
            if i % 5 == 0:
                print('   %d/%d %-26s rows=%d' % (i + 1, len(reps), r['title'][:24], len(rows)), flush=True)
            PACE()
        fh.close()
        print('  done', key, 'reports fetched', len(done), 'failed', len(failed), flush=True)
    # 汇总
    panel = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
             'source': 'ChemicalBook 价格报告（PriceInfo / PriceInfoAll 归档）',
             'source_kind': '厂家/贸易商公开挂牌报价（dealer quotation），非统一市场价',
             'products': {}}
    for key, meta in PRODUCTS.items():
        rp = os.path.join(RAW, 'cb_rows_%s.jsonl' % key)
        if not os.path.exists(rp):
            continue
        rows = [json.loads(x) for x in open(rp, encoding='utf-8') if x.strip()]
        lp = os.path.join(RAW, 'cb_list_%s.json' % key)
        reps = json.load(open(lp, encoding='utf-8')) if os.path.exists(lp) else []
        panel['products'][key] = {'meta': meta, 'reports': reps, 'rows': rows}
        ds = sorted({r['date'] for r in rows})
        print(key, 'rows', len(rows), 'dates', (ds[0] + ' .. ' + ds[-1]) if ds else '-')
    json.dump(panel, open(os.path.join(RAW, 'chembook_panel.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved chembook_panel.json')


if __name__ == '__main__':
    main()
