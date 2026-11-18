# -*- coding: utf-8 -*-
"""生成 Excel 工作簿（15 张表，原生公式可重算）。依赖 openpyxl。

    python build/build_excel.py --pack build/out/scan_pack.json --out 交付/xxx.xlsx
"""
import argparse
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference, ScatterChart, BarChart
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

NAVY, BLUE, LBLUE = '1F3864', '2E5C8A', 'DCE6F1'
GREY, AMBER, RED, GREEN, WHITE = 'F2F2F2', 'FFF2CC', 'FCE4E4', 'E2EFDA', 'FFFFFF'
THIN = Side(style='thin', color='BFBFBF')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def title(ws, text, ncol, sub=None, row=1):
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(name='微软雅黑', size=14, bold=True, color=WHITE)
    c.fill = PatternFill('solid', fgColor=NAVY)
    c.alignment = Alignment(vertical='center', indent=1)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=max(1, ncol))
    ws.row_dimensions[row].height = 26
    if sub:
        s = ws.cell(row=row + 1, column=1, value=sub)
        s.font = Font(name='微软雅黑', size=9, italic=True, color='595959')
        s.alignment = Alignment(wrap_text=True, vertical='top')
        ws.merge_cells(start_row=row + 1, start_column=1, end_row=row + 1, end_column=max(1, ncol))
        ws.row_dimensions[row + 1].height = 30


def header(ws, row, cols, widths=None):
    for i, cname in enumerate(cols, start=1):
        c = ws.cell(row=row, column=i, value=cname)
        c.font = Font(name='微软雅黑', size=9, bold=True, color=WHITE)
        c.fill = PatternFill('solid', fgColor=BLUE)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = BORDER
    ws.row_dimensions[row].height = 36
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w


