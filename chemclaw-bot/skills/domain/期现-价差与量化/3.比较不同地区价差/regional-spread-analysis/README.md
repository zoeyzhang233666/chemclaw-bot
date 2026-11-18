# chemical-region-spread · 比较不同地区价差

一个把「同一化工品在不同地区的现货价差」做成**可交付、可复算、不误导**的研究包。

## 一句话

选 2–5 个地区 → 统一口径 → 对齐日期 → 算两两价差与历史分位 → 叠加运费看物流可行性 →
解释异常阶段的产业原因 → 交付**一个自包含 HTML 报告 + 一个全公式 Excel 工作簿**。

## 30 秒上手

```bash
cd regional-spread-analysis

# 用内置的纯碱 DEMO 数据跑一遍（无需联网、无需 API key）
python scripts/build_all.py

# 用自己的数据
python scripts/build_all.py --prices my_prices.csv
```

产物在 `build/`：

| 文件 | 说明 |
|---|---|
| `regional-spread-report.html` | 交互式报告，**双击即可离线打开**（ECharts 已内嵌，零外部请求） |
| `workbook.xlsx` | 17 张表，**改价格/运费自动重算**（原生公式，无宏） |
| `result.json` | 中间结果，可被其他程序消费 |

## 五条硬约束（写死在代码里）

1. **未提供运费时不得自行估算，也不要直接将价差认定为套利机会**
2. 三地区报价先统一口径，再按日期对齐；缺口**剔除，绝不插值**
3. 缺失值一律 `null`，**绝不用 0 顶替**；算不出来就不让算
4. 裸价差 / 运输成本 / 扣费后差异**永远分列**
5. 相关不写成因果；历史分位不写成价格预测

## 数据怎么给

长表 CSV，一行一个「日期 × 地区」：

```csv
date,region,price,caliber,unit,source,note
2025-06-27,SD,1350,DELIVERED,元/吨,期货日报华北,
2025-06-27,HB,1265,DELIVERED,元/吨,期货日报华北,
2025-06-27,JS,1370,DELIVERED,元/吨,隆众华东,
```

- `region` 用 `config/project.json` 里的地区代码
- `caliber`：`DELIVERED`（送到）/ `EXW`（出厂），决定进哪套口径
- **缺失就留空**，不要填 0

模板见 `data/prices_template.csv`。

## 换产品 / 换地区

改 `config/project.json`：

```json
{
  "product": "重质纯碱",
  "spec": "GB/T 210-2022 Ⅱ类优等品，Na₂CO₃ ≥ 99.2%",
  "regions": [
    {"id": "SD", "name": "山东", "lat": 36.7, "lon": 118.0,
     "quote_basis": "...", "role": "净调出", "basis_risk": "..."}
  ],
  "calibers": {
    "DELIVERED": {"label": "送到价", "why": "..."},
    "EXW":       {"label": "出厂价", "why": "..."}
  }
}
```

`config/routes.json` 放路线与运费参数，`config/events_fundamentals.json` 放事件与产能/下游结构。

## 质量门

```bash
python scripts/selftest.py                       # 内核单测（28 项）
python scripts/data_quality.py --result build/result.json   # 质检（0 ERROR 才交付）
python scripts/check_html.py  --html build/xxx.html --result build/result.json  # 真实浏览器执行
python scripts/verify_excel.py --xlsx build/xxx.xlsx --result build/result.json # LibreOffice 重算对账
```

| 门 | 判据 |
|---|---|
| 内核 | 28 项单测全绿 |
| HTML | 无头浏览器真实执行，无 JS 异常，6 张图 canvas 均有像素，JS 与 Python 分位差 < 0.15 |
| Excel | LibreOffice 重算后**无 `#REF!`/`#VALUE!` 等错误值**，矩阵/分位/运费与 Python 差 < 0.01 |
| 质检 | Q1–Q10 无 ERROR |

当前状态：**28/28 单测通过 · HTML 39 项通过 · Excel 45 项通过 · 质检 0 ERROR**。

## 目录

```
SKILL.md                     技能入口（给 AI 代理读）
README.md                    本文件
config/                      project.json · events_fundamentals.json · routes.json
data/                        模板 + DEMO 双口径序列
scripts/                     spreadlib 内核 + analyze/build/check/verify 流水线
assets/                      echarts.min.js · geo/china-shell.json · 报告模板
references/                  01 方法 · 02 公式 · 03 可比性清单 · 04 数据源 · 05 写作 · 06 错误案例 · 07 措辞纪律
examples/                    纯碱 山东/河北/江苏 完整案例（含成品 HTML 与 xlsx）
工作区/说明.txt               给人看的一句话说明
```

## 依赖

- Python 3.9+（**计算内核只用标准库**；Excel 需要 `openpyxl`）
- 校验脚本可选依赖：Edge/Chrome（HTML）、LibreOffice（Excel 重算）
- 不需要 numpy / pandas / scipy
