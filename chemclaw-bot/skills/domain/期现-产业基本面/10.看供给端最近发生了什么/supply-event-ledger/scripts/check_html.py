# -*- coding: utf-8 -*-
"""HTML 自检：结构完整性、内联资源、数据注入、关键文案、潜在 JS 陷阱。"""
import os, re, sys, json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(os.path.dirname(here))
case = os.environ.get('CASE_DIR') or os.path.join(root, 'case')
html_path = os.environ.get('OUT_HTML') or os.path.join(case, 'out', '甲醇供给事件时间线报告.html')

src = open(html_path, encoding='utf-8').read()
fails, warns = [], []


def chk(cond, msg, warn=False):
    if cond:
        print('  PASS', msg)
    else:
        print('  FAIL' if not warn else '  WARN', msg)
        (warns if warn else fails).append(msg)


print('== 文件 ==')
print('  size = %.2f MB' % (len(src.encode('utf-8')) / 1048576))

print('== 结构 ==')
chk('<!DOCTYPE html>' in src, 'doctype')
chk(src.count('<html') >= 1 and '</html>' in src, 'html 闭合')
chk(src.rstrip().endswith('</html>'), '以 </html> 结尾')
chk('__DATA__' not in src, '无未替换的 __DATA__ 占位符')
chk('__TITLE__' not in src, '无未替换的 __TITLE__ 占位符')
chk('__ECHARTS__' not in src, '无未替换的 __ECHARTS__ 占位符')

print('== 内联资源 ==')
chk('echarts' in src[:200000].lower(), 'ECharts 已内联')
chk(src.count('<script') == src.count('</script>'), 'script 标签配对 (open=%d)' % src.count('<script'))

print('== 数据注入 ==')
m = re.search(r'const DATA = (\{.*?\});\n', src, re.S)
chk(bool(m), '找到 DATA 注入')
if m:
    try:
        D = json.loads(m.group(1).replace('<\\/', '</'))
        print('  events=%d planned=%d units=%d' % (len(D['events']), len(D['planned']), len(D['units'])))
        chk(len(D['events']) >= 20, '事件数 >= 20')
        chk(len(D['planned']) >= 5, '未来事项数 >= 5')
        chk(all(e.get('event_id') for e in D['events']), '每个事件有 event_id')
        chk(all(e.get('sources') for e in D['events']), '每个事件有来源')
        n_src = sum(len(e['sources']) for e in D['events'])
        print('  来源总数 = %d' % n_src)
        # 时间窗内
        ws, we = D['meta']['window_start'], D['meta']['window_end']
        bad = [e['event_id'] for e in D['events']
               if e.get('start_date') and not (ws <= e['start_date'] <= we) and not e.get('starts_before_window')]
        chk(not bad, '所有事件起始日落在窗口内 %s' % (bad or ''))
        # 国内已确认事件必须有 loss
        nocl = [e['event_id'] for e in D['events']
                if e['bucket'] == 'domestic_confirmed' and e.get('loss_t') is None]
        chk(not nocl, '国内已确认事件均有减产量 %s' % (nocl or ''))
        # 未确认不计入
        chk(D['summary']['totals']['domestic_loss_t'] > 0, '国内确认减产 > 0')
        print('  domestic=%s 万吨 overseas=%s 万吨' % (D['summary'].get('domestic_loss_wt'),
                                                     D['summary'].get('overseas_loss_wt')))
    except Exception as e:
        fails.append('DATA JSON 解析失败: %s' % e)
        print('  FAIL DATA 解析', e)

print('== 关键文案与功能 ==')
FUNCS = ['renderTimeline', 'renderRank', 'renderRegion', 'renderType', 'renderRoute',
         'renderTable', 'renderPlan', 'openDrawer', 'closeDrawer', 'filtered']
for f in FUNCS:
    chk(('function %s' % f) in src or ('%s=' % f) in src or f in src, '函数/引用存在: %s' % f, warn=True)
chk('计划检修' in src and '实际停车' in src and '复产' in src and '降负荷' in src, '事件类型词表齐全')
chk('煤制' in src and '天然气制' in src and '焦炉气制' in src, '工艺路线区分齐全')
chk('只看已确认事件' in src, '含“只看已确认事件”切换')
chk('含未来计划事件' in src, '含“含未来计划事件”切换')
chk('id="fStatus"' in src and 'id="fType"' in src and 'id="fRegion"' in src and 'id="fRoute"' in src,
    '筛选控件齐全')
chk('不构成供应预警' in src, '含免责声明（不输出预警/价格结论）')
for bid in ['domestic_confirmed', 'overseas', 'unconfirmed', 'stock_stop']:
    chk(bid in src, '口径分桶存在: %s' % bid)

print('== JS 隐患 ==')
# 检查 ganttXY 未使用（死代码）
if 'function ganttXY' in src:
    warns.append('存在未使用的死函数 ganttXY（无害）')
    print('  WARN 死函数 ganttXY')
# 显式编码轴
chk('encode:{x:[0,1],y:2}' in src, 'custom series 使用 encode 指定 x/y 轴')
chk('dataZoom' in src, '含时间轴缩放')
# 括号平衡粗检
for pair in [('{', '}'), ('(', ')'), ('[', ']')]:
    a, b = src.count(pair[0]), src.count(pair[1])
    print('  %s%s  %d / %d' % (pair[0], pair[1], a, b))

print()
print('RESULT:', 'PASS' if not fails else 'FAIL -> ' + '; '.join(fails))
if warns:
    print('WARNINGS:', '; '.join(warns))
sys.exit(0 if not fails else 1)

