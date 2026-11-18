---
name: futures-calendar-spread
description: >
  看期货月差为什么变了：用逐合约日线算近远月价差（跨期价差/月差/calendar spread），
  给出当前值、近期变化、跨年可比分位、完整期限结构、同月份组合历史对照，
  并把“近月 vs 远月谁推动了变化”做精确分解，再用库存/仓单/交割规则/季节性/已知供需事件解释。
  触发词：看月差为什么变了 / 月差 / 跨期价差 / 近远月价差 / 期限结构 / contango / backwardation /
  反向市场 / 正向市场 / 换月 / 月差走弱 / 月差走强 / 近月升水 / 远月升水 / calendar spread。
  适用品种：国内商品期货（纯碱 SA、玻璃 FG、甲醇 MA、PTA TA、尿素 UR、烧碱 SH 等），
  纯碱为完整验证过的参考实现。
---

# 看月差为什么变了

## 这个 Skill 干什么

把“月差为什么变了”拆成七个可逐一验证的问题，并交付一份能被人追问三层而不塌的结论：

1. 两个合约的最新价格与完整历史序列（逐合约，不用主力连续）
2. 月差的定义与符号约定（`A − B`，全程不换序）
3. 当前月差、近 1 周/1 月/3 月变化、历史分位
4. 当前挂牌合约的**完整期限结构**
5. 历史**相同月份组合 + 相近距交割时间**的同类月差对照
6. 库存、仓单、交割规则、季节性、已知供需事件的解释（带来源、分证据等级）
7. **近月与远月各自对月差变化的贡献分解**（对数口径，精确可加）

**核心洞察**：用户问的“月差变了”，很多时候变的是**整条曲线的水平**，而不是月差本身。
本 Skill 会先把这件事查清楚，再谈原因——顺序错了，后面的解释全是猜。

## 什么时候用

- 用户问“月差为什么变了”“近远月价差怎么走”“期限结构怎么变成这样”
- 需要判断当前月差“贵不贵”，而不是只想知道它数值多少
- 换月之后需要重新对齐近月锚，看近端结构有没有变形
- 期货研究、套保方案评估、基差贸易定价都需要先看清结构

**不适合**：单边价格预测、推荐交易方向（本 Skill 明确不做）。

## 执行流程

### 第 1 步：确认合约与口径（不可跳过）

```bash
python scripts/match_contracts.py list --product SA --date 2026-10-20
python scripts/match_contracts.py pair --product SA --a 近月 --b 次近月 --date 2026-10-20 --json
```

先回答清楚：
- A、B 分别是哪两个具体合约（写出代码，不能写“近月”“主力”就完事）
- 相隔几个月（gap）
- 各自距交割还有多少交易日

**用户没说时**：默认取“当日最近月 − 次近月”，并在报告里明确写出这一选择。

### 第 2 步：抓数据

```bash
python scripts/fetch_futures.py --product SA --years 3 --extra SA2701 SA2703 SA2705 SA2709
python scripts/fetch_industry.py warrant SA --out data/external/warrant_SA.csv --meta data/external/warrant_SA.meta.json
```

### 第 3 步：算

```bash
python scripts/analyze_spread.py --product SA --a SA2612 --b SA2701 --asof 2026-10-20 \
    --out build/result.json \
    --warehouse data/external/warrant_SA.csv --warehouse-label "郑商所纯碱仓单(品种级)" \
    --events data/external/events_SA.json

python scripts/build_panel.py --result build/result.json --out build/enriched.json \
    --events data/external/events_SA.json
```

`analyze_spread.py` 一次产出：合约信息、月差序列、各窗口变化、三种分位、期限结构、
可比样本、贡献分解、持仓变化、仓单、事件、数据质量。

### 第 4 步：交付

```bash
python scripts/build_html.py  --data build/enriched.json --out examples/<case>/spread-report.html
python scripts/build_excel.py --data build/enriched.json --out examples/<case>/spread-workbook.xlsx
```

## 交付物

| 文件 | 内容 |
|---|---|
| `spread-report.html` | 自包含交互报告：月差走势（可切合约对/顺序/均线）、分位分布、期限结构（可回放历史日）、逐年对照、近端分段演变、贡献分解、事件台账、结论与限制。无外部依赖、无网络请求。 |
| `spread-workbook.xlsx` | 15 张表：说明、结论、合约价格、月差历史、近期变化、历史分位、可比样本、期限结构、贡献分解、近端演变、仓单库存、事件台账、**真实公式页**、数据来源、数据质量。 |
| `build/enriched.json` | 全部中间结果，供二次开发与复现。 |

## 工具与依赖

- Python 3.10+，`scripts/spreadlib.py` 只用标准库（可独立运行）
- `build_excel.py` 需要 `openpyxl`
- 数据源：新浪财经 K 线接口、东方财富仓单接口、生意社报价（均为公开接口，无需 key）
- `scripts/check_html.js` 需要 Node + 本地 Edge（用于无头渲染自检）

## 红线

1. **不给交易建议**，不给目标价，不说“建议做多/做空这个价差”。
2. **不用主力连续合约**算月差——换月跳空会凭空造出价差。
3. **不把不同剩余到期时间的月差混入同一分布**。这是本场景最容易犯、也最致命的错误。
4. **不插值、不回填、不前向填充**。缺就是缺，并在报告里说明缺什么。
5. **品种级仓单不能拆成近月/远月仓单**，也不能与社会库存相加。
6. **不把同期发生写成因果**。没做检验就只说“同期存在”。
7. **样本不足时必须说不足**。SA 上市才 6 年，很多“3 年分位”根本不成立。
8. 任一数据质量 **ERROR** 存在时，不出结论。

## 示例

`examples/SA-2612-2701/` 是完整跑通的真实案例（纯碱，2026-10-20，`SA2612 − SA2701`），
包含 HTML 报告、Excel 工作簿、结果 JSON 与 `README.md`（含逐条结论与踩过的坑）。

## 自检

```bash
python scripts/selftest.py                                   # 33 项已知答案测试
python scripts/verify_excel.py build/spread-workbook.xlsx build/enriched.json
node   scripts/check_html.js  build/spread-report.html       # 无头渲染 + 交互校验
```
