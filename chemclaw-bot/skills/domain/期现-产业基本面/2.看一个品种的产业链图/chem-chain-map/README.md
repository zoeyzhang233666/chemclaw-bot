# 化学品产业链知识图谱 Skill（chem-chain-map）

> 给一个化工/材料品种，产出一张**每个节点和每条线都能追溯证据**的产业链图。
> 上限 2 层原料、下限 2 层下游，层数、工艺路线、支链可调。

---

## 30 秒上手

```bash
# 1. 用最小模板起一个新品
cp -r examples/minimal/data mydata
# 2. 改 mydata/meta.json 里的品种，按 references/03-data-contract.md 填节点与关系
# 3. 一条命令跑完
python tools/run_all.py --data-dir mydata --out-dir out --verify
```

产出：
- `out/<id>_chain.html` — 自包含交互图谱（离线可开、可发邮件）
- `out/<id>_chain.xlsx` — 12 sheet 研究工作簿
- `out/<id>_report.json` — 校验结果与覆盖率明细

---

## 看成品示例

`examples/sbs/` 是一个完整的真实案例（SBS 热塑性弹性体）：

| 文件 | 说明 |
|---|---|
| `sbs_chain.html` | 36 节点 / 48 关系的交互图谱 |
| `sbs_chain.xlsx` | 12 sheet 工作簿（含 61 条缺口登记） |
| `data/` | 全量原始 JSON，可复现 |
| `README.md` | 这份图谱背后的判断与取舍 |

直接双击 HTML 就能看，不需要联网。

---

## 它和"画个流程图"的区别

| 普通产业链图 | 本 Skill |
|---|---|
| 所有连接都是箭头 | 9 类关系（转化/联产/副产/配方/成型/终端/替代/路线/包装）各有画法 |
| 终端的"鞋"画成 SBS 的下游 | 强制 `SBS → TPR → 鞋底 → 鞋`，用途不能当产品 |
| 单耗写个数字 | 必须带口径（化学计量/工业级/配方比）与规格基准 |
| 覆盖 95%（不知道分母） | 分母是**开工前冻结的核心清单**，未通过项逐条列出 |
| 缺数据就空着或估一个 | 显式登记为缺口，写明"为什么缺、到哪里补" |
| 图画歪了也不知道 | 布局几何机检（重叠/越界/穿线/斜线/共线），失败自动降级表格 |
| 静态图片 | 可缩放/拖拽/搜索/筛选/上下游高亮/价格联动/表格兜底 |

---

## 目录

```
chem-chain-map/
├── SKILL.md                     Agent 入口（执行流程 7 步）
├── references/
│   ├── 01-method.md             怎么定层数、选节点、判关系、给单耗
│   ├── 02-relation-taxonomy.md  9 类关系的判定标准 + 决策树
│   ├── 03-data-contract.md      全部 JSON 字段契约
│   ├── 04-evidence-and-verification.md  证据分级与数据获取纪律
│   ├── 05-layout-and-rendering.md       布局算法与 34 项交互断言
│   ├── 06-qa-checklist.md       交付前逐项检查表
│   └── 07-new-product-playbook.md       换品种操作手册
├── examples/
│   ├── sbs/                     完整实例（含成品 HTML + XLSX）
│   └── minimal/                 与品种无关的最小模板
├── tools/
│   ├── chain_layout.py          布局引擎 + 几何自检
│   ├── validate_chain.py        校验 + 覆盖率
│   ├── build_chain_html.py      HTML 生成
│   ├── build_chain_xlsx.py      Excel 生成
│   ├── verify_html.py           浏览器端 34 项断言
│   ├── fetch_prices.py          公开价格抓取（示例实现）
│   └── run_all.py               一键全流程
└── assets/
    ├── chain.html.tpl / chain.css / chain_graph.js
    └── schemas/*.schema.json
```

---

## 依赖

```bash
pip install openpyxl          # 必需（Excel）
pip install playwright        # 可选（仅 verify_html.py 自检用）
python -m playwright install chromium
```

Python ≥ 3.9。生成的 HTML **零外部依赖**。

---

## 关键设计取舍

1. **坐标在 Python 端算，不在浏览器算**。换来确定性与可断言的几何质量；代价是布局逻辑要跟着数据形态演进。
2. **`column` 是图谱列号，不是层级数**。缺列是正常的；层数一致性由"物质流边严格递增"保证。
3. **延长线（额外上游列）不计入覆盖率**，但在图上必须标注，否则会被误读成核心结论。
4. **覆盖率是自评工具，不是营销指标**。分母冻结在前，数据填充在后。
5. **宁可留缺口也不估算**。缺口清单本身是有价值的交付内容——它告诉下一个人该往哪里查。

---

## 常见问题

**Q：我的图 100 个节点，一屏放不下怎么办？**
「适应」按可读比例聚焦目标品种，其余可拖拽；「总览」整图入屏。两者配合使用。

**Q：某个节点数据完全查不到。**
保留节点，`missing_flags` 标 `price_missing` / `capacity_missing`，在 `price_mapped_note` 写清原因与补充渠道。覆盖率会扣分，这是正确的。

**Q：布局报警 `edge_collinear` 怎么办？**
≤2 条可接受（记入报告）。更多时见 `references/05-layout-and-rendering.md` 第 8 节调参。

**Q：能改配色/尺寸吗？**
改 `assets/chain.css` 顶部的 CSS 变量；尺寸常量在 `tools/chain_layout.py` 顶部。

**Q：怎么加一种新的关系类型？**
同步改四处：`validate_chain.py` 的 `REL_TYPES` 与 `NON_MONO_TYPES`、`chain_layout.py` 的走线样式、`chain_graph.js` 的 `REL_STYLE`、`references/02-relation-taxonomy.md`。
