# 测算汇率波动对进口成本的影响

一个给**进口采购**用的汇率敏感性测算 Skill。输入一张合同，输出“汇率动一动，人民币成本变成多少”，并给出一份可交互的 HTML 计算器和一份公式可运行的 Excel 工作簿。

> **不预测汇率走势，不推荐避险产品。** 所有情景都是条件式的：“若汇率为 X，成本将是 Y”。

---

## 快速开始

```bash
# 1. 引擎自检（应输出 ALL PASS）
python scripts/fx_engine.py --demo

# 2. 跑一个案例
python scripts/fx_engine.py examples/meg-saudi-1m-usd/input.json \
    --history data/fx_real_data.json -o result.json

# 3. 生成 HTML 计算器
python scripts/build_html.py examples/meg-saudi-1m-usd/input.json \
    -o out.html --history data/fx_real_data.json

# 4. 生成 Excel 工作簿（公式可运行）
python scripts/build_xlsx.py examples/meg-saudi-1m-usd/input.json \
    -o out.xlsx --history data/fx_real_data.json

# 5. 三层校验（32 项断言）
python scripts/verify_calc.py --all
```

---

## 能做什么

| # | 能力 | 输出 |
|---|---|---|
| 1 | 四类汇率取值 + 报价方向确认 | 市场 / 中间价 / 银行购汇价 / 海关计征汇率，各带时点与来源 |
| 2 | 1/3/5 年真实历史 + 当前分位 | 趋势图、最低/最高/均值、分位百分比 |
| 3 | ±1%/±3%/±5% 敏感性 | 人民币付款额、变动额、方向判定 |
| 4 | 到厂成本影响 | 完税价格、关税、增值税、固定费用、汇率相关占比 |
| 5 | 毛利额与毛利率 | 按汇率情景逐档 |
| 6 | 盈亏平衡汇率 | 0% 与指定目标毛利，含适用性判断 |
| 7 | 分批付款敞口 | 按批次、按结算日、按情景的矩阵 |
| 8 | 四口径区分 | 法规依据与差异量化 |

---

## 目录结构

```
fx-import-cost-sensitivity/
├── SKILL.md                    # 技能主文档（硬边界、八步流程、公式速查）
├── README.md                   # 本文件
├── VERSION                     # 1.0.0
├── CHANGELOG.md
├── references/
│   ├── rate-basis.md           # 四类汇率口径详解 + 法规
│   ├── data-sources.md         # 真实数据源、可达性、取数方法
│   ├── formulas.md             # 全部公式推导与边界情况
│   ├── parameters.md           # 输入参数表
│   ├── sensitivity.md          # 敏感性与分批付款设计
│   ├── validation.md           # 三层校验体系
│   ├── portability.md          # 换币种/换商品/换条款
│   ├── qa.md                   # 常见问答与措辞边界
│   └── citations.md            # 完整出处
├── scripts/
│   ├── fx_engine.py            # 计算引擎（全参数化）
│   ├── build_html.py           # HTML 生成
│   ├── build_xlsx.py           # Excel 生成（活公式）
│   ├── xlsx_recalc.py          # 纯 Python Excel 公式求值器
│   ├── verify_calc.py          # 三层校验
│   └── cdp_check.mjs           # HTML 无头 DOM 校验
├── templates/
│   └── calculator.template.html
├── data/
│   └── fx_real_data.json       # 1,743 交易日真实汇率
└── examples/
    └── meg-saudi-1m-usd/
        ├── input.json
        ├── 案例说明.md
        └── output/
            ├── MEG_沙特_进口汇率敏感性计算器.html
            ├── MEG_沙特_进口汇率敏感性工作簿.xlsx
            └── result.json
```

---

## 防护机制

本 Skill 内置了多条拦截规则，防止常见的测算错误：

| 风险 | 拦截方式 |
|---|---|
| 报价方向搞反 | `quote_direction` 必须显式声明 |
| 用中间价冒充银行购汇价 | 四口径分离；缺 `bank` 时降级并告警，标注“演示”徽标 |
| 用当日汇率算税款 | 计征汇率独立取值，按 272 号令回溯上月第三个星期三 |
| 增值税默认计入成本 | 默认 `deductible`，需显式切换到 `cost` |
| 只有金额却算出利润 | 缺 `sales` 时强制跳过毛利模块 |
| 分位偏高 | 计算时排除当前观测本身 |
| 基准毛利已低于目标仍给平衡汇率 | 返回 `applicable: False` + 原因 |
| 人民币固定费用也乘汇率 | 固定费用单列，不参与汇率折算 |
| 编造历史数据 | 只使用真实公开数据；缺失就写缺口 |

---

## 案例速览

案例：从沙特进口 USD 1,000,000 工业级 MEG（1,136.4 吨），CFR 华东主港，装船后 90 天付款。

| 指标 | 数值 |
|---|---|
| 基准汇率（银行购汇价，演示） | **6.7435** |
| 人民币付款额 | **6,743,500** |
| 汇率每动 1% | **±67,435** |
| 到厂成本 | **7,204,900**（6,340.11 元/吨） |
| 汇率相关成本占比 | **98.73%** |
| 毛利（模拟售价 7,600 元/吨） | **+142,680.25（+1.87%）** |
| 零毛利平衡汇率 | **6.8788（+2.01%）** |
| 近 3 年中间价分位 | **4.6%** |

**一个必须注意的发现**：毛利率仅 1.87%，汇率上涨 **3%** 即转亏（毛利 −70,712.75，−0.93%）。安全垫不厚。

**另一个真实发现**：MEGlobal ACP 报价折算到厂约 6,334 元/吨，而华东现货约 5,722 元/吨，**进口平价倒挂约 1,270 元/吨**。以挂牌价进口在当前汇率下不具经济性。

---

## 校验状态

```
V1 引擎自检        13/13 PASS
V2 Excel 公式重算  13/13 PASS
V3 参数联动独立性   6/6  PASS
─────────────────────────────
合计               32/32 PASS
```

V3 的 6 项分别改动：金额翻倍、银行汇率改 7.0000、预付款比例改 50%、预付款锁定 6.7000、关税率改 0、增值税改不可抵扣。每项都重建工作簿后重新求值，确认没有硬编码。

---

## 环境要求

| 组件 | 版本 |
|---|---|
| Python | ≥ 3.10（开发于 3.14.4） |
| xlsxwriter | 3.2.9 |
| openpyxl | 3.1.5 |
| pandas / numpy | 3.0.3 / 2.4.4 |
| Node.js | ≥ 18（仅 HTML 无头校验需要） |

**不需要 Excel，也不需要 LibreOffice。** Excel 公式的正确性由内置的纯 Python 求值器 `xlsx_recalc.py` 验证。

---

## 免责

本 Skill 的输出是测算工具的结果，**不是投资建议、不是避险建议、不是汇率预测**。

- 所有情景为条件式假设；
- 银行购汇价、售价、成本须由用户以实际数据替换；
- 税率与法规以使用时最新的官方公告为准；
- 最终决策由用户及其财务/资金部门作出。
