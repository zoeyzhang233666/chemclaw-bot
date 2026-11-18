---
name: chem-supplier-qualification
description: Use when a domestic chemical buyer must verify a supplier's licence and regulatory status before purchase — 查询供应商资质证照 / 资质核验 / 供应商证照 / 危化品经营许可证查询 / 易制爆易制毒核查 / 索证清单 — for ANY chemical product (过氧化氢、甲醇、盐酸、烧碱、双氧水、溶剂、树脂…). It (1) identifies the product's hazard and special-control categories from current Chinese catalogues with clause-level citations and explicit "unconfirmed ≠ not applicable" results, (2) derives the licences a supplier needs depending on whether it produces, trades or stores, (3) derives the buyer's own obligations, (4) records publicly available licences with four mutually exclusive states (verified / inconsistent / pending / no public record), validity and scope-coverage comparison, (5) builds a prioritised material-to-request list and a supplier request-letter draft. Delivers a single-file interactive HTML report plus a multi-sheet Excel ledger. Never infers licence status from a company name, business scope, or a missing search hit.
---

# 化学品供应商资质证照核验

面向内贸采购的一句话任务：**「我要向 X 采购 Y，请核实产品监管属性、双方资质、供应商证照是否覆盖，并出索证清单。」**
本技能把这句话拆成可复核的流程，产出**一份能进供应商档案的核验底稿**（HTML）+ **一份能持续维护的台账**（Excel）。

## 一、什么场景用

| 场景 | 用不用 |
|---|---|
| 新供应商准入 / 追加新品类 | 用（本技能） |
| 危险化学品、易制爆、易制毒、重点监管化学品采购 | **必用** |
| 只在比较报价、看行情 | 不用 |
| 已经成交、核对到货 COA vs 规格 | 不用（用 16.核对到货质量分析证书与规格） |
| 想判断供应商「是不是真厂家」 | 先用 5.查供应商是不是真厂家，再用本技能 |

## 二、六条硬纪律（违反任何一条，交付作废）

1. **不得把「查不到」写成「没有」。** 公开检索未发现记录 → 状态只能是 `no_public`（无公开信息），并原样进入索证清单。
2. **不得用名称、经营范围、行业常识推断许可状态。** 「经营范围含危险化学品生产」≠ 有安全生产许可证；「有营业执照」≠ 能卖危化品。
3. **产品定性必须落到条目与条款。** 写清「哪个目录、第几项/第几条、适用条件（如含量阈值）」；只写「属于危险化学品」不合格。
4. **「未确认」不等于「不属于」。** 任一目录未完成逐条比对 → `pending`（待核验），禁止输出「不属于剧毒/不属于易制爆」这类否定结论，除非目录全文核对为凭。
5. **证照状态四态互斥**：`已核验 / 信息不一致 / 待核验 / 无公开信息`；过期以 `已过期` 单列。一份证件不能证明企业整体合规。
6. **全表只有一个时间基准 `as_of`。** 「有效期、剩余天数、是否过期」全部相对它计算；不写「近期」「上个月」。

## 三、流程（P0–P8）

### P0 · 锁定四要素
供应商全称 + 统一社会信用代码（必填，用于主体锁定）；产品名称 + CAS + **浓度/规格** + **用途**；`as_of` 日期。
> 同一 CAS 在不同浓度下可能落入不同目录条目（阈值型条目很多），浓度必须写在采购口径里。

### P1 · 产品身份识别
1. 用 CAS 在现行《危险化学品目录（2015版）》及其**实施指南**中定位条目；注意「溶液」「混合物」的适用条件与 70% 规则。
2. 逐项核对特殊管理类别目录：剧毒标注栏、易制爆名录、易制毒品种目录、重点监管的危险化学品名录、监控化学品、重大危险源（GB 18218）、危险货物运输分类（GB 12268/SDS 第14节）、以及用途型专项（食品添加剂/消毒剂/药用）。
3. 输出 `product.findings`（每条：结论 + 判定 + 依据 + 适用条件）与 `classification_checklist`（逐项打勾）。

### P2 · 判定供应商角色
| 角色 | 核心证照 | 判据 |
|---|---|---|
| 生产企业 | 危险化学品**安全生产许可证** | 有自有装置、自己生产该品种 |
| 生产企业兼销售 | 同上（自产直销通常无需经营许可，但须满足「自产 + 该品种在许可范围」） | 实施指南第三条：改变物质状态后再销售 → 需经营许可 |
| 经营企业 | 危险化学品**经营许可证**（带储存/不带储存） | 不生产，转售他人产品；经营方式须与实际业务一致 |
| 仅物流 | 危险货物道路运输经营许可 + 车辆/人员资质 | 承运人 |
> 许可跟着「活动」走：有无自有储存设施决定「带储存」还是「不带储存」；实际发货工厂必须有生产许可。

### P3 · 判定采购方义务
使用许可（行业目录 + 数量标准双前提）、重大危险源辨识、储存安全条件、购买凭证与身份核验、**易制爆 5 日内流向报备**、出入库台账、运输委托、人员培训。
> 最常见的两个错误：把「安全使用许可证」当成人人必办；或把「购买易制爆品」当成普通采购。

