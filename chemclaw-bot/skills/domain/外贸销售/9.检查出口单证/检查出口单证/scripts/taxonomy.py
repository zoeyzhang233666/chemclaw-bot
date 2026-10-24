# -*- coding: utf-8 -*-
"""taxonomy.py —— 出口单证类型分类学 + 标准化字段矩阵定义（跨产品/国家/术语通用）。

三个概念必须分清，这是本 skill 的核心判断依据：

1. **单证类型（doc_type）**：文件是什么，决定"它本应有什么、不该有什么"。
2. **事实字段（fact）**：同一票业务中客观唯一的事实（合同号、数量、净重、收货人…），
   跨文件必须一致，不一致 = 冲突 / 缺失 / 不可核实。
3. **角色字段（role）**：由各单证用途决定、允许合理差异的字段（如提单的 Notify Party
   合同上通常没有；发票的付款条款与合同措辞不同）。**不同名称 ≠ 冲突。**

字段矩阵只对"事实字段"做强一致校验；"角色字段"只在声明了 dependent_on 或
consistency 时才做跨文件比对，否则只做"该文件是否具备"的完整性检查。
"""
from __future__ import annotations

from typing import Dict, List

# ---------------------------------------------------------------------------
# 1. 单证类型
# ---------------------------------------------------------------------------
DOC_TYPES: Dict[str, Dict] = {
    "SC": {
        "cn": "销售合同", "en": "Sales Contract",
        "aliases": ["销售合同", "外贸合同", "出口合同", "销售确认书", "SALES CONTRACT",
                    "CONTRACT", "SALES CONFIRMATION", "PURCHASE ORDER", "购货确认书"],
        "why": "交易的根基：买卖双方、品名、数量、单价、贸易术语、装运与付款方式的第一来源。",
        "role": "authority",
        "must_have": ["seller_name", "buyer_name", "contract_no", "date", "product_name_cn",
                      "quantity", "unit_price", "amount", "currency", "incoterm",
                      "pol", "pod", "packing", "net_weight", "signatures"],
        "never_has": [],
        "notes": "合同是事实的源头；当其他单证与合同冲突时，不能默认合同是对的——可能合同本身写错。",
    },
    "PI": {
        "cn": "形式发票", "en": "Proforma Invoice",
        "aliases": ["形式发票", "預估發票", "预估发票", "PROFORMA INVOICE", "P/I", "PI",
                    "PROFORMA", "INVOICE PROFORMA"],
        "why": "报价 + 客户开证/申汇的凭据，通常冻结 30–90 天才开正式发票。",
        "role": "authority",
        "must_have": ["seller_name", "buyer_name", "contract_no", "pi_no", "date",
                      "product_name_cn", "quantity", "unit_price", "amount", "currency",
                      "incoterm", "payment_terms", "validity"],
        "never_has": ["bl_no"],
        "notes": "PI 的有效期（validity）过期而客户仍据此开证，是高频争议点。",
    },
    "CI": {
        "cn": "商业发票", "en": "Commercial Invoice",
        "aliases": ["商业发票", "發票", "发票", "COMMERCIAL INVOICE", "INVOICE"],
        "why": "结汇与清关的核心文件，金额/价格条款/货物描述必须与提单、信用证、报关单一致。",
        "role": "authority",
        "must_have": ["seller_name", "buyer_name", "consignee_name", "ci_no", "date",
                      "product_name_en", "hs_code", "quantity", "unit_price", "amount",
                      "currency", "incoterm", "pol", "pod", "net_weight", "gross_weight",
                      "package_count", "packing"],
        "never_has": [],
        "notes": "HS 编码在 CI 上并非所有国家强制，但印尼等国清关常需要；缺 HS 是不及格而非冲突。",
    },
    "PL": {
        "cn": "装箱单", "en": "Packing List",
        "aliases": ["装箱单", "裝箱單", "包装单", "PACKING LIST", "PACKING SPEC"],
        "why": "唯一负责「物理装箱事实」的单证：件数、毛重、净重、体积、唛头。",
        "role": "authority",
        "must_have": ["seller_name", "buyer_name", "ci_no", "date", "product_name_en",
                      "package_count", "package_type", "net_weight", "gross_weight",
                      "volume", "marks"],
        "never_has": ["unit_price"],
        "notes": "包装单上写单价/金额是模板混用；不算错，但会被海关质疑。",
    },
    "BL": {
        "cn": "海运提单", "en": "Ocean Bill of Lading",
        "aliases": ["提单", "提單", "海运提单", "BILL OF LADING", "B/L", "MASTER BILL",
                    "HOUSE BILL", "SEA WAYBILL", "SURRENDERED BILL"],
        "why": "物权凭证 + 承运人收据，所有卸港、收货人、件数毛重的裁判者。",
        "role": "authority",
        "must_have": ["bl_no", "shipper_name", "consignee_name", "notify_name",
                      "vessel_voyage", "pol", "pod", "product_name_en", "quantity",
                      "package_count", "gross_weight", "volume", "marks", "onboard_date",
                      "freight_terms"],
        "never_has": ["unit_price", "amount"],
        "notes": "提单不写单价与总金额（只为交货事实负责）；也没必要与合同同号。",
    },
    "COA": {
        "cn": "质量检验证书", "en": "Certificate of Analysis",
        "aliases": ["质检报告", "出厂检验报告", "质量证明书", "品质证书", "COA",
                    "CERTIFICATE OF ANALYSIS", "CERTIFICATE OF QUALITY", "INSPECTION CERTIFICATE"],
        "why": "证明本批货达到合同规格，是印尼客户清关与产线验收的必要附件。",
        "role": "authority",
        "must_have": ["batch_no", "test_date", "spec_items", "conclusion"],
        "never_has": ["amount"],
        "notes": "COA 上的批号必须能回溯到装箱单/提单的唛头与批次；不一致 = 货证不符。",
    },
    "SDS": {
        "cn": "安全技术说明书", "en": "Safety Data Sheet",
        "aliases": ["安全技术说明书", "化学品安全技术说明书", "MSDS", "SDS",
                    "SAFETY DATA SHEET", "MATERIAL SAFETY DATA SHEET"],
        "why": "GHS 16 部分，是危险属性、CAS、运输名称、UN 号的第一来源。",
        "role": "reference",
        "must_have": ["cas_no", "product_name_en", "un_number", "hazard_class", "packing_group"],
        "never_has": ["amount", "quantity"],
        "notes": "SDS 的 UN/危规等级与提单、Booking 的 DGD 不一致 = 高危冲突（可能被拒载）。",
    },
    "CO": {
        "cn": "原产地证书", "en": "Certificate of Origin",
        "aliases": ["原产地证书", "产地证", "一般原产地证", "CO", "C/O",
                    "CERTIFICATE OF ORIGIN", "FORM A", "FORM E", "FORM RCEP"],
        "why": "印尼享受 RCEP/ACFTA 关税优惠与清关准入的凭据，原产地标准决定能否享受优惠。",
        "role": "authority",
        "must_have": ["co_no", "exporter_name", "consignee_name", "hs_code",
                      "product_name_en", "quantity", "net_weight", "package_count",
                      "origin_country", "marks", "issue_date"],
        "never_has": ["unit_price"],
        "notes": "CO 须与发票/装箱单同批；品名需与提单一致，但允许英文描述的合理简写差异。",
    },
    "DGD": {
        "cn": "危险货物申报单", "en": "Dangerous Goods Declaration",
        "aliases": ["危险货物申报单", "危险品申报单", "DANGEROUS GOODS DECLARATION", "DGD",
                    "IMDG DECLARATION"],
        "why": "向船公司/港口申报危险属性，决定能否装船。",
        "role": "authority",
        "must_have": ["un_number", "proper_shipping_name", "hazard_class", "packing_group",
                      "quantity", "package_count"],
        "never_has": ["amount"],
        "notes": "纯碱不是危化品 → 正常票不应出现 DGD；出现反而是错误线索。",
    },
    "CUSTOMS": {
        "cn": "出口报关单", "en": "Customs Export Declaration",
        "aliases": ["出口报关单", "报关单", "海关报关单", "CUSTOMS DECLARATION",
                    "EXPORT DECLARATION", "报关资料", "中华 人民 共和国海关出口货物报关单"],
        "why": "境内出口申报，HS 编码、成交方式、数量金额的第一国别事实。",
        "role": "authority",
        "must_have": ["hs_code", "quantity", "amount", "currency", "incoterm",
                      "product_name_cn", "pol", "net_weight", "gross_weight"],
        "never_has": [],
        "notes": "报关单上的「成交方式」是海关代码（FOB/CFR/CIF），需与合同的 Incoterms 2020 术语对应。",
    },
    "LC": {
        "cn": "信用证", "en": "Letter of Credit",
        "aliases": ["信用证", "LETTER OF CREDIT", "L/C", "LC"],
        "why": "付款条件，决定哪些单证、哪些数据必须严格一致（UCP600 严格相符）。",
        "role": "authority",
        "must_have": ["lc_no", "applicant_name", "beneficiary_name", "amount", "currency",
                      "required_docs", "latest_shipment_date", "expiry_date", "port_loading",
                      "port_discharge", "incoterm"],
        "never_has": [],
        "notes": "信用证不是货物本身，而是「单证要求清单」；其日期与金额是交单的最后裁决者。",
    },
    "INSP": {
        "cn": "装运前检验报告", "en": "Pre-shipment Inspection",
        "aliases": ["装运前检验", "检验报告", "SGS 报告", "PRE-SHIPMENT INSPECTION", "PSI"],
        "why": "客户/政府指定的第三方验货结论，证明到港货与合同一致。",
        "role": "authority",
        "must_have": ["product_name_en", "batch_no", "quantity"],
        "never_has": [],
        "notes": "在有些国家（如印尼工业原料）PSI 不是强制；是否有要求以客户/目的国为准。",
    },
}

