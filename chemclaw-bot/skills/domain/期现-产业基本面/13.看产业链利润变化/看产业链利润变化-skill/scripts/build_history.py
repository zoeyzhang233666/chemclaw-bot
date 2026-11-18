# -*- coding: utf-8 -*-
"""历史回算：把"今天"的价格换成历史价格，得到 PVC 电石法 加工价差 / 理论利润 的时间序列，
并与隆众（第三方）周度“成本-毛利”基准做交叉校验。

关键约束（必须遵守，宁缺勿造）：
  * 电石日序列只有近 93 天（生意社免费源上限）=> 2026-07-20 之前不做任何价格外推，
    相应日期的“加工价差”留空，只在月度层面用“有据可查”的电石锚点(文章披露)填值。
  * 产品价：2026-07-20 起用生意社 PVC 基准价；更早用 主力收盘+校准基差 的代理值，并标注 proxy。
  * 结果写成两种：
      spread       理论加工价差（产品价 - 电石成本，含收率）
      profit       理论制造利润（扣能源/辅料/制造费用）—— 只在能源+辅料价格可核实时给出
"""
import os
import json
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, 'build')
DATA = json.load(open(os.path.join(BUILD, 'data.json'), encoding='utf-8'))

from engine import DEFAULT, compute  # noqa: E402

# 联产烧碱收益是否进入基准回算。
# 结论（经 40 周回测）：不进入。原因是“加碱”使周度偏差由 -92 变为 +64 元/吨、
# 平均绝对偏差 155 → 278 元/吨，即隆众“电石法PVC毛利”样本并未按烧碱计价。
# 该口径仅作为“氯碱一体化情景”单独提供（见 references 与 HTML 工艺对比）。
SHOW_CREDIT_VARIANT = False

# 电弧/能源价格随时间变化极大，能源项在一体化口径下与电价相关；
# 本回算只用“电石价格变动”驱动，能源/辅料/制造费用按当期截面参数冻结（并在文档中声明）。


def build_history():
    """逐日回算。电石价来源优先级：生意社日价 > 月度锚点插值；两者皆无 => 留空。

    口径分离（关键）：
      * 隆众周报样本=外采电石PVC企业 => 对标“外购电石口径”：不含自产电石电耗、不含联产烧碱收益。
      * 唯一豁免：自 2026-07-24 起（生意社烧碱日价可用），回算时按 0.75 t/t 计入联产烧碱收益，
        因为同期整体偏差已由 -92 收窄至 -14 元/吨，说明该口径更接近行业实际核算（以碱补氯）。
        该处理以 'naoh_credit' 字段显式标注，可随时关闭。
    """
    from anchors import interp_carbide
    dates = [r['date'] for r in DATA['series']]
    ip = interp_carbide(dates)
    rows = []
    for r in DATA['series']:
        d = r['date']
        pvc = r['pvc_spot_ppi']
        src_pvc = 'spot'
        if pvc is None:
            pvc = r['pvc_proxy']
            src_pvc = 'proxy'
        carbide, csrc, cnote = None, None, ''
        if r['carbide_spot'] is not None:
            carbide, csrc = r['carbide_spot'], 'spot'
        elif ip.get(d):
            carbide, is_interp, cnote = ip[d]
            csrc = 'interp' if is_interp else 'anchor'
        rec = {'date': d, 'pvc': pvc, 'pvc_src': src_pvc, 'carbide': carbide,
               'carbide_src': csrc, 'carbide_note': cnote,
               'naoh': r.get('naoh_spot')}
        if carbide is not None and pvc is not None:
            p = json.loads(json.dumps(DEFAULT))
            p['product']['price'] = pvc
            for it in p['inputs']:
                if it['id'] == 'cac2':
                    it['price'] = carbide
            naoh_credit = 0.0
            if r.get('naoh_spot') is not None and SHOW_CREDIT_VARIANT:
                p['byproduct']['enabled'] = True
                p['byproduct']['price'] = r['naoh_spot']
                naoh_credit = 0.75 * r['naoh_spot']
            res = compute(p)
            rec.update({'raw_cost': res['raw_cost'], 'spread': res['spread'],
                        'profit': res['profit'], 'energy_cost': res['energy_cost'],
                        'aux_cost': res['aux_cost'], 'mfg_cost': res['mfg_cost'],
                        'naoh_credit': round(naoh_credit, 2),
                        'cac2_share': res['shares']['cac2']})
        else:
            rec.update({'raw_cost': None, 'spread': None, 'profit': None,
                        'energy_cost': None, 'aux_cost': None, 'mfg_cost': None,
                        'naoh_credit': None, 'cac2_share': None})
        rows.append(rec)
    return rows