def body(ws, row, vals, fills=None, fmts=None, wrap=()):
    for i, v in enumerate(vals, start=1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = Font(name='微软雅黑', size=9)
        c.border = BORDER
        c.alignment = Alignment(vertical='top', wrap_text=(i in wrap))
        if fills and fills.get(i):
            c.fill = PatternFill('solid', fgColor=fills[i])
        if fmts and i in fmts:
            c.number_format = fmts[i]


def num(v, nd=4):
    if v is None:
        return ''
    if isinstance(v, float):
        return round(v, nd)
    return v


def vfill(v):
    return {'异常背离（候选）': RED, '关注': AMBER, '偏离但未达门槛': GREY}.get(v, GREEN)


# ---------------------------------------------------------------------------
def s00(wb, pack):
    ws = wb.active
    ws.title = '00 说明与使用指南'
    title(ws, '产业链异常背离扫描工作簿 ｜ 化工品种池（PP / LLDPE / PX / PTA 等 16 组产业关系）', 4)
    ws.column_dimensions['A'].width = 3
    ws.column_dimensions['B'].width = 22
    ws.column_dimensions['C'].width = 110
    rows = [
        ('解决什么',
         '①按真实产业关系筛出有业务意义的品种对；②价格对齐、标准化变化、价差/比价、滚动收益率相关；'
         '③识别相关性下降与价差/比价偏离历史分布的组合；④补齐双方库存/开工/供需/成本/事件与可比性评估。'),
        ('不做什么', '不输出交易建议；不把统计偏离等同于套利机会；不对无产业关联的品种做全组合搜索；不插补、不外推。'),
        ('结论口径', '背离结论 = 产业关系成立 + 统计四门槛通过 + 基本面/事件可解释 + 可比性达标。缺任一项即降级。'),
        ('Sheet 导航',
         '01 品种池与口径 ｜ 02 产业链关系图谱 ｜ 03 配对构建规则 ｜ 04 候选组合清单 ｜ 05 异常背离榜单 ｜ '
         '06 统计口径与阈值 ｜ 07 统计详情 ｜ 08 价格价差明细(公式) ｜ 09 滚动相关明细(公式) ｜ '
         '10 多重检验与稳健性 ｜ 11 基本面清单 ｜ 12 事件与解释 ｜ 13 可比性与稳定性 ｜ 14 来源清单 ｜ 15 方法与限制'),
        ('数据来源', '新浪财经 InnerFuturesNewService 公开日线接口（主力连续），抓取于 2026-10-20；'
                     '产业关系与事件来源见"14 来源清单"，逐条带 URL 与日期。'),
        ('单价口径', '全部统一为"元/吨"，期货主力连续收盘价（非现货、非结算价）。见"01 品种池与口径"。'),
        ('可重算性', '08/09 表的收益率、价差、z、滚动相关均为原生 Excel 公式，与 Python 内核列并排可交叉校验。'),
        ('扫描参数', f'滚动窗口 {pack["params"]["window_mask"]} 日；|z| ≥ {pack["params"]["z_threshold"]}；'
                     f'持续性 ≥ {pack["params"]["persist_days"]} 日；脱钩阈值 {pack["params"]["drop_threshold"]}；'
                     f'检验次数 m = {pack["n_tests"]}'),
        ('生成时间', pack['generated_at']),
    ]
    r = 3
    for k, v in rows:
        ws.cell(row=r, column=2, value=k).font = Font(name='微软雅黑', size=10, bold=True, color=NAVY)
        c = ws.cell(row=r, column=3, value=v)
        c.font = Font(name='微软雅黑', size=10)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[r].height = 34
        r += 1
    c = ws.cell(row=r + 1, column=2, value='⚠ 合规声明')
    c.font = Font(name='微软雅黑', size=10, bold=True, color='C00000')
    c = ws.cell(row=r + 1, column=3,
                value='本工作簿为研究记录。所有"异常/背离"均为统计描述，不构成投资建议、套利建议或交易指令。'
                      '统计相关不等于因果；历史偏离不等于未来回归；期货价格不等于现货成交价。')
    c.font = Font(name='微软雅黑', size=10, color='C00000')
    c.fill = PatternFill('solid', fgColor=RED)
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.row_dimensions[r + 1].height = 44


def s01(wb, pack):
    ws = wb.create_sheet('01 品种池与口径')
    title(ws, '01 品种池与数据口径（数据可比性的前提）', 10)
    header(ws, 3, ['代码', '品种', '分类', '产业链归属', '合约乘数(吨/手)', '数据起', '数据止',
                   '交易日数', '合约与连续性口径', '数据文件'],
           [9, 24, 15, 20, 13, 12, 12, 10, 62, 15])
    r = 4
    for u in pack['universe']:
        m = pack['universe_meta'].get(u['code'], {})
        body(ws, r, [u['code'], u['name'], u['cat'], u['chain'], u['mult'], m.get('first'),
                     m.get('last'), m.get('n'), u['spec'], m.get('file')], wrap=(9,))
        r += 1
    ws.freeze_panes = 'A4'


def s02(wb, pack):
    ws = wb.create_sheet('02 产业链关系图谱')
    title(ws, '02 产业链关系图谱（类型 / 强度 / 系数 / 来源）', 13)
    header(ws, 3, ['#', 'A 品种', 'B 品种', '关系类型', '类型说明', '强度', '方向', 'A 的角色', 'B 的角色',
                   '传导机制', '经济系数 k', '业内常用监测口径', '来源编号'],
           [5, 11, 11, 15, 26, 8, 14, 34, 34, 52, 12, 42, 15])
    r = 4
    for i, rel in enumerate(pack['relations'], start=1):
        info = pack['rtype_info'].get(rel['rtype'], {})
        body(ws, r, [i, rel['a'], rel['b'], info.get('cn', rel['rtype']), info.get('desc', ''),
                     rel['strength'], rel['direction'] or '', rel['a_role'], rel['b_role'],
                     rel['mechanism'], rel['k'] if rel['k'] is not None else '无（仅比价）',
                     rel['market_convention'], ', '.join(rel['source_ids'])],
             fills={6: LBLUE if rel['strength'] == 'weak' else None}, wrap=(5, 8, 9, 10, 12))
        r += 1
    ws.freeze_panes = 'C4'


def s03(wb, pack):
    ws = wb.create_sheet('03 配对构建规则')
    title(ws, '03 组合构建规则（先筛关系，再上统计）', 5)
    ws.column_dimensions['B'].width = 26
    ws.column_dimensions['C'].width = 104
    rules = [
        ('步骤1 定义品种池', f'化工期货品种池 {len(pack["universe"])} 个，按炼化/烯烃/芳烃/煤化工/黑色/油品分链（见 01 表）。'),
        ('步骤2 列出产业关系', f'只录入存在上下游、共用原料、替代或同装置切换的品种对，共 {len(pack["relations"])} 条，'
                              '每条写清 A/B 角色、传导机制与来源。'),
        ('步骤3 强度分级', 'strong=直接物料流/同一装置；medium=共用原料/部分替代/二级成本；weak=仅成本共振，只作背景。'),
        ('步骤4 最小重叠期', f'重叠交易日 ≥ {pack["pair_rules"]["min_overlap_days"]}，否则标"数据不足"，不做推断。'),
        ('步骤5 禁止全组合搜索', f'不对无产业关联品种做 C(n,2) 全遍历。当前 {pack["n_tests"]} 次检验已需 FDR/Bonferroni；'
                                '全池 105 对将大幅放大偶然极端值。'),
        ('步骤6 四门槛', '产业关系成立 → |z| 达标 → 持续性达标 → 相关脱钩达标（另以全期相关显著性作门控）。'),
        ('步骤7 基本面复核', '过门槛后逐项核查双方库存/开工/供需/成本/事件，并给出可比性等级 A/B/C。'),
        ('参数固定原则', '窗口、阈值、样本起点必须在扫描前固定并记录（即本表与 06 表），不为凑结论而调参。'),
    ]
    r = 3
    for k, v in rules:
        ws.cell(row=r, column=2, value=k).font = Font(name='微软雅黑', size=10, bold=True, color=NAVY)
        c = ws.cell(row=r, column=3, value=v)
        c.font = Font(name='微软雅黑', size=10)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[r].height = 32
        r += 1


def s04(wb, pack):
    ws = wb.create_sheet('04 候选组合清单')
    title(ws, '04 候选组合清单（产业关系驱动的配对，先于统计）', 14)
    header(ws, 3, ['#', '组合', '关系类型', '强度', '重叠起', '重叠止', '重叠交易日', '有效收益样本',
                   '可比性', '关系稳定性备注', '产业关系来源', '进主榜单', 'k 系数', '业内常用口径'],
           [5, 11, 16, 8, 11, 11, 10, 11, 8, 54, 14, 11, 8, 40])
    r = 4
    rels = {(x['a'], x['b']): x for x in pack['relations']}
    for i, res in enumerate(sorted(pack['results'], key=lambda x: (x['rtype'], x['code_a'])), start=1):
        rel = rels.get((res['code_a'], res['code_b']), {})
        q = res.get('quality') or {}
        body(ws, r, [i, f"{res['code_a']}/{res['code_b']}", res['rtype'], rel.get('strength', ''),
                     res.get('first'), res.get('last'), res.get('n_overlap'), res.get('n_returns'),
                     q.get('level', '数据不足'), '；'.join(q.get('notes', [])) or '—',
                     ', '.join(rel.get('source_ids', [])),
                     '否（仅背景）' if rel.get('strength') == 'weak' else '是',
                     rel.get('k') if rel.get('k') is not None else '—',
                     rel.get('market_convention', '')],
             fills={9: {'A': GREEN, 'B': AMBER, 'C': RED}.get(q.get('level'), GREY)},
             wrap=(10, 14), fmts={7: '#,##0', 8: '#,##0'})
        r += 1
    ws.freeze_panes = 'B4'
    ws.auto_filter.ref = f'A3:N{r - 1}'


def s05(wb, pack):
    ws = wb.create_sheet('05 异常背离榜单')
    title(ws, '05 异常背离榜单（可按偏离程度 / 相关性变化 / 关系类型筛选）', 16)
    header(ws, 3, ['排名', '组合', '关系类型', '强度', '判定', '评分', '价差/比价 z', 'z 历史分位%',
                   '连续超阈值日数', '|z| 历史最大', '滚动相关(最新)', '相关性变化(基线-近)', '脱钩连续日数',
                   '全期日收益相关', '可比性', '门槛通过明细'],
           [6, 11, 16, 8, 16, 7, 11, 11, 12, 11, 13, 14, 12, 12, 8, 34])
    r = 4
    ok = [x for x in pack['results'] if x.get('status') == 'ok']
    order = {'异常背离（候选）': 0, '关注': 1, '偏离但未达门槛': 2, '正常': 3}
    for i, res in enumerate(sorted(ok, key=lambda x: (order.get(x['judge']['verdict'], 9),
                                                     -x['judge']['score'])), start=1):
        j = res['judge']
        body(ws, r, [i, f"{res['code_a']}/{res['code_b']}", res['rtype'], res.get('strength'), j['verdict'],
                     j['score'], num(res.get('z_last')), num(res.get('z_pct'), 1), res.get('z_run_days'),
                     num(res.get('z_abs_max_hist')), num(res.get('roll_corr_last')), num(j.get('corr_drop')),
                     res.get('drop_run_days', 0), num(res.get('r_daily')),
                     (res.get('quality') or {}).get('level'), '；'.join(j['reasons'])],
             fills={5: vfill(j['verdict'])}, fmts={6: '0.0', 8: '0.0'}, wrap=(16,))
        r += 1
    for res in [x for x in pack['results'] if x.get('status') != 'ok']:
        body(ws, r, ['—', f"{res['code_a']}/{res['code_b']}", res['rtype'], '', '数据不足'] + [''] * 10 +
             ['；'.join(res.get('notes', []))], fills={5: GREY})
        r += 1
    ws.freeze_panes = 'C4'
    ws.auto_filter.ref = f'A3:P{r - 1}'


def s06(wb, pack):
    ws = wb.create_sheet('06 统计口径与阈值')
    title(ws, '06 统计口径、公式与阈值（可复核 / 可重算）', 7)
    header(ws, 3, ['类别', '指标或门槛', '公式 / 定义', '本次取值', '为什么这样定', '注意点', '重算位置'],
           [12, 24, 44, 12, 44, 40, 16])
    P = pack['params']
    items = [
        ('对齐', '可比重叠日', '两品种都有交易日的交集；不插补、不外推', '逐对',
         '主力连续在非交易日的补位会引入假波动', '节假日差异导致同日流动性不一致', '08 A 列'),
        ('对齐', '换月/断档剔除', '|log r|>5% 且前后日振幅<2% 且持仓跳变>10%；或日历间隔≥9 天', '规则见脚本',
         '主力换月会产生与市场无关的跳空', '无法完整还原每次换月（见 15 表）', '08 F/G 列'),
        ('相关', '价格水平相关', 'Pearson(P_A, P_B)', '逐对', '反映长期共同趋势，仅作背景',
         '易被共同趋势/通胀抬升', '07 O 列'),
        ('相关', '收益率相关（主口径）', 'Pearson(r_A, r_B)，r=ln(P_t/P_{t-1})', '逐对', '剔除趋势后更接近信息同步',
         '日度相关对微结构噪声敏感', '09 O 列'),
        ('相关', '滚动相关', f'窗口内 Pearson，W={P["window_mask"]}', P['window_mask'], '窗口过短噪声大、过长不敏感',
         '首窗口前无值', '09 P 列'),
        ('相关', '相关性变化', '|全期 r| − 滚动相关(最新)', f'阈值 {P["drop_threshold"]}', '衡量脱钩而非单纯变弱',
         '全期相关本身很低时意义有限', '05 L 列'),
        ('变化', '标准化价格变化', 'Z=Σln(1+r_i)/(σ_daily·√n)', '5/20/60 日', '跨品种可比的信息单位波动',
         'σ 用全样本估计会随时间漂移', '07 表下段'),
        ('价差', '比价/价差(对数)', '有 k：ln(P_B)−ln(k·P_A)；无 k：ln(P_B/P_A)', '逐对', '对数差可加、与价格水平无关',
         '期货价≠现货；k 为行业近似', '08 E 列'),
        ('价差', '滚动 z', 'z_t=(s_t−mean(s_{t−W..t−1}))/sd(...)', str(P['z_threshold']), '只用历史、避免前视',
         '窗口内制度切换会使 z 失真', '08 G 列'),
        ('异常', '门槛1 偏离幅度', '|z| ≥ 阈值', f'|z| ≥ {P["z_threshold"]}', '正态下双侧约 4.6%',
         '厚尾时偏松，需配合持续性', '05 G 列'),
        ('异常', '门槛2 持续性', '连续 ≥ N 日 |z| 超阈值', f'≥ {P["persist_days"]} 日', '过滤单日跳空/数据问题',
         '过大则漏掉快速收敛情形', '05 I 列'),
        ('异常', '门槛3 关系显著性', 'Bonferroni p_raw×m<0.05（另算 BH-FDR q）', f'm={pack["n_tests"]}',
         '控制多组合搜索的假阳性', '显著≠稳定', '10 表'),
        ('异常', '门槛4 相关性脱钩', '|r_all| − r_roll ≥ 阈值', f'≥ {P["drop_threshold"]}',
         '识别联动失效', '共同冲击会让相关上升', '05 L/M 列'),
    ]
    r = 4
    for it in items:
        body(ws, r, list(it), wrap=(3, 5, 6))
        r += 1


def s07(wb, pack):
    ws = wb.create_sheet('07 统计详情')
    title(ws, '07 逐组合统计详情（相关性部分）', 21)
    header(ws, 3, ['组合', '关系类型', '样本区间', '重叠日 N', '收益样本 n', 'n_eff', '价格水平相关',
                   '水平相关(Spearman)', '日收益相关 r', 'CI 下', 'CI 上', 'p_raw', 'p_调整', '置换 p',
                   '置换零分布σ', '5日窗口相关', '20日窗口相关', '60日窗口相关', '滚动相关中位数', '滚动相关最新',
                   '滚动相关历史分位%'],
           [11, 16, 19, 9, 9, 9, 10, 12, 10, 9, 9, 10, 10, 9, 10, 10, 10, 10, 11, 11, 12])
    r = 4
    ok = [x for x in pack['results'] if x.get('status') == 'ok']
    for res in sorted(ok, key=lambda x: x['rtype']):
        wc = res.get('window_corr') or {}
        pm = res.get('perm') or {}
        ci = res.get('r_daily_ci') or [None, None]
        body(ws, r, [f"{res['code_a']}/{res['code_b']}", res['rtype'], f"{res['first']}~{res['last']}",
                     res['n_overlap'], res['n_returns'], num(res.get('n_eff'), 0), num(res.get('r_level')),
                     num(res.get('r_level_spearman')), num(res.get('r_daily')), num(ci[0]), num(ci[1]),
                     num(res.get('r_daily_p'), 6), num(res.get('r_daily_p_eff'), 6), num(pm.get('p_perm'), 4),
                     num(pm.get('null_sd')), num(wc.get('5')), num(wc.get('20')), num(wc.get('60')),
                     num(res.get('roll_corr_median')), num(res.get('roll_corr_last')),
                     num(res.get('roll_corr_pct'), 1)],
             fmts={4: '#,##0', 5: '#,##0', 6: '#,##0'}, wrap=(3,))
        r += 1
    ws.freeze_panes = 'B4'
    r += 2
    ws.cell(row=r, column=1, value='价差 / 比价偏离与标准化变化').font = Font(name='微软雅黑', size=11, bold=True, color=NAVY)
    r += 1
    header(ws, r, ['组合', '价差口径', '当前价差(对数)', '当前比价 B/A', '价差历史分位%', 'z(最新)',
                   'z 历史分位%', 'z 历史最大绝对值', '连续超阈值日数', '20日价差变化', '60日价差变化',
                   '20日标准化变化 A', '20日标准化变化 B', '60日标准化变化 A', '60日标准化变化 B',
                   'A 日波动率%', 'B 日波动率%'],
           [11, 22, 11, 11, 11, 9, 10, 12, 12, 11, 11, 12, 12, 12, 12, 10, 10])
    r += 1
    for res in sorted(ok, key=lambda x: x['rtype']):
        sc = res.get('std_change') or {}
        ch = res.get('spread_change') or {}
        a20, a60 = sc.get('20') or {}, sc.get('60') or {}
        body(ws, r, [f"{res['code_a']}/{res['code_b']}", res.get('spread_label'), num(res.get('spread_last')),
                     num(res.get('ratio_last'), 4), num(res.get('spread_pct'), 1), num(res.get('z_last')),
                     num(res.get('z_pct'), 1), num(res.get('z_abs_max_hist')), res.get('z_run_days'),
                     num(ch.get('20'), 4), num(ch.get('60'), 4), num(a20.get('a_std')), num(a20.get('b_std')),
                     num(a60.get('a_std')), num(a60.get('b_std')),
                     num((res.get('sigma_daily_a') or 0) * 100, 2), num((res.get('sigma_daily_b') or 0) * 100, 2)],
             fills={6: AMBER if (res.get('z_last') is not None and abs(res['z_last']) >= 2) else None})


def s08(wb, pack, res):
    """价格与价差明细：原生公式。"""
    ws = wb.create_sheet('08 价格价差明细')
    title(ws, f"08 价格与价差明细 ｜ {res['code_a']} / {res['code_b']}（样本最长的组合，{res['first']}～{res['last']}）",
          12, sub='价格列为元/吨收盘价；比价、对数价差、滚动 z、对数收益均由原生 Excel 公式计算，'
                  '可直接替换价格列重算；底部"交叉校验"与 Python 内核结果对照。')
    header(ws, 4, ['日期', 'A 品种价', 'B 品种价', '比价 B/A', '对数价差 ln(B/kA)', 'z（60日滚动）',
                   'A 对数收益', 'B 对数收益', 'z 是否超阈值', '累计 A', '累计 B', '',
                   '说明' if False else '备注'],
           [12, 11, 11, 10, 14, 11, 13, 13, 10, 10, 10, 2, 34])
    k = res.get('k')
    ca, cb = res['close_a'], res['close_b']
    gap_dates = set(res.get('excluded_roll_dates') or [])
    start = 5
    for i, d in enumerate(res['dates']):
        row = start + i
        ws.cell(row=row, column=1, value=d)
        c = ws.cell(row=row, column=2, value=ca[i]); c.number_format = '#,##0'
        c = ws.cell(row=row, column=3, value=cb[i]); c.number_format = '#,##0'
        expr = f'LN(C{row}/({k}*B{row}))' if k else f'LN(C{row}/B{row})'
        ws.cell(row=row, column=4, value=f'=IFERROR(C{row}/B{row},"")').number_format = '0.0000'
        ws.cell(row=row, column=5, value=f'=IFERROR({expr},"")').number_format = '0.0000'
        if i >= 60:
            ws.cell(row=row, column=6,
                    value=f'=IFERROR((E{row}-AVERAGE(E{row-60}:E{row-1}))/STDEV(E{row-60}:E{row-1}),"")'
                    ).number_format = '0.00'
        if i >= 1:
            # 换月/断档日的收益必须置空：这一天的价格跳空来自合约拼接，不是市场波动。
            if d in gap_dates:
                ws.cell(row=row, column=7, value='')
                ws.cell(row=row, column=8, value='')
                ws.cell(row=row, column=12, value='换月/断档日，收益已剔除')
            else:
                ws.cell(row=row, column=7, value=f'=IFERROR(LN(B{row}/B{row-1}),"")').number_format = '0.0000'
                ws.cell(row=row, column=8, value=f'=IFERROR(LN(C{row}/C{row-1}),"")').number_format = '0.0000'
            ws.cell(row=row, column=9, value=f'=IF(F{row}="","",IF(ABS(F{row})>=2,"是","否"))')
        ws.cell(row=row, column=10, value=f'=IFERROR(B{row}/$B${start},"")').number_format = '0.0000'
        ws.cell(row=row, column=11, value=f'=IFERROR(C{row}/$C${start},"")').number_format = '0.0000'
    last = start + len(res['dates']) - 1
    chk = last + 2
    ws.cell(row=chk, column=1, value='交叉校验').font = Font(bold=True, color=NAVY)
    pairs = [('最新比价（Excel 公式）', f'=D{last}', '0.000000', '最新比价（Python）', res.get('ratio_last')),
             ('最新对数价差（Excel 公式）', f'=E{last}', '0.000000', '最新对数价差（Python）', res.get('spread_last')),
             ('全期日收益相关（Excel CORREL）', f'=CORREL(G{start+1}:G{last},H{start+1}:H{last})', '0.000000',
              '全期日收益相关（Python）', res.get('r_daily'))]
    for n, (lab, f, nf, lab2, v) in enumerate(pairs):
        r = chk + 1 + n
        ws.cell(row=r, column=1, value=lab).font = Font(name='微软雅黑', size=9)
        c = ws.cell(row=r, column=2, value=f); c.number_format = nf
        ws.cell(row=r, column=4, value=lab2).font = Font(name='微软雅黑', size=9)
        c = ws.cell(row=r, column=5, value=num(v, 8)); c.number_format = nf
    ws.freeze_panes = 'A5'
    ch = LineChart()
    ch.title = f"{res['code_a']} 与 {res['code_b']} 收盘价（元/吨）"
    ch.height, ch.width = 7.5, 20
    ch.add_data(Reference(ws, min_col=2, max_col=3, min_row=4, max_row=last), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=5, max_row=last))
    ws.add_chart(ch, 'M4')
    ch2 = LineChart()
    ch2.title = '对数价差与 60 日滚动 z'
    ch2.height, ch2.width = 7.5, 20
    ch2.add_data(Reference(ws, min_col=5, max_col=6, min_row=4, max_row=last), titles_from_data=True)
    ws.add_chart(ch2, 'M21')
    return ws


