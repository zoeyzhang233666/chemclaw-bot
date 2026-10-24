# 示例说明

两个示例用**同一套脚本**生成，用于证明「换产品 = 换配置」，并给使用者两个对照基准。

---

## 1. `soda-ash-cn-2026/` —— 完整示例（纯碱）

| 项 | 值 |
|---|---|
| 规模 | 32 个基地 / 24 个集团 / 9 个项目 / 30 条来源 / 15 个省份 |
| 样本覆盖 | 3,570 万吨，占全国 4,468 万吨的 79.9% |
| 数据截止 | 2026-10-19；基准年 2025 |
| 特色 | 多口径并列（4,078/4,305/4,393/4,450/4,468）、置换项目净增还原、天然碱子市场 HHI 5,642 |

**适合看的点**

- `project.json` → `metrics.capacity_total_note` 与 `basis_notes`：口径怎么并列
- `project.json` → `verdicts`：结论怎么写成「证据 + 采购含义 + 置信度」
- `projects.json` → 金山潜江（搬迁）、雪天衡阳（100 置换 80）、海化（100 置换 120）：
  净增还原的三种典型情形
- `project.json` → `gaps`：8 项缺口怎么描述影响与补齐方式

生成：

```bash
python scripts/build_all.py --dir examples/soda-ash-cn-2026
python scripts/check_project.py --dir examples/soda-ash-cn-2026
```

预期：数据 0 错误 0 警告；HTML 6 个标签页 / 24 张企业卡 / 9 张项目卡；Excel 16 表 6 图。

---

## 2. `caustic-soda-cn-2026/` —— 精简示例（烧碱）

| 项 | 值 |
|---|---|
| 规模 | 8 个基地 / 7 个集团 / 5 个项目 / 3 条来源 / 6 个省份 |
| 样本覆盖 | 682 万吨，仅占示例全国口径 5,200 万吨的 13.1% |
| 特色 | 演示「数据不全时报告长什么样」：低覆盖率、占位来源、净增待确认项 |

**适合看的点**

- 覆盖只有 13% 时，报告仍能给出**结构性判断**（碱氯平衡、液碱半径、折百口径），
  但不给出不可靠的集中度结论 —— 这是「宁缺勿猜」的正确姿势。
- `projects.json` 里 CJ03 的 `net: null`（拟建技改，净增待确认）、CJ05 置换净增为 0，
  演示时间线如何区分「毛产能」与「净新增」。
- 价格与产能数字都是**演示量级**，`caveat` 已写明「必须替换为当日真实报价」。

> ⚠ 本示例的数字是为了演示结构而写的量级值，**不要直接引用到真实决策中**。
> 正式使用时，请按 `SKILL.md` 十步工作流，把每个数字替换为带日期的公开来源。

生成：

```bash
python scripts/build_all.py --dir examples/caustic-soda-cn-2026
python scripts/check_project.py --dir examples/caustic-soda-cn-2026
```

---

## 3. 想要第三个示例？

```bash
python scripts/new_project.py --dir work/pvc-cn-2026 \
    --product "PVC（聚氯乙烯）" --short PVC --cas 9002-86-2 \
    --grades "电石法/乙烯法" --year 2025 --forward 2026,2027
```

然后照 `examples/soda-ash-cn-2026/*.json` 的结构填数据即可。脚本不认识「纯碱」或「PVC」
这些字眼 —— 它只认识配置里的字段。
