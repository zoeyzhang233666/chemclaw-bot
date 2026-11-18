# 基差分位信息检验 Skill

> 检验「基差处在历史高/低分位」这件事，对之后 1/2/4 周（及 3/6 月）的
> 现货价格、期货价格与基差本身有没有历史信息。
> **只输出历史统计，不生成交易建议。**

## 它解决的问题

用户常问：

- 「甲醇基差现在在历史 94% 分位，历史上这种时候之后一般怎么走？」
- 「帮我检验华东甲醇现货和期货的基差有没有历史信息。」
- 「基差低分位之后是现货涨还是期货跌？要分清楚。」
- 「换个分位阈值、换个观察窗口，结论还成立吗？」

这个 Skill 给出的是**一个可复核的答案**，而不是一个结论句。

## 交付物

| 交付物 | 说明 |
|---|---|
| **交互 HTML 报告** | 单文件、无外链、双击离线打开。可调基差口径 / 窗口 / 阈值 / 观察期，改动即重算 |
| **Excel 工作簿** | 13 张表，含真公式（分位排名用 `COUNTIF` 独立复算，与引擎结果并排对照） |
| **中间数据** | `research_data.json` / `report_data.json` / `basis_daily.csv`，逐日可核 |
| **自检报告** | `tests/test_statistics.py`，47 项断言 |

## 核心设计：三道闸门

1. **窗口严格滞后**：`P_t = rank(B_t | {B_{t−1}…B_{t−W}}) / N`，不含当日、不含未来
2. **未来收益不回填**：信息检验 `[t, t+h]` 与可操作 `[t−h, t]` 两种口径都报
3. **末端回填标记**：最后 W 个点标为"当时未知"，稳定性检验中剔除

## 为什么必须分拆现货与期货

`Δ基差 = Δ现货 − Δ期货`。
同一句"基差从低分位回升"，可能是现货涨出来的，也可能是期货跌出来的，
两者的价格风险完全不同。

**甲醇案例的实测**：4 周低−高差值 +6.47%（p<0.0001），
但现货端贡献 +7.72%（p=0.0001），期货端只有 +1.25%（p=0.44）。
只报基差就会误导成"可以做基差回归"——**实际上期货端几乎无反应**。

## 快速开始

```bash
# 一键跑完整流程（用已附带的原始数据）
python scripts/run_all.py --case examples/methanol-east-china

# 从网络重新抓数据再跑
python scripts/run_all.py --case examples/methanol-east-china --fetch
```

产出在 `examples/methanol-east-china/out/`：

```
报告.html      交互报告（1.2MB，双击打开）
数据表.xlsx    13 表工作簿
report_data.json / research_data.json / basis_daily.csv
```

## 目录结构

```
basis-percentile-info/
├── SKILL.md                      技能说明（Agent 入口）
├── README.md                     本文件
├── manifest.yaml                 元数据
├── scripts/
│   ├── fetch_data.py             抓原始数据
│   ├── basis_core.py             计算引擎（约 1200 行）
│   ├── report_data.py            压缩为报告数据
│   ├── build_html.py             生成 HTML
│   ├── build_xlsx.py             生成 Excel
│   └── run_all.py                一键全流程 + 自检
├── references/
│   ├── 01_口径定义与合约规则.md
│   ├── 02_滚动分位与无未来函数.md
│   ├── 03_统计口径与推断.md
│   ├── 04_偏差清单.md
│   ├── 05_数据源与字段规范.md
│   └── 06_常见错误与QA.md
├── templates/
│   └── report_template.html      报告模板（__DATA_JSON__ / __TITLE__ 占位）
├── tests/
│   └── test_statistics.py        47 项断言
└── examples/
    └── methanol-east-china/
        ├── CASE.md               完整案例解读
        ├── raw/                  原始抓取数据
        └── out/                  产出
```

## 换品种怎么用

引擎只认五个字段：`date / spot / fut / oi / contract`。
换品种需要改的只有：

1. `fetch_data.py` 里的现货源与合约代码前缀
2. `templates/report_template.html` 里的品种名与合约规则表
3. `references/01` 里的合约规则（交易单位、最后交易日、交割品级）

**统计与推断代码完全不用改。**

## 环境

- Python 3.10+（`openpyxl` 用于 Excel，`requests` 用于抓取）
- 不需要 pandas / numpy（纯标准库实现，便于审计）
- HTML 无任何外部依赖，任何现代浏览器可离线打开

## 边界

- **不做交易建议**：不扣成本、不判断可交易性
- **不跨品种套用**：每个品种重跑
- **样本不足时明说**：块长≥样本半数时判定退化，宁可不给 p 值
- **拿不到就明写降级**：不臆造华东实盘价

## 已知的最好实践

- 分位实现完，先打印 `min / max / median` 三件套（应为 ≈0 / ≈1 / ≈0.5）
- 每个统计表都要有 `n` 列
- 每条偏差都要有实测数字，不能只写"已注意"
- 结论句由数据生成，不手写（避免结论与表格不一致）
