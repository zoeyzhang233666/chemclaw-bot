# 09 准据法、争议解决与语言版本（第 10 项展开）

> 这是全篇唯一一处「必须交给法务」的地方。商务审查能做的是：
> **把条款读通、把矛盾找出来、把该问的问题问清楚**——而不是判断哪份法适用、条款是否有效。

---

## 1. 三个必须分开的概念

| 概念 | 问题 | 常见错误 |
|---|---|---|
| **仲裁地（seat / legal place）** | 仲裁程序受哪国法院监督 | 与「开庭地点（venue）」混为一谈 |
| **仲裁规则（rules）** | 按哪套程序规则走 | 与仲裁地混为一谈 |
| **准据法（governing law）** | 实体争议用哪国法判断 | 与仲裁地混为一谈 |

三者**可以不同**（如：仲裁地新加坡、规则 SIAC、准据法英国法），但必须**写明且自洽**。

---

## 2. 本案的矛盾：仲裁条款内部打架

第 13.1 条：

> `… shall be finally settled by arbitration administered by the Singapore International Arbitration Centre (SIAC) under the SIAC Rules in Singapore. The seat of arbitration shall be the Dubai International Financial Centre (DIFC).`
> `In respect of matters not covered by the arbitration rules, the laws of the country of the seat shall prevail.`

问题：

1. **「in Singapore」与「seat = DIFC」直接冲突**。开了庭在新加坡、仲裁地却在 DIFC 的写法，实务中会引出「由哪国法院行使监督管辖权」的争议。
2. **兜底条款指向「仲裁地所在国法律」**，而仲裁地本身不明，兜底也就落空。
3. **没有写仲裁庭人数、仲裁语言、仲裁员资格**。

**审查报告该怎么写**：

> ✅ 「第 13.1 条同时约定在新加坡仲裁并约定仲裁地为 DIFC，两处指向不同法域；仲裁地决定由哪国法院监督仲裁程序，也会影响裁决的承认与执行路径。合同未约定仲裁庭人数与仲裁语言。**该冲突属于准据法与管辖判断，需由法务/律师确认其后果与修正方案。**」

而不是：

> ❌ 「该条款因矛盾而无效，应由中国法院管辖。」

---

## 3. 常见仲裁/诉讼结构对照

| 结构 | 写法示例 | 要点 |
|---|---|---|
| 境外机构仲裁 | `SIAC Rules, seat Singapore, in English, 3 arbitrators` | 需评估裁决在对方国家的执行便利性 |
| 中国机构仲裁 | `CIETAC, seat Beijing, in Chinese` | 中国买方最熟悉；对方可能不接受 |
| 香港仲裁 | `HKIAC, seat Hong Kong` | 兼顾中立与执行（《安排》下与内地互认） |
| 诉讼 | `exclusive jurisdiction of the courts of Ningbo, China` | 判决的域外承认执行需看有无条约/互惠 |
| 混合（弊多） | 「仲裁或诉讼由任一方选择」 | 通常导致管辖争议，应避免 |

**「仲裁地 vs 开庭地」说清楚**：仲裁地是一个法律概念（决定监督法院、裁决国籍），开庭地点只是物理地点。合同里只写「in Singapore」而不写 seat，容易被解释为开庭地。

---

## 4. 单方诉讼保留条款

本案第 13.2 条：

> `Notwithstanding the foregoing, the Seller may sue the Buyer in any competent court for the recovery of the advance payment or the balance payment.`

这条给了**卖方单方**在「任何有管辖权的法院」起诉的权利，等于让买方在境内被起诉、同时自己还要去新加坡仲裁。虽然这类条款在某些法域可能被限制，但**不要下结论**，只写：

> 「卖方保留了在任意法院就预付款/尾款起诉的权利，我方须评估在境内应诉的成本与效果；建议删除或限定为『无争议款项且限于指定法院』，**具体效力需法务判断**。」

---

## 5. 准据法：CISG 与国内法

**CISG（《联合国国际货物销售合同公约》）的关键事实**（此类事实必须核实后再写）：

- 营业地在不同缔约国的当事人之间的货物销售合同，公约可能自动适用（第 1 条(1)(a)）。
- 中国在加入时**对第 1 条(1)(b) 作了保留**（声明不受该款的约束），因此「依国际私法规则导致适用某缔约国法」这一路径对中国不适用。
- 沙特阿拉伯**不是 CISG 缔约国**。
- 因此：若卖方是沙特实体，CISG 的自动适用路径不可靠；若卖方是 UAE 实体（UAE 是缔约国，需核对其保留与生效情况），情况不同。
- **当事人可以约定排除 CISG**（第 6 条），也可以用「适用某国国内法」间接排除——但写法要明确。

> ⚠ 以上都需要在报告出具时**核对缔约方名单与保留声明**，并在 `legal_refs` 中记录来源与日期。不要把「我记得 UAE 是缔约国」写进报告。

**报告应写**：「本合同未约定是否适用 CISG。鉴于卖方为 [X] 主体、实际供货可能来自 [Y]，CISG 是否自动适用取决于双方营业地，**需法务确认**；建议在合同中明确『CISG 适用/排除』。」

---

## 6. 语言版本冲突

本案第 14.1 条：

> `This Contract is executed in English and Chinese, both versions being equally authentic. In case of any discrepancy, the English version shall prevail. For the avoidance of doubt, the Chinese version shall prevail for the interpretation of the arbitration agreement.`

三重问题：

1. **「同等有效」+「英文优先」**自相矛盾。
2. **仲裁协议以中文为准**，与实际仲裁语言（未约定，但凭英文文本仲裁）冲突。
3. 若仲裁庭以英文审理，却要按中文文本解释仲裁协议，程序上难以操作。

**应争取**：

- 单一权威文本（通常争取中文或双语一致）。
- 若保留双语，明确：**中文文本为准**，或至少「仲裁协议与责任限制条款以中文为准」。
- 明确译文的提供方与纠错机制。

---

## 7. 语言之外：合同解释的实务提醒

- **标题仅供参考**：`Headings are for convenience only` 的条款常被忽略。
- **可分割性**：某条无效不影响其它条款——这对责任限制条款尤其重要。
- **转让与变更**：卖方能否把合同转给关联方（涉及实际供货主体变化）。
- **通知条款**：地址与联系人，是否接受电子邮件；争议时常因「通知未送达」失权。
- **签署主体**：签署人与营业执照/授权书一致；FZE 等自由区实体要额外核对存续证明。

---

## 8. 核对表

- [ ] 准据法写明（哪国法），是否排除 CISG
- [ ] 仲裁机构/规则写明
- [ ] **仲裁地（seat）**写明，与「开庭地」「机构所在地」区分
- [ ] 「in Singapore」这类措辞是否被误用为仲裁地
- [ ] 仲裁庭人数、仲裁语言、仲裁员资格
- [ ] 临时措施/保全由哪个法院受理
- [ ] 是否存在单方诉讼保留条款
- [ ] 仲裁与诉讼是否重复约定
- [ ] 语言版本：优先文本、译文提供方、仲裁协议语言
- [ ] 通知条款：地址、联系人、是否接受电子邮件
- [ ] 转让限制、可分割性、完整协议
- [ ] 签署主体与营业执照/授权书一致
