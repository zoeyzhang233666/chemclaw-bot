# -*- coding: utf-8 -*-
"""extract_i18n.py · 多语言询盘的正则补充表

extract.py 的英文规则覆盖英语询盘；本文件提供越南语 / 印尼语 / 西班牙语 / 葡萄牙语 /
阿拉伯语 / 俄语 / 日语的**少量高价值模式**（数量、付款、包装、贸易术语、港口）。
刻意保持克制：宁可漏抓标"缺失"，也不要错抓后当真——漏了客户看得见，抓错了没人看得见。

用法：
    from extract_i18n import MULTI, match_first
    m = match_first("qty_trial", text)
"""
from __future__ import annotations

import re

# 通用数字 + 单位（含越/印尼千分位写法 3.000 / 3,000）
NUM = r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
MT_UNIT = (r"(?:MT|M/T|metric\s*tons?|tonnes?|tons?|tấn|tan|toneladas?|tonnen?"
           r"|أطنان|طن|тонн\w*|トン|톤|公吨|吨)\b")

# key → [(regex, 说明)]，regex 必须带命名组或用 group(0) 定位原句
MULTI = {
    "qty_trial": [
        # vi: 40 tấn cho đơn hàng đầu tiên
        NUM + r"\s*" + MT_UNIT + r"\s*(?:cho\s+)?(?:đơn\s+hàng\s+)?(?:đầu\s+tiên|thử|lần\s+đầu)",
        # id: 300 MT untuk pengiriman pertama / order pertama
        NUM + r"\s*" + MT_UNIT + r"\s*(?:untuk|pada)\s*(?:pengiriman|order|pesanan)\s*(?:pertama|awal)",
        # es/pt: 40 toneladas para el primer pedido
        NUM + r"\s*" + MT_UNIT + r"\s*(?:para|para\s+el|para\s+o)\s*(?:primer|primeiro)\s*(?:pedido)",
        # ar: 40 طن للطلب الأول
        NUM + r"\s*(?:أطنان|طن)\s*(?:للطلب|لأول)",
    ],
    "qty_annual": [
        NUM + r"\s*" + MT_UNIT + r"\s*(?:/|mỗi|per|por|/\s*)\s*(?:năm|tahun|año|ano|annum|year)",
        r"(?:hàng\s+năm|mỗi\s+năm|per\s+tahun|por\s+año)[^\n.]{0,30}?" + NUM + r"\s*" + MT_UNIT,
    ],
    "payment": [
        r"(?:thanh\s+toán|payment|pembayaran|pago|pagamento|الدفع|оплата|支払|결제)\s*[:：]?\s*([^\n]{2,60})",
        r"\bL\s*/\s*C\b[^\n.]{0,40}",
        r"\bT\s*/\s*T\b[^\n.]{0,40}",
        r"\bD\s*/\s*P\b[^\n.]{0,40}",
    ],
    "pack_std": [
        r"(\d{1,4})\s*(?:kg|kgs|Kg|KG)\s*(?:/|per|mỗi|per\s+)\s*(?:bao|bag|saco|sak|كيس|袋|자루)",
        r"(?:bao\s+bì|đóng\s+gói|packing|kemasan|envase|embalagem|التعبئة|упаковка|包装|포장)\s*[:：]?\s*([^\n]{2,80})",
        r"jumbo[^\n.]{0,40}",
    ],
    "incoterm": [
        r"\b(FOB|CFR|CIF|CIP|CPT|EXW|FCA|DAP|DDP)\b\s*([A-Za-zÀ-ỹđ'\- ]{2,30})?",
    ],
    "port_dest": [
        r"\b(?:FOB|CFR|CIF|CPT|CIP)\b\s+([A-Za-zÀ-ỹđ'\- ]{2,28}?)(?:[.,\n]|$)",
        r"(?:cảng|cang|port|puerto|porto|ميناء|港口|港)\s*[:：]?\s*([A-Za-zÀ-ỹđ'\- ]{2,28})",
    ],
    "product_raw": [
        r"(?:xút\s+vảy|soda\s+api|sosa\s+cáustica|soda\s+cáustica|caustic\s+soda|"
        r"natri\s+hidroxit|natrium\s+hidroksida|هيدروكسيد\s+الصوديوم)[^\n.]{0,40}",
        r"(?:natri\s+cacbonat|natrium\s+karbonat|carbonato\s+de\s+sodio|کربنات\s+الصوديوم|"
        r"كربونات\s+الصوديوم|soda\s+ash)[^\n.]{0,40}",
    ],
}

# 付款/贸易术语的"能力问句"识别：客户在问"你们能不能"，不是"我要"
CAPABILITY_ASK = [
    r"có\s+cung\s+cấp\s+được\s+không", r"có\s+làm\s+được\s+không", r"bisa\s+(?:tidak|kah)",
    r"¿pueden", r"podem\s+fornecer", r"هل\s+يمكن", r"can\s+you\s+(?:provide|supply|issue)",
    r"do\s+you\s+(?:provide|supply|issue)", r"能否提供", r"是否可以提供",
]


def match_first(key, text, flags=re.I):
    """返回第一个命中的 match（含 group(0)），没有则 None。"""
    for pat in MULTI.get(key, []):
        m = re.search(pat, text, flags)
        if m:
            return m
    return None


def is_capability_ask(sentence):
    """客户在问能力（不是提出要求）→ 不能记成客户已确认的条款。

    只扫同一个分句（按 ; , . 切开），避免整行里出现 "cần C/O" 就把 COA 也判成问句。
    """
    s = sentence or ""
    # 1) 同一行内的问句（客户常把问句折到下一行，识别时限"当前行 + 下一行"由调用方传入）
    if "?" in s or "？" in s:
        for qs in re.split(r"\?", s):
            if any(re.search(p, qs, re.I) for p in CAPABILITY_ASK):
                return True
    # 2) 同一分句
    for clause in re.split(r"[;。.;!?]", s):
        if any(re.search(p, clause, re.I) for p in CAPABILITY_ASK):
            return True
    return False


def clean_num(x):
    """3.000 → 3000；3,000 → 3000；40 → 40。"""
    x = x.strip()
    if re.match(r"^\d{1,3}(?:[.,]\d{3})+$", x):
        return re.sub(r"[.,]", "", x)
    if re.match(r"^\d+[.,]\d+$", x):
        return x.replace(",", ".")
    return x
