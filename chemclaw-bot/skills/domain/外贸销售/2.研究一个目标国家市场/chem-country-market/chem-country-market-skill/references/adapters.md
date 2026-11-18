# 在各 Agent 平台里调用本技能

本技能是**纯文件 + Python 标准脚本**，没有任何专有依赖。唯一的可选依赖是 `openpyxl`（Excel）
和 `websocket-client`（浏览器渲染校验），两者缺失时脚本会明确报错或自动降级。

```
chem-country-market/
├─ SKILL.md            ← 各平台的技能入口
├─ references/         ← 渐进式披露的细节文档
├─ scripts/            ← 可执行流水线
└─ examples/           ← 完整案例（可直接复用）
```

---

## 1. DeepSeek Harness / DSH（含 ChemClaw 场景目录）

场景技能放在：

```
../../../../..\外贸销售\2.研究一个目标国家市场\
```

DSH 会把该目录下的 `SKILL.md` 的 front-matter（`name` / `description`）作为技能索引，
正文按需加载。调用方式（自然语言即可）：

> 用 chem-country-market 帮我研究中国重质纯碱出口印度尼西亚市场，窗口 2021–2025。

Agent 的执行顺序：

```bash
python scripts/fetch_trade.py --reporter 360 --product 283620 --years 2021-2025 --exporter 156
python scripts/sync_case.py examples/01-idn-soda-ash/case.json --raw raw/comtrade_360_283620.json
python scripts/validate.py case.json
python scripts/build_all.py case.json --render
```

**注意**
- Python 解释器在每个平台上不同；DSH 里优先用会话自带的运行时，
  或任意装了 `openpyxl` 的 3.9+ Python（Windows 上设置 `PYTHONIOENCODING=utf-8` 避免中文乱码）。
- 全部命令都用**绝对路径**，避免工作目录不同导致的相对路径失败。
- `--render` 会启动本机 Edge/Chrome 无头实例截图；没有浏览器时这一步会打印“跳过”，不影响交付。

---

## 2. Claude Code / Claude Desktop（skills 目录）

```
~/.claude/skills/chem-country-market/       # macOS / Linux
%USERPROFILE%\.claude\skills\chem-country-market\   # Windows
```

放置后重启会话，技能以 `chem-country-market` 被索引。Claude Code 中可直接：

```
> 用 chem-country-market 技能，研究甲醇出口印度的市场
```

`SKILL.md` 的 `description` 里已经写了中英文触发词，不点名技能也能命中。

---

## 3. OpenAI Codex / Codex CLI

Codex 读取仓库根目录的 `AGENTS.md` 或 `.codex/` 配置。两种接法：

**(a) 仓库即技能**：把本目录作为仓库根，在 `AGENTS.md` 写一句：

```markdown
技能入口：SKILL.md（国别市场研究）。修改 case.json 后必须跑
`python scripts/build_all.py case.json --render` 才算完成。
```

**(b) 嵌入现有仓库**：把本目录放到 `skills/chem-country-market/`，
在 `AGENTS.md` 里加一行索引即可。

Codex 在沙箱模式下可能无法访问网络（`fetch_trade.py` 会失败），
此时让用户提前把 `raw/comtrade_*.json` 放进 `raw/`，从 `sync_case.py` 开始跑。

---

## 4. WorkBuddy / 其它"工具调用型"Agent

这类平台通常要求一个**单一入口**。推荐暴露三个工具：

| 工具名 | 映射到 | 说明 |
|---|---|---|
| `country_market_research_build` | `scripts/build_all.py <case.json> --render` | 主入口，一次产出 HTML+Excel |
| `country_market_trade_fetch` | `scripts/fetch_trade.py --reporter … --product …` | 取海关数据，返回 raw 路径 |
| `country_market_case_validate` | `scripts/validate.py <case.json>` | 结构/证据校验，返回 errors/warnings |

工具定义（JSON Schema 摘要）：

```json
{
  "name": "country_market_research_build",
  "description": "从 case.json 生成国别市场研究报告（HTML+Excel），并做静态与渲染校验",
  "parameters": {
    "type": "object",
    "properties": {
      "case_path": {"type": "string", "description": "case.json 绝对路径"},
      "render": {"type": "boolean", "default": true}
    },
    "required": ["case_path"]
  }
}
```

调用约定：
- 成功 stdout 最后一段固定是 `结果：全部通过，可以交付`，失败是 `结果：有步骤失败…`
- 退出码 0 = 可交付，非 0 = 不可交付（工具层可直接用退出码判定）

---

## 5. 与其它技能的交接

报告第 5 节的两个按钮是**跨技能跳转**的 UI 实现，数据来自 `common.nco_report_links(case)`：

```python
{
  "national_market_handoff":  {  # → 找海外候选买家 (b2b-lead-sourcing)
      "product": "...", "hs_code": "...", "country": "...",
      "downstream_segments": [...], "known_buyers": [...], "gaps": [...]
  },
  "export_requirement_handoff": {  # → 查产品出口要求
      "hs_code": "...", "destination": "...",
      "verified_policy": [...], "unverified_policy": [...]
  }
}
```

接收方技能应把 `gaps` / `unverified_policy` 直接作为下一步的工作队列，
而不是重新问用户一遍。

---

## 6. CI / 定时任务接法

```bash
# 每天凌晨用最新 Comtrade 数据刷新（前提：年份数据已更新）
python scripts/fetch_trade.py --reporter 360 --product 283620 --years 2021-2026 --exporter 156
python scripts/sync_case.py case.json --raw raw/comtrade_360_283620.json
python scripts/build_all.py case.json          # CI 里不加 --render（无浏览器）
python scripts/check_html.py out/*.html
```

失败即返回非 0，可直接接 CI 阻断。

---

## 7. 依赖清单

| 依赖 | 必需 | 用途 | 缺失时 |
|---|---|---|---|
| Python 3.9+ | ✅ | 全部脚本 | — |
| `openpyxl` | 生成 Excel 必需 | 写 .xlsx | `build_xlsx.py` 明确报错 |
| `websocket-client` | 可选 | 浏览器渲染校验 | `qa_render.py` 降级为整页截图 |
| Edge / Chrome | 可选 | 渲染校验 | 打印“跳过” |
| 网络 | 取数时需要 | Comtrade API / 网页 | 用已存档的 `raw/*.json` 继续 |
