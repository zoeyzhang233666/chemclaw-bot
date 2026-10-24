# 安装与移植（Windows / macOS / Linux）

这是一个**文件夹即技能**的包：没有服务、没有数据库、没有网络依赖。把整个目录拷到目标机器，
agent 读 `SKILL.md`，脚本按相对路径找模板与依赖。

## 1. 复制

```bash
# 目标机器上的 skills 目录（按你所用 agent 的实际约定替换）
cp -r inquiry-to-quotation ~/.claude/skills/
# 或
cp -r inquiry-to-quotation ~/.codex/skills/
```

如果目标 agent 没有“技能目录”概念：

- 把 `SKILL.md` 全文作为系统提示词/项目指令；
- 把 `examples/example-1-soda-ash-glass/` 作为 few-shot 输入输出；
- 需要出文件时，再调用 `scripts/` 里的 Python。

## 2. 依赖

| 用途 | 依赖 | 是否必需 |
|---|---|---|
| 抽字段、HTML、报价草稿、自检 | Python 3.9+ 标准库 | 必需 |
| Excel 工作簿 | `xlsxwriter` | 出 XLSX 时必需 |
| Excel 校验 | `openpyxl` | 可选 |
| 生成案例微信截图 / 扫描件 | `Pillow` | 仅复现示例时需要 |
| 工作台/案例页自测 | Node 18+ + Edge/Chrome | 可选 |

没有 `xlsxwriter` 时，HTML 与 Markdown 仍可正常生成。

## 3. 冒烟测试（用自带纯碱案例）

```bash
PY=<python>
S=scripts
EX=examples/example-1-soda-ash-glass

# HTML（单价默认空白，打开即有默认文本）
$PY $S/build_workbench.py $EX/fields.json -o /tmp/询盘工作台.html \
    --demo-text-file $EX/input/询盘原文_合并.md

# Excel（7 表，单价留空）
$PY $S/build_xlsx.py $EX/fields.json -o /tmp/报价工作簿.xlsx

# 自检
$PY $S/selfcheck.py $EX/fields.json --html /tmp/询盘工作台.html --xlsx /tmp/报价工作簿.xlsx
```

## 4. 生成带价格的报价（必须由销售确认）

```bash
$PY $S/build_quote.py $EX/fields_demo.json --price 1180 --qty 200 \
  --tax "含税（13% 增值税专用发票）" --freight "到厂价（含运费）" \
  --company "我方公司全称" --ack "我确认该单价为我方销售价格" \
  -o /tmp/demo --xlsx
```

没有 `--ack` 会直接 exit 2。不要把 `fields_demo.json` 的 1,180 当成默认价或建议价。

## 5. 接到别的 agent / 系统

| 目标 | 做法 |
|---|---|
| Claude / Codex | 放 skills 目录，保留 `SKILL.md` frontmatter 的 `name` / `description` |
| ChemClaw / WorkBuddy | 无技能目录时，把 `SKILL.md` 作为系统提示词；不能跑脚本时用 `PORTABLE_PROMPT.md`（纯提示词版） |
| 任意聊天 agent | 直接粘 `PORTABLE_PROMPT.md`；它只输出字段表/缺口/报价结构，不产生价格 |
| 自建 Web 产品 | 复用 `templates/workbench.template.html`；后端只注入 `__DATA__` 等占位符 |
| CRM | 把 `fields.json` 映射为询盘对象；`price` 段不落库，报价时再带 |
| 合同审阅 | 工作台“下一步：合同审阅”复制报价全文 + 审阅要点；也可把 `demo/*.md` 喂给合同审阅技能 |

## 6. 跨平台注意

- Windows 控制台默认 GBK，中文输出可能乱码；设置 `PYTHONIOENCODING=utf-8`，或直接看生成的文件。
- 路径含中文时，Node 侧用 `pathToFileURL` 转 `file:///…`；不要把中文路径直接拼进 `file://`。
- Excel 公式引用带空格的工作表名要加单引号：`'04 价格与口径'!$C$6`。
- 无头浏览器自测找不到 Edge/Chrome 会自动跳过，不影响交付文件。
- HTML 是单文件、纯前端；上传的文件不会离开本机。不要把它改成默认上传到服务器。

## 7. 目录速览

```
inquiry-to-quotation/
├── SKILL.md                  ← agent 主流程
├── README.md                 ← 人读的快速开始
├── INSTALL.md                ← 本文件
├── AGENTS.md                 ← 给 Codex 等读的短约束
├── VERSION / CHANGELOG.md
├── products/                 ← 产品画像（纯碱示例 + 空白模板）
├── schemas/                  ← fields.json / quote.json 的 JSON Schema
├── references/               ← 字段口径、抽取规则、报价写法、价格红线、研究手册、QA
├── scripts/                  ← 抽取、HTML、Excel、报价、自检、示例素材生成
├── templates/                ← 工作台模板、默认报价模板
└── examples/                 ← 纯碱完整案例 + 空白骨架
```
