# 变更记录

## 1.0 — 2026-10-19

首个可移植版本。

### 包含

- `SKILL.md`：工作流、六条硬规则、交付话术；
- `references/`：
  - `00-quickstart.md` 快速上手
  - `01-research-protocol.md` 检索与实体拆分
  - `02-evidence-grading.md` A/B/C/D 证据分级
  - `03-data-model.md` `project.json` 字段
  - `04-scoring.md` 权重、预设、敏感性
  - `05-output-spec.md` Excel/HTML 细目
  - `06-product-adaptation.md` 不同化工品适配
  - `07-qa-checklist.md` 交付前 25+ 项检查
  - `08-agent-integration.md` ChemClaw/WorkBuddy/Codex 集成
- `templates/`：
  - `project.schema.json`（JSON Schema）
  - `project.example.json`（最小可跑示例）
  - `report.html` + `style.css` + `app.js`（HTML 模板）
- `scripts/`：
  - `validate_project.py`（字段/来源/规格覆盖/权重校验）
  - `build_excel.py`（12  sheet Excel）
  - `build_html.py`（单文件 HTML）
  - `run_all.py`（校验 + 出件）
- `examples/`：
  - `soda-ash/` 完整真实示例（17 家 / 22 基地 / 3,030 万吨 / 49 来源）
  - `caustic-soda-structure/` 结构示例（32% 液碱，匿名占位）

### 已知限制

- 距离为直线距离，不含实际运费模型；
- 不抓取实时价格；
- HTML 无 OCR：PDF/图片规格书需先转文本；
- 未内置工商/司法/海关 API；
- 示例 `soda-ash` 的数据截止 2026-10-19，之后的使用需重新核验。

### 兼容性

- Python 3.10+；
- openpyxl 3.1+；
- 无 Node/前端构建依赖；
- 输出 HTML 无外部 CDN。
