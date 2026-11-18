---
name: customer-qualification-card
description: 化工品内贸销售「客户值不值得跟」多维判断卡。给定一个化工产品（纯碱、烧碱、尿素、甲醇、钛白粉等任意品）和候选客户，产出可调权重的七维事实卡：Excel（7 表）+ 自包含 HTML，每维给出事实、评级、可追溯依据，并附最强信号、主要疑点、待确认清单。用于客户准入、销售资源排序、拜访前准备。
---

# 客户多维判断卡（化工品内贸销售）

## 这个 skill 解决什么

内贸销售最贵的是时间。这份 skill 不回答"这家客户好不好"，而是回答三件事：

1. **先跟谁**（P1–P4 优先级）
2. **为什么**（七个维度的事实与依据）
3. **还缺什么**（打单前必须向客户确认的问题）

产物是 **Excel 工作簿 + 自包含 HTML 判断卡**，两份必须同时交付。核心原则：**永远展示事实，不输出单一黑盒总分**。

## 何时触发

- "我卖 XX 化工品，帮我判断 A/B/C 这家客户值不值得跟"
- "找几家 XX 的下游客户，排个优先级"
- "客户准入 / 客户分级 / 下周先拜访谁"
- 拜访前准备、招标前评估、大客户年度复盘

## 输出契约（硬性）

| 产物 | 说明 | 命名 |
|---|---|---|
| `data.json` | 唯一事实源（所有数字只写这一份） | `{product}-{segment}-{YYYY-MM}.json` |
| `*.xlsx` | 7 个工作表，见下 | 同名 `.xlsx` |
| `*.html` | 自包含交互卡，双击可开 | 同名 `.html` |

Excel 七表：客户判断总览 / 七维判断明细 / 权重与排序（公式联动）/ 待确认清单 / 数据来源 / 市场背景 / 阅读说明。

**交付前必须**运行 `verify_card.py` 并得到 `RESULT: PASS`。任一附件缺失即视为未完成。

## 七维定义

| 键 | 维度 | 看什么 | 方向 |
|---|---|---|---|
| match | 产品匹配 | 用途是否对口、采购体系是否开放、能否投标进入 | 越高越好 |
| demand | 需求规模 | 年采购量/采购额（按产能×单耗估算） | 越高越好 |
| capacity | 真实产能 | 窑炉是否在产、开工率、改造/冷修降量 | 越高越好 |
| scale | 企业规模 | 营收/资产/信用与付款能力 | 越高越好 |
| region | 距离/区域 | 运距、运费占货值比例、竞争半径 | 越高越好 |
| chance | 近期机会 | 6–12 个月内的投产、招标、扩建窗口 | 越高越好 |
| risk | 不确定性 | 资信、账期、锁价与需求波动（**分数越低风险越大**） | 反向 |

## 工作流

### 第 0 步：确认输入（写进 meta）
问清：产品与规格（重碱/轻碱、片碱/液碱、品位）、你的位置与可供量、最低订单量、重点区域、判断时点（`as_of`）。客户池没有就让 agent 自己找（第 2 步）。

### 第 1 步：下游地图
查 `references/industry-map.md`，得到该化工品的下游行业、检索关键词、需求估算口径。若表里没有你的产品，按同样格式补一行：产品 → 主要下游（按用量排序）→ 关键词 → 单耗口径。

### 第 2 步：候选池（3–6 家）
- 优先选上市公司（年报/公告可查），再补 1–2 家中型民企增加真实感；
- **必做排除**：客户是否自产该原料、是否集团内配套（见 `references/gotchas.md` 第 1 条）。自产者不是客户；
- 每家写一句话"为什么入选"。

### 第 3 步：逐维取证
按 `references/evidence-playbook.md` 的检索模板逐维找证据：
- 每个维度至少 1 条**可点开**的公开链接；
- 事实 ≤120 字（写结论+关键数字，不堆原文）；
- 估算必须标"估/待核"，查不到就写"无公开数据/待核实"并进疑点；
- 严禁无来源的断言。

### 第 4 步：评分与评级
按 `references/scoring-rubric.md`。分数是"事实→排序"的映射，评级只是锚点（高≥75 / 中55–74 / 低<55）。风险维度反向。

### 第 5 步：写 data.json
复制 `examples/soda-ash-glass-2026-10/data.json` 改内容最省事。字段契约见下节。

### 第 6 步：生成附件
```bash
python scripts/build_workbook.py data.json out.xlsx
python scripts/build_card.py data.json out.html
```

