# historical-analog-search · 找历史上最像现在的阶段

给定一个观察日，在过去里检索结构最像的几个窗口，然后如实报告它们随后 1 个月、3 个月**实际**发生了什么。

**核心立场**：这不是预测工具。它的价值一半在于找到类比，另一半——通常更重要——在于告诉你**什么时候历史样本根本不够，不能下结论**。

## 快速开始

```bash
# 1. 先体检你的数据
python scripts/search_analogs.py --csv data/methanol_weekly_panel.csv --date-col date --qc-only

# 2. 跑完整研究（产出 HTML + Excel + JSON）
python scripts/search_analogs.py \
    --csv data/methanol_weekly_panel.csv --date-col date \
    --config data/config_methanol.json \
    --asof 2026-10-14 --freq-days 7 --price-col fut_close \
    --display-cols fut_close,spot,basis,port_inv,operating_rate \
    --forward-cols fut_close,basis_pct,port_inv \
    --name methanol --outdir build

# 3. 自测（验证无未来函数、去重、缺失处理等硬规则）
python scripts/selftest.py
```

## 输入格式

**一份宽表 CSV**：每行一个观测日，每列一个指标。

```
date,spot,fut_close,basis_pct,ret_4w,port_inv,operating_rate,...
2026-10-07,3950.0,3100.0,18.1,-1.2,34.5,89.1,...
```

**一份配置 JSON**：说明每个指标是什么、怎么标准化、权重多少。参考 `data/config_example.json`。

关键字段：

| 字段 | 说明 |
|---|---|
| `key` | 必须与 CSV 列名一致 |
| `weight` | 权重，0 表示纳入展示但不影响相似度 |
| `std_method` | `rolling_z` / `expanding_z` / `rank` / `pctile_rank` / `diff_std` |
| `lookback` | 滚动窗口（期数） |
| `min_obs` | 窗口内最少有效观测，不足则不出值 |
| `rationale` | **为什么这样处理**——写给自己和复核者看 |

## 目录

```
historical-analog-search/
├── SKILL.md                        # 主文件：9 步流程 + 常见错误
├── README.md                       # 本文件
├── references/
│   ├── 01-方法论.md                 # 问题定义、时点原则、覆盖率分层
│   ├── 02-标准化与相似度公式.md       # 全部公式，可与代码逐行对照
│   ├── 03-数据源与口径清单.md         # 各品种可得数据、实测覆盖、坑
│   └── 04-报告写作模板.md            # 措辞红绿灯、自检清单
├── scripts/
│   ├── analog_lib.py               # 核心引擎（标准化/相似度/去重/后续表现）
│   ├── search_analogs.py           # 通用 CLI（跨品种）
│   ├── selftest.py                 # 27 项硬规则自测
│   ├── check_render.js             # 用 Playwright 真实渲染校验 HTML
│   └── templates/
│       ├── analog_report_template.html
│       └── assets/echarts.min.js
├── data/
│   ├── config_example.json         # 指标配置模板
│   ├── config_methanol.json        # 甲醇专用配置（实测）
│   └── methanol_weekly_panel.csv   # 甲醇 598 周真实面板（2015-01 ~ 2026-10）
└── examples/
    └── methanol-2026-10/           # 完整案例：HTML + Excel + JSON + 结论
```

## 三个硬规则（不可关闭）

1. **无未来函数**：历史日 t 的均值/标准差/分位，只用 t 当日及以前的数据。
2. **不补造**：缺失保留为 NaN。若某历史时点的指标覆盖率不足 90%，该时点直接剔除。
3. **不重复**：相邻日期不能占满名次（非极大值抑制 + 行情轮次）。

这三条都写进了 `selftest.py`，每次改代码都应该重跑。

## 覆盖率分层（本 Skill 的核心诚实机制）

实测甲醇：价格/基差回到 2015 年，但库存到 2022 年、开工率到 2025-07。若严格「全部指标都有值」，近 5 年只剩 **1~3** 个可比窗口。

所以强制输出三层对照：

| 口径 | 甲醇实测结果 |
|---|---|
| **A** 全部指标（覆盖≥90%） | 3 个候选 → 命中 **1** 个 |
| **B** 剔除覆盖不足指标 | 40 个候选 → 命中 **5** 个 |
| **C** 近 10 年仅价格/基差/月差 | 75 个候选 → 命中 **5** 个（多出 2 个 2021 年窗口） |

**A 只剩 1 个，正确结论是「样本内没有足够可比对象」，不是「找到了唯一答案」。**

## 依赖

- Python 3.9+，`pandas`、`numpy`、`openpyxl`
- 可选：`playwright`（仅 `check_render.js` 需要，用于真实渲染校验）

## 局限（写在最前面而不是最后面）

- 权重与距离尺度是人为设定，换权重名单就会变（附敏感性表）。
- 指标之间高度相关，会把同一维度的差异重复计入。
- 后续表现样本很小（N ≤ 5）且自相关，不能当作概率。
- 结构会变：形态相似 ≠ 驱动机制相同。
- 本工具**不预测价格、不给交易建议**。