# ---------------------------------------------------------------------------
# 2. 标准化字段
#     group: party / commerce / logistics / quality / document
#     kind : fact（跨文件强一致） / role（按用途允许差异） / calc（由公式得到）
# ---------------------------------------------------------------------------
FIELDS: List[Dict] = [
    # ---- 当事人 ----
    dict(id="seller_name", cn="出口商/卖方", en="Seller / Exporter", group="party", kind="fact",
         fmt="text", aliases=["卖方 Seller", "卖方 SELLER", "出口商 Exporter", "出口商 SHIPPER",
                              "卖方：", "出口商：", "BENEFICIARY", "SHIPPER（发货人）"]),
    dict(id="buyer_name", cn="买方/进口商", en="Buyer / Importer", group="party", kind="fact",
         fmt="text", aliases=["买方 Buyer", "买方 BUYER", "进口商 Importer", "进口商",
                              "APPLICANT", "PURCHASER", "开证申请人"]),
    dict(id="consignee_name", cn="收货人", en="Consignee", group="party", kind="fact",
         fmt="text", aliases=["Consignee 收货人", "收货人 CONSIGNEE", "Consignee / 收货人",
                              "Consignee", "CONSIGNEE"]),
    dict(id="notify_name", cn="通知方", en="Notify Party", group="party", kind="role",
         fmt="text", aliases=["Notify Party 通知方", "通知方", "通知人", "NOTIFY PARTY"]),
    dict(id="buyer_address", cn="买方地址", en="Buyer Address", group="party", kind="fact",
         fmt="address", aliases=["买方地址", "ADDRESS OF BUYER"]),
    dict(id="seller_address", cn="出口商地址", en="Seller Address", group="party", kind="fact",
         fmt="address", aliases=["卖方地址", "出口商地址", "ADDRESS OF SELLER"]),

    # ---- 单证编号 ----
    dict(id="contract_no", cn="合同编号", en="Contract No.", group="document", kind="fact",
         fmt="code", aliases=["合同编号", "合同号", "Contract No", "S/C No", "SC No", "关联合同"]),
    dict(id="pi_no", cn="形式发票号", en="P/I No.", group="document", kind="fact",
         fmt="code", aliases=["形式发票号", "PI No", "Proforma Invoice No", "P/I No"]),
    dict(id="ci_no", cn="商业发票号", en="Invoice No.", group="document", kind="fact",
         fmt="code", aliases=["发票号 Invoice No", "商业发票号", "Invoice No", "INV No", "商业发票 Commercial Invoice No"]),
    dict(id="bl_no", cn="提单号", en="B/L No.", group="document", kind="fact",
         fmt="code", aliases=["提单号", "B/L No", "Bill of Lading No", "提单编号"]),
    dict(id="co_no", cn="产地证号", en="CO No.", group="document", kind="fact",
         fmt="code", aliases=["产地证号", "CO No", "Certificate No"]),
    dict(id="batch_no", cn="批号", en="Batch / Lot No.", group="quality", kind="fact",
         fmt="code", aliases=["批号 Batch No", "批号 Batch", "批次号", "Batch No", "Lot No", "BATCH NO."]),
    dict(id="date", cn="单证日期", en="Date", group="document", kind="role", fmt="date",
         aliases=["日期", "Date", "Invoice Date", "Issue Date"]),

    # ---- 商品 ----
    dict(id="product_name_cn", cn="产品中文名", en="Product Name (CN)", group="commerce",
         kind="fact", fmt="text",
         aliases=["货物名称", "商品名称", "产品名称", "中文品名", "商品描述"]),
    dict(id="product_name_en", cn="产品英文名", en="Product Name (EN)", group="commerce",
         kind="fact", fmt="text",
         aliases=["Description of Goods", "Goods", "Commodity", "Product", "Description",
                  "英文品名", "产品名称 Product name", "Product name", "Trade name"]),
    dict(id="cas_no", cn="CAS 登记号", en="CAS No.", group="quality", kind="fact", fmt="cas",
         aliases=["CAS No", "CAS 号", "CAS登记号", "CAS Number"]),
    dict(id="hs_code", cn="HS 编码", en="HS Code", group="commerce", kind="fact", fmt="hs",
         aliases=["HS 编码", "HS Code", "HS 码", "商品编码", "海关编码", "商品编号"]),
    dict(id="spec", cn="规格/等级", en="Specification / Grade", group="quality", kind="fact",
         fmt="text", aliases=["规格", "等级", "标准", "Specification", "Grade", "Purity"]),
    dict(id="un_number", cn="UN 编号", en="UN Number", group="quality", kind="fact", fmt="code",
         aliases=["UN No", "UN Number", "联合国编号"]),

    # ---- 数量与金额 ----
    dict(id="quantity", cn="数量", en="Quantity", group="commerce", kind="fact", fmt="num",
         unit="MT", aliases=["数量", "Quantity", "Qty", "QUANTITY SHIPPED", "SOUND IN BULK"]),
    dict(id="unit_price", cn="单价", en="Unit Price", group="commerce", kind="fact",
         fmt="money", unit="USD/MT", aliases=["单价", "Unit Price", "PRICE PER UNIT"]),
    dict(id="amount", cn="总金额", en="Total Amount", group="commerce", kind="calc",
         fmt="money", unit="USD", formula="quantity * unit_price",
         aliases=["金额", "总价", "Total", "Amount", "Total Value", "Invoice Value",
                  "TOTAL AMOUNT"]),
    dict(id="currency", cn="币种", en="Currency", group="commerce", kind="fact", fmt="code",
         aliases=["币种", "币制", "Currency"]),
    dict(id="incoterm", cn="贸易术语", en="Incoterms", group="commerce", kind="fact",
         fmt="code", aliases=["贸易术语", "价格条件", "成交方式", "价格条款", "Terms",
                              "Incoterm", "INCOTERMS", "Price Term", "Delivery Terms"]),

    # ---- 物流 ----
    dict(id="pol", cn="起运港", en="Port of Loading", group="logistics", kind="fact",
         fmt="port", aliases=["起运港", "装运港", "Port of Loading", "POL"]),
    dict(id="pod", cn="目的港", en="Port of Discharge", group="logistics", kind="fact",
         fmt="port", aliases=["目的港", "卸货港", "Port of Discharge", "POD", "Port of Delivery"]),
    dict(id="final_dest", cn="最终目的地", en="Final Destination", group="logistics",
         kind="role", fmt="text", aliases=["最终目的港", "最终目的地", "Final Destination"]),
    dict(id="vessel_voyage", cn="船名航次", en="Vessel / Voyage", group="logistics",
         kind="role", fmt="code", aliases=["船名", "船名航次", "Vessel", "Voyage"]),
    dict(id="onboard_date", cn="装船日期", en="On Board Date", group="logistics", kind="fact",
         fmt="date", aliases=["装船日期", "开船日期", "Shipped on Board", "ON BOARD DATE"]),
    dict(id="package_count", cn="包装件数", en="Number of Packages", group="logistics",
         kind="fact", fmt="int", unit="bags", aliases=["件数", "总件数", "包装件数",
                                                       "No. of Packages", "Packages"]),
    dict(id="package_type", cn="包装方式", en="Package Type", group="logistics", kind="fact",
         fmt="text", aliases=["包装方式", "包装种类", "包装 Packing", "Package Type", "Packing",
                              "Type of Packages"]),
    dict(id="net_weight", cn="净重", en="Net Weight", group="logistics", kind="fact",
         fmt="num", unit="KG", aliases=["净重", "NET WEIGHT", "N.W.", "NW"]),
    dict(id="gross_weight", cn="毛重", en="Gross Weight", group="logistics", kind="fact",
         fmt="num", unit="KG", aliases=["毛重", "GROSS WEIGHT", "G.W.", "GW"]),
    dict(id="volume", cn="体积", en="Meas.", group="logistics", kind="fact", fmt="num",
         unit="CBM", aliases=["体积", "尺码", "MEAS", "MEASUREMENT", "CBM"]),
    dict(id="marks", cn="唛头", en="Shipping Marks", group="logistics", kind="fact",
         fmt="text", aliases=["唛头", "运输标志", "MARK", "MARKS", "SHIPPING MARKS"]),
    dict(id="freight_terms", cn="运费条款", en="Freight", group="logistics", kind="role",
         fmt="code", aliases=["运费", "运费支付方式", "FREIGHT", "FREIGHT PREPAID"]),

    # ---- 付款与装运 ----
    dict(id="payment_terms", cn="付款方式", en="Payment Terms", group="commerce",
         kind="role", fmt="text", aliases=["付款方式", "支付条款", "Payment", "PAYMENT TERMS",
                                           "TERMS OF PAYMENT"]),
    dict(id="shipment_period", cn="装运期", en="Shipment Period", group="logistics",
         kind="role", fmt="text", aliases=["装运期", "交货期", "SHIPMENT", "TIME OF SHIPMENT",
                                           "LATEST SHIPMENT DATE"]),
    dict(id="origin_country", cn="原产国", en="Country of Origin", group="commerce",
         kind="fact", fmt="text", aliases=["原产国", "产地", "Country of Origin", "ORIGIN"]),
]

