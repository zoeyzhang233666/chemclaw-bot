#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自检：不依赖真实数据，构造一份最小可用 regions.json，跑通 校验 → HTML → Excel → QA。

用法:
  python selftest.py                 # 用临时目录
  python selftest.py --keep out/selftest

检验的是**管线**，不是数据：形状对不对、门禁是否生效、产物是否自洽、离线是否可开。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_html  # noqa: E402
import build_xlsx  # noqa: E402
import common  # noqa: E402
import validate  # noqa: E402


def fixture():
    """一份刻意的"最小真实形状"数据：含 1 个精确点、1 个县级点、1 个否证条目、1 个置换项目。"""
    return {
        'meta': dict(product='测试品', region='测试省', asof='2026-01-01', capacity_unit='万吨/年',
                     capacity_basis='设计产能', scope_note='自检用',
                     title='自检数据', subtitle='这不是真实数据，只用于验证管线',
                     tags=['自检'], focus_provinces=['山东'], hub_label='测试',
                     capacity_scope_total=200, capacity_scope_note='自检口径'),
        'companies': [dict(id='c1', name='甲企业', group='甲集团', listed='000001.SZ'),
                      dict(id='c2', name='乙企业', group='—', listed='—')],
        'cities': [dict(province='山东省', city='潍坊市', capacity=100, capacity_covered=100, data_grade='A'),
                   dict(province='山东省', city='淄博市', capacity=None, data_grade='C',
                        note='无产能，仅下游')],
        'sites': [
            dict(site_id='t1', company_id='c1', site_name='甲厂区', role='production', site_type='生产工厂',
                 route='氨碱', capacity=100, raw_capacity='年产能 100 万吨', capacity_basis='设计产能',
                 status='在产', province='山东省', city='潍坊市', district='滨海区', park_id='p1',
                 lon=119.02, lat=37.13, precision='精确', coord_source='地图地名库',
                 reg_address='某路 1 号', reg_address_type='实际生产地址（注册地同址）',
                 plant_address='某工业园区 1 号', address_type='园区地址',
                 products=['测试品'], upstream=['原料A'], downstream=['下游A'],
                 evidence_grade='A', source_ids=['s1'], note='自检', verify=['待核实项']),
            dict(site_id='t2', company_id='c1', site_name='甲厂区配套装置', role='production',
                 site_type='一体化/配套装置', route='氨碱', capacity=None,
                 raw_capacity='现产量 5 万吨/年（非本品种）', capacity_basis='衍生产品，不进合计',
                 status='在产', province='山东省', city='潍坊市', district='滨海区', park_id='p1',
                 lon=119.021, lat=37.129, precision='精确', coord_source='地图地名库',
                 reg_address='某路 1 号', reg_address_type='实际生产地址（注册地同址）',
                 plant_address='某工业园区 1 号', address_type='园区地址',
                 products=['衍生物'], evidence_grade='C', source_ids=['s1'], note='不应进入产能合计'),
            dict(site_id='t3', company_id='c2', site_name='乙厂区（否证）', role='production',
                 site_type='生产工厂', route='未知', capacity=None, raw_capacity='无本品种装置',
                 capacity_basis='否证', status='在产', province='山东省', city='淄博市',
                 precision='市级', coord_source='未核实',
                 reg_address='某街 2 号', reg_address_type='注册地址',
                 plant_address='某街 2 号', address_type='园区地址',
                 evidence_grade='B', source_ids=['s2'], note='否证条目'),
        ],
        'parks': [dict(id='p1', name='测试化工园', level='省级', province='山东省', city='潍坊市',
                       district='滨海区', short='测试园', main_industries=['盐化工'],
                       soda_relevance='甲企业所在园区', supporting=['铁路专用线'],
                       lon=119.02, lat=37.13, precision='园区级', coord_basis='企业群中心',
                       evidence_grade='A', source_ids=['s1'], note='')],
        'projects': [dict(id='P1', company_id='c1', name='甲厂区技改置换', type='技改',
                          province='山东省', city='潍坊市', district='滨海区', park='测试化工园',
                          capacity=80, capacity_retired=100, status='拟建', status_asof='2026-01-01',
                          products=['测试品'], impact='净减 20 万吨', evidence_grade='A',
                          source_ids=['s1'], verify=['是否开工'])],
        'upstream': [dict(material='原料A', spec='—', name='甲原料基地', province='山东省',
                          city='潍坊市', quant='未取得', note='自检', evidence_grade='B', source_ids=['s1'])],
        'downstream': [dict(segment='下游A', company='丙玻璃厂', plant='某基地', province='山东省',
                            city='淄博市', scale='2×600t/d', use='助熔剂', note='自检',
                            evidence_grade='B', source_ids=['s2'])],
        'nodes': [dict(id='n1', name='测试港', role='port', province='山东省', city='潍坊市',
                       lon=119.05, lat=37.12, precision='园区级', cap_note='通过能力 100 万吨',
                       evidence='装卸清单含本品种', evidence_grade='B', source_ids=['s1'])],
        'flows': [],
        'prices': dict(observations=[dict(asof='2026-01-01', spec='轻', region='测试省', value=1000,
                                          unit='元/吨', basis='出厂含税', note='自检', sources=['s1'])],
                       regional_features=[dict(region='潍坊', feature='产地端', source=['s1'])],
                       note='自检'),
        'conclusions': [dict(text='自检结论', method='自检', sources=['s1'])],
        'narrative': dict(coverage_note='自检覆盖说明', address_rule='注册地不作点位',
                          route_note='工艺说明', sankey_note='定性流向', concentration_note='集中度说明',
                          project_note='1 个项目',
                          price_diff_factors=[dict(text='运费', source=['s1'])],
                          gaps=[dict(item='全名单', scope='全省', why='无政府名单', impact='可能低估',
                                     how='查排污许可平台', priority='P0')],
                          method=[dict(k='主体口径', v='企业≠厂区')],
                          usage=['仅用于自检']),
        'sources': [dict(id='s1', publisher='测试A', title='测试来源一', url='https://example.com/a',
                         date='2026-01', doc_type='年报', grade='A', note='自检'),
                    dict(id='s2', publisher='测试B', title='测试来源二', url='https://example.com/b',
                         date='2026-01', doc_type='官网', grade='B', note='自检')],
        'layers': [],
    }


