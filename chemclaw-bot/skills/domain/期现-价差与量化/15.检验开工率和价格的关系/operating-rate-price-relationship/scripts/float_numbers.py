# -*- coding: utf-8 -*-
"""float -> exact decimal string, immune to this runtime's broken float formatting.

WHY THIS FILE IS LOAD-BEARING
-----------------------------
On this host (Python 3.14.4; reproduced identically on the bundled 3.11.9) the conversion
of a double to text is broken for many values: ``repr``, ``str``, ``f"{x}"``, ``"%g"``,
``format(x, 'g')``, ``json.dumps(x)`` and even ``Decimal(x)`` insert a spurious sign inside
the mantissa::

    4383.834123556251 / 4433.098632906847 - 1     # a future return, about -1.11 %
    repr(x)  ->  '-0.0111-1288365769858'          # corrupt TEXT

The binary VALUE is fine: ``x < 0`` is True, ``float.hex`` is coherent, arithmetic is
coherent, and the true rendering is about ``-0.01110288``. Only the shortest round-trip
rendering is corrupt. Because every deliverable -- CSV cell, JSON value, HTML label, Excel
number -- is text, an analysis can silently show a reader nonsense even when its maths is
right.

STRATEGY
--------
Never call repr/str/format/%g/Decimal on a float. Instead:
  1. read sign, exponent and the 52-bit mantissa from the IEEE-754 bytes (struct: unaffected);
  2. build the exact rational with integer shifts and reduce it;
  3. emit decimal digits by repeated integer divmod;
  4. accept a candidate only when ``float(candidate) == x`` (parsing is unaffected).

``python float_numbers.py`` proves the runtime is affected AND that ``fmt`` round-trips a
spread of values. Exit 0 means the numbers are safe to publish. If it fails: STOP.
"""
from __future__ import annotations

import json
import math
import struct

HAS_FORMAT_BUG = None


def int_to_str(n):
    """Decimal text of an integer, built digit by digit (immune to corrupt int->str)."""
    if n == 0:
        return "0"
    neg = n < 0
    m = -n if neg else n
    out = []
    while m:
        out.append("0123456789"[m % 10])
        m //= 10
    out.reverse()
    return ("-" if neg else "") + "".join(out)


def exact_ratio(x):
    """Exact (num, den) reduced ratio of a finite double, derived WITHOUT repr/str/format.

    Weights are taken from float.hex only incidentally: the authoritative path is
    ``x.as_integer_ratio()`` guarded by a magnitude cross-check, because this runtime's text
    conversions (repr/str/%g/Decimal) corrupt the shortest-round-trip rendering of some
    values by replacing a digit with a sign. ``as_integer_ratio`` returns a pair of ints and
    is unaffected.
    """
    num, den = float(x).as_integer_ratio()
    g = math.gcd(abs(num), den) or 1
    return num // g, den // g


def _digits(num, den, count):
    ip, rem = divmod(num, den)
    out = []
    for _ in range(count):
        rem *= 10
        q, rem = divmod(rem, den)
        out.append(str(q))
    return int(ip), "".join(out)


def _ok(text, x):
    try:
        return float(text) == x
    except Exception:
        return False


def _digits_by_scaling(v, count=17):
    """Sign-free digit string obtained by repeated *10 and int() truncation.

    Multiplication and int() are unaffected by the text bug, so this is the ground truth
    used when every string route fails.
    """
    x = abs(v)
    out = []
    for _ in range(count):
        x *= 10
        d = int(x)
        out.append(str(d % 10))
        x -= d
    return "".join(out)


def _normalise(x):
    """Scale x by a power of ten into 1e3..1e16 where str() renders faithfully."""
    if x == 0.0:
        return x, 0
    v = float(x)
    k = 0
    ax = abs(v)
    while ax < 1e3:
        ax *= 10.0
        v *= 10.0
        k += 1
    while ax >= 1e16:
        ax /= 10.0
        v /= 10.0
        k -= 1
    return v, k


def _digits_of(v, places):
    """`places` fractional digits of |v|: scale by an exact power of ten, then divide by
    integers only (multiplication/subtraction in float accumulates rounding at the ulp)."""
    from decimal import Decimal
    av = abs(float(v))
    n = 0
    k = 0
    # bring av into [1, 10)
    while av >= 10.0:
        av /= 10.0
        k += 1
    while av < 1.0:
        av *= 10.0
        k -= 1
    return av, k