FIELD_BY_ID = {f["id"]: f for f in FIELDS}

FACT_FIELDS = [f["id"] for f in FIELDS if f["kind"] == "fact"]
CALC_FIELDS = [f["id"] for f in FIELDS if f["kind"] == "calc"]

# 各单证类型"逻辑上应出现"的字段集合；用于区分"缺失（应有而无）"与"不适用"
# 依据：国际惯例 + 常见到岸国清关要求；具体到某国/某客户可在 case.overrides 里覆盖。
DOC_FIELDS: Dict[str, List[str]] = {
    "SC": ["seller_name", "buyer_name", "contract_no", "date", "product_name_cn",
           "product_name_en", "quantity", "unit_price", "amount", "currency", "incoterm",
           "pol", "pod", "packing_fields", "net_weight", "package_count", "payment_terms",
           "shipment_period", "spec"],
    "PI": ["seller_name", "buyer_name", "pi_no", "date", "product_name_en", "quantity",
           "unit_price", "amount", "currency", "incoterm", "payment_terms", "shipment_period"],
    "CI": ["seller_name", "buyer_name", "consignee_name", "ci_no", "date", "product_name_en",
           "hs_code", "quantity", "unit_price", "amount", "currency", "incoterm", "pol",
           "pod", "net_weight", "gross_weight", "package_count", "package_type", "marks"],
    "PL": ["seller_name", "buyer_name", "ci_no", "date", "product_name_en", "package_count",
           "package_type", "net_weight", "gross_weight", "volume", "marks"],
    "BL": ["bl_no", "seller_name", "consignee_name", "notify_name", "vessel_voyage", "pol",
           "pod", "product_name_en", "package_count", "package_type", "gross_weight",
           "volume", "marks", "onboard_date", "freight_terms"],
    "COA": ["batch_no", "date", "product_name_en", "cas_no", "spec"],
    "SDS": ["product_name_en", "cas_no", "un_number", "hs_code"],
    "CO": ["co_no", "seller_name", "buyer_name", "hs_code", "product_name_en", "quantity",
           "net_weight", "package_count", "origin_country", "marks", "date"],
    "CUSTOMS": ["hs_code", "product_name_cn", "quantity", "amount", "currency", "incoterm",
                "pol", "net_weight", "gross_weight", "package_count"],
    "LC": ["seller_name", "buyer_name", "amount", "currency", "incoterm", "pol", "pod",
           "shipment_period"],
    "INSP": ["product_name_en", "batch_no", "quantity", "net_weight"],
    "DGD": ["un_number", "quantity", "package_count"],
}

