---
name: regional-procurement-cost
description: Use when a domestic chemical buyer or trader needs to compare procurement cost across source regions for one product — 比较不同地区采购成本 / 哪个产地采购更划算 / 跨区域到厂成本对比 / 区域价差能不能覆盖运费 / 河北沙河比山东便宜那么多,运到江苏还划算吗 — compares ≥2 source regions against one receiving location, unifying spec/unit/tax basis, giving real road distance per route, and decomposing landed-cost differences into 市场裸价差 + 运输费用 + 装卸费用. Delivers a self-contained interactive HTML dashboard plus an Excel cost model with live formulas. Never estimates freight: when the user has no freight quote, it shows the bare-price spread, transport distance and the missing items only, and refuses to produce a landed-cost ranking.
---

# 比较不同地区采购成本

## 这个 Skill 解决什么

同一件货，从山东、河北、河南买，哪个到厂更便宜？难的不是查价格，而是**四件容易做错的事**：

1. **口径没对齐**：一个报"出厂自提"、一个报"送到本地"，直接相减就是错的。
2. **距离是拍脑袋**：用省会到省会的直线距离，误差能到 30% 以上。
3. **运费靠猜**：随手填个"吨公里 0.3 元"，算出一个看着很精确的排名，实际上没有任何依据。
4. **一个省用一个点**：山东从西到东 700 多公里，用一个城市代表整个省，结论必然失真。

本 skill 的输出**只在你能验证的地方给数字**，验证不了的一律标"待补"。

## 三条硬规矩（不可协商）

> **① 不估算运费。** 没有承运方报价，就不出现任何运费金额。只展示：裸价差、运输距离、待补项目清单。
>
> **② 不同口径不直接比。** 自提 / 出厂 / 送到 必须显式标注。只要混用，就必须在"缺口假设"里登记，否则校验不通过。
>
> **③ 缺项不做排名。** 任何一个区域的运费或装卸费缺失，到厂成本排序就显示"不排名"，而不是把缺的当 0 算。

违反任意一条，`scripts/validate.py` 会直接报错退出。

## 输入

只需要一个 `research.json`（见 `references/data-contract.md`）。最少要有：

| 字段 | 说明 |
|---|---|
| `request` | 产品、规格、收货地、采购数量 |
| `quotes` | 每个区域的价格，必须带 数值/规格/地区/含税/日期/来源 六要素 |
| `routes` | 每个区域到收货地的线路与**可核验里程** |
| `regions` | 把 quote 和 route 绑起来 |
| `cost_params` | 数量、税率、装卸费（**可全为空**） |
| `gaps` / `assumptions` | 缺什么、假设什么 |

`freight_unit` / `freight_total` **允许全部为 `null`** —— 这是最常见也最合规的初态。

## 工作流

```
① 收集价格（每个数字都要能点回原文）
        ↓  references/research-playbook.md
② 核实里程（用路线库，不用直线距离）
        ↓  references/distance-and-freight.md
③ 写 research.json
        ↓  references/data-contract.md
④ 校验
        ↓  python scripts/validate.py <案例目录>
⑤ 出交付物
        ├─ python scripts/build_xlsx.py <案例目录>
        └─ node  scripts/build_engine.cjs
           node  scripts/build_html.cjs <案例目录>
        ↓
⑥ 自检
        ↓  python scripts/qa.py <案例目录>
```

计算口径见 `references/cost-formulas.md`，验收清单见 `references/qa-checklist.md`。

## 交付物

**1) HTML 交互看板**（单文件、离线、零外链 ≈ 1.1 MB）

- 首屏 KPI：裸价最低区域、区域极差、距离范围、到厂完整度
- 参数面板：收货地、数量、装卸费，**逐线路填运价，改动即时重算**
- 现货价格表：区间、不含税折算、交货方式标签、数据日、来源链接
- SVG 地图：各起点到收货地的弧线 + 里程标签（坐标内置，无需联网）
- 到厂成本表 + 堆叠图，支持「裸价 / 到厂价 / 价差分解」三种视图
- 因素分解：裸价差 vs 运输差 vs 装卸差，附闭合校验
- 历史价差走势 + 区间表
- 逐区展开的计算明细（可直接代入的公式串）
- 缺口清单、假设清单、口径红线
- 供应商下钻链接

**2) Excel 成本模型**（9 个工作表，≈23 KB）

`0-说明 / 1-参数 / 2-价格口径 / 3-到厂成本 / 4-因素分解 / 5-线路与距离 / 6-历史价差 / 7-缺口与假设 / 8-来源`

浅黄底 = 输入格，灰蓝底 = 公式。改 `1-参数` 或 `3-到厂成本` 里的黄色格，整本联动。

## 换一个案例怎么做

1. 复制 `examples/01-soda-ash-su-zhou/` 为新目录。
2. 按 `references/data-contract.md` 重写 `data/research.json`：换产品、换区域、换收货地。
3. 重跑 ④⑤⑥。

**换收货地**要注意：里程必须重新核实，不能拿旧案例的距离改个数字。`scripts/lib/geo.cjs` 里内置了约 190 个城市的经纬度，可作为"途经点折线"的兜底估算（已用 11 条真实公路里程标定，平均偏差 −2.3%，相对 RMSE 9.5%），但**只要可能，就用真实路线里程**。

## 目录结构

```
regional-procurement-cost/
├── SKILL.md
├── README.md
├── references/
│   ├── data-contract.md          # research.json 逐字段说明
│   ├── research-playbook.md      # 价格从哪查、怎么判可比
│   ├── distance-and-freight.md   # 里程核实与运费口径
│   ├── cost-formulas.md          # 到厂成本与因素分解的完整算法
│   └── qa-checklist.md           # 交付前验收清单
├── schema/
│   └── data.schema.json
├── scripts/
│   ├── lib/geo.cjs               # 计算引擎（距离 + 到厂成本 + 因素分解）
│   ├── lib/model.cjs             # research.json → 模型输入
│   ├── build_engine.cjs          # 生成浏览器内联版引擎
│   ├── build_html.cjs            # 出 HTML
│   ├── build_xlsx.py             # 出 Excel
│   ├── validate.py               # 数据契约校验
│   ├── qa.py                     # 交付物自检
│   ├── calibrate.cjs             # 里程算法标定（对照真实公里数）
│   └── assets/                   # 模板、ECharts、内联引擎
└── examples/
    └── 01-soda-ash-su-zhou/      # 完整可跑示例
        ├── data/research.json
        ├── output/index.html
        ├── output/cost-model.xlsx
        └── README.md
```

## 依赖

- **Node.js ≥ 18**（跑 `geo.cjs`、`build_engine.cjs`、`build_html.cjs`）
- **Python ≥ 3.9 + openpyxl**（跑 `build_xlsx.py`、`validate.py`、`qa.py`）
- ECharts 5.6.0 已内置于 `scripts/assets/echarts.min.js`，不联网

## 边界

- **不预测价格。** 历史走势只描述已发生的事实。
- **不代替询价。** 运费、装卸费必须来自承运方或供应商报价。
- **不做供应商尽职调查。** 本 skill 给的是"在哪买更划算"，不是"这家能不能信"。企业风险另见 `chemical-supplier-risk-radar` 类技能。
- **运价口径必须一致。** 各条线路的运价要同为"含税/不含税""含装卸/不含装卸""单程/往返"，否则排序无意义 —— HTML 里对此有专门提醒。