def s09(wb, pack):
    ws = wb.create_sheet('09 滚动相关明细')
    title(ws, '09 滚动收益率相关明细（原生公式：滚动 60 日 CORREL）', 8,
          sub='取样本最长的三个组合；O 列 Python 内核值与 P 列 Excel 公式值并排，用于交叉校验。')
    r = 3
    ok = [x for x in pack['results'] if x.get('status') == 'ok']
    picks = sorted(ok, key=lambda x: -x['n_overlap'])[:3]
    from stats_core import rolling_corr
    for res in picks:
        ws.cell(row=r, column=1, value=f"{res['code_a']} / {res['code_b']}（{res['rtype']}）"
                ).font = Font(name='微软雅黑', size=11, bold=True, color=NAVY)
        r += 1
        header(ws, r, ['日期', 'A 对数收益', 'B 对数收益', '滚动60日相关(Excel)', '相关性变化(Excel)',
                       '是否脱钩', '', '滚动60日相关(Python)'],
               [12, 13, 13, 18, 16, 10, 2, 18])
        hdr = r
        r += 1
        start = r
        rc = rolling_corr(res['ret_a'], res['ret_b'], 60)
        rets = {'date': res['ret_dates'], 'a': res['ret_a'], 'b': res['ret_b']}
        n = len(rets['date'])
        for i in range(n):
            row = start + i
            ws.cell(row=row, column=1, value=rets['date'][i])
            ws.cell(row=row, column=2, value=round(rets['a'][i], 8)).number_format = '0.0000'
            ws.cell(row=row, column=3, value=round(rets['b'][i], 8)).number_format = '0.0000'
            if i >= 59:
                ws.cell(row=row, column=4, value=f'=IFERROR(CORREL(B{row-59}:B{row},C{row-59}:C{row}),"")'
                        ).number_format = '0.0000'
                ws.cell(row=row, column=5,
                        value=f'=IFERROR(CORREL(B{start}:B{row},C{start}:C{row}),"")').number_format = '0.0000'
                ws.cell(row=row, column=6, value=f'=IF(D{row}="","",IF(ABS(D{row})<0.2,"脱钩",""))')
            ws.cell(row=row, column=8, value=num(rc[i]) if rc[i] is not None else '').number_format = '0.0000'
        r = start + n + 1
        ws.cell(row=r, column=1, value='Python 滚动相关末值：').font = Font(size=9)
        ws.cell(row=r, column=4, value=num(res.get('roll_corr_last'), 6)).number_format = '0.000000'
        ws.cell(row=r, column=5, value='Excel 末值：').font = Font(size=9)
        ws.cell(row=r, column=6, value=f'=D{start + n - 1}').number_format = '0.000000'
        r += 3


