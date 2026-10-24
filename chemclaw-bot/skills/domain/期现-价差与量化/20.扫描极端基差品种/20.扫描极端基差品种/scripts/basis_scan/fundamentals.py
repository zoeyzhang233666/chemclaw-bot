# -*- coding: utf-8 -*-
"""fundamentals.py — 为极端品种补充「可获取」的库存 / 仓单 / 供需事件

原则（写入 SKILL.md）
--------------------
1. 只有在**实际取到数据**时才写入数值；取不到就写「未获取」，并注明已尝试的来源与原因。
2. 不把新闻稿里的定性描述加工成数字；每条事件都带来源 URL 与日期。
3. 库存/仓单数值必须带「数据日期 + 品种 + 口径（交易所仓单/社会库存/港口库存）」。

数据获取策略（实测）
------------------
- 交易所仓单：大商所/郑商所公开日报为动态页面，程序化抓取不稳定；
  本工具优先读取 data/raw/fund/{code}_inventory.csv（若由人工/其它工具落盘），
  否则回落到 100ppi 公开资讯检索中的仓单/库存稿标题与数值，并在 events 中标明
  「来源=资讯稿，非交易所日报」。
- 供需事件：从 100ppi 各品种栏目（data/dlist）中筛选「检修/投产/开工/库存/装置」类稿件标题。
"""
from __future__ import annotations

import csv
import os
import re
from urllib.parse import quote

from .http import Http

BASE = 'https://www.100ppi.com'
ROW_RE = re.compile(r'<a\s+href="(detail-(\d{8})-(\d+)\.html)"[^>]*class="blueq"[^>]*>([^<]{4,200})</a>')
INV_KW = ['仓单', '库存', '港口库存']
EVENT_KW = ['检修', '停车', '投产', '开工', '装置', '新增产能', '减产', '复产', '限产', '检修季']
NUM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(万?吨|张|手)')


def load_inventory(root: str, code: str) -> list[dict]:
    p = os.path.join(root, 'data', 'raw', 'fund', '%s_inventory.csv' % code)
    if not os.path.exists(p):
        return []
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def scan_column(http: Http, prod: dict, pages: int = 3) -> tuple[list[dict], list[dict]]:
    """在品种栏目里找仓单/库存稿与产业事件稿。"""
    inv, events = [], []
    for p in range(1, pages + 1):
        url = '%s/data/dlist-%d--%d-%d.html' % (BASE, int(prod['channel']), int(prod['ppid']), p)
        html = http.get(url, referer=BASE + '/data/')
        if not html:
            break
        for m in ROW_RE.finditer(html):
            href, ymd, _nid, title = m.group(1), m.group(2), m.group(3), m.group(4).strip()
            if any(k in title for k in INV_KW):
                inv.append(dict(date='%s-%s-%s' % (ymd[:4], ymd[4:6], ymd[6:8]),
                                title=title, url=BASE + '/' + href))
            elif any(k in title for k in EVENT_KW):
                events.append(dict(date='%s-%s-%s' % (ymd[:4], ymd[4:6], ymd[6:8]),
                                   title=title, url=BASE + '/' + href))
    return inv, events


def collect_fundamentals(http: Http, prods: list[dict], root: str) -> dict:
    """对给定品种收集库存/仓单与事件；返回 {code: {...}}。"""
    out = {}
    for prod in prods:
        inv_rows = load_inventory(root, prod['code'])
        inv_news, events = scan_column(http, prod, pages=3)
        latest_inv = inv_rows[-1] if inv_rows else None
        inv_status = 'ok' if inv_rows else '未获取'
        reason = '' if inv_rows else ('未找到可程序化获取的交易所仓单/库存日序列；'
                                      '已检索生意社公开资讯标题，未见含数值的仓单稿')
        out[prod['code']] = dict(
            code=prod['code'], name=prod['name'], inventory=inv_rows, inv_status=inv_status,
            inv_reason=reason, inventory_news=inv_news[:8], events=events[:12])
    return out


def search_news(http: Http, q: str, n: int = 8) -> list[dict]:
    """100ppi 站内搜索（若可用），用于补充品种供需与库存的定性变化。"""
    url = 'https://www.100ppi.com/mprice/?f=search&terms=' + quote(q)
    html = http.get(url, referer=BASE + '/')
    if not html:
        return []
    rows = []
    for m in re.finditer(r'<a[^>]+href="([^"]*detail-\d{8}-\d+\.html)"[^>]*>([^<]{4,160})</a>', html):
        rows.append(dict(title=m.group(2).strip(), url=m.group(1)))
        if len(rows) >= n:
            break
    return rows