# 单证"不是事实源"的字段：出现即提示（不一定是错，但需要解释）
NOT_EXPECTED: Dict[str, List[str]] = {
    "BL": ["unit_price", "amount", "currency"],
    "PL": ["unit_price", "amount"],
    "COA": ["amount", "unit_price", "quantity"],
    "SDS": ["amount", "quantity", "unit_price"],
    "CO": ["unit_price", "amount"],
}

GROUP_LABEL = {
    "party": "当事人", "document": "单证编号", "commerce": "商品与商务",
    "logistics": "物流与包装", "quality": "质量与安全",
}

# 状态码：与 HTML / Excel 共用同一套语义
STATUS = {
    "OK":     {"cn": "一致", "en": "MATCH",         "hex": "E7F6EC", "deep": "166534"},
    "DIFF":   {"cn": "不一致", "en": "CONFLICT",    "hex": "FDE7E7", "deep": "991B1B"},
    "CALC":   {"cn": "计算错误", "en": "CALC ERROR", "hex": "FBE3F0", "deep": "9D174D"},
    "MISS":   {"cn": "缺失", "en": "MISSING",       "hex": "FEF3C7", "deep": "92400E"},
    "NA":     {"cn": "不适用", "en": "NOT REQUIRED", "hex": "EEF1F4", "deep": "475569"},
    "UNK":    {"cn": "无法判断", "en": "UNVERIFIABLE", "hex": "E8EAF6", "deep": "3730A3"},
    "MANUAL": {"cn": "需人工核对", "en": "HUMAN CHECK", "hex": "FDE68A", "deep": "78350F"},
}

SEVERITY = {
    "S1": {"cn": "阻断", "desc": "不改会直接导致交单被拒 / 清关受阻 / 货被扣", "hex": "FDE7E7", "deep": "991B1B"},
    "S2": {"cn": "重要", "desc": "银行或海关会质疑，需在开船前修正", "hex": "FEF3C7", "deep": "92400E"},
    "S3": {"cn": "一般", "desc": "影响专业度，可在下次开票前统一", "hex": "EAF2FB", "deep": "1E40AF"},
}


def doc_type_label(code: str, lang: str = "cn") -> str:
    d = DOC_TYPES.get(code, {})
    return d.get(lang, code)


def field_label(fid: str, lang: str = "cn") -> str:
    f = FIELD_BY_ID.get(fid)
    if not f:
        return fid
    return f.get(lang, fid)


def expected_fields(doc_type: str) -> List[str]:
    out = list(DOC_FIELDS.get(doc_type, []))
    # packing_fields 是伪字段，展开为包装三件套
    if "packing_fields" in out:
        out.remove("packing_fields")
        out += ["package_count", "package_type", "gross_weight", "net_weight"]
    return list(dict.fromkeys(out))
