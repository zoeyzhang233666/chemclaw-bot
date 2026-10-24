# chem-supplier-verification

> 查供应商是不是真厂家：把"对方说自己有厂"变成可复核的证据链。

面向化工品内贸采购与销售：输入**企业 + 产品**，自动按"许可—装置—产量—业务"检索公开证据，分成**直接生产证据 / 间接业务证据 / 不构成证据**三组，最后只给四种结论：

**生产厂家 · 分装或复配 · 贸易经销 · 证据不足暂无法确认**

产出固定两件套：**自包含 HTML 报告 + 10 表 Excel 工作簿**。产品无关，纯碱、钛白粉、双氧水、树脂、食品添加剂都能用。

---

## 一分钟上手

```bash
# 1. 拿最接近的案例，复制成自己的
cp -R examples/example-1-soda-ash my-case

# 2. 只留 input.json，改内容（保留结构，改 meta.slug）
rm my-case/*.xlsx my-case/*.html

# 3. 生成两件套
python scripts/build_report.py my-case/input.json -o my-case

# 4. 交付前自检
python scripts/selfcheck.py my-case/input.json --outdir my-case
```

## 环境要求

| 依赖 | 说明 |
|---|---|
| Python ≥ 3.9 | 3.9—3.14 均可 |
| openpyxl | 生成 Excel 需要：`pip install openpyxl`；没有它时自动只生成 HTML |
| 网络 | 仅在**检索阶段**需要；生成附件全程离线 |

Windows 控制台出现乱码时，脚本已自动把 stdout 切到 UTF-8；如仍异常，先 `$env:PYTHONIOENCODING="utf-8"`。

---

## 它会做什么

| 步骤 | 产出 |
|---|---|
| 定契约 | 企业全名、产品规格、判断时点、品类 |
| 定硬证据 | `product_profile`：本产品什么算硬证据、什么不算、要验哪些指标 |
| 五路检索 | 许可环保 / 产能装置 / 产品市场 / 运营痕迹 / 现场第三方 |
| 三分法归档 | 每条证据带组别、强度（●●●/●●○/●○○/不计分）、来源、原文、采信理由 |
| Q1→Q4 判定 | 四类结论之一；证据不足就写"暂无法确认" |
| 100 分模型 | 五维打分，定位缺口，不推翻结论 |
| 附件 | HTML（交互）+ Excel（10 表），同源生成 |

**三条硬约束**：经营范围与宣传语不进直接证据；证据不够不许推断；每条证据必须能点回来源。

---

## 目录

```text
chem-supplier-verification/
├── SKILL.md                 方法本体（Agent 读这个）
├── README.md                本文件
├── references/
│   ├── schema.md            input.json 全字段契约
│   ├── evidence.md          三分法 + 强度 + 20 个易混案例
│   ├── regulatory-matrix.md 品类 → 硬证据对照表（危化/食品/农药/肥料/药品/气体）
│   ├── search-playbook.md   检索式、官方入口、失效链接替代
│   ├── research-workflow.md 研究时间盒、饱和信号、多案例配比
│   ├── verdicts.md          Q1—Q4 边界、置信度、矛盾处理
│   ├── request-materials.md 12 项索取清单 + 话术 + 品类变体
│   ├── portability.md       装到其他电脑 / Agent（ChemClaw、WorkBuddy、Codex…）
│   ├── qa.md                交付前 40 项自检
│   └── failure-log.md       症状 → 病因 → 处方
├── scripts/
│   ├── build_report.py      一条命令出全套（推荐入口）
│   ├── build_html.py        生成自包含 HTML
│   ├── build_xlsx.py        生成 10 表 Excel
│   ├── validate.py          只校验 input.json
│   ├── selfcheck.py         交付前自检（数据 + Excel + HTML）
│   ├── pack_skill.py        重新打包成 zip（改完后用）
│   └── _common.py           强度、四类结论、判定规则、校验
└── examples/
    ├── example-1-soda-ash/  纯碱：5 案例，覆盖四类结论（真实 + 脱敏）
    ├── example-2-tio2/      钛白粉：3 案例，演示换品类（1 真 2 合成）
    └── _skeleton/           空白模板
```

