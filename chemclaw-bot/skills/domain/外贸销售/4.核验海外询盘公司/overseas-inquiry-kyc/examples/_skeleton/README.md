# 骨架案例（_skeleton）

**这是空白模板，不是案例。** 用于快速开始自己的核验。

```bash
cp -r examples/_skeleton work/my-inquiry
# 编辑 work/my-inquiry/inquiry.json
python scripts/build_all.py work/my-inquiry/inquiry.json work/my-inquiry/output --name 我的客户
```

## 生成出来会是什么样

- 13 条核验项，全部为「未核实」——这是**正确**的空模板状态，不是 bug；
- `validate.py` 会给 13 条 warning（K02–K13 没有关联来源、没有「已核实」、B 区块缺已核实项），
  这些 warning 就是你的待办清单；
- HTML 与 Excel 都能正常生成，可以先把空壳跑通，再逐条填。

## 建议的填写顺序

1. `meta`（尤其是 `synthetic` 改成 `false`）
2. `inquiry`（原文邮件）
3. `extraction`（照抄字段）
4. `sources`（先去官网/登记入口把链接收集齐）
5. `checks`（先写 A 区块 3–5 条，挂上 `source_ids`，每填完一个区块跑一次 `validate.py`）
6. `matrix` / `email_auth`
7. `business_fit`
8. `risks` / `requests` / `actions` / `messages`
9. `boundaries`

> 每完成一个区块就跑一次 `validate.py`，比全部写完再调试快得多。

## 想让模板"有内容"？

直接用 [`../id-soda-ash-demo/`](../id-soda-ash-demo/) 复制过去改，
它已经填满了 24 条核验、12 项资料清单、4 段话术，改起来比重写快。
