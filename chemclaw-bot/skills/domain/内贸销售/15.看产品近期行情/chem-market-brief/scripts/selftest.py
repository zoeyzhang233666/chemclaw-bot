# -*- coding: utf-8 -*-
"""一键回归：两个范本 + 降级路径 + 反例，验证整套自检是否真的有效。

用法（在 scripts/ 下）：
  python selftest.py
返回码 0 = 全部通过。
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING='utf-8')


def run(args, cwd=HERE):
    p = subprocess.run([PY] + args, cwd=cwd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=ENV)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def head(name):
    print('\n' + '=' * 62)
    print('##', name)
    print('=' * 62)


fails = []


def expect(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        fails.append(msg)


# ---------------------------------------------------------------- 1. 两个范本
for ex, nm in [('01-soda-ash-national', '纯碱-全国'), ('02-glass-shahe', '玻璃-沙河')]:
    head('范本 %s（应 0 error / 0 失败）' % ex)
    d = os.path.join(ROOT, 'examples', ex)
    rc, out = run(['validate.py', os.path.join(d, 'research.json')])
    print(out.strip().splitlines()[-1] if out.strip() else '')
    expect('0 error' in out, '%s validate 0 error' % ex)

    rc, out = run(['assemble.py', os.path.join(d, 'research.json'),
                   '--out', os.path.join(d, 'build', 'data.json')])
    expect(rc == 0 and '已生成' in out, '%s assemble' % ex)
    print('   ' + [l for l in out.splitlines() if '摘要' in l][0].strip()[:150])

    html = os.path.join(d, 'output', nm + '_行情看板.html')
    xlsx = os.path.join(d, 'output', nm + '_行情与销售事实.xlsx')
    rc, out = run(['build_html.py', os.path.join(d, 'build', 'data.json'), '--out', html])
    expect(rc == 0, '%s rebuild from current template' % ex)
    rc, out = run(['check_html.py', html, os.path.join(d, 'build', 'data.json')])
    print(out.strip().splitlines()[-1] if out.strip() else '')
    expect(' 0 error ' in out, '%s check_html 0 error' % ex)

    rc, out = run(['check_xlsx.py', xlsx, os.path.join(d, 'build', 'data.json')])
    print(out.strip().splitlines()[-1] if out.strip() else '')
    expect(' 0 error ' in out, '%s check_xlsx 0 error' % ex)

    rc, out = run(['qa_render.py', html, os.path.join(d, 'build', 'data.json')])
    if 'playwright' in out and '跳过' in out:
        print('  skip qa_render（未安装 playwright）')
    else:
        print(out.strip().splitlines()[-1] if out.strip() else '')
        expect('0 项失败' in out, '%s qa_render 0 失败' % ex)

# ---------------------------------------------------------------- 2. 降级路径
head('降级路径：无期货 + 只有 1 条现货（应能出片且模块显示缺口）')
tmp = tempfile.mkdtemp(prefix='cmb-degrade-')
R = {
    "meta": {"product": "硫酸", "spec": "98% 工业级", "region": "华东",
             "asof": "2026-10-19", "unit": "元/吨"},
    "spot": [{"region": "华东", "sub": "江苏 · 98%（出厂）", "product": "硫酸 98%",
              "lo": 380, "hi": 420, "tax": "含税", "basis": "出厂价", "date": "2026-10-16",
              "conf": "中", "note": "区间报价", "src": "降级测试"}],
    "upstream": [{"name": "硫磺", "value": None, "unit": "", "chg": "未取得", "date": "",
                  "direction": "gap", "logic": "硫磺制酸主要原料", "src": "缺口"}],
    "gaps": [{"item": "无场内期货", "status": "缺口", "detail": "硫酸无期货合约",
              "impact": "无法给历史分位", "fix": "用周度均价序列替代"}],
    "caveats": ["降级测试用，不可对外。"],
    "sources": [{"name": "降级测试", "date": "2026-10-16", "type": "测试", "url": ""}],
}
p = os.path.join(tmp, 'research.json')
with io.open(p, 'w', encoding='utf-8') as f:
    json.dump(R, f, ensure_ascii=False, indent=1)
rc, out = run(['build_all.py', p, '--out', os.path.join(tmp, 'out'), '--skip-validate'])
expect(rc == 0, '降级路径整体 rc=0')
expect(os.path.exists(os.path.join(tmp, 'out', '硫酸-华东_行情看板.html')), '降级路径仍产出 HTML')
expect(os.path.exists(os.path.join(tmp, 'out', '硫酸-华东_行情与销售事实.xlsx')), '降级路径仍产出 Excel')
expect('0 error' in out, '降级路径自检 0 error')
print('   ' + [l for l in out.splitlines() if 'summary' in l or '现货' in l][-1].strip()[:150])

# ---------------------------------------------------------------- 3. 反例
head('反例：预言 + 坏日期 + 空报价（必须被判 error）')
bad = json.load(io.open(os.path.join(ROOT, 'examples', '01-soda-ash-national', 'research.json'),
                        encoding='utf-8'))
bad['facts'][0]['note'] = '后市看涨，建议月底前备货'
bad['meta']['asof'] = '2026-13-45'
bp = os.path.join(tmp, 'bad.json')
bad['futures']['series'] = os.path.join(ROOT, 'examples', '01-soda-ash-national', 'raw', '纯碱_daily.json')
with io.open(bp, 'w', encoding='utf-8') as f:
    json.dump(bad, f, ensure_ascii=False, indent=1)
rc, out = run(['validate.py', bp])
expect(rc != 0, 'validate 拒绝坏输入')
expect('不是可解析日期' in out, 'validate 抓到坏日期')
expect('看涨' in out, 'validate 抓到预测词')
expect('备货' in out, 'validate 抓到囤货建议')
print('   ' + out.strip().splitlines()[-1])

head('反例：把预测写进 data.json（check_html / check_xlsx 必须拒绝）')
D = json.load(io.open(os.path.join(ROOT, 'examples', '02-glass-shahe', 'build', 'data.json'),
                      encoding='utf-8'))
D['facts'][0]['note'] = '玻璃预计上涨，建议月底前备货'
D['talk'][0]['a'] = '现在基本见底，可以抄底'
dp = os.path.join(tmp, 'bad_data.json')
with io.open(dp, 'w', encoding='utf-8') as f:
    json.dump(D, f, ensure_ascii=False)
bh = os.path.join(tmp, 'bad.html')
run(['build_html.py', dp, '--out', bh])
rc, out = run(['check_html.py', bh, dp])
expect(rc != 0, 'check_html 拒绝')
expect('预计上涨' in out, 'check_html 抓到「预计上涨」')
expect('抄底' in out, 'check_html 抓到「抄底」')

bx = os.path.join(tmp, 'bad.xlsx')
run(['build_xlsx.py', dp, '--out', bx])
rc, out = run(['check_xlsx.py', bx, dp])
expect(rc != 0, 'check_xlsx 拒绝')
print('   ' + out.strip().splitlines()[-2])

shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------- 汇总
print('\n' + '=' * 62)
if fails:
    print('== 自检失败 %d 项 ==' % len(fails))
    for f in fails:
        print('  -', f)
    sys.exit(1)
print('== 全部通过 ==')
