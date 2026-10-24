---
name: operating-rate-price-relationship
description: Use when a researcher or analyst asks whether a product's 开工率 / 产能利用率 / 装置负荷 / 检修损失量 indicator has a stable historical statistical relationship with later price moves — 检验开工率和价格的关系 / 开工率是否影响价格 / 开工率高低之后价格怎么走 / 开工率上升是不是要跌 / 检修多是不是要涨 / utilization factor study / operating rate factor. Deliverable is an honest statistical report: three factor families (absolute level, weekly change, expanding historical percentile) built strictly from point-in-time published data, forward 1/2/4-week spot and futures outcomes measured from the first tradable session after publication, overlap-aware and multiple-testing-corrected inference with explicit power/MDES reporting, per-year and per-process-route stability, placebo tests, plus a self-contained interactive HTML report and a multi-sheet Excel workbook.
---

# 开工率—价格关系检验（Operating Rate – Price Relationship Study）

## 这个 Skill 解决什么问题

给一个「品种 + 开工率指标」，回答**唯一一个**问题：

> 在历史上，当开工率处于某种状态（绝对水平高低、周度升降、历史分位高低）之后，
> 随后的 1 / 2 / 4 周里，现货与期货价格的变化是否表现出**稳定且可复现**的差异？

产出不是"信号"，而是**带不确定性的历史分布 + 数据可得性边界 + 明确失效区间**。

最关键的一句定位：

> 本 Skill 评估的是「开工率是否提供**稳定的历史统计信息**」，
> **不是**「开工率变化**导致**价格涨跌」。

## 什么时候用 / 不用

**用**：
- "XX 的开工率跟价格到底有没有关系？"
- "开工率上升之后是不是该跌？"
- "检修集中、开工下滑的时候价格会不会涨？"
- "帮我做一个开工率因子的历史检验，按工艺路线分开看"

**不用**：
- 只想知道开工率当前水平 / 最新一周 → 用行情类 Skill
- 想知道"谁领先谁"（两条序列的领先滞后） → 用 lead-lag 类 Skill
- 想回测一条明确交易规则（含成本、仓位） → 用策略回测类 Skill
- 想做供需平衡表推演 → 用平衡表类 Skill

## 八条不可妥协的原则

1. **先确认定义与公布时点，再谈统计关系。** 开工率的「定义」（产能利用率 / 装置开工负荷 / 检修损失反推）、「样本企业数」、「产能基数」、「统计周期」四件事必须逐期记录，并保留原文链接。
2. **公布时点 ≠ 统计周期结束。** 因子只用 `真实公布时间 ≤ t` 的信息；观察基期取**公布后第一个可交易交易日**的收盘。
3. **分位必须 expanding。** 历史分位只能用 t 之前**已公布**的样本；用全样本排名是最常见的未来函数。且必须披露「最少历史期数」与「因历史不足而未生成的期数」。
4. **重叠窗口如实处理。** 1/2/4 周窗口互相重叠：HAC(带宽 = 窗口 − 1) + 有效样本数 n_eff = n / (窗口 / 步长) + 块 bootstrap。
5. **必须先报功效，再报显著性。** 每个「因子 × 窗口」单元给出 n、n_eff、最小可检测效应 MDES、以及概率半宽。样本不足时结论必须是「数据不足，不可检验」，而不是「不显著 = 没关系」。
6. **多重检验必须校正。** 因子 × 窗口同时检验，用 BH-FDR，并给出「纯噪声下期望显著数」作参照。
7. **工艺路线必须单独看。** 同一品种的电石法 / 乙烯法 / 天然气法成本曲线不同，开工率对价格的含义可能相反。合并样本可能**掩盖方向相反的两组**。
8. **统计证据与产业解释分开写。** 前者是数字，后者是机制假设；不得用机制故事掩盖不显著或不稳定的结果。

## 标准流程

```
0. 口径与来源确认   → references/01-data-sources-and-release-calendar.md
1. 开工率序列构建   → references/02-utilization-series-construction.md
2. 价格序列与收益   → references/03-factor-construction.md
3. 三族因子构造     → references/03-factor-construction.md
4. 未来收益对齐     → scripts/pipeline.py (align / forward 阶段)
5. 分组统计与不确定性 → references/04-grouping-and-inference.md
6. 稳定性：年度 / 工艺路线 / 市场阶段 → references/05-stability-and-process-route.md
7. 安慰剂与多重检验 → references/06-placebo-and-multiple-testing.md
8. 报告与工作簿     → references/07-report-and-workbook-spec.md
9. 自查清单         → references/08-pitfalls-checklist.md
```

可复现脚本（与 PVC 案例完全同源）：

```bash
python scripts/pipeline.py --config examples/pvc-caulking-utilization/config.json
python scripts/build_outputs.py examples/pvc-caulking-utilization/output \
        examples/pvc-caulking-utilization/narrative.json
```

数字安全自检（本运行时必需，见下节）：

```bash
python scripts/float_numbers.py      # 必须 exit 0，否则不许发布
```

