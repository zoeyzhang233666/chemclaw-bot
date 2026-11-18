# 进口折算全部公式（与 `scripts/core.py` 逐行对应）

本文件是公式的**人读版本**。代码为准，此处为解释与推导。
凡本文件与 `core.py` 冲突，以 `core.py` 为准，并立即修文档。

记号：所有金额单位 **元/吨**（除标注 USD 的原始报价），四舍五入到 6 位小数（`r6`）。

---

## 0. 输入

| 符号 | 代码键 | 含义 | 单位 |
|---|---|---|---|
| $P$ | `price_quote` | 海外报价（取区间中值） | USD/t 或 CNY/t |
| $c$ | `currency` | 报价币种，`USD` / `CNY` | — |
| $T$ | `term` | 贸易术语，EXW/FCA/FOB/CFR/CIF/DAP | — |
| $E$ | `fx_usdcny` | 汇率 | CNY/USD |
| — | `purity` | 纯度系数（折纯用） | — |
| — | `gross_weight_factor` | 毛净比（皮重修正） | — |
| $I_o$ | `inland_origin` | 出口国内陆运费 | 原币/t |
| $X$ | `export_clear` | 出口报关杂费 | 原币/t |
| $F$ | `ocean_freight` | 国际海运费 | 原币/t |
| $k$ | `insurance_rate` | 保险加成率（惯例 1.1） | 倍 |
| $r_i$ | `insurance_rate_pct` | 保险费率 | 小数 |
| $D$ | `discharge_fee` | 目的港卸货/港杂 | 原币/t |
| $I_d$ | `inland_dest` | 进口国内陆运费 | 原币/t |
| $U$ | `unload_fee` | 装卸/损耗附加 | 原币/t |
| $t_d$ | `duty_rate` | 进口关税率 | 小数 |
| $t_o$ | `other_tax_rate` | 其他税率（反倾销等） | 小数 |
| $t_v$ | `vat_rate` | 进口增值税率 | 小数（13%） |
| $\lambda$ | `vat_credit_ratio` | 增值税可抵扣比例 | 0~1 |

**汇率处理**：`USD` 报价时 $E$ 为实际汇率；`CNY` 报价时强制 $E=1$（否则人民币价会被再乘一次汇率）。
所有以「原币」计的中间费用都通过 $\text{cny}(x) = x \cdot E$ 折成人民币。

---

## 1. 术语屏蔽（去重的核心）

设 $\text{inc}[T]$ 为术语 $T$ 的包含标记（0/1），则每个费用层先过一个闸门：

$$
\tilde{I}_o = I_o \, \text{cny} \cdot (1-\text{inc}[\text{inland\_origin}])
$$

$$
\tilde{X} = X \, \text{cny} \cdot (1-\text{inc}[\text{export\_clear}]),\qquad
\tilde{F} = F \, \text{cny} \cdot (1-\text{inc}[\text{freight}])
$$

$$
\tilde{D} = D \, \text{cny} \cdot (1-\text{inc}[\text{discharge}]),\qquad
\tilde{I}_d = I_d \, \text{cny} \cdot (1-\text{inc}[\text{inland\_dest}])
$$

**为什么用乘法闸门而不是 if/else**：乘法让"已含"这一事实在公式里显式可见（乘 0），
任何读者打开 Excel 都能看到「术语=CFR ⇒ 运费系数为 0」，而不需要猜测分支。

---

## 2. 货值与保险

$$
G = P \cdot E \qquad \text{（货值折人民币）}
$$

$$
\tilde{V} = \begin{cases}
0 & \text{inc[insurance]}=1 \quad(\text{CIF/DAP 已含保险})\\[4pt]
(G + \tilde{I}_o + \tilde{X} + \tilde{F}) \cdot k \cdot r_i & \text{否则}
\end{cases}
$$

