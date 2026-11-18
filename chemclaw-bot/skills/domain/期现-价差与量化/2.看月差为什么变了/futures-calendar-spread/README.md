# futures-calendar-spread · 看月差为什么变了

把“月差为什么变了”拆成七个可验证的问题，交付一份**交互 HTML 报告 + 15 表 Excel 工作簿**，
并附一个跑通的真实案例（纯碱 `SA2612 − SA2701`，2026-10-20）。

## 快速开始

```bash
# 1) 抓逐合约日线（必须用单合约，不能用主力连续）
python scripts/fetch_futures.py --product SA --years 3 --extra SA2701 SA2703 SA2705 SA2709

# 2) 产业数据（可选，没有就如实显示缺口）
python scripts/fetch_industry.py warrant SA --out data/external/warrant_SA.csv --meta data/external/warrant_SA.meta.json

# 3) 算
python scripts/analyze_spread.py --product SA --a SA2612 --b SA2701 --asof 2026-10-20 \
    --out build/result.json --warehouse data/external/warrant_SA.csv \
    --warehouse-label "郑商所纯碱仓单(品种级)" --events data/external/events_SA.json
python scripts/build_panel.py --result build/result.json --out build/enriched.json \
    --events data/external/events_SA.json

# 4) 出报告
python scripts/build_html.py  --data build/enriched.json --out build/spread-report.html
python scripts/build_excel.py --data build/enriched.json --out build/spread-workbook.xlsx

# 5) 自检
python scripts/selftest.py
python scripts/verify_excel.py build/spread-workbook.xlsx build/enriched.json
node   scripts/check_html.js  build/spread-report.html
```

## 目录

```
SKILL.md                    技能入口（何时用、怎么跑、红线）
references/
  01-方法说明.md            三种价差的区别，为什么固定合约价差不能直接算历史分位
  02-统计公式.md            全部公式、对数贡献分解、判读规则、数据质量门槛
  03-合约匹配规范.md        别名解析、拒绝规则、gap 与 dtd 计算、流动性陷阱
  04-数据源与口径清单.md    每个数据源、覆盖区间、口径警告、已失效来源
  05-报告写作模板.md        七问对照、叙事骨架、语言纪律
  contracts_registry.json   品种合约规则登记表（含未核实字段标注）
scripts/
  spreadlib.py              纯标准库内核：月差/分位/期限结构/可比样本/分解/质检
  fetch_futures.py          逐合约日线抓取
  fetch_industry.py         仓单（东财）/ 现货（生意社）抓取
  fetch_news.py             产业新闻检索（只作线索，须回原文核对）
  match_contracts.py        近月/远月/主力/第N月 -> 具体合约代码
  analyze_spread.py         主分析，产出 result.json
  build_panel.py            构建跨年份期限结构面板 + 事件挂载，产出 enriched.json
  build_html.py             生成自包含交互报告
  build_excel.py            生成 15 表工作簿（含真实公式）
  selftest.py               33 项已知答案测试
  verify_excel.py           工作簿结构与数值一致性校验
  check_html.js             无头浏览器渲染 + 交互校验
assets/templates/
  spread-report-template.html   HTML 报告模板（构建时注入数据）
examples/SA-2612-2701/      完整真实案例：报告 + 工作簿 + result.json + README
data/raw/                   37 个 SA 合约日线 CSV
data/external/              仓单、现货、事件台账
```

## 设计上的三个关键决定

**1. 三套价差严格分开。** 固定合约价差、跨年同月份组合、动态近远月价差，
在报告里各有各的位置，绝不混入同一个历史分布。这是本场景最容易出错的地方。

**2. 样本不足就明说不不足。** SA 上市才 6 年，`SA2612` 更是 2025-12 才挂牌。
技能会把“近 1 年 / 近 3 年分位”标成不可用，而不是返回一个和全样本一模一样的数字来充数。

**3. 贡献分解用对数。** `Δln(spread) = ln(A₁/A₀) − ln(B₁/B₀)` 精确可加、无残差。
当两腿近乎同幅变动时，它如实告诉你“两腿同步相抵”，而不是算出 −2200% 这种垃圾数字。

## 红线

不给交易建议 · 不用主力连续 · 不混不同到期时间 · 不插值 · 品种级仓单不拆合约 ·
不把同期当因果 · 有 ERROR 不出结论。

完整清单见 `SKILL.md`。
