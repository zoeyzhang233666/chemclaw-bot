---
name: chemical-region-spread
description: Use when someone needs to compare the same chemical product's spot price across two or more regions and understand whether the gap is real or an artifact — 比较地区价差 / 区域价差 / 山东河北江苏纯碱价差 / 哪个地区更贵 / 跨区调货划不划算 / 两地价差历史分位 / 价差为什么扩大 / regional price spread / inter-region arbitrage check. Covers any bulk chemical (纯碱、烧碱、尿素、甲醇、PVC、PTA、玻璃、碳酸锂、钛白粉、丙烯酸…). Delivers a self-contained interactive HTML report (click to pick 2–5 regions, price curves, pairwise spread matrix, historical percentile, regional map, live freight re-computation, drill-down into anomalous spread phases) plus a 17-sheet Excel workbook in which the spread matrix, percentiles and freight adjustment are all native formulas, so changing a price re-computes everything.
---

# 比较不同地区价差（区域价差研究）

## 这个 Skill 解决什么问题

用户问的是这一类问题：

> 「请比较**重质纯碱**在**山东**、**河北**、**江苏**最近一年的现货价格。」

表面上是查三个价格然后相减。真正要交付的是**四个分开的结论**，并且**不能被混成一句话**：

| 层 | 内容 | 常见错误 |
|---|---|---|
| ① 可比性 | 三地区卖的是不是同一个东西（规格 / 税率 / 计量 / 交付 / 付款 / 时点） | 拿「出厂价」和「送到价」直接相减 |
| ② 裸价差 | 按日期对齐后的 `价差 = 甲 − 乙`，方向写清 | 只说「价差 95」不说谁减谁 |
| ③ 运输成本 | 地区间里程、可用方式、运费 | 未提供真实运费就自己估一个数 |
| ④ 扣费后参考差异 | `目的价 − (产价 + 综合运费)` | 把「覆盖运费」直接说成「套利机会」 |

**这个 Skill 的核心纪律（写死在代码里，不靠自觉）：**

1. **未提供运费时不得自行估算，也不要直接将价差认定为套利机会。**
2. 三地区报价先统一口径，再按日期对齐；缺口**剔除，绝不插值**。
3. 缺失值一律 `null`，**绝不用 0 顶替**；算不出来就不让算。
4. 裸价差、运输成本、扣费后差异**永远分列**。
5. 相关关系不写成因果；历史分位不写成价格预测。

---

## 什么时候用它

**用：**
- 「X 在 A、B、C 三地最近 N 个月的现货价差」
- 「哪个地区价格最高 / 最低，价差现在处在历史什么位置」
- 「两地价差这么大，能不能跨区调货 / 套利」
- 「河北比山东便宜 95 元，运到山东还有钱赚吗」
- 「这段时间价差为什么扩大了」

**不用（换别的 Skill）：**
- 只看**单个**地区的行情走势 → 用行情速览类 Skill
- 要**找客户 / 找下游工厂** → 用客户线索类 Skill
- 要**期现基差 / 期货套保** → 本 Skill 只做区域现货价差，期货是可选扩展而非主体

---

## 标准工作流

### Step 0 · 先问清三件事（缺了就按默认值并在报告里标注）

| 要素 | 默认 | 为什么必须问 |
|---|---|---|
| 产品 + 规格 | 重质 / 轻质必须分开 | 轻重碱价差本身就有 100–300 元/吨，混算等于废掉结论 |
| 地区（2–5 个） | 用户点选 | 超过 5 个两两组合爆炸，且运费矩阵不可维护 |
| 时间范围 | 近 1 年（52 周）；分位另算 1y / 3y | 少于 52 期不足以谈分位 |

### Step 1 · 定口径（**先做这步，做错全盘皆错**）

按 `references/03-价格可比性检查清单.md` 逐项过五要素：**规格 / 税率 / 计量 / 交付 / 付款**。

对纯碱，有一条关键行业事实决定了整个设计：

> **轻碱统一采用出厂价；重碱除西北以外地区采用送到价，西北地区采用出厂价。**
> —— 期货日报《纯碱的物流仓储与价格政策介绍》（2019-12-01）

所以山东 / 河北 / 江苏的重碱报价**运费已经内含**。因此本 Skill 默认：

- **主口径 = 送到价**（同口径直接可比，换算步数为 0）
- **对照口径 = 出厂价**（用于把运费显性化、做物流可行性核对）
- 报告必须提示：**送到价口径下不可重复扣减整段运费**

### Step 2 · 取数

`references/04-数据源与口径清单.md` 列了可用源与每个源的已知缺陷。取数时**每条都要记**：
日期 / 规格 / 地区 / 税基 / 交付方式 / 来源机构 / 数值。

**找不到就写「未查到」**，不要用估算数冒充。DEMO 数据必须在报告顶部挂醒目徽标。

### Step 3 · 对齐

ISO 周（周五锚）或 exact 日对齐。规则见 `references/02-计算口径与公式.md`：

