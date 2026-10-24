# 移植到其他电脑 / 其他 Agent

这个 skill 不依赖任何特定平台，只有三样东西：一份方法（`SKILL.md`）、一份数据契约（`references/schema.md`）、两个纯 Python 脚本。

---

## 一、Skill 里有什么

```text
chem-customer-followup/
├── SKILL.md                  ← 方法（平台的入口文件，必须有）
├── README.md                 ← 安装说明
├── references/               ← 判定口径、数据契约、QA 清单
├── scripts/
│   ├── _common.py            ← 公共函数（配色、日期、停滞与逾期计算、校验）
│   ├── build_xlsx.py         ← 生成 Excel（需要 openpyxl）
│   ├── build_html.py         ← 生成 HTML（纯标准库）
│   ├── build_followup.py     ← 一条命令出全套（推荐入口）
│   ├── validate.py           ← 只校验数据
│   └── selfcheck.py          ← 交付前自检（数据+Excel+HTML）
└── examples/                 ← 三个完整案例 + 空白模板
```

---

## 二、依赖

| 依赖 | 是否必需 | 说明 |
|---|---|---|
| **Python ≥ 3.10** | 必需 | 3.10 / 3.11 / 3.12 / 3.13 / 3.14 都测过（3.14 上 `openpyxl` 正常） |
| **openpyxl** | 生成 Excel 必需 | `pip install openpyxl`；没有它时 HTML 仍可生成 |
| 其他 | 无 | HTML 产出是纯标准库拼字符串，无 jinja、无 markdown 库 |
| 网络 | 不需要 | 全程离线 |
| 字体 | 不需要 | HTML 用系统字体栈兜底：微软雅黑 → PingFang SC → 思源黑体 → sans-serif |

检查环境：

```bash
python -c "import sys; print(sys.version)"
python -c "import openpyxl; print('openpyxl', openpyxl.__version__)"
```

`openpyxl` 缺失时：

```bash
pip install openpyxl
# 或（无 pip 权限时）
python -m pip install --user openpyxl
```

---

## 三、装到各平台

### 通用规则

把**整个文件夹**（不是散文件）放到该平台的 skill 目录里，文件夹名保持 `chem-customer-followup`，`SKILL.md` 必须在文件夹根目录。

| 平台 | 建议位置 |
|---|---|
| **通用 / Codex / 本工作区** | `~/.agents/skills/chem-customer-followup/` |
| 项目级（只给某个项目用） | `<项目根>/.agents/skills/chem-customer-followup/` |
| Claude Code | `~/.claude/skills/chem-customer-followup/` |
| 其他支持 Agent Skills 的工具 | 该工具文档里的 skills 目录；命名与结构一致 |

Windows：

```powershell
Copy-Item -Recurse -Force .\chem-customer-followup "$env:USERPROFILE\.agents\skills\"
```

macOS / Linux：

```bash
cp -R ./chem-customer-followup ~/.agents/skills/
```

### chemclaw / workbuddy 这类没有 skills 目录的工具

两种情况：

1. **支持自定义提示/知识库**：把 `SKILL.md` 作为系统提示或知识片段导入，`references/` 作为补充文档上传；把 `scripts/` 留在本机，模型通过执行命令调用。
2. **只支持对话**：把 `SKILL.md` 全文贴进系统提示，模型就会按这个流程走；产出 Excel/HTML 时让它调用本机 Python 脚本（路径写死或用相对路径）。

关键是：**`SKILL.md` 是自包含的**。只要模型读了它，方法和判定标准就齐了，`references/` 是深挖用的附录。

### 给不支持执行命令的 Agent 的降级路径

如果环境里跑不了 Python：

1. 按 `SKILL.md` 的第 0–5 步产出结构化内容；
2. 先落一份 `followup.json`（严格按 `references/schema.md`）；
3. 让用户在有 Python 的机器上跑一条命令：

