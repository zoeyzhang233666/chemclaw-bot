# -*- coding: utf-8 -*-
"""Validation rules for the import-source-country skill.

Product-agnostic: nothing here mentions MEG, HS 290531 or any country.
Each rule returns a list of (status, rule_id, detail) where status is
PASS / WARN / FAIL.

Usage
-----
    from validators import run_all
    results = run_all(data)          # data = the assembled JSON skeleton
    for status, rid, detail in results:
        ...

The rules operate on the *assembled* structure described in
references/output-spec.md, section C.
"""
import re

# ---------------------------------------------------------------- helpers

FORBIDDEN_PATTERNS = [
    # claims that must never appear as conclusions
    r"最佳(进口)?来源国", r"最优来源国", r"唯一正确", r"保证供应", r"必然涨价",
    r"肯定会", r"我判断.{0,8}最优", r"一定是最",
]

# a number token that looks like it was stated without a year nearby
NUMERIC = re.compile(r"\d[\d,]*\.?\d*")

# Phrases that mean "this figure does not exist in public sources".
# Word-bounded on purpose: a bare "n/?a" or loose substring match wrongly flags
# real evidence such as "1,025,000 MTA", "Plaquemine" or "Geismar".
MISSING_RE = re.compile(
    r"\bnot\s+found\b|\bnot\s+(?:publicly\s+)?disclosed\b|\bno\s+public\b"
    r"|\bn/?a\b|未找到|未公开披露|未披露|无法取得",
    re.I)


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _res(status, rid, detail):
    return (status, rid, detail)


# ---------------------------------------------------------------- V01-V03 trade rows

def rule_trade_rows(rows):
    """Every trade row must carry year, partner, value, quantity and a source."""
    out = []
    need = {"year", "partner_iso", "value_usd_m", "qty_kt", "source"}
    bad = [r for r in rows if not need.issubset(r)]
    out.append(_res(
        "PASS" if not bad else "FAIL", "V01-columns",
        f"{len(rows)} rows, {len(bad)} missing one of {sorted(need)}"))

    empty = [r for r in rows
             if r.get("value_usd_m") is None and r.get("qty_kt") is None]
    out.append(_res(
        "WARN" if empty else "PASS", "V02-empty-rows",
        f"{len(empty)} rows carry neither value nor quantity "
        f"(acceptable only if reported in the gap table)"))

    nosrc = [r for r in rows
             if r.get("value_usd_m") is not None and not str(r.get("source") or "").strip()]
    out.append(_res(
        "PASS" if not nosrc else "FAIL", "V03-source-required",
        f"{len(nosrc)} valued rows without a source"))
    return out


# ---------------------------------------------------------------- V04 partner sum

def rule_partner_sum(tot_value, parts_value, tot_qty, parts_qty, tol=0.005):
    """The world total must equal the sum over partners."""
    out = []
    for name, t, p in (("value", tot_value, parts_value),
                       ("quantity", tot_qty, parts_qty)):
        t = _num(t)
        p = _num(p)
        if not t or p is None:
            out.append(_res("WARN", f"V04-{name}-sum",
                            "total or partner sum unavailable"))
            continue
        dev = abs(p - t) / abs(t)
        out.append(_res(
            "PASS" if dev <= tol else "FAIL", f"V04-{name}-sum",
            f"partners {p:,.1f} vs total {t:,.1f} (dev {dev:.2%})"))
    return out


# ---------------------------------------------------------------- V05 shares

def rule_share(rows, totals=None):
    """Shares must lie in [0,1]; the sum over partners must not exceed 1."""
    out = []
    bad = [r for r in rows
           if r.get("share_cn") is not None
           and not (-1e-9 <= r["share_cn"] <= 1 + 1e-9)]
    out.append(_res("PASS" if not bad else "FAIL", "V05-share-range",
                    f"{len(bad)} out-of-range shares"))
    for y, s in (totals or {}).items():
        if s is not None and s > 1.0005:
            out.append(_res("FAIL", "V05-share-sum",
                            f"{y}: partner shares sum to {s:.4f}"))
    return out


# ---------------------------------------------------------------- V06 value/quantity

def rule_unit_value(rows, lo=100.0, hi=100000.0):
    """USD per tonne must be plausible; extreme values signal a unit error.

    lo/hi are deliberately wide (100-100 000 USD/t) because the rule must work
    for cheap bulk chemicals and for fine chemicals alike.
    """
    bad = []
    for r in rows:
        uv = _num(r.get("unit_value_usd_t"))
        if uv is None:
            v, q = _num(r.get("value_usd_m")), _num(r.get("qty_kt"))
            if v and q:
                uv = v * 1000.0 / (q * 1000.0)
        if uv is None:
            continue
        if not (lo <= uv <= hi):
            bad.append((r.get("partner_iso"), round(uv, 1)))
    return [_res("PASS" if not bad else "WARN", "V06-unit-value",
                 f"{len(bad)} implausible unit values {bad[:4]} (expected {lo}-{hi} USD/t)")]


