# ⚠️ 模拟文件 · SIMULATED DOCUMENT — 非真实报价单

> **本文件由核验方法演示生成，用于测试「合同主体 / 收款主体 / 联系方式」一致性检查逻辑。**
> **任何真实企业均未向我方发出本报盘，也未提供本文件。文件中的抬头、金额、账号、人名、邮箱均为虚构，仅「被冒用名称的法定信息」参照公开资料，不构成对该企业的任何主张。**
> 真实采购中，请以供应商实际提交的原件扫描件替换本文件，并保留原件时间戳。

---

# PROFORMA INVOICE — [SIMULATED]

| | |
|---|---|
| **PI No.** | PKM/MEG/2026-1012（模拟） |
| **Date** | 12 October 2026（模拟签发日） |
| **Valid Until** | 27 October 2026 |
| **Seller** | **ARABIAN PETROCHEMICAL COMPANY (PETROKEMYA)**<br>Al Jubail Industrial City, Eastern Province, Kingdom of Saudi Arabia<br>Tel: +966 13 XXX XXXX · Email: sales@petrokemya-sabic.com |
| **Buyer** | [买方名称待填] · [买方地址待填] · China |
| **Payment Terms** | 30% T/T advance, 70% against B/L copy |
| **Currency / Incoterm** | USD / **CFR** [Chinese main port] |
| **Shipment** | November 2026, from Al Jubail, Saudi Arabia |
| **Country of Origin** | Saudi Arabia |

### Goods

| # | Description | Spec | Qty | Unit Price (USD/MT) | Amount (USD) |
|---|---|---|---|---|---|
| 1 | Monoethylene Glycol (MEG) — Fiber Grade | Purity ≥99.9 wt%, DEG ≤0.08 wt%, Colour ≤10 APHA | 5,000 MT | 000.00 | 0,000,000.00 |
| | | | | **Total CFR** | **0,000,000.00** |

> 说明：演示件故意不填真实价格，避免被误读为市场报价。

### Beneficiary / Bank Details

| Field | Value |
|---|---|
| Beneficiary Name | **GULF MERIDIAN TRADING FZE** |
| Beneficiary Address | *(blank)* |
| Bank Name | [Bank name withheld in simulation] |
| Account No. | 0000000000000（模拟） |
| SWIFT | XXXXAEXX |
| IBAN | AE00 0000 0000 0000 0000 000（模拟） |
| Bank Country | United Arab Emirates |

### Remarks

1. Partial shipment not allowed. Transshipment under carrier's option.
2. Quality as per manufacturer's COA at load port.
3. This PI is governed by the laws of England and Wales. **（原文如此）**

**For and on behalf of ARABIAN PETROCHEMICAL COMPANY (PETROKEMYA)**

Electronic stamp image only — **no printed name, title, or signature**.
`[SEAL.png]`

---

## 核验批注（不属于 PI 内容，供核验人员使用）

| 检查点 | 结论 | 说明 |
|---|---|---|
| 卖方名称与页眉是否一致 | ✓ | 抬头与公开法定名称一致（需以 E04/E05 佐证） |
| 是否载明商业登记号 CR | ✗ | 缺 CR 号 → 无法做唯一主体识别（G01） |
| 收款户名是否等于卖方 | ✗ | 收款方为阿联酋 FZE，与沙特卖方不同主体（G02） |
| 收款开户地与卖方注册国 | ✗ | 阿联酋 vs 沙特，需解释资金归集或代理收款 |
| 是否附银行确认函 | ✗ | 未附 → 无法核实账户归属 |
| 签字人姓名 / 职务 | ✗ | 仅有电子章图片，无法验签 |
| 品名 / 规格 / 数量 / 贸易术语 | ✓ | 要素齐全 |
| 联系邮箱域名 | ✗ | `petrokemya-sabic.com` 不是 `sabic.com` 子域（G03） |
| 适用法律 | ⚠ | 沙特卖方 + 中国买方，却约定英格兰法，需对方解释 |

**综合：该模拟 PI 存在 4 项主体一致性缺口。差异本身不构成欺诈认定，但在补齐「付款指令 + 银行确认函 + 关系声明 + 官网回呼」之前不得付款。**