- 三地区**同一周都有报价**才进入价差样本
- 缺失周剔除，计入「对齐质量」表
- 不同口径的缺口不同 → 可用周数不同，**这是正确行为，不是 bug**

### Step 4 · 算价差

```python
spread(a, b) = P(a) − P(b)      # 正数 = a 比 b 贵
matrix[i][j] = P_i − P_j         # 行 − 列
```
- 全部有序对（A−B 与 B−A 都要算，互为相反数，用作自检）
- 同时给：当前值、N、均值、标准差、最小 / 最大、最新日期

### Step 5 · 历史分位

```
分位 = (#{x < v} + 0.5 · #{x = v}) / N × 100%
```
**必须用中秩处理并列值**。`PERCENTRANK` 对并列取最小秩，会把重复报价的分位系统性算偏。
同时报告 **N**；N < 30 标注低置信。

### Step 6 · 运输与运费

- 里程：标清「已核实」还是「估算」；估算是必须替换的项
- 方式：≤300 km 汽运为主，>300 km 铁运为主；沿江沿海可内河 / 海运
- 运费：**分「真实报价」和「默认参考值」两级**，逐条标来源

```
综合运费 F = 主运费 + 装货费 + 卸货费 + 短驳费 + 其他
到货成本 Landed = P(产地) + F
扣费后参考差异 Ref = P(目的地) − Landed = 裸价差 − F
```

**任一项未知 → F 为空 → Ref 不计算。** 不按 0 计。

### Step 7 · 解释变化

把价差变化挂到**可核对的事件**上（装置检修 / 产能投放 / 需求塌陷 / 物流中断 / 口径变更），
每条写清 `经济链条`：装置事件 → 区域供给 → 本地价格 → 价差。
用 `references/07` 的措辞纪律：**只解释「可能为什么变化」，不做因果判定**。

### Step 8 · 交付

```bash
python scripts/init_analysis.py --prices my_prices.csv --events config/events_fundamentals.json
python scripts/analyze.py --config config/project.json --out build/result.json
python scripts/build_html.py --result build/result.json --out build/report.html
python scripts/build_excel.py --result build/result.json --out build/workbook.xlsx
python scripts/check_html.py  --html build/report.html --result build/result.json
python scripts/verify_excel.py --xlsx build/workbook.xlsx --result build/result.json
```

或一条命令：`python scripts/build_all.py --prices my_prices.csv`

---

## 交付物

### HTML 报告（单文件、可离线、零外部请求）

- 顶部：数据状态徽标（REAL / DEMO / CLIENT）+ 口径徽标 + 样本期
- ① 口径统一：三地区报价口径对照 + 8 项核对清单 + 换算日志 + 双口径对照
- ② 价格与对齐：**点选 2–5 个地区**的走势图（可切 元/吨 或 指数）、对齐质量表、点某周看当日三价与事件
- ③ 两两价差：**行−列矩阵**（红=偏贵、绿=偏便宜，悬停看 N 与日期）+ 全部有序对明细
- ④ 历史分位：1y / 3y / 全样本分位表 + **滚动 1 年分位曲线** + 分布直方图
- ⑤ 物流与运费：路线表（里程可信度、可用方式）、**运费输入框、开关运费调整实时重算**
- ⑥ 异常价差阶段：`|z| ≥ 1` 且连续 ≥3 周 → 点击查看该阶段**三地区价格快照 + 同期事件 + 经济链条**
- ⑦ 区域地图：三地区气泡（大小=可核实产能）+ 连线（粗细=里程）
- ⑧ 已知缺口与免责声明

### Excel 工作簿（17 张表，全原生公式）

`00 封面说明` / `01 口径与来源` / `02 价格(主口径)` / `03 价格(对照口径)` / `04 价差明细` /
`05 价差矩阵` / `06 历史分位` / `07 滚动分位` / `08 运输距离` / `09 运费参数` /
`10 运费调整` / `11 企业产能` / `12 下游结构` / `13 国标与规格` / `14 区域事件` /
`15 数据质检` / `16 计算公式`

**改 `02` 表的价格，`04`/`05`/`06`/`10` 全部自动重算。** 改 `09` 表的运费，`10` 表自动重算。
每个公式的含义见 `16 计算公式`，都能被复算。

---

## 必须说出口的话

报告里必须出现这些句子（不是免责套话，是防止误读的实质性提示）：

1. 「主口径为送到价，**运费已内含在报价内，不可重复扣减**」
2. 「**未提供真实运费**，扣费后差异仅作敏感性参考」
3. 「价差覆盖运费 **≠ 套利机会**」（未计资金占用、损耗、账期、短驳、仓储、开票、可成交批量）
4. 「分位高**不预示**回落；分位只回答『在这段历史里排第几』」
5. 「事件与价差变化的对应**只用于解释**，未做因果检验」
6. DEMO 数据：「**金额与分位不得用于报价、交易或对外引用**」

---

## 文件结构