**为什么保险基准是「货值 + 出口端 + 运费」而不是纯货值**：
保险标的是被保险货物在运输途中的价值，通常按 CIF 价的 110% 投保。
CFR 价 = 货值 + 出口端 + 运费，恰好就是 CIF 的"无保险"形态；所以以它为基数乘加成率与费率，
得到的保险费与「CIF × 110% × 费率」在数学上等价，且避免了循环定义（CIF 含保险，保险按 CIF 算会自指）。

---

## 3. 第一层：CIF 折人民币

$$
\text{cif} = G + \tilde{I}_o + \tilde{X} + \tilde{F} + \tilde{V}
$$

**读法**：这是「货到中国港口、不含中国进口税费」的到岸价。
它常被误当成"进口成本"，其实漏了关税、增值税、港杂与内陆运费。

---

## 4. 税费

$$
\text{duty} = (\text{cif} + \tilde{D}) \cdot t_d
$$

$$
\text{other\_tax} = (\text{cif} + \tilde{D}) \cdot t_o
$$

$$
\text{vat} = (\text{cif} + \tilde{D} + \text{duty}) \cdot t_v
$$

**三个要点**：

1. **卸货费进入税基**。中国进口完税价格按 CIF 价（含运至境内输入地点的运输及其相关费用、保险费），
   目的港卸货费属于"运抵境内输入地点起卸前"的费用，实务中计入完税价格。
   若你的报关行按不含卸货的 CIF 申报，就把 $\tilde{D}$ 设为 0 并在缺口里说明。
2. **增值税税基含关税**，即"组成计税价格 = 关税完税价格 + 关税 + 消费税"。本例消费税为 0。
3. **最惠国税率 ≠ 实际执行税率**。查到的 5.5% 是最惠国税率，实际可能适用暂定税率（常为 0）、
   自贸协定税率或反倾销税。**默认值应保守地填你实际能提供的那个，并把差异写进缺口**。

$$
T_{\text{taxable}} = \text{cif} + \tilde{D} + \text{duty} \qquad \text{（组成计税价格，`taxable`）}
$$

---

## 5. 第二、三、四层

$$
\text{landed\_cash} = \text{cif} + \tilde{D} + \text{duty} + \text{other\_tax} + \text{vat} + \tilde{I}_d + \tilde{U}
$$

这是**现金口径**：一笔生意真正付出去的钱（含可抵扣的进项税，因为钱确实先付出去了）。

$$
\text{vat\_credit} = \text{vat} \cdot \lambda
$$

$$
\text{net\_cash} = \text{landed\_cash} - \text{vat\_credit}
$$

这是**经济口径**：把可抵扣的进项税当作"暂时垫付、后续抵回"，不计入真实成本。

$$
\text{cash\_out} = \text{duty} + \text{other\_tax} + (\text{vat} - \text{vat\_credit})
$$

这是**税费现金支出**：真正留在海关与税局、拿不回来的部分。

$$
\text{unit\_net} = \frac{\text{net\_cash}}{\text{purity}} \cdot \text{gross\_weight\_factor}
$$

折纯成本：用于跨规格比较（如 99% vs 99.9% 纯度）。

---

## 6. 国内可比价

设国内报价 $D_0$（`dom_quote`）、税基 $\text{tax}\in\{\text{含税},\text{不含税}\}$、
是否已含送到运费 `dom_term_incl_freight`、需补的送到运费 $f_d$、规格/地区调整 $a$：

$$
D_{\text{all-in}} =
\begin{cases}
D_0 & \text{含税}\\
D_0 (1+t_v) & \text{不含税}
\end{cases}
\;+\; \mathbf{1}[\text{未含运费}]\, f_d \;+\; a
$$

$$
D_{\text{net}} = \frac{D_{\text{all-in}}}{1+t_v}
$$

**为什么国内未税价用除法**：含税价 = 未税价 × (1+13%)，故反解即除。
进口口岸价也隐含同样的增值税关系，所以两边都除以后才能真正可比。

---

## 7. 价差四口径

以 $D_{\text{all-in}}$、$D_{\text{net}}$ 与三层成本对比：

