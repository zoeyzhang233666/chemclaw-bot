---
name: policy-event-study
description: Use when someone wants to test what a government policy actually did to a commodity's price and basis — “某政策对纯碱/玻璃/甲醇的价格和基差有多大影响”、“做个政策事件研究”、“环保限产/出口退税/能耗双控/关税调整对行情的影响”、“复盘政策发布前后的价格走势”. Covers: 政策原文字节级核验、发布日/首知日/生效日三重时间锚点、政策事件分类与可比性判断、Event Study 窗口计算（1/5/10/20 日）、逐事件归因边界、混杂因素清单。Delivers a self-contained interactive HTML report plus a 12-sheet Excel workbook, and refuses to report significance when n < 5.
---

# 做政策事件研究（Policy Event Study）

把"某政策出台 → 价格涨了跌了"这种口头因果，做成**能被反驳的证据链**：
政策原文核实到文号 → 三重时间锚点 → 可比性分组 → 窗口统计 → 逐事件归因边界。

## 四条硬规矩（违反任一条，本次交付作废）

1. **不把价格变化全部归因给政策。** 事件窗内的价格是政策、产业周期、宏观、资金、信息噪声共同的结果。
   只陈述"时间上重合"，不写"政策导致价格上涨 X 元"。
2. **样本量 n < 5 不计算显著性。** 不打 p 值、不写"显著"、不写"有效应"。只给均值/中位数/分位等描述统计。
   事件研究尤其如此——事件不可重复，样本天生小。
3. **三重日期必须分开。** 原文发布日 ≠ 市场首知日 ≠ 政策生效日。只报一个锚点、且挑最有利的那个，等于造假。
4. **拿不到就写缺口。** 政策原文查不到官方源就标"二手转载/未找到"，价格缺就留空。
   不插值、不估算、不用行业均值顶替。

## 六步

### 第 0 步：确认口径（必问，不猜）

| 要素 | 为什么必须问 |
|---|---|
| 品种 + 期货代码 | 决定能不能算基差（无期货则退化为现货单序列） |
| 政策类型 | 环保限产 / 能耗约束 / 产业准入 / 税收贸易 / 价格干预，性质和渠道完全不同 |
| 时间范围 | 决定样本量。注意**期货上市日之前的基差不可得**（纯碱 SA 为 2019-12-06） |
| 地区 | 区域政策（如青海督察）与全国政策不可比，必须分组建模 |

同时确认：该品种的**价格序列实际能从哪一年取到**。很多品种的"全国均价基准价"序列只有近几年，
不要用"用户要求 2015 年起"倒推数据存在。**完成标准**：四项口径 + 数据实际覆盖区间，五项都有确定答案。

### 第 1 步：核验政策原文（最容易被跳过、也最决定成败的一步）

逐条打开**发布机关官网**（*.gov.cn / ndrc / miit / mee / chinatax / 交易所），下载 PDF 附件做全文比对。
细则见 [`references/policy-source-verification.md`](references/policy-source-verification.md)。

**必查的四类坑**（纯碱案例中全部踩过）：
- **文件名改了**：征求意见时叫《目录（2023年本）》，正式发布才叫《2024年本》。只搜"2024年本"必然漏掉征求意见稿。
- **条款在征求意见稿里就已经改了**：真正的"市场首知日"可能比正式发布早 5 个月。
- **政策不适用于该品种**：出口退税公告的附件清单要逐税号检索，纯碱 HS2836 在 209 项里零命中。
  这类文件不要硬当事件，**改作安慰剂对照**反而更有价值。
- **通报≠停产**：督察原文可能是"未落实限产50%的要求"，不是"责令停产"。措辞差异直接决定方向判断。

**完成标准**：每个事件都有 `publish_date / market_first_aware / effective_date` 三个日期，
且每个日期都能指向一段原文或一个官方链接；核验状态明确标注（原文 / 二手转载 / 存疑）。

### 第 2 步：取价格数据

优先级：交易所官方 → AKShare（`futures_spot_price_daily` 可批量取期现价+基差）→ 第三方产业资讯。
**必须做双源交叉验证**：纯碱案例中，100ppi 逐日抓取与 AKShare 期现表在 1546 个交易日上零差异，
这个校验把"数据可信"从表态变成了证据。方法见 [`references/data-provenance.md`](references/data-provenance.md)。

注意两个口径陷阱：
- **全国均价 vs 交割地价**：现货是"全国均价"、期货交割基准是"华东/华北"，两者存在恒定水平偏误。
  **基差水平值不可直接交易**，但基差变动（Δ基差）在同期内可用。
- **上市日边界**：期货上市前没有基差，相关事件只能定性讨论，不许用现货替代期货拼基差。

### 第 3 步：政策事件分类与可比性判断（决定能不能做统计）

先回答"这些事件能不能放在一张表里算平均值"，再谈统计。五个维度逐项判断：

