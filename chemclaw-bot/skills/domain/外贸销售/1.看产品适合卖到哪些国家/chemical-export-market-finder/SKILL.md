---
name: chemical-export-market-finder
description: Use when deciding which countries a chemical product should be sold into — "看产品适合卖到哪些国家" / "我们的产品出口到哪个国家好" / which export markets to target / 全球进口市场分析 / 中国份额与竞争来源国 / 目的国关税对比. Works for any bulk, fine or intermediate chemical (纯碱、甲醇、烧碱、钛白粉、柠檬酸、PTA、尿素…). Delivers an interactive HTML report (world map + trends + country drill-down) and an Excel workbook, in which every number carries year + source + currency + unit + HS code, every gap is marked rather than estimated, and trade size is explicitly separated from selling opportunity.
---

# 化工品出口目标市场筛选（看产品适合卖到哪些国家）

**一句话**：先把产品钉成 HS 编码，再拿**真实的双边贸易数据**筛国家，然后用**可核验的关税与产业事实**判断"值不值得去"，最后产出可交付的 HTML 报告与 Excel 工作簿。

**这个 Skill 要抵抗的最大诱惑**：把"进口规模大 / 增长快"直接写成"存在销售机会"。本 Skill 强制把**贸易统计事实**与**初步判断**分开，并明确"进口大"只是**必要不充分**条件。

---

## 0. 输入清单（先问清，缺了就问，不要猜）

| 项 | 必需 | 说明与示例 |
|---|---|---|
| 产品名称 | ✅ | 中文 + 英文规范名。例：重质纯碱 / Sodium Carbonate (Dense) |
| CAS 号 | 建议 | 497-19-8。CAS **不能**直接映射 HS，只用于锁定物质名称 |
| 规格/等级 | 建议 | 纯度、粒径、堆积密度、用途级（工业级/食品级/电池级）。**决定是否需要拆分编码** |
| 供应优势 | 可选 | 价格 / 产能 / 认证 / 规格。只影响后续"能不能打"，**不改变贸易事实** |
| 目标年份区间 | 建议 | 默认近 5 年（最新完整年 + 前 4 年） |
| 目标区域 | 可选 | 例：只要东南亚、或排除欧盟 |
| 需排除国家 | 可选 | 例：已有独家代理的国家 |
| 已覆盖市场 | 可选 | 用于区分"新市场"与"守份额" |

> 如果用户只给"想做外贸销售"这类模糊需求，**必须先问产品**，不能拿示例产品硬套。

---

## 1. 第一步：确定产品身份与 HS 编码（**必须先做，不能跳过**）

```bash
python scripts/hs_match.py "重质纯碱" --cas 497-19-8 --spec "dense >=99.2%"
```

输出候选编码 + 置信度 + 匹配依据 + 口径提示。**然后必须让用户确认**这三件事：

1. 该 6 位编码是否覆盖产品？（规格不同可能落入不同子目）
2. 是否要纳入相邻编码？（混合物/副产品可能入 3824、过碳酸钠入 2836.99 等）
3. 重点国家是否有更细的本地编码需要单独取数？

**口径纪律**（写进报告，不是内部备注）：
- 跨国比较**只在 6 位层**做；本地 8/10 位编码各国不同，**不得跨编码相加**。
- 同一 6 位编码内部可能仍混杂不同规格（如纯碱的**重质/轻质**在 2836.20 下不区分）——**这是必须声明的核心局限**，不可假装数据粒度足够。
- 关税**不能**用 6 位税率代替；必须取本国 8/10 位行级税率。

参考：`references/hs_subheadings.json`（184 个化工子目）、`references/methodology.md`

---

## 2. 第二步：取真实贸易数据

```bash
python scripts/fetch_trade.py --hs 283620 --years 2019-2025 --partners --top 15 --out trade_data
```

- 数据源：**UN Comtrade** 公开预览 API（无需 key，有速率限制）。进口口径 `flowCode=M`，金额 CIF，数量净重 kg。
- 取三类：①报告国自全球进口（`partnerCode=0`）②报告国自中国进口（`partnerCode=156`）③主要进口国的来源国明细（省略 partnerCode）。
- 原产国可换：`--origin 699`（印度）；出口口径：`--flow X`。
- **全部原始响应落盘缓存**（`trade_data/raw/`），重跑免费、可复核。
- 被限流（429 / 403 Quota Exceeded）会自动退避重试；**取不到的年份留空，绝不插值、绝不以 0 填充**。

