# customer-entry-point-scan · 化工品内贸销售「客户切入点扫描」技能包

一个**产品无关、客户无关、跨 agent 可用**的技能：当销售要开发某家下游企业、销售某种化工品时，按本技能扫描该客户最近 3–6 个月的事件（扩产/点火/冷修/招标/业绩/资金/行业与上游市场），产出 3–5 张可操作的"事件卡"，并交付 **Excel + HTML** 两个附件。

核心理念：**研究结论 = 一份 cards.json；Excel 和 HTML 都是它的渲染产物。** 换任何化工品（纯碱→玻璃厂、甲醇→醋酸厂、钛白粉→涂料厂…）只换数据，不换结构。

## 包结构

```
customer-entry-point-scan/
├── SKILL.md                        # ★ 主指令：任何 agent 从这里开始读
├── README.md                       # 本文件：安装与跨平台用法
├── prompts/
│   └── scan-prompt.md              # 轻量用法：可直接粘贴的提示词（无文件能力的 agent 用）
├── references/
│   ├── methodology.md              # 研究方法论：事件分类学、检索源清单、关键词模板、优先级评分
│   ├── output-schema.md            # 结果结构规范：cards.json 字段 / Excel 六表 / HTML 交互
│   └── quality-and-inference.md    # 证据分级、推断标注规则、常见错误、交付前自检清单
├── templates/
│   ├── scan_data.schema.json       # cards.json 的 JSON Schema
│   ├── build_deliverables.py       # ★ 一键生成附件：cards.json → .xlsx + .html
│   └── report.template.html        # 交互式 HTML 模板（单占位符 __SCAN_DATA_JSON__）
└── examples/
    ├── example-soda-ash-flat-glass/    # 完整实例：纯碱 → 福莱特玻璃（含成品 xlsx/html）
    └── example-template-skeleton/      # 空白骨架：换掉占位符即用于任何化工品
```

## 快速开始（任何有文件执行能力的 agent）

```bash
# 1. agent 按 SKILL.md 完成研究后，填写数据文件 cards.json
# 2. 一键生成两个附件（依赖仅 Python3 + openpyxl）：
python templates/build_deliverables.py cards.json -o 输出目录 -n 纯碱客户切入点扫描_福莱特_2026-10-15
#    → 生成 .xlsx 和 .html
```

研究阶段不需要任何特殊工具——普通的联网搜索即可；关键是要**遵守 SKILL.md 的七步流程与证据/推断规则**。

## 各平台接入方法

| 平台 | 接入方式 |
|---|---|
| **Claude Code / Claude 系** | 整个文件夹复制到 `~/.claude/skills/customer-entry-point-scan/`；SKILL.md 的 YAML frontmatter（name/description）即为技能声明，会按 description 自动触发 |
| **DSH（DeepSeek Harness）** | 放入技能目录即可被技能目录扫描；或直接让 Bot 读 `SKILL.md` 后按其执行 |
| **Codex（OpenAI）** | 无原生技能机制：在仓库的 `AGENTS.md` 加一行——"当用户要求客户切入点扫描/开发某化工客户时，先读 `customer-entry-point-scan/SKILL.md` 并严格遵循"；或把 `prompts/scan-prompt.md` 内容作为任务提示词 |
| **workbuddy / chemclaw 等自研 agent** | 支持技能目录的放入其技能目录（frontmatter 通用）；不支持就把 `SKILL.md` + 三个 `references/*.md` 作为该类任务的系统指令/任务上下文注入 |
| **纯对话（无文件能力）** | 只带 `SKILL.md` + `prompts/scan-prompt.md`，让 agent 直接在回复里输出事件卡与六张表的内容（跳过附件生成），用户自行粘贴到 Excel |

## 设计要点（为什么这样移植性强）

1. **思路与结构分离**：`SKILL.md + references/` 只固化研究思路和结果结构，不含任何纯碱专属内容；换产品只改 cards.json。
2. **数据与渲染分离**：研究产出物是标准 JSON（有 Schema 校验），Excel/HTML 由模板渲染，三个 agent 各自研究、共用同一套模板，产物完全一致。
3. **生成器零依赖**：`build_deliverables.py` 只依赖 openpyxl，Windows/macOS/Linux 通用；HTML 模板零外部资源、离线可开。
4. **推断标注是一等公民**：证据分级（L1一手→L4弱来源）、五类推断类型学、交付前 10 条自检，全部写入规则文件，避免不同 agent 产出质量漂移。

## 常见问题

- **换化工品要改什么？** 只改 cards.json 的数据（产品、单耗锚点、证据、卡片），不改模板与脚本。单耗数据按 `references/methodology.md` §3 重新检索。
- **没有 Python 环境怎么办？** 让 agent 按 `references/output-schema.md` 手工构建：Excel 六表照列名写、HTML 用模板把 `__SCAN_DATA_JSON__` 替换为 JSON 文本。
- **如何校验我的 cards.json？** 对照 `templates/scan_data.schema.json`；`build_deliverables.py` 运行时也会做必需字段与证据引用完整性校验，缺什么会明确报错。
