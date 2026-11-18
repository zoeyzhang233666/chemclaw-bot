# INSTALL · 安装与运行

## 1. 依赖

| 组件 | 版本 | 必需？ | 说明 |
|---|---|---|---|
| Python | 3.9+ | **必需** | 主流程只用标准库（`re` / `json` / `email` / `zipfile`） |
| `openpyxl` | 3.0+ | 生成 Excel 时必需 | 没有它时 `build_xlsx.py` 会退出，但 HTML/MD 仍可生成 |
| Node.js | 16+ | 可选 | 只用于 `selftest_workbench.mjs` 浏览器自测 |
| Edge / Chrome | 任意近期版 | 可选 | 同上；找不到浏览器时自测会跳过而不是失败 |

```bash
python -m pip install openpyxl        # 只装这一个即可
python scripts/selfcheck.py --skill .  # 自检环境与包结构
```

本技能**不联网**。所有抽取、生成、校验都在本机完成，客户邮件不出本机。

## 2. 目录约定

```
overseas-inquiry-triage/
├── scripts/     所有脚本（互不依赖第三方）
├── templates/   回复模板与 HTML 模板
├── products/    产品画像（换品类加 JSON）
├── references/  方法论
└── examples/    跑通的样例 + 空白骨架
```

## 3. 一次完整运行的顺序

```bash
PY="python"; S="scripts"; EX="examples/example-1-id-soda-ash-dense"

# ① 抽取：邮件 → 字段/素材/问题/回复（不产价格）
$PY $S/extract.py --email "$EX/input/询盘邮件.eml" --emit out/

# ② 双栏审阅板（单文件 HTML，离线可用）
$PY $S/build_workbench.py out/fields.json out/reply.json -o out/04_询盘审阅板.html

# ③ 8 表工作簿
$PY $S/build_xlsx.py out/fields.json out/reply.json -o out/05_询盘处理工作簿.xlsx

# ④ 可复制英文草稿（--pack 会检查占位符是否都已由我方确认，未确认则 exit 3）
$PY $S/build_md.py out/fields.json out/reply.json -o out/03_英文回复草稿.md
$PY $S/build_md.py out/fields.json out/reply.json -o out/03_英文回复草稿.md --pack

# ⑤ 中文一页简报
$PY $S/build_md.py out/fields.json out/reply.json --brief cn -o out/06_中文缺口简报.md

# ⑥ 自检（产物齐全 / 字段有依据 / 无承诺 / 占位符登记 / HTML 无外链）
$PY $S/selfcheck.py out/
node $S/selftest_workbench.mjs out/04_询盘审阅板.html     # 可选
```

> 上面六步其实就是 `make_example.py` 做的事——**新同学先跑它**：
> `python scripts/make_example.py examples --all`

## 4. 参数速查

### extract.py

| 参数 | 作用 |
|---|---|
| `--email FILE.eml` | 单封邮件（推荐，保留 Date/From/Subject） |
| `--text FILE.md\|.txt` | 合并素材，支持 `素材01` / `素材02` 分块 |
| `--eml-dir DIR` | 目录下多封 `.eml`，按文件名排序，各成一块素材 |
| `--fields FILE` | 以已有 fields.json 为基底，只补空字段（**不改已确认值**） |
| `--emit DIR` | 输出目录 |
| `--tone formal\|friendly-professional\|concise-direct` | 回复语气 |
| `--template reply_A_confirm\|reply_B_quote_structure\|reply_C_sample\|reply_D_docs_only` | 回复模板 |
| `--no-reply` | 只出字段，不出回复 |
| `--inquiry-no INQ-...` | 询盘号（默认按日期生成） |

### build_md.py

| 参数 | 作用 |
|---|---|
| `--pack` | 生成"可发送版"；仍有占位符未 `confirmed_by_us` → **exit 3** |
| `--brief cn` | 输出中文一页简报而不是英文正文 |

### polish.py

| 参数 | 作用 |
|---|---|
| `--lang en\|id\|vi\|...` | 目标语言语境（决定检查规则） |
| `--report FILE` | 输出 JSON：语言修正项 + 新增承诺/新增数字检查 |

## 5. 闸门一览

| 闸门 | 位置 | 触发条件 | 结果 |
|---|---|---|---|
| 报价闸门 | HTML「缺口页」+ `fields.json.can_quote` | A 类 `affects_quote` 字段有 `缺失`/`歧义` 且未人工放行 | `LOCKED`，禁止点「生成报价」，并列出阻塞字段 |
| 占位符闸门 | `build_md.py --pack` | 任一占位符 `status != confirmed_by_us` | 拒绝生成可发送版，exit 3 |
| 承诺闸门 | HTML 右上角常驻 | 正文命中 `COMMITMENT_PATTERNS` 17 类句式 | 红色告警，标出原句 + 改法 |
| 价格闸门 | HTML 常驻 | 正文出现金额/单价/区间价 | 红色告警 |
| 润色闸门 | HTML「已写稿润色」页 | 润色结果新增承诺或新增数字 | 拒绝输出，列出新增项 |

**人工放行要留痕**：在 HTML 里标「客户已确认」或在工作簿里填 `confirmed_by` + 日期，
否则闸门不会开——这是审计要求，不是麻烦。

## 6. 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| `ModuleNotFoundError: openpyxl` | 没装 openpyxl | `python -m pip install openpyxl` |
| 控制台中文乱码 | Windows 控制台默认 GBK | `set PYTHONIOENCODING=utf-8`（PowerShell：`$env:PYTHONIOENCODING='utf-8'`） |
| `--pack` exit 3 | 还有占位符没填 | 在 HTML 回复区逐项填值，或改 `reply.json` 里 `status` 为 `confirmed_by_us` |
| HTML 打开是空白 | JS 出错（模板被手改坏） | 按 F12 看红字；`node scripts/selftest_workbench.mjs <html>` 会报出首个错误 |
| 抽取漏了某个字段 | 小语种冷门句式 / 版式特殊 | 在 HTML 里手工补值并标依据；**不要让它猜** |
| `selftest_workbench.mjs` 跳过 | 没找到 Edge/Chrome | 装浏览器，或 `--browser <path>` 指定可执行文件 |
| Excel 打开提示修复 | 用旧版 openpyxl 生成 | 升到 3.0+ 重新生成 |

## 7. 搬到别的 agent

见 `AGENTS.md`（契约）与 `PORTABLE_PROMPT.md`（可粘贴提示词）。
核心是一句话：**先抽字段、再定缺口、最后写邮件；顺序不许反。**
