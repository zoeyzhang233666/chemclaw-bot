# -*- coding: utf-8 -*-
"""一键自检：数据完整性 → 计算引擎 → Excel → HTML → JS 运行期。

用法：
    python skill/scripts/selftest.py                # 用默认案例（examples 里最新的）
    CASE_DIR=case python skill/scripts/selftest.py  # 指定案例目录
"""
from __future__ import annotations
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)

PY = sys.executable
FAILS, WARNS = [], []


def hdr(t):
    print('\n' + '=' * 62)
    print(' ' + t)
    print('=' * 62)


def ok(msg):
    print('  [PASS] ' + msg)


def bad(msg):
    print('  [FAIL] ' + msg)
    FAILS.append(msg)


def warn(msg):
    print('  [WARN] ' + msg)
    WARNS.append(msg)


def run(cmd, env=None, expect_zero=True):
    e = os.environ.copy()
    if env:
        e.update(env)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', env=e, cwd=os.path.dirname(SKILL))
    out = (p.stdout or '') + (p.stderr or '')
    if expect_zero and p.returncode != 0:
        bad(f'命令失败: {" ".join(cmd)}\n{out[-1500:]}')
    return p.returncode, out


def find_case():
    if os.environ.get('CASE_DIR'):
        return os.path.abspath(os.environ['CASE_DIR'])
    ex = os.path.join(SKILL, 'examples')
    cands = [os.path.join(ex, d, 'case') for d in sorted(os.listdir(ex))] if os.path.isdir(ex) else []
    cands = [c for c in cands if os.path.isfile(os.path.join(c, 'datum.json'))]
    if cands:
        return cands[-1]
    return os.path.join(os.path.dirname(SKILL), 'case')


CASE = find_case()
OUT = os.path.join(tempfile.gettempdir(), 'sell_selftest_out')
os.makedirs(OUT, exist_ok=True)

hdr('0. 环境')
print('  python  :', PY)
print('  skill   :', SKILL)
print('  case    :', CASE)
print('  out     :', OUT)
if not os.path.isdir(CASE):
    bad('案例目录不存在: ' + CASE)
    print('\nRESULT: FAIL')
    sys.exit(1)
ok('案例目录存在')

# ---------------------------------------------------------------- 1. 数据
hdr('1. 数据契约校验')


def J(f):
    p = os.path.join(CASE, f)
    if not os.path.isfile(p):
        bad(f'缺少文件 {f}')
        return None
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception as ex:
        bad(f'{f} 解析失败: {ex}')
        return None


datum = J('datum.json')
comps = J('companies.json')
units_doc = J('units.json')
ev_doc = J('status_events.json')
pl_doc = J('planned_events.json')

if not all([datum, comps, units_doc, ev_doc, pl_doc]):
    print('\nRESULT: FAIL（数据文件缺失）')
    sys.exit(1)
ok('五个数据文件均可解析')

meta = datum['meta']
units = units_doc['units']
events = ev_doc['events']
planned = pl_doc['planned_events']

for k in ('product', 'window_start', 'window_end', 'as_of'):
    if k not in meta:
        bad(f'datum.meta 缺少 {k}')
ok('datum.meta 关键字段齐全')

# unit_id 唯一
ids = [u['unit_id'] for u in units]
if len(ids) != len(set(ids)):
    bad('unit_id 存在重复')
else:
    ok(f'unit_id 唯一（{len(ids)} 套装置）')

# 事件外键
uid = set(ids)
orphan = [e['event_id'] for e in events if e.get('unit_id') not in uid]
if orphan:
    bad(f'事件引用了不存在的 unit_id: {orphan}')
else:
    ok(f'事件外键完整（{len(events)} 条事件）')

# 来源
nosrc = [e['event_id'] for e in events if not e.get('sources')]
if nosrc:
    bad(f'事件缺少来源: {nosrc}')
else:
    ok('每条事件至少 1 个来源')

nourl = [(e['event_id'], s.get('name')) for e in events
         for s in e.get('sources', []) if not s.get('url')]
if nourl:
    bad(f'来源缺少 url: {nourl[:5]}')
else:
    ok('所有来源均有 url')

noquote = [(e['event_id']) for e in events
           for s in e.get('sources', []) if not s.get('quote')]
if noquote:
    warn(f'{len(noquote)} 个来源缺少原文引用')
else:
    ok('所有来源均有原文引用')

