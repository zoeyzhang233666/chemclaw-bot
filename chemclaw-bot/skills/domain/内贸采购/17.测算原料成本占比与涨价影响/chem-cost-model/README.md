# chem-cost-model · 化工原料成本占比与涨价影响测算

> 输入一个产品的主料单耗和市场价格，输出两份东西：
> **① 一个可交互的 HTML 计算器**（改单耗/改价格/改涨跌幅，结果当场变）
> **② 一个全是真公式的 Excel**（改黄色格子，全表联动）
> 两者都由同一个计算引擎产生，每个数都能追到来源。

## 30 秒上手

```powershell
$env:PYTHONUTF8='1'
python scripts/build_all.py examples/01-dop-dehp/input.json --out out --name DOP-华东
```

打开 `out/DOP-华东_理论原料成本.html` 和 `.xlsx` 即可。

## 它回答什么

| 问题 | 页面位置 |
|---|---|
| 每吨产品的原料成本是多少钱？ | 首屏大数字 |
| 钱主要花在哪种原料上？ | 成本构成饼图 + 占比 |
| 最近涨了还是跌了？ | 30 天 / 3 个月窗口 |
| 某个原料再涨 5% / 10% 会怎样？ | 敏感性热力图 |
| 两种原料同时变动呢？ | 组合情景（可改幅度） |
| 这段时间涨的钱是谁带来的？ | 贡献分解 |
| 哪些数据缺？怎么办？ | 缺口清单 |

## 它不回答什么（重要）

- **不预测价格。** 敏感性只是"若涨 X% 则成本变成 Y"的机械演算。
- **不算生产成本，不算利润。** 只含原料，能源/人工/折旧/运输/期间费用全部列在"未纳入项"。
- 不用理论原料成本的价差冒充利润。

## 目录

```
SKILL.md                    技能主文件（给 agent 读）
references/
  methodology.md            六步研究法
  formulas.md               全部公式（唯一权威）
  unit-consumption.md       单耗四层口径与来源分级
  price-data-standard.md    价格六项口径与采集
  data-contract.md          input/result 字段规范
  presentation-spec.md      HTML / Excel 版式规范
  no-forecast-policy.md     表述红线
  qa-checklist.md           人工复核清单
examples/
  input.template.json       空白模板
  01-dop-dehp/              DOP（苯酐+异辛醇），真实价格 + 环评单耗
  02-soda-ash-solvay/       纯碱（氨碱法），真实价格 + 行业单耗，演示缺口处理
scripts/
  build_all.py              一键出稿
  cost_engine.py            计算引擎（唯一实现）
  units.py                  单位与税口径换算
  stoichiometry.py          化学式/分子量/配平/理论单耗
  validate.py               输入校验
  check_result.py           结果自洽（7 条恒等式）
  check_xlsx.py             工作簿静态检查（能否打开）
  check_workbook.py         Excel COM 重算对账
  qa_render.py              浏览器渲染与交互自检
  fetch_prices.py           抓生意社基准价
  refresh_prices.py         更新已保存模型的价格
  build_html.py / build_xlsx.py / templates/ / assets/
tests/test_engine.py        单元测试
```

## 自检全套（交付前必跑）

```powershell
$env:PYTHONUTF8='1'
python tests/test_engine.py
python scripts/validate.py  examples/01-dop-dehp/input.json
python scripts/check_result.py examples/01-dop-dehp/out/result.json
python scripts/check_xlsx.py  examples/01-dop-dehp/out/DOP-华东_理论原料成本.xlsx
python scripts/check_workbook.py examples/01-dop-dehp/out/DOP-华东_理论原料成本.xlsx examples/01-dop-dehp/out/result.json
python scripts/qa_render.py  examples/01-dop-dehp/out/DOP-华东_理论原料成本.html --out shots
```

## 依赖

- Python 3.9+，`openpyxl`
- 可选：`playwright`（HTML 自检）、`pywin32` + Excel（公式重算自检）

## 换成你自己的产品

1. 复制 `examples/input.template.json`。
2. 填 `meta`（产品、工艺、数据截止日、税口径）。
3. 填 `materials[]`：每个原料的 `dosage`（带来源与工艺）与 `price`（六项口径）。
4. 拿不到价格的原料，`price` 留空 → 自动进缺口清单，不会被当成 0。
5. 跑 `build_all.py`。
