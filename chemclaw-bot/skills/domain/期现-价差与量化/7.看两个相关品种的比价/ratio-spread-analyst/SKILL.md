---
name: ratio-spread-analyst
description: Use when the user wants to compare two related products' prices as a ratio/spread — 看两个相关品种的比价 / 期现价差 / 比价处于什么位置 / 比价回不回归 / 两个品种谁强谁弱 / 相关性品种怎么对比 / 裂解价差 / 加工价差. Covers futures-vs-futures, futures-vs-spot, product-vs-feedstock and cross-product pairs. Delivers a self-contained interactive HTML ratio page plus an 11-sheet Excel workbook, where every statistic carries its sample size, calendar basis and period, percentiles are true empirical ECDFs (never min-max interpolation), contributions are decomposed to show which side drove the move, and rollover contamination is quantified and disclosed.
---

# 两个相关品种比价分析（ratio-spread-analyst）

## 这个 Skill 解决什么问题

用户拿着两个"看起来相关"的品种，想知道它们的比价现在处在什么位置、为什么会走到这里、
以及这个位置有没有意义。绝大多数错误答案长这样：

> "PP/L 比价 1.07，处于历史 98% 分位，明显偏高，预计将回归均值。"

这句话有三个致命问题：**分位口径没交代**（哪个窗口？含不含当前值？样本跨没跨结构变化？）、
**没说清是谁把比价推上去的**（可能一边涨一边跌，也可能两边同涨但一边更快）、
**把极端当成了回归的理由**（中枢可能已经迁移，回归的前提是结构回到旧状态）。

本 Skill 的输出必须同时给出：口径、样本量、方向、贡献分解、结构检验，以及
"这个结论在什么条件下会失效"。**不预设均值回归。**

## 何时使用

| 触发场景 | 例子 |
|---|---|
| 两个期货品种比价 | PP/L、螺纹/热卷、豆粕/菜粕、原油/燃料油 |
| 产品与其原料的加工差 | PTA-PX、螺纹-铁矿、豆油-豆粕（压榨） |
| 期现价差 / 基差 | 某品种主力 vs 华东现货 |
| 跨品种替代关系 | LLDPE/HDPE、甲醇/尿素（煤头共享） |
| 用户说"这个比价高不高""会不会回归" | 一律先走本 Skill 的口径与分解流程 |

## 七步协议（顺序不能换）

这是本 Skill 的骨架。**第 2 步不做完，后面全部作废。**

### 1. 定关系
两个品种是替代、上下游、共同原料，还是仅有统计相关？关系决定了比价**有没有天然锚**。

- **上下游**（产品 vs 原料）：有加工利润锚，比价长期受"装置能不能活下去"约束。
- **替代品**（同一用途、不同工艺）：有替代锚，但**替代不完全时锚很弱**。
- **共同原料**（同一feedstock 的不同下游）：比价反映**两个下游的相对景气**，没有硬锚。
- **纯统计相关**：没有产业锚，比价可以永久漂移。必须明确告诉用户。

输出格式：关系类型 + 一句话解释 + "对比价的含义"（这个比价能/不能说明什么）。

### 2. 验口径（强制前置）
逐项核对，任一项不一致就必须标出来：

- 单位（元/吨？美元/桶？）
- 含税/不含税、含运费/出厂/仓库
- 品质规格（**PP 拉丝级 vs LLDPE 膜料是不同标准品**，比价含牌号价差）
- 报价时点（收盘/结算/午间/日度均价）
- 合约乘数、交割地升贴水
- **是否混用现货与期货**（绝对不允许为了凑长度而混）
- 主力连续序列是否做过换月复权（大多数免费接口**没有**）

只有全部通过才进入计算。任何"差不多"都必须写成风险提示。

### 3. 定方向
明确 **A/B 还是 B/A**，并在全文中保持一致。方向的后果很直观：

- A/B 与 B/A 的分位互补（97.8% ↔ 2.2%），**必须一起给出或明确声明**，否则用户会读反。
- 贡献分解会反转：A/B 下"PP 主导"，B/A 下"L 主导"——**主导方是按分母在不同方向**，
  报告里必须写清"在 A/B 口径下，是 A 侧在推动比价上行"。