def s10(wb, pack, hist=None):
    ws = wb.create_sheet('10 多重检验与稳健性')
    title(ws, '10 多重检验与稳健性（防止"大量搜索制造偶然极端值"）', 9)
    header(ws, 3, ['组合', '关系类型', '检验次数 m', '原始 p（z 偏离）', 'Bonferroni p × m', 'BH-FDR q',
                   '全期相关原始 p', '全期相关 Bonferroni p', '置换检验 p'],
           [11, 18, 11, 14, 15, 11, 14, 16, 13])
    r = 4
    m = pack['n_tests']
    for res in [x for x in pack['results'] if x.get('status') == 'ok']:
        zp = res.get('z_p')
        pm = res.get('perm') or {}
        body(ws, r, [f"{res['code_a']}/{res['code_b']}", res['rtype'], m,
                     num(zp, 6), num(None if zp is None else min(1, zp * m), 6), num(res.get('z_q_bh'), 4),
                     num(res.get('r_daily_p'), 6), num(res.get('r_daily_p_eff'), 6), num(pm.get('p_perm'), 4)])
        r += 1
    r += 1
    notes = [
        '① 本表对每个组合只做 1 次"当前 z"检验与 1 次全期相关检验，合计 m = %d 个组合 × 双向口径；' % m,
        '② 全期相关 p 值几乎全部远小于 0.05（因为强产业关系本身就高度相关），因此它只作为"关系是否存在"的门控，'
        '不能作为"异常"的证据；',
        '③ 判定"异常"依赖的是"当前 z 是否处在该组合自身历史分布的尾部"，而不是 p 值大小；',
        '④ 置换检验用循环平移打乱 B 的收益对齐关系，保留其自相关结构，用于检验相关是否由共同趋势驱动。',
    ]
    for n in notes:
        ws.cell(row=r, column=1, value=n).font = Font(name='微软雅黑', size=9, italic=True, color='595959')
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
        ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True)
        ws.row_dimensions[r].height = 26
        r += 1
    if hist:
        r += 2
        ws.cell(row=r, column=1, value='假设历史区间扫描（过去 12 个月，按月回拨"当下"重跑同一套阈值）'
                ).font = Font(name='微软雅黑', size=11, bold=True, color=NAVY)
        r += 1
        header(ws, r, ['组合', '关系类型', '回看次数', '被判"异常背离"次数', '命中率%', 'z 最小值', 'z 最大值', '', ''],
               [11, 18, 11, 16, 10, 10, 10, 2, 2])
        r += 1
        for v in hist['summary']:
            rate = v['n_anom'] / v['n'] * 100 if v['n'] else None
            body(ws, r, [v['pair'], v['rtype'], v['n'], v['n_anom'], num(rate, 1), num(v.get('ai_min'), 3),
                         num(v.get('zmax'), 3)],
                 fills={4: AMBER if v['n_anom'] else None})
            r += 1