### P4 · 证照查询（公开 + 上传）
按 `references/source-playbook.md` 的顺序查：主管部门公示/政务服务网 > 上市公司公告/信用中国 > 企业官网 > 企业公示系统。每条来源登记为 `E01…En`。
上传件（营业执照、许可证扫描件、SDS）→ 按 `references/ocr-extract-schema.md` 提取字段，并标注字段来源为「上传扫描件」。

### P5 · 有效期与范围比对
- 有效期：用 `qclib.validity()` 相对 `as_of` 计算，180 天内到期必须预警。
- 范围：逐字比对「许可范围是否含本产品、本浓度、本产能」；比对失败就是 `not_cover` 或 `unknown`，不能模糊成「大致覆盖」。
- 主体：签约主体 = 开票主体 = 持证主体 = 实际供货装置归属主体，四者必须一致。

### P6 · 交叉核验
A 侧（证照/供应商材料）× B 侧（主管部门公示）× C 侧（工商身份）。三方对不上即 `mismatch`；只有一方可得 → 只能 `pending`。

### P7 · 索证清单 + 请求草稿
按 P0（不取得不得下单）/ P1（卡合同或首批发货）/ P2（档案完善）分级；每项写「为什么必须索取」+「要确认的具体问题」。再转成可直接发给供应商的邮件/公函草稿。

### P8 · 出报告
写 `data.json` → 跑 `build_all.py` → 得到 HTML + Excel。

## 四、怎么产出

```bash
cd chem-supplier-qualification
python scripts/validate.py examples/hydrogen-peroxide-30/data.json   # 先自检
python scripts/build_all.py examples/hydrogen-peroxide-30/data.json  # 校验+出 HTML+XLSX
```

| 文件 | 用途 |
|---|---|
| `assets/` | 设计系统（CSS/JS），改 `:root` 变量即可换皮 |
| `scripts/qclib.py` | 信用代码校验、有效期计算、四态/覆盖判定——所有"规则"都在这里，改规则只改它 |
| `scripts/render_html.py` | data.json → 单文件交互式 HTML（筛选、抽屉、清单进度、保存核验记录） |
| `scripts/render_xlsx.py` | data.json → 15 页签 Excel 台账（含公式列与下拉校验） |
| `scripts/validate.py` | 把「不得写什么」变成可执行检查（禁用表述、证据链、枚举、主体冲突） |
| `scripts/gen_mock_scans.py` | 生成**明确标注模拟**的扫描件（仅演示用） |
| `templates/data.template.json` | 最小可运行骨架 |
| `references/` | 数据契约、法规与来源手册、判定口径、索证清单方法、OCR 字段、质检闸门 |
| `examples/hydrogen-peroxide-30/` | 主示例：华东供应商 30% 过氧化氢（真实主体 + 真实法规依据 + 缺口保留） |
| `examples/methanol-trading/` | 对照示例：贸易商路径（证明模板不限品） |

## 五、跨品类复用（本技能为何不写死任何一条化学品规则）

- **所有产品知识只存在于 `data.json` 的 `product.findings` / `classification_checklist` 里**，脚本中没有任何"过氧化氢"或"甲醇"字面量。
- 判定结果的三种取值 `confirmed / not_confirmed / pending` 是**方法论**，不是产品结论。
- 换品时：替换 findings 与 checklist、替换 certs（应具备的证照随角色变化）、换 `as_of`。模板与规则不动。
- 参考 `references/regulation-map.md`：它给的是「查哪些目录、去哪个官网查」，而不是「X 属于什么」。

## 六、交付验收（出稿前逐条打勾）

- [ ] 每个产品定性结论都有「目录名称 + 条目/条款号 + 适用条件」
- [ ] 每个「不属于」都有目录全文核对依据；没有就改 `pending`
- [ ] 每张证照：编号/机关/有效期/范围/字段来源/公开状态 齐全；「已核验」必有 evidence_id
- [ ] 有效期相对 `as_of` 计算，临近到期已标黄
- [ ] 主体四者一致性已核（签约/开票/持证/装置）
- [ ] 索证清单 P0 项全部含具体确认问题；草稿可直接发送
- [ ] `validate.py` 0 FAIL
- [ ] 报告里没有「企业无证」「完全合规」「已确认不属于…」这类表述
- [ ] 模拟件已显式标注为 mock，且未使用被核验企业的真实证照字段

## 七、常见坑

| 坑 | 正确做法 |
|---|---|
| 用经营范围证明能卖危化品 | 看许可证「许可范围」逐字比对 |
| 把 ISO 体系认证当准入资格 | 体系认证标注为「参考项/不构成许可依据」 |
| 生产企业直销还硬要经营许可证 | 说明实施指南第三条的例外，但要求「自产声明」闭环 |
| 只有官网证书目录 → 判定「资质齐全」 | 官网自宣 = `pending`，需原件与公示 |
| 看到注销名单里没有 → 判定「证照有效」 | 不在注销名单是弱证据，不等于现行有效 |
| 浓度写「30% 左右」 | 写死「30%（质量分数）」并写入合同与送货单 |

## 八、边界

- 本技能是**资料核验辅助**，不是法律意见，也不替代主管部门公示与证照原件。
- 无法自动获取的内部数据（许可证扫描件、SDS、装置归属、企业信用记录）一律进索证清单，**不得编造**。
- 涉及剧毒/易制爆/易制毒的实际购买，必须由企业 EHS 与属地公安确认操作口径。
