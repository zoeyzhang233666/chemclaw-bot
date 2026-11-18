---
name: industrial-morning-brief
description: 生成任意化工/大宗品种的「产业研究晨报」——把某个交易日的新增变化整理成可交付的多品种晨报，交付一份单文件离线互动 HTML + 一份逐格可追溯的 Excel。适用于期现研究、产业基本面跟踪、品种日报/晨会材料，触发词：生成品种晨报 / 品种晨报 / 产业晨报 / 期货晨报 / 基本面晨报 / 甲醇晨报 / PP晨报 / PVC晨报 / 今天有什么变化 / 帮我做一份晨会材料。核心约束：只写当日新增与实质变化，旧闻新发必须识别并降级，拿不到的数据写缺口不写估算，全文禁止方向性预测。
---

# 产业研究晨报生成技能

## 这个技能解决什么问题

研究员的真实痛点不是「找不到信息」，而是**信息太多、且新旧混在一起**。搜索引擎会把去年同日的稿件、三个月前的装置新闻、无信息量的机构观点一起端上来；如果直接汇总，晨报就会变成「昨天看涨、今天还是看涨」的废话集。

本技能的判定标准只有一条：

> **这份晨报里每一条，都必须是「上一期之后新发生或实质变化的」，并且读者能顺着它点到原始来源。**

因此流程的重心不在「抓」，而在**基线对比 → 变化判定 → 去重 → 分级 → 淘汰**。

## 交付什么

| 交付物 | 形态 | 关键要求 |
|---|---|---|
| 晨报正文 | 单个 HTML 文件（约 1.1 MB，ECharts 内联，零外链，可微信/邮件直发，双击即开） | 首屏品种摘要 → 可展开模块 → 每条可点开抽屉看来源与验证项 |
| 底稿数据 | 单个 Excel（12 张表） | 原始指标 / 上期值 / 本期值 / 变动 / 级别 / 事件 / 排除 / 缺口 / 来源，逐格可与 HTML 对齐 |
| 研究记录 | `research.json` + `raw/events_raw.json` | 保留判断依据，下一期可直接当基线复用 |

## 一条铁律：三条基线不能混

初学者最常犯的错，是把「上一交易日」「上一期晨报」「数据自身发布日期」当成同一个东西。

- **报告日**（如 2026-10-20）：本期晨报的日期。
- **对比基线**（如 2026-10-16）：上一期晨报的收盘口径。所有「变动」都相对它计算。
- **数据日期**（如库存 2026-10-15）：某个数字本身的时间戳。

一条库存数据发布于 10-15，报告日是 10-20，它**不是**「今天的变化」，只能写「截至 10-15，较 10-08 增加 3.92 万吨」。凡是 `stale_days > 1` 的指标，页面自动打「未更新」标签并降级，正文不得称其为当天最新变化。

## 执行流程

### 第 0 步：确认输入（缺失就用默认值，不要空转）

| 输入 | 默认 | 说明 |
|---|---|---|
| 关注品种 | 必填 | 中文名或代码均可，如 甲醇/PP/PVC |
| 报告日 | 今天（若为非交易日，取最近交易日） | |
| 对比基线 | 上一期晨报；没有则自动取上一交易日 | 有上期数据时，变化判定准确度显著提高 |
| 研究地区 | 全国，重点华东/华南/华北 | |
| 期货合约 | 主连 + 主力月份 + 次主力 | |
| 自定义观察指标 | 无 | 如「MTO 利润」「出口签单」 |

若用户只说「做一份甲醇晨报」而不给基线，**不要停下来问**，直接按上一交易日做，并在报告里注明「本期为首次，无上一期可比，变动均相对上一交易日」。

### 第 1 步：拉取行情序列

```bash
python scripts/fetch_futures.py 甲醇 PP PVC --contracts 2611,2612,2701,2705 --beg 20250101 --out raw
```

- 东方财富公开接口，无需 key；`scripts/fetch_futures.py` 已内置 host 轮换与重试（该接口偶发 `RemoteDisconnected`，单 host 会失败）。
- 至少取 **250 个交易日**，否则无法算年内分位与 60 日变化。
- 主连必须同时取「主力实际合约月份」，原因见下方「主连换月陷阱」。

### 第 2 步：采集现货、基差、库存、开工、事件

这一步是人工+检索的混合工作，见 `references/research-playbook.md`，其中给出了每类数据的可靠来源、常见坑与交叉核对方法。

**关键：所有数字都要带四要素** —— 规格、区域、单位、税基。缺任何一项，这个数字就不能进晨报。

### 第 3 步：写本期研究配置 `research.json`

结构见 `references/data-contract.md`。每条指标必须写清五件事：

1. `current` / `data_date`：本期值与其真实发布日期；
2. `base` / `base_date`：**同口径**的上期值（口径不同宁可不写）；
3. `what`：发生了什么（陈述事实）；
4. `why`：为什么重要（讲传导机制，不下结论）；
5. `verify`：今天继续验证什么（给出可执行的下一条线索）。

缺 `why` 或 `verify` 的条目，说明这条信息其实没想清楚，应当删掉而不是硬凑。

### 第 4 步：事件去重与分级

```bash
python scripts/dedupe.py raw/events_raw.json --out raw/events.json \
       --report-date 2026-10-20 --baseline-date 2026-10-16
```

三条规则（`references/change-detection.md` 有完整推导）：

