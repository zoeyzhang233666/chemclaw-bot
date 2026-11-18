# 查开工率季节性（Operating-Rate Seasonality）

一个**产品无关**的分析技能：回答"现在这个开工率，算高还是低"，并诚实地处理数据不足的情况。

## 它解决的核心问题

"高低"只有在同一产品、同一口径、同一周号的历史坐标里才有意义。市面上最常见的三种错误答案：

1. 拿今年的数字和"印象中的常年水平"比，不给可核验的历史序列；
2. 只有一个短序列，却算出了"P10–P90 区间"和"当前处于 30% 分位"；
3. 把不同机构（隆众/卓创/钢联）的"开工率"拼成一条线，拼出一条**根本不存在的季节性**。

本技能的核心不是画图，而是**在数据不够时明确拒绝给结论，并说清缺什么、怎么补**。

## 七条铁律

1. 开工率 ≠ 产能利用率（统计局·价值量口径）≠ 实际产量，禁止互换或换算
2. 样本开工率不得直接等同于全行业实际产量；`利用率 × 产能 ≠ 产量`
3. 只统计真实观测：不插值、不前向填充、不拿首周冒充 12 周前
4. 分位数少于 3 个样本不出；少于 5 个必须标注"样本不足"
5. 不同发布方不得合并成一条序列，只做方向性对照
6. 环比/同比的锚点要问清是"上一个发布日"还是"上一个日历周"
7. 春节等移动节假日必须另建相对周视图，不能只做 ISO 周对齐

## 快速开始

```bash
# 1) 登记数据（每行带 URL 与原文摘录）
cp templates/data_register.csv raw/data_register.csv

# 2) 建表
python scripts/build_dataset.py raw/data_register.csv

# 3) 统计（输出同周分位、逐周定位、4W/12W、异常年、跨年对照）
python scripts/seasonality.py --weekly raw/pvc_util_weekly.csv \
       --anchor-series raw/anchor_weekly.csv --out out

# 4) 出报告
python scripts/make_html.py --out assets/report.html
python scripts/make_xlsx.py --out assets/workbook.xlsx

# 5) 自检（14 项，含分位对标 numpy、缺口审计、端到端重放）
python scripts/selfcheck.py
```

## 目录

```
SKILL.md                            技能主文档（何时用、铁律、七步工作流、措辞规范）
references/
  data-sources.md                   取数渠道、四口径辨析、各家差异、取不到时的正确姿势
  stat-methods.md                   分位算法锁定、样本量红线、ISO周/春节相对周、季节性强度
  comparability-audit.md            可比性审计清单 + 三个真实踩坑判例
  event-calendar.md                 春节/检修/事件台账模板 + 各品种季节性假设
templates/
  data_register.csv                 观测登记表
  report_template.md                报告骨架（留空必修写"缺口"）
scripts/
  seasonality.py                    统计引擎（产品无关）
  make_html.py                      自包含交互式 HTML
  make_xlsx.py                      多 sheet 可复算工作簿
  build_dataset.py                  登记表 → 周度宽表 + 锚点校验
  fetch_mysteel.py / crawl_oilchem.py   取数示例
  selfcheck.py                      14 项自检
examples/pvc-china/                 完整案例：中国 PVC 开工率季节性
assets/
  PVC开工率季节性报告.html            成品：交互式报告
  PVC开工率季节性分析.xlsx            成品：12 sheet 工作簿
```

## 完整案例：中国 PVC（2026）

`examples/pvc-china/README.md` —— 12 个带源周度观测（2026-W30~W42），71 家样本，
电石法/乙烯法双口径，含七项要求的逐条应答。

这个案例**故意不完美**：

- 目标是 5 年周度数据，实际只拿到 1 年 → 缺口如实登记，不填补
- 每个周号 n=1 → **不出历史分位**，并论证了 n=1 时线性插值必然退化成单点
- 12 周变化 → 因观测数不足 13 而记为"缺口"，另用"窗口涨跌幅"措辞区分
- 与 2025 年的对比 → 只用可核验单周锚点，并标注"非同周号，仅作量级参照"

它演示了一件事：**"本期不出具季节性结论"也是一份合格的结论**，前提是说清了缺什么、为什么缺、怎么补。

## 一个实战教训

隆众原文的"环比"锚点是**上一个发布日**，不是 ISO 周−1。
初版脚本用 ISO 周匹配，导致 19 行环比锚点**全部判为"不一致"**；改用真实日期间隔后立刻对齐。

> 当所有环比都"不一致"时，先怀疑自己的对齐逻辑。

同类问题在 `references/comparability-audit.md` 里一共记录了三个，都带现象、错误推断、真相和修正。

## 数据源姿态

- 资讯机构公开转载页：可取到最近若干期完整正文（带样本说明）
- 会员站列表页：可枚举历史文章**标题**（证明某周确实发布过），正文需付费
- 机构图表接口：只给滚动 13 周窗口，需**长期定时抓取**才能攒满历史
- 财经快讯（如新华财经）：可检索到单周原句，是补历史锚点最现实的路子

若历史文章 URL 中的标识是随机串，则不可穷举——不要浪费时间去爆破。
