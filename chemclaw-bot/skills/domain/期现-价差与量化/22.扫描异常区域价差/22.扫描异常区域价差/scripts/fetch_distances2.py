# -*- coding: utf-8 -*-
"""
fetch_distances.py —— 抓取物流节点之间的公路里程（OSRM 公共路由，实测非估算）

节点用「面板地区代码」命名，与 build_panel.py 的 REGION_MAP 保持一致，
这样 scan.py 的距离查表可以直接命中。输出 data_raw/distances.json。
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'data_raw')

# code -> (显示名, 代表点, lon, lat)
NODES = {
    'EC_TAICANG':      ('江苏太仓', '太仓港（进口集散/交割库）', 121.10, 31.45),
    'EC_ZIBO':         ('山东淄博', '淄博（纯碱/甲醇产区）', 118.05, 36.81),
    'EC_SHANDONG':     ('山东', '潍坊（海化/海天纯碱基地）', 119.16, 36.71),
    'EC_JIANGSU':      ('江苏', '连云港（碱业/港口）', 119.22, 34.60),
    'EC_ZHEJIANG':     ('浙江', '杭州（消费地）', 120.15, 30.28),
    'EC_SHANGHAI':     ('上海', '上海（贸易节点）', 121.47, 31.23),
    'EC_ANHUI':        ('安徽', '阜阳（昊源化工）', 115.81, 32.90),
    'EC_JIANGXI':      ('江西', '南昌（消费地）', 115.89, 28.68),
    'H_HENAN':         ('河南', '桐柏（天然碱）', 113.42, 32.38),
    'H_HUBEI':         ('湖北', '武汉（联碱/长江节点）', 114.31, 30.59),
    'H_HUNAN':         ('湖南', '长沙（消费地）', 112.94, 28.23),
    'N_HEBEI':         ('河北沙河', '沙河（玻璃集群/交割地）', 114.50, 36.86),
    'N_TIANJIN':       ('天津', '天津港（下水/集散）', 117.20, 39.13),
    'N_INNERMONGOLIA': ('内蒙古', '鄂尔多斯（天然碱/煤化工）', 109.78, 39.61),
    'N_SHAANXI':       ('陕西', '榆林（煤化工产区）', 109.74, 38.28),
    'N_NINGXIA':       ('宁夏', '银川（产区）', 106.28, 38.47),
    'N_QINGHAI':       ('青海', '格尔木（盐湖/天然碱）', 94.90, 36.40),
    'N_GANSU':         ('甘肃', '兰州（产区）', 103.82, 36.06),
    'N_XINJIANG':      ('新疆', '乌鲁木齐（产区）', 87.62, 43.79),
    'N_SHANXI':        ('山西', '太原（产区）', 112.55, 37.87),
    'W_SICHUAN':       ('四川', '成都（西南产区/消费）', 104.07, 30.65),
    'W_CHONGQING':     ('重庆', '重庆（长江节点）', 106.55, 29.56),
    'W_GUIZHOU':       ('贵州', '贵阳', 106.63, 26.65),
    'W_YUNNAN':        ('云南', '昆明', 102.71, 25.05),
    'S_GUANGDONG':     ('广东', '广州（华南消费/港口）', 113.26, 23.13),
    'S_FUJIAN':        ('福建', '福州（消费地）', 119.30, 26.08),
    'S_HAINAN':        ('海南', '海口', 110.20, 20.04),
    'NE_LIAONING':     ('辽宁', '沈阳', 123.43, 41.80),
    'NE_JILIN':        ('吉林', '长春', 125.32, 43.90),
    'NE_HEILONGJIANG': ('黑龙江', '哈尔滨', 126.53, 45.80),
}

OSRM = 'https://router.project-osrm.org/route/v1/driving/{},{};{},{}?overview=false'
LAST_ERR = []


def fetch(a, b, tries=3):
    u = OSRM.format(NODES[a][2], NODES[a][3], NODES[b][2], NODES[b][3])  # lon,lat;lon,lat
    for i in range(tries):
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'spread-scan/1.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read().decode('utf-8'))
            rt = (j.get('routes') or [None])[0]
            if rt:
                return {'km': round(rt['distance'] / 1000.0, 1),
                        'hours': round(rt['duration'] / 3600.0, 2)}
        except Exception as e:
            LAST_ERR.append('%s->%s: %r' % (a, b, e))
            time.sleep(2 + i * 3)
    return None


def main():
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, 'distances.json')
    old = {}
    if os.path.exists(path):
        old = json.load(open(path, encoding='utf-8')).get('distances', {})
    codes = sorted(NODES)
    out = dict(old)
    ok = fail = 0
    n = 0
    total = len(codes) * (len(codes) - 1) // 2
    for i, a in enumerate(codes):
        for b in codes[i + 1:]:
            n += 1
            k = '%s|%s' % (a, b)
            if k in out and out[k].get('km'):
                ok += 1
                continue
            r = fetch(a, b)
            if r:
                out[k] = r
                ok += 1
            else:
                fail += 1
            if n % 10 == 0:
                print('  %d/%d  ok=%d fail=%d' % (n, total, ok, fail), flush=True)
            time.sleep(2.2)   # 公共服务限速
    json.dump({'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
               'source': 'OSRM 公共路由服务（OpenStreetMap 路网），driving 模式实测里程',
               'nodes': [{'code': c, 'market': NODES[c][0], 'point': NODES[c][1],
                          'lon': NODES[c][2], 'lat': NODES[c][3]} for c in codes],
               'distances': out},
              open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if LAST_ERR:
        print('前 5 条错误：')
        for e in LAST_ERR[:5]:
            print('  ', e)
    print('saved %s  组合 %d，成功 %d，失败 %d' % (path, total, ok, fail))


if __name__ == '__main__':
    main()