```bash
python scripts/build_followup.py followup.json -o out/ --md
```

4. 或退回最简交付：把 JSON 内容直接写成 Markdown 表 + 用平台自带的表格能力生成 Excel。

**不要**因为跑不了脚本就跳过四类分层、跳过出处——分层才是这个 skill 的价值，格式是次要的。

---

## 四、装完先验收

```bash
cd ~/.agents/skills/chem-customer-followup

# 1. 跑一个案例（应输出两个 [ok] 和一行摘要）
python scripts/build_followup.py examples/example-1-soda-ash-glass/input.json \
       -o /tmp/verify --md

# 2. 自检（应输出 [pass] 全部检查通过）
python scripts/selfcheck.py examples/example-1-soda-ash-glass/input.json \
       --outdir /tmp/verify
```

预期输出：

```text
[ok] xlsx -> /tmp/verify/纯碱_德润玻璃_跟进卡.xlsx
[ok] html -> /tmp/verify/纯碱_德润玻璃_跟进卡.html  (79595 bytes)
[ok] md   -> /tmp/verify/纯碱_德润玻璃_跟进卡.md

阶段：报价谈判｜停滞 5 天｜逾期承诺 1 项｜记录 22 条
```

三个案例都跑一遍更稳：

```bash
for d in examples/example-*/; do
  python scripts/build_followup.py "$d/input.json" -o "$d" --strict
  python scripts/selfcheck.py "$d/input.json" --outdir "$d"
done
```

`--strict` 会把 warning 也当失败，用于确保停滞天数与时间线自洽。

---

## 五、跨平台坑

| 坑 | 现象 | 解法 |
|---|---|---|
| **BOM** | `json.load` 报 `Unexpected UTF-8 BOM` | 脚本已用 `utf-8-sig` 读取，无需处理；自己写的代码要注意 |
| 控制台中文乱码 | Windows 终端输出问号 | 运行前 `set PYTHONIOENCODING=utf-8`（PowerShell：`$env:PYTHONIOENCODING="utf-8"`） |
| 路径含中文/空格 | 找不到文件 | 用引号包路径；输出目录允许中文 |
| 路径分隔符 | Linux 上 `examples\x\a.json` 报错 | 用 `/` 或 `os.path.join` |
| 文件名非法字符 | 保存失败 | `slug` 避免 `\ / : * ? " < > \|`；中文可用 |
| 无写权限 | `PermissionError` | 输出到用户目录或临时目录 |
| 系统缺中文字体 | HTML 显示方块 | 字体栈已兜底；极端情况下装思源黑体 |
| `openpyxl` 版本过旧 | `Styles` 报错 | `pip install -U openpyxl`（≥3.0） |

---

## 六、版本与兼容

- `schema_version: "1.0"`。字段只增不改；新增字段缺席时脚本给默认值，不会崩。
- 新增分类颜色：改 `scripts/_common.py` 里的 `CATEGORY_COLORS`（未知分类会自动分配灰色，不会报错）。
- 新增工作表：改 `scripts/build_xlsx.py` 的 `build()`；HTML 同理改 `build_html.py`。

---

## 七、把示例当模板用

不要从零写 JSON。最省事的路径：

```bash
cp -R examples/example-1-soda-ash-glass my-case
rm my-case/*.xlsx my-case/*.html my-case/*.md      # 只留 input.json
# 改写 input.json 里的内容（保留结构），改 meta.slug
python scripts/build_followup.py my-case/input.json -o my-case --md
python scripts/selfcheck.py my-case/input.json --outdir my-case
```

挑最接近的案例：
- 报价没谈拢、承诺逾期 → 抄 `example-1-soda-ash-glass`
- 条款在磨、快签了 → 抄 `example-2-tio2-coatings`
- 客户没动静、要资质 → 抄 `example-3-methanol-stalled`

空白模板：`examples/_skeleton/input.json`（结构完整、内容占位）。
