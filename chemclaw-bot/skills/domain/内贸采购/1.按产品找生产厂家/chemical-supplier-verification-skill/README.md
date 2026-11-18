# Chemical Supplier Verification Skill

一个可移植的“按化工品找真实生产厂家”skill 包。它不是某个产品的固定报告，而是一套**研究协议 + 数据模型 + 生成器 + 示例**，换产品时只换 `project.json`。

## 适合谁

- 内贸采购/供应链：按产品找生产厂家、做供应商初筛；
- 化工销售/市场：快速摸清某产品的生产商版图；
- 咨询/研究：需要可追溯的产能、规格、证据链；
- 任何 agent：ChemClaw、WorkBuddy、Codex、Claude/其他支持 Markdown + Python 的环境。

## 产出

```text
output/
  {产品}_生产厂家核验池_{收货地}_{YYYYMM}.xlsx
  {产品}_生产厂家核验池_{收货地}_{YYYYMM}.html
```

Excel 至少 10 个工作表；HTML 是单文件，无外部依赖，可筛选、排序、看证据、做准入尽调、对比最多 3 家。

## 30 秒上手

```bash
pip install -r requirements.txt
python scripts/run_all.py examples/soda-ash/project.json --outdir examples/soda-ash/output
```

生成 `examples/soda-ash/output/` 下的 Excel + HTML。

## 详细步骤

先读 `references/00-quickstart.md`。

### 1. 环境

```bash
python --version        # 3.10+
pip install -r requirements.txt
```

只有 Excel 生成需要 `openpyxl`；HTML 生成只用 Python 标准库。

### 2. 跑示例

```bash
python scripts/validate_project.py examples/soda-ash/project.json
python scripts/run_all.py examples/soda-ash/project.json --outdir examples/soda-ash/output
```

打开 `examples/soda-ash/output/` 下的 `.xlsx` 和 `.html`。

### 3. 做新产品

1. 复制 `examples/soda-ash/project.json` 为 `my-project.json`；
2. 按 `references/03-data-model.md` 修改 `meta`、`rfq`、`specs`、`companies`、`sources`；
3. 运行：

```bash
python scripts/validate_project.py my-project.json
python scripts/run_all.py my-project.json --outdir output
```

## 目录

```text
SKILL.md                         # agent 主入口：工作流、规则、交付话术
references/
  00-quickstart.md               # 从需求到两份附件的最短路径
  01-research-protocol.md        # 怎么搜、怎么拆集团/基地/销售主体
  02-evidence-grading.md         # A/B/C/D 证据分级与判定
  03-data-model.md               # project.json 字段说明
  04-scoring.md                  # 权重、产品预设、分级
  05-output-spec.md              # Excel/HTML 的详细结构
  06-product-adaptation.md       # 大宗/危化/精细/液体/气体怎么适配
  07-qa-checklist.md             # 交付前 25 项检查
  08-agent-integration.md        # ChemClaw / WorkBuddy / Codex 集成
templates/
  project.schema.json            # JSON Schema
  project.example.json           # 最小可跑骨架
  report.html                    # HTML 模板
  style.css                      # 样式
  app.js                         # 交互
scripts/
  validate_project.py            # 数据校验
  build_excel.py                 # Excel 生成
  build_html.py                  # HTML 生成
  run_all.py                     # 校验 + 生成
examples/
  soda-ash/                      # 完整真实示例：重质纯碱
  caustic-soda-structure/        # 结构示例：32% 液碱（匿名占位）
```

## 跨 agent 使用

### Codex

把整个目录放进仓库，或在 `AGENTS.md` 增加：

```md
当任务涉及“按化工品找生产厂家/供应商核验/区分贸易商”时，先读
`chemical-supplier-verification-skill/SKILL.md`，并按其中工作流执行；
数据写入 `project.json`，再用 `scripts/run_all.py` 生成 Excel + HTML。
```

### ChemClaw / WorkBuddy

上传/挂载整个目录，先让 agent 读取 `SKILL.md`。如果平台只支持单文件，至少上传：

- `SKILL.md`
- `references/03-data-model.md`
- `templates/project.schema.json`
- `scripts/validate_project.py`、`build_excel.py`、`build_html.py`

生成脚本在本机 Python 跑；agent 只负责研究与填 JSON。

### 其他 agent

把 `SKILL.md` 作为系统提示/任务说明，把 `templates/project.schema.json` 作为输出约束。任何能读写文件、运行 Python 的 agent 都可以用。

## 设计原则

1. **生产身份是一等公民**：没有装置/产能/产量/环评/政府项目/官网产品页，不进入厂家池。
2. **经营范围不是证据**：营业执照、店铺 SKU、代理宣称只做 D 级线索。
3. **每个数字有来源**：产能、产量、员工、地址、规格都要 `source_id`。
4. **标准不等于批次合格**：没有 COA 不写“符合”。
5. **缺口必须变成动作**：RFQ 追问、样品检测、现场审核、物流比价。
6. **输出可复现**：`project.json` 是唯一事实源，Excel/HTML 都由它生成。

## 例子说明

### `examples/soda-ash`

完整真实示例：光伏玻璃用重质纯碱，2,000 吨/月，收货地苏州。

- 17 家生产厂家、22 个基地、3,030 万吨样本产能；
- 5 个贸易/流通样本单独列出；
- 53 条证据、49 个来源；
- 结论：中盐化工、博源化工、山东海化、三友化工、华昌化工为优先谈判；金晶科技规格最贴近但外销可得性低。

### `examples/caustic-soda-structure`

结构示例：32% 液碱。**公司名与数字是匿名占位，只用于演示“换产品/换规格/换评分”时 JSON 怎么改，不可用于采购。**

它演示：

- 液体产品用“槽车/ISO 罐”而不是吨袋；
- 规格从“总碱量/Fe₂O₃/粒度”换成“NaOH 浓度/碳酸钠/氯化钠/Fe₂O₃”；
- 距离权重要提高，危化品合规作为 gate。

## 常见问题

**Q：没有 openpyxl 怎么办？**
A：先 `pip install -r requirements.txt`。如果目标机器不能装包，HTML 仍可生成；Excel 可先用 CSV 交付，但本 skill 的标准交付是 xlsx。

**Q：数据找不到怎么办？**
A：写“未披露/待核”，并在 `gaps` 里写清影响与复核方法。不要用行业平均值、猜测值或经营范围填充。

**Q：能不能只用 HTML 不用 Excel？**
A：不建议。Excel 是底稿，HTML 是展示；至少两份都出。

**Q：能不能直接拿示例数据改公司名？**
A：不能。示例数据有明确截止日和口径；换产品必须重新核验来源，不能改名字当新报告。

## License / 使用边界

本包是研究方法与模板，不构成采购决策建议。产能、规格、价格、合规信息均需以企业最新文件和现场审核为准。
