# regional-procurement-cost · 比较不同地区采购成本

同一件货，从不同产地买、运到同一个收货地，**哪个到厂更便宜**？

难点不在查价，而在四件常被做错的事：口径没对齐（自提 vs 送到）、距离靠直线估（少算 15%）、运费靠拍脑袋（算出假排名）、一个省用一个点（省内差 400 km）。

本工具把能验证的地方给数字，验证不了的一律标「待补」。

---

## 快速开始

```bash
# 1. 校验数据
python scripts/validate.py examples/01-soda-ash-su-zhou

# 2. 生成 HTML（单文件、离线、零外链）
node scripts/build_engine.cjs
node scripts/build_html.cjs examples/01-soda-ash-su-zhou

# 3. 生成 Excel（含活公式）
python scripts/build_xlsx.py examples/01-soda-ash-su-zhou

# 4. 自检
python scripts/qa.py examples/01-soda-ash-su-zhou
```

产物在 `examples/01-soda-ash-su-zhou/output/`：

| 文件 | 说明 |
|---|---|
| `index.html` | 交互看板，双击即开，不联网 |
| `cost-model.xlsx` | 9 表成本模型，浅黄格可改，整本联动 |

---

## 示例案例

**重质纯碱 · 山东 / 河北 / 河南 → 江苏苏州，100 吨**

真实数据（2026-10-16 口径），已核验公路里程：

| 区域 | 裸价（含税） | 交货口径 | 距苏州 | 特点 |
|---|---|---|---|---|
| 山东 | 1,150 | 送到（华北） | 707–760 km | 主流产区，运费中等 |
| 河北（沙河） | **945** | **自提** | 999–1,126 km | 裸价最低，但自提 + 最远 |
| 河南 | 1,100 | 送到（华中） | 665–881 km | 价格与距离都居中 |
| 江苏本地 | 1,150 | 送到（华东） | 336–436 km | 距离最近，运价最低 |

**核心张力**：沙河裸价比山东便宜 **205 元/吨**，但它是**自提**且运距 999 km 起。运费能不能吃掉这 205 元，取决于你拿到的真实运价 —— 所以示例**不给运费、不给排名**，只给判断依据。

完整说明见 [`examples/01-soda-ash-su-zhou/README.md`](examples/01-soda-ash-su-zhou/README.md)。

---

## 三条硬规矩

| # | 规矩 | 系统怎么保证 |
|---|---|---|
| 1 | **不估算运费** | 没有报价就不出现运费金额；`null` 不会被当成 0 |
| 2 | **不同口径不直接比** | 自提/出厂/送到 显式标注；混用必须登记缺口，否则校验报错 |
| 3 | **缺项不做排名** | 任一区域缺运费或装卸费 → 到厂排序显示"不排名" |

`scripts/validate.py` 会把这些规则变成可执行的检查，违规直接退出码 1。

---

## 交付物长什么样

**HTML 看板**（≈1.1 MB，单文件）

10 个区块：总览 → 参数与区域 → 现货价格 → 运输距离（SVG 地图）→ 到厂成本 → 因素分解 → 价差历史 → 计算明细 → 缺口与假设 → 找供应商 → 数据来源。

逐线路填运价，页面即时重算；运价留空时，到厂成本显示"待补"，汇总显示"不排名"。

**Excel 模型**（≈23 KB，9 表）

`0-说明 / 1-参数 / 2-价格口径 / 3-到厂成本 / 4-因素分解 / 5-线路与距离 / 6-历史价差 / 7-缺口与假设 / 8-来源`

到厂成本、因素分解、汇总排名全部是真公式。因素分解带闭合校验（`Δ裸价 + Δ运费 + Δ装卸 = Δ到厂`）。

---

## 数据从哪来

见 [`references/research-playbook.md`](references/research-playbook.md)。

本示例的价格来源（每条可点回原文）：

- 化盟网《10月16日纯碱日评》分区价格表 —— 华北/华中/华东/华南 重碱区间
- 生意社重碱基准价序列 —— 历史走势
- 郑商所合约说明 —— 交货口径规定（轻碱出厂价、重碱送到价除西北）
- 期货公司研报（转引隆众）—— 交叉验证

里程来源：车主手册 icauto 城际路线库，逐条记录了高速方案与链接，见 [`research/ROUTE_VERIFICATION.md`](research/ROUTE_VERIFICATION.md)。

---

## 换一个案例

1. 复制 `examples/01-soda-ash-su-zhou/` 为新目录
2. 按 [`references/data-contract.md`](references/data-contract.md) 重写 `data/research.json`
3. 重跑上面的四步

**换收货地必须重新核实里程**，不能把旧案例的距离改个数字。`scripts/lib/geo.cjs` 内置约 190 个城市经纬度，可在没有路线库数据时用途经点折线兜底（已标定：平均偏差 −2.3%，相对 RMSE 9.5%）。

---

## 目录

```
├── SKILL.md                        # skill 定义（给 AI 读）
├── README.md                       # 本文件（给人读）
├── references/
│   ├── data-contract.md            # research.json 逐字段说明
│   ├── research-playbook.md        # 价格从哪查、怎么判可比
│   ├── distance-and-freight.md     # 里程核实与运费口径
│   ├── cost-formulas.md            # 到厂成本与因素分解算法
│   └── qa-checklist.md             # 交付前验收清单
├── schema/data.schema.json
├── scripts/
│   ├── lib/geo.cjs                 # 计算引擎
│   ├── lib/model.cjs               # 数据适配
│   ├── build_engine.cjs            # 生成浏览器内联引擎
│   ├── build_html.cjs
│   ├── build_xlsx.py
│   ├── validate.py
│   ├── qa.py
│   ├── calibrate.cjs               # 里程算法标定
│   └── assets/                     # 模板 / ECharts / 内联引擎
├── research/                       # 来源与线路核实记录
└── examples/01-soda-ash-su-zhou/
```

---

## 依赖

- **Node.js ≥ 18** — `geo.cjs`、`build_engine.cjs`、`build_html.cjs`
- **Python ≥ 3.9 + openpyxl** — `build_xlsx.py`、`validate.py`、`qa.py`
- ECharts 5.6.0 已内置，不联网

---

## 边界

不预测价格 · 不代替询价 · 不做供应商尽调 · 不含资金成本/损耗/库存成本。
运费、装卸费必须来自承运方或供应商的真实报价。
