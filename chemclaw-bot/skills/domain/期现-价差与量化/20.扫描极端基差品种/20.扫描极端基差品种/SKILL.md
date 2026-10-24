---
name: scan-extreme-basis
description: Use when a trader, analyst or sales rep needs to find which chemical futures products currently sit at an extreme spot-futures basis — 扫描极端基差品种 / 哪些品种基差走极端 / 基差历史分位 / 现货升贴水偏离 / 现货vs期货价差排行 / 品种基差位置一览. Runs a cross-product scan where every product's basis is scored against ITS OWN history only (never against other products' basis amounts), discloses sample length, valid dates, contract mapping and cross-validation for every product, states plainly which products could not be scanned and why, and delivers a self-contained interactive HTML leaderboard plus a 13-sheet Excel workbook.
---

# 扫描极端基差品种（scan-extreme-basis）

跨品种扫描「现货 − 期货」基差，找出当前处于**自身历史分布极端**位置的品种，
交付一份自包含 HTML 看板 + 一份可复现 Excel 工作簿。

## 何时使用

用户说「扫一下基差」「哪些品种基差走极端」「基差历史分位」「现货期货价差排行」
「哪个品种现货便宜/贵」「品种基差位置一览」等，或需要在一批化工品里挑出基差异常的品种时。

## 三条不可让步的口径红线

1. **基差 = 现货基准价 − 期货收盘价**，符号永远如此，不允许逐个品种换符号。
2. **分位只在品种自身历史内计算**。不同产品的基差金额绝对不可横向比较
   （甲醇 769 元/吨与 PVC −39 元/吨之间没有"谁更极端"的含义）。
   排行榜只按分位排序，绝不按金额排序。
3. **不把高低分位翻译成多空信号**。看板与工作簿都必须带这句声明。
   现货含税、期货不含税，基差天然含增值税项，绝对值不能与"无税基差"经验值对照。

## 必须披露的四件事（否则榜单不可复现）

| 项 | 披露位置 |
|---|---|
| 样本长度（实际有效交易日数） | 看板顶部提示条 + KPI + 覆盖核验表 |
| 有效日期区间（窗口起止） | 覆盖核验表逐品种 |
| 合约映射规则（主力/近月 + 换月） | 品种池表 + 详情页口径声明 |
| 交叉校验通过率（我方 = 源站） | 覆盖核验表 + Excel 04 页 |

**样本长度是最容易翻车的地方。** 名义窗口（默认 3 年）只是上界；
公开可回溯的现货样本往往只有几个月。必须实测后如实写"实际 n 个交易日"，
并在样本 < 1 年时明确说明"尚未覆盖完整季节性，不能外推为多年分位"。
不要因为名义窗口是 3 年就宣称做了 3 年历史分位。

## 标准流程

```bash
export PYTHONPATH=$PWD/src           # Windows: $env:PYTHONPATH="$PWD\src"

# 1) 抓现货基准价（生意社逐日「市场基差」稿）
python -m basis_scan.fetch_spot --codes MA,SA,V,PP,L,TA,EG,UR,SH,EB,FG,PX \
    --max-pages 12 --out data/raw/spot --cache data/cache

# 2) 抓期货逐合约日线 + 构造连续序列
python -m basis_scan.fetch_futures --codes MA,SA,V,PP,L,TA,EG,UR,SH,EB,FG,PX \
    --years-back 6 --cache data/cache

# 3) 补充库存/仓单（交易所仓单）+ 产业事件线索
python -m basis_scan.fetch_fund --root . --out out/fundamentals.json

# 4) 扫描：对齐 → 基差 → 品种内分位 → 极端判定 → 覆盖核验
python -m basis_scan.scan --codes MA,SA,V,PP,L,TA,EG,UR,SH,EB,FG,PX \
    --window-years 3 --threshold 0.10 --min-obs 120 --out out

# 5) 交付物
python -m basis_scan.make_html --result out/scan_result.json --out "out/极端基差扫描看板.html"
python -m basis_scan.make_xlsx --result out/scan_result.json --out "out/化工极端基差扫描_数据工作簿.xlsx"
```

`out/scan_result.json` 是唯一数据源，HTML 与 Excel 都从它渲染 —— 所以两者必然一致。

## 参数（全都可调）

| 参数 | 默认 | 说明 |
|---|---|---|
| `--codes` | 12 品种 | 品种池，逗号分隔 |
| `--window-years` | 3 | 名义历史窗口上界；实际按可用样本降级 |
| `--threshold` | 0.10 | 极端阈值，低端 ≤10% 分位、高端 ≥90% 分位 |
| `--min-obs` | 120 | 窗口内有效交易日不足则判「数据不足」，不参与排名 |
| `--change-window` | 21 | 近一月的交易日口径 |
| `--roll-rule` | main | `main` 主力连续 / `near` 近月连续 |
| `--anchor` | 数据最新日 | 历史窗口的锚点日期 |

## 关键实现要点

- **单位换算必须在相减之前**。现货与期货计价单位可能不同（玻璃现货 元/平方米、
  烧碱现货 32% 液碱折百，期货 元/吨）。正确做法是从源站文章自带的换算式
  `市场基差=现货价格-期货价格=629/0.32-1707=258.625` 反解除数，取逐日中位数，
  而不是凭经验拍一个系数。换算后必须仍能通过交叉校验，通不过说明系数错了。
- **交叉校验是质量闸门**。用源站稿子自带的三行公式与我方独立计算逐日比对，
  差值 ≤0.05 元/吨 记一致。某个品种通过率突然下降，通常意味着单位/口径错了。
- **源站自身也可能前后不一致**。识别方式：某日「标题基差」≠「正文公式计算值」。
  这类日子单列为 `src_drift`，如实记录，不静默修正。
- **换月跳空不修正但必须披露**。主力连续在换月日有价格跳空，
  窗口内换月次数与 ≥30 元/吨 的跳变在详情页与 Excel 10 页列出。
- **不做插值/前值填充**。期货缺该交易日即不出基差。

## 无法扫描的品种必须单列

分两类写清楚，附已尝试的来源与后续建议：
- **历史窗口样本不足**（如 PTA 96 日、乙二醇 118 日 < 120 日门槛）
- **口径不一致 / 无逐日序列**（如液化气进口价、纸浆无同基准现货）

「本次只覆盖 X/Y 个品种」必须明说，不得把部分扫描包装成全市场排名。

## 文件布局

```
scan-extreme-basis/
├── SKILL.md                     本文件
├── references/
│   ├── data-sources.md          数据源、接口与反爬处理
│   ├── basis-methodology.md     基差/分位/换月/校验的方法论与边界
│   └── troubleshooting.md       常见故障与修复
├── examples/
│   └── case-2026-10-20.md       完整实战案例（含真实数字）
├── scripts/
│   ├── basis_scan/              可运行包（7 个模块）
│   └── assets/echarts.min.js    离线图表库
└── templates/
    └── 极端基差扫描看板.html      HTML 模板（模板变量说明见文件头）
```

## 交付前自检

- [ ] 每个品种的 `status` 都已判定，`数据不足` 的写明了原因
- [ ] 覆盖核验表里每个可扫描品种的交叉校验通过率 ≥95%，否则回查口径
- [ ] 名义窗口与实际样本数的差异已在看板顶部与 Excel 01 页写明
- [ ] 排行榜按分位排序，没有按基差金额排序
- [ ] HTML 无外链（离线可打开）、图表能渲染、点击能展开详情
- [ ] 工作簿通过 `check_office.py` 结构检查，sheet 数正确
- [ ] 多空信号声明在 HTML 与 Excel 里都出现