- **D1 转载合并**：同事件类型族 + 同主体 + 量化数字指纹有交集 → 合并为一条。**不要只靠文本相似度**：中文改写稿的 2-gram 相似度实测仅约 0.06，完全无法识别。
- **D2 旧闻识别**：事件发生日早于基线 → 标「旧闻·仅进展更新」，最高评 B。不删（读者需要背景），但绝不当作当日新事件。
- **D3 泛评剔除**：无量化、无明确影响路径的观点归纳 → C 级噪声，不进正文，但写入 Excel 且在页面列出「为什么被排除」。

评分 = 影响路径 30 + 量化 25 + 时效 20 + 独特性 15 + 覆盖度 10。

### 第 5 步：组装与变化检测

```bash
python scripts/assemble.py research.json --out build/data.json --baseline baseline_prev.json
```

会输出：期货序列与分位、逐条指标变动与级别、事件簇、缺口、来源、产业链。

### 第 6 步：渲染交付物

```bash
python scripts/build_html.py build/data.json --out out/晨报.html
python scripts/build_xlsx.py build/data.json --out out/晨报.xlsx
```

### 第 7 步：四道校验（缺一不可）

```bash
python scripts/selftest.py                                   # 判定逻辑单测（33 项）
python scripts/check_html.py out/晨报.html build/data.json    # 占位符/外链/数字同源/禁用词
python scripts/check_xlsx.py out/晨报.xlsx build/data.json   # 逐格与 data.json 对齐
python scripts/qa_render.py out/晨报.html --shots shots       # 真浏览器渲染（无 playwright 时自动跳过）
```

`check_html.py` 的**方向性表述扫描**会拦下「预计下跌 / 看涨 / 抄底 / 底部已现」。注意它允许条件句（「若进口恢复，港口将集中到港」），因为那是传导逻辑而非预测。

## 主连换月陷阱（必须处理）

主连在换月日会「跳接」到下一个合约。若直接用相邻收盘相除，会得到一天的假涨跌。

实测案例：2026-10-20 甲醇主连前收 3,143、当日 3,117，算出 -0.83%；但主力当日已从 MA2701 切到新合约，真实主力 2701 当日为 -0.50%。

`assemble.py` 的处理：若 `|今开 - 昨收| / 昨收 > 8%`，判为换月，改用「收盘/开盘」的日内涨跌并置 `rolled=True` 提示。因此 `futures` 配置里**必须同时给 `main_month_label`**。

## 三种必须写「没有」的情况

1. **没有重要新信息**：直接写「截至报告日，本品种无可核实的实质新增变化」，不要用旧数据重新包装成当天的发现。
2. **数据没拿到**：写进「数据缺口」表，说明缺什么、为什么缺、怎么补。**禁止**用估算值、同比反推、上月数据顶替。
3. **事件性质不明确**：标注「待核实」并给出核实路径，不要替它定性。

## 内容红线

- 不预测价格方向、不给目标价、不写「建议囤货/建仓」。
- 不把含税现货与不含税期货直接比较得出套利结论（基差只作结构观察）。
- 不将旧闻当当日新事件（触发 D2 规则）。
- 不将未更新数据称为「当天最新变化」（`stale_days` 兜底）。
- 同一屏内只使用一套价格口径：表格用「报告日收盘 vs 基线收盘」，盘中价另标「盘中参考」。

## 目录结构

```
industrial-morning-brief/
├── SKILL.md                         本文件
├── README.md                        给第一次使用者
├── references/
│   ├── data-contract.md             research.json / data.json 字段契约
│   ├── change-detection.md          基线对比、去重、分级、换月的完整规则
│   ├── research-playbook.md         各类数据的来源、坑与交叉核对
│   ├── adapters.md                  换成别的品种/接口（原油、有色、农产品）
│   └── qa-checklist.md              交付前逐项检查表
├── scripts/
│   ├── common.py                    公共工具（行情读取、格式化、禁用词）
│   ├── fetch_futures.py             行情抓取（含 host 轮换与重试）
│   ├── assemble.py                  变化检测与数据组装
│   ├── dedupe.py                    事件去重与重要性分级
│   ├── build_html.py                HTML 渲染
│   ├── build_xlsx.py                Excel 渲染
│   ├── check_html.py                HTML 静态校验
│   ├── check_xlsx.py                Excel 校验
│   ├── qa_render.py                 浏览器渲染实测（可选）
│   ├── selftest.py                  判定逻辑单测
│   ├── simulate_render.js           无浏览器时的 DOM 模拟渲染测试
│   ├── templates/brief.html         页面模板（含样式与交互）
│   └── assets/echarts.min.js        内联图表库
└── examples/
    └── 01-ma-pp-pvc-2026-10-20/     完整实战案例（可当模板复制）
```

## 换品种怎么办

`scripts/common.py` 的 `PRODUCT_LIB` 已内置常见品种的主连 secid 与交易所前缀。新增品种只需补一条：

```python
'尿素': ('115.URM', 'URM', '郑商所', 'UR'),
```

然后 `python scripts/fetch_futures.py 尿素 --out raw` 即可。交易所 secid 前缀：郑商所 115、大商所 114、上期所 113、上期能源 142、广期所 225。完整说明见 `references/adapters.md`。

## 第一次使用的最短路径

```bash
# 1 复制样例当作本期骨架
cp -r examples/01-ma-pp-pvc-2026-10-20 mybrief && cd mybrief

# 2 改 research.json 里的报告日、数值、来源（这是唯一需要人工判断的文件）

# 3 跑
python ../../scripts/assemble.py research.json --out build/data.json --baseline baseline_2026-10-16.json
python ../../scripts/build_html.py build/data.json --out out/晨报.html
python ../../scripts/build_xlsx.py build/data.json --out out/晨报.xlsx
python ../../scripts/check_html.py out/晨报.html build/data.json
```
