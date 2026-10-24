# 完整输入输出案例（examples）

本目录提供**两个**可运行的完整案例，覆盖"大宗无机化工品"与"精细有机中间体"两类，证明本 Skill 不绑定任何单一产品或国家。

---

## 案例总览

| 案例 | 产品 | HS-6 | 目录 | 数据状态 |
|---|---|---|---|---|
| A | 重质纯碱 Sodium Carbonate (Dense) | 283620 | `soda-ash/` | **真实数据**（UN Comtrade 实时拉取，2019–2025） |
| B | 甲醇 Methanol | 290511 | `methanol/` | **仅有输入样例**（未取数，用于演示第一步） |

---

## 案例 A：重质纯碱（完整端到端）

### A.1 用户输入

> 我们是中国的**重质纯碱**供应商，Na2CO3 ≥99.2%，堆积密度 0.9–1.1 g/cm³。
> 主要优势是**价格**和**产能**。想找未来重点出口市场。
> 请比较近 5 年全球主要进口国的进口金额/数量、中国供应份额、竞争来源国、关税与下游产业。

### A.2 第一步：HS 编码确认

```bash
python scripts/hs_match.py "重质纯碱" --cas 497-19-8 --spec "dense >=99.2%"
```

**实际输出**：
```
[1] HS 283620  置信度 高（score 145.0）
    英文：Disodium carbonate (soda ash)
    中文：碳酸钠（纯碱）
    依据：与关键词完全一致；与关键词“纯碱”部分匹配

口径提示（第28章）：同一种物质会因晶体结构/用途/纯度落入不同子目...
```

用户确认：是 → 283620 覆盖产品；但**重质与轻质在该编码下不区分**，须在报告中声明。

同时确认本地编码：
- 欧盟 `2836 20 00`（10 位 `2836200000`）
- 美国 `2836.20.00.00`

### A.3 第二步：取数（真实执行）

```bash
python scripts/fetch_trade.py --hs 283620 --years 2019-2025 --partners --top 15 --out trade_data
```

**实际得到**（见 `fetch_meta.json`）：
- 报告国覆盖：2019 年 169 个 → 2024 年 144 个 → 2025 年 119 个
- 全球已报送进口合计：2019 年 41.1 亿美元 → 2022 年峰值 60.2 亿 → 2024 年 47.1 亿 → 2025 年 42.6 亿
- 中国供应合计：2019 年 3.03 亿 → 2024 年 2.65 亿（份额 7.4% → 5.6%）

### A.4 第三步：关税核验（真实执行）

| 国家 | 结果 | 状态 |
|---|---|---|
| 美国 | `2836.20.00.00` General **1.2%**；Column 2 8.5%；FTA 免税（中国不适用） | ✅ 已核验（USITC HTS） |
| 欧盟（德/意/西/波/荷/比/法） | `2836200000` 第三国关税 **5.50%**；含废物条例管制；**未发现**反倾销/反补贴 | ✅ 已核验（EU TARIC） |
| 智利 | 非 FTA 原产统一 **6%**；美国原产零关税 | ✅ 已核验（trade.gov） |
| 印度 | CBIC JS 渲染不可取 → 行级税率缺失 | ⚠ 缺口（CRITICAL） |
| 印尼/马来/巴西/墨西哥/土耳其/越南/韩国/泰国/尼日利亚/南非 | 仅有税制结构，无行级税率 | ⚠ 缺口 |

### A.5 第四步：产业信息（真实来源）

USGS Mineral Commodity Summaries 2025（Soda Ash）：
- 美国 2024 年产量约 1,200 万吨，名义产能 1,390 万吨/年
- 2024 年出口 740 万吨（超过产量一半）→ **净出口国**
- 终端用途：玻璃 45%、化学品 29%
- 美国进口来源中土耳其占 92%

### A.6 第五步：生成交付物

```bash
python scripts/build_outputs.py --data trade_data --config analysis_config.json --out out
python scripts/validate_outputs.py --data trade_data --config analysis_config.json --out out
```

产出（本目录已有）：`report.html`、`workbook.xlsx`

### A.7 关键结论（如何区分事实与判断）

**【贸易统计事实】**
- 墨西哥 2025 年进口 3.25 亿美元，美国占 100%，中国 0.0%
- 智利 2025 年进口 2.62 亿美元，美国占 97%，中国 1.8%；2019→2025 CAGR **+16.0%**
- 印尼 2025 年进口 2.26 亿美元，中国占 **27.0%**
- 马来西亚 2025 年进口 1.76 亿美元，中国占 **23.5%**，CAGR +7.0%
- 印度 2025 年进口 2.49 亿美元，中国占 5.5%（2022 年曾达 3,340 万美元 / 16.2%）

