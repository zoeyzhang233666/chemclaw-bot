---
name: futures-spread-anomaly-scan
description: Use when someone asks to scan near-far month spreads across a chemical futures pool and flag which contract combinations sit at historical extremes — 扫描异常月差 / 近远月价差 / 期限结构极端分位 / 跨期价差历史分位 / 月差是不是太夸张 / 哪个品种的近远月价差离谱 / contango 太陡 / backwardation / 合约间价差异常. Covers 甲醇MA、纯碱SA、PTA、聚丙烯PP、乙二醇EG、PVC、苯乙烯EB、尿素UR、玻璃FG、烧碱SH and other 郑商所/大商所/上期所 品种. Delivers a self-contained interactive HTML dashboard plus an Excel workbook in which each product×month-pair gets its own separate historical distribution — never merged — with comparable samples defined by identical remaining term in whole weeks, sample-shortage cases explicitly marked as 样本不足, and extreme spreads flagged as research leads rather than trading recommendations.
---

# 扫描异常月差（近远月价差历史极端分位）

## 这个技能做什么

把一个化工期货**品种池**的当日期限结构，逐组合地放到**属于自己的**历史分布里，
找出当前处在极端分位的位置，并附上能解释这个位置的产业面证据。

**输出的不是交易建议，是"哪里不对劲"的清单 + 下一步该查什么。**

---

## 一、调用前必须先确认的三件事

| 确认项 | 为什么 | 默认值 |
|---|---|---|
| 品种池 | 跨品种的月差绝对量纲不同（元/吨），但分位可跨品种比较 | MA SA PP TA |
| 历史窗口 | 决定样本年数 N 的上限 | 近 5 个年度合约（2022–2026） |
| 极端阈值 | 报告"极端"还是"偏高" | 极端 5/95，偏高 20/80；扫描提醒线 10/90 |

若用户没说，按默认走并在报告首屏写明，不要回头问。

---

## 二、执行流程（严格按序，不可跳步）

```bash
python scripts/run_pipeline.py --products MA SA PP TA --as-of 2026-10-20 --outdir build
```

单步跑法见 `references/03-执行手册.md`。流程与硬性约束：

### 步骤 1　建立合约规则对照
先读 `data/contract_rules.json`（已核验：四品种 1–12 月全月挂牌）。
新品种先用 `scripts/rule_matcher.py` 校准，**不要凭印象假设主力只在 1/5/9 月** ——
实测显示换月是逐月滚动的，1/5/9 只是生命周期锚点。

### 步骤 2　抓当日行情 + 仓单
- 郑商所官方日报（结算价、持仓、成交）+ 仓单日报 → 官方口径
- 大商所官网对脚本返回 HTTP 412，改用东方财富，**只有最新价、没有当日结算价**

> ⚠ 价格口径必须分产品记录并在所有输出中标注。CZCE 用 `settle`，DCE 走东财只能用 `last`。
> **两套口径不得混算**，也不得把 PP 的月差和 MA 的月差当成同一口径下的量直接比大小 ——
> 比的是**分位**，不是绝对元数。

### 步骤 3　计算月差
```
spread = P_near − P_far        （近月结算价 − 远月结算价，元/吨）
```
- 必须 `far` 晚于 `near`；倒序组合直接判 `ORDER_REVERSED` 拒绝
- 正值 = 近月升水（正向市场 contango）；负值 = 近月贴水（反向市场）
- **剔除最前两个交割月**：临近交割报价受单边交割逻辑扭曲，且历史无同剩余期限可比样本

### 步骤 4　构造可比历史样本（本技能的技术核心）
一个样本只有在下列条件全部相同时才可比：

| 维度 | 要求 |
|---|---|
| 品种 | 相同 |
| 月份组合 | 相同（SA 1–5 的样本只能与 SA 1–5 的历史比） |
| 剩余期限 | 相同整周数 `floor((近月交割月结束日 − 观测日).days / 7)` |
| 年度 | **每个历史年份只取 1 个样本** |

> 为什么"每年 1 个"：早期实现用了 ±N 周窗口，结果每年放进约 20 个自相关的日度点，
> 把 N 从 5 虚增到 57，分位被严重压缩失真。**N 必须是"独立年度"的个数。**

### 步骤 5　算分位与极端度
```
分位 = (小于当前值的历史样本数 + 0.5 × 等于的个数) / N × 100
Z    = (当前月差 − 历史均值) / 历史标准差
极端度 = |分位 − 50| × 2          # 0=历史中位，100=历史极限
```
同时给 q05/q25/q50/q75/q95 与 min/max。

### 步骤 6　筛选排序
排序主键是**极端度**，不是分位绝对值方向。
分位 100% 和 0% 极端度都等于 100 —— **两端都是极端，不要只报一端**。

### 步骤 7　补充产业面
对每个异常组合补：库存、仓单、现货/基差、供需事件、新增产能、装置检修。
每个数字**必须带日期 + 单位 + 来源 + 可信度 A/B/C/D**，缺就留空写"未获取"。

### 步骤 8　标注局限
样本不足（N < 3）、历史不可比、口径差异、异常未解释的事项，单独列清单。

---

## 三、绝对红线（写进每一份输出）

1. **不把异常月差直接当作跨期交易建议。** 报告里出现的只有"位置"与"线索"。
2. **不同月份组合绝不合并成一个分布。** SA 1–5 与 SA 5–9 是两个独立分布。
3. **样本不足不硬算分位。** N < 3 时写"样本不足"，不补数、不插值、不放宽口径凑 N。
4. **不用主力连续合约算月差。** 换月会制造假跳变，必须逐合约取价。
5. **不插值、不向前填充。** 结算价为 0/空、或成交与持仓同时为 0 的交易日直接跳过。
6. **月差未扣成本。** 仓储费、资金占用、交割费用、品级与地区升贴水都在月差之外。

---

## 四、产物

| 产物 | 说明 |
|---|---|
| `build/dashboard.html` | 单文件交互看板：改品种池/口径/阈值即重算；点品种看曲线、历史分布、库存仓单、事件时间线 |
| `build/异常月差扫描工作簿.xlsx` | 11 个工作表，293 个原生公式，改源数据即重算，无宏 |
| `build/scan_result.json` | 全量结构化结果，供下游消费 |

模板在 `assets/templates/`，可直接套用改数据。
完整案例（甲醇/纯碱/PP/PTA，2026-10-20）见 `examples/`。

---

## 五、交付前自检

```bash
python scripts/selftest.py          # 24 项已知答案，必须全绿
node   scripts/check_html.js build/dashboard.html   # 看板渲染逻辑
python scripts/verify_excel.py      # 公式与 Python 侧一致性
```

还要人眼确认三件事：
- 有没有哪个组合被悄悄合并进了别的分布？
- 有没有哪个"样本不足"被算出了分位？
- 有没有哪句话读起来像交易建议？

清单见 `references/05-交付检查表.md`。

---

## 六、参考文档

| 文件 | 内容 |
|---|---|
| `references/01-方法说明.md` | 月差定义、可比样本构造、分位与极端度公式、为何如此设计 |
| `references/02-合约规则对照.md` | 四品种交易所规则、挂牌月份、交易单位、交割与仓单注销 |
| `references/03-执行手册.md` | 逐步命令、参数含义、换品种池怎么改 |
| `references/04-产业面数据源.md` | 库存/仓单/现货/事件的可信来源与可信度分级 |
| `references/05-交付检查表.md` | 交付前逐项打勾 |
| `references/06-常见错误.md` | 这个技能踩过的坑与正确做法 |
