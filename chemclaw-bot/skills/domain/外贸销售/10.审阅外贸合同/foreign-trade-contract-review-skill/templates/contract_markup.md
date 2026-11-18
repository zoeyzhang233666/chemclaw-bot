# 合同标记语法

目的只有一个：**给合同的每个段落一个稳定 ID**，让风险提示能精确指回原文。
标记不改变合同内容，也不做排版。

---

## 基本规则

- 一行一个标记
- 标记以 `@@` 开头，后接标签名，空格后接内容
- 空行会被忽略
- 编码 UTF-8；保存时**不要带 BOM**（BOM 会导致第一行解析失败）

---

## 标签表

| 标签 | 用途 | 解析成 | 生成的 id |
|---|---|---|---|
| `@@DOC 编号` | 文档标识（首行） | — | — |
| `@@BANNER 文本` | 顶部醒目提示（如「模拟合同」） | banner | `banner` |
| `@@TITLE 文本` | 合同大标题 | — | — |
| `@@META 键 \| 值` | 元信息行（编号、日期、地点等） | meta | — |
| `@@PARTIES` | 当事人区开始标记 | — | — |
| `@@H1 文本` | **章**（如 `ARTICLE 6 — PAYMENT`） | h1 | `art-<slug>` |
| `@@H2 文本` | **条**（如 `6.1 Payment method`） | h2 | `clause-<slug>` |
| `@@P 文本` | 正文段落 | p | `p-<slug>-<NNN>` |
| `@@CONT 文本` | 上一段的续行 | 并入上段 | — |
| `@@TABLE` | 规格表开始 | table | `tbl-<slug>` |
| `@@TR 单元格1 \| 单元格2` | 表格行，`\|` 分隔 | — | — |
| `@@ANNEXES` | 附件区开始 | — | — |
| `@@ANNTITLE 文本` | 附件标题 | annex-title | `ann-<slug>` |
| `@@EXEC` | 签署区开始 | — | — |
| `@@EXCLEFT` | 左侧签署栏开始 | exec-col | `p-exec-left` |
| `@@EXCRIGHT` | 右侧签署栏开始 | exec-col | `p-exec-col` |
| `@@EXCLINE 文本` | 签署栏内一行 | exec-line | `xl-<NNN>` |
| `@@END` | 结束 | — | — |

> `@@BANNER`、`@@TITLE`、`@@META`、`@@PARTIES`、`@@ANNEXES`、`@@END`、`@@DOC`
> 只是结构标记，不产生独立可锚定的块——它们的信息进入报告的页头区。

---

## 最小示例

```
@@DOC TEST-001
@@BANNER SIMULATED — for testing only
@@TITLE SALE CONTRACT

@@META Contract No. | TEST-001
@@META Date | 1 January 2026

@@PARTIES

@@H1 ARTICLE 1 — PRODUCT
@@H2 1.1 Description
@@P The Seller sells and the Buyer buys 1,000 MT of heavy soda ash.
@@P Specification is set out in Annex A.
@@TABLE
@@TR Parameter | Value | Method
@@TR Na2CO3 | min. 99.2% | ISO 740

@@H1 ARTICLE 2 — PAYMENT
@@H2 2.1 Payment method
@@P The Buyer shall pay by irrevocable Letter of Credit at sight.

@@ANNEXES
@@ANNTITLE ANNEX A — SPECIFICATION
@@P As per the table in Article 1.

@@EXEC
@@EXCLEFT
@@EXCLINE For and on behalf of the SELLER
@@EXCLINE Signature: ____________
@@EXCRIGHT
@@EXCLINE For and on behalf of the BUYER
@@EXCLINE Signature: ____________

@@END
```

---

## 写好标记的几条经验

1. **一条一句。** 一段里塞三句话，定位后读者找不到重点。
   原文本身就是一个大段的，用 `@@CONT` 拆行。
2. **`@@H1` 只给「章」，`@@H2` 只给「条」。** 层级乱了，条款索引就没法用。
3. **表格用 `@@TR` 以 `|` 分隔，单元格内的 `|` 请改写为全角 `｜` 或去掉。**
4. **不要手工编 id。** id 由脚本生成；手工编号会在改合同后失效。
5. **抄录要逐字。** 因为 `quote` 校验是逐字比对；抄错一个字，
   后续所有引用都会对不上（这是好事，能逼出错误）。
6. **扫描件先 OCR。** OCR 出来的乱码不要直接进标记——人工校对一遍再解析。

---

## 解析与校验

```bash
python scripts/parse_contract.py contract_source.txt contract_parsed.json
```

输出会打印块统计：

```
blocks=221 kinds={'h1': 18, 'h2': 67, 'p': 130, 'exec-col': 2, 'annex-title': 3, 'table': 1}
articles=21
clauses=67
```

若出现 `unknown tag`，说明标签拼错或有多余空格。
若 `articles` 或 `clauses` 为 0，说明没写 `@@H1`/`@@H2`。