def run(keep=None):
    out = keep or tempfile.mkdtemp(prefix='selftest_')
    os.makedirs(out, exist_ok=True)
    D = fixture()
    dp = os.path.join(out, 'regions.json')
    with open(dp, 'w', encoding='utf-8') as f:
        json.dump(D, f, ensure_ascii=False, indent=1)

    fails = []
    E, W = validate.check(D)
    print('validate: error %d / warning %d' % (len(E), len(W)))
    for w in W:
        print('  [WARN]', w)
    if E:
        fails += ['validate 报错：' + e for e in E]

    N = common.normalize(D)
    A = N['_agg']
    if abs(A['capacity_sample_total'] - 100) > 1e-6:
        fails.append('衍生品装置被计入合计：样本产能 %.2f ≠ 100' % A['capacity_sample_total'])
    if A['plants_total'] != 3:
        fails.append('生产厂区数 %d ≠ 3（含否证条目，capacity 为 null 也要入表）' % A['plants_total'])
    if A.get('plants_capacity_total') != 1:
        fails.append('有公开产能的厂区数 %s ≠ 1（衍生品/否证条目不应计入）'
                     % A.get('plants_capacity_total'))
    nets = [p.get('net') for p in N['projects']]
    if nets != [-20]:
        fails.append('置换项目净增量 %s ≠ [-20]' % nets)

    html_p = os.path.join(out, 'test.html')
    xlsx_p = os.path.join(out, 'test.xlsx')
    build_html.build(dp, html_p)
    build_xlsx.build(dp, xlsx_p)
    for p in (html_p, xlsx_p):
        if not os.path.exists(p) or os.path.getsize(p) < 20000:
            fails.append('产物缺失或过小：%s' % p)

    # 离线自包含
    with open(html_p, encoding='utf-8') as f:
        h = f.read()
    if '%%' in h:
        fails.append('HTML 残留 %% 占位符')
    if 'http://' in h.replace('http://www.w3.org', '') or 'https://' in h:
        # 允许来源清单里的 URL（文本，不是资源引用）
        import re
        ext = re.findall(r'(?:src|href)\s*=\s*["\']https?://', h)
        if ext:
            fails.append('HTML 引用了 %d 个外部资源' % len(ext))

    # 门禁有效性：故意注入一个"注册地址当装置位置"的站点，必须被拦
    bad = json.loads(json.dumps(D))
    bad['sites'][0]['reg_address'] = '某总部大厦 18 层'
    bad['sites'][0]['reg_address_type'] = '注册地址'
    bad['sites'][0]['plant_address'] = '某总部大厦 18 层'
    E2, _ = validate.check(bad)
    if not any('总部' in e or '注册地址' in e for e in E2):
        fails.append('地址门失效：注册地址当装置位置未被拦截')

    # 门禁有效性：产能单位错
    bad2 = json.loads(json.dumps(D))
    bad2['sites'][0]['raw_capacity'] = '年产能 10000 吨'
    _, W2 = validate.check(bad2)
    if not any('对不上' in w or '单位' in w for w in W2):
        fails.append('口径门失效：万吨/吨单位错未被警告')

    # Excel 结构
    try:
        from openpyxl import load_workbook
        wb = load_workbook(xlsx_p)
        if len(wb.sheetnames) != 14:
            fails.append('Excel 表数 %d ≠ 14' % len(wb.sheetnames))
    except Exception as e:  # noqa: BLE001
        fails.append('Excel 打不开：%s' % e)

    print('HTML %.0f KB / XLSX %.0f KB' % (os.path.getsize(html_p) / 1024,
                                           os.path.getsize(xlsx_p) / 1024))
    if keep:
        print('保留产物：', out)
    else:
        shutil.rmtree(out, ignore_errors=True)
    if fails:
        for f in fails:
            print('[FAIL]', f)
        print('—— 自检未通过（%d 项）' % len(fails))
        return 1
    print('—— 自检通过：校验 / 聚合 / HTML / Excel / 门禁 均正常')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep', default=None, help='保留自检产物到该目录')
    a = ap.parse_args()
    sys.exit(run(a.keep))


if __name__ == '__main__':
    main()
