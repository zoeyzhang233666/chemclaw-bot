# ratio-spread-analyst · 两个相关品种比价分析

一个可复用的分析 Skill：把"两个品种的比价现在高不高"这个问题，
拆成**口径、分位、贡献、结构**四件可以被复核的事。

## 它解决的核心问题

绝大多数比价分析长这样：

> "PP/L 比价 1.07，处于历史 98% 分位，明显偏高，预计将回归均值。"

这句话有三处硬伤：

1. **98% 是哪个窗口的？含不含当前值？样本跨没跨结构变化？** —— 没说。
2. **是谁把比价推上去的？** —— 可能是 PP 涨了 20% 而 L 没动（单边推动），
   也可能是两边同涨但一边更快（成本传导差异）。这两者的产业含义完全不同。
3. **"极端"为什么是回归的理由？** —— 中枢可能已经迁移，回归的前提是结构回到旧状态。

本 Skill 的输出必须同时给出：**口径、样本量、方向、贡献分解、结构检验**，
以及"这个结论在什么条件下会失效"。**不预设均值回归。**

## 30 秒上手

```bash
# 0) 先让内核自测全绿（改任何统计代码之前都要跑）
python scripts/selftest.py                    # 期望 96 passed / 0 failed

# 1) 装配 + 换月识别 + 数据质量闸门（ERROR 必须为 0）
python scripts/prep_data.py --raw <原始json目录> --out out --prefix-a PP --prefix-b L

# 2) 主分析
python scripts/analyze.py --a out/price_A.csv --b out/price_B.csv \
    --rolls out/roll_ledger.csv --out out/result.json --name-a PP --name-b L

# 3) 反方向
python scripts/analyze.py --a out/price_A.csv --b out/price_B.csv \
    --rolls out/roll_ledger.csv --out out/result_BA.json \
    --name-a PP --name-b L --direction BA

# 4) 产业事件台账
python scripts/events.py out/events.csv

# 5) 交互式 HTML
python scripts/build_html.py --result out/result.json --result-ba out/result_BA.json \
    --events out/events.csv --meta out/meta.json --out out/report.html

# 6) Excel 工作簿
python scripts/build_excel.py --result out/result.json \
    --price-a out/price_A.csv --price-b out/price_B.csv \
    --events out/events.csv --qc out/qc_report.json --out out/report.xlsx

# 7) 校验
python scripts/verify_excel.py --xlsx out/report.xlsx --result out/result.json
node scripts/js_check.js out/report.html
```

## 产物

| 文件 | 内容 |
|---|---|
| `report.html` | 自包含交互页（零外部依赖，离线可开）：A/B↔B/A 切换、1/3/5年窗口切换、首屏 KPI、历史曲线、分布直方图、两边价格、贡献分解、滚动分位、极端阶段点击展开产业事件、结构漂移、结论与红线 |
| `report.xlsx` | 11 表工作簿，**21,067 个原生公式**，无宏，打开即复算 |
| `result.json` | 全部可复核数字 |
| `qc_report.json` | 数据质量闸门 |
| `roll_ledger.csv` | 换月台账 |
| `events.csv` | 产业事件台账（带核对级别 A/B/C） |

## 七步协议

1. **定关系** — 替代/上下游/共同原料/仅统计相关？关系决定比价有没有天然锚。
2. **验口径** — 单位、税、运费、品质、时点、合约、交割地、乘数、交易日历。**这一步不做完，后面全废。**
3. **定方向** — A/B 还是 B/A，全文一致；两者分位互补（97.8% ↔ 2.2%）。
4. **算统计** — 1/3/5年 + 全样本，每个都带 N；分位用 **ECDF**，禁止线性反推。
5. **拆贡献** — 对数恒等式 `Δln(A/B) = ΔlnA − ΔlnB`，回答"谁在主导"。
6. **找极端 + 配事件** — 每条事件标核对级别，只用来说明，不证明因果。
7. **检验结构漂移** — Welch t 断点扫描 + 252 日滚动均值 + 分阶段分位。

## 关键实现细节

### 分位必须是 ECDF

```
pct = (严格小于当前值的样本数 + 0.5 × 等于当前值的样本数) / N × 100
```

