# 海外供应商核验（overseas-supplier-verification）

面向外贸采购 / 化工买方的**海外供应商核验 Skill**：查主体、查产品、查制造关系、查交易一致性、查公开风险、比对单据、出英文询证单。
**只给事实与状态，不给风险分数。**

---

## 安装

把整个文件夹放进平台的 skills 目录，文件夹名保持 `overseas-supplier-verification`，`SKILL.md` 在根目录。

| 平台 | 位置 |
|---|---|
| Codex / 通用 Agent Skills | `~/.agents/skills/overseas-supplier-verification/` |
| Claude Code | `~/.claude/skills/overseas-supplier-verification/` |
| 项目级 | `<项目根>/.agents/skills/overseas-supplier-verification/` |
| ChemClaw / 场景技能库 | `…/skills/外贸采购/<编号>.核验海外供应商/` |

```powershell
# Windows
Copy-Item -Recurse -Force .\overseas-supplier-verification "$env:USERPROFILE\.agents\skills\"
```

```bash
# macOS / Linux
cp -R ./overseas-supplier-verification ~/.agents/skills/
```

---

## 依赖

| 依赖 | 必需性 | 说明 |
|---|---|---|
| Python ≥ 3.9 | 生成 HTML 必需 | 纯标准库，无第三方依赖 |
| openpyxl ≥ 3.0 | 生成 Excel 必需 | `pip install openpyxl`；缺失时只出 HTML |
| 网络 | 仅"检索证据"阶段 | 生成报告全程离线 |
| 字体 | 不需要 | 用系统字体栈 |

检查：

```bash
python -c "import sys; print(sys.version)"
python -c "import openpyxl; print(openpyxl.__version__)"
```

---

## 30 秒上手

```bash
cd overseas-supplier-verification

# 1) 先跑自带案例，确认环境正常
python scripts/build_all.py examples/example-01-saudi-meg/project.json -o /tmp/out --strict

# 2) 用模板开始自己的核验
cp templates/project.template.json my-project.json
#    编辑 my-project.json（字段说明见 references/data-contract.md）

# 3) 校验 + 生成
python scripts/validate.py my-project.json --strict
python scripts/build_all.py my-project.json -o out/
```

预期输出：

```
[pass] 无阻断问题，无警告
[ok] html -> out/海外供应商核验报告_….html
[ok] xlsx -> out/海外供应商核验报告_….xlsx
结论分布：已核实 16｜存在疑点 12｜未核实 28｜未知 8｜不适用 0
```

---

## 没有 Python 也能用

1. 读 `SKILL.md` + `references/method.md`，按七步法完成核验；
2. 把结论写成 Markdown 表（五态 + 证据编号）；
3. HTML：复制 `assets/report-template.html`，替换文字即可（该文件就是一份生成好的完整报告，带样式与交互）；
4. Excel：按 `SKILL.md` §4 的 8 表结构手工建。

> **方法比工具重要。** 没有脚本也要先做"分层 + 挂证据"。

---

## 目录

```
├── SKILL.md                      方法总纲（平台入口）
├── references/
│   ├── method.md                 七步法详版
│   ├── entity-mapping.md         四层主体 + 收款不一致处置
│   ├── evidence-grading.md       五态门槛 + 证据分级
│   ├── country-registries.md     30+ 国家官方登记入口
│   ├── manufacturing-evidence.md 制造关系取证
│   ├── document-checks.md        PI/CR/SDS/COA/银行 逐项清单
│   ├── risk-screening.md         制裁/司法/供应/贸易救济
│   ├── rfi-standard.md           14 条英文询证标准条款
│   ├── data-contract.md          project.json 字段规范
│   └── qa-checklist.md           交付前自检
├── scripts/
│   ├── ovslib.py                 词汇表与工具函数
│   ├── validate.py               交付前校验（0 分阻断）
│   ├── build_html.py             交互式 HTML 报告
│   ├── build_xlsx.py             8 工作表 Excel
│   └── build_all.py              一键：校验 → HTML → Excel
├── templates/project.template.json
├── assets/report-template.html   HTML 样式样板（可直接改）
└── examples/
    ├── example-01-saudi-meg/     沙特 MEG 生产商（含模拟 PI）
    └── example-02-saudi-tradeco-mock/  贸易商自称生产商（反例）
```

---

## 常见问题

| 问题 | 解决 |
|---|---|
| `ModuleNotFoundError: openpyxl` | `pip install openpyxl`，或只用 `--no-xlsx` 出 HTML |
| 中文乱码（Windows 控制台） | `$env:PYTHONIOENCODING="utf-8"` |
| HTML 表格列错位 | `rows` 列数必须等于 `columns` 列数；validate 会提示 |
| validate 报 F03「已核实但没有证据」 | 补证据，或把状态降为「未核实」——这是设计如此 |
| validate 报 F06「出现评分字段」 | 本 Skill 不接受任何评分，删除该字段 |
| 想让某种判断变成警告而非阻断 | 不要改；阻断项代表"不能交付"，改判定而不是改规则 |

---

## 边界

本 Skill 产出的是**采购决策辅助材料**，不构成法律意见、审计结论或信用报告，
不替代海关 AEO 验证、第三方工厂审核、银行资信调查、律所尽调与原产地核查。
付款前请确保「主体 + 收款 + 单据」三者闭环。

---

## 版本

见 `CHANGELOG.md`。`schema_version: "1.0"`，字段只增不改。