### 4. 算统计（1年 / 3年 / 5年）
每个窗口必须同时给出：**N、均值、中位数、最低、最高、当前值分位**。
并且分位必须是**经验分布（ECDF）**：

```
pct = (严格小于当前值的样本数 + 0.5 × 等于当前值的样本数) / N × 100
```

**禁止**用 `(当前 - 最低) / (最高 - 最低)` 线性反推。这个错误在本 Skill 的自测里有明确定义：
一个右偏分布下，线性法给出 60%，真实 ECDF 是 93.8%——**差 34 个百分点**。

同时必须区分两种口径并都报：

- **日历口径**：窗口内含当前值（用户最直观，但有自评分偏差）
- **前序样本口径**：剔除最近 N 个交易日后再打分（更保守）
- **分阶段口径**：按产业结构分段，看"相对同结构时代"的分位

### 5. 拆贡献
用对数恒等式，不要用简单差值：

```
ln(A/B) = lnA − lnB
Δln(A/B) = ΔlnA − ΔlnB
份额_A = |ΔlnA| / (|ΔlnA| + |ΔlnB|)
```

回答的是"**谁在主导**"（份额），配合方向（正负号）。
**关键洞察**：份额接近 50/50 时比价几乎不动，但**两边都在动**——
这时候说"比价没反应，所以两者没关系"是错的。反之份额 94/6 说明是单边推动。

### 6. 找极端阶段 + 配产业事件
对每个历史极端段，列出该区间内的产业事件（产能投放、装置检修、政策、地缘、成本冲击）。
事件表的每条都必须带**核对级别**：

- **A**：有原始报道标题或正文可直接核对
- **B**：有标题但细节需二次确认
- **C**：行业背景/常识，未逐条核实，**不得单独支撑结论**

事件只用于**解释比价为何那样走**，不能证明因果，也不能用于预测。

### 7. 检验结构漂移
这是最容易被跳过、但最重要的一步。

- 对 ln(比价) 做**两段均值偏移扫描**（Welch t），找最强断点。
- 画出 252 日滚动均值，看中枢是否台阶式迁移。
- 对比"全样本分位"与"同结构阶段分位"。如果两者差 >15 个百分点，
  **就不能用"历史高位"作为单一论据**。

## 硬性红线（写进每份报告）

1. **不因为比价处于极端位置就认定必然回归。** 中枢可能已经迁移。
2. 不把相关性/共变说成因果。
3. **不插值、不回填、不外推**缺失数据；缺失一律剔除并在 N 中体现。
4. 不混用现货与期货口径。
5. 不给交易建议、不给目标价、不说做多/做空/做扩/做缩。
6. **换月日的比价跳空必须单独标注并剔除**，不得并入产业解释。

## 工作流

```
工作区/
  csv/     ← 放原始价格（date,close,...）两份
  events/  ← 产业事件台账（可选）
  out/     ← 产物
```

```bash
# 0) 自测内核（必须先绿）
python scripts/selftest.py

# 1) 装配价格序列 + 换月台账 + 数据质量闸门（ERROR 必须为 0）
python scripts/prep_data.py --raw <原始json目录> --out out \
    --prefix-a PP --prefix-b L

# 2) 主分析 → 全量 JSON
python scripts/analyze.py --a out/price_A.csv --b out/price_B.csv \
    --rolls out/roll_ledger.csv --out out/result.json --name-a PP --name-b L

# 2b) 反方向（用于 A/B ↔ B/A 切换）
python scripts/analyze.py --a out/price_A.csv --b out/price_B.csv \
    --rolls out/roll_ledger.csv --out out/result_BA.json \
    --name-a PP --name-b L --direction BA

# 3) 事件台账
python scripts/events.py out/events.csv

# 4) 交互式 HTML
python scripts/build_html.py --result out/result.json \
    --result-ba out/result_BA.json --events out/events.csv \
    --meta out/meta.json --out out/report.html

# 5) Excel 工作簿（原生公式，无宏）
python scripts/build_excel.py --result out/result.json \
    --price-a out/price_A.csv --price-b out/price_B.csv \
    --events out/events.csv --qc out/qc_report.json --out out/report.xlsx

# 6) 校验
python scripts/verify_excel.py --xlsx out/report.xlsx --result out/result.json
```

