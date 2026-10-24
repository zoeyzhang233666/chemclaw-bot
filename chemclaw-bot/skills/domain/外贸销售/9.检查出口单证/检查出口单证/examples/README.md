# 示例票说明：重质纯碱出口印尼（模拟）

> **全部文件为模拟生成的演示单证，企业名称、编号、航次、银行均为虚构，不对应任何真实业务。**
> 每页页脚标有 `DEMO 模拟单证 · 非真实业务文件`。

## 场景

| 项目 | 内容 |
| --- | --- |
| 商品 | 重质纯碱（天然碱法）／ SODA ASH DENSE |
| CAS | 497-19-8 |
| HS 编码 | 2836.20.00 |
| 出口商 | 青岛海化进出口有限公司 / QINGDAO HAIHUA IMPORT & EXPORT CO., LTD. |
| 进口商 / 收货人 | PT SAMUDRA ANDALAN KIMIA（印尼） |
| 合同号 | HYE-SC-2026-0817 |
| 数量 / 单价 / 金额 | 1,000.000 MT ／ USD 520.00/MT ／ USD 520,000.00 |
| 贸易术语 | CFR TANJUNG PRIOK（合同正文因笔误写成 CIF） |
| 路线 | QINGDAO, CHINA → TANJUNG PRIOK, JAKARTA |
| 船名航次 | MV OCEAN PRIDE / V.016，装船日 2026-09-18 |
| 包装 | 1,000 × 1,000KG 吨袋，43 × 40'HQ |
| 净重 / 毛重 / 体积 | 1,000,000 KG ／ 1,050,000 KG ／ 1,050 CBM |
| COA 批号 | HYB26-0821-07 |

## 12 份文件

| # | 文件 | 类型 | 说明 |
| --- | --- | --- | --- |
| 01 | `01_销售合同_Sales_Contract.pdf` | SC | 4 页，含商品描述表、包装条款、签字页 |
| 02 | `02_形式发票_Proforma_Invoice.pdf` | PI | 1 页 |
| 03 | `03_商业发票_Commercial_Invoice.pdf` | CI | 1 页，三栏当事人 + 商品表 |
| 04 | `04_装箱单_Packing_List.pdf` | PL | 2 页，含唛头块 |
| 05 | `05_海运提单_Bill_of_Lading.pdf` | BL | 3 页，含背面条款 |
| 06 | `06_质量检验证书_COA.pdf` | COA | 1 页，含检验项目表 |
| 07 | `07_安全技术说明书_SDS.pdf` | SDS | 2 页，GHS 格式节选 |
| 08 | `08_原产地证书_Certificate_of_Origin.pdf` | CO | 1 页 |
| 09 | `09_出口报关单_Customs_Declaration.pdf` | CUSTOMS | 1 页 |
| 10 | `10_信用证_Letter_of_Credit.pdf` | LC | 1 页，MT700 报文格式 |
| 11 | `11_物流公司提单模板_Carrier_Template.pdf` | — | **参考文件**，应被排除 |
| 12 | `12_公司出口文件标准_Export_Doc_Standard.pdf` | — | **参考文件**，应被排除 |

## 注入的 14 处典型错误

| 编号 | 出错文件 | 字段 | 错误值 | 正确值 | 性质 |
| --- | --- | --- | --- | --- | --- |
| E01 | 商业发票 | 总金额 | 500,000.00 | 520,000.00 | 金额算错（应触发 C1） |
| E02 | 装箱单 | 净重 | 1,005,000.000 | 1,000,000 | 重量抄错 |
| E03 | 海运提单 | 包装件数 | 1,010 | 1,000 | 件数抄错 |
| E04 | 海运提单 | 目的港 | PORT OF WILSON | TANJUNG PRIOK | 港口错（S1 典型） |
| E05 | 原产地证 | 收货人 | PT SAMUDRA ANDALAN KIMIA - GUDANG CIKARANG | PT SAMUDRA ANDALAN KIMIA | 多出仓库后缀 |
| E06 | 海运提单 | 发货人 | QINGDAO HAIHUA CHEMICAL CO., LTD. | QINGDAO HAIHUA IMPORT & EXPORT CO., LTD. | 公司名错 |
| E07 | SDS | 英文品名 | SODA ASH LIGHT(苏打灰,轻质) | SODA ASH DENSE | 规格错（轻质/重质） |
| E08 | 装箱单 | 唛头 | 与商业发票唛头不同 | 一致 | 唛头不符 |
| E09 | 销售合同 | 贸易术语 | CIF | CFR | 术语错 |
| E10 | 海运提单 | 毛重 | 1,045,000.000 | 1,050,000 | 重量抄错 |
| E11 | 形式发票 | PI 号 | HYE-PI-2026-0817A | HYE-PI-2026-0817 | 多余后缀（应触发 C6） |
| E12 | COA | CAS 号 | 497-19-2 | 497-19-8 | 校验位错 |
| E13 | COA | 关联合同号 | HYE-SC-2026-0871 | HYE-SC-2026-0817 | 数字换位 |
| E14 | 装箱单 | 体积 | 4,800.000 CBM | 1,050 CBM | 超柜容量（应触发 C5） |

## 这套示例想演示什么

1. **同义写法不算冲突**：`SODA ASH DENSE` / `DISODIUM CARBONATE (SODA ASH DENSE)`、
   `CFR` / `CFR TANJUNG PRIOK`、`1,000.000 MT` / `1,000,000 KG` 都判一致；
2. **单证本就不载明的字段要给「不适用」**：提单没有价格、装箱单没有单价和术语、
   合同没有通知方，都不能报「缺失」；
3. **单证内自洽 vs 跨文件一致要分开抓**：E01 靠 C1 抓、E11 靠 C6 抓（PI 号只出现在 PI 上，
   跨文件比对抓不到）、E14 靠 C5 抓（体积没有可比对象，只能靠物理容量）；
4. **参考文件要识别出来但排除**：11、12 号文件标题区是"模板/标准"，必须排除在比对之外；
5. **数字别硬猜**：`TO BE ADVISED` 这类占位不作值，`For Buyer's Confirmation` 判「无法判断」。

## 运行

```bash
python scripts/check_docs.py examples/demo_docs --out ./示例结果
# 或
python scripts/verify.py --full
```

预期：识别 10 份本票单证 + 2 份参考文件（排除）；14 处注入错误全部命中；
C1/C3/C5/C6 计算核验不通过。

本目录附带的 `check_page.html` 与 `出口单证检查结果.xlsx` 即上述命令的产物，可直接打开对照。
