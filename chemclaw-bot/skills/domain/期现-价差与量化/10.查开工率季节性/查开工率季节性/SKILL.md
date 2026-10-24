---
name: operating-rate-seasonality
description: Use when someone needs to know whether a plant/industry operating rate (开工率/产能利用率/开工负荷率) is high or low *for this time of year* — 查开工率季节性 / 开工率历史分位 / 今年开工率跟往年比 / 检修季规律 / 春节前后负荷 / 产能利用率季节性 — for any chemical or material where a weekly or monthly operating-rate series exists. Delivers a self-contained interactive HTML seasonality report plus a multi-sheet Excel workbook in which every number carries source URL, sample definition, capacity base and release cadence, and every missing week is marked as a gap instead of being interpolated.
---

# 查开工率季节性（Operating-Rate Seasonality）

## 这个 Skill 解决什么问题

用户问的是：**“现在这个开工率，算高还是低？”**

而“高低”只有在**同一产品、同一口径、同一周号**的历史坐标里才有意义。
最常见的三种错误答案：

1. 拿今年的数字和“印象中的常年水平”比，不给任何可核验的历史序列；
2. 手上只有一个数据源的一个短序列，却算出了“P10–P90 区间”和“当前处于 30% 分位”；
3. 把不同机构（隆众/卓创/钢联）的“开工率”拼成一条线，拼出一条**根本不存在的季节性**。

本 Skill 的核心不是画图，而是**在数据不够时明确拒绝给结论，并说清缺什么**。

## 何时使用

| 触发场景 | 是否使用 |
|---|---|
| “PVC 现在开工率多少？比往年同期高还是低？” | ✅ |
| “装置检修季是几月？开工率低点在哪个季度？” | ✅ |
| “今年春节后复工比往年快吗？” | ✅ |
| “给我做个尿素/纯碱/甲醇/PTA 开工率季节性” | ✅（任何有周/月度开工率序列的品种） |
| 只问“今天开工率多少” | ⚠️ 偏简单，但若要做判断仍需本 Skill |
| 问“这个月产量多少” | ❌ 用产量工具，开工率≠产量（见下） |
| 问价格季节性 | ❌ 用基差/价格季节性 Skill，方法论同源但数据对象不同 |

## 铁律（不可协商）

1. **开工率 ≠ 产能利用率（统计局）≠ 实际产量。** 三者定义不同、样本不同、频率不同，禁止互换或换算。
2. **样本开工率不得直接等同于全行业实际产量。** `利用率 × 全国产能 = 产量` 是错误换算。
3. **只统计真实观测。** 不插值、不前向填充、不用“上一期”补洞、不拿首周冒充 12 周前。缺数就写“缺口”。
4. **分位数少于 3 个样本不出**，少于 5 个样本必须标注“样本不足”。要在输出里打印 n 和年份。
5. **不同发布方不得合并成一条序列。** 只做方向性对照，登记在单独的“异口径”表里。
6. **环比/同比的锚点在源头上就要问清。** 多数机构的“环比”=与上一个**发布日**比，不是 ISO 周−1。
7. **移动节假日（春节）必须另建相对周视图**，不能只做 ISO 周对齐。

## 工作流

### 第 0 步：先确认口径（不确认就不要往下走）

向用户（或从数据源文档中）问清这 6 件事，记到 `assets` 的“口径定义”页：

| 问题 | 为什么必须问 |
|---|---|
| **指标全称** | “开工率”“开工负荷率”“产能利用率”字面不同，往往定义也不同 |
| **样本企业与厂区数** | 样本变了，数字就不可跨期比 |
| **产能基数** | 分母；每年年底会不会剔除僵尸产能（连续停车 ≥2 年）？ |
| **统计周期** | “自然周”？“上周五~本周四”？“周五~次周四”？决定怎么对齐 |
| **发布节奏** | 每周几发？有没有断档/合并发布？ |
| **覆盖范围** | 全国？分省份？分工艺（电石法/乙烯法、联碱/氨碱、煤制/气制）？ |

参考：[references/data-sources.md](references/data-sources.md)

### 第 1 步：取数并登记来源

每个观测必须能追到：`周期截止日`、`值`、`来源 URL`、`原文摘录`、`口径标签`。
登记表格式见 [templates/data_register.csv](templates/data_register.csv)。

宁可只有 12 个带源的观测，也不要有 260 个来源不明的观测。

### 第 2 步：审计可比性（最容易翻车的一步）

逐项检查：样本数量是否变化、产能基数是否变更、统计周期是否漂移、发布节奏是否跳跃、
指标名称是否被混用。每一项变更都要在报告里**显式标注为口径变更点**。

参考：[references/comparability-audit.md](references/comparability-audit.md)

