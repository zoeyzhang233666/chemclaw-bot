# 可移植性（Portability）

本 skill 只用 Python 标准库 + `openpyxl`。没有数据库、没有网络请求、没有 LFS 大文件。

## 一、目录要求

```
overseas-inquiry-kyc/
├── SKILL.md              ← 入口（YAML frontmatter + 方法）
├── AGENTS.md             ← 给通用 Agent 的执行约定
├── README.md
├── LICENSE / VERSION / CHANGELOG.md
├── requirements.txt
├── references/           ← 方法、口径、国别手册
├── templates/            ← inquiry.skeleton.json 等骨架
├── examples/             ← 案例（含 inquiry.json 与产物）
└── scripts/
    ├── _common.py        规范化 / 统计 / 校验基础
    ├── validate.py       结构 + 纪律校验
    ├── build_html.py     → 单文件 HTML
    ├── build_xlsx.py     → 14 表 Excel
    ├── build_all.py      一键跑全流程
    ├── check_xlsx.py     Excel 结构自检（无图像）
    ├── check_render.py   HTML 渲染 QA（可选，需 playwright）
    ├── selfcheck.py      交付前清单
    └── templates/        report.html / style.css / app.js
```

## 二、装到另一个 Agent

### 通用（任意支持 skills 目录的 Agent）

```bash
unzip overseas-inquiry-kyc.zip -d <agent>/skills/
python <agent>/skills/overseas-inquiry-kyc/scripts/validate.py \
       <agent>/skills/overseas-inquiry-kyc/examples/id-soda-ash-demo/inquiry.json
```

`SKILL.md` 的 frontmatter 含 `name` / `description`，触发词已写在 description 里，
支持自动召回的 Agent 会据此匹配。

### Codex / Claude Code

把目录放进项目或用户级 skills 目录，并在该 Agent 的说明文件里加一行指向 `AGENTS.md`。

### ChemClaw / 场景分类体系

按"场景编号目录"放：`skills/外贸销售/4.核验海外询盘公司/`。
解压后顶层目录名保持 `overseas-inquiry-kyc`，或按需重命名（脚本不依赖目录名，依赖相对路径）。

## 三、依赖

| 依赖 | 是否必需 | 说明 |
|---|---|---|
| Python ≥ 3.9 | ✔ | 仅标准库 + openpyxl |
| `openpyxl` ≥ 3.1 | ✔ | 生成 xlsx |
| `playwright` | ✘ | 只用于 `check_render.py` 渲染 QA |

```bash
python -m pip install -r requirements.txt
# 可选渲染 QA
python -m pip install playwright && python -m playwright install chromium
```

## 四、跨平台注意

- **编码**：所有 `.py` 用 UTF-8（无 BOM）；脚本内部强制 `stdout` 为 UTF-8，
  并在 Windows 控制台设置 `PYTHONIOENCODING=utf-8` 更稳妥。
- **路径**：脚本用 `os.path`，不要在 JSON 里写绝对路径。
- **文件名**：产物名可含中文，`pack_skill.py` 会过滤 `\ / : * ? " < > |`。
- **无网络**：构建阶段不访问网络。所有研究在填 `inquiry.json` 之前完成。

## 五、二次开发

| 想改什么 | 改哪里 | 不要改 |
|---|---|---|
| 报告视觉 | `scripts/templates/style.css` | 不要改 `app.js` 的 DOM 契约 |
| 报告结构 | `scripts/templates/app.js` + `report.html` | 不要引入 CDN（必须离线可用） |
| 表结构 | `scripts/build_xlsx.py` 的 `sheet_*` 函数 | 不要改 `_common.normalize` 的默认值语义 |
| 判定规则 | `scripts/_common.py` 的 `verdict_line` | 不要删三分法 |
| 校验规则 | `scripts/validate.py` | 不要放宽"已核实必须有来源" |
| 新国家 | `references/country-playbook/` + `examples/` | 不要往脚本里硬编码国家名 |

## 六、版本升级

- `VERSION` 一行版本号，`pack_skill.py` 会读出来。
- `CHANGELOG.md` 记录改动。
- 数据格式向后兼容：新增字段一律有默认值，旧 `inquiry.json` 必须仍能构建。
