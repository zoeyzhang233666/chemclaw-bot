# 示例

两个**完整跑通**的样例 + 一个空白骨架。每个样例目录里都同时放着"输入"和"产物"，
方便对照看：客户原话是怎么变成字段、字段是怎么变成邮件的。

| 样例 | 场景 | 语言 | 特意埋的坑 |
|---|---|---|---|
| `example-1-id-soda-ash-dense` | 印尼玻璃厂 · 重质纯碱 · CFR Semarang | 英文 | 缺付款细节、有效期、样品要求、包装偏好；年量与首单量并存 |
| `example-2-vn-caustic-soda-vi` | 越南经销商 · 片碱 · 危化品 | **越南语** | `FOB Hải Phòng` 港口冲突、L/C 未定类型、25 kg 与 1000 kg 包装冲突、FORM E 能力问句 |
| `_skeleton` | 空白骨架 | — | 换品类时整目录复制 |

---

## example-1 · 印尼玻璃厂 · 重质纯碱（主案例）

**客户：** PT Glassworks Nusantara（Semarang，玻璃容器与浮法玻璃）· Budi Santoso
**询盘原文：** `input/询盘邮件.eml`（英文，2026-10-19）

关键参数（客户**说了**的）：

| 字段 | 客户原话 |
|---|---|
| 产品 | Dense Soda Ash |
| 规格 | Na2CO3 99.2% min; Fe 0.003% max; +80 mesh 75% min |
| 数量 | 300 MT first order, approx. 3,000 MT/year |
| 交付 | CFR Semarang, Indonesia |
| 付款 | L/C |
| 单证 | COA, SDS, TDS |

客户**没说**的（正是回复要问的）：报价有效期、L/C 类型与有效期、包装偏好、样品要求、
装运港、是否需要原产地证/第三方检验、公司注册全称与收货地址。

**产物：** `04_询盘审阅板.html`（双栏审阅板）、`05_询盘处理工作簿.xlsx`、`03_英文回复草稿.md`、
`06_中文缺口简报.md`、`01/02` JSON、`07_运行自检.txt`。

运行：

```bash
python scripts/make_example.py examples/example-1-id-soda-ash-dense
```

---

## example-2 · 越南经销商 · 片碱（多语言 + 冲突检测）

**客户：** Công ty TNHH Hóa chất Hạnh Phát（Hải Phòng，纸张与水处理工厂的分销商）· Nguyen Thi Mai
**询盘原文：** `input/询盘邮件.eml`（**越南语**，2026-11-03）

这个样例专门用来演示"客户说了，但说错了 / 说得不完整"时会发生什么：

| 客户原话 | 脚本判定 | 为什么 |
|---|---|---|
| `Điều kiện giao hàng: FOB Hải Phòng` | `incoterm = ambiguous` | FOB 后面必须是**装运港**（中国港口），客户写的是买方港口 → 追问 "FOB China 还是 CFR/CIF Hải Phòng" |
| `Thanh toán: L/C` | `payment = ambiguous` | L/C 不等于"即期不可撤销保函"；类型/有效期未定 |
| `25kg/bao` 与 `jumbo 1000kg` 同时出现 | `pack_std = ambiguous` | 两种包装 → 必须分别报价，不能替客户选 |
| `cần C/O form E ... có cung cấp được không?` | `doc_form_e = ambiguous` | 这是**能力问句**，不是要求；回复只能说"按核实结果确认" |
| `40 tấn` / `800 tấn/năm` | 分别落到 `qty_trial` / `qty_annual` | 越南语数字锚点；首单量与年量分字段 |
| 无买方公司英文名 | `buyer_name` 仍能识别 | `Công ty TNHH …` 公司名前缀识别 |

**价格占位符**在本例会降级成 `‹PRICE_PER_MT_TERMS_TBC›`——因为术语与港口冲突，
不允许拼出 `FOB Hải Phòng` 这种错误口径。

---

## 看产物时的建议顺序

1. 先打开 `04_询盘审阅板.html`，点右栏任意字段 → 看左栏原句是否高亮到**同一行**；
2. 切到「缺失与歧义」页 → 确认红色是"客户没说"、黄色是"说了但不唯一"；
3. 切到「待确认问题」页 → 每条问题点一下，都能跳回它对应的原句；
4. 切到「英文回复草稿」页 → 换语气、换模板，看占位符跟着变；正文里**不该有任何数字价格**；
5. 切到「已写稿润色」页 → 粘一段带 `We can supply 40 MT immediately` 的稿子，看它被拦下；
6. 切到「下一步场景」页 → 导出交接 JSON，这是给报价/核验场景的输入。

---

## 关于「模拟」

两个样例的公司、联系人、电话、数量、价格参数**全部虚构**，`.eml` 里带 `X-Demo-Notice: SIMULATED` 头，
HTML / Excel / MD 三处都标注「模拟案例」。换成真实询盘时，把标记去掉即可——但请确认你能对内容负责。
