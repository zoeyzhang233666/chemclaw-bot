# 交付前自检（逐项打勾）

## A. 抽取层

- [ ] 每条有值的字段都有 `source_id` + `quote`（原句，原语言） + `locator`
- [ ] 引用原句与原文逐字一致（脚本 `selfcheck.py` 会比对，允许大小写/空白差异，不允许改词）
- [ ] 同一字段多处不一致时，旧值保留在 `note`
- [ ] `unreadable` 里的模糊数字**没有**被填进任何字段
- [ ] CAS 有来源（customer / our_docs / verified + 日期）；查不到就留空并写明"待我方产品资料确认"
- [ ] 品名形态（dense/light、flake/liquid、granular/prilled）没有被合并
- [ ] 数量拆清试单量 / 年量 / 单批量，且没有把 L/C 数量当试单量

## B. 分桶层

- [ ] A 桶字段全部 `stated` 才允许"可报价"为真
- [ ] B 桶字段用 `assume` 时，HTML/Excel/MD 三处都带 `(our assumption – to be confirmed)` / 「我方假设」
- [ ] C 桶字段（我方主体、装运港、含税口径）没有从询盘单向推断
- [ ] 每条缺口都映射到一个**具体的客户问题**（不是"请补充资料"）
- [ ] 问题条数 ≤ 6，且优先阻塞报价的

## C. 回复层

- [ ] 邮件正文里没有任何未占位化的价格（正则扫 `USD|USD/MT|\$\s?\d|Rp\.?\s?\d` 后面跟数字）
- [ ] 没有任何具体天数/日期（正则扫 `\d+\s*(days|weeks|个月|天)`）
- [ ] 没有 `guarantee / guaranteed / we accept / we can supply … immediately`
- [ ] 没有承诺未经确认的单证（`Form E will be provided`、`SGS report attached` 之类）
- [ ] 所有占位符都在 `reply.json.placeholders` 里有登记，且都有 `owner`
- [ ] 回复里的公司名、签字人是 `‹…›` 占位或客户提供的原文，**不是编的**
- [ ] 语气（formal / friendly-professional / concise-direct）与客户层级匹配
- [ ] 主题行不带占位符、不带全大写、不带 `Urgent`

## D. 润色层（如有自写稿）

- [ ] 改动清单逐条给出"原文 → 改后 → 理由（语言/清晰度/语气）"
- [ ] 改动清单里**没有一项**增加新承诺（新增数字、新增条件、新增"保证"）
- [ ] 事实值（数量/规格/港口/币种）零改动
- [ ] 输出"新增承诺检查：无 / 发现 N 处已回退"

## E. 禁止项

- [ ] 没有对询盘真实性、客户质量、成交可能性打分/分级
- [ ] 没有给出参考价、区间价、建议价、市场价
- [ ] 没有替客户补公司全称、税务号、地址
- [ ] 没有把"我方通常做法"写成"客户要求"

## F. 产物层

- [ ] HTML 单文件、离线可开、中文字体回退正常、左原文右字段、点击字段能定位
- [ ] Excel 7 表齐全，缺失项黄色高亮，原文列为原语言
- [ ] MD 独立可复制（不依赖 HTML/Excel）
- [ ] 所有产物带"模拟案例"标注（示例/演示场景）
- [ ] 文件名不含非法字符，中文路径在 Windows 下可打开

## 一键自检

```bash
$PY scripts/selfcheck.py fields.json reply.json --html 询盘审阅板.html --xlsx 询盘工作簿.xlsx --md 回复.md
node scripts/selftest_workbench.mjs 询盘审阅板.html
```

`selfcheck.py` 退出码：0 = 通过；1 = 有 ERROR；2 = 仅 WARN。
