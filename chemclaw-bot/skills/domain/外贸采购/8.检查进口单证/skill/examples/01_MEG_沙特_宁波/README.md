# 示例案例 01：乙二醇（MEG）沙特 → 宁波【模拟】

> **本目录下全部单证均为虚构模拟件**，公司名、编号、金额、船名均为编造，仅用于测试进口单证核对流程，
> 不具任何法律效力。所有文件页眉页脚都带【模拟单证 · SIMULATED DOCUMENTS】标识。

## 一、交易背景

| 项目 | 内容 |
|---|---|
| 批次号 | SIM-MEG-2026-0518 |
| 货物 | 乙二醇（工业级）/ ETHYLENE GLYCOL (MEG), INDUSTRIAL GRADE |
| CAS / HS | 107-21-1 / 2905310000 |
| 数量/单价/金额 | 200.000 MT × USD 612.00/MT = USD 122,400.00 |
| 贸易术语 | CFR NINGBO（Incoterms 2020） |
| 装运 | KING ABDULLAH PORT, JUBAIL (SAJUB) → NINGBO PORT, CHINA (CNNGB)；MSC ISABELLA V. 2618W；ETD 2026-05-12 / ETA 2026-06-20 |
| 买方/收货人 | NINGBO HAIYUAN NEW MATERIAL TRADING CO., LTD.（USCC 91330212MA2HC8P47K） |
| 卖方 | AL-NOOR PETROCHEMICAL TRADING COMPANY（生产商：AL-NOOR PETROCHEMICAL COMPANY） |
| 包装 | 9 × 20 FT ISO TANK，单罐净重 20,000 KGS，合计净重 180,000 KGS / 毛重 180,180 KGS |
| 批号 | MEG2605-B12 |
| 危险品 | UN 3082, Class 9, PG III, Marine Pollutant |

## 二、单证清单（`documents/`）

| 文件 | 类型 | 说明 |
|---|---|---|
| `01_采购合同_Purchase_Contract.docx` | 采购合同 | 2 页；第 5 节包装、第 6 节价格/装运/付款 |
| `02_形式发票_Proforma_Invoice.docx` | 形式发票 | 报价条件（付款方式写 L/C at sight，属报价期旧条款） |
| `03_商业发票_Commercial_Invoice.docx` | 商业发票 | **含植入错误**：8 TANKS / 160.000 MT / USD 117,000.00 |
| `04_装箱单_Packing_List.xlsx` | 装箱单 | 9 罐明细，G/H 列用 `=D*E` 公式，TOTAL 行 `=SUM()` |
| `05_提单_Bill_of_Lading.png` + `.ocr.txt` | 提单（扫描件） | **含植入错误**：批号 `MEG2605-B11` |
| `06_分析证书_COA.docx` | COA | 规格 ≥99.99%，实测 99.97%（满足合同 ≥99.9%） |
| `07_化学品安全技术说明书_SDS.docx` | SDS | 2 页；第 14 节写"8 ISO TANKS / 160,000 / 160,160"（说明性数据） |
| `08_产品规格书_Product_Spec_Sheet.png` + `.ocr.txt` | 产品规格书 | 参考装运基准 8×20MT（说明性数据） |

## 三、本案例设计的"考点"

### A. 必须判出来（真问题）

| 编号 | 问题 | 判定 | 说明 |
|---|---|---|---|
| ISSUE-01 | 批号：装箱单/COA = MEG2605-B12，提单 = MEG2605-B11 | 【不一致】 | 质量追溯与索赔的关键锚点 |
| ISSUE-02 | 缺少原产地证 CO | 【缺失】 | 合同第 5.2 条约定 |
| ISSUE-03 | 缺少保险单 | 【缺失·提示】 | CFR 下由买方投保，属提示级，不进更正函 |
| ISSUE-04 | 发票：612 × 160 = 97,920，却写 117,000（多计 19,080） | 【计算错误】 | 大写与小写一致，属录入/计价错误，须改单 |
| PENDING-01 | 付款方式：合同 T/T 30%+70% vs 发票即期信用证 | 【待确认】 | **不是**单证不符，须买方书面确认付款路径 |

### B. 必须"不"判出来（不可比，判【无法直接比较】）

| 字段 | 为什么会误判 | 正确处理 |
|---|---|---|
| 金额 | 形式发票 122,400 vs 商业发票 117,000 | PI 是报价、CI 是结算，可不相同 |
| 件数/净重/毛重 | SDS 与规格书写 8 罐 / 160,000 KGS | 这是"标准装运基准"说明，非本票实发数 |
| 通知方 ↔ 收货人 | 两个不同公司 | 本可不同主体 |
| 生产商 ↔ 卖方 | 工厂 vs 贸易商 | 本可不同主体 |
| 包装表述 | ISO TANK CONTAINERS / ISOTANK / BULK IN ISO TANKS | 同一事物不同写法 |
| 规格 | 合同 ≥99.9% vs COA ≥99.99% | COA 严于合同属正常，看实测 99.97% 是否 ≥ 99.9% |

> 如果一套核对结果把这些也报成"不一致"，说明判定口径错了 —— 这是本案例最重要的用法：
> **用它检验核对逻辑是否"只会报错、不会区分"**。

## 四、产物（`expected/` 与 `report/`）

| 文件 | 内容 |
|---|---|
| `expected/fields_MEG.json` | 8 份单证的字段抽取结果，每个值带页码/行号/原文片段（已通过定位回查） |
| `expected/manifest.json` | 批次信息 + 应有单证清单 |
| `expected/report.json` | 核对引擎输出（矩阵 / 计算 / 问题 / 待确认 / 汇总） |
| `report/核对看板_Verification_Board.html` | 交互式看板（自包含，双击即开） |
| `report/单证核对台账_Verification_Workbook.xlsx` | 6 页台账 |
| `report/更正函_Correction_Request.txt` | 英文要更正函（自动生成） |

## 五、复现命令

```bash
C="examples/01_MEG_沙特_宁波"
python scripts/verify_docs.py --fields "$C/expected/fields_MEG.json" \
        --manifest "$C/expected/manifest.json" --out "$C/expected/report.json"
python scripts/verify_docs.py --fields "$C/expected/fields_MEG.json" --check-locate --docs "$C/documents"
python scripts/render_report.py --report "$C/expected/report.json" --manifest "$C/expected/manifest.json" \
        --docs "$C/documents" --out "$C/report/核对看板_Verification_Board.html" \
        --xlsx "$C/report/单证核对台账_Verification_Workbook.xlsx"
python scripts/make_letter.py --report "$C/expected/report.json" \
        --batch "$C/expected/manifest.json" --out "$C/report/更正函_Correction_Request.txt"
```

预期输出：

```
单证 8 份 | 字段行 41（一致 20 / 不一致 1 / 无法直接比较 5 / 无法判断 14）| 问题 4 项
其中【待确认】字段行 1 项
计算校验 19 项，未通过 1 项
定位回查：130 个字段，失败 0 个，按片段折算 4 个
```