---

## 装到其他机器 / Agent

把**整个文件夹**放进平台的 skill 目录，名字保持 `chem-supplier-verification`，`SKILL.md` 在根目录。

```powershell
# Windows
Copy-Item -Recurse -Force .\chem-supplier-verification "$env:USERPROFILE\.agents\skills\"
```

```bash
# macOS / Linux
cp -R ./chem-supplier-verification ~/.agents/skills/
```

| 平台 | 位置 / 用法 |
|---|---|
| Codex / 通用 Agent Skills | `~/.agents/skills/chem-supplier-verification/` |
| Claude Code | `~/.claude/skills/chem-supplier-verification/` |
| 项目级 | `<项目根>/.agents/skills/chem-supplier-verification/` |
| **ChemClaw / WorkBuddy** 等无 skills 目录 | 把 `SKILL.md` 导入系统提示或知识库，`references/` 作为补充文档；`scripts/` 留本机，让模型执行命令 |
| 纯对话环境（不能执行命令） | 只贴 `SKILL.md`，让模型按 schema 产出 `input.json`，再到有 Python 的机器上生成附件 |

装完验收：

```bash
cd ~/.agents/skills/chem-supplier-verification
python scripts/build_report.py examples/example-1-soda-ash/input.json -o /tmp/verify
python scripts/selfcheck.py examples/example-1-soda-ash/input.json --outdir /tmp/verify
```

看到两个 `[ok]` 和 `[pass] 全部检查通过` 就装好了。

详细说明（含无 Python 的降级路径）见 [`references/portability.md`](references/portability.md)。

---

## 三个示例演示什么

| 案例 | 产品 | 结构 | 演示重点 |
|---|---|---|---|
| example-1 | 纯碱 | 5 案例 / 46 条证据 | 四类结论全覆盖；排污许可“无机碱制造”、产能置换反向证明、**交割厂库 ≠ 生产资质**、脱敏样例 |
| example-2 | 钛白粉 | 3 案例 / 22 条证据 | 换品类后硬证据换成“颜料制造”+ 分线产能；**危化证不覆盖非危化品**；只有 1 家真实企业，其余标注合成 |
| _skeleton | 占位 | 1 案例 | 最小可运行结构，复制即用 |

> example-2 只对龙佰集团做了公开来源核验（证券时报、巨潮资讯半年报、官网）；另外两个案例是**脱敏合成样例**，用于演示判定路径，不对应任何真实企业。

---

## 常见问题

**Q：能用在非化工品上吗？**
方法（定硬证据 → 五路检索 → 三分法 → Q1—Q4）与行业无关，换品类主要改 `product_profile` 与 `materials`。但许可体系差异很大，非化工品请先补一份自己的 regulatory-matrix。

**Q：企业/产品换了要改脚本吗？**
不用。所有文案、案例、评分都在 `input.json`，脚本不硬编码任何产品。

**Q：Excel 和 HTML 数字不一致？**
说明有人手改了产物。只改 JSON，两个都重新生成。

**Q：为什么有的案例分数低但结论是"生产厂家"？**
分数衡量证据链完整度，不衡量真假。现场核验没做，第五维就是 0 分。结论只看 Q1—Q4。

**Q：能只出 HTML 吗？**
可以：`python scripts/build_report.py input.json -o out --html-only`，或 `python scripts/build_html.py input.json -o out/`。

**Q：能查到真实企业吗？**
脚本只做结构与排版，**检索必须由 Agent 完成**。Agent 拿着 `search-playbook.md` 去查，把结果写进 `input.json`。不要把"没查到"写成"不存在"。

---

## 版本

`schema_version: 1.0`。字段只增不改；新增字段缺席时脚本给默认值，不会崩。
