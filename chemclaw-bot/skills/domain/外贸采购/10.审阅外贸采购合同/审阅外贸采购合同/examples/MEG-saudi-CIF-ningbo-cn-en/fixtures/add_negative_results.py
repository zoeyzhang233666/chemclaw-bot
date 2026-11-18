"""补充「已审未见风险（负结果）」清单，供 HTML/Excel 展示，避免被误读为漏审。"""
import json
from pathlib import Path

P = Path(r"./intl-procurement-contract-review\examples\MEG-saudi-CIF-ningbo-cn-en\review.json")
data = json.loads(P.read_text(encoding="utf-8"))

NEGATIVE = [
    {"clause_ids": ["C01"], "note": "封面与模拟合同标识：仅用于声明文件性质，不含权利义务约定，未产生可作为审查对象的条款；其「SIMULATED」标识与本案一致。"},
    {"clause_ids": ["C09", "C10"], "note": "合同金额与价格固定条款：金额与第 5.1、1.1 条自洽（5,000 MT × USD 512.00 = USD 2,560,000），未发现算术错误；固定价本身不构成风险点，但其与「关税/汇率不调价」的组合已在 R17、R04 中作为背景提示。"},
    {"clause_ids": ["C34"], "note": "签署条款：「签署 + 卖方邮件回传」生效对买方基本可行；未发现明显不利，但未约定双方法定代表人或授权代表身份证明，建议在尽调环节补充（未单列为风险）。"},
    {"clause_ids": ["A1-C1", "A1-C2"], "note": "附件 1 表头（Parameter / Specification）：表头为中性表述，未发现风险；其内容缺陷已在 R07 中针对具体数据行说明。"},
    {"clause_ids": ["A1-T3", "A1-T4", "A1-T5", "A1-T6", "A1-T7"], "note": "附件 1 中 DEG/TEG/Fe/UV 透光率数据行：指标有明确上限/下限，未发现数值或方向错误；缺少的是方法版本与空白项，已在 R06、R07 中合并说明。"},
    {"clause_ids": ["A2-T1", "A2-T2", "A2-T3", "A2-T4", "A2-T5", "A2-T6", "A2-T8"], "note": "附件 2 中除 SDS 外的单据行：单据种类与第 8.3 条基本对应；提单「3/3 正本、clean on board」表述本身可用，其份数与抬头细节已在 R04 中提示。"},
]
data["negative_results"] = NEGATIVE
P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("negative_results:", len(NEGATIVE), "covering", sum(len(x["clause_ids"]) for x in NEGATIVE), "clauses")