def s11(wb, pack):
    ws = wb.create_sheet('11 基本面清单')
    title(ws, '11 基本面五问清单（双方库存 / 开工 / 供需 / 成本 / 事件）', 8,
          sub='本表是"要查什么、从哪查"的核查清单，所列口径为行业通用可查口径；'
              '本次仅对检索到的公开事实做记录（见 12 表），未获得连续数值的地方一律标注"未取得"，不做估算。')
    header(ws, 3, ['组合', '品种', '① 库存', '② 开工', '③ 供需', '④ 成本', '⑤ 重要事件编号', '本次取得情况'],
           [11, 16, 30, 30, 34, 30, 14, 34])
    r = 4
    ev = pack['events']
    for res in [x for x in pack['results'] if x.get('status') == 'ok']:
        for code in (res['code_a'], res['code_b']):
            t = pack['fund_template'].get(code, {})
            keys = t.get('events_keys', '')
            got = [e['title'] for e in ev if e['ticker'] == code]
            body(ws, r, [f"{res['code_a']}/{res['code_b']}", code, t.get('inventory', ''), t.get('operating', ''),
                         t.get('supply_demand', ''), t.get('cost', ''), keys,
                         f'已检索到 {len(got)} 条公开事件；连续库存/开工数值未取得' if got
                         else '未检索到窗口内公开事件；连续数值未取得'],
                 wrap=(3, 4, 5, 6, 8))
            r += 1
    ws.freeze_panes = 'C4'


