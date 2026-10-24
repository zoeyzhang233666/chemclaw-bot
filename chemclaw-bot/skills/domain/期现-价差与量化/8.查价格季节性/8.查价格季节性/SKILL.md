---
name: 查价格季节性
description: Use when someone needs to know how a commodity's price behaves at the same time of year across many years — 查价格季节性 / 季节性规律 / 历史同期对比 / 这几月是不是淡季 / 旺季规律 / 今年比往年同期贵还是便宜 / seasonality of prices — for any product in any region or contract. Aligns 5–10 years of real prices by ISO week or calendar month, shows each year's own trajectory, computes same-period mean / median / p10 / p25 / p75 / p90 with sample sizes, overlays the current year, and compares both absolute price and year-normalized returns, flagging anomalous years and their pull on the mean. Delivers a self-contained interactive HTML report plus a multi-sheet Excel workbook with live formulas. Never a price forecast.
---

# 查价格季节性

一句话：**把同一个品种、同一个地区/合约，过去 5–10 年在"一年中的第几周/第几月"的价格摆在一起，
看清今年此刻站在历史同期的什么位置 —— 并且严格只讲已经发生的事。**

交付两件东西：一个**能点、能切换、能悬停看具体年份**的单文件 HTML，一个**公式可复算**的 Excel。
不是交一张"季节性图"截图，也不是交一段"淡季已过、旺季将至"的判断。

---

## 三条硬规矩

1. **不预测。** 本 skill 的产物只描述历史已实现分布。禁止"预计/看涨看跌/将迎来旺季/底部已现"。
   要说的是"过去 4 年这一周落在 2,200–2,900 区间，今年 3,966 高于全部历史同期"，
   而不是"今年会回落"。**每个产物都必须带"非预测"声明**（HTML 首屏 + Excel 封面）。
2. **口径降级必须写进第一屏，不许悄悄替换。** 想要的是"华东甲醇现货"，
   实际只有"生意社甲醇基准价（全国口径）"，那就要在报告最顶部写明降级、原因、以及该口径
   不能用来推什么（区域价差、交割地贴水）。**永远不要把全国基准价写成区域现货价。**
3. **拿不到就不补造。** 不插值、不前值填充、不用行业均值顶替、不"补一个大概的数"。
   实际覆盖多少年就写多少年，缺哪一段就在覆盖表里标哪一段，缺报日期逐条列进缺口表。

---

## 六步流程

### 第 1 步 定口径（不确认完不动手）

| 要素 | 必问 | 踩过的坑 |
|---|---|---|
| 品种 + 规格 | 品种必问；规格默认该品种主流 | "甲醇"要写明是现货还是期货、哪种基准价 |
| 地区 / 合约 | 该品种主销区 | "华东现货"往往要付费；写清实际拿到的区域口径 |
| 频率 | 周度 / 月度（默认两套都给） | 周度必须用 ISO 周，不能用自然周 |
| 样本年数 | 5–10 年（默认 10，实际给到几年算几年） | 要的 10 年常常只能拿到 5 年 |
| 当前年 | 哪一年算"今年" | 当前年常常还没走完，必须标为部分覆盖 |

同时确认该品种**有没有场内期货**。有期货 = 多一条不受付费墙限制的 5–10 年日线序列，
可作为独立交叉验证；没有就只做现货，并在缺口表写明。

**完成标准**：五要素 + 有无期货，六项都有明确答案，且已写进 `config.json`。

### 第 2 步 抓真实历史价格（这一步决定报告值不值钱）

按 [`references/data-sources.md`](references/data-sources.md) 的渠道顺序逐条试，
**命中一条立刻记下口径六项**（数值·规格·地区·含税·日期·来源）。

核心顺序：
1. **生意社 100ppi 基准价频道**：`https://me.100ppi.com/news/list--1217-{page}.html`
   文章正文含"生意社XX基准价为 N 元/吨"，逐页翻即可拿到多年日频序列，**免费**。
   这是目前最稳的免费源，脚本见 `scripts/fetch_100ppi_methanol.py`（改品种即可复用）。
2. **新浪期货 K 线**：`InnerFuturesNewService.getDailyKLine?symbol=MA2701`，免费、按合约取，
   自己按持仓量拼主连（脚本 `scripts/fetch_contract_history.py`，含换月日志）。
3. **隆众 / 卓创**：区域现货日度最全，但**需要登录态或付费**，接口会返回 `-` 或空 `data`。
   探到这一步就**记录"不可得"**，不要反复试。
4. 其它行业资讯站 / 交易所 / 协会周报。

