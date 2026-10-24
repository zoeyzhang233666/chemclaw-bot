#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regions.json → 自包含 HTML 区域产业地图（离线可开、可打印、可切图层）。

用法:
  python build_html.py regions.json --out out/山东-纯碱产业地图.html
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

GEO_B64_PLACEHOLDER = '%%GEO%%'
DATA_PLACEHOLDER = '%%DATA%%'
ECHARTS_PLACEHOLDER = '%%ECHARTS%%'


def _asset_bytes():
    """贪心压缩：把省界 GeoJSON 用 zip+base64 内联，前台用 DecompressionStream 解压。"""
    import base64
    import gzip
    import io
    path = os.path.join(common.ASSETS, 'china_prov.json')
    raw = open(path, 'rb').read()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=9, mtime=0) as g:
        g.write(raw)
    return base64.b64encode(buf.getvalue()).decode('ascii')


def build_json(D):
    """把 normalize 后的数据压成前端包。"""
    site = D.get('sites', [])
    parks = D.get('parks', [])
    comps = D.get('companies', [])
    projs = D.get('projects', [])
    A = D['_agg']
    M = D['meta']

    def site_out(s):
        return {
            'sid': s.get('site_id') or s.get('site_name'),
            'name': s.get('site_name'),
            'company': s.get('company'), 'company_id': s.get('company_id'),
            'group': s.get('group'),
            'role': s.get('role'), 'type': s.get('site_type', '生产工厂'),
            'route': s.get('route') or '未知',
            'capacity': s.get('capacity'), 'raw_capacity': s.get('raw_capacity'),
            'capacity_unit': s.get('capacity_unit') or M.get('capacity_unit'),
            'capacity_basis': s.get('capacity_basis'),
            'status': s.get('status'),
            'prov': s.get('province'), 'city': s.get('city'), 'district': s.get('district'),
            'park_id': s.get('park_id'), 'park': s.get('park'),
            'lon': s.get('lon'), 'lat': s.get('lat'),
            'precision': s.get('precision'), 'coord_source': s.get('coord_source'),
            'reg_address': s.get('reg_address'), 'reg_address_type': s.get('reg_address_type'),
            'plant_address': s.get('plant_address'), 'address_type': s.get('address_type'),
            'products': s.get('products') or [],
            'upstream': s.get('upstream') or [], 'downstream': s.get('downstream') or [],
            'grade': s.get('evidence_grade'), 'sources': s.get('source_ids') or [],
            'verify': s.get('verify') or [], 'note': s.get('note'),
            'coordinate_usable': s.get('coordinate_usable'),
            'layers': s.get('layers') or [],
        }

    sites_f = [site_out(s) for s in site]
    projects_f = [{
        'id': p.get('id') or p.get('name'), 'name': p.get('name'), 'company': p.get('company_id'),
        'company_name': next((c['name'] for c in comps if c.get('id') == p.get('company_id')), p.get('company')),
        'type': p.get('type'), 'capacity': p.get('capacity'), 'capacity_retired': p.get('capacity_retired'),
        'net': p.get('net'), 'status': p.get('status'), 'status_asof': p.get('status_asof'),
        'online': p.get('online'), 'prov': p.get('province'), 'city': p.get('city'),
        'district': p.get('district'), 'park': p.get('park'), 'lon': p.get('lon'), 'lat': p.get('lat'),
        'precision': p.get('precision'), 'products': p.get('products') or [],
        'impact': p.get('impact'), 'grade': p.get('evidence_grade'),
        'sources': p.get('source_ids') or [], 'verify': p.get('verify') or [],
    } for p in projs]
    parks_f = [{
        'id': p.get('id'), 'name': p.get('name'), 'level': p.get('level'),
        'prov': p.get('province'), 'city': p.get('city'), 'district': p.get('district'),
        'lon': p.get('lon'), 'lat': p.get('lat'), 'coord_basis': p.get('coord_basis'),
        'precision': p.get('precision'), 'addr': p.get('address'),
        'main_industries': p.get('main_industries') or [],
        'soda_relevance': p.get('soda_relevance'), 'supporting': p.get('supporting') or [],
        'site_count': sum(1 for s in site if s.get('park_id') == p.get('id')),
        'grade': p.get('evidence_grade'), 'sources': p.get('source_ids') or [],
        'note': p.get('note'),
    } for p in parks]
    nodes_f = [{
        'id': n.get('id'), 'name': n.get('name'), 'role': n.get('role'),
        'prov': n.get('province'), 'city': n.get('city'), 'lon': n.get('lon'), 'lat': n.get('lat'),
        'precision': n.get('precision'), 'index': n.get('index'), 'evidence': n.get('evidence'),
        'grade': n.get('evidence_grade'), 'sources': n.get('source_ids') or [],
    } for n in D.get('nodes', [])]
    flows_f = [{
        'id': f.get('id'), 'kind': f.get('kind'), 'from': f.get('from_site'),
        'to': f.get('to_node') or f.get('to_site'), 'material': f.get('material'),
        'volume': f.get('volume'), 'basis': f.get('basis'), 'note': f.get('note'),
        'sources': f.get('source_ids') or [],
    } for f in D.get('flows', [])]
    cities_f = [dict(v) for v in A['by_city'].values()]
    cities_f.sort(key=lambda c: -(c.get('capacity_sample') or 0))
    provs_f = sorted(A['by_prov'].values(), key=lambda x: -(x.get('capacity_sample') or 0))

    return {
        'meta': M,
        'summary': D.get('summary') or {},
        'sites': sites_f, 'parks': parks_f, 'projects': projects_f, 'nodes': nodes_f,
        'flows': flows_f, 'companies': comps, 'cities': cities_f, 'provinces': provs_f,
        'upstream': D.get('upstream', []), 'downstream': D.get('downstream', []),
        'prices': D.get('prices', {}), 'conclusions': D.get('conclusions', []),
        'narrative': D.get('narrative', {}), 'sources': D.get('sources', []),
        'agg': {k: v for k, v in A.items() if k not in ('by_city', 'by_prov')},
        'layers': D.get('layers') or [],
        'filters': M.get('filters') or {},
    }


def build(data_path, out_path):
    D = common.load(data_path)
    pkg = build_json(D)
    tpl_path = os.path.join(common.TEMPLATES, 'report.html')
    with open(tpl_path, encoding='utf-8') as f:
        tpl = f.read()
    for ph in (ECHARTS_PLACEHOLDER, GEO_B64_PLACEHOLDER, DATA_PLACEHOLDER):
        n = tpl.count(ph)
        if n != 1:
            raise SystemExit('模板占位符 %s 出现 %d 次（必须恰好 1 次）' % (ph, n))
    with open(os.path.join(common.ASSETS, 'echarts.min.js'), encoding='utf-8') as f:
        echarts = f.read()
    # 内联进 <script> 前先把 </script 拆开，否则 HTML 解析器会提前闭合脚本，echarts 只剩半包
    echarts = echarts.replace('</script', '<\\/script')
    html = tpl.replace(ECHARTS_PLACEHOLDER, echarts)
    html = html.replace(GEO_B64_PLACEHOLDER, _asset_bytes())
    html = html.replace(DATA_PLACEHOLDER, json.dumps(pkg, ensure_ascii=False, separators=(',', ':')))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print('HTML →', out_path, '(%.1f KB)' % (os.path.getsize(out_path) / 1024))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data')
    ap.add_argument('--out', default='out/区域产业地图.html')
    a = ap.parse_args()
    build(a.data, a.out)


if __name__ == '__main__':
    main()
