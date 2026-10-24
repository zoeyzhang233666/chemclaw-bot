# 演示数据与真实数据的边界（Disclosure template）

演示文件的作用是让用户看到成品长什么样、以及规则如何生效；它**不能被当作真实报价使用**。
真实报价只能来自用户确认过的商务信息。两层数据必须一眼可分。

## 1. 演示数据（examples/ 与 dist/examples/）

| 位置 | 标记方式 |
|---|---|
| 公司名 | 一律带 `(SIMULATED DEMO)` 后缀 |
| 邮箱 | `@example-demo.invalid`（`.invalid` 是保留域名，永远不会发出邮件） |
| 电话 | `+86 000 0000 0000 (Simulated)` 等明显占位号码 |
| 税号 | `USCI SIMULATED-0000000000` / `GSTIN SIMULATED00A0A0Z0` |
| 银行账号 | **不出现任何数字**，只显示 `[ BANK DETAILS TO BE CONFIRMED … ]` |
| 价格 | 可以是具体数字，但带"演示"标记（便于演示计算），且文件带头水印 |
| 文档纸面 | 斜向水印 `SIMULATED DEMO / NOT FOR TRADE USE` |
| 页脚 | `Draft — not a valid offer` |
| JSON | `meta.dataClass = "SIMULATED — DEMO DATA / 模拟演示数据"` |
| Excel | 00_Cover 页顶部红色声明 + 每个数据页页眉声明 |

## 2. 真实数据（用户自己的 case）

| 位置 | 要求 |
|---|---|
| `meta.dataClass` | `"USER-CONFIRMED"` |
| 公司名/地址 | 与营业执照、对外合同一致（英文） |
| 价格 | 用户明确确认（`amountState:"confirmed"` + `amountConfirmedValue`） |
| 金融机构 | 仅当用户书面确认账号后才可显示 |
| 水印 | 关闭（`view.watermark:false`），页脚 `Original` |
| 状态 | `FORMAL`，且 `review.name` / `review.signatoryTitle` 已填 |

## 3. 切换清单（从演示到真实）

```
[ ] 新建 case 文件（不要直接改 examples 里的演示文件）
[ ] meta.dataClass 改为 USER-CONFIRMED，caseId 换成本单号
[ ] 卖/买双方全部替换为真实英文信息，删除所有 (SIMULATED DEMO)
[ ] 商品：真实品名、CAS、规格、HS、原产地（向技术/单证确认）
[ ] 数量与单价：只用客户已确认的数字；改完重新确认价格
[ ] 贸易术语：规则 + 2020 + 指定地点三要素齐全
[ ] 银行：填占位，等卖方书面确认后再打开显示开关
[ ] 检查页清零错误，逐条处理黄提示
[ ] 复核人签字 → FORMAL → 导出 Original
```

## 4. 对外发送前的一句话

> "Attached is our [Quotation / Proforma Invoice] No. QT-xxxx. Prices are valid until yyyy-mm-dd.
> Bank details will be confirmed separately by our finance department."

这句话不涉及任何未经确认的账号或条款，可安全随附。

## 5. 给内部同事的提示

* 演示文件可以直接发给同事看样式，但**不要发给客户**。
* 若客户看到演示文件里的数字，请立即说明这是样例，并以正式件为准。
* 任何"先把账号填上一个看看效果"的做法都禁止——占位符本身就是正确效果。