**【初步判断】值得进一步研究**
1. **马来西亚** — 中国已有 23.5% 份额且在增长（CAGR +7.0%），说明规格与清关路径已被验证
2. **印尼** — 中国份额 27.0% 且各年稳定在 19–27%，绝对规模大
3. **印度** — 来源分散（美国 37%、土耳其 26%），中国曾有单年 3,340 万美元成交
4. **智利** — 美国单一来源 97%，但进口 5 年翻倍，结构性替代议题成立（须先核 FTA 优惠税率）
5. **欧盟** — 关税已核验 5.5% 且无 AD/CVD，但物流半径与天然碱成本是硬约束

**【反向证据】**
- 中国整体份额从 7.4% 降至 5.6%
- 巴西 2022 年自华进口 8,180 万美元，2024 年骤降至 70 万美元 → 机会型供应，不可外推
- 2024 年全球合计下降 21.6%，部分源于报告国由 162 减至 144 的统计缺口

### A.8 本案例揭示的"陷阱"

| 陷阱 | 案例中的体现 |
|---|---|
| 把"进口大"当机会 | 墨西哥外莱最大进口国，但美国占 100%，中国几乎没戏 |
| 忽略覆盖度变化 | 2024/2025 合计下降 ≠ 市场萎缩 |
| 用平均值代替行级税率 | 印尼平均 MFN 8.1% 不能当纯碱税率 |
| 忽略领域编码局限 | 283620 不分重质/轻质 |
| 忽略港口中转 | 荷兰、比利时进口额高估本国消费 |

---

## 案例 B：甲醇（演示第一步的泛化能力）

### B.1 输入
> 我们是中国的甲醇供应商，优等品 ≥99.9%，优势是产能与价格。想看出口市场。

### B.2 HS 匹配输出

```bash
python scripts/hs_match.py "甲醇" --top 3
```
```
[1] HS 290511  置信度 高（score 260.0）
    英文：Methanol (methyl alcohol)
    中文：甲醇
    依据：与关键词完全一致；与子目名称完全一致；中文名包含输入词
```

### B.3 后续步骤（与案例 A 完全相同的命令）

```bash
python scripts/fetch_trade.py --hs 290511 --years 2020-2025 --partners --out methanol/trade_data
python scripts/build_outputs.py --data methanol/trade_data \
       --config methanol/analysis_config.json --out methanol/out
```

**只需换 `--hs` 与 config，其余流程完全复用** —— 这就是"不写死产品与国家"的验证方式。

### B.4 甲醇案例需要额外注意的口径

- 甲醇是**危险化学品**，进口国常有额外的危化品登记、包装与运输要求（非关税壁垒往往比关税更关键）
- 甲醇下游与中国出口结构（MTO、燃料）高度相关，需结合能源政策判断，不能只看进口额
- HS 290511 同时包含"甲醇"与"甲基醇"，纯度高无需拆分，但**工业级/燃料级**在部分国家有细分

---

## 文件说明

### soda-ash/
| 文件 | 说明 |
|---|---|
| `analysis_config.json` | 完整配置：产品身份、20 个国家的关税（含核验状态）、6 条产业事实、3 段判断 |
| `imports_by_reporter_year.csv` | 1,084 行报告国×年份原始数据（world 与 China 两列） |
| `partners_by_reporter_year.csv` | 1,281 行来源国明细 |
| `fetch_meta.json` | 取数元信息：年份覆盖、来源、币种、单位 |
| `report.html` | **最终交互报告**（2.1 MB，自包含：地图+图表+钻取+筛选） |
| `workbook.xlsx` | **最终 Excel**（10 页签，含活公式与缺口页） |

### methanol/
| 文件 | 说明 |
|---|---|
| `analysis_config.json` | 甲醇的输入样例（关税均为 gap，未核验） |
| `hs_match_output.txt` | 第一步的实际输出留档 |

---

## 复现命令（从零）

```bash
cd <skill 根目录>

# 1. 编码确认
python scripts/hs_match.py "重质纯碱" --cas 497-19-8

# 2. 取数（需要外网；结果会缓存，重跑免费）
python scripts/fetch_trade.py --hs 283620 --years 2019-2025 --partners --top 15 --out /tmp/trade

# 3. 出报告
python scripts/build_outputs.py --data /tmp/trade \
       --config examples/soda-ash/analysis_config.json --out /tmp/out

# 4. 自检
python scripts/validate_outputs.py --data /tmp/trade \
       --config examples/soda-ash/analysis_config.json --out /tmp/out
```

> 若只想看结果、不重跑取数，直接用 `examples/soda-ash/report.html` 与 `workbook.xlsx`。
> 若要离线重建，用 `examples/soda-ash/` 里的三个 csv/json 作为 `--data` 目录（把 csv 与 fetch_meta.json 放在同一目录即可）。
