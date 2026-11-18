# -*- coding: utf-8 -*-
"""技能自测：不联网、不依赖真实数据，用样例配置跑通全链路并验证判定规则。

用法（在技能根目录）：
  python scripts/selftest.py

覆盖：
1. 变化检测：基线空位不得与陈旧值相减、首次出现判「新增」、陈旧天数正确；
2. 主连换月：跳接日改用日内涨跌，不得当成真实单日涨跌；
3. 事件去重：转载合并、旧闻降级为 B、泛评判 C；
4. 方向性表述过滤：条件句放行、预测性结论拦截；
5. 重要性分级：阈值边界；
6. 交易日与日期工具。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common
import dedupe
import assemble

FAIL = []
OK = []


def chk(cond, msg):
    (OK if cond else FAIL).append(msg)


def test_change_detection():
    """基线里是空位（上期未发布）时，不能与陈旧值相减，必须判为新增。"""
    base_map = {'X1': {'value': None, 'date': None, 'report_date': '2026-10-16'}}
    cfg = {'id': 'X1', 'product': '甲醇', 'module': 'inventory', 'name': '测试指标',
           'current': 41.33, 'data_date': '2026-10-15', '_report_date': '2026-10-20'}
    row = assemble.build_indicator(cfg, base_map)
    chk(row['is_new'] is True, '基线空位应判为新增指标')
    chk(row['abs'] is None, '新增指标不应有变动值（不能与空值相减）')
    chk(row['stale_days'] == 5, '陈旧天数应为 5（10-15 → 10-20），实际 %s' % row['stale_days'])

    # 基线有值：正常相减
    base_map2 = {'X2': {'value': 37.41, 'date': '2026-10-08', 'report_date': '2026-10-16'}}
    cfg2 = dict(cfg, id='X2', current=41.33)
    row2 = assemble.build_indicator(cfg2, base_map2)
    chk(row2['is_new'] is False and abs(row2['abs'] - 3.92) < 1e-9,
        '有基线时应算出 +3.92，实际 %s' % row2['abs'])

    # 上一期沿用了源头未更新（上期值与本期完全相同）→ 必须回退到配置基线
    base_map3 = {'X3': {'value': 41.33, 'date': '2026-10-15', 'report_date': '2026-10-16'}}
    cfg3 = {'id': 'X3', 'product': '甲醇', 'module': 'inventory', 'name': '测试指标',
            'current': 41.33, 'data_date': '2026-10-15',
            'base': 37.41, 'base_date': '2026-10-08', '_report_date': '2026-10-20'}
    row3 = assemble.build_indicator(cfg3, base_map3)
    chk(abs((row3['abs'] or 0) - 3.92) < 1e-9,
        '上一期沿用旧值时应回退到配置基线 +3.92，实际 %s' % row3['abs'])


def test_main_contract_roll():
    rows = [{'d': '2026-10-19', 'o': 3100, 'c': 3143, 'h': 3150, 'l': 3090},
            {'d': '2026-10-20', 'o': 3500, 'c': 3480, 'h': 3520, 'l': 3470}]
    dp = assemble.main_contract_day_pct(rows, rows[1], rows[0])
    chk(dp['rolled'] is True, '开盘跳接 11%% 应识别为换月')
    chk(abs(dp['pct'] - round((3480 / 3500 - 1) * 100, 2)) < 0.01,
        '换月日应改用日内涨跌，实际 %s' % dp['pct'])

    normal = [{'d': '2026-10-19', 'o': 3150, 'c': 3143, 'h': 3160, 'l': 3130},
              {'d': '2026-10-20', 'o': 3140, 'c': 3117, 'h': 3150, 'l': 3100}]
    dp2 = assemble.main_contract_day_pct(normal, normal[1], normal[0])
    chk(dp2['rolled'] is False, '正常连续日不应判为换月')
    chk(abs(dp2['pct'] - round((3117 / 3143 - 1) * 100, 2)) < 0.01,
        '正常日应为收盘/昨收，实际 %s' % dp2['pct'])


def test_event_dedupe():
    events = [
        {'id': 'A1', 'products': ['甲醇'], 'event_type': 'geo', 'entity': '霍尔木兹海峡',
         'title': '海峡遇袭致集装箱船沉没', 'detail': '通航受限', 'event_date': '2026-10-16',
         'quant': '日均通航 170 艘降至 8-20 艘', 'impact_path': 'x', 'status': 'ongoing',
         'source': 'S1', 'source_url': ''},
        # 同一事件的改写转载：实体同、数字同、日期近
        {'id': 'A2', 'products': ['PP', 'PVC'], 'event_type': 'geo', 'entity': '霍尔木兹海峡',
         'title': '霍尔木兹海峡周边航线再遭袭击', 'detail': '油轮遇袭', 'event_date': '2026-10-15',
         'quant': '日均通航 170 艘降至 8-20 艘', 'impact_path': 'x', 'status': 'ongoing',
         'source': 'S2', 'source_url': ''},
        # 旧闻：发生在基线之前
        {'id': 'A3', 'products': ['甲醇'], 'event_type': 'plant', 'entity': '国能榆林',
         'title': '国能榆林装置停车', 'detail': '180 万吨甲醇停车 45 天',
         'event_date': '2026-10-10', 'quant': '180 万吨/45 天', 'impact_path': 'x',
         'status': 'done', 'recorded_before': True, 'source': 'S3', 'source_url': ''},
        # 泛评：无量化
        {'id': 'A4', 'products': ['甲醇'], 'event_type': 'comment', 'entity': '',
         'title': '机构称短期震荡偏弱', 'detail': '关注库存', 'event_date': '2026-10-20',
         'quant': '', 'impact_path': '', 'status': 'comment', 'source': 'S4', 'source_url': ''},
    ]
    res = dedupe.dedupe(events, '2026-10-20', '2026-10-16')
    by_id = {r['id']: r for r in res}
    merged = [r for r in res if (r.get('dup_count') or 0) > 0]
    chk(len(res) == 3, '4 条事件应聚为 3 簇，实际 %d' % len(res))
    chk(len(merged) >= 1, '应至少合并 1 条转载')
    chk(by_id['A3']['tier'] == 'B', '旧闻应降为 B（不当作当日新事件），实际 %s' % by_id['A3']['tier'])
    chk(by_id['A3'].get('status') == 'repeat', '旧闻状态应为 repeat')
    chk(by_id['A4']['tier'] == 'C', '无量化泛评应判 C，实际 %s' % by_id['A4']['tier'])
    chk(by_id['A4'].get('exclude_reason'), 'C 级事件应写明排除原因')


def test_banned_language():
    allow = ['若进口恢复，港口将集中到港', '10月19日主力下跌 6.62%',
             '如果海峡复航，甲醇溢价将回落']
    block = ['机构预计甲醇将进一步下跌', '盘面看涨', '底部已现，建议囤货',
             '后市有望上涨', '价格可能抄底']
    for t in allow:
        chk(not common.banned_hits(t), '条件句应放行：%s' % t)
    for t in block:
        chk(bool(common.banned_hits(t)), '预测性表述应拦截：%s' % t)


def test_significance():
    def mk(module, cur, base, pct, is_new=False):
        return {'module': module, 'current': cur, 'base': base,
                'abs': None if base is None else cur - base,
                'pct': pct, 'is_new': is_new, 'stale_days': 1}
    chk(assemble.significance(mk('price', 3143, 3366, -6.63), {}) == 'A', '价格跌 6.63% 应为 A')
    chk(assemble.significance(mk('price', 10900, 10900, 0.0), {}) == 'C', '价格无变化应为 C')
    chk(assemble.significance(mk('basis', 822, 618, 33.0), {}) == 'A', '基差变动 204 应为 A')
    chk(assemble.significance(mk('basis', 1580, 1557, 1.48), {}) == 'C', '基差变动 23 应为 C（噪声）')
    chk(assemble.significance(mk('inventory', 41.33, 37.41, 10.48), {}) == 'A', '库存 +10.48% 应为 A')


def test_date_utils():
    chk(common.parse_date('2026-10-20').isoformat() == '2026-10-20', '日期解析')
    chk(common.days_between('2026-10-15', '2026-10-20') == 5, '天数差')
    # 2026-10-20 是周二，上一交易日应为 10-19（周一）
    import datetime
    ltd = common.last_trading_day(datetime.date(2026, 10, 20))
    chk(ltd.isoformat() == '2026-10-19', '上一交易日应为 10-19，实际 %s' % ltd)
    # 周一的上一个交易日应跨过周末到周五
    ltd2 = common.last_trading_day(datetime.date(2026, 10, 19))
    chk(ltd2.isoformat() == '2026-10-16', '周一上一交易日应为周五 10-16，实际 %s' % ltd2)
    chk(common.jaccard('甲醇现货下跌', '甲醇现货下跌') == 1.0, 'Jaccard 同文本应为 1')


def main():
    test_change_detection()
    test_main_contract_roll()
    test_event_dedupe()
    test_banned_language()
    test_significance()
    test_date_utils()
    for m in OK:
        print('[ ok   ] ' + m)
    if FAIL:
        for m in FAIL:
            print('[ FAIL ] ' + m)
        print('\n自测未通过：%d 项失败 / %d 项通过' % (len(FAIL), len(OK)))
        sys.exit(1)
    print('\n自测全部通过：%d 项' % len(OK))


if __name__ == '__main__':
    main()