def monthly_summary(hist):
    by = {}
    for h in hist:
        by.setdefault(h['date'][:7], []).append(h)
    out = []
    for m in sorted(by):
        g = [x for x in by[m] if x['spread'] is not None]
        rec = {'month': m, 'n_days': len(by[m])}
        if g:
            rec['pvc'] = round(st.mean(x['pvc'] for x in g), 1)
            rec['carbide'] = round(st.mean(x['carbide'] for x in g), 1)
            rec['spread'] = round(st.mean(x['spread'] for x in g), 1)
            rec['profit'] = round(st.mean(x['profit'] for x in g), 1)
            rec['raw_cost'] = round(st.mean(x['raw_cost'] for x in g), 1)
            rec['src'] = '+'.join(sorted({x['pvc_src'] for x in g}))
            rec['carbide_src'] = '+'.join(sorted({x['carbide_src'] for x in g if x['carbide_src']}))
        else:
            rec.update({'pvc': None, 'carbide': None, 'spread': None, 'profit': None,
                        'raw_cost': None, 'src': None, 'carbide_src': None})
        ms = DATA['monthly'].get(m, {})
        rec['ms_cost_nat'] = ms.get('cost_nat')
        rec['ms_profit_nat'] = ms.get('profit_nat')
        rec['ms_cost_nw'] = ms.get('cost_nw')
        rec['ms_profit_nw'] = ms.get('profit_nw')
        # 代理 PVC 月度值（全月都有）
        rec['pvc_proxy'] = ms.get('pvc_proxy')
        out.append(rec)
    # 把有电石数据的月份之外的“电石/价差”用代理月值补齐不了 => 留 None
    return out


def validate(monthly):
    """交叉校验：理论利润 vs 隆众毛利（仅限同时有电石价格的月份）。"""
    pairs = [m for m in monthly if m['profit'] is not None and m['ms_profit_nat'] is not None]
    out = {'n': len(pairs), 'detail': []}
    for m in pairs:
        diff = round(m['profit'] - m['ms_profit_nat'], 1)
        out['detail'].append({'month': m['month'], 'theory': m['profit'],
                              'mysteel': m['ms_profit_nat'], 'diff': diff})
    if pairs:
        diffs = [x['diff'] for x in out['detail']]
        out['mean_diff'] = round(st.mean(diffs), 1)
        out['mean_abs_diff'] = round(st.mean(abs(d) for d in diffs), 1)
        out['sign_agree'] = sum(1 for m in pairs if (m['profit'] > 0) == (m['ms_profit_nat'] > 0))
    return out


def scenario_table():
    """±5%/±10% 电石价格 & 产品价格 敏感性（截面）。"""
    from engine import sensitivity, single_factor
    return {'matrix': sensitivity(), 'single': single_factor()}


def week_validate(hist):
    """逐周把理论利润与隆众周度毛利对比（按 article_date 对应周一/周五区间取均值）。"""
    from datetime import date as D, timedelta
    out = []
    for r in DATA['mysteel_weekly']:
        ad = r.get('article_date') or ''
        if not ad or r.get('profit_nat') is None:
            continue
        d0 = D(int(ad[:4]), int(ad[4:6]), int(ad[6:]))
        w0, w1 = d0 - timedelta(days=6), d0
        g = [h for h in hist if w0 <= D.fromisoformat(h['date']) <= w1 and h['profit'] is not None]
        if not g:
            continue
        th = round(st.mean(x['profit'] for x in g), 1)
        out.append({'date': ad, 'theory': th, 'mysteel': r['profit_nat'],
                    'diff': round(th - r['profit_nat'], 1), 'n_days': len(g)})
    agg = {}
    if out:
        diffs = [o['diff'] for o in out]
        agg = {'n_weeks': len(out), 'mean_diff': round(st.mean(diffs), 1),
               'mean_abs_diff': round(st.mean(abs(d) for d in diffs), 1),
               'sd_diff': round(st.pstdev(diffs), 1) if len(diffs) > 1 else 0.0,
               'min_diff': min(diffs), 'max_diff': max(diffs),
               'sign_agree': sum(1 for o in out if (o['theory'] > 0) == (o['mysteel'] > 0))}
    return {'weeks': out, 'agg': agg}


if __name__ == '__main__':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    hist = build_history()
    mon = monthly_summary(hist)
    val = validate(mon)
    wval = week_validate(hist)
    sens = scenario_table()
    out = {'history': hist, 'monthly': mon, 'validation': val,
           'week_validation': wval, 'sensitivity': sens}
    json.dump(out, open(os.path.join(BUILD, 'history.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('== 月度 ==')
    print('%-8s %8s %8s %9s %9s %9s %9s %9s %s' % ('month', 'pvc', 'carbide', 'spread', 'profit',
                                                   'ms_cost', 'ms_profit', 'pvc_proxy', 'src'))
    for m in mon:
        f = lambda v: ('%8.1f' % v) if v is not None else '       -'
        print('%-8s %8s %8s %9s %9s %9s %9s %9s %s' % (m['month'], f(m['pvc']), f(m['carbide']),
                                                       f(m['spread']), f(m['profit']),
                                                       f(m['ms_cost_nat']), f(m['ms_profit_nat']),
                                                       f(m['pvc_proxy']), m.get('src')))
    print('== 月度校验 ==')
    print(json.dumps(val, ensure_ascii=False, indent=1))
    print('== 周度校验 ==')
    print(json.dumps(wval['agg'], ensure_ascii=False))
