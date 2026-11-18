#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thin Python wrapper around templates/engine.js (the single source of truth).

Runs the engine in the bundled Node runtime and returns a Python dict with formatted
amounts, validation results and the document state. Never re-implements the arithmetic.
"""
import json, os, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NODE = os.environ.get("QUOTE_NODE") or "node"
ENGINE = os.path.join(ROOT, "templates", "engine.js")

_JS = r"""
const E = require(process.argv[1]);
const doc = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const docType = process.argv[3] || null;
const v = E.validate(doc, docType);
const fmt = (x, dp) => (x === null || x === undefined) ? null :
  Number(x).toLocaleString('en-US', {minimumFractionDigits: dp === undefined ? 2 : dp,
                                     maximumFractionDigits: dp === undefined ? 2 : dp});
const lineAmounts = {};
for (const it of (doc.items || [])) {
  const q = Number(it.quantity), p = Number(it.unitPrice), d = Number(it.discountPct || 0);
  if (it.unitPrice === '' || it.unitPrice === null || it.unitPrice === undefined || !isFinite(p)) continue;
  lineAmounts[String(it.id || '')] = fmt(Math.round(q * p * (1 - d / 100) * 100) / 100);
}
const out = {
  version: E.VERSION,
  state: v.state, label: v.label,
  total: v.calc.total, subtotal: v.calc.subtotal,
  totalFmt: fmt(v.calc.total), subtotalFmt: fmt(v.calc.subtotal),
  words: v.calc.totalInWords,
  validUntil: v.validUntil,
  tradeTermText: v.tradeTermText,
  completeness: v.completeness,
  placeholderCount: (v.completeness && v.completeness.missing) ? v.completeness.missing.length : 0,
  lineAmounts: lineAmounts,
  errors: v.errors, warnings: v.warnings,
  problems: v.problems, checks: v.checks
};
console.log(JSON.stringify(out));
"""


def validate(case, doc_type=None):
    """Run engine.validate() on a case dict; returns the engine result as a dict."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(case, f, ensure_ascii=False)
        r = subprocess.run([NODE, "-e", _JS, ENGINE, path, doc_type or ""],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError("engine.js failed: " + (r.stderr or r.stdout)[-1500:])
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    import sys
    print(json.dumps(validate(json.load(open(sys.argv[1], encoding="utf-8"))), ensure_ascii=False, indent=2)[:2000])