# ---------------------------------------------------------------- V07 evidence

def rule_quote(evidence_rows):
    """Every capacity/policy claim must carry a verbatim quote AND an http URL.

    A row that has neither a number nor a quote (a pure "not found" placeholder)
    is not a claim, so it is not a violation - but it must be reported as a gap.
    A row that states a number without a quote+url is a hard failure: an
    unsourced number is exactly what this skill exists to prevent.
    """
    claims, gaps, bad = 0, [], []
    for r in evidence_rows:
        has_num = r.get("capacity_kt") not in (None, 0, "")
        # a quote that only says "not found" is a documented absence, not evidence
        q = str(r.get("quote") or "").strip()
        says_missing = bool(MISSING_RE.search(q)) if q else True
        has_quote = bool(q) and not says_missing
        has_url = str(r.get("source_url") or "").startswith("http")
        name = r.get("company") or r.get("site") or "?"
        if not has_num:
            gaps.append(name)
            continue
        claims += 1
        if not (has_quote and has_url):
            bad.append(name)
    out = [_res("PASS" if not bad else "FAIL", "V07-evidence-quote",
                f"{len(bad)} of {claims} numeric evidence rows lack quote+url: {bad[:4]}")]
    if gaps:
        out.append(_res("WARN", "V07-evidence-gap",
                        f"{len(gaps)} evidence rows carry no number and no quote "
                        f"(placeholders, must appear in the gap table): {gaps[:4]}"))
    return out


# ---------------------------------------------------------------- V08 forbidden conclusions

def rule_forbidden(text):
    """No 'best source country' conclusions, no unhedged certainty."""
    hits = []
    for pat in FORBIDDEN_PATTERNS:
        hits.extend(re.findall(pat, text))
    return [_res("PASS" if not hits else "FAIL", "V08-forbidden-conclusions",
                 f"{len(hits)} banned phrases: {sorted(set(hits))[:5]}")]


# ---------------------------------------------------------------- V09 capacity vs trade

def rule_capacity_vs_trade(capacity_kt, exports_to_cn_kt, country, coverage=None):
    """Published capacity should be able to cover exports to China.

    Three distinct outcomes:
      * capacity is None/0  -> UNKNOWN: no published figure. This is a gap,
        not a contradiction, so it must NOT be reported as a failure.
      * capacity >= exports -> PASS
      * capacity <  exports but coverage < 1.0 -> WARN: the disclosed sites are
        only part of the country's plants, so the shortfall is explained by the
        undisclosed remainder. Requires the explanation to be in the report.
      * capacity <  exports and coverage >= 1.0 -> FAIL: either the capacity
        figure is wrong or the trade figure is transhipped.
    """
    c, e = _num(capacity_kt), _num(exports_to_cn_kt)
    if not c:
        return [_res("PASS", "V09-capacity-vs-trade",
                     f"{country}: no published capacity (gap, not a contradiction); "
                     f"exports-to-CN {e or 0:,.0f} kt must appear in the gap table")]
    if e is None:
        return [_res("WARN", "V09-capacity-vs-trade",
                     f"{country}: capacity {c:,.0f} kt but no export figure")]
    if c >= e:
        return [_res("PASS", "V09-capacity-vs-trade",
                     f"{country}: capacity {c:,.0f} kt covers exports-to-CN {e:,.0f} kt")]
    cov = _num(coverage)
    ratio = c / e if e else None
    if cov is not None and cov < 1.0:
        return [_res("WARN", "V09-capacity-vs-trade",
                     f"{country}: disclosed sites {c:,.0f} kt < exports-to-CN {e:,.0f} kt "
                     f"(coverage {cov:.0%}; shortfall explained by undisclosed plants - say so in the report)")]
    return [_res("FAIL", "V09-capacity-vs-trade",
                 f"{country}: capacity {c:,.0f} kt < exports-to-CN {e:,.0f} kt "
                 f"with full coverage - either the capacity figure or the trade figure is wrong")]


# ---------------------------------------------------------------- V10 mirror reconciliation

def rule_reconciliation(cn_import_m, partner_export_m, country, tol=0.30):
    """China's reported imports (CIF) vs the partner's reported exports (FOB).

    A positive deviation is normal (CIF > FOB, order of 5-20%). Beyond `tol`
    the deviation must be explained in the checks table, not silently dropped.
    """
    a, b = _num(cn_import_m), _num(partner_export_m)
    if not a or not b:
        return [_res("WARN", "V10-mirror", f"{country}: missing input")]
    dev = (a - b) / a
    status = "PASS" if abs(dev) <= tol else "WARN"
    return [_res(status, "V10-mirror",
                 f"{country}: CN imports {a:,.1f} vs partner exports {b:,.1f} "
                 f"(dev {dev:+.1%}; CIF>FOB is normal, transhipment is not)")]


