---
name: inventory-price-relationship
description: Use when a researcher or analyst asks whether a product's INVENTORY indicator (港口库存 / 企业库存 / 社会库存 / 厂库 / 交易所仓单) has a stable historical statistical relationship with later price or basis changes — 检验库存和价格的关系 / 库存是否影响价格 / 库存对基差有没有预测力 / 累库去库之后价格怎么走 / 库存因子回测 / inventory factor study. Deliverable is an honest statistical report: factors built strictly from point-in-time (already-published) data, forward 1/2/4-week spot, futures and basis outcomes measured from the first tradable session after release, overlap-aware and multiple-testing-corrected inference, per-year stability, placebo tests, plus a self-contained interactive HTML report and a multi-sheet Excel workbook.
---

# 库存—价格关系检验（Inventory–Price Relationship Study）

## 这个 Skill 解决什么问题

给一个「品种 + 库存指标」，回答**唯一一个**问题：

> 在历史上，当库存处于某种状态（水平高低、累库/去库、连续变化）之后，
> 随后的 1 / 2 / 4 周里，现货价格、期货收益率与基差变化是否表现出**稳定且可复现**的差异？

产出不是"信号"，而是**带置信区间的历史分布 + 数据可得性边界 + 失效区间**。

## 什么时候用 / 不用

**用**：
- "XX 的港口库存跟价格到底有没有关系？"
- "累库之后是不是该跌？"
- "库存能不能预测基差？"
- "帮我做一个库存因子的历史检验"

**不用**：
- 只想知道库存当前水平 → 用行情类 Skill
- 想知道"谁领先谁"（两个序列的领先滞后） → 用 lead-lag 类 Skill
- 想回测一条明确交易规则（含成本、仓位） → 用策略回测类 Skill

## 七条不可妥协的原则

1. **先确认公布时点，再谈统计关系。** 库存数据的"统计截止日"和"真实公布时点"必须分开记录。所有因子只用 `公布时间 ≤ t` 的信息。
2. **分位必须 expanding。** 历史分位/标准化只能用 t 之前**已公布**的样本；用全样本排名做历史信号是最常见的未来函数。
3. **观察基期后移。** 库存 14:00 公布、现货收盘价 16:30 才定，基期取**公布后第一个交易日收盘**。
4. **重叠窗口如实处理。** 1/2/4 周窗口互相重叠：HAC(带宽=窗口−1) + 非重叠子样本 + 块 bootstrap。
5. **季节性必须单独处理。** 库存与价格都强季节性，普通随机置换会**高估**显著性；用**年度内循环平移**做安慰剂。
6. **多重检验必须校正。** 因子×目标×窗口同时检验，用 BH-FDR；并给出"纯噪声下期望显著数"作为参照。
7. **统计证据与产业解释分开写。** 前者是数字，后者是机制假设；不得用机制故事去掩盖不显著的结果。

## 标准流程

```
0. 定义文档       → references/01-data-and-release-calendar.md
1. 库存序列构建   → references/02-inventory-series-construction.md
2. 价格与基差     → references/03-factor-construction.md
3. 因子构造       → references/03-factor-construction.md
4. 未来收益对齐   → scripts/pipeline.py (align stage)
5. 分组统计       → references/04-grouping-and-inference.md
6. 稳定性与安慰剂 → references/05-stability-placebo-multiple-testing.md
7. 报告与工作簿   → references/06-report-and-workbook-spec.md
8. 自查清单       → references/07-pitfalls-checklist.md
```

可复现脚本（与案例完全同源）：

```bash
python scripts/pipeline.py --config examples/methanol-port-inventory/config.json
```

## 典型产物

| 产物 | 说明 |
|---|---|
| `研究报告.html` | 自包含交互式（无外链 CDN），章节含数据口径/时点管理/总览/54 组检验/分组分布/分年度/显著性与安慰剂/失效区间/方法论自查/结论 |
| `数据工作簿.xlsx` | 12 表：原始库存、因子构造、未来收益、分组统计、样本数量、分年度、显著性、安慰剂、稳健性、日度价格、口径说明 |
| `res_*.csv` | 全部中间结果，可单独复核 |

## 硬性质量门（缺一项即视为未完成）

- [ ] 每期库存都有 `asof`（统计截止日）与 `pub_ts`（真实公布时间）两列，并保留原文链接
- [ ] 因子列可逐行解释"这个数在当天算得出来吗"
- [ ] 未来收益的基期日期**严格晚于**公布时间
- [ ] 报告同时给出：名义 p、HAC p、BH q、安慰剂 p
- [ ] 报告明确写出：显著组数 / 总检验数、FDR 后通过数、失效年份
- [ ] 报告明确写出数据可得性边界，**不给 2019–2023 这类缺口编造连续序列**
- [ ] 结论段区分「统计证据」与「产业解释」
- [ ] 全文不出现交易信号、仓位、收益承诺

## 参数与默认值（不要寻优）

| 项目 | 默认 | 理由 |
|---|---|---|
| 未来窗口 | 1 / 2 / 4 周 | 与库存周频匹配，且覆盖常见持有期 |
| 分位分组 | p20 / p50 / p80 | 固定阈值，避免"挑最优切点" |
| 周度变化分组 | ±3 万吨（按品种量级调整一次后固定） | 同上 |
| 分位最少历史 | 26 周 | 半年，兼顾可用样本与稳定性 |
| HAC 带宽 | 窗口 − 1 | h 步重叠收益的标准做法 |
| bootstrap | 环形块，块长=窗口，2000 次 | 保留重叠依赖 |
| 置换检验 | 年度内循环平移，2000 次 | 保留季节性 |

> **禁止**为了"跑出显著结果"而更改分组切点、窗口或样本区间。若必须调整，须在报告中标注为事后探索并同时披露调整前后结果。

## 一句话预期管理

多数品种的结论会是：**库存绝对水平几乎没有预测能力；库存"变化的方向+持续性"偶有信息，但跨年不稳定。**
这正是有价值的结论——它阻止使用者把季度故事当成量化规律。
