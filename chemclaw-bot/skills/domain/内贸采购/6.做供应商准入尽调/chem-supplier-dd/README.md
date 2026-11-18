# 化工品供应商准入尽调 Skill（可移植包）

一个**与 agent 平台无关**的技能包：任意支持"读取一个目录 + 执行 Python"的 agent 都能用。
给一份供应商名单，产出一份带证据链的准入尽调底稿（HTML + Excel）。

```
chem-supplier-dd/
├── SKILL.md                     ← 技能主文件（方法、纪律、判定规则）
├── README.md                    ← 本文件（安装与运行）
├── assets/
│   ├── dossier.css              ← 底稿样式（设计系统，改这里换皮）
│   └── dossier.js               ← 交互：筛选、勾选导出、清单进度、打印
├── scripts/
│   ├── ddlib.py                 ← 公共渲染组件（零依赖）
│   ├── render_html.py           ← data.json → 单文件 HTML
│   ├── render_xlsx.py           ← data.json → 12 页签 Excel
│   ├── validate.py              ← 渲染前自检（证据引用/状态词/合规红线）
│   └── build_all.py             ← 一条命令跑完
├── references/
│   ├── data-contract.md         ← data.json 全字段说明
│   ├── research-playbook.md     ← 各字段去哪儿查、怎么交叉
│   └── quality-gates.md         ← 证据标准、写作规范、分级口径
├── templates/
│   └── data.template.json       ← 最小可运行骨架
└── examples/
    └── soda-ash/                ← 完整示例：山东海化 · 纯碱
        ├── data.json            ← 全部内容（76 KB）
        ├── out/                 ← 生成好的 HTML + XLSX
        └── NOTES.md             ← 这份示例的做法与缺口说明
```

## 环境要求

- Python **3.9+**（无第三方依赖即可生成 HTML）
- `openpyxl`（仅生成 Excel 需要）：`pip install openpyxl`
- 不需要联网、不需要浏览器、不需要 Office

## 安装到不同 agent

### Claude Code / 支持 Agent Skills 的客户端
```bash
# 个人级
cp -r chem-supplier-dd ~/.claude/skills/
# 或项目级
cp -r chem-supplier-dd .claude/skills/
```
出现 `SKILL.md` 后即可被自动发现，说"帮我做个供应商准入尽调"就会触发。

### OpenAI Codex CLI
```bash
mkdir -p ~/.codex/skills && cp -r chem-supplier-dd ~/.codex/skills/
```
若你的版本只认 `AGENTS.md`，在项目根目录写一行指针即可：
```
供应商准入尽调一律读取 ~/.codex/skills/chem-supplier-dd/SKILL.md 并按其流程执行。
```

### chemclaw / workbuddy / 其他自建 agent
这类平台通常"上传知识库"或"挂载工作目录"，两种接法都可以：

1. **整包挂载**（推荐）：把整个目录挂进工作区，在系统提示里写明
   `遇到供应商准入/尽调类任务，先读 chem-supplier-dd/SKILL.md，再按其中流程执行`。
2. **只喂 SKILL.md**：把 `SKILL.md` 作为该技能的 instructions 正文，把 `references/` 作为附件知识，
   把 `scripts/` 放进代码沙箱。方法完全一致。

### 通用（任何能跑 shell 的 agent）
```bash
cd chem-supplier-dd
python scripts/build_all.py examples/soda-ash/data.json
```
agent 只需要做两件事：**查资料 → 写 data.json → 跑命令**。

## 快速开始

```bash
# 1. 用模板起步
cp templates/data.template.json mydata.json

# 2. 按 references/data-contract.md 填内容（这是唯一需要动脑的部分）

# 3. 校验 + 生成
python scripts/build_all.py mydata.json --out ./out
```

产物：

| 文件 | 用途 |
|---|---|
| `供应商准入尽调底稿_<主体>_<品类>.html` | 单文件交互底稿，可直接邮件/IM 发送 |
| `供应商准入尽调底稿_<主体>_<品类>.xlsx` | 12 页签工作簿，可当台账持续维护 |

HTML 里已经内置：模块勾选导出、状态聚焦（风险/待核验/已核实）、清单完成度、打印/导出 PDF。

## 让 agent 写 data.json 的提示词模板

```
请按 chem-supplier-dd/SKILL.md 的流程，对 <主体全称>（<股票代码或信用代码>）做
<品类> 的供应商准入尽调，采购场景为 <年用量>、<金额>、<用途>，数据截止 <日期>。
只使用巨潮资讯网/政府监管平台的公开披露作为证据，逐条登记 E01…En。
查不到的写“无公开信息”并转入材料清单，不要用行业常识补位，不要预测履约表现。
产出 data.json 后运行 scripts/build_all.py，把 HTML 和 Excel 一起给我。
```

## 改样式 / 改结构

- **换配色**：改 `assets/dossier.css` 顶部的 `:root` 变量（`--brand`、`--brass`、`--ink` 等）。
- **改模块数量**：`data.json` 的 `sections` 是数组，增删即可；`nav` 同步增删。
- **改 Excel 页签**：`scripts/render_xlsx.py` 每个页签是一段独立代码，删掉不影响其他页签。
- **换语言**：`ddlib.DEFAULT_STATUS` 与 `render_html.DEFAULT_UI` 里是全部界面文案。

## 已验证

- 示例产物：HTML 123 KB / 单文件；Excel 12 页签 / 46 KB；`validate.py` 0 FAIL 0 WARN。
- HTML 在 1440 / 1024 / 430 px 三档宽度无横向溢出；打印样式隐藏导航与勾选框、保留章节与表头。
- Excel 结构自检通过（`check_office.py` → pass）。

## 许可

内部使用。示例中的第三方数据均来自公开披露，引用请保留原文链接。
