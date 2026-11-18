# 化学品标准化 · 品名 / CAS / 规格 / HS / 单证

抽取解决"客户说了什么"，标准化解决"客户说的那个东西，在我们系统里叫什么"。
**标准化的每一步都必须可回查**，否则不如不做。

## 1. 品名标准化三步

1. **形态先拆出来**：`dense granular` / `light powder` / `flake 98%` / `pearl` / `prill`。
   形态词直接决定产品线，`soda ash` 三个字不能定型。
2. **落到标准名**：`Soda Ash Dense (Sodium Carbonate, Dense)`、`Caustic Soda Flake`、`Urea Granular (Prilled)`。
3. **保留别称表**：客户下一封邮件可能换词（`natrium karbonat`、`carbonato de sodio`、`soude`），
   别称进 `synonyms`，下次命中更快。

常见别名对照（节选，完整见 `products/*.json`）：

| 英文 | 中文 | 印尼语 | 越南语 | 西班牙语 | CAS |
|---|---|---|---|---|---|
| Soda ash (dense / light) | 纯碱（重质/轻质） | soda abu / natrium karbonat | tro soda | ceniza de sosa / carbonato de sodio | 497-19-8 |
| Caustic soda (flake / pearl / liquid) | 烧碱（片碱/粒碱/液碱） | soda api | xút vảy (NaOH) | soda cáustica | 1310-73-2 |
| Urea (granular / prilled) | 尿素 | urea | phân urê | urea | 57-13-6 |
| Titanium dioxide | 钛白粉 | titanium dioksida | titan đioxit | dióxido de titanio | 13463-67-7 |
| Polyvinyl chloride | PVC | PVC | nhựa PVC | cloruro de polivinilo | 9002-86-2 |

## 2. CAS 号红线

**CAS 只能来自三个来源，并且必须记来源：**

| 来源 | 写法 | 可信度 |
|---|---|---|
| 客户原文 | `cas.source = "customer"` + 原句 | 最高（客户若写错，仍以客户原文为准并提示核对） |
| 我方产品资料 / COA / SDS | `cas.source = "our_docs:<文件名>"` | 高 |
| 权威库查证 | `cas.source = "verified:<库名/URL> <日期>"` | 高 |

禁止做法：

- ❌ 翻译品名后凭记忆填 CAS。典型事故：客户写 `brown fused alumina`，被"标准化"成 `aluminium oxide 1344-28-1`——
  棕刚玉主成分虽为 Al₂O₃，但它是混合物，不是该 CAS 化学品，出口归类与 SDS 都会错。
- ❌ 同一形态不同 CAS 的混填：`caustic soda flake 1310-73-2` 与 `caustic soda solution 1310-73-2` 同 CAS 但危险品/包装不同。
- ❌ 查不到就猜一个"看着像"的号。查不到就留空，写 `待我方产品资料确认`。

标准表述：

```
CAS No.: 497-19-8 (source: verified via Wikidata Q190227 / PubChem CID 10340, 2026-10-19)
```

## 3. 规格标准化

- **只抄客户原话**：`Na2CO3 ≥ 99.2% min`、`Fe (as Fe2O3) ≤ 0.003%`、`+80 mesh ≥ 75% min`、`bulk density 0.95–1.10 g/cm3`。
- 客户只给等级词（`industrial / standard / glass grade`）→ `ambiguous`；
  可以附「我方常规规格，请确认」但必须明确标为我方建议，且该段不得写成客户要求。
- 客户给的规格与国标冲突（`Na2CO3 98%` 但要求 `food grade`）→ 提出来问，不建议自行调和。
- 规格书/TDS 只作附件引用，不覆盖客户文字要求。

**纯碱（dense）常见指标框架**（仅作参考框架，不代表任何一家的实际能力）：

| 项目 | 典型区间 | 客户常见写法 |
|---|---|---|
| Na₂CO₃ | ≥ 99.2% | `Na2CO3: 99.2% min` |
| Fe | ≤ 0.003% | `Fe: 0.003% max` |
| 粒度 | +80 mesh ≥ 75% | `particle size +80 mesh min 75%` |
| 堆密度 | 0.95–1.10 g/cm³ | `bulk density 1.0 g/cm3` |
| 氯化物 (NaCl) | ≤ 0.7% | `chloride 0.7% max` |
| 硫酸盐 | ≤ 0.03% | `sulphate 0.03% max` |
| 水分/烧失 | ≤ 0.2% / ≤ 0.5% | `moisture 0.2% max` |

## 4. HS 编码（只给候选，不给结论）

出口归类涉及税则号列、加工方法、纯度、包装，属报关行/货代最终确认事项。
本技能只允许输出**候选**并标注"待报关行确认"：

- 纯碱（碳酸钠）：`2836.20` 项下候选；
- 烧碱（氢氧化钠固/液）：`2815.11` / `2815.12` 候选。

**不得**在给客户的邮件里写 HS 编码，除非客户明确询问且我方已有报关结论（此时也必须写"subject to final classification by our customs broker"）。

## 5. 单证集（DocSet）标准化

把客户的零散要求整理成固定单证名，避免"客户说 COA、我们回 Analysis"这种来回：

| 标准名 | 别称/写法 | 谁出 |
|---|---|---|
| COA (Certificate of Analysis) | 质检单、分析报告、Certificate of Quality | 我方质检 |
| SDS (Safety Data Sheet) | MSDS | 我方/供应商，需对应语言版本 |
| TDS (Technical Data Sheet) | spec sheet、产品规格书 | 我方技术 |
| CO (Certificate of Origin) | 原产地证、COO | 贸促会/海关 |
| FORM E | ACFTA 优惠原产地证 | 贸促会/海关 |
| IMO/DG Declaration | 危险品声明、MSDS + DG 申报 | 货代 |
| Third-party inspection | SGS / BV / Intertek / CIQ | 第三方，费用另议 |
| Packing List / Invoice / B/L | 常规装运单证 | 我方 + 船公司 |

规则：**只有客户明说 + 我方确认能做**的单证，才写进回复的"documents we will provide"。
其余进 `documents_to_confirm`（给客户看：我们确认后再答复）或内部清单。

## 6. 危险品属性（别乱标）

| 产品 | 一般情况 | 注意 |
|---|---|---|
| 纯碱 | 非危险品；刺激性与粉尘防护见 SDS | 某些国家港口对碱性粉尘有作业要求 |
| 烧碱（固） | UN 1823，Class 8，PG II | 包装必须有 UN 认证，普通 PP 袋不行 |
| 烧碱（液） | UN 1824，Class 8，PG II/III | 罐箱/槽船需 IMDG 申报 |

回复里若涉及危险品，只写客户已提的+我方确认的，不自行判定"非危险品无需单证"。
