# 生成出口报价单与形式发票 — 使用说明

本技能把**已确认**的商务信息，做成一份可直接发给客户的英文报价单（Quotation）或形式发票（Proforma Invoice）。

## 快速开始（三步）

1. **准备数据**：复制 `examples/case-ex001-soda-ash-indonesia.json`，把里面的模拟信息换成你的确认信息。
   单价是必填项；没有确认的字段留空，文件会自动显示占位符。
2. **打开网页编辑器**：双击 `dist/deliverables/EX-001_QT-SIM-2610-001_Studio.html`（单文件，无需联网）。
   左侧按标签页填：单据 / 双方 / 商品 / 条款 / 银行 / 检查 / 模板；右侧是实时英文 A4 预览。
3. **复核并导出**：在“检查”页看完所有错误和提示 → 点“复核签发”填写复核人 → 导出 Word / PDF / JSON / 数据表。

命令行方式（可选）：

```bash
python scripts/build_docx.py --case 你的case.json --out 报价单.docx --doc-type QUOTATION --pdf
python scripts/build_xlsx.py --case 你的case.json --out 数据表.xlsx
python scripts/build_all.py          # 一次生成全部文件 + QA_report.md
```

## 五条底线

| 底线 | 表现 |
|---|---|
| 不改商务条件 | 价格、付款、交期、有效期、条款全部来自你输入，一字不改 |
| 没有单价不出正式文件 | 总额显示 `[ PENDING PRICE ]`，文件标为草稿 |
| 不编造银行账号 | 未确认时显示红色占位：`[ BANK DETAILS TO BE CONFIRMED BY THE SELLER … ]` |
| 危险品必须有依据 | 未核实状态直接阻断（`DG status: TO BE VERIFIED`） |
| 必须人工复核 | 复核人填写姓名+职务并逐项打勾后，才能转为 FORMAL 正式件 |

## 演示数据声明

`examples/` 与 `dist/examples/` 里的 6 个案例全部是**模拟演示数据**：
公司名带 `(SIMULATED DEMO)`、邮箱为 `@example-demo.invalid`、电话为占位号码、银行账号一律占位，
文档带“SIMULATED DEMO / NOT FOR TRADE USE”水印。真实使用时请新建案例文件，不要直接用演示文件改数字。

## 演示案例一览

| 案例 | 产品 | 国家 | 贸易术语 | 币种 | 说明 |
|---|---|---|---|---|---|
| EX-001 | 重质纯碱 1,000 MT × USD 217 | 印尼 | CIF 雅加达 | USD | 主案例：T/T 预付、40,000 袋 × 25 kg、非危险品 |
| EX-002 | PVC SG-5 / SG-8 | 越南 | DAP 买方工厂 | USD | 多行、LC 即期完整条款 |
| EX-003 | 邻苯二甲酸二辛酯 DOP | 韩国 | FCA 浦东机场 | USD | 空运 + 草稿路径（缺单价、DG 未核实） |
| EX-004 | 颗粒尿素 46% N | 印度 | CFR 图蒂科林 | USD | 形式发票、含运费不含保险 |
| EX-005 | 一水柠檬酸（食品级） | 德国 | CIP 杜伊斯堡 | EUR | 多式联运、保险含在单价内 |
| EX-006 | 钛白粉（金红石型） | 巴西 | EXW 深圳仓库 | USD | 占位路径：无单价/付款/有效期 |

## 文件结构

```
SKILL.md              技能主说明（给 AI 执行用）
references/           字段规范、Incoterms 矩阵、金额规则、校验规则、危险品、银行边界、报价单 vs PI、排版、QA
schemas/              quote.schema.json（数据契约）、company-template.schema.json（公司模板）
templates/            engine.js（校验与计算引擎）、studio.template.html + studio.app.js（网页编辑器）
scripts/              engine_check / engine_bridge / build_docx / build_xlsx / build_studio_html
                      / make_examples / build_all / browser_probe
examples/             6 个案例 JSON + 索引
dist/deliverables/    主案例交付物：HTML 编辑器 + 报价单 Word/PDF + 形式发票 Word/PDF + Excel 数据表
dist/examples/        EX-002 ~ EX-006 各自一套同样的文件
dist/QA_report.md     构建与核对报告（含独立金额复算）
```