**抓完必须做三件审计**（`fetch_*.py` 里已内置，输出 `fetch_manifest.json`）：
- 逐行留 `source_url`（一条报价能点回原文）；
- 数工作日缺口（周末不算，停市日对照 `data/cn_market_holidays.txt` 扣除）；
- 找 `|Δ|>8%` 的跳变，逐条回原文核实是**源数据跳变**还是**解析错误**
  （脚本 `scripts/verify_jumps.py`）。

**完成标准**：CSV 里每行都有来源链接；缺口清单已产出；跳变已逐条定性；
并做一次**独立重抓比对**（同样的抓取再跑一遍，逐行比价，差异应为 0）。

### 第 3 步 对齐与统计（调 `seasonality_core.py`，不要手算）

```bash
python scripts/build_case.py --case <case_id>     # 产出 data/out/<case_id>.json
```

引擎负责全部派生，规则固定并已在 `scripts/selftest.py` 里锁死：

- **周度**：ISO 8601 周（周一为首日），**ISO 第 53 周折叠进第 52 周**；
  周值 = 该周最后一个有报价日。→ 见 [`references/alignment.md`](references/alignment.md)
- **月度**：自然月，月值 = 该月最后一个有报价日。
- **统计**：经验分位线性插值（= Excel `PERCENTILE.INC` = numpy 默认 = R type 7），
  同期样本给 mean / median / std / min / max / p10 p25 p50 p75 p90 / IQR / CV / n。
  → 见 [`references/statistics.md`](references/statistics.md)
- **归一化**：每年以该年窗口内**第一个有效观测**为 100（不是 1 月 1 日插值）。
- **当前年位置**：分位与排名**剔除当前年本身**，否则今年会抬高自己的基准。
- **异常年**：自动识别、给证据、**绝不自动删除**。→ 见 [`references/anomaly.md`](references/anomaly.md)
- **缺失**：同一位置有效年数 < `min_years`（默认 3）→ 标 `样本不足`，不参与形态判断。

**完成标准**：`python scripts/selftest.py` 全部通过（它验证分位一致性、53 周折叠、
不插值、趋势消除、异常识别、单调性、当前年剔除、重复/空值处理 8 组不变式）。

### 第 4 步 生成 HTML + Excel

```bash
python scripts/build_html.py --case <case_id>     # 单文件交互报告
python scripts/build_xlsx.py --case <case_id>     # 13 表工作簿（活公式）
```

HTML 必须做到（模板 `templates/report_template.html` 已实现）：
选择品种/样本年数 · 季节性分位带 · 当前年高亮 · 逐年开关 · 绝对价格/归一化切换 ·
悬停看具体年份数值 · 覆盖与样本量面板 · 首屏"非预测"声明 · **零外链、离线可开**。

Excel 必须做到（`scripts/build_xlsx.py` 已实现 13 表）：
日度价格（含来源链接）· 周度/月度面板（年份×位置矩阵）· 周次映射规则 ·
周度/月度统计（**统计列是真公式**，直连面板，改面板按 F9 复算）· 归一化面板 ·
当前年位置 · 异常年证据 · 样本覆盖 · 数据缺口 · 来源与复现。

**完成标准**：两个文件都生成；HTML ≈100–300 KB 且无外链；Excel 含上千个活公式。

### 第 5 步 自检（这一步不能跳）

```bash
python scripts/qa_html.py out/xxx.html            # 浏览器实测，必须 0 失败
python scripts/check_xlsx.py out/xxx.xlsx <case> --recalc out/_recalc.xlsx   # 必须 0 失败
```

`qa_html.py` 用 Playwright 真开浏览器：抓 JS 报错、确认 SVG 真画出像素、
**真的去点**频率切换/归一化切换/年份全关全开、**真的去悬停**看 tooltip、
1600/1280/420 三档查横向溢出。

`check_xlsx.py` 做两件事：结构（13 表齐全、无预测词、无占位符）+
**用 LibreOffice 重算公式后逐位置比对引擎 JSON** —— 这是最容易被手改破坏的一环。

> ⚠ 写 Excel 分位公式时用 `_xlfn.PERCENTILE.INC`（或外层套裸 `PERCENTILE` 兜底）。
> openpyxl 写的裸 `PERCENTILE.INC` 在重算引擎里会变成 `#NAME?`/`#VALUE!`，
> 而 `#VALUE!` 会被 `IFERROR` 吞掉看不见 —— **只查"有没有公式"是查不出来的，必须核对重算值**。

### 第 6 步 交付

产物 + **一段 3–5 句的事实摘要** + **缺口清单**。摘要只陈述事实：
覆盖了几年、这一周历史区间是多少、今年在第几分位、哪些年份异常。
不要在回复里重写整份报告，也不要在摘要里给方向判断。

---

## 交付物结构

```
out/<品种>-<地区>_季节性分析报告.html     单文件交互看板（离线可开）
out/<品种>-<地区>_季节性数据工作簿.xlsx   13 表，公式可复算
```

### Excel 13 表

| # | 表 | 作用 |
|---|---|---|
| 00 | 封面与口径 | 需求口径/实际口径/降级说明/区间/覆盖/使用边界 |
| 01 | 日度价格 | 原始逐日报价 + 来源链接，可逐行追溯 |
| 02 | 周度面板 | 年份 × ISO 周 矩阵（每年一条独立轨迹）+ 折线图 |
| 03 | 月度面板 | 年份 × 月 矩阵 |
| 04 | 周次映射规则 | ISO 周定义、53 周折叠、取数规则、长假处理、逐年覆盖 |
| 05 | 周度统计 | 均值/中位/分位/CV（**活公式直连 02**） |
| 06 | 月度统计 | 同上（直连 03） |
| 07 | 归一化面板 | 年初=100 的逐年轨迹 |
| 08 | 当前年位置 | 当前年 vs 历史同期（不含当年）分位/排名/z |
| 09 | 异常年证据 | 逐位置离群证据 + 剔除后均值变化 |
| 10 | 样本覆盖 | 每年首末位置/报价天数/内部缺口/可否统计 |
| 11 | 数据缺口 | 工作日缺报清单 + 停市日扣除 + 不可得口径 |
| 12 | 来源与复现 | 数据源/时间/校验方式/复现命令 |

---

## 降级路径

| 情况 | 做法 |
|---|---|
| 区域现货拿不到，只有全国基准价 | **保留分析**，首屏声明降级，并写明该口径不能推区域价差 |
| 只要 10 年只拿到 5 年 | 照实做 5 年，首屏写"申请 10 年，实际覆盖 5 年"，覆盖表标部分年份 |
| 当前年还没走完 | 标"部分覆盖"，计入覆盖表但**不计入完整年份**，分位计算时剔除当年 |
| 某年整段缺失 | 该位置该年留空，`years_missing` 记下，n 变小；n<3 标样本不足 |
| 该品种无期货 | 只做现货；缺口表写"无场内期货，未做期货交叉验证" |
| 样本只有 3–4 年 | 照实出，但**每处结论都带 n**，并把"弱样本强读数"写进提示 |
| 想做季度而非全年 | 改 `config.json` 的 `window_start_iso_week` / `window_end_iso_week` |

---

## 参考与示例

- [`references/alignment.md`](references/alignment.md) — 周次对齐、53 周折叠、长假、缺口、归一化基期
- [`references/statistics.md`](references/statistics.md) — 分位算法、小样本、均值 vs 中位数、季节性强度 R²
- [`references/anomaly.md`](references/anomaly.md) — 异常年判定规则、为什么**不自动删除**、如何报告影响
- [`references/data-sources.md`](references/data-sources.md) — 逐渠道可用性、接口细节、踩坑记录
- [`references/qa-checklist.md`](references/qa-checklist.md) — 交付前逐项打勾
- [`examples/01-华东甲醇现货/`](examples/01-华东甲醇现货/) — 完整案例（真实数据、真实缺口、完整走查）
- [`templates/`](templates/) — HTML 模板、配置模板

## 脚本清单

| 脚本 | 作用 |
|---|---|
| `scripts/seasonality_core.py` | 引擎：对齐/统计/归一化/异常/覆盖（所有派生都在这） |
| `scripts/build_case.py` | 跑某个 case 的全部统计 → `data/out/<case>.json` |
| `scripts/build_html.py` | JSON → 单文件交互 HTML |
| `scripts/build_xlsx.py` | JSON → 13 表工作簿（活公式） |
| `scripts/selftest.py` | 引擎 8 组不变式自测 |
| `scripts/qa_html.py` | 浏览器实测报告（Playwright） |
| `scripts/check_xlsx.py` | 工作簿结构 + 公式重算一致性校验 |
| `scripts/fetch_100ppi_methanol.py` | 生意社基准价抓取（改品种可复用） |
| `scripts/fetch_contract_history.py` | 新浪期货逐合约 K 线 + 主连拼接（含换月日志） |
| `scripts/verify_jumps.py` | 跳变日回原文核实 |
