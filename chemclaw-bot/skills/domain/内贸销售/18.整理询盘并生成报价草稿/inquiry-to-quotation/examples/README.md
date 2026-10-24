# 参考例子（examples）

## 1. `example-1-soda-ash-glass/` · 纯碱 → 浮法玻璃（完整案例）

这是主案例：客户、询盘、字段、缺口、报价草稿、Excel、交互工作台、案例研究页全都有。
**客户、联系人、公司与价格均为教学演示虚构。**

```
example-1-soda-ash-glass/
├── input/
│   ├── 询盘原文_合并.md              ← 按素材编号切块的可读原文
│   ├── 微信截图_华宇玻璃.png         ← 可上传的微信截图（含 1?30 脏数据）
│   ├── 询盘邮件_华宇玻璃.eml         ← 可上传的邮件
│   ├── 客户需求表_华宇玻璃.xlsx      ← 可上传的 Excel 需求表
│   └── 客户需求表_华宇玻璃_扫描件.pdf ← 可上传的扫描件
├── fields.json                       ← 标准字段（无价格、无口径）
├── fields_demo.json                  ← 演示用字段（销售已确认 1,180 元/吨）
├── 询盘工作台_华宇玻璃纯碱.html      ← 交互式主战场（单价默认空白）
├── 报价工作簿_华宇玻璃纯碱.xlsx      ← 7 表，单价留空
├── 案例研究_纯碱询盘报价.html        ← 研究过程 + 报价效果（演示价）
└── demo/
    ├── 报价_…-报价草稿.md            ← 销售确认价后的报价正文
    └── 报价_…-报价工作簿.xlsx        ← 带演示价的 Excel
```

### 先看哪个？

1. 想看“最终效果” → 打开 `案例研究_纯碱询盘报价.html`。
2. 想自己点一遍 → 打开 `询盘工作台_华宇玻璃纯碱.html`，按页面底部提示填价。
3. 想走审批/留痕 → 打开 `报价工作簿_华宇玻璃纯碱.xlsx`（官方版单价空）。
4. 想看确认价后的 Excel → `demo/` 里的工作簿（明确标 DEMO）。

### 演示价说明

`1,180 元/吨` 是演示者为了展示版式手动填入的，不是系统建议价、不是市场报价、不是成交价。
换成你自己的产品时，**不要沿用这个数字**。

## 2. `_skeleton/` · 换品类的空白骨架

复制整个目录，替换：

1. `fields.json`：按 `references/field-schema.md` 填字段；A 类没有就留 `missing`。
2. `products/<product>.json`：按 `references/product-profile-schema.md` 填产品画像。
3. `input/`：放你的询盘邮件、截图、需求表。
4. 跑 `scripts/extract.py` 或让 agent 按 `SKILL.md` 抽字段。
5. 跑 `build_workbench.py` / `build_xlsx.py` 出交付物。

## 3. 案例复现命令

```bash
PY=<python>; S=scripts
EX=examples/example-1-soda-ash-glass

# 1) 重新生成可上传素材（微信截图 / 邮件 / 需求表）
$PY $S/make_example_inputs.py

# 2) 校正字段并生成演示版 fields_demo.json
$PY $S/prepare_case.py

# 3) 官方版（无价格）
$PY $S/build_workbench.py $EX/fields.json -o $EX/询盘工作台_华宇玻璃纯碱.html \
    --demo-text-file $EX/input/询盘原文_合并.md
$PY $S/build_xlsx.py $EX/fields.json -o $EX/报价工作簿_华宇玻璃纯碱.xlsx

# 4) 演示版（销售已确认 1,180）
$PY $S/build_quote.py $EX/fields_demo.json --price 1180 --qty 200 \
    --tax "含税（13% 增值税专用发票）" --freight "到厂价（含运费）" \
    --company "鲁盐化工（山东）有限公司" --contact "内贸部 李经理  138****0000" \
    --quote-no "QT-20261019-01" --ack "我确认该单价为我方销售价格（演示输入）" \
    -o $EX/demo --xlsx

# 5) 案例研究页
$PY $S/build_case_html.py
```

## 4. 自检

```bash
$PY $S/selfcheck.py $EX/fields.json --html $EX/询盘工作台_华宇玻璃纯碱.html \
    --xlsx $EX/报价工作簿_华宇玻璃纯碱.xlsx
node $S/selftest_workbench.mjs $EX/询盘工作台_华宇玻璃纯碱.html --price 1180
node $S/selftest_case.mjs $EX/案例研究_纯碱询盘报价.html
```
