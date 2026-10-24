# Agent 集成指南：ChemClaw / WorkBuddy / Codex / 其他

本 skill 不绑定任何平台，也不调用专有 API。只要目标环境能**读文件、写文件、跑 Python**，就能用。

## 一、装什么

把整个目录复制过去：

```text
chemical-supplier-verification-skill/
  SKILL.md
  README.md
  requirements.txt
  references/
  templates/
  scripts/
  examples/
```

然后：

```bash
pip install -r requirements.txt      # 只有 openpyxl
```

验证：

```bash
python scripts/validate_project.py examples/soda-ash/project.json
```

## 二、三个入口文件

| 文件 | 给谁看 | 作用 |
|---|---|---|
| `SKILL.md` | agent | 工作流、硬规则、交付话术 |
| `README.md` | 人 | 安装、目录、跨平台说明 |
| `references/00-quickstart.md` | 人 + agent | 从需求到两份附件的最短路径 |

agent 必须先读 `SKILL.md`，再按需读 `references/`。

## 三、Codex

1. 把目录放进仓库，例如 `skills/chemical-supplier-verification-skill/`；
2. 在仓库根 `AGENTS.md` 增加：

```md
## 化工品供应商核验

当任务涉及“按化工品找生产厂家 / 供应商核验 / 区分贸易商 / 规格匹配 / 供应商池”时：

1. 先读 `skills/chemical-supplier-verification-skill/SKILL.md`；
2. 按 `references/01-research-protocol.md` 建立样本、拆实体；
3. 按 `references/02-evidence-grading.md` 给每条证据分级；
4. 把结果写入 `project.json`（字段见 `references/03-data-model.md`）；
5. 运行：
   - `python scripts/validate_project.py project.json`
   - `python scripts/run_all.py project.json --outdir output`
6. 交付 Excel + HTML，并用 `SKILL.md` 末尾的话术说明边界。
```

3. 让 Codex 在任务里显式引用该路径；不要让它凭记忆编脚本。

## 四、ChemClaw

如果平台支持“技能/知识库”挂载：

1. 上传整个目录；
2. 把 `SKILL.md` 设为技能主文档；
3. 在系统提示或技能描述里写：

```text
使用 chemical-supplier-verification skill：先读 SKILL.md，按 references/03-data-model.md
输出 project.json，再调用 scripts/run_all.py 生成 Excel + HTML。不得用经营范围判定生产厂家。
```

如果平台只支持单文件：

- 至少上传 `SKILL.md`、`references/03-data-model.md`、`templates/project.schema.json`；
- 生成脚本由 agent 在本机 Python 环境运行，或在平台代码执行环境中运行。

## 五、WorkBuddy

1. 把目录作为“工作区”或“资料夹”导入；
2. 提示词中写：

```text
请以 chemical-supplier-verification-skill/SKILL.md 为唯一方法论来源；
不要自行发明字段名；数据先落 project.json，再用 scripts/run_all.py 出件。
```

3. 如果 WorkBuddy 支持自定义动作，把 `scripts/run_all.py` 注册为动作。

## 六、其他 agent（Claude / Gemini / 自建）

- 把 `SKILL.md` 作为系统提示的一部分；
- 把 `templates/project.schema.json` 作为输出约束；
- 让 agent 只做“研究 + 填 JSON”，生成交给脚本，避免它手写 HTML/Excel。

## 七、目录无关

脚本全部用 `Path(__file__).resolve().parent` 定位 `templates/`，不依赖当前工作目录：

```bash
python /any/path/scripts/run_all.py /any/path/project.json --outdir /any/path/output
```

## 八、没有 Python 怎么办

- 只出 HTML：仍需要 Python（模板填充在 Python 里）；
- 没有 Python 的极端环境：把 `project.json` + `templates/report.html` 交给有 Python 的机器跑；
- 不要用聊天窗口“手工拼 HTML”，容易漏字段。

## 九、验证清单

集成完成后跑一遍：

```bash
python scripts/validate_project.py examples/soda-ash/project.json
python scripts/run_all.py examples/soda-ash/project.json --outdir /tmp/out
```

应看到：

```text
companies: 17, plants: 22, sources: 49
validation: 0 errors, 0 warnings
saved ...xlsx
saved ...html
RESULT: PASS
```

再跑第二个示例，确认换产品/换权重也能出件：

```bash
python scripts/run_all.py examples/caustic-soda-structure/project.json --outdir /tmp/out2
```

## 十、不要把什么交给 agent

- 不要让它“估一个产能”；
- 不要让它把经营范围当生产证据；
- 不要让它跳过 `validate_project.py`；
- 不要让它手工改生成的 HTML；
- 不要让它用示例数据冒充真实企业。

这些约束已经写进 `SKILL.md` 的“六条硬规则”和“不要做”，集成时保留原文即可。