| 代码 | 公式 | 它回答的问题 | 什么时候用 |
|---|---|---|---|
| **G1** | $D_{\text{net}} - \text{cif}$ | 纯价格：国际与国内**价格本身**谁高 | 判断产业竞争力、出口是否有优势 |
| **G2** | $D_{\text{all-in}} - \text{landed\_cash}$ | 现金：全部含税付出去谁高 | 现金流测算、资金占用 |
| **G3** | $D_{\text{all-in}} - \text{net\_cash}$ | 经济：抵扣完 VAT 后谁高 | **最常被当作"窗口"的那个口径** |
| **G4** | $D_{\text{net}} - \text{net\_cash}$ | 税制：抵扣权的估值差异 | 分析 G1 与 G3 的背离 |

**符号约定**：正 = 国内更强（进口不便宜），负 = 进口更便宜。
注意这只是**口径差异**，既不含资金成本、也不含通关时效、品质折价与数量折扣，
**因此任何一列都不能读作"可实现的套利利润"**。

解析关系（可用来验算）：

$$
G3 - G1 = (D_{\text{all-in}} - D_{\text{net}}) - (\text{net\_cash} - \text{cif})
$$

即「国内价内增值税」减去「进口净成本相对 CIF 的其余成本」。

---

## 8. 市场隐含其余成本

$$
\text{residual} = D_{\text{all-in}}^{\text{不含税?}} - \text{cif} - \tilde{F} - \tilde{V} - \tilde{D}
$$

具体实现：`core.implied_other_costs(dom_price, cif, freight, insurance, discharge)`，
其中 freight / insurance / discharge 已按术语屏蔽（报价为 CIF 时不再重复扣）。

**读法**：国内价与到岸价之间"未被本模型显式解释"的那部分，通常由税费、通关与仓储、
区域供需溢价、品质差异共同构成。它是**参数合理性的旁证**，不是利润。
若某个时点残差突然大幅偏离历史均值，优先怀疑该时点某一侧的数据有问题，而不是相信窗口出现了。

---

## 9. 驱动分解（归因）

以对比期参数 $P_0$（价差 $g_0$）到基准期参数 $P_1$（价差 $g_1$），逐项一次替换：

$$
\Delta g = g_1 - g_0 = \sum_{i} \Delta g_i + \varepsilon
$$

其中 $\Delta g_i$ 是"只把第 $i$ 个参数从对比期值换成基准期值、其余保持对比期值"时价差的增量。
因为逐项替换存在交互项，残差 $\varepsilon$ 单列，且必须满足 $|\varepsilon| < 10^{-6}$ 才算闭合
（`assemble.build_attribution` 会计算并输出，未闭合会进缺口清单）。

因子顺序：海外报价 → 汇率 → 运费 → 关税 → 增值税抵扣 → 保险 → 国内价。

---

## 10. 敏感性

**单参数**：固定其余参数，取该参数的一组候选值，输出 $\text{cif}$ / $\text{landed\_cash}$ /
$\text{net\_cash}$ 与相对基准的增量。

**二维矩阵**：行 = 运费，列 = 汇率（与报告表格一致）。
单元格为 G3 价差 $\;D_{\text{all-in}} - \text{net\_cash}(F_j, E_k)$。

**解读要点**：看矩阵的**等值线方向**。若沿汇率方向变化远比运费方向陡，说明结论主要由
汇率决定，此时"运费涨多少"的争论就是无关紧要的；反之亦然。

---

## 11. 数值稳定性约定

- 所有对外输出统一 `r6`（6 位小数），避免浮点尾巴污染展示；
- `core.js` 与 `core.py` 使用完全相同的表达式顺序，`check_consistency.py` 逐值比对容差 $10^{-6}$；
- 除法全部带保护：`purity`、`gross`、$1+t_v$ 为 0 时回退到安全默认值，不产生 `NaN`/`Infinity`；
- 任何一步出现 `NaN`，`selftest.py` 会判定失败。