def s12(wb, pack):
    ws = wb.create_sheet('12 事件与解释')
    title(ws, '12 重要事件库与"为什么偏离/为什么没偏离"的解释框架', 9,
          sub='事件只用于解释统计差异的来源，不用于把相关性升级为因果；所有事件均带来源编号（见 14 表）。')
    header(ws, 3, ['编号', '品种', '日期', '类别', '事件', '细节', '方向提示', '来源', '可用于解释的组合'],
           [7, 9, 11, 12, 40, 60, 24, 8, 40])
    r = 4
    rels = pack['relations']
    for e in pack['events']:
        used = [f"{x['a']}/{x['b']}" for x in rels if e['ticker'] in (x['a'], x['b'])]
        body(ws, r, [e['id'], e['ticker'], e['date'], e['kind'], e['title'], e['detail'],
                     e['direction_hint'], e['source'], '、'.join(used)], wrap=(5, 6, 7, 9))
        ws.row_dimensions[r].height = 58
        r += 1
    r += 2
    ws.cell(row=r, column=1, value='共同冲击说明').font = Font(bold=True, color=NAVY)
    r += 1
    body(ws, r, ['—', '全池', pack['common_shock']['focus'], '共同冲击', pack['common_shock']['note'], '', '', '', ''],
         wrap=(5,))
    ws.row_dimensions[r].height = 44