**禁止** `(v − min) / (max − min)`。自测里固化了反例：
重尾样本下真实 ECDF = **93.81%**，线性反推 = **60.00%**，差 **33.8 个百分点**。

### 并列值处理必须与 Excel 对齐

Python 与 Excel 的公式已对齐到 1e-9：

```excel
=(COUNTIF(range,"<"&v) + 0.5*COUNTIF(range,v)) / COUNT(range) * 100
```

不对齐的话，两个工具会给出差 0.2 个百分点的两个答案。

### 换月识别用持仓量，不用价格相等

价格相等法在示例数据上产生 **189 个假事件**（大量并列）；
持仓量法得到 **48 个真实换月**，符合 1/5/9 合约交替节奏。

### 异常点用稳健 z（MAD）

普通 z 的均值和标准差会被异常值本身污染（掩蔽效应）。
本 Skill 用 `z = 0.6745 × (x − median) / MAD`，窗口 120、阈值 3.5，
在示例数据上标记率 3.3%，集中在真实极端期。

### 纯标准库内核

`ratiolib.py` 只用 `math` / `statistics`，**不需要 numpy / pandas**，可在任何机器上跑。
（Excel/HTML 生成脚本需要 `openpyxl`。）

## 目录

```
ratio-spread-analyst/
├── SKILL.md                        七步协议 + 红线 + 工作流
├── README.md                       本文件
├── references/
│   ├── 01-方法说明.md              公式推导、判定标准、做错的样子
│   ├── 02-数据口径核验.md          十项核验表、换月识别、缺失处理
│   ├── 03-分位与统计口径.md        ECDF、三种口径、并列值、异常检测
│   ├── 04-贡献分解与结构检验.md    对数分解、Welch t、共变结构
│   ├── 05-报告写作模板.md          报告骨架、禁用句式清单
│   └── 06-产业关系图谱.md          常见品种对的产业定位
├── scripts/
│   ├── ratiolib.py                 统计内核（纯标准库）
│   ├── selftest.py                 96 项自测
│   ├── prep_data.py                装配 + 换月 + 质量闸门
│   ├── analyze.py                  主分析
│   ├── events.py                   事件台账
│   ├── build_html.py               生成交互页
│   ├── build_excel.py              生成工作簿
│   ├── verify_excel.py             工作簿校验
│   └── js_check.js                 页面 JS 校验
├── assets/
│   ├── templates/
│   │   ├── ratio-report-template.html
│   │   └── ratio-workbook.xlsx
│   └── data/                       示例数据
├── examples/
│   └── pp-vs-lldpe/                完整实战案例（含 README）
└── 工作区/
    └── 说明.txt
```

## 完整案例

`examples/pp-vs-lldpe/` 是一个跑通的完整案例：

- PP/L 比价，3,069 个交易日，2014-02-28 → 2026-10-20
- 当前 1.0745，近5年分位 97.8%，但分阶段分位 **79.4%–100%**
- 2024-10 → 2026-05 比价 +21.5%，**PP 贡献 94%**（PP +20.1%、L −1.2%）
- 结构断点 2017-11-30，t = 42.04，中枢 +12.8%
- 48 次换月，最大跳空 L +5.02% / PP +8.71%（同日）
- 34 条产业事件，核对级别 A=27 / B=2 / C=5

详见 `examples/pp-vs-lldpe/README.md`。

## 红线

1. **不因为比价处于极端位置就认定必然回归。**
2. 不把相关性/共变说成因果。
3. 不插值、不回填、不外推缺失数据。
4. 不混用现货与期货口径。
5. 不给交易建议、不给目标价、不说做多/做空/做扩/做缩。
6. 换月日的比价跳空必须单独标注并剔除。

## 依赖

| 用途 | 依赖 |
|---|---|
| 统计内核 + 分析 | 仅 Python 标准库 |
| 生成 Excel | `openpyxl` |
| 校验 HTML | Node.js（`new Function` 语法检查） |
| 渲染测试（可选） | Playwright |

## 已知局限

- 期货主力连续**不复权**，换月跳空需单独处理（本 Skill 已量化并披露）。
- 标准品规格可能不同（如 PP 拉丝级 vs LLDPE 膜料），比价含牌号价差。
- 数据末端的连续序列可能是多合约混合报价（已披露）。
- 早期历史缺少逐条产业数据，相关事件标为核对级别 C。
