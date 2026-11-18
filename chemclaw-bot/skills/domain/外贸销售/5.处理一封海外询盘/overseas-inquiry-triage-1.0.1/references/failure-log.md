# 失败日志 · 输出不对劲时先看这里

## 症状 → 根因 → 改法

| 症状 | 根因 | 改法 |
|---|---|---|
| 邮件里出现了具体美元金额 | 为了"看起来完整"填了占位价 | 一律占位符；`selfcheck.py` 的价格正则必须零命中 |
| 回复承诺了 `delivery within 30 days` | 把行业常规当客户要求 | 交期只能占位符；天数正则零命中 |
| 把 `CNF` 直接写成 `CIF` | 术语混用 | 术语与地点分开抽；`CNF→CFR` 要保留原词说明 |
| 客户写 `industrial grade`，回复给出 `99.2%` | 拿我方常规当客户规格 | 等级词 → `ambiguous`；附我方建议必须标"for your confirmation" |
| 把 `L/C` 当完整付款条件 | 只抓了关键词 | 付款要拆类型/期限/开证行/保兑 |
| 印尼客户 `Jakarta` 被当成港口 | 地理常识缺失 | 标注 `Tanjung Priok (Jakarta)`，请客户确认 |
| 把 `3,000 MT/year` 当首单量 | 数量不拆维度 | 试单/年量/单批量三分 |
| 给多家客户用同一模板但细节未改 | 批量回复 | 每条字段都有 source，模板只替换变量 |
| 客户是印尼本地贸易商却被写成"玻璃厂" | 从"glass industry"推公司类型 | `buyer_type` 只能 `stated` 或 `missing` |
| 翻译后 CAS 号变了 | 用模型记忆填 CAS | CAS 三来源规则；查不到留空 |
| 润色后从"please consider"变成"we guarantee" | 润色时升级承诺 | 承诺扫描 + 改动清单逐条回退 |
| 中文简报里出现"该客户成单概率较高" | 越界 | 本技能禁止任何概率/评分，删除 |
| 客户发来的是西班牙语，字段全空 | 锚点词表只有英文 | 用 `references/extraction-rules.md` §2 多语言锚点；仍不行则人工出中文/英文双栏 |
| HTML 打开右侧字段空白 | `__DATA__` 注入失败 / JSON 里有 `</script>` | 注入前转义 `<`；用 `selftest_workbench.mjs` 验 |
| Excel 里原文换行被截断 | 行高没按字数算 | `build_xlsx.py: row_height()` |
| 客户提到"form E"但只是问有没有 | 把问句当要求 | 「问」≠「要」；进 `documents_to_confirm` |
| 邮件签名里的公司全称被缩写成 `PT Glassworks` | 只抓了第一行 | 签名块整体解析，取含 `PT/CV/Ltd/Inc/GmbH` 的最长串 |
| 把客户 WhatsApp 截图里的"OK"当成接受价格 | 即时消息≠合同 | 价格确认必须有邮件/PO/L/C |

## 已发生过的真实事故（脱敏）

1. **棕刚玉 CAS 事故**：客户询 `brown fused alumina`，业务员"标准化"成氧化铝 CAS 1344-28-1，
   报出去后客户做 SDS 备案被退。教训：混合物不等于 CAS 单体；查不到就不填。
2. **CIF 变 CFR**：销售把客户要的 `CIF Semarang` 回成 `CFR Semarang`（省了保费），
   客户签合同时发现没保险，反过来索赔运费差额。教训：术语不许"优化"。
3. **年量当首单**：客户 `5,000 MT/year, trial 200 MT`，报价按 5,000 MT 的阶梯价报出去，
   首单 200 MT 时单价撑不住。教训：报价数量与商务年量必须双列。
4. **"as usual documents"**：客户说单证照旧（指去年那份 FORM E），新业务员回复"常规单证齐全"却出了普通 CO，
   客户清关多缴关税。教训：单证必须逐项列名并回查历史。

## 报告问题的格式

```
[症状] 邮件里出现 USD 215/MT
[证据] 回复_客户.md L18
[根因] fields.price 被当作已确认
[修复] 改占位符 ‹PRICE_DENSE_CFR_SEMARANG›；selfcheck 加 USD 正则
[复测] selfcheck.py 0 error
```