def s13(wb, pack):
    ws = wb.create_sheet('13 可比性与稳定性')
    title(ws, '13 数据可比性与关系稳定性评级（哪些组合本来就不该硬扫）', 8)
    header(ws, 3, ['组合', '关系类型', '评级', '评分', '重叠日', '跨度(年)', '三段滚动相关均值差', '具体理由'],
           [11, 18, 8, 7, 10, 10, 15, 96])
    r = 4
    for res in sorted([x for x in pack['results'] if x.get('status') == 'ok'],
                      key=lambda x: (x.get('quality') or {}).get('score', 0)):
        q = res.get('quality') or {}
        body(ws, r, [f"{res['code_a']}/{res['code_b']}", res['rtype'], q.get('level'), q.get('score'),
                     q.get('n_overlap'), num(q.get('span_years'), 1), num(res.get('rc_regime_spread'), 3),
                     '；'.join(q.get('notes', []))],
             fills={3: {'A': GREEN, 'B': AMBER, 'C': RED}.get(q.get('level'))}, wrap=(8,))
        r += 1
    ws.freeze_panes = 'C4'


def s14(wb, pack):
    ws = wb.create_sheet('14 来源清单')
    title(ws, '14 来源清单（数据 / 产业关系 / 事件，逐条可点击）', 7)
    header(ws, 3, ['编号', '分组', '标题', 'URL', '日期', '可靠性', '用于'], [7, 10, 70, 62, 12, 8, 56])
    r = 4
    for sid, s in pack['sources'].items():
        c = body(ws, r, [sid, s['group'], s['title'], s['url'], s['date'], s['reliability'], s['usage']],
                 wrap=(3, 4, 7))
        cell = ws.cell(row=r, column=4)
        if s['url'].startswith('http'):
            cell.hyperlink = s['url']
            cell.font = Font(name='微软雅黑', size=9, color='0563C1', underline='single')
        r += 1
    ws.freeze_panes = 'A4'


