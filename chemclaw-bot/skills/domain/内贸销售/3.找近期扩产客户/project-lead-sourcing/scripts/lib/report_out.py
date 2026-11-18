# -*- coding: utf-8 -*-
"""生成《方法与边界说明.md》——交付必须包含的四块。

原则：**能用数据算出来的，脚本算**（分布、剔除名单、覆盖不均衡、抽检结果）；
**属于判断的，交给 agent/人写**（负结果、通道失效原因、行业周期判断），
脚本只在文里显式标出"这一段需要你补"，不替它编。
"""
import collections
import json
import os

MARK_BEGIN = '<!-- GAPS:BEGIN 以下为 agent/人工补充的判断性内容，脚本不生成 -->'
MARK_END = '<!-- GAPS:END -->'


def _table(counter, key_label='类别', value_label='条数'):
    rows = ['| %s | %s |' % (key_label, value_label), '|---|---|']
    items = counter.most_common() if hasattr(counter, 'most_common') else sorted(counter.items())
    for k, v in items:
        rows.append('| %s | %s |' % (k, v))
    return '\n'.join(rows)


def _as_counter(d):
    return collections.Counter(d or {})


def build_report(cfg, leads, stats, out_path, channels=None, qa=None, gaps_text=None,
                 excluded_text=None):
    """写《方法与边界说明.md》，返回路径。"""
    prod = cfg['product']['name']
    region = cfg['region']['name']
    months = cfg['window_months']
    formula = cfg['product'].get('formula') or ''
    has_est = sum(1 for r in leads
                  if (r.get('年需求量估算') or '').strip() not in ('', '无法估算', '未披露'))

    L = []
    A = L.append
    A('# %s · %s · 未来 %d 个月 —— 项目级潜客清单：方法与边界说明\n' % (prod, region, months))
    A('- 产品：%s%s' % (prod, ('（%s）' % formula) if formula else ''))
    A('- 地区：%s%s' % (region, ('（%s）' % ' / '.join(cfg['region']['provinces'])
                                if cfg['region'].get('provinces') else '')))
    A('- 时间窗：%s ~ %s（生成日 %s，窗口 %d 个月）'
      % (stats.get('today', ''), stats.get('window_end', ''), stats.get('today', ''), months))
    A('- 线索：**%s 条项目级线索**（原始 %s 条，去重剔除 %s 条，peer 剔除 %s 条）'
      % (stats.get('final', len(leads)), stats.get('raw_records', '?'),
         stats.get('dups_removed', 0), len(stats.get('peers_removed', []))))
    A('- **一条记录 = 一个具体项目，不是一家公司**\n')

    # ---------------------------------------------------------------- 一
    A('## 一、条数与分布（交付四块之一）\n')
    A('**销售时点**\n\n%s\n' % _table(_as_counter(stats.get('by_timing'))))
    A('**建设阶段**\n\n%s\n' % _table(_as_counter(stats.get('by_stage'))))
    A('**置信度**\n\n%s\n' % _table(_as_counter(stats.get('by_confidence'))))
    A('**产品角色**\n\n%s\n' % _table(_as_counter(stats.get('by_role'))))
    A('**需求性质**（直接＝进入产品分子或配合料主体系；间接＝仅上游转化/中和等衍生需求）\n\n%s\n'
      % _table(_as_counter(stats.get('by_nature'))))
    A('**省份**\n\n%s\n' % _table(_as_counter(stats.get('by_province'))))
    A('**板块（lane）**\n\n%s\n' % _table(_as_counter(stats.get('by_lane'))))
    A('**来源类型**\n\n%s\n' % _table(_as_counter(stats.get('by_source_type'))))
    A('**年需求量可估算**：%d / %d 条；其余 %d 条如实写「无法估算」——公开公告普遍不披露单耗，'
      '只有拿到配合料配比、反应式或原辅材料清单的条目才给数字，**不做无出处的估算**。\n'
      % (has_est, len(leads), len(leads) - has_est))

    # ---------------------------------------------------------------- 二
    A('## 二、置信度分级与证据基础（交付四块之二）\n')
    bc = _as_counter(stats.get('by_confidence'))
    A('- **高（%d 条）**：来源原文明确写出项目名称、产能、（如有）投产时间，链接可点开复核。'
      % bc.get('高', 0))
    A('- **中（%d 条）**：企业业务与该产品工序可确认，项目存在但产能或时间细节缺失。' % bc.get('中', 0))
    A('- **低（%d 条）**：主体或项目细节未完全核实，**必须电话确认后再投入销售资源**。\n'
      % bc.get('低', 0))
    A('**销售时点判定规则**（可在 `config.json` 调窗口月数后自动重算）\n')
    A('| 建设阶段 | 投产月份 | 判定 | 理由要点 |')
    A('|---|---|---|---|')
    A('| 试车 | 任意 | 现在就该联系 | 装置正在消化原料，供应商名单可切入 |')
    A('| 已投产 | 近 6 个月内 | 现在就该联系 | 达产爬坡期，补量/换源机会大 |')
    A('| 已投产 | 更早 | 仅需关注 | 供应商格局稳定，只作长期替换储备 |')
    A('| 在建 | ≤ %s | 现在就该联系 | 提前 1~3 个月锁定原料、完成合格供应商入库 |'
      % stats.get('now_cutoff', ''))
    A('| 在建 | %s ~ %s | 3-6个月后再联系 | 采购启动点落在窗口后半段 |'
      % (stats.get('now_cutoff', ''), stats.get('win_cutoff', '')))
    A('| 在建 | 未披露 | 3-6个月后再联系 | 入库/送样本身要 1~3 个月，不能等到点火 |')
    A('| 在建 | > %s | 仅需关注 | 超出窗口 |' % stats.get('win_cutoff', ''))
    A('| 备案 | 窗口内 | 3-6个月后再联系 | 确定性较高但采购未启动，先建联 |')
    A('| 备案 / 拟建 / 未披露 | 其它 | 仅需关注 | 尚未形成当期原料需求 |\n')
    A('**优先级** = 用量强度（板块星级）× 置信度权重（高 3 / 中 2 / 低 1）；'
      '间接需求额外降权。本表分布：%s\n' % dict(_as_counter(stats.get('by_priority'))))

    A('**取证通道**\n')
    if channels:
        A('| 通道 | 类型 | 本次可用性 | 说明 |')
        A('|---|---|---|---|')
        for c in channels.get('channels', []):
            A('| %s | %s | %s | %s |' % (c.get('name', ''), c.get('kind', ''),
                                         c.get('status', ''), c.get('note', '')))
        A('')
    else:
        A('（未运行 `b2bctl probe`，通道可用性未记录。建议先探测再铺 lane。）\n')

    if qa:
        A('**链接抽检（链接闸门）**：唯一来源 %s 个，抽检 **%s** 条；'
          '坏链/抓取失败 **%s** 条。\n' % (qa.get('unique_sources', '?'),
                                          qa.get('sampled', '?'), qa.get('broken_count', 0)))
        A('%s\n' % _table(_as_counter(qa.get('tally')), '抽检结论', '条数'))

    # ---------------------------------------------------------------- 三
    A('## 三、被剔除的同行（peer）名单（交付四块之三）\n')
    peers = stats.get('peers_removed', [])
    if peers:
        A('以下主体**自身生产 %s**，是同行而非客户，已按 peer gate 剔除、**不计入 %s 条线索**：\n'
          % (prod, stats.get('final', len(leads))))
        A('| 被剔除主体 | 命中关键词 |')
        A('|---|---|')
        seen = set()
        for d in stats.get('peer_details', []):
            if d['company'] in seen:
                continue
            seen.add(d['company'])
            A('| %s | %s |' % (d['company'], d['keyword']))
        for p in peers:
            if p not in seen:
                A('| %s | （来自 peer_keywords） |' % p)
        A('')
    else:
        A('**merge 阶段未剔除任何条目。**但这**不等于本轮没有同行**——更常见的情况是 lane 在'
          '检索阶段就识别出同行并**没有把它写进 JSON**，所以 merge 统计里自然是 0。\n')
        A('> 因此下面这一节必须由人补全：**在 lane 阶段判断为同行、因而未进入本表的主体**。'
          '漏了它，交付四块的第三块就是空的。\n')
    if excluded_text and excluded_text.strip():
        A('### 在 lane 阶段剔除的同行（未进入 JSON，故 merge 计数为 0）\n')
        A(excluded_text.strip() + '\n')
    else:
        A('<!-- PEERS:BEGIN 以下为 lane 阶段剔除的同行，由 agent/人工补充 -->')
        A('（待补：本轮在 lane 阶段被判定为同行、因而未写入 `leads_raw/` 的主体及其依据。'
          '写成表格：主体 / 依据 / 原以为的机会。）')
        A('<!-- PEERS:END -->\n')
    A('完整 peer 关键词清单（`config.json → peer_keywords`，可按产品替换）：\n')
    A('%s\n' % ('、'.join(cfg.get('peer_keywords', [])) or '（空）'))

    oor = stats.get('out_of_region', [])
    if oor:
        A('**地区闸门剔除**（%s 以外，共 %d 家）：%s\n'
          % (region, len(oor), '、'.join(oor[:30])))
    dr = stats.get('dropped') or {}
    if dr:
        A('**其它剔除计数**：%s\n' % dr)

    # ---------------------------------------------------------------- 四
    A('## 四、未覆盖的缺口与负结果（交付四块之四）\n')
    A('### 4.1 脚本自动算出的覆盖缺口\n')
    fanout = cfg.get('lane_fanout', {})
    lo = int(fanout.get('min_records_per_lane', 8))
    thin = [(k, v) for k, v in _as_counter(stats.get('by_lane')).items() if v < lo]
    if thin:
        A('- **产出偏薄的板块**（低于每 lane %d 条的目标）：%s。'
          '薄通常意味着该方向要么确实在萎缩（是重要负结果），要么通道未打通；**需在 4.2 说明原因**。\n'
          % (lo, '、'.join('%s（%d 条）' % (k, v) for k, v in sorted(thin, key=lambda x: x[1]))))
    else:
        A('- 各板块产出均达到每 lane %d 条目标。\n' % lo)
    if stats.get('unverified_source'):
        A('- **无来源（未核实）%d 条**：这些条目未取得可信链接，置信度已置为「低」，'
          '只能电话确认。\n' % stats['unverified_source'])
    if stats.get('problems'):
        A('- **解析问题**：%s\n' % stats['problems'])
    if qa and qa.get('broken_count'):
        A('- **坏链/抓取失败 %d 条**：已在上文链接抽检中逐条列出，需人工复核或替换来源。\n'
          % qa['broken_count'])
    A('')

    A('### 4.2 判断性缺口与负结果（agent/人工补充）\n')
    if gaps_text and gaps_text.strip():
        A(gaps_text.strip() + '\n')
    else:
        A(MARK_BEGIN)
        A('（此处应由 agent/人填写，脚本不生成。至少要写清：）\n')
        A('1. **哪些通道失效**、为什么（直接影响覆盖到哪些省份/板块）；')
        A('2. **哪些板块是"负结果"**——不是没找到，而是该方向本身在萎缩/停缓建/工艺不用本产品；')
        A('3. **哪些"有项目但缺关键信息"**（如厂址、产能未披露）只能人工补证；')
        A('4. **非上市企业覆盖程度**，以及为什么（备案/环评通道可达性）。')
        A(MARK_END)
        A('')

    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
    return out_path


def load_gaps(root, cfg):
    """如果项目根下有 gaps.md，就作为 4.2 的判断性内容嵌入。"""
    p = os.path.join(root, 'gaps.md')
    if os.path.exists(p):
        with open(p, encoding='utf-8-sig') as f:
            return f.read()
    return None


def load_excluded_peers(root, cfg):
    """lane 阶段（写 JSON 之前）就判定为同行、因而未进入本表的主体名单。

    放在项目根 `peers_excluded.md`。为什么必须单独有一份：lane 在检索时就直接跳过了同行，
    所以它们不会出现在 leads_raw 里，merge 的 peer 计数必然是 0——
    若只依赖自动统计，第三块会错误地报告"本轮没有同行"。
    """
    p = os.path.join(root, 'peers_excluded.md')
    if os.path.exists(p):
        with open(p, encoding='utf-8-sig') as f:
            return f.read()
    return None


def load_json(path):
    if path and os.path.exists(path):
        try:
            with open(path, encoding='utf-8-sig') as f:
                return json.load(f)
        except Exception:
            return None
    return None