---
name: chain-divergence-scan
description: Use when someone asks to find chemical product pairs whose recent prices have diverged abnormally from their industrial-chain relationship — 扫描产业链异常背离 / 哪些品种对背离了 / 上下游价差异常 / 相关品种脱钩 / 比价偏离历史区间 / 加工费异常 / 品种间价差异常 — for example PP vs LLDPE, PX vs PTA, 焦煤 vs 焦炭, 甲醇 vs PP. Delivers a self-contained interactive HTML dashboard (universe & relation-type pickers, anomaly leaderboard, chain graph, per-pair research page) plus a 16-sheet Excel workbook in which every pair carries its industrial relation + source, alignment rules, standardized changes, spread/ratio z, rolling return correlation, both sides' inventory/operating-rate/events checklist, and a data-comparability grade — and states plainly when no pair actually qualifies.
---

# 扫描产业链异常背离（Chain Divergence Scan）

## 这个 Skill 干什么

在**有真实产业关系的品种对**里，找"最近价格关系明显不对劲"的组合，并把**产业关系 + 统计异常程度 +
基本面可解释性 + 数据可比性**四件事一起交代清楚。

七个必答问题，缺一不可：

1. **这些品种对有产业关系吗**——上下游 / 共用原料 / 替代 / 同装置切换，逐条带类型、强度、系数与来源。
2. **价格是怎么对齐的**——重叠交易日、换月剔除规则、不插补不外推。
3. **变化可不可比**——标准化价格变化（σ 单位），而不是"涨了多少钱"。
4. **价差/比价偏不偏**——对数价差（有系数的用 ln(P_B) − ln(k·P_A)），滚动 z，历史分位。
5. **联动有没有变弱**——滚动收益率相关、"脱钩"幅度（|r_all| − r_roll）。
6. **异常说不说得通**——双方库存 / 开工 / 供需 / 成本 / 重要事件。
7. **哪些组合本来就不该扫**——数据不足、关系不稳、口径不可比，必须显式列出。

**绝不做的事**：对无产业关联的品种做 C(n,2) 全遍历；把统计偏离直接写成交易建议；
为了让结果好看而调窗口/阈值/起点；在没数据的地方插值、外推、编造数字。

---

## 什么时候用 / 不用

**用**：PP-LLDPE、PX-PTA、焦煤-焦炭、甲醇-PP 这类**有明确产业关系**的品种对，
判断近期是否出现"价差偏离 + 联动变弱"的异常背离。

**不用**：
- 只想看单个品种走势 → `chem-market-brief`
- 只想算两个指标的相关性（含库存等非价格指标）→ `two-indicator-correlation`
- 只想看月差、基差、区域价差 → 对应专项 skill
- 想要交易信号/仓位建议 → 这不是研究工具，不给

---

## 执行流程（8 步）

### 第 0 步：先有真实数据

```bash
python scripts/fetch_futures.py --symbols PP0 L0 PX0 TA0 MA0 EG0 --out data
```

生成 `data/{CODE}.csv`（`date,open,high,low,close,volume,open_interest,settle`）。
**没有真实序列就不要往下走**——先跟用户确认数据来源，不许"估一个"。

数据自检：每个品种的起止日期与交易日数必须打印出来并记录。
本次实测：PX0 只从 2023-09-15 起（745 日），其余品种 1600–5300 日不等。

### 第 1 步：登记产业关系（最重要的一步）

编辑 `scripts/chain_graph.py` 里的 `RELATIONS`，每条至少写：

```python
dict(a='PX0', b='TA0', rtype='upstream_downstream', strength='strong',
     direction='upstream_to_downstream',
     a_role='对二甲苯，PTA 的唯一主流原料',
     b_role='精对苯二甲酸，PX 经氧化加氢制得',
     mechanism='吨 PTA 约耗 0.655 吨 PX，价差即 PTA 加工费',
     k=0.655, coef_kind='吨耗系数',
     market_convention='PTA 加工费 = PTA 价格 − 0.655 × PX 价格',
     source_ids=['S5','S6','S7'],
     comparability='均为期货主力连续价；与现货加工费口径不同')
```

来源统一登记进 `scripts/sources.py`（**标题 + URL + 日期 + 用途**，四者缺一不可）。

四类关系与判定要求见 `references/01-产业关系类型与配对规则.md`。
**强度分级**：strong（直接物料流/同装置）/ medium（共用原料、部分替代）/ weak（仅成本共振，只作背景）。

### 第 2 步：跑扫描（参数一次定死）

```bash
python scripts/run_scan.py --data data --out out --window 60 --z 2.0 --persist 5 --drop 0.45 --perm 1200
```

输出 `out/scan_pack.json`（完整统计）、`out/scan_pack_pretty.json`、`out/series/*.csv`（逐日价差与 z）、
`out/series_web/web_series.json`（按月抽样 + 最近 120 日，供 HTML 用），并打印结果表。

**参数必须在看结果之前确定并写进交付文档**，不允许事后调整（见 `references/03` 第 5 节）。

### 第 3 步：跑历史回看（量化假阳性率）

```bash
python scripts/run_hist.py --data data --out out --months 12
```

把"当下"逐月回拨 15 个时点重跑，输出 `out/hist_scan.json` 与 `hist_scan_summary.json`。
**每个组合被判"异常"的频率必须进报告**——这是判断"没找到异常"是真没有还是阈值太松的关键证据。

### 第 4 步：读结果，先看"通过几条门槛"

```bash
python -X utf8 -c "import json;d=json.load(open('out/scan_pack.json',encoding='utf-8'));
[print(r['code_a'],r['code_b'],r['judge']['verdict'],round(r['judge']['score'],1),[c['passed'] for c in r['judge']['checks']]) for r in d['results']]"
```

四门槛（**必须同时满足**）：

| # | 门槛 | 默认 |
|---|---|---|
| 1 | 价差/比价偏离幅度 | \|z\| >= 2.0 |
| 2 | 偏离持续性 | 连续 >= 5 个交易日 |
| 3 | 全期相关显著性（**仅门控**） | Bonferroni p < 0.05 |
| 4 | 最近相关性脱钩 | \|r_all\| − r_roll >= 0.45 |

> 门槛 3 只是确认"A 与 B 真有关系"，**不是**异常的证据。强产业关系的日收益相关常常 p 极小，
> 报告里必须讲清楚，否则读者会把"相关显著"误读为"发现异常"。

### 第 5 步：逐条过伪异常检查清单

`references/03-多重检验与伪异常检查清单.md` 的 12 项（数据层 A1–A4 / 统计层 B1–B6 / 逻辑层 C1–C3）。
**多数"异常"死在这一步**：换月污染、窗口不稳健、关系强度 weak、共同冲击。

### 第 6 步：基本面复核（五问，双方都要）

对过了门槛的组合，逐项查：

| # | 查什么 | 常见口径 |
|---|---|---|
| 1 | **库存** | 企业库存、港口库存、社会库存；周度 |
| 2 | **开工** | 产能利用率、检修损失量；周度 |
| 3 | **供需** | 产量、进口、表观消费、下游开工 |
| 4 | **成本** | 原料价格、加工费/利润、能源成本 |
| 5 | **重要事件** | 检修、投产、事故、政策、制裁、运费 |

**红线**：没有可公开复算的连续序列，就写"未取得"，**不估算、不填补**。
本次实测：库存/开工的连续序列未能从公开渠道取得，只记录了可核验的时点事实与来源。

### 第 7 步：生成交付物

```bash
python scripts/build_excel.py --pack out/scan_pack.json --hist out/hist_scan.json --out 交付/产业链异常背离扫描.xlsx
python scripts/build_html.py  --pack out/scan_pack.json --web out/series_web/web_series.json --hist out/hist_scan.json --out 交付/看板.html
```

### 第 8 步：自检 + 报告

```bash
python scripts/selftest.py        # 24 项已知答案断言
python scripts/probe_html.py 交付/看板.html    # 无头浏览器：canvas 是否真的画出来、有无 JS 错误、容器是否为空
python scripts/verify_outputs.py 交付/x.xlsx 交付/看板.html   # Excel 公式与 HTML 自包含、两边判定一致性
```

报告按 `references/05-报告写作模板.md` 的八段骨架写。**摘要必须敢写"没有找到异常"。**

---

## 交付物

### 1. 交互式 HTML 看板（自包含单文件，无外链依赖）

六个页面 + 每个组合的完整研究页：

- **① 异常背离榜单**：品种池 / 关系类型 / 强度 / 判定 多选筛选器 + 偏离程度与相关变化的滑杆 + 搜索；
  表格可点表头排序；每行带滚动相关迷你火花线；点任意行进入组合研究页。
- **② 产业链关系图谱**：SVG 节点-连线图，节点大小按关系数，实线=强/中、虚线=弱；点节点筛选该品种。
- **③ 关系与配对规则**：四类关系说明、构建七步、为什么重点看 PP-LLDPE 与 PX-PTA。
- **④ 历史回看检验**：15 个时点的假阳性率表，解释"扫描器有多容易报假警"。
- **⑤ 来源与口径**：32 条来源分组列出，均可点击跳转。
- **⑥ 方法与限制**：统计口径表 + 已知限制六条。

**组合研究页**（五个 tab）：

| Tab | 内容 |
|---|---|
| 概览与判定 | 六张指标卡、四门槛逐条核查、产业关系（角色/机制/系数/来源）、自动生成的核心结论 |
| 价格·价差·标准化变化 | 双品种价格曲线、对数价差曲线（canvas 手绘）、5/20/60 日标准化变化表 |
| 统计与检验 | 价差 z 轨迹（含 ±2 阈值线）、滚动相关分布位置、相关性分层表（水平/收益/CI/N_eff/置换 p）、四门槛明细 |
| 基本面与事件 | 双方"基本面五问"清单、可复核的价格事实（含按 k 系数算的名义加工费）、事件时间线、解释框架 |
| 可比性与历史回看 | 重叠期/剔除数/可比性评级、该组合历史命中率、三段稳定性、不适用理由 |

### 2. Excel 工作簿（16 张表，原生公式可重算）

| # | Sheet | 内容 |
|---|---|---|
| 00 | 说明与使用指南 | 解决什么/不做什么/结论口径/导航/参数/合规声明 |
| 01 | 品种池与口径 | 15 品种的代码、交易所、乘数、起止日期、交易日数、合约口径 |
| 02 | 产业链关系图谱 | 16 条关系：类型、强度、A/B 角色、机制、系数、业内口径、来源 |
| 03 | 配对构建规则 | 七步规则 + 禁止事项 |
| 04 | 候选组合清单 | 关系驱动的配对、重叠期、可比性、是否进主榜单 |
| 05 | 异常背离榜单 | 排名、判定、评分、z、分位、持续、相关变化、门槛明细（带筛选器） |
| 06 | 统计口径与阈值 | 14 行：口径、公式、取值、为什么这样定、注意点、重算位置 |
| 07 | 统计详情 | 相关性段 + 价差偏离段 |
| 08 | 价格价差明细 | **原生公式**：比价、对数价差、滚动 z、对数收益、超阈值标记 + 交叉校验 + 2 张图 |
| 09 | 滚动相关明细 | **原生公式**：滚动 60 日 CORREL，与 Python 内核值并排 |
| 10 | 多重检验与稳健性 | p_raw / p_bonf / q_bh / p_perm + 历史回看命中率 |
| 11 | 基本面清单 | 双方五问的"应查口径"与本次取得情况 |
| 12 | 事件与解释 | 事件库 + 可解释的组合 |
| 13 | 可比性与稳定性 | A/B/C 评级、重叠日、跨度、三段极差、理由 |
| 14 | 来源清单 | 32 条，可点击 |
| 15 | 方法与限制 | 九条限制 + 历史扫描说明 |

### 3. 脚本

| 脚本 | 作用 | 依赖 |
|---|---|---|
| `stats_core.py` | 统计内核：Pearson/Spearman/Fisher CI/t 分布（不完全 Beta）/N_eff/BH-FDR/置换检验/滚动相关/滚动 z | **仅标准库** |
| `chain_graph.py` | 品种池与产业关系登记表 | 标准库 |
| `sources.py` | 32 条来源（数据/产业关系/事件） | 标准库 |
| `fundamentals.py` | 事件库 E01–E12 + 双方基本面五问模板 | 标准库 |
| `run_scan.py` | 装载 → 换月识别 → 扫描 → 判定 → 可比性评级 → 导出 | 标准库 |
| `run_hist.py` | 假设历史区间扫描（假阳性率） | 标准库 |
| `build_excel.py` | 16 表工作簿（原生公式 + 图表） | openpyxl |
| `build_html.py` | 自包含交互看板 | 标准库 |
| `fetch_futures.py` | 新浪财经日线抓取 | 标准库 |
| `selftest.py` | 24 项已知答案断言 | 标准库 |
| `probe_html.py` | 无头浏览器自检（canvas 是否画出、有无 JS 错误） | playwright（可选） |

### 4. 参考文档

- `references/01-产业关系类型与配对规则.md`
- `references/02-统计指标与阈值.md`
- `references/03-多重检验与伪异常检查清单.md`
- `references/04-数据源与可比性清单.md`
- `references/05-报告写作模板.md`

---

## 工具与依赖

- Python 3.9+。统计内核与扫描/HTML **仅用标准库**（t 分布、不完全 Beta、Fisher-z、置换检验全部内置，
  不需要 scipy / numpy / pandas）。
- `build_excel.py` 需要 `openpyxl`。
- `probe_html.py` 需要 `playwright` + chromium（可选，用于交付前自检）。
- 自检：`python scripts/selftest.py`（含 t 分布查表值、BH-FDR 已知答案、Fisher CI 已知答案、
  合成数据相关还原、配对规则自洽性、PP/L 与 PX/TA 必须在表中）。

---

## 红线（逐条照做）

- ❌ **不对无产业关联的品种做组合搜索**。组合数一多，极端值必然出现且大多没有产业含义。
- ❌ **不把统计偏离转成交易建议**。不写"建议做多/做空"、不给目标价、不写止盈止损。
- ❌ **不为了凑结论调参数**。窗口/阈值/起点先定后跑，写进交付文档。
- ❌ **不补数**。缺失留空，标"未取得"；不插值、不前向填充、不"按趋势估算"。
- ❌ **不把 weak 关系的统计极值写进主结论**。weak 只作背景，最多写进"排除说明"。
- ❌ **不混淆"价格水平相关"与"收益率相关"**。必须分开报，水平相关只作背景。
- ❌ **不隐藏不利结果**。没找到异常就写"没有找到"；数据不足就写"数据不足"。
- ✅ **每个数字都能追溯**：数据源 + 口径 + 时间段 + N + 显著性。
- ✅ **必须报历史回看命中率**，让读者知道"没报警"意味着什么。
- ✅ **必须列"哪些组合不该扫"**，否则读者会误以为这些组合"没问题"。

---

## 一个真实结论长什么样（本次实测，2026-10-20）

> 在 15 个化工品种、16 组产业关系中扫描，**未发现同时满足四门槛的异常背离**。
> PP-LLDPE：z = −1.42（历史分位 19.7%），连续超阈值 0 日，滚动相关 0.95（历史 95.9% 分位），
> 相关性变化 −0.136（更联动，不是脱钩）→ **偏离但未达门槛**（评分 19.0/100）。
> PX-PTA：z = −0.36（分位 36.8%），连续超阈值 0 日，滚动相关 0.956（分位 47.5%），
> 相关性变化 −0.003 → **偏离但未达门槛**（评分 4.8/100）。
> 唯一"候选"BU/FU 因关系强度 weak、三段相关均值极差 0.52、BU 存在未查明跳空而被排除。
> 历史回看：PP-L 15 次中 4 次被判异常（27%），PX-TA 0 次——说明阈值没有过松，
> 也说明单次报警的信息量有限。

完整案例见 `examples/pp-lldpe-px-pta/`。
