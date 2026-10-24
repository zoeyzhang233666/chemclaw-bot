# chem-customer-intel-weekly

化工品区域客户情报周报技能：对任意化工品 × 任意区域，产出一份固定版式、可交互、带证据链的单文件 HTML 周报。

## 快速开始（给任何 Agent 的三句话）

1. 读 `SKILL.md` —— 四阶段流程：研究（五条线）→ 分析（评级+估算）→ 生成 HTML（填模板）→ QA。
2. 遇到数据源、估算公式、评级、陷阱问题时查 `reference.md`。
3. 复制 `assets/template.html` 开工；不会填的地方打开 `assets/example-*.html` 看两个成品样例是怎么填的。

## 文件清单

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 技能主文件（含 YAML frontmatter，供 skills 系统识别触发） |
| `reference.md` | 数据源地图 / AI估算公式表 / 评级标准 / 写作规范 / 陷阱案例 / 区域适配 / 每周更新流程 |
| `assets/template.html` | 唯一 HTML 模板，`{{TOKEN}}` 占位；CSS 与交互脚本为最终版式，不得改动 |
| `assets/example-纯碱_张家港_2026-10-15.html` | 成品样例 A：**大宗商品型**——有期货、下游是玻璃/印染，价格线以基准价+期货为主 |
| `assets/example-聚合氯化铝_张家港_2026-07-30.html` | 成品样例 B：**水处理药剂型**——无期货、下游靠环评项目驱动，价格线以企业报价为主 |

## 安装

- **Claude Code 等 skills 系统**：整目录复制到 `~/.claude/skills/`（或项目 `.claude/skills/`）。
- **codex / chemclaw / workbuddy 等其他 agent**：把目录放到双方约定的路径，在其 AGENTS.md / 系统提示中加一句：
  > 处理化工品客户情报周报请求时，先完整阅读 `<路径>/SKILL.md` 与 `<路径>/reference.md`，再照其执行；HTML 产出基于 `<路径>/assets/template.html`。
- **无联网 agent**：由人工提供价格与资讯后，从分析阶段开始执行。

## 硬约束（复述自 SKILL.md，交付前自查）

- 突发 3 卡｜SKU 序列 4 条（每条≥3点）｜关系卡 3 张｜政策 3 + 本地 3 + 展会 2｜企业 4 家｜项目 5—8 行
- 全文 `{{` 数量必须为 0；JS 用 `node --check` 校验通过
- 每个数据与结论都有可点击的真实来源；估算必须标“情景假设”