# 负荷字段语义（历史 bug 防回归）
print('\n  -- 负荷字段语义检查（关键回归项）')
sem_bad = []
for e in events:
    if e.get('event_type') in ('计划检修', '实际停车', '意外故障', '降负荷'):
        dl = e.get('downtime_load')
        if dl is None:
            sem_bad.append((e['event_id'], 'downtime_load 缺失'))
        elif e['event_type'] in ('计划检修', '实际停车', '意外故障') and dl != 0:
            sem_bad.append((e['event_id'], f'停车类事件 downtime_load={dl}，应为 0'))
        elif not (0 <= float(dl) <= 1):
            sem_bad.append((e['event_id'], f'downtime_load={dl} 越界'))
if sem_bad:
    bad(f'负荷字段语义错误: {sem_bad}')
else:
    ok('停车类事件 downtime_load 均为 0，取值合法')

# 置信度枚举
CONF = {'official', 'industry', 'rumor'}
badc = [e['event_id'] for e in events if e.get('confidence') not in CONF]
if badc:
    bad(f'confidence 非法: {badc}')
else:
    ok('confidence 枚举合法')

# 时间窗口
ws, we = meta['window_start'], meta['window_end']
oob = [e['event_id'] for e in events
       if e.get('start_date') and not (ws <= e['start_date'] <= we)
       and not e.get('starts_before_window')]
if oob:
    bad(f'事件起始日越界且未标记 starts_before_window: {oob}')
else:
    ok('事件起始日均在窗口内或已标记跨窗口')

# 未来事项分离
if any('plan_id' in e for e in events):
    bad('status_events 中混入了 plan_id 字段（应与 planned 分离）')
else:
    ok('已发生事件与未来事项已物理分离')
if not planned:
    warn('planned_events 为空')
else:
    ok(f'未来事项 {len(planned)} 条，独立文件')

# ---------------------------------------------------------------- 2. 引擎
hdr('2. 计算引擎')
import calc_impact as ci

ws_d, we_d = ci.parse_date(ws), ci.parse_date(we)
S = ci.summarize(events, ws_d, we_d, meta.get('national_capacity_wt'),
                 meta.get('weekly_output_t'))
T = S['totals']
print(f"  窗口 {ws} ~ {we}（{S.get('window_days')} 天）")
print(f"  国内确认减产   {S.get('domestic_loss_wt')} 万吨（{T['n_domestic_confirmed']} 起）")
print(f"  境外影响       {S.get('overseas_loss_wt')} 万吨（{T['n_overseas']} 起）")
print(f"  未确认/待核     {S.get('unconfirmed_loss_wt')} 万吨（{T['n_unconfirmed']} 起）")
print(f"  新增产能        {S.get('new_capacity_wt')} 万吨")
print(f"  占窗口内理论产能 {S.get('domestic_loss_pct_window_capacity')}%")
print(f"  折合周产量      {S.get('domestic_loss_weeks')} 周")

if T['domestic_loss_t'] <= 0:
    bad('国内确认减产为 0（很可能负荷语义错配，见历史 bug）')
else:
    ok('国内确认减产 > 0')

if T['n_domestic_confirmed'] == 0:
    bad('没有国内确认事件')

# 量级合理性
pct = S.get('domestic_loss_pct_window_capacity') or 0
if pct > 15:
    bad(f'占窗口产能比例 {pct}% 过高，疑重复计算或混入长期停车')
elif 0 < pct < 0.3:
    warn(f'占窗口产能比例 {pct}% 偏低，可能漏采事件')
else:
    ok(f'量级合理（占窗口内理论产能 {pct}%）')

# 口径互斥完备
buckets = {}
for r in S['rows']:
    buckets[r['bucket']] = buckets.get(r['bucket'], 0) + 1
print('  分桶:', buckets)
if buckets.get('domestic_confirmed', 0) + buckets.get('overseas', 0) + \
   buckets.get('unconfirmed', 0) + buckets.get('stock_stop', 0) + \
   buckets.get('status_only', 0) + buckets.get('new_capacity', 0) != len(S['rows']):
    bad('存在未分桶的事件')
else:
    ok('全部事件已归入互斥分桶')

# 每个国内确认事件都必须有公式与损失量
nof = [r['event_id'] for r in S['rows']
       if r['bucket'] == 'domestic_confirmed' and r.get('loss_t') is None]
if nof:
    bad(f'国内确认事件缺损失量: {nof}')
else:
    ok('国内确认事件均有损失量')

# 公式可读性
sample = next((r for r in S['rows'] if r.get('formula')), None)
if sample:
    print('  公式样例:', sample['formula'])
    ok('公式字符串可生成（可审计）')
else:
    bad('无可展示公式')

