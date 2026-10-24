# chem-country-market · 研究一个目标国家市场

给外贸销售用的国别市场研究技能：换一个国家、换一个产品，产出一份**每个数字都有出处、
不知道的地方明确写缺口**的市场研究报告。

## 30 秒开始

```bash
# 1) 复制案例作为起点
cp -r examples/01-idn-soda-ash my-case

# 2) 拉目标国海关数据（免密钥）
python scripts/fetch_trade.py --reporter 360 --product 283620 --years 2021-2025 --exporter 156
python scripts/sync_case.py my-case/case.json --raw raw/comtrade_360_283620.json

# 3) 改 case.json（企业、政策、来源、缺口），然后校验
python scripts/validate.py my-case/case.json

# 4) 一条命令出全部产物（含浏览器渲染检查）
python scripts/build_all.py my-case/case.json --render
```

产物在 `my-case/out/`：
- `<国家>-<产品>_国别市场研究.html` —— 离线可开的交互式报告（1 MB 左右，ECharts 已内联）
- `<国家>-<产品>_国别市场研究.xlsx` —— 17 个工作表的工作底稿
- `data.json` —— 派生数据（给下游技能用）
- `qa/` —— 渲染截图与检查结果

## 报告长什么样

| 板块 | 内容 |
|---|---|
| 首屏 | 国别市场概览 + 6 张关键指标卡（进口额/同比/数量/中国份额/第一大来源国/本地产能） |
| 概览 | 进口趋势图 + 来源国结构环形图 + 关键判断卡 |
| 01 贸易结构 | 逐年进口表（金额/数量/单位价值/同比）、来源国前 8 位、中国出口、目标国再出口 |
| 02 本地产能与企业 | 在运/在建/中试项目卡片、本地无产能的证据链、下游企业可点击查看公开信息 |
| 03 下游产业 | 分段需求信号 + 每段明确标出的缺口、竞争来源国、当地渠道 |
| 04 关税与政策 | 税率（带状态列）、非关税措施、贸易关系时间线、研报要点与警示 |
| 05 市场进入待核实事项 | 缺口清单、P0/P1/P2 待核实行动、两个下游技能交接按钮 |
| 06 口径与来源 | 九个必答问题的口径对照表、全部来源（可点开）、字段与口径说明 |

## 这个技能和其它技能的分工

| 你想干什么 | 用哪个技能 |
|---|---|
| 一个国家的市场全貌（本技能） | **chem-country-market** |
| 某产品现在什么价、还能不能降 | `chem-market-brief` |
| 找这个国家可能买你货的工厂名单 | `b2b-lead-sourcing` |
| 照着成功客户找相似客户 | `benchmark-lead-sourcing` |
| 国内某区域该先拜访哪些城市 | `chemical-region-market-map` |
| 通过在建/拟建项目找未来客户 | `project-lead-sourcing` |

本技能的第 5 节会直接把结论打包传给 `b2b-lead-sourcing` 与出口要求查询技能。

## 三条硬规矩

1. **不臆造**：市场规模、产能、企业采购量无法核实的一律写缺口，不给数字。
2. **不分层不写**：实际贸易数据 / 机构估算 / 企业公开资料 / 一般产业描述，四类必须可区分。
3. **税率只用官方**：第三方汇总站的税率只能写“第三方称”，并进 P0 待核实。

## 文档索引

| 文件 | 什么时候看 |
|---|---|
| `SKILL.md` | 第一次用，看流程 |
| `references/data-contract.md` | 写/改 case.json 时 |
| `references/source-playbook.md` | 找数据、找不到数据时 |
| `references/tariff-policy-guide.md` | 查关税、写政策段落时 |
| `references/evidence-grading.md` | 判断一句话能不能当事实时 |
| `references/qa-checklist.md` | 交付前 |
| `references/adapters.md` | 在别的 Agent 平台里跑时 |

## 依赖

- Python 3.9+（必需）
- `openpyxl`（生成 Excel 必需）
- `websocket-client` + 本机 Edge/Chrome（渲染校验可选，缺了就跳过）

## 案例

`examples/01-idn-soda-ash/` —— 中国重质纯碱出口印度尼西亚：
43 个来源、8 项缺口、9 条待核实行动，HTML 与 Excel 均已生成并通过全部检查。
