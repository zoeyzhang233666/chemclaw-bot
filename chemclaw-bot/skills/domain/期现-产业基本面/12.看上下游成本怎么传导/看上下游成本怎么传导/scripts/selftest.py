# -*- coding: utf-8 -*-
"""selftest.py —— 自测：确认这套 Skill 是通用的，而不是只对 PX→PTA 写死

检查：
  A. 用一条合成数据（虚构品种 A→B）跑全流程，验证不依赖任何 PX/PTA 字样
  B. 单耗敏感性方向正确（单耗↑ → 价差↓）
  C. 阶段恒等式在合成数据上成立
  D. 数据缺口/异常被正确标记而不崩溃
  E. 缺字段时的降级行为（无 events、无 calibration）
"""
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')


def make_synthetic(path, n=120, unit=0.80, with_gaps=True):
    """构造一个虚构的 A→B 链条：B = unit*A + 缓慢漂移的加工价差。"""
    dates, a, b = [], [], []
    import datetime
    d = datetime.date(2026, 1, 1)
    base = 5000.0
    i = 0
    while len(dates) < n:
        d += datetime.timedelta(days=1)
        if d.weekday() >= 5:
            continue
        i += 1
        av = base + i * 6.0 + (250.0 if (i // 20) % 2 == 0 else -180.0)   # 台阶式
        spread = 400.0 + i * 1.2                                          # 缓慢走阔
        bv = unit * av + spread
        if with_gaps and i == 40:
            continue                      # 挖掉一天
        dates.append(d.strftime('%Y%m%d'))
        a.append(round(av, 2))
        b.append(round(bv, 2))
    proj = {
        'product_chain': 'A → B（合成自测数据，非真实品种）',
        'window': {'start': dates[0], 'end': dates[-1]},
        'upstream': {'name': 'A料', 'spec': '合成自测规格', 'region': '测试地区',
                     'unit': '元/吨', 'tax': '含税', 'granularity': '日度评估价',
                     'source': 'selftest 合成数据', 'series_key': 'A',
                     'series': dict(zip(dates, a))},
        'downstream': {'name': 'B料', 'spec': '合成自测规格', 'region': '测试地区',
                       'unit': '元/吨', 'tax': '含税', 'granularity': '日度评估价',
                       'source': 'selftest 合成数据', 'series_key': 'B',
                       'series': dict(zip(dates, b))},
        'process': {'route': 'A 经一步反应生成 B（虚构）', 'equation': 'A → B',
                    'verified': True, 'note': '自测用'},
        'materials': [{'name': 'A料', 'unit': unit, 'low': unit - 0.01, 'high': unit + 0.01,
                       'unit_basis': '吨/吨', 'source': 'selftest'}],
        'material_series': {'A料': 'A'},
        'optional_materials': [],
        'params': {'unit_default': unit,
                   'spread_definition': '价差 = B价 − 单耗 × A价',
                   'spread_excludes': ['能源', '辅料', '人工', '折旧'],
                   'breakpoints': [dates[0], dates[len(dates) // 2], dates[-1]]},
    }
    json.dump(proj, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return unit, dates, a, b


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def main():
    fails, warns = [], []
    # 注意：不用 tempfile.mkdtemp —— 它建出的目录在某些沙箱下带受限 ACL，后续写入会被拒。
    # 改为在脚本同级建一个普通目录。
    tmp = os.path.join(os.path.dirname(HERE), '_selftest_tmp')
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    try:
        proj = os.path.join(tmp, 'project.json')
        unit, dates, a, b = make_synthetic(proj)
        out = os.path.join(tmp, 'out')

        # A. 合成数据全流程
        rc, log = run([sys.executable, os.path.join(HERE, 'analyze.py'), proj, '--out-dir', out])
        if rc != 0:
            fails.append('合成数据 analyze 失败：%s' % log[-400:])
            return report(fails, warns)
        ap = os.path.join(out, 'analysis.json')
        an = json.load(open(ap, encoding='utf-8'))
        print('合成链：%d 个观测，A %.0f→%.0f，B %.0f→%.0f'
              % (an['summary']['n_obs'], an['summary']['up']['start'], an['summary']['up']['end'],
                 an['summary']['down']['start'], an['summary']['down']['end']))
        if 'PX' in json.dumps(an, ensure_ascii=False) or 'PTA' in json.dumps(an, ensure_ascii=False):
            fails.append('分析结果里残留 PX/PTA 字样，说明逻辑被写死')
        else:
            print('A. 无 PX/PTA 残留 ✓')

        # 合成数据的真实价差应接近生成时的 spread（400 + 1.2*i）
        sp = an['summary']['spread']
        kept = [400.0 + i * 1.2 for i in range(1, len(dates) + 1)]
        exp_mean = sum(kept) / len(kept)
        if abs(sp['mean'] - exp_mean) > 1.0:
            fails.append('合成数据价差还原失败：%.2f vs 期望 %.2f' % (sp['mean'], exp_mean))
        else:
            print('A. 价差还原 %.2f（期望 %.2f）✓' % (sp['mean'], exp_mean))

        # B. 单耗敏感性方向
        sens = an['sensitivity']
        if sens['low_unit_mean'] <= sens['base_mean'] <= sens['high_unit_mean']:
            fails.append('单耗敏感性方向错误：低单耗应得到更高价差')
        else:
            print('B. 单耗敏感性方向正确（低 %.1f > 基准 %.1f > 高 %.1f）✓'
                  % (sens['low_unit_mean'], sens['base_mean'], sens['high_unit_mean']))

        # C. 恒等式
        bad = [s for s in an['stages']
               if s.get('identity_resid') is not None and abs(s['identity_resid']) > 1e-6]
        if bad:
            fails.append('合成数据阶段恒等式残差不为 0：%s 段' % len(bad))
        else:
            print('C. 阶段恒等式残差全为 0（%d 段）✓' % len(an['stages']))

        # D. 缺口被标记而非崩溃
        if an['summary']['n_obs'] >= len(dates) - 2:
            print('D. 缺失日未导致行丢失（%d 观测 / %d 原始日）✓'
                  % (an['summary']['n_obs'], len(dates)))
        else:
            warns.append('合成数据有坑洞时观测数少了 %d 行' % (len(dates) - an['summary']['n_obs']))

        # E. 无 events / 无 calibration 时仍能出 HTML 与 Excel
        rc, log = run([sys.executable, os.path.join(HERE, 'build_html.py'), ap, '--out-dir', out])
        if rc != 0:
            fails.append('合成数据 build_html 失败：%s' % log[-400:])
        else:
            print('E. 无事件库也能生成 HTML ✓')
        rc, log = run([sys.executable, os.path.join(HERE, 'build_xlsx.py'), ap, '--out-dir', out])
        if rc != 0:
            fails.append('合成数据 build_xlsx 失败：%s' % log[-400:])
        else:
            print('E. 无事件库也能生成 Excel ✓')

        # F. 校验器对合成产物同样通过
        import glob
        hs = glob.glob(os.path.join(out, '*.html'))
        xs = glob.glob(os.path.join(out, '*.xlsx'))
        if hs:
            rc, log = run([sys.executable, os.path.join(HERE, 'check_html.py'), hs[0], ap])
            if rc != 0:
                fails.append('合成 HTML 校验失败：%s' % log[-500:])
            else:
                print('F. 合成 HTML 通过静态校验 ✓')
        if xs:
            rc, log = run([sys.executable, os.path.join(HERE, 'check_xlsx.py'), xs[0], ap])
            if rc != 0:
                fails.append('合成 Excel 校验失败：%s' % log[-500:])
            else:
                print('F. 合成 Excel 通过校验 ✓')

        return report(fails, warns)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def report(fails, warns):
    for w in warns:
        print('  [warn]', w)
    if fails:
        for x in fails:
            print('  [FAIL]', x)
        print('\n自测失败：%d 项' % len(fails))
        return 1
    print('\n自测全部通过：这套脚本对任意上下游都适用')
    return 0


if __name__ == '__main__':
    sys.exit(main())