# 单事件手工复核
def manual_check(cap, days, k):
    return cap * 10000 / 365 * days * k

ec = {e['event_id']: e for e in events}
mism = []
for r in S['rows']:
    if r['bucket'] != 'domestic_confirmed':
        continue
    e = ec[r['event_id']]
    if e['event_type'] == '降负荷':
        k = float(e.get('baseline_load', 1.0)) - float(e['downtime_load'])
    else:
        k = 1.0
    exp = manual_check(float(e['capacity_wt']), r['days'], k)
    if abs(exp - r['loss_t']) > 1.0:
        mism.append((r['event_id'], exp, r['loss_t']))
if mism:
    bad(f'引擎结果与手工复核不一致: {mism[:4]}')
else:
    ok(f'引擎结果与手工复核一致（{T["n_domestic_confirmed"]} 起事件全部核对）')

# ---------------------------------------------------------------- 3. Excel
hdr('3. Excel 交付物')
xlsx = os.path.join(OUT, 'selftest.xlsx')
rc, out = run([PY, os.path.join(HERE, 'build_excel.py')],
              env={'CASE_DIR': CASE, 'OUT_XLSX': xlsx})
if rc == 0 and os.path.isfile(xlsx):
    ok(f'Excel 生成成功（{os.path.getsize(xlsx)/1024:.0f} KB）')
    rc2, out2 = run([PY, os.path.join(HERE, 'check_xlsx.py')],
                    env={'CASE_DIR': CASE, 'OUT_XLSX': xlsx})
    if rc2 == 0:
        ok('check_xlsx PASS')
        for line in out2.splitlines():
            if '[check]' in line:
                print('    ' + line.strip())
    else:
        bad('check_xlsx FAIL\n' + out2[-1200:])
else:
    bad('Excel 生成失败')

# ---------------------------------------------------------------- 4. HTML
hdr('4. HTML 交付物')
html = os.path.join(OUT, 'selftest.html')
rc, out = run([PY, os.path.join(HERE, 'build_html.py')],
              env={'CASE_DIR': CASE, 'OUT_HTML': html})
if rc == 0 and os.path.isfile(html):
    ok(f'HTML 生成成功（{os.path.getsize(html)/1048576:.2f} MB，单文件）')
    rc2, out2 = run([PY, os.path.join(HERE, 'check_html.py')],
                    env={'CASE_DIR': CASE, 'OUT_HTML': html})
    if rc2 == 0:
        ok('check_html PASS')
    else:
        bad('check_html FAIL\n' + '\n'.join(l for l in out2.splitlines() if 'FAIL' in l))

    # JS 运行期
    js = os.path.join(HERE, 'check_html_runtime.js')
    node = None
    for c in ('node', 'node.exe'):
        try:
            subprocess.run([c, '--version'], capture_output=True, timeout=10)
            node = c
            break
        except Exception:
            continue
    if node:
        rc3, out3 = run([node, js, html])
        if rc3 == 0:
            ok('check_html_runtime PASS（JS 实际解析并执行）')
            for line in out3.splitlines():
                if 'chart' in line:
                    print('    ' + line.strip())
        else:
            bad('check_html_runtime FAIL\n' + out3[-1500:])
    else:
        warn('未找到 node，跳过 JS 运行期校验')
else:
    bad('HTML 生成失败')

# ---------------------------------------------------------------- 5. 交付检查
hdr('5. 红线检查')
src_html = open(html, encoding='utf-8').read() if os.path.isfile(html) else ''
red_lines = [
    ('不构成供应预警', '明确声明不输出预警/价格结论'),
    ('未来已披露', '未来事项独立呈现'),
    ('未确认', '未确认事项单独列示'),
]
for kw, desc in red_lines:
    if kw in src_html:
        ok(desc)
    else:
        bad(f'缺少红线文案: {kw}（{desc}）')

forbid = ['建议做多', '建议做空', '价格上涨', '价格下跌', '看涨', '看跌', '供应紧张']
hits = [w for w in forbid if w in src_html]
if hits:
    bad(f'HTML 中出现价格方向性表述: {hits}')
else:
    ok('无价格方向性表述（不输出价格结论）')

# ---------------------------------------------------------------- 汇总
hdr('结果')
if FAILS:
    print(f'  {len(FAILS)} 项失败：')
    for f in FAILS:
        print('   ×', f.splitlines()[0])
if WARNS:
    print(f'  {len(WARNS)} 项提示：')
    for w in WARNS:
        print('   !', w)
print()
print('RESULT:', 'PASS' if not FAILS else 'FAIL')
sys.exit(0 if not FAILS else 1)