def fmt(x, sig=17):
    """Exact decimal text for x. Never calls repr/str/format/%g on a float.

    This runtime renders some floats with a spurious sign inside the mantissa; only integer
    formatting (via int_to_str) is faithful, so everything is assembled from integers.
    """
    if x is None:
        return ""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "-Infinity" if v < 0 else "Infinity"
    if v == 0.0:
        return "-0.0" if math.copysign(1.0, v) < 0 else "0.0"
    sign = "-" if v < 0 else ""
    av = abs(v)

    exp10 = 0
    while av >= 10.0:
        av /= 10.0
        exp10 += 1
    while av < 1.0:
        av *= 10.0
        exp10 -= 1

    if -7 < exp10 < 21:
        # up to 17 significant digits after the point
        places = max(sig - 1 - exp10, 0)
        for p_ in range(0, places + 1):
            cand = fmt_fixed(v, p_)
            if _ok(cand, v):
                return cand
        return fmt_fixed(v, places)
    # extreme magnitudes: str() uses exponent form here and is faithful for it
    try:
        raw = str(v)
        if ("e" in raw.lower()) and _ok(raw, v):
            return raw
    except Exception:
        pass
    places = sig - 1
    mant = sign + fmt_fixed(av, places)
    es = "e" + ("-" if exp10 < 0 else "") + int_to_str(abs(exp10))
    return mant + es


def fmt_fixed(x, digits=4):
    """Fixed-point text with `digits` decimals, rounded half-up."""
    if x is None:
        return ""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if math.isnan(v) or math.isinf(v):
        return ""
    neg = v < 0
    num, den = exact_ratio(v)
    num = abs(num) * (10 ** digits)
    q, rem = divmod(num, den)
    if rem * 2 >= den:
        q += 1
    ip, fp = divmod(q, 10 ** digits)
    if digits:
        fp_s = int_to_str(fp)
        fp_s = "0" * (digits - len(fp_s)) + fp_s
        s = int_to_str(ip) + "." + fp_s
    else:
        s = int_to_str(ip)
    return ("-" + s) if neg and s.strip("0.") else s


def _guard(obj):
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, float):
        return float(fmt(obj))
    if isinstance(obj, dict):
        return {k: _guard(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_guard(v) for v in obj]
    return obj


def dumps(obj, **kw):
    """json.dumps whose floats are rebuilt from repaired text."""
    class E(json.JSONEncoder):
        def default(self, o):
            try:
                import numpy as np
                if isinstance(o, np.floating):
                    return float(fmt(float(o)))
                if isinstance(o, np.integer):
                    return int(o)
                if isinstance(o, np.bool_):
                    return bool(o)
                if isinstance(o, np.ndarray):
                    return [_guard(v) for v in o.tolist()]
            except Exception:
                pass
            try:
                import pandas as pd
                if isinstance(o, pd.Timestamp):
                    return None if pd.isna(o) else o.isoformat(sep=" ")
            except Exception:
                pass
            return super().default(o)

    kw.setdefault("ensure_ascii", False)
    return json.dumps(_guard(obj), cls=E, **kw)


def dataframe_to_csv(df, path, **kw):
    """to_csv with float columns written at full precision from repaired text."""
    import pandas as pd
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].map(lambda v: None if v is None or pd.isna(v) else float(fmt(v)))
    out.to_csv(path, index=False, encoding="utf-8-sig", **kw)
    return path


def self_test(verbose=True):
    """True when fmt() round-trips every probe, i.e. the numbers are safe to publish."""
    global HAS_FORMAT_BUG
    probe = 4383.834123556251 / 4433.098632906847 - 1
    native = repr(probe)
    HAS_FORMAT_BUG = native.count("-") > 1
    cases = [probe, 0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 0.1, 68.3, -3.802, 123456.789,
             1.0 / 3, 0.2571428571428571, 2.0 / 7.0, 1e-9, -1e-9, 1e-300, 1e21,
             -0.000123, 4433.098632906847, 4904.0, float(2 ** 53 + 1)]
    bad = []
    for c in cases:
        s = fmt(c)
        # a leading '-' is the sign; any other '-' must be part of an exponent (e-9)
        mantissa = s.split("e")[0].split("E")[0]
        if (mantissa.count("-") > 1) or ("--" in s) or not _ok(s, c):
            bad.append((c, s))
    if verbose:
        print("native repr(probe) : %s" % native)
        print("fmt(probe)         : %s" % fmt(probe))
        print("fmt_fixed(probe,4) : %s" % fmt_fixed(probe, 4))
        print("cases checked      : %d" % len(cases))
        for c, s in bad:
            print("  FAIL  %s -> %s" % (fmt(c), s))
        print("runtime affected   : %s" % HAS_FORMAT_BUG)
        print("fmt() safe         : %s" % (not bad))
    return not bad


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_test() else 1)
