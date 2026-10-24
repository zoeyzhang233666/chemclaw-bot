# 查基差季节性 — 技能包

研究一个品种的**期现基差季节性**：当前处在历史什么位置、有没有稳定的季节形态、
这个形态可不可信。

## 快速开始

```
SKILL.md                              ← 先读这个，核心原则与执行流程
references/
  contract-mapping-rules.md           ← 四种映射口径 + 换月记录规范（必读）
  comparability-audit.md              ← 可比性审计逐项检查表
  data-sources.md                     ← 各数据源可用性实测结论（避免重复踩坑）
  stat-methods.md                     ← 经验分位/稳定性/位置判定算法
examples/
  methanol-basis-walkthrough.md       ← 甲醇完整实战案例（含踩坑与修正过程）
templates/
  report_template.md                  ← HTML 报告结构规范与验证方法
  workbook_spec.md                    ← Excel 15 表结构规范与公式要点
scripts/                              ← 可直接复用的脚本
  fetch_futures.py                    ← 逐合约期货日线抓取
  fetch_spot_100ppi.py                ← 生意社基准价抓取
  build_contracts.py                  ← 合约日历与最后交易日规则核验
  build_basis.py                      ← 三套映射 + 基差 + 换月日志
  basis_seasonality.py                ← 季节性统计引擎（命令行）
  supp_analysis.py                    ← 稳定性/换月污染/固定交割月
  make_report_data.py                 ← 汇总 JSON 数据包
  make_html.py                        ← 生成自包含 HTML 报告
  make_xlsx.py                        ← 生成 Excel 工作簿
assets/
  甲醇_基差季节性研究报告.html          ← 成品 HTML 报告（可直接打开）
  甲醇_基差季节性_数据工作簿.xlsx       ← 成品 Excel 工作簿（15 表）
```

## 三分钟上手

```bash
# 1. 抓期货（逐合约，不要只抓连续合约）
python scripts/fetch_futures.py --prefix MA --start 2019-01 --end 2027-12 --outdir raw

# 2. 抓现货
python scripts/fetch_spot_100ppi.py --outdir out

# 3. 核验合约规则
python build_contracts.py --raw raw --out out

# 4. 构建映射与基差
python scripts/build_basis.py --raw raw --out out

# 5. 季节性统计
python scripts/basis_seasonality.py \
    --spot out/_in_spot_near.csv \
    --map  out/_in_fut_near.csv \
    --outdir out/seas_near --label near

# 6. 补充分析
python scripts/supp_analysis.py --out out

# 7. 出报告
python scripts/make_report_data.py --out out
python scripts/make_html.py --out out
python scripts/make_xlsx.py --out out
```

## 三条不能违反的原则

1. **基差 = 现货 − 期货**，符号全程不变，正数表示现货升水。
2. **映射规则显式声明 + 记录每一次换月**。固定交割月/主力连续/近月连续
   三者的基差序列**不能混为一个统计样本**。
3. **缺失数据不填补**。不插值、不前值填充、不估算。缺失就是缺失，写进缺口表。

## 最容易犯的错

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 用全国基准价冒称华东现货 | 下游按错误口径套保定价 | 显式降级声明，写清限制 |
| 近月映射不加流动性门槛 | 基差方向都可能算反 | 临近交割持仓<主力5%则跳过 |
| 用第三方连续合约 | 换月规则不透明，无法复现 | 从逐合约自建 |
| 把换月跳空当基差变化 | 污染季节性统计 | 提取换月日志，单独量化 |
| 只看均值 | 被单一年份拉飞 | 均值与中位数并列 |
| 插值补缺失 | 凭空制造季节性 | 标记缺失，不填补 |
| 把固定交割月跨年拼接 | 接缝处伪跳变 | 各年独立样本 |
| 只给一条均值线 | 看不到极端年份 | 每年一条原始曲线 |

## 数据源可用性速查

| 数据 | 渠道 | 状态 |
|---|---|---|
| 全国现货基准价 | 生意社资讯列表页 | ✅ 可用，1083 条含链接 |
| 期货逐合约日线 | 新浪 InnerFuturesNewService | ✅ 可用，95 个合约 |
| 华东区域现货 | 隆众/卓创 | ❌ 需登录/付费 |
| 交易所仓单库存 | 郑商所 | ❌ HTTP 412 |

详见 `references/data-sources.md`。

## 成品示例的核心结论

甲醇 2022-08 ~ 2026-10（4.18 年，1003 个日度配对）：

- **当前**：近月连续基差 631.67 元/吨，处于 10 月历史同期 100% 分位（z=+5.49，样本仅 4 年）
- **形态**：3–6 月倾向升水（中位 134–180），7–8 月走弱，8 月 5 年全部贴水
- **稳定性**：月份仅解释基差总方差 **19.0%**，多数月份跨年 CV > 1 → 季节性弱
- **限制**：现货为全国基准价非华东报价；样本 4–5 年；库存数据缺口

> 以上描述**历史已实现**规律，不构成对未来基差变化的预测。