```
chemical-region-spread/
├── SKILL.md
├── README.md
├── config/
│   ├── project.json              # 项目元信息 + 地区 + 口径 + 来源 + 已知缺口
│   ├── events_fundamentals.json  # 事件日历 + 产能/下游/工艺结构
│   └── routes.json               # 6 条有向路线 + 运费参数 + 已核实锚点
├── data/
│   ├── prices_template.csv              # 空白模板（附示例行 + 列说明）
│   └── demo_soda_ash_*_weekly.csv       # 纯碱 DEMO 双口径序列
├── scripts/
│   ├── spreadlib.py       # 计算内核（纯标准库，可单测）
│   ├── analyze.py         # 主分析 → result.json
│   ├── init_analysis.py   # 用户 CSV → 标准配置
│   ├── make_data.py       # DEMO 数据生成（锚定已核实骨架）
│   ├── build_html.py      # → 自包含 HTML
│   ├── build_excel.py     # → 17 表工作簿
│   ├── build_all.py       # 一键驱动
│   ├── check_html.py      # 无头浏览器真实执行校验
│   ├── verify_excel.py    # LibreOffice 重算 + 与 Python 对账
│   ├── data_quality.py    # 质检报告
│   ├── selftest.py        # 内核单测
│   ├── app-core.js        # JS 计算内核（与 Python 逐函数对齐）
│   └── app-ui.js          # 渲染与交互
├── assets/
│   ├── echarts.min.js           # 图表内核（内联，离线可用）
│   ├── geo/china-shell.json     # 示意地图
│   └── templates/regional-spread-report-template.html
├── references/
│   ├── 01-方法说明.md
│   ├── 02-计算口径与公式.md
│   ├── 03-价格可比性检查清单.md
│   ├── 04-数据源与口径清单.md
│   ├── 05-报告写作模板.md
│   ├── 06-常见错误案例.md
│   └── 07-措辞纪律.md
├── examples/soda-ash-shandong-hebei-jiangsu/
│   ├── README.md
│   ├── data/…  result.json  report.html  workbook.xlsx
└── 工作区/说明.txt
```

---

## 质量门（不通过不许交付）

| 门 | 判据 | 谁来验 |
|---|---|---|
| 内核正确 | 单测全绿（分位、运费、对齐、反常识别） | `selftest.py` |
| HTML 能跑 | 无头浏览器真实执行，**无 JS 异常**，图表 canvas 有像素 | `check_html.py` |
| 数值一致 | JS 与 Python 的价差 / 分位差异 < 0.15 | `check_html.py` |
| Excel 能算 | LibreOffice 重算后**无 `#REF!` 等错误值** | `verify_excel.py` |
| Excel 对账 | 矩阵 / 分位 / 运费差异 < 0.01 | `verify_excel.py` |
| 口径完整 | 换算日志无缺失参数，或缺失项已标注 | `data_quality.py` |

---

## 常见坑（详见 `references/06`）

1. **出厂价减送到价** → 凭空多出 50–100 元/吨的"价差"
2. **从送到价里再扣一遍运费** → 重复扣减
3. **用外部运费替代「内含运费」** → 换算基数是错的
4. **缺失填 0** → 价差被凭空创造出来
5. **插值填缺口** → 分位被平滑掉，异常阶段消失
6. **`PERCENTRANK` 算并列** → 分位系统性偏低
7. **把「覆盖运费」说成「套利机会」** → 最严重的一类错误
8. **省级产能合计凑数** → 宁缺不假
9. **「河北碱多所以便宜」** → 相关不等于因果，且事实方向可能相反
10. **月份对不齐** → 把「周一发布的上周数据」配给本周价格

---

## 纯碱实例（已跑通）

`examples/soda-ash-shandong-hebei-jiangsu/`

| 项 | 值 |
|---|---|
| 口径 | 重质纯碱，GB/T 210-2022 Ⅱ类优等品，元/吨 |
| 样本 | 152 周（DEMO，锚定已核实骨架），剔除 4 周缺口 |
| 山东 / 河北 / 江苏 | 1370 / 1275 / 1385（全期分位约 10%，绝对价格处历史低位） |
| 山东−河北 | +95（1y 分位 91.3%，3y 分位 89.1%）→ 价差处历史高位 |
| 河北−江苏 | −110（1y 分位 4.8%，3y 分位 8.2%） |
| 江苏−河北 | +110（1y 分位 95.2%，3y 分位 91.8%）→ 价差处历史高位 |
| 异常阶段 | 18 段；最大：山东−河北 2024-09~12 走阔 +45.6、河北−江苏 2024-03~07 收敛 −44.9 |
| 运费覆盖 | 6 个方向 **0 个** 覆盖承运成本（默认参考运费参数） |

> **教学点**：三地区**绝对价格**都在历史低位（全期分位约 10%），但**价差**在历史高位。
> 两者不矛盾——价格同步下跌，跌幅不同把价差推到极端。报告必须分开这两层，
> 不能写成「价格低所以价差小」。

**数据状态：DEMO。** 山东、河北、江苏的城市级独立日度序列在免费公开源中未查到；
序列以已核实的真实骨架为锚构造，用于演示完整方法，**金额不可对外引用**。
