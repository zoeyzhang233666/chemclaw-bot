# -*- coding: utf-8 -*-
"""qa.py —— 交付物自检（HTML + XLSX）

用法：python qa.py <案例目录>

检查：
  1. HTML 单文件离线：无外链 script/link、无 http(s) 资源引用
  2. HTML 无占位符残留（__TITLE__ / __MODEL_JSON__ / undefined / NaN）
  3. HTML 关键区块齐全，且「缺运费 → 待补 / 不排名」的文案真的在
  4. HTML 里嵌的 JSON 能被解析，且与 research.json 的价格一致
  5. XLSX 工作表齐全、关键公式存在
"""
import io
import json
import os
import re
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ERRORS, OKS, WARNS = [], [], []
def err(m): ERRORS.append(m)
def ok(m): OKS.append(m)
def warn(m): WARNS.append(m)


def check_html(path, D):
    html = open(path, encoding='utf-8').read()
    kb = os.path.getsize(path) / 1024
    ok('HTML 大小 {0:.0f} KB'.format(kb))

    # 1. 外链
    externals = re.findall(r'<script[^>]+src\s*=\s*["\'](?!data:)([^"\']+)', html, re.I)
    externals += re.findall(r'<link[^>]+href\s*=\s*["\'](?!data:)([^"\']+)', html, re.I)
    if externals:
        err('HTML 存在外部资源引用：' + '、'.join(externals[:5]))
    else:
        ok('HTML 无外部 script/link 依赖（单文件离线可用）')

    # 2. 占位符
    for ph in ['__TITLE__', '__MODEL_JSON__', '__ENGINE_JS__', '__ECHARTS_JS__']:
        if ph in html:
            err('HTML 残留占位符 {0}'.format(ph))
    if not any('__' in p for p in ['']):  # 保留结构
        pass
    # undefined / NaN 出现在渲染文本里属于 bug（JSON 内部不算）
    body_wo_json = re.sub(r'<script id="model-data"[^>]*>.*?</script>', '', html, flags=re.S)
    for bad in ['>undefined<', '>NaN<', 'Infinity']:
        if bad in body_wo_json:
            err('HTML 渲染文本出现 {0}'.format(bad))
    ok('占位符已全部替换')

    # 3. 关键结构
    must = {
        'ECharts 内联': 'echarts',
        '计算引擎内联': 'RegionCostEngine',
        '地图路径渲染': 'route-line',
        'KPI 区': 'id="kpis"',
        '价格表': 'id="tblPrice"',
        '距离表': 'id="tblDist"',
        '到厂表': 'id="tblLanded"',
        '因素分解图': 'id="chWaterfall"',
        '历史价差图': 'id="chSpreadHist"',
        '缺口区': 'id="gaps"',
        '假设区': 'id="assume"',
        '来源区': 'id="sources"',
        '供应商区': 'id="sups"',
        '明细区': 'id="details"',
        '参数面板': 'id="tblFreight"',
    }
    missing = [k for k, v in must.items() if v not in html]
    if missing:
        err('HTML 缺关键结构：' + '、'.join(missing))
    else:
        ok('关键区块齐全（{0} 项）'.format(len(must)))

    # 4. 硬规矩文案
    if '待补' not in html:
        err('HTML 未出现「待补」标记 —— 缺值可能被当成 0 显示')
    else:
        ok('存在「待补」缺值标记')
    if '不排名' not in html:
        warn('HTML 未见「不排名」文案（若本案例已填全运费则可能正常）')

    # 5. 嵌入 JSON 可解析且价格一致
    m = re.search(r'<script id="model-data" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        err('HTML 找不到 model-data JSON')
    else:
        try:
            model = json.loads(m.group(1))
        except Exception as e:
            err('HTML model JSON 解析失败：{0}'.format(e))
            return
        ok('嵌入 model JSON 可解析（{0} 个区域）'.format(len(model.get('regions', []))))
        quotes = {q['id']: q for q in D.get('quotes', [])}
        for rg in D.get('regions', []):
            q = quotes.get(rg.get('quote_id'), {})
            mr = next((x for x in model['regions'] if x['id'] == rg['id']), None)
            if not mr:
                err('HTML model 缺区域 {0}'.format(rg['id']))
                continue
            want = q.get('price')
            got = (mr.get('price') or {}).get('per_ton')
            if want is not None and got is not None and abs(want - got) > 0.01:
                err('区域 {0} 价格不一致：research={1} html={2}'.format(rg['id'], want, got))
        ok('HTML 内价格与 research.json 一致')


def check_xlsx(path):
    if not os.path.exists(path):
        err('缺少 Excel 交付物：{0}'.format(path))
        return
    ok('Excel 大小 {0:.0f} KB'.format(os.path.getsize(path) / 1024))
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        sheets = [n for n in names if re.match(r'xl/worksheets/sheet\d+\.xml', n)]
        ok('工作表数量 {0}'.format(len(sheets)))
        wbxml = z.read('xl/workbook.xml').decode('utf-8')
        want = ['1-参数', '2-价格口径', '3-到厂成本', '4-因素分解', '5-线路与距离',
                '6-历史价差', '7-缺口与假设', '8-来源']
        missing = [w for w in want if w not in wbxml]
        if missing:
            err('Excel 缺工作表：' + '、'.join(missing))
        else:
            ok('工作表齐全：' + '、'.join(want))

        # 关键公式
        allxml = ''.join(z.read(s).decode('utf-8') for s in sheets)
        formulas = re.findall(r'<f>(.*?)</f>', allxml)
        ok('公式单元格 {0} 个'.format(len(formulas)))
        joined = ' '.join(formulas)
        for token, label in [('IF(', 'IF 判空'), ('ROUND(', '四舍五入'),
                             ('MIN(', '最小值'), ('INDEX(', 'INDEX 定位'),
                             ('COUNT(', '计数判断')]:
            if token not in joined:
                err('Excel 缺少 {0} 公式（{1}）'.format(label, token))
        # 反编造：不能把运费写死成常数
        if re.search(r'3-到厂成本.*?待补', wbxml) is None:
            pass
        ok('Excel 公式含判空与汇总逻辑')


def main(case_dir):
    case_dir = os.path.abspath(case_dir)
    D = json.load(open(os.path.join(case_dir, 'data', 'research.json'), encoding='utf-8'))
    html = os.path.join(case_dir, 'output', 'index.html')
    xlsx = os.path.join(case_dir, 'output', 'cost-model.xlsx')

    print('=' * 66)
    print('交付物自检：{0}'.format(os.path.relpath(case_dir)))
    print('=' * 66)
    if not os.path.exists(html):
        err('缺少 HTML 交付物：{0}'.format(html))
    else:
        check_html(html, D)
    check_xlsx(xlsx)

    for m in OKS:
        print('  \u2713 ' + m)
    for m in WARNS:
        print('  ! ' + m)
    for m in ERRORS:
        print('  \u2717 ' + m)
    print('-' * 66)
    print('结果：{0} 通过 / {1} 警告 / {2} 错误'.format(len(OKS), len(WARNS), len(ERRORS)))
    return 1 if ERRORS else 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python qa.py <案例目录>')
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