# ---------------------------------------------------------------- V11 year coverage

def rule_year_coverage(years, required):
    missing = [y for y in required if y not in years]
    return [_res("PASS" if not missing else "WARN", "V11-years",
                 f"missing years {missing} (must appear in the gap table)")]


# ---------------------------------------------------------------- V12 gaps declared

def rule_gaps_declared(partners, gaps):
    """Countries with no published capacity must be named somewhere in the gap table."""
    gap_text = " ".join(str(g.get("item", "")) + str(g.get("why", "")) + str(g.get("fix", ""))
                        for g in gaps)
    silent = []
    for p in partners:
        if p.get("capacity_kt"):
            continue
        label = p.get("label") or ""
        iso = p.get("iso") or ""
        if not label or iso in ("//CHN", "CHN", "WLD", ""):
            continue
        if label not in gap_text and iso not in gap_text:
            silent.append(label)
    return [_res("PASS" if not silent else "WARN", "V12-gaps-declared",
                 f"{len(silent)} countries without published capacity not named in gaps: {silent[:6]}")]


# ---------------------------------------------------------------- V13 logistics freshness

def rule_logistics_stale(logistics, asof_expected):
    """Chokepoint status must carry an as-of date matching the report date."""
    got = str((logistics or {}).get("asof") or "")
    ok = got == str(asof_expected)
    return [_res("PASS" if ok else "FAIL", "V13-logistics-asof",
                 f"logistics as-of {got!r} vs report {asof_expected!r}")]


# ---------------------------------------------------------------- runner

def run_all(data):
    """Run every applicable rule over the assembled data structure."""
    res = []
    years = data.get("years") or []
    partners = data.get("partners") or []
    tmap = {t["year"]: t for t in (data.get("totals") or [])}

    # per-year trade rows built from china_import_partners
    rows = []
    for y, plist in (data.get("china_import_partners") or {}).items():
        for p in plist:
            rows.append(dict(year=int(y), partner_iso=p.get("iso"),
                             value_usd_m=p.get("value_m"), qty_kt=p.get("qty_kt"),
                             unit_value_usd_t=p.get("unit_value"),
                             share_cn=p.get("share"),
                             source="UN Comtrade"))

    res += rule_trade_rows(rows)
    if years:
        last = max(years)
        pl = data["china_import_partners"][str(last)]
        res += rule_partner_sum(
            tmap[last]["value_m"], sum(p.get("value_m") or 0 for p in pl),
            tmap[last]["qty_kt"], sum(p.get("qty_kt") or 0 for p in pl))
        sums = {}
        for y, plist in data["china_import_partners"].items():
            sums[int(y)] = sum(p.get("share") or 0 for p in plist)
        res += rule_share(rows, sums)

    res += rule_unit_value(rows)
    res += rule_quote(data.get("producer_rows") or [])

    body = " ".join(str(v) for v in [
        data.get("meta", {}).get("title", ""),
        data.get("cn_ports_note", ""),
        (data.get("logistics") or {}).get("headline", ""),
        " ".join(str(g.get("item", "")) for g in (data.get("gaps") or [])),
    ])
    res += rule_forbidden(body)

    for p in partners:
        res += rule_capacity_vs_trade(p.get("capacity_kt"), p.get("qty_kt"),
                                      p.get("label") or p.get("iso"),
                                      p.get("capacity_coverage"))
    res += rule_year_coverage(years, [y for y in range(2021, 2026)])
    res += rule_gaps_declared(partners, data.get("gaps") or [])
    if data.get("logistics"):
        res += rule_logistics_stale(data["logistics"],
                                    data.get("meta", {}).get("asof")
                                    or data.get("logistics", {}).get("asof"))
    return res


def summarize(results):
    """One-line summary plus the failing details."""
    n = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for s, _, _ in results:
        n[s] = n.get(s, 0) + 1
    lines = [f"{k}:{v}" for k, v in n.items()]
    fails = [f"  [{s}] {rid}: {d}" for s, rid, d in results if s != "PASS"]
    return " ".join(lines) + ("\n" + "\n".join(fails) if fails else "")


if __name__ == "__main__":
    import json
    import os
    import sys

    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (sys.argv[1] if len(sys.argv) > 1 else None,
                 os.path.join(here, "..", "examples", "data.json")):
        if cand and os.path.exists(cand):
            data = json.load(open(cand, encoding="utf-8"))
            print(summarize(run_all(data)))
            break
    else:
        print("usage: python validators.py <data.json>")