> 若 Comtrade 不可达，退回 **WITS / Trade Map / 各国海关**，并在 `fetch_meta.json` 与报告中标明实际来源与覆盖差异——**不要混用不同来源拼成一条时间序列而不声明**。

---

## 3. 第三步：核验关税（**最容易造假的一步，必须诚实**）

优先级：
1. **美国**：USITC HTS REST API —— `https://hts.usitc.gov/reststop/search?keyword=<hs>`
   返回 General / Special / Column 2 三档税率。
2. **欧盟**：EU TARIC（需会话流程，`measures.jsp` → 解析 `measures_details.jsp` 的 `Sid` 参数）
   `Area=<原产国ISO2>`、`SimDate=<yyyy-mm-dd>`、`Taric=<10位编码>`。同时看 **反倾销/反补贴** 与 **进出口管制措施**。
3. **其他国家**：`trade.gov/country-commercial-guides/<country>-import-tariffs` 提供**税制结构与税种**，但**通常没有行级税率**。
4. 其他备选：WTO Tariff & Trade Data、MacMap、各国海关官网（部分需 JS/账号）。

**规则（写死在配置里）**：
- 只有**本次会话真的从官方系统取到行级税率**，才可标 `status: "verified"` 并写出 `mfn` 数值。
- 否则 `status: "gap"` + `mfn: null`，在报告与 Excel 中显示"待核验（黄色）"。
- **绝不**用"该国税负偏高""平均 MFN 8%"之类的国家平均值冒充产品税率。
- 贸易救济（反倾销/反补贴/保障措施）**单独核查**并写明结论；"未发现"也要写"未发现"，而不是直接留空。

详见 `references/tariff_verification.md`

---

## 4. 第四步：产业与下游信息（帮助解释贸易结构，不替代事实）

核查方向（每条都要能落到一个**真实来源**）：
- **下游应用结构**（玻璃/洗涤剂/化学品…占比）
- **本地产能与供给行为**（是净出口国还是净进口国）→ 决定"它是客户还是对手"
- **在建/投产项目**（玻璃产线、洗涤剂厂）→ 需求的增量来源
- **贸易政策与非关税措施**（许可、标准、反倾销、原产地规则）

示例可用来源：USGS Mineral Commodity Summaries（矿产与基础化工）、UNIDO、各国统计局、行业协会。
**"行业常识"不算来源**——要么给出处，要么删掉这句。

参考 `references/industry_evidence.md`

---

## 5. 第五步：生成交付物

1) 复制 `templates/analysis_config.template.json`，填入产品身份、关税（带核验状态）、产业信息、判断。

2) 生成：

```bash
python scripts/build_outputs.py --data trade_data --config my_product.json --out out
```

产出：
- **HTML 交互报告**（自包含，离线可用）：全球地图（额/份额/CAGR 切换）、筛选、国家排名表、点击国家展开历年结构+竞争来源国+关税、趋势图、来源国堆叠图、目标市场清单。
- **Excel 工作簿**（9 页签）：说明口径 / 国家比较（**带活公式**）/ 历年明细 / 竞争来源国 / 全球趋势 / 关税与限制 / 下游产业 / **数据缺口** / 来源清单。

3) **自检**（不通过不算完成）：
```bash
python scripts/validate_outputs.py --data trade_data --config my_product.json --out out
```
检查：口径完整性、缺失年份是否被误填、份额分母是否正确、是否存在"已核验但无税率"或"有税率却未核验"的矛盾、报告是否引用了不存在的来源。

模板：`templates/report_template.html`、`templates/analysis_config.template.json`
资产：`assets/echarts.min.js`、`assets/world.json`（内置，报告**不依赖外网**）

---

## 6. 结论该怎么写（这是本 Skill 的核心价值）

必须**同时**给出三块，缺一不可：

**A. 结构性事实**（Fact）
> 例：全球纯碱出口由美国与土耳其两个天然碱国主导；在墨西哥(美国100%)、智利(97%)、印尼(70%)等最大市场中国份额≈0。

