# 空白骨架：复制后换产品

这个目录只有 `fields.json`，没有任何价格、没有客户数据。用法：

1. 复制本目录为 `examples/example-2-<product>/`。
2. 把客户询盘放进 `input/`（邮件 `.eml`、微信截图 `.png`、需求表 `.xlsx/.pdf`）。
3. 复制 `products/_template.json` 为 `products/<product>.json`，填产品事实。
4. 让 agent 按 `SKILL.md` 抽字段，或手工改 `fields.json`：
   - A 类没有的字段：`value=""`，`status="missing"`；
   - B 类客户没说的：`status="assumed"`，`assume_default` 写我方默认；
   - 客户只给简称：`status="tbc"`，不要补“有限公司”；
   - 任何单价：`price.unit_price` 保持 `null`。
5. 出交付物：

```bash
PY=<python>; S=scripts; EX=examples/example-2-<product>
$PY $S/build_workbench.py $EX/fields.json -o $EX/询盘工作台.html --demo-text-file $EX/input/询盘原文.md
$PY $S/build_xlsx.py $EX/fields.json -o $EX/报价工作簿.xlsx
```

6. 销售确认单价与口径后，才生成带价格的草稿：

```bash
$PY $S/build_quote.py $EX/fields.json --price <销售确认价> --qty <数量> \
    --tax "<税费口径>" --freight "<运费口径>" --company "<我方抬头>" \
    --ack "我确认该单价为我方销售价格" -o $EX/demo --xlsx
```

没有 `--ack`，脚本会拒绝生成。没有单价，报价单金额显示“待填单价”。
