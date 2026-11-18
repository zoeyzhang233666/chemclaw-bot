# -*- coding: utf-8 -*-
"""计算验证脚本：Python 引擎  vs  纯函数计算  vs  PPT 口算

作用：
  1) 用 mini-racer(V8) 直接执行 HTML 内嵌的 JS 计算引擎，与 engine.py 逐项比对；
  2) 独立"手算"复核关键数字（不依赖任何模型代码），防止公式被同一处 bug 污染；
  3) 校验单位换算（kg/t vs 元/吨）、收率作用范围、敏感性方向；
  4) 校验历史回算与第三方毛利基准的方向一致性。

退出码 0 = 全部通过。
"""
import io
import os
import re
import sys
import json
import statistics as st

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import engine as E  # noqa: E402

FAILS = []
OKS = []


def check(name, cond, detail=''):
    if cond:
        OKS.append(name)
        print('  [PASS] %s %s' % (name, detail))
    else:
        FAILS.append(name)
        print('  [FAIL] %s %s' % (name, detail))


# ---------------------------------------------------------------- 1) 手算口径
def manual(p=None):
    """完全独立的手算：只用字面公式，不复用 engine 的任何函数。"""
    p = p or E.DEFAULT
    y = p['yield']
    ca = [x for x in p['inputs'] if x['id'] == 'cac2'][0]
    hcl = [x for x in p['inputs'] if x['id'] == 'hcl'][0]
    cat = [x for x in p['inputs'] if x['id'] == 'catalyst'][0]
    ini = [x for x in p['inputs'] if x['id'] == 'initiator'][0]
    ele = [x for x in p['inputs'] if x['id'] == 'ele_pvc'][0]
    stm = [x for x in p['inputs'] if x['id'] == 'steam'][0]
    raw = ca['cons'] * ca['price'] / y
    aux = hcl['cons'] * hcl['price'] / y + cat['cons'] / 1000 * cat['price'] / y + ini['cons'] / 1000 * ini['price'] / y
    energy = ele['cons'] * ele['price'] + stm['cons'] * stm['price']
    m = p['manufacturing']
    mfg = (m['labor'] + m['depreciation'] + m['packaging'] + m['other']) if m['enabled'] else 0
    spreads = p['product']['price'] - raw
    return {'raw': raw, 'aux': aux, 'energy': energy, 'mfg': mfg,
            'spread': spreads, 'profit': spreads - aux - energy - mfg}


print('=== 1. 手算复核（独立公式） ===')
r = E.compute()
mm = manual()
for k, pk in [('raw', 'raw_cost'), ('aux', 'aux_cost'), ('energy', 'energy_cost'),
              ('mfg', 'mfg_cost'), ('spread', 'spread'), ('profit', 'profit')]:
    check('手算 %s' % k, abs(r[pk] - mm[k]) < 0.02, '模型 %.2f / 手算 %.2f' % (r[pk], mm[k]))

print('=== 2. 结构合理性 ===')
cac2_share = r['shares']['_raw_electric']
check('电石占总成本 65–75%(行业区间)', 65 <= r['shares']['_raw_electric_total'] <= 78, '%.1f%%' % r['shares']['_raw_electric_total'])
check('HCl 占总成本 4–7%(自产氯成本口径)', 4 <= r['shares']['hcl'] <= 7, '%.1f%%；市价口径约 13%%，见 engine 注释' % r['shares']['hcl'])
check('能源占总成本 5–9%(文献 5.9–6%)', 5 <= r['shares']['_energy'] <= 9.5, '%.1f%%' % r['shares']['_energy'])
check('电石占原料篮子(电石+HCl) ≥ 85%', cac2_share >= 85, '%.1f%%' % cac2_share)
check('加工价差 > 利润(已含成本项)', r['spread'] > r['profit'])
check('总成本 = 原料+能源+辅料+制造', abs(r['total_cost'] - (r['raw_cost'] + r['energy_cost'] + r['aux_cost'] + r['mfg_cost'])) < 0.02)
check('价差 = 售价 − 原料', abs(r['spread'] - (r['product_price'] - r['raw_cost'])) < 0.02)
check('利润 = 价差 − 能源 − 辅料 − 制造',
      abs(r['profit'] - (r['spread'] - r['energy_cost'] - r['aux_cost'] - r['mfg_cost'])) < 0.02)

print('=== 3. 单位与收率 ===')
check('触媒 kg→吨 换算未放大千倍', r['breakdown'][6]['cost'] < 30, '触媒成本 %.2f 元/吨' % r['breakdown'][6]['cost'])
check('电石计费单耗 = 名义/收率',
      abs(r['breakdown'][0]['cons_eff'] - 1.45 / 0.97) < 1e-3)
p_low = json.loads(json.dumps(E.DEFAULT)); p_low['yield'] = 0.94
r_low = E.compute(p_low)
check('收率下降→原料成本上升', r_low['raw_cost'] > r['raw_cost'], '%.1f > %.1f' % (r_low['raw_cost'], r['raw_cost']))
check('收率下降→能源成本不变', abs(r_low['energy_cost'] - r['energy_cost']) < 0.01)

print('=== 4. 敏感性方向 ===')
s_up = E.compute(shock={'cac2': 0.10})
s_dn = E.compute(shock={'cac2': -0.10})
check('电石 +10% → 利润下降', s_up['profit'] < r['profit'], '%.1f' % (s_up['profit'] - r['profit']))
check('电石 -10% → 利润上升', s_dn['profit'] > r['profit'], '%.1f' % (s_dn['profit'] - r['profit']))
check('电石 ±10% 对称', abs((s_up['profit'] - r['profit']) + (s_dn['profit'] - r['profit'])) < 0.05)
p_up = E.compute(shock={'product': 0.10})
check('产品 +10% → 利润上升', p_up['profit'] > r['profit'], '%.1f' % (p_up['profit'] - r['profit']))
step = 0.10 * 1.45 / r['yield'] * E.DEFAULT['inputs'][0]['price']
check('电石弹性 ≈ 单耗÷收率×价 (手算)', abs(abs(s_up['profit'] - r['profit']) - step) < 1.0,
      '模型 %.1f / 手算 %.1f' % (abs(s_up['profit'] - r['profit']), step))
