# AGENTS.md · 给 Agent 的接入契约

本文件写给**调用本技能的 agent 或自动化流程**，不是写给人看的操作手册。
人类请看 `README.md` / `INSTALL.md`。

---

## 0. 一句话

**输入一封询盘（任意语言、任意格式），输出四件东西：有依据的字段表、缺口清单、待确认问题、零承诺的英文回复。**
中途不许产生价格、不许产生商务承诺、不许给客户打分。

---

## 1. 必须按顺序执行

```
① 素材清点        → 带编号的素材块（素材NN），每条记录 source_id / locator
② 八类字段抽取    → 64 个字段，每个值三态：stated / missing / ambiguous
③ 三桶分级        → A 报价前必须确认 / B 可带假设 / C 我方内部定
④ 缺口 → 问题     → 只问 A 类缺口 + 真歧义，≤6 条，封闭式问句
⑤ 回复渠道选择    → A_confirm（默认）/ B_quote_structure / C_sample / D_docs_only
⑥ 生成英文回复    → 价格与商务承诺一律占位符
⑦ 交付            → HTML 审阅板 + XLSX 工作簿 + MD 草稿 (+ 中文简报)
⑧ 润色通道        → 仅在用户已写稿时启用；只改语言
```

**顺序不许反。** 先写邮件再倒推字段，缺失项一定会被"行文需要"填上——这是本技能存在的原因。

---

## 2. 输入契约

| 可接受 | 处理 |
|---|---|
| `.eml` / `.txt` / 邮件正文转贴 | 保留 Date / From / To / Subject / 正文 / 签名 |
| 转发串（多轮） | 按 `From:…Sent:…` 切块，**只有最新一轮是有效数据**，旧轮留痕 |
| 合并素材 `.md` | 用 `素材01` / `素材02` 标记分块 |
| 聊天截图 OCR / RFQ 表格 / 招标文件 | 先转成逐行文本再入流水线；识别不了的标 `unreadable` |
| 用户已写好的英文稿 | **不进抽取通道**，进 ⑧ 润色通道 |

必须先向用户确认的只有一件事：**这封邮件是客户原文，还是转述/模拟？**
模拟件必须在所有产物里标注「模拟」。

---

## 3. 输出契约

```jsonc
// 01_标准化字段.json
{
  "meta": { "inquiry_no": "...", "customer": "...", "inquiry_date": "...", "simulation": true },
  "fields": {
    "qty_trial": {
      "key": "qty_trial", "label_cn": "试单量", "cat": "D", "bucket": "A", "affects_quote": true,
      "value": "300 MT", "status": "stated",          // stated|missing|ambiguous|assumed|internal
      "confidence": "high",                            // 只表示"我读得准不准"
      "source_id": "S01", "quote": "Quantity: 300 MT for the first order",
      "lang": "en", "locator": "S01:L5",
      "note": "", "assume": "", "confirmed_by": ""
    }
  },
  "summary": { "stated": 28, "missing": 30, "ambiguous": 6, "assumed": 0 },
  "blocking_fields": ["payment", "port_load", "..."],
  "can_quote": false,
  "snippets": [{ "id": "S01", "title": "客户邮件", "lines": ["..."] }]
}

// 02_英文回复草稿.json
{
  "channel": "A_confirm", "tone": "friendly-professional", "template": "reply_A_confirm",
  "subject": "Re: Inquiry - Dense Soda Ash - PT Glassworks Nusantara - CFR Semarang",
  "body": "... ‹PRICE_PER_MT_CFR_SEMARANG› ...",
  "placeholders": [{ "key": "PRICE_PER_MT_CFR_SEMARANG", "label_cn": "单价", "owner": "销售",
                     "status": "open", "used": true }],
  "questions_used": ["..."],
  "commitment_scan": [], "price_scan": []
}
```

Schema 见 `schemas/fields.schema.json`、`schemas/reply.schema.json`。

---

## 4. 十条红线（违反即视为任务失败）

