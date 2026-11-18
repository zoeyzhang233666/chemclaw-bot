"""Refresh the case JSON facts that come straight from the raw Comtrade dump.

Keeps numbers and partner rows in sync with raw/ so the case can never drift from its evidence.
  python sync_case.py --raw ../raw/comtrade_360_283620.json --case ../examples/01-idn-soda-ash/case.json
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import calc_trade as CT  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--years", default="")
    ap.add_argument("--exporter", default="156")
    a = ap.parse_args()

    raw = C.load_json(a.raw)
    case = C.load_json(a.case)
    years = ([int(x) for x in a.years.split(",")] if a.years
             else sorted(int(y) for y in (C.jget(raw, "IDN", "M", default={}) or {}).keys()))
    facts = CT.analyze(raw, years, int(a.exporter))

    # trade.imports and trade.imports_history: every year available in raw
    trade = case.setdefault("trade", {})
    hist = []
    for y in years:
        row = next((r for r in facts["imports"] if r["year"] == y), None)
        if row:
            hist.append({"year": y, "value_usd": row["value_usd"], "qty_t": row["qty_t"], "source": "comtrade"})
    win = int(case.get("meta", {}).get("window") or 5)
    trade["imports_history"] = hist
    trade["imports"] = hist[-win:]
    trade["partners"] = {str(y): facts["partners"].get(y) or [] for y in years}
    trade["exports"] = facts["exports"]
    trade["china_exports"] = [
        {"year": r["year"], "to_idn_usd": r["to_reporter_usd"], "to_idn_t": r["to_reporter_t"],
         "to_world_usd": r["to_world_usd"]} for r in facts["exporter_rows"]]
    C.save_json(case, a.case)
    print("synced %s  imports=%d partners_years=%d china_rows=%d" % (
        a.case, len(trade["imports"]), len(trade["partners"]), len(trade["china_exports"])))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