**B. 值得研究的市场 + 每个国家的具体依据**（Judgment，须标注为初步判断）
每个国家至少写清**两个可核实的理由**，例如：
- "中国已有 X% 份额且 5 年 CAGR +Y%"（已有接受度 + 在增长）
- "最大来源国占 Z%，高度集中"（替代空间）
- "曾有单年 A 万美元对华采购"（真实成交痕迹）
- "关税已核验且未发现 AD/CVD"（进入条件明确）

**C. 反向证据**（Counter-evidence）
> 例：中国整体份额从 7.4% 降到 5.6%；某国 2022 年自华进口 8,180 万美元、2024 年降到 70 万美元 → 属价格驱动的机会型供应，不能按高点外推。

**禁止表述**：
- ❌ "该国进口 3 亿美元，所以我们有机会"（把规模当机会）
- ❌ "预计可实现 X 吨销量 / 目标客户有 N 家"（编造需求）
- ❌ 把 2025 年部分年份数据当作完整年度结论而不声明

**允许表述**：
- ✅ "基于 2024 年完整年度数据，该国进口 X，中国占 Y%，最大来源国 Z%；**值得进一步核实**本地玻璃产能与买方结构"

---

## 7. 常见坑（按踩坑频率排序）

| 坑 | 后果 | 正确做法 |
|---|---|---|
| Comtrade 全量 partner 用 `partnerCode=all` | HTTP 400 | 省略该参数；或按 `reporterCode` 逐个取 |
| 报告国覆盖逐年减少（169→119） | 全球合计被误判为"萎缩" | 必写覆盖度；跨年比较需谨慎；决策用完整年 |
| 2025 是部分年度 | 增长率失真 | 标注"最新完整年度"，或改用 2024 |
| 净重缺失时用 qty 顶替 | 单价错 | 显示 n/a，不估算 |
| 用国家平均关税冒充产品税率 | 报价错误 | 只认行级税率；否则标缺口 |
| 用 6 位编码谈关税优惠 | 错失 FTA/原产地规则 | 优惠税率按本国 8/10 位 + 原产地规则核验 |
| 把转口港（荷兰/比利时/新加坡）的进口额当作本国消费 | 高估市场 | 标注"港口中转效应" |
| 竞争来源国只取"中国 vs 全世界" | 看不出谁是真对手 | 必看来源国明细（partner breakdown） |

---

## 8. 文件结构

```
chemical-export-market-finder/
├── SKILL.md                       本文件
├── scripts/
│   ├── hs_match.py                HS 编码候选匹配（第一步）
│   ├── fetch_trade.py             UN Comtrade 取数（含缓存/退避）
│   ├── build_outputs.py           生成 HTML + Excel
│   └── validate_outputs.py        交付前自检
├── references/
│   ├── hs_subheadings.json        184 个化工 HS-6 参考（含中英文与关键词）
│   ├── methodology.md             统计口径、算法、口径冲突处理
│   ├── tariff_verification.md     关税核验：哪个源、怎么取、怎么标状态
│   └── industry_evidence.md       产业信息核查清单与可用来源
├── templates/
│   ├── report_template.html       交互报告模板（echarts + 世界地图）
│   └── analysis_config.template.json
├── assets/
│   ├── echarts.min.js             本地化，报告离线可用
│   └── world.json                 世界地图 GeoJSON
└── examples/
    ├── soda-ash/                  完整案例：重质纯碱（真实数据）
    └── README.md                  输入输出样例说明
```

## 9. 兼容性

- **纯 Python 3.9+**，仅需 `xlsxwriter`（生成 Excel 时）。无 pandas/numpy 依赖。
- **跨 Agent**（ChemClaw / WorkBuddy / Codex / Claude Code）：所有脚本是标准 CLI，`--json` 可机器读取（`hs_match.py`），不依赖任何专有运行时。
- **Windows / macOS / Linux** 均可；`build_outputs.py` 会调用 `node --check` 做 JS 语法自检（无 node 时自动跳过，不影响生成）。
- 报告**完全自包含**（echarts 与地图已内联），可邮件发送、离线打开。

## 10. 快速开始（3 条命令）

```bash
python scripts/hs_match.py "你的产品" --cas <CAS>          # 1. 确认编码
python scripts/fetch_trade.py --hs <6位> --years 2020-2025 --partners   # 2. 取数
python scripts/build_outputs.py --data trade_data --config my.json --out out   # 3. 出报告
```