1. 不产生**任何价格**（含默认价、参考价、区间价、历史价、"大约"）。
2. 不承诺**库存 / 船期 / 交期 / 账期 / 单证能力 / 认证 / 样品费**。
3. 不由模型记忆填 **CAS / EC / HS**；只能来自客户原话、`products/` 画像或权威库，并记录来源与查证日期。
4. 不把**年量**当首批量、不把 **L/C 数量**当试单量。
5. 不把 `CFR` 写成 `CIF`；术语与地点分开抽；`FOB` 后面的地点必须是**装运港**，客户写买方港口要标冲突。
6. 不把"出口常规做法"当成客户要求（`COA/MSDS will be provided` 这类句子未经确认不得出现）。
7. 不给**询盘真实性**或**成交可能性**打分，不出现 A/B/C 客户分级、可信度百分比。
8. 抽取不到就留空（`missing`），不"取个常见值"；不确定就 `ambiguous`。
9. B 类假设只能在渲染层出现，且必须带 `(our assumption – to be confirmed)`。
10. 润色不改事实值（数量/规格/港口/币种），不升级承诺（`can supply` → `guarantee supply` 是禁止的）。

---

## 5. 占位符协议

- 形式：`‹KEY›`，Unicode U+2039 / U+203A（**不是** `<` / `>`，避免与 HTML 冲突）。
- 命名：`PRICE_PER_MT_<TERM>_<PORT>`、`QUOTE_VALIDITY`、`LEAD_TIME_FOR_OFFER`、`SHIPMENT_TIME`、
  `PACKING_PROPOSAL`、`PAYMENT_TERMS`、`SAMPLING_POLICY`、`SIGNER_NAME`、`OURCOMPANY_NAME` …
- 术语未定时统一用 `PRICE_PER_MT_TERMS_TBC`，**不许**拼出 `FOB Hải Phòng` 这种错误口径。
- 清单只登记**正文里真正出现**的占位符。
- 未确认的占位符不得进入可发送版：`build_md.py --pack` 会以 exit 3 拒绝。

---

## 6. 校验：交付前必须跑

```bash
python scripts/selfcheck.py <示例目录>       # 12 项：齐全/依据/无承诺/占位符/模拟声明/无外链
python scripts/selfcheck.py --skill .        # 包结构 + 无临时文件
node scripts/selftest_workbench.mjs <html>   # 24 项：页面功能（可选，需浏览器）
```

任何一项 FAIL 都**不许交付**，先修再交。

---

## 7. 交接给下游场景

HTML 第 ⑥ 页会导出 `handoff` JSON，字段干净、可直接喂给下游：

| 下游场景 | 需要的字段 |
|---|---|
| 算出口报价 | product_std, spec_*, qty_trial, incoterm, incoterm_place, port_dest, pack_std, currency |
| 核验海外询盘公司 | buyer_name, buyer_country, contact_*, buyer_address, website |
| 查产品出口要求 | cas, hs_candidates, un_number, dangerous_goods |
| 建客户档案 | 全部 A 类 + H 类背景字段 |

**交接时如实标注缺口**：下游看到 `status=missing` 必须知道那是"客户没说"，不是"没有要求"。

---

## 8. 语气与模板

| 语气 | 用在 |
|---|---|
| `formal` | 大客户、招标、政府/国企、首次接触高层 |
| `friendly-professional` | **默认**，绝大多数化工 B2B 询盘 |
| `concise-direct` | 老客户、WhatsApp 转邮件、已来回两三轮 |

| 模板 | 用途 |
|---|---|
| `reply_A_confirm` | **默认**：缺关键参数，先确认再报价 |
| `reply_B_quote_structure` | A 类已齐，价格已由我方确认 |
| `reply_C_sample` | 客户寄样/索样为主 |
| `reply_D_docs_only` | 只要单证/TDS/COA，暂不报价 |

---

## 9. 出错时

先看 `references/failure-log.md`（症状 → 根因 → 改法），再改脚本，改完跑 `selfcheck.py` + `selftest_workbench.mjs`。
**不要靠手工改 HTML 里的数据来"让它看起来对"**——数据来自 JSON，改模板会被下次生成覆盖。