> 本项目踩过的坑：2026-08-20 起所有“环比”都被判定为不一致，原因是拿 ISO 周−1 去匹配，
> 而原文的环比锚点是**上一个发布日**。改用真实发布间隔后立刻对齐。
> **没有对齐的环比，说明你对齐错了，不是数据错了。**

### 第 3 步：周次对齐

两套视图，**并列给出，不互相替代**：

- **ISO 周视图**：按覆盖周四（或发布日）的 ISO 周号对齐。适合“通常的”季节性。
- **春节相对周视图**：以春节所在周为 0，前后 ±N 周。适合 1—3 月。

春节在 1 月下旬到 2 月中旬之间漂移，**最多差 4~5 个 ISO 周**。
只用 ISO 周对齐会把节前备货、节中停车、节后复工三个状态混在一起。

公式与等价性验证见 [references/stat-methods.md](references/stat-methods.md)。

### 第 4 步：统计

```bash
python scripts/seasonality.py --weekly raw/pvc_util_weekly.csv \
       --anchor-series raw/anchor_weekly.csv --out out
```

产出：`seasonal_profile.csv`（同周均值/中位数/分位）、`current_year.csv`（今年逐周定位 + 4W/12W）、
`anomaly.csv`（异常年）、`comparison.csv`（跨年对照）、`summary.json`。

口径必须锁死为：**经验分位线性插值** = Excel `PERCENTILE.INC` = R `quantile(type=7)`
= `numpy.percentile(method='linear')`。四处必须一致，否则报告和 Excel 会打架。

### 第 5 步：解释季节性成因

季节性不是“曲线看起来有峰谷”，而是要有**机制**。逐条核实并写明证据：

| 机制 | 需要什么证据 | 常见陷阱 |
|---|---|---|
| 春节 / 长假 | 春节日期表 + 节前节后周度值 | 与“冬季需求淡季”混淆 |
| 集中检修（春检/秋检/夏检） | 检修产能、检修损失量、检修计划表 | 检修季与需求淡季时间重叠，单看开工率分不清原因 |
| 需求季节性（施工/农业/纺织） | 下游开工率、订单、库存 | 下游口径与上游口径不可混用 |
| 成本与利润（以碱补氯、煤头/气头价差） | 成本曲线、综合利润 | 高利润可以压过季节性 |
| 政策与事件（能耗双控、限电、节能监察、关停） | 政策文号、执行范围、时间 | 一次性冲击**不是**季节性，别混进季节曲线 |

参考：[references/event-calendar.md](references/event-calendar.md)

### 第 6 步：出报告

```bash
python scripts/make_html.py   --out assets/report.html
python scripts/make_xlsx.py   --out assets/workbook.xlsx
```

- HTML：自包含单文件，无外部 CDN；含指标切换、逐周悬浮明细、断档标记。
- Excel：多 sheet；**公式可复算**（真实 `PERCENTILE.INC` 等，不是粘贴数值）；
  口径警示/缺口/已处理三种配色固定。

### 第 7 步：自检

```bash
python scripts/selfcheck.py
```

检查：缺口是否被填、分位是否在 n<3 时被算出、HTML 是否有 undefined/NaN、
Excel 公式是否能重算、跨源数据是否混入主序列。

## 结论怎么措辞（照着抄）

| 情况 | 可以写 | 不可以写 |
|---|---|---|
| 有 ≥3 年同周数据 | “本周 68.2%，处于近 3 年同周 P35” | “处于历史低位”（不给分位不给依据） |
| 只有 1 年数据 | “本周 64.59%，为 **2026 年内** 最低” | “处于历史低位” |
| 只有单周锚点 | “与 2025-07-04 的 77.44% 相比低 12.85pp（非同周号）” | “同周同比下降 12.85pp” |
| 数据不足 | “**本期不出具季节性结论**，需补齐 ≥3 年逐周数据” | 用 1 年数据算 P10–P90 |

## 交付物清单

```
SKILL.md
references/data-sources.md          取数渠道与各家口径差异
references/stat-methods.md          统计口径、公式、等价性
references/comparability-audit.md   可比性审计清单
references/event-calendar.md        春节/检修/事件台账模板
templates/data_register.csv         观测登记表
templates/report_template.md        报告骨架
scripts/seasonality.py              统计引擎（产品无关）
scripts/make_html.py                HTML 生成
scripts/make_xlsx.py                Excel 生成
scripts/selfcheck.py                自检
examples/pvc-china/                 完整案例：中国 PVC 开工率季节性
assets/                             成品 HTML + XLSX
```

## 完整案例

[examples/pvc-china/README.md](examples/pvc-china/README.md) —— 中国 PVC（2026-W30~W42，12 个带源观测，
71 家样本，电石法/乙烯法双口径），含 7 项要求的逐条应答与**为什么不出季节性结论**的完整论证。
