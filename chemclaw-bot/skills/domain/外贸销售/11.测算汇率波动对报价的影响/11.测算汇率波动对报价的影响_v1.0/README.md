# 汇率波动对报价的影响 · 外贸销售测算技能

一笔 10 万美元的出口订单，90 天后才收汇。这三个月里汇率每动 1%，毛利就挪 6,704 元。
销售需要的不是"汇率会涨还是会跌"，而是三个能交代的数字：**现在在历史什么位置、动多少会少赚多少、跌到哪儿就白干**。

本技能把这三个问题的答案做成两份文件：一份能点的 HTML 测算台，一份改了输入就自动重算的 Excel 工作簿。

---

## 快速开始

### 看现成的案例

打开 `examples/01-export-soda-ash-usd/build/` 下的 HTML，双击即可（离线、无外链）。

### 跑自己的单子

```bash
# 1. 复制并改案例参数
cp examples/01-export-soda-ash-usd/case.json my-case.json
#    改 amount_fx / currency / direction / cny_cost / target_margin_pct ...

# 2. 算
python scripts/run_case.py my-case.json

# 3. 出文件
python scripts/build_html.py  --scenario my-case/build/scenario.json --out my-case/out.html
python scripts/build_xlsx.py  --scenario my-case/build/scenario.json --out my-case/out.xlsx
```

### 汇率数据过期了？

```bash
python _fx/fetch_safe.py                                  # 重抓最近 3 年中间价
python scripts/build_fx_series.py --raw data/safe_mid_raw.json --out build/fx_series.json
```

---

## 两份交付物

### HTML 测算台（单文件 1.5 MB，离线可用）

四个页签，改任何输入都实时重算：

| 页签 | 你能在这里做什么 |
|---|---|
| **测算台** | 一眼看到六个数：基准汇率、历史分位、人民币收入、每 1% 敞口、毛利额、平衡汇率。下面接走势图、历史位置条、±1/2/3/5% 敏感性表与双图、平衡汇率曲线、可编辑的分批结算表 |
| **历史数据** | 1 年 / 3 年切换，看走势、分布直方图、区间统计、735 天原始明细 |
| **带入报价** | 算报价底线（保目标毛利所需的最低外币金额与单价），导出 JSON 给报价单用 |
| **公式与缺口** | 所有公式的写法、9 项未计入因素、数据来源、免责声明 |

### Excel 工作簿（11 张表，公式全部保留）

```
00_封面说明      用法指引 + 数据标签 + 合规边界
01_输入参数      ★ 黄底就是这里，改这一个表的 8 个数
02_汇率敏感性    9 档 × 6 列，全部公式
03_毛利测算      毛利、毛利率、三个平衡汇率
04_计算公式      16 条公式的写法与推导
05_分批结算      各批金额/天数/汇率可改，自动校验合计
06_历史汇率序列  735 天 × 25 币种（唯一存放静态数值的表）
07_历史分位      分位、最高最低、区间宽度——用公式现场算
08_实时汇率记录  取数留痕模板
09_报价带入      报价底线
10_口径与免责    9 项缺口 + 来源 + 免责
```

**只用改黄底格。** 打开后建议按一次 `Ctrl+Alt+F9` 全量重算。

---

## 三个反直觉的发现（来自本案例实测）

### 1. 中间价不等于到手价，差 0.75%

2026-10-19 官方中间价 6.7208，但中国银行美元**现汇买入价**（出口结汇真正用的）是 6.6701。
10 万美元一单，纸面数字和到手数字差 **5,070 元**。

### 2. 真正脆弱的不是"会亏"，而是"达不到目标毛利"

| 平衡点 | 汇率 | 距基准 |
|---|---|---|
| 毛利归零 | 6.0000 | **−10.50%** |
| 保住 10% 目标毛利 | 6.6667 | **−0.56%** |

按近一年 1.06% 的年化波动，90 天跌 10.5% 几乎不可能，所以"这单会亏"基本不用担心。
但 90 天的正常波动就有 0.53%，而保 10% 毛利只剩 0.56% 的空间——**目标本身几乎没有容错**。

### 3. 分批不降低汇率风险

分批改变的是"暴露时点的分散程度"，不改变"汇率变动 × 总敞口"这一项。
方向未知时，分批只降低单点集中度，不降低期望损失。不要把它当成"更安全"的方案。

---

## 硬性边界

| 做什么 | 不做什么 |
|---|---|
| 用官方原始数据，每条带来源+日期+时刻 | ❌ 预测汇率方向 |
| 报历史分位、波动幅度、情景盈亏 | ❌ 推荐远期/期权/掉期或任何避险操作 |
| 把"若汇率为 R"作为压力测试呈现 | ❌ 说"大概率会涨/跌" |
| 明确列出未计入的因素 | ❌ 假装模型完整 |
| 模拟参数打「模拟」标签 | ❌ 把示例数据说成真实成交 |

**分位低不等于会涨，历史波动不代表未来波动。** 这两句话出现在每一处可能出现误读的地方。

---

## 校验

交付前必须全绿：

```bash
python scripts/check_workbook_static.py <xlsx> <scenario.json> build/fx_series.json   # 29 项
node   scripts/qa_render.mjs <html> --shots shots/                                     # 37 项
node   scripts/visual_audit.mjs <html>                                                 # 布局/对比度
python scripts/verify_formulas_com.py <xlsx> <scenario.json> build/fx_series.json      # Excel 真算
```

案例实测结果：静态 29/29、渲染 37/37、视觉审计 0 问题、Excel 与 Python 引擎逐项一致。

细则见 `references/qa-checklist.md`。

---

## 目录

```
SKILL.md                     技能定义（给 agent 读）
README.md                    本文件
references/
  data-contract.md           四个 JSON 的字段契约
  formulas.md                全部公式、推导、边界情形
  data-sources.md            取数来源与口径陷阱
  qa-checklist.md            交付前校验清单
  adapters.md                接入报价系统 / 换币种 / 进口 / 订单池
examples/
  01-export-soda-ash-usd/    完整案例 + 逐步走查（含 HTML 与 Excel 成品）
    case.json                输入
    README.md                案例走查
    build/                   生成的 HTML / Excel / scenario.json
    shots/                   四个页签 + 移动端截图
scripts/
  calculations.py            计算引擎（币种无关，纯函数）
  build_fx_series.py         SAFE 原始数据 → fx_series.json
  run_case.py                case.json + 汇率 → scenario.json
  build_html.py              生成 HTML（内含禁用词扫描）
  build_xlsx.py              生成 Excel（公式可运行）
  check_workbook_static.py   Excel 结构与公式静态检查
  verify_formulas_com.py     用 Excel 计算引擎真机验算
  qa_render.mjs              Playwright 渲染与交互检查 + 截图
  visual_audit.mjs           重叠/截断/对比度/字号审计
  templates/dashboard.html   HTML 模板
  assets/echarts.min.js      内联图表库
```

---

## 环境

- Python 3.12+（`openpyxl`, `numpy`, `pandas`；`pywin32` 仅 Excel 真机验算需要）
- Node 18+（`playwright`，用于渲染检查）
- Excel 2016+ / WPS（打开工作簿）

**依赖说明**：Excel 侧刻意不使用 `MAXIFS` / `MINIFS`（部分 Office 版本返回 `#NAME?`，已在本机实测），改用 `AGGREGATE` + `SUMPRODUCT`，兼容范围更宽。