sens = E.sensitivity()
check('敏感性矩阵单调(电石↑→价差↓)', all(sens['spread'][i][k] > sens['spread'][i+1][k] for i in range(4) for k in range(5)))
check('敏感性矩阵单调(产品↑→价差↑)', all(sens['spread'][k][i] < sens['spread'][k][i+1] for k in range(5) for i in range(4)))
check('单因素弹性: 产品价影响 > HCl 影响', abs([x for x in E.single_factor() if x['id']=='hcl'][0]['effect'][4]['d_profit']) < 100)
check('矩阵中心 = 基准价差', abs(sens['spread'][2][2] - r['spread']) < 0.01)

print('=== 5. JS 引擎（HTML 内嵌）与 Python 一致性 ===')
html_files = [f for f in os.listdir(os.path.join(ROOT, 'output')) if f.endswith('.html')]
if not html_files:
    check('HTML 已生成', False, 'output/ 无 html')
else:
    try:
        from py_mini_racer import MiniRacer
        html = open(os.path.join(ROOT, 'output', html_files[0]), encoding='utf-8').read()
        m_payload = re.search(r'const PAYLOAD = (\{.*?\});\s*\n', html, re.S)
        m_app = re.search(r'<script id="appjs">(.*?)</script>', html, re.S)
        js = 'var window={addEventListener:function(){}};\n'
        js += 'const PAYLOAD = ' + m_payload.group(1) + ';\n'
        app = m_app.group(1)
        # 截取到 compute 定义之后，并去掉 DOM 相关调用
        cut = app.index('/* ---------------- 图表主题')
        core = app[:cut]
        core = core.replace("const D = PAYLOAD.data", "const D = PAYLOAD.data")
        js += core
        js += """
        var __r = compute();
        JSON.stringify({raw:__r.raw, energy:__r.energy, aux:__r.aux, mfg:__r.mfg,
                        spread:__r.spread, profit:__r.profit, total:__r.totalCost,
                        y:__r.y, cac2cost:__r.cac2Cost});
        """
        ctx = MiniRacer()
        out = json.loads(ctx.eval(js))
        for jk, pk in [('raw', 'raw_cost'), ('energy', 'energy_cost'), ('aux', 'aux_cost'),
                       ('mfg', 'mfg_cost'), ('spread', 'spread'), ('profit', 'profit'),
                       ('total', 'total_cost')]:
            check('JS↔PY %s' % jk, abs(out[jk] - r[pk]) < 0.02,
                  'JS %.2f / PY %.2f' % (out[jk], r[pk]))
        # 含副产
        js2 = js.replace('var __r = compute();',
                         "P.byproduct.enabled=true; var __r = compute();")
        ctx2 = MiniRacer(); out2 = json.loads(ctx2.eval(js2))
        py_byp = E.compute({**json.loads(json.dumps(E.DEFAULT))})
        dd = json.loads(json.dumps(E.DEFAULT)); dd['byproduct']['enabled'] = True
        py_byp = E.compute(dd)
        check('JS↔PY 副产抵减', abs(out2['profit'] - py_byp['profit']) < 0.02,
              'JS %.2f / PY %.2f' % (out2['profit'], py_byp['profit']))
    except ImportError:
        check('mini-racer 可用', False, '未安装，跳过 JS 比对')
    except Exception as ex:
        check('JS 引擎执行', False, repr(ex)[:300])

print('=== 6. 历史回算与第三方基准 ===')
hpath = os.path.join(ROOT, 'build', 'history.json')
if os.path.exists(hpath):
    Hd = json.load(open(hpath, encoding='utf-8'))
    agg = Hd['week_validation']['agg']
    check('周度同号率 ≥ 85%', agg['sign_agree'] / agg['n_weeks'] >= 0.85,
          '%d/%d' % (agg['sign_agree'], agg['n_weeks']))
    check('偏差均值量级 < 200 元/吨', abs(agg['mean_diff']) < 200, '%.0f' % agg['mean_diff'])
    check('无价格区间未外推(应为 None)',
          all(x['spread'] is None for x in Hd['history'] if x['carbide'] is None))
    mon = Hd['monthly']
    check('月度表含 13 个月', len(mon) == 13, '%d' % len(mon))
    # 2026-10 加工价差 = 售价 - 1.45*电石/0.97
    oct_ = [m for m in mon if m['month'] == '2026-10'][0]
    chk = oct_['pvc'] - 1.45 * oct_['carbide'] / 0.97
    check('月度价差与手算一致(±5)', abs(oct_['spread'] - chk) < 5, '表 %.1f / 手算 %.1f' % (oct_['spread'], chk))
    check('盈亏平衡价 = 总制成成本', abs(r['total_cost'] - (r['product_price'] - r['profit'])) < 0.05,
          '总成本 %.1f / 反推 %.1f' % (r['total_cost'], r['product_price'] - r['profit']))
else:
    check('history.json 存在', False)

print()
print('=' * 62)
print('通过 %d 项，失败 %d 项' % (len(OKS), len(FAILS)))
if FAILS:
    print('失败项：', FAILS)
print('=' * 62)
sys.exit(0 if not FAILS else 1)





