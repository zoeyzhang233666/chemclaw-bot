# customer-qualification-card · 安装与移植指南

把「化工品客户值不值得跟」的判断方法，做成任何 agent 都能复用的技能包。
产物固定为 **Excel（7 表）+ HTML（自包含交互卡）**，数据全部来自一份 `data.json`。

---

## 1. 依赖与自检（30 秒）

- Python 3.8+，唯一第三方库：`openpyxl`
- 无需联网、无需 LibreOffice、无需 Office

```bash
pip install openpyxl

# 用自带样例自检（应输出 RESULT: PASS 与 4 行排序）
python scripts/verify_card.py examples/soda-ash-glass-2026-10/data.json \
       --xlsx examples/soda-ash-glass-2026-10/soda-ash-card.xlsx \
       --html examples/soda-ash-glass-2026-10/soda-ash-card.html

# 重新生成一遍看效果
python scripts/build_workbook.py examples/soda-ash-glass-2026-10/data.json /tmp/card.xlsx
python scripts/build_card.py     examples/soda-ash-glass-2026-10/data.json /tmp/card.html
```

Windows 下把 `/tmp/` 换成任意目录即可；中文路径没问题（脚本全程 UTF-8）。

---

## 2. 目录结构

```
customer-qualification-card/
├── SKILL.md                       # 研究手册 + 数据契约（agent 读这个）
├── README.md                      # 本文件：怎么装、怎么接
├── scripts/
│   ├── build_workbook.py          # data.json -> xlsx（公式+缓存值）
│   ├── build_card.py              # data.json -> 自包含 html
│   └── verify_card.py             # 交付前校验（含 Excel/HTML 一致性）
├── templates/card.template.html   # 交互卡模板（数据驱动）
├── references/
│   ├── industry-map.md            # 化工品→下游地图（纯碱/烧碱/尿素/甲醇/钛白粉…）
│   ├── evidence-playbook.md       # 七维证据来源与检索模板
│   ├── scoring-rubric.md          # 评分细则、估算公式、权重语义
│   └── gotchas.md                 # 12 个判断陷阱（自产、长协、账期…）
└── examples/
    ├── soda-ash-glass-2026-10/    # 完整样例：纯碱 4 家玻璃客户
    └── _skeleton/data.json        # 空壳模板（复制即用）
```

---

## 3. 三种接入方式（按你的 agent 支持情况选）

### 方式 A：agent 支持 Agent Skills（SKILL.md 规范）
常见于 Claude Code 及兼容该规范的 agent。把整个目录放进它的 skills 目录，例如：

```bash
# Claude Code（个人级）
mkdir -p ~/.claude/skills
cp -r customer-qualification-card ~/.claude/skills/

# 项目级
mkdir -p .claude/skills
cp -r customer-qualification-card .claude/skills/
```
agent 会根据 `SKILL.md` 的 description 自动在合适时机加载；需要执行代码时用 `python scripts/...`。

### 方式 B：项目内约定（Codex / 任意读 AGENTS.md 的 agent）
把目录放进仓库（建议 `tools/customer-qualification-card/`），在 `AGENTS.md` 里加一段：

```markdown
## 客户判断卡（化工品内贸销售）
做「客户值不值得跟 / 客户优先级」类任务时，先读 tools/customer-qualification-card/SKILL.md，
按其工作流执行；生成 data.json 后运行 scripts/build_workbook.py 与 build_card.py，
交付前必须运行 scripts/verify_card.py 并通过（RESULT: PASS）。
```

Codex 执行本地命令需要开启沙箱写权限；两条命令都是纯本地 Python，不联网。

### 方式 C：纯提示词 agent（WorkBuddy / ChemClaw / 网页版模型）
这类 agent 通常不能直接读文件夹，按"提示词 + 附件"喂给它：

1. **系统提示词 / 自定义技能**：粘贴 `SKILL.md` 全文；
2. **知识库 / 附件**：上传 `references/*.md`（需要时让它检索）和 `examples/soda-ash-glass-2026-10/data.json`（结构范例）；
3. **执行能力**：若它能跑代码，把 `scripts/` 与 `templates/` 作为可访问文件；若不能，让它**直接输出 data.json**，由你本地跑两条命令生成 xlsx/html。

> 关键点：无论哪种 agent，**"研究"和"生成"是分开的**——agent 负责按 references 搜集事实、填 data.json；脚本负责稳定产出 Excel/HTML。这样换 agent 不会改变交付质量。

---

## 4. 各 agent 接线速查

| agent | 怎么接 | 注意 |
|---|---|---|
| Claude Code / 兼容 Agent Skills | 方式 A，放 `skills/` 目录 | 允许 Bash 执行 python |
| Codex CLI | 方式 B，AGENTS.md 引用 + `tools/` 目录 | 需开沙箱写权限；首次先跑自检命令确认 openpyxl 可用 |
| WorkBuddy | 方式 C：自定义技能/知识库 + 允许代码执行 | 优先让它产出 data.json，生成交给本地脚本 |
| ChemClaw | 方式 C：同 WorkBuddy；可把 references 作为领域知识 | 化工术语多，建议先喂 industry-map.md |
| 其它（扣子/Dify/自建） | 方式 C；把 SKILL.md 当 workflow 说明 | 结构化输出优先用 JSON 模式 |

---

## 5. 常见问题

**Q：Excel 打开排序分显示 0 或空白？**
A：脚本已把计算结果写入缓存，并设置打开时重算。若个别 WPS 版本不刷新，选中"权重与排序"任一黄色格改一下数字回车即可。

**Q：HTML 打开一片空白？**
A：检查是否用记事本另存过（可能改坏编码）。直接用浏览器打开 `*.html`；文件 30–60KB 属正常。

**Q：中文在命令行输出乱码？**
A：只是控制台编码问题，文件内容正常（UTF-8）。Windows 可先 `chcp 65001`。

**Q：想加一个维度（比如"付款条件"）？**
A：`dimensions` 里追加一项，并在每个客户的 `dims` 补齐；Excel 表头会自动扩展，但 HTML 的对比表固定 7 列宽，建议维度不超过 8 个。

**Q：想换行业（比如钛白粉→涂料厂）？**
A：只改 `data.json`：`meta.product/seller`、`market`、7 个维度的事实与证据、`customers`。`dimensions` 的 hint/rubric 可沿用，也可按 `references/scoring-rubric.md` 调整单耗口径。

**Q：能给销售团队批量用吗？**
A：把客户池导出成名单，一家一份 data.json（或一个 JSON 里多个 customer），跑脚本即可批量出卡；建议按"重点区域/最低订单量"预设不同 weights，让排序贴合各自的资源约束。

---

## 6. 版本与维护

- 数据时点写在 `meta.as_of`，每条来源带日期；事实更新后重跑脚本即可，历史卡不要当永久结论。
- 新增行业口径请补 `references/industry-map.md` 一行（产品/下游/关键词/单耗），下次直接复用。
- 如需增加"证据等级（一级/二级/三级）"校验，可在 `verify_card.py` 里对 `sources[].type` 做白名单检查。