def s15(wb, pack, hist=None):
    ws = wb.create_sheet('15 方法与限制')
    title(ws, '15 方法学与已知限制（读结论前请先看这一页）', 3)
    ws.column_dimensions['A'].width = 4
    ws.column_dimensions['B'].width = 28
    ws.column_dimensions['C'].width = 108
    items = [
        ('价格口径', '全部使用期货主力连续收盘价（元/吨）。主力连续在换月时会拼接不同月份合约，跨月价差被记入"价格变化"；'
                     '本工具用规则识别换月跳空并剔除其收益，但无法完整还原每一次换月。'),
        ('与现货的差异', '期货价 ≠ 现货成交价。加工费/价差若与行业现货口径（如 PTA 现货加工费）比较，需替换为现货序列。'),
        ('对齐规则', '只在双方都有交易的日期上计算；不插补、不回填、不外推。缺失日造成样本减少已在表中列明。'),
        ('相关性口径', '"价格水平相关"与"收益率相关"分开报告：前者高可能是共同趋势所致，后者才是主口径。'),
        ('多重比较', '已用 Bonferroni 与 BH-FDR 校正，并用置换检验检验共同趋势。即便如此，仍不能排除"巧合"。'),
        ('关系稳定性', '部分组合（如仅成本共振型、替代弹性极小的替代型）历史关系本身不稳定，评级会在 13 表降为 B/C。'),
        ('基本面', '库存/开工/供需的连续口径需付费数据库；本次仅记录可公开检索的时点事实与来源，未取得的数值标"未取得"。'),
        ('事件与因果', '事件库用于解释统计差异，不代表因果。价格由多因素共同决定，任何单一事件都无法完整解释。'),
        ('不作交易建议', '本工作簿不含任何交易、套利、择时建议；不构成投资研究意见。'),
    ]
    r = 3
    for k, v in items:
        ws.cell(row=r, column=2, value=k).font = Font(name='微软雅黑', size=10, bold=True, color=NAVY)
        c = ws.cell(row=r, column=3, value=v)
        c.font = Font(name='微软雅黑', size=10)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[r].height = 40
        r += 1
    if hist:
        r += 1
        ws.cell(row=r, column=2, value='假设历史扫描').font = Font(name='微软雅黑', size=10, bold=True, color=NAVY)
        ws.cell(row=r, column=3,
                value=f'在过去 {hist["months"]} 个月里，将"当下"按月回拨，用同一套阈值重跑扫描，'
                      f'共 {len(hist["cut_offs"])} 个时点、{len(hist["rows"])} 次组合判定，用于量化扫描器本身的假阳性率。'
                ).font = Font(name='微软雅黑', size=10)
        ws.cell(row=r, column=3).alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[r].height = 36


# ---------------------------------------------------------------------------
def build(pack, hist, out_path):
    wb = Workbook()
    s00(wb, pack)
    s01(wb, pack)
    s02(wb, pack)
    s03(wb, pack)
    s04(wb, pack)
    s05(wb, pack)
    s06(wb, pack)
    s07(wb, pack)
    ok = [x for x in pack['results'] if x.get('status') == 'ok']
    longest = max(ok, key=lambda x: x['n_overlap'])
    s08(wb, pack, longest)
    s09(wb, pack)
    s10(wb, pack, hist)
    s11(wb, pack)
    s12(wb, pack)
    s13(wb, pack)
    s14(wb, pack)
    s15(wb, pack, hist)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    wb.save(out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', default='build/out/scan_pack.json')
    ap.add_argument('--hist', default='build/out/hist_scan.json')
    ap.add_argument('--out', default='交付/产业链异常背离扫描.xlsx')
    a = ap.parse_args(argv)
    pack = json.load(open(a.pack, encoding='utf-8'))
    hist = None
    if a.hist and os.path.exists(a.hist):
        h = json.load(open(a.hist, encoding='utf-8'))
        summ = json.load(open(os.path.join(os.path.dirname(a.hist), 'hist_scan_summary.json'), encoding='utf-8'))
        hist = dict(months=h['months'], cut_offs=h['cut_offs'], rows=h['rows'], summary=summ)
    p = build(pack, hist, a.out)
    print('saved', p)


if __name__ == '__main__':
    main()
