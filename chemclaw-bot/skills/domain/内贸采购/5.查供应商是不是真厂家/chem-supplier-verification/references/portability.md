# 移植到其他电脑 / 其他 Agent

这个 skill 只依赖三样东西：**一份方法（SKILL.md）、一份数据契约（input.json）、两个纯 Python 脚本**。没有平台 API、没有外部服务、没有字体依赖。

---

## 一、包里有什么

```text
chem-supplier-verification/
├── SKILL.md                  ← 方法（平台入口文件，必须有）
├── README.md                 ← 安装与使用说明
├── references/               ← 判定口径、品类对照、检索、QA
├── scripts/
│   ├── _common.py            ← 强度、四类结论、校验（无第三方依赖）
│   ├── build_html.py         ← 生成自包含 HTML（纯标准库）
│   ├── build_xlsx.py         ← 生成 Excel（需要 openpyxl）
│   ├── build_report.py       ← 一条命令出全套（推荐入口）
│   ├── validate.py           ← 只校验数据
│   └── selfcheck.py          ← 交付前自检
└── examples/                 ← 3 个完整案例 + 空白模板
```

---

## 二、依赖

| 依赖 | 是否必需 | 说明 |
|---|---|---|
| Python ≥ 3.9 | 必需 | 3.9—3.14 均可 |
| openpyxl | 生成 Excel 必需 | `pip install openpyxl`；缺失时自动只出 HTML |
| 网络 | 仅检索阶段 | 生成附件全程离线 |
| 字体 | 不需要 | HTML 用系统字体栈兜底 |

检查：

```bash
python -c "import sys; print(sys.version)"
python -c "import openpyxl; print(openpyxl.__version__)"
```

---

## 三、装到各平台

### 通用规则

把**整个文件夹**放进该平台的 skill 目录，文件夹名保持 `chem-supplier-verification`，`SKILL.md` 在根目录。

| 平台 | 位置 |
|---|---|
| **Codex / 通用 Agent Skills** | `~/.agents/skills/chem-supplier-verification/` |
| **Claude Code** | `~/.claude/skills/chem-supplier-verification/` |
| 项目级（只给某项目用） | `<项目根>/.agents/skills/chem-supplier-verification/` |
| 其他支持 Agent Skills 的工具 | 按该工具文档的 skills 目录 |

```powershell
# Windows
Copy-Item -Recurse -Force .\chem-supplier-verification "$env:USERPROFILE\.agents\skills\"
```

```bash
# macOS / Linux
cp -R ./chem-supplier-verification ~/.agents/skills/
```

### ChemClaw / WorkBuddy 这类没有 skills 目录的工具

分三种情况：

**1. 支持自定义系统提示 / 知识库**
- 把 `SKILL.md` 全文导入系统提示或"角色设定"；
- 把 `references/*.md` 作为知识库文档上传（按需检索）；
- `scripts/` 留在本机，提示模型用相对路径调用 `python scripts/build_report.py input.json -o out/`。

**2. 支持"工具/函数调用"但没有文件系统**
- 让模型只负责产出 `input.json`（严格按 `references/schema.md`）；
- 附件生成放到你自己的机器上跑一条命令；
- 或让模型把 JSON 内容直接写成 Markdown 表，Excel 用平台自带表格能力生成（质量会下降，但结构不丢）。

**3. 纯对话（不能执行命令、不能上传文件）**
- 只贴 `SKILL.md`；
- 让模型按第 0—7 步产出结构化结论：结论、证据三组、缺口、下一步；
- 提醒用户：**分层方法比附件格式重要**，没有附件也要先做分层。

> 关键：`SKILL.md` 是自包含的。只要模型读了它，方法、判定、输出口径就齐了；`references/` 是深挖用的附录。

### 给不支持执行命令的 Agent 的降级路径

```text
1. 按 SKILL.md 第 0—7 步完成研究与判定
2. 产出结构化 JSON（字段见 references/schema.md）
3. 在有 Python 的机器上：
      python scripts/build_report.py input.json -o out/
4. 仍不行：把 JSON 转成 Markdown 表 + 手工建 Excel（保留三组证据与四类结论）
```

**不要**因为跑不了脚本就跳过三分法、跳过来源——分层才是这个 skill 的价值。

---

## 四、跨平台坑

| 坑 | 现象 | 解法 |
|---|---|---|
| Windows 控制台 GBK | 打印 `₂`、`③` 时 `UnicodeEncodeError` | 脚本已在 `_common.py` 里把 stdout 切到 UTF-8；仍异常则 `$env:PYTHONIOENCODING="utf-8"` |
| BOM | `json.load` 报 `Unexpected UTF-8 BOM` | 脚本用 `utf-8-sig` 读取，无需处理 |
| 路径含中文/空格 | 找不到文件 | 用引号包路径；输出目录允许中文 |
| 路径分隔符 | Linux 上 `examples\x\a.json` 报错 | 用 `/` 或 `os.path.join` |
| 文件名非法字符 | 保存失败 | `meta.slug` 避免 `\ / : * ? " < > \|` |
| 无写权限 | `PermissionError` | 输出到用户目录或临时目录 |
| openpyxl 版本过旧 | 样式报错 | `pip install -U openpyxl`（≥3.0） |
| 缺中文字体 | HTML 显示方块 | 字体栈已兜底；极端情况装思源黑体 |
| Excel 打开分数为 0 | 公式未重算 | 文件已设 `fullCalcOnLoad`；用 WPS 打开可手动重算 |

---

## 五、装完先验收

```bash
cd ~/.agents/skills/chem-supplier-verification

python scripts/build_report.py examples/example-1-soda-ash/input.json -o /tmp/verify
python scripts/selfcheck.py  examples/example-1-soda-ash/input.json --outdir /tmp/verify
```

预期：

```text
[ok] xlsx -> /tmp/verify/纯碱供应商真伪核验报告.xlsx
[ok] html -> /tmp/verify/纯碱供应商真伪核验报告.html
结论分布：生产厂家 2｜贸易经销 1｜分装或复配 1｜证据不足暂无法确认 1

[pass] 全部检查通过：5 案例 / 46 条证据（直接 11）/ 12 项材料
```

三个案例都跑一遍：

```bash
for d in examples/example-*/; do
  python scripts/build_report.py "$d/input.json" -o "$d"
  python scripts/selfcheck.py "$d/input.json" --outdir "$d"
done
```

---

## 六、定制

| 想改什么 | 改哪里 |
|---|---|
| 评分维度/权重 | `dimensions`（权重必须合计 100） |
| 四类结论的措辞 | `scripts/_common.py` 的 `VERDICT_META`（同时改 `VERDICT_FILL` 颜色） |
| 新增证据分类 | `scripts/_common.py` 的 `CATEGORY_ORDER` |
| 报告配色/版式 | `scripts/build_html.py` 顶部 `CSS` |
| Excel 工作表 | `scripts/build_xlsx.py` 的 `build()` |
| 新增品类 | 先补 `references/regulatory-matrix.md`，再填 `product_profile` |

改完跑 `selfcheck.py`，确认没把公式引用改坏（01 表引用 05 表的行号是动态算的）。

---

## 七、版本

- `schema_version: "1.0"`：字段只增不改，新字段缺席时给默认值；
- 升级时保留旧 `input.json` 即可继续生成；
- 产物不要手改——改了会和 JSON 不一致，下次生成就被覆盖。