## 产物

| 文件 | 内容 |
|---|---|
| `report.html` | 自包含交互页：A/B↔B/A 切换、1/3/5年窗口切换、首屏 KPI、历史曲线、分布直方图、两边价格、贡献分解、滚动分位、极端阶段（点击展开产业事件）、结构漂移、结论与红线 |
| `report.xlsx` | 11 表：说明/原始价格/比价序列/窗口统计/分位口径对照/贡献分解/异常点/换月台账/分年统计/产业事件台账/数据来源 |
| `result.json` | 全部可复核数字，报告只能引用这里算出来的值 |
| `qc_report.json` | 数据质量闸门结果 |
| `roll_ledger.csv` | 换月台账 |
| `events.csv` | 产业事件台账（含核对级别） |

## 文件地图

```
ratio-spread-analyst/
├── SKILL.md
├── README.md
├── references/
│   ├── 01-方法说明.md          七步协议逐条展开、公式推导
│   ├── 02-数据口径核验.md      口径清单、常见陷阱、换月识别
│   ├── 03-分位与统计口径.md    ECDF、日历/前序/分阶段、并列处理
│   ├── 04-贡献分解与结构检验.md 对数分解、Welch t 断点扫描
│   ├── 05-报告写作模板.md      报告骨架、措辞红线、禁用句式
│   └── 06-产业关系图谱.md      常见品种对的产业定位
├── scripts/
│   ├── ratiolib.py            纯标准库统计内核（无 numpy/pandas）
│   ├── selftest.py            96 项自测，含反例与陷阱验证
│   ├── prep_data.py           装配 + 换月识别 + 质量闸门
│   ├── analyze.py             主分析 → result.json
│   ├── events.py              产业事件台账
│   ├── build_html.py          生成交互页
│   ├── build_excel.py         生成工作簿
│   ├── verify_excel.py        工作簿校验
│   └── js_check.js            页面 JS 语法检查
├── assets/
│   ├── templates/
│   │   ├── ratio-report-template.html
│   │   └── ratio-workbook.xlsx
│   └── data/                  示例数据与 QC 结果
├── examples/
│   └── pp-vs-lldpe/           PP vs LLDPE 完整案例
└── 工作区/说明.txt
```

## 关键实现细节

- **纯标准库内核**：`ratiolib.py` 只用 `math`/`statistics`，可在任何机器上跑，不需要 numpy/pandas。
- **并列值处理**：分位用"严格小于 + 0.5×等于"，与 Excel 公式 `(COUNTIF(<)+0.5*COUNTIF(=))/COUNT()` 完全一致。
  这个细节在本 Skill 里被专门对齐过——否则 Python 与 Excel 会给出差 0.2 个百分点的两个答案。
- **换月识别用持仓量**，不用"收盘价相等"（多个合约可能恰好同价，会造成假换月）。
- **异常点用稳健 z**（滚动中位数/MAD），不用均值/标准差（后者本身被异常值污染）。
  窗口 120、阈值 3.5，在示例数据上给出 3.3% 的标记率，集中在真实极端期。
- **HTML 零外部依赖**：不引 CDN、不引图表库，SVG 手绘，离线可开。

## 常见失败模式

| 症状 | 原因 | 处理 |
|---|---|---|
| 分位 100%，看起来"极端到不可能" | 样本跨了结构断点 | 报分阶段分位，说明中枢已迁移 |
| A/B 与 B/A 分位不互补 | 一侧有缺失导致样本不同 | 检查 N 是否一致 |
| 换月日出现巨大比价跳空 | 主连未复权 | 标为数据原因，剔除后再做产业解释 |
| 两边价格同涨但比价不动 | 力度相当（份额 ~50/50） | 说"两边都在动"，不要说"无关" |
| Excel 与 Python 分位差 0.2% | 并列值处理不同 | 用 `(COUNTIF(<)+0.5*COUNTIF(=))/COUNT()` |
| 无法解释早期极端 | 早期无逐条产业数据 | 核对级别标 C，明说"未逐条核实" |