## ⚠ 本运行时的浮点转文本缺陷（务必先读）

本机上 `repr` / `str` / `f"{x}"` / `"%g"` / `json.dumps(x)` 在部分数值上会把**尾数中间的数字渲染成负号**，例如真实值 `-0.0111…` 可能被写成 `-0.0111-1288…`。数值本身正确，只有文本坏了。

因此**所有写入磁盘的数字都必须经过 `scripts/float_numbers.py`**：

- `fmt(x)` — 精确十进制文本
- `fmt_fixed(x, digits)` — 定点文本
- `int_to_str(n)` — 整数文本
- `dataframe_to_csv(df, path)` — 替代 `df.to_csv`
- `dumps(obj)` — 替代 `json.dumps`

发布前必须 `python scripts/float_numbers.py` 返回 0。这不是可选项：一旦绕过，报告与工作簿会显示错数字而计算完全正确。

## 典型产物

| 产物 | 说明 |
|---|---|
| `研究报告.html` | 自包含交互式（无外链 CDN）：可选开工率指标 / 未来窗口 / 工艺路线 / 分组规则，展示三族因子的分组结果、未来收益分布、年度稳定性；点击任一观测点显示该期原始数据 |
| `数据工作簿.xlsx` | 14 表：使用说明与质量声明、开工率原始、因子构造、未来收益、公式与参数、三族分组统计、显著性、年度与阶段、安慰剂与同向性、月度交叉验证、期货连续合约、期货月线 |
| `res_*.csv` / `summary.json` | 全部中间结果，可单独复核 |
| `raw/util_gaps.json` | **缺失周清单**：哪一周、为什么没拿到 |

## 硬性质量门（缺一项即视为未完成）

- [ ] 每期开工率都有 `stat_week_end`（统计截止）、`pub_ts`（真实公布时间）、`url`（原文）三列
- [ ] 记录「样本企业数」「产能基数」「样本调整事件」，且**样本调整前后不做无缝拼接**
- [ ] 因子列可逐行解释"这个数在当天算得出来吗"；分位列注明最少历史期数
- [ ] 未来收益的基期日期**严格晚于**公布时间
- [ ] 每个单元给出 n、n_eff、MDES；样本不足时明确写「不可检验」
- [ ] 报告同时给出：名义 p、HAC p、BH q、安慰剂 p
- [ ] 报告明确写出：显著组数 / 总检验数、FDR 后通过数、失效年份
- [ ] 工艺路线能分就分；不能分时写明原因
- [ ] 报告明确写出数据可得性边界，**不给缺口编造连续序列**（不得用产量、图表数字化、插值凑历史）
- [ ] 结论段区分「统计证据」与「产业解释」
- [ ] 全文不出现交易信号、仓位、收益承诺
- [ ] `python scripts/float_numbers.py` 返回 0

## 参数与默认值（不要寻优）

| 项目 | 默认 | 理由 |
|---|---|---|
| 未来窗口 | 1 / 2 / 4 周（5 / 10 / 20 交易日） | 与周频开工率匹配，覆盖常见持有期 |
| 水平分组 | 固定绝对阈值（按品种历史区间定一次后锁定） | 避免"挑最优切点" |
| 变化分组 | ±1.0 个百分点 | 低于此视为噪声 |
| 分位分组 | 历史分位 <33% / 33–67% / >67% | 三分位，样本利用充分 |
| 分位最少历史 | 52 周 | 一年，兼顾可用样本与稳定性 |
| 最少有效样本 | n_eff ≥ 30 | 低于此只报"不可检验" |
| HAC 带宽 | 窗口 − 1 | h 步重叠收益的标准做法 |
| bootstrap | 环形块，块长 = ⌈窗口/5⌉，2000 次 | 保留重叠依赖 |
| 置换检验 | 年度内循环平移，2000 次 | 保留季节性 |
| BH-FDR | q = 0.10 | 探索性研究的常规门槛 |

> **禁止**为了"跑出显著结果"而更改分组切点、窗口或样本区间；**禁止**事后只挑表现最好的那个因子定义。
> 若必须调整，须在报告中标注为事后探索，并**同时披露调整前后**的结果。

## 一句话预期管理

多数品种的结论会是下面三种之一，三种都是有价值的结果：

1. **开工率绝对水平几乎没有预测力**；"开工率变化的方向 + 持续性"偶有信息，但跨年不稳定。
2. **不同工艺路线方向相反**，合并样本互相抵消 —— 这正是"看总开工率看不出东西"的技术原因。
3. **公开数据根本不够检验**（周频样本 < 30 期）—— 此时正确结论是「数据不足，不可检验」，
   并写清需要多少期、需要哪些数据源，而不是用插值或产量数据凑一条曲线。

本 Skill 的 PVC 案例就是第 3 种：公开可得的开工率只有 7 周，因此报告的全部价值在于
**诚实地量化"这个样本量能检出多大的效应"**，而不是给一个假的相关系数。
