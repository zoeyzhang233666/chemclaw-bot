# -*- coding: utf-8 -*-
"""check_html.py —— 静态自检：占位符残留、外链、禁用词、数字一致性"""
import json, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')

BANNED = ['预计上涨', '预计下跌', '看涨', '看跌', '抄底', '必涨', '必跌', '稳赚',
          '有望上涨', '有望下跌', '将会上涨', '将会下跌', '后市将', '建议买入',
          '建议卖出', '囤货待涨', '底部已现', '顶部已现']
# 这些是必须出现的限定语
REQUIRED = ['价差口径', '不是利润', '不作因果推断']


def main(html_path, analysis_path):
    h = open(html_path, encoding='utf-8').read()
    a = json.load(open(analysis_path, encoding='utf-8'))
    fails, warns = [], []

    # ECharts 库内部含有 {title}/}} 等字符，检查前先剔除库体，避免误报
    i0 = h.find('<script>')
    i1 = h.find('</script>', i0)
    lib = h[i0:i1] if i0 >= 0 else ''
    body = h.replace(lib, '') if len(lib) > 100_000 else h

    # 1 占位符（只看自己生成的模板部分）
    for ph in ['{unit0}', '{stages}', '{data}', '{nav}', '{echarts}', '{title}', '{css}', '{sections}']:
        if ph in body:
            fails.append('占位符未替换：%s' % ph)
    if '{{' in body:
        fails.append('检测到未展开的双花括号，模板转义有误')
    if re.search(r'\{[a-z_]{3,}\}', body):
        m = re.search(r'\{[a-z_]{3,}\}', body)
        warns.append('疑似残留占位符：%s' % m.group(0))

    # 2 外链（必须离线可开）
    ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', body)
    ext = [e for e in ext if '100ppi' not in e and 'eastmoney' not in e]
    if len(ext) > 5:
        fails.append('外链过多（%d 个），可能未内联：%s' % (len(ext), ext[:3]))
    elif ext:
        warns.append('存在 %d 个外链（来源页，可接受）' % len(ext))

    # 3 禁用词（预测/建议）
    for w in BANNED:
        if w in h:
            fails.append('出现禁用表述：%s' % w)

    # 4 必需限定语
    for w in REQUIRED:
        if w not in h:
            fails.append('缺少必需限定语：%s' % w)

    # 5 结构完整
    if h.count('<section') < 8:
        fails.append('分页不足 8 个（当前 %d）' % h.count('<section'))
    charts = re.findall(r'id="(c-[a-z]+)"', h)
    if len(charts) < 4:
        fails.append('图表容器不足（%d 个）' % len(charts))

    # 6 数字一致性：抽查 KPI
    s = a['summary']
    sp = s['spread']
    for label, val in [('价差均值', sp['mean']), ('最新价差', sp['latest'])]:
        txt = ('{:,.1f}'.format(val)) if label == '价差均值' else ('{:,.0f}'.format(val))
        if txt not in h:
            fails.append('KPI 数字未出现在 HTML：%s=%s' % (label, txt))

    # 7 数据规模
    if len(h) < 500_000:
        fails.append('文件过小（%d 字节），ECharts 可能未内联' % len(h))
    if 'echarts' not in h:
        fails.append('未检测到 ECharts')

    print('文件：%s（%.2f MB）' % (os.path.basename(html_path), len(h) / 1048576))
    print('分页 %d 个，图表容器 %d 个' % (h.count('<section'), len(charts)))
    for w in warns:
        print('  [warn]', w)
    if fails:
        for x in fails:
            print('  [FAIL]', x)
        print('\n检查失败：%d 项' % len(fails))
        return 1
    print('\n全部通过：%d 项检查' % (8 + len(warns)))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('用法：python check_html.py <report.html> <analysis.json>')
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