约束性（强制/指导）· 覆盖范围（全国/区域）· 政策方向（收紧/放松）· 传导渠道 · 市场背景

任一维度差异过大 → **不合并**，单独成组。纯碱案例的结论是：
13 个事件拆成 7 个可比组，其中只有 G1（全国性强制约束）达到 n=5 的统计门槛，
**且剔除方向相反的放松型事件后仅剩 n=4，又跌回门槛之下**——这个细节必须写进报告。

详见 [`references/comparability-rules.md`](references/comparability-rules.md)。

### 第 4 步：跑 Event Study

```bash
python scripts/event_study.py --selftest          # 先自检，确认引擎正常
python scripts/event_study.py --config build/events.json \
                              --prices build/prices.json --out build
```

引擎行为（已内置，不要绕过）：
- 事件前最后一个交易日 = 基准日 T-1；T+k 为事件后第 k 个交易日；
- 三个锚点**各跑一遍**，全部输出；
- 缺数据留 `None`，路径出现断点就是缺数据，**不插值**；
- `n < MIN_N_FOR_SIGNIFICANCE(=5)` 时 `p_value` 恒为 `None`。

**完成标准**：`event_stats.json` / `event_windows.csv` / `paths.json` 三件产出齐全，
且 `study['gaps']` 如实反映缺失。

### 第 5 步：生成 HTML + Excel

```bash
python templates/build_html.py --research build/research.json \
        --study build/event_stats.json --out out/<品种>_政策事件研究报告.html
python templates/build_xlsx.py --research build/research.json \
        --study build/event_stats.json --out out/<品种>_政策事件研究.xlsx
```

`research.json` 的字段见 [`references/data-contract.md`](references/data-contract.md)。
**结论段里的数字一律从 `event_stats.json` 读出来写，不许手敲**——手敲必与统计结果不一致。

**完成标准**：HTML ≈1.2 MB（说明 ECharts 内联成功）、Excel 12 张表齐全。

### 第 6 步：自检并交付

```bash
python templates/check_report.py out/xxx.html build/event_stats.json
```

检查项：占位符残留、外链、JS 报错、三张图是否画出像素、各模块渲染数、三档分辨率横向溢出、
样本不足时是否真的没出现 p 值、禁用词（"预计/看涨/抄底/必然"）。

改过模板或脚本后跑 `python scripts/event_study.py --selftest`。**必须 0 失败。**

交付时给：两个文件的绝对路径 + 3~5 句事实摘要 + **可比性结论**（能不能做统计）+ **缺口清单**。
不要在回复里重写整份报告。

## 最容易出错的六件事

| 现象 | 正确做法 |
|---|---|
| 只报一个时间锚点 | 三锚点全报。纯碱案例中 G1 的 +20 日期货变动在两种锚点下是 +69.2 与 +7.6，方向都变了 |
| 把系统性冲击当品种政策 | 先查有没有**指名该品种**的部委文件；没有就单列，别并入政策组 |
| 事件窗重叠还分开算 | 相距 < 20 交易日的事件要么合并为一个事件，要么明确披露重叠 |
| 用全段涨跌幅当事件收益 | 全段跨了多个事件。用窄窗 [−1,+1]/[−1,+3]，并注意涨跌停造成的滞后反应 |
| 信息污染没剔除 | 查证监会处罚决定；纯碱 2023-11-28～12-01 有已处罚的虚假信息，正好压在督察通报窗上 |
| 把"不适用"的文件扔掉 | 改作安慰剂对照。若安慰剂也"有效应"，说明模型在抓噪声 |

## 交付物

- `out/<品种>_政策事件研究报告.html`：单文件离线、零外链、内联 ECharts，双击可开、可微信发送
- `out/<品种>_政策事件研究.xlsx`：12 表，与 HTML 同源同数

## 降级路径

| 情况 | 做法 |
|---|---|
| 无期货 | 只算现货序列，基差全部标缺口，报告自动降级 |
| 现货序列起点晚于政策事件 | 该事件只做定性/政策叙事，不进入统计，明确标注原因 |
| 所有组 n < 5 | 只做逐事件分析，首页红框声明"不做汇总统计" |
| 政策原文只找到二手转载 | 保留但标 `二手转载`，不标"原文已核" |
| 没装 playwright | 跳过浏览器实测，静态检查仍执行 |

## 参考

- [`references/policy-source-verification.md`](references/policy-source-verification.md)——政策原文核验方法、政府站点特性、四类坑
- [`references/comparability-rules.md`](references/comparability-rules.md)——五维可比性判断、分组规则、何时禁止汇总
- [`references/data-provenance.md`](references/data-provenance.md)——价格数据源优先级、双源校验、口径陷阱
- [`references/data-contract.md`](references/data-contract.md)——`events.json` / `prices.json` / `research.json` 全字段
- [`examples/01-soda-ash-policy/`](examples/01-soda-ash-policy)——纯碱完整案例（13 事件、21 处原文、1546 日序列）
