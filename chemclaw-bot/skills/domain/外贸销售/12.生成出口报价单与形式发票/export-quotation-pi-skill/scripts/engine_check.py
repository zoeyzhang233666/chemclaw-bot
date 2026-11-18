#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Allow `python scripts/engine_check.py case.json` to print engine validation
via the bundled Node runtime (the engine itself is engine.js)."""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NODE = os.environ.get("QUOTE_NODE") or "node"
JS = r"""
const E = require(process.argv[1]);
const doc = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const v = E.validate(doc);
// independent arithmetic check (plain math, no engine rounding helpers)
let ind = 0, anyMissing = false;
for (const it of (doc.items || [])) {
  const q = Number(it.quantity), p = Number(it.unitPrice), d = Number(it.discountPct || 0);
  if (it.unitPrice === '' || it.unitPrice === null || it.unitPrice === undefined || !isFinite(p)) { anyMissing = true; continue; }
  ind += q * p * (1 - d / 100);
}
let charges = 0;
for (const c of (doc.charges || [])) {
  const n = Number(c.amount);
  if (c.amount !== '' && c.amount !== null && c.amount !== undefined && isFinite(n) && c.addToTotal !== false) charges += n;
}
const indTotal = anyMissing ? null : Math.round((ind + charges) * 100) / 100;
const out = {state: v.state, label: v.label, total: v.calc.total, subtotal: v.calc.subtotal,
  independent_total: indTotal, independent_match: indTotal !== null && v.calc.total !== null ? Math.abs(indTotal - v.calc.total) < 0.011 : (indTotal === v.calc.total),
  inWords: v.calc.totalInWords, errors: v.errors.length, warnings: v.warnings.length,
  completeness: {filled: v.completeness.filled, required: v.completeness.required, missing: v.completeness.missing},
  checks: v.checks.map(c => c.key + ':' + c.status),
  problems: v.problems.map(p => p.severity.toUpperCase() + ' ' + p.code + ' — ' + p.msg)};
console.log(JSON.stringify(out));
"""

def main():
    case = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "demo-ex001-soda-ash-indonesia.json")
    r = subprocess.run([NODE, "-e", JS, os.path.join(ROOT, "templates", "engine.js"), case],
                       capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(r.stdout or "")
    sys.stderr.write(r.stderr or "")
    return r.returncode

if __name__ == "__main__":
    sys.exit(main())