### 第 7 步：校验与交付
```bash
python scripts/verify_card.py data.json --xlsx out.xlsx --html out.html
```
必须 PASS。正文交付时给四行：①先跟谁 ②最强信号 ③主要疑点 ④要客户确认什么。

## data.json 契约

```jsonc
{
  "meta": {
    "title": "XX客户多维判断卡",
    "product": "产品+规格",
    "seller": "你的位置 · 角色 · 可供量",
    "as_of": "2026-10",
    "thresholds": {"high": 75, "mid": 55},
    "method_line": "事实优先，评级只做锚点",
    "estimate_note": "估算口径一句话（显示在 HTML 页脚）",
    "estimate_bullets": ["Excel 阅读说明里的口径条目"]
  },
  "dimensions": [            // 固定 7 个，可用 data 覆盖 name/hint/rubric
    {"key":"match","name":"产品匹配","hint":"…","rubric":"高：…；中：…；低：…"}
  ],
  "market": [                // 5–9 条行情，先定买方/卖方市场
    {"metric":"…","value":"…","when":"2026-10-15","source":"…","url":"https://…"}
  ],
  "presets": [               // 权重预设，至少一个 even
    {"key":"even","name":"均衡","weights":{"match":1,"demand":1,"capacity":1,"scale":1,"region":1,"chance":1,"risk":1}}
  ],
  "customers": [{
    "id":"cust1","name":"…","code":"601636.SH",
    "location":"…","distance":"…km","demand":"≈X 万吨/年（估）","spend":"≈Y 亿元/年",
    "tags":"业务标签","priority":"P1","priority_note":"本周优先","action":"跟进打法",
    "best":"最强积极信号（一句话）",
    "doubts":["主要疑点"],
    "asks":[{"q":"问题","dim":"影响哪个维度","why":"为什么重要","who":"找谁问"}],
    "dims": {
      "match": {"level":"高","score":90,"basis":"核实|估算","fact":"…","evidence":[{"label":"…","url":"https://…","date":"2026-04-18"}]}
    },
    "sources":[{"type":"年报","label":"…","url":"https://…","date":"2026-04-18"}]
  }]
}
```

## 评分规则

- 排序分 = Σ(维度分 × 权重) / Σ权重，只用于**排序**；
- 默认预设：均衡 / 规模更重要 / 近期机会更重要 / 距离更重要（可在 `presets` 增删）；
- 权重可被销售现场修改（HTML 滑杆；Excel 黄色格），但**卡上的事实与评级不随权重变化**；
- 风险维度方向相反：分数 40 = 风险高，不是"匹配度低"。

## 质量门槛（verify_card.py 会查）

- 每客户 7 维齐全；每维 fact ≥8 字、evidence ≥1 条且 URL 以 http 开头；
- 评级与分值基本一致（风险维度豁免）；
- 每客户 doubts ≥1、asks ≥2、sources ≥4（建议）；
- Excel 7 表齐全、排序分与排名有缓存值（打开即显示）；
- HTML 已注入数据、无 `__CARD_DATA__` 占位符。

## 禁忌

1. 不编造链接、日期、数字；查不到就写"待核实"。
2. 不把估算写成事实；需求/运费/距离必须标注。
3. 不输出单一总分作为结论；排序分只是"先跟谁"的参考。
4. 不把**自产该原料**的企业当客户（自己产碱的玻璃集团不是纯碱客户）。
5. 不把 2023 年的产能当 2026 年的产能——每个数字都要带年份/时点。
6. 不省略"谁在供"：客户现有供应商结构决定你有没有位置。

## 文件地图

```
scripts/build_workbook.py   JSON → Excel（openpyxl，公式带缓存值）
scripts/build_card.py       JSON → HTML（注入模板，自包含）
scripts/verify_card.py      交付前校验（数据 + Excel + HTML）
templates/card.template.html  交互卡模板（数据驱动，勿写死行业）
references/industry-map.md    化工品→下游地图（含单耗口径）
references/evidence-playbook.md  七维证据来源与检索模板
references/scoring-rubric.md  评分细则、估算公式、权重语义
references/gotchas.md         12 个判断陷阱
examples/soda-ash-glass-2026-10/  完整样例（纯碱，4 家玻璃客户）
```

## 参考

- 完整样例：`examples/soda-ash-glass-2026-10/`（data.json + xlsx + html）
- 均衡权重下样例排序：信义玻璃 75.4 > 旗滨集团 73.6 > 安彩高科 68.6 > 利虎玻璃 64.3；把"距离"权重拉到最高后，安彩高科 72.7 跃居第一——**排序会变，事实不变**。
