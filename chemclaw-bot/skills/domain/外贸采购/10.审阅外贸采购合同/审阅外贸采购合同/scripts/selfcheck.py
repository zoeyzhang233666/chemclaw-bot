"""数据完整性自检：逐字引用、条款覆盖、标签合理性、清单一致性。"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

DEFAULT_CASE = SKILL_ROOT / "examples" / "MEG-saudi-CIF-ningbo-cn-en"


def _resolve(argv) -> Path:
    if "--dir" in argv:
        return Path(argv[argv.index("--dir") + 1]).resolve()
    return DEFAULT_CASE
from common import load_case, validate_case, _norm  # noqa: E402

CASE = _resolve(sys.argv)
print(f"[dir] {CASE}")
case = load_case(CASE)
contract, review = case["contract"], case["review"]
clauses = {c["id"]: c for c in contract["clauses"]}
problems = []

# 1. 校验器
chk = validate_case(contract, review)
print(f"[1] validate: errors={len(chk['errors'])} warnings={len(chk['warnings'])}")
problems += chk["errors"]

# 2. 逐字引用（严格包含 + 规范化包含都要过）
n_q = 0
for f in review["findings"]:
    for q in f.get("quotes", []):
        n_q += 1
        src = clauses[q["clause_id"]]["text"]
        if q["text"] not in src and _norm(q["text"]) not in _norm(src):
            problems.append(f"非逐字: {f['id']} {q['clause_id']}")
print(f"[2] quotes checked: {n_q}")

# 3. 条款覆盖
clause_hit = set()
for f in review["findings"]:
    clause_hit.update(f["clause_ids"])
print(f"[3] clauses={len(clauses)} referenced={len(clause_hit)} unreferenced={sorted(set(clauses)-clause_hit)}")

# 4. 标签：写入「不含风险」的条款不应被引用（除了明确设计为对照的）
for cid in ("C01",):
    if cid in clause_hit:
        problems.append(f"{cid} 是封面（含错误标识），不应被引用为风险")

# 5. 每条风险的 to_confirm 与 confirmations 对应
conf_ids = {q["finding_id"] for items in review["confirmations"].values() for q in items}
for f in review["findings"]:
    if f["id"] not in conf_ids:
        problems.append(f"{f['id']} 不在任何清单中")
    if not f.get("title_en"):
        problems.append(f"{f['id']} 缺 title_en")

# 6. 中英问题一一对应（供应商清单）
for owner, items in review["confirmations"].items():
    for q in items:
        if not q.get("question_en") and owner == "supplier":
            problems.append(f"供应商问题缺英文: {q['finding_id']}")

# 7. 关键数字一致性
cb = review["summary"]["calc_basis"]
calc = {
    "contract_value_usd": cb["quantity_mt"] * cb["unit_price_usd"],
    "advance_usd": cb["quantity_mt"] * cb["unit_price_usd"] * cb["advance_pct"],
    "balance_usd": cb["quantity_mt"] * cb["unit_price_usd"] * (1 - cb["advance_pct"]),
    "ld_per_day_usd": cb["contract_value_usd"] * 0.0005,
    "ld_cap_usd": cb["contract_value_usd"] * cb["ld_cap_pct"],
}
for k, v in calc.items():
    got = cb[k]
    ok = abs(got - v) < 1e-6
    print(f"[7] {k}: table={got} calc={v} {'OK' if ok else 'MISMATCH'}")
    if not ok:
        problems.append(f"测算不一致 {k}")

# 8. 引用中出现的金额是否与合同一致（防止编造数字）
texts = " ".join(f["business_impact"] for f in review["findings"])
allowed = {f"{v:,}".replace(",", "") for k, v in cb.items() if isinstance(v, (int, float)) and v >= 1000}
allowed |= {"768000", "1792000", "2560000", "128000", "1280", "12800"}
for amt in re.findall(r"USD [\d,]+", texts):
    v = amt.replace("USD ", "").replace(",", "")
    if v not in allowed:
        problems.append(f"业务影响中出现未登记金额: {amt}")
print(f"[8] amount scan done; allowed={sorted(allowed)}")

# 9. 覆盖率：条款总数 = 被风险引用 + 负结果覆盖 + 未覆盖（未覆盖必须为 0）
neg = {c for n in review.get("negative_results", []) for c in n["clause_ids"] if c in clauses}
left = sorted(set(clauses) - clause_hit - neg)
print(f"[9] coverage: total={len(clauses)} hit={len(clause_hit)} negative={len(neg)} uncovered={len(left)}")
if left:
    problems.append(f"未覆盖条款（既无风险也未列入负结果）: {left}")
for n in review.get("negative_results", []):
    bad = [c for c in n["clause_ids"] if c not in clauses]
    if bad:
        problems.append(f"负结果引用了不存在的条款: {bad}")
    if set(n["clause_ids"]) & clause_hit:
        problems.append(f"负结果与风险引用重叠: {n['clause_ids']}")

print()
print("PROBLEMS:", len(problems))
for p in problems:
    print("  -", p)
sys.exit(1 if problems else 0)
