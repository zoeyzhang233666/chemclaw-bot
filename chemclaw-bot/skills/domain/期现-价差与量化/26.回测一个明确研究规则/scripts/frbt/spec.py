# -*- coding: utf-8 -*-
"""Specification model for a backtested research rule.

A "rule spec" is the single source of truth for every number the backtester produces.
It is written either by a human in YAML/JSON or by an agent that parsed a natural-language
rule. `docs/SPEC_SCHEMA.md` documents every field, and `provenance` records where each
number came from so that a review cannot mistake an assumption for a contract fact.

Nothing in this module is specific to methanol: commodities, exchanges, contract
multipliers, trading windows and cost models are all data.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

SUPPORTED_SIGNAL_OPS = {
    "channel_change": "indicator at lower channel changed by <= threshold (drawdown in channel units)",
    "change_run": "indicator strictly falling/rising for N consecutive published points",
    "level": "indicator compared with a constant",
    "zscore": "indicator vs rolling mean / rolling std",
    "cross_section": "rule referenced another instrument; run rule by rule",
}

SUPPORTED_PRICE_OPS = {"pct_quantile": "basis vs rolling percentile of the same definition"}


@dataclass
class RuleSpec:
    """A validated, serialisable research-rule specification."""

    raw: dict = field(default_factory=dict)

    # ---------------------------------------------------------------- helpers
    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def fingerprint(self) -> str:
        """Stable hash of the rule definition (everything except runtime paths)."""
        payload = copy.deepcopy(self.raw)
        payload.pop("runtime", None)
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    # ------------------------------------------------------------- validation
    def validate(self) -> list[str]:
        errors, _ = validate_dict(self.raw)
        return errors

    def require(self) -> None:
        errors = self.validate()
        if errors:
            raise SpecError("; ".join(errors))


class SpecError(ValueError):
    """Raised when a rule spec is structurally invalid or unsafe to trade."""


REQUIRED_BLOCKS = ("meta", "universe", "contract", "timing", "signal", "price_filter",
                   "entry", "exit", "position", "costs", "data")

PROVENANCE_KEYS = {"contract_spec", "margin_rate", "fee_per_lot", "slippage_ticks",
                   "tick_size", "multiplier", "indicator_publication"}


def validate_dict(d: dict) -> tuple[list[str], list[str]]:
    """Structural validation. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(d, dict):
        return ["rule spec must be a mapping"], []
    for blk in REQUIRED_BLOCKS:
        if blk not in d or not isinstance(d[blk], dict):
            errors.append("missing block: %s" % blk)
    if errors:
        return errors, warnings

    prov = d.get("provenance", {})
    if not isinstance(prov, dict):
        errors.append("provenance must be a mapping")
        prov = {}
    for k in PROVENANCE_KEYS:
        if k not in prov:
            errors.append("provenance missing key: %s (assumptions must be labelled)" % k)
        elif not isinstance(prov[k], dict) or "basis" not in prov[k]:
            errors.append("provenance[%s] must state a basis" % k)

    # ---- universe / contract
    uni = d["universe"]
    if not uni.get("exchange"):
        errors.append("universe.exchange is required")
    if not uni.get("product_code"):
        errors.append("universe.product_code is required (exchange code, e.g. MA)")
    if uni.get("direction_mode") not in ("long", "short", "both"):
        errors.append("universe.direction_mode must be long|short|both")

    con = d["contract"]
    if con.get("selection") not in ("kth_by_open_interest", "front_month", "fixed_contract"):
        errors.append("contract.selection must be kth_by_open_interest|front_month|fixed_contract")
    if con.get("selection") == "kth_by_open_interest" and int(con.get("k", 1)) < 1:
        errors.append("contract.k must be >= 1")
    if int(con.get("roll_lead_days", 0)) < 0:
        errors.append("contract.roll_lead_days must be >= 0")
    if con.get("roll_rule") not in ("open_interest_kth", "delivery_month_lead", "none"):
        errors.append("contract.roll_rule must be open_interest_kth|delivery_month_lead|none")
    if float(con.get("no_trade_window_days_before_delivery", 0)) < 0:
        errors.append("contract.no_trade_window_days_before_delivery must be >= 0")

    # ---- timing
    tim = d["timing"]
    for k in ("signal_cutoff_same_day", "entry_lag_sessions"):
        if k not in tim:
            errors.append("timing.%s is required" % k)
    if tim.get("prices") not in ("open", "close", "settle"):
        errors.append("timing.prices must be open|close|settle")
    if tim.get("indicator_lag_sessions_min", 0) < 0:
        errors.append("timing.indicator_lag_sessions_min must be >= 0")
    if tim.get("same_day_release_price") is not None and tim["same_day_release_price"] not in ("close", "settle"):
        errors.append("timing.same_day_release_price must be close|settle|null")

    # ---- signal
    sig = d["signal"]
    ops = sig.get("ops") or []
    if not ops:
        errors.append("signal.ops is empty")
    for i, op in enumerate(ops):
        kind = op.get("type")
        if kind not in SUPPORTED_SIGNAL_OPS:
            errors.append("signal.ops[%d].type unsupported: %r" % (i, kind))
            continue
        if kind == "channel_change":
            if "n" not in op or int(op["n"]) < 2:
                errors.append("signal.ops[%d].n must be >= 2" % i)
            if "threshold" not in op:
                errors.append("signal.ops[%d].threshold required" % i)
        if kind == "change_run":
            if int(op.get("weeks", 0)) < 1:
                errors.append("signal.ops[%d].weeks must be >= 1" % i)
            if op.get("direction") not in ("down", "up"):
                errors.append("signal.ops[%d].direction must be down|up" % i)
        if kind == "zscore" and not op.get("threshold"):
            errors.append("signal.ops[%d].threshold required" % i)
        if op.get("min_history") is not None and int(op["min_history"]) < 2:
            errors.append("signal.ops[%d].min_history must be >= 2" % i)
    if sig.get("combine") not in ("and", "or"):
        errors.append("signal.combine must be and|or")
    if not sig.get("indicator"):
        errors.append("signal.indicator is required (indicator id from the data manifest)")

    # ---- price filter
    pf = d["price_filter"]
    if pf.get("enabled"):
        op = pf.get("type")
        if op not in SUPPORTED_PRICE_OPS:
            errors.append("price_filter.type unsupported: %r" % op)
        if "lookback_points" not in pf or int(pf["lookback_points"]) < 20:
            errors.append("price_filter.lookback_points must be >= 20")
        if pf.get("side") not in ("above", "below"):
            errors.append("price_filter.side must be above|below")
        thr = float(pf.get("threshold", 0))
        if not (0.0 < thr <= 1.0):
            errors.append("price_filter.threshold must be in (0,1]")
    if pf.get("basis_mapping") not in ("spot_minus_fut", "fut_minus_spot"):
        errors.append("price_filter.basis_mapping must be spot_minus_fut|fut_minus_spot")

    # ---- entry / exit / position
    ent = d["entry"]
    if ent.get("order_type") not in ("market_next_open", "limit_next_open", "none"):
        errors.append("entry.order_type invalid")
    if ent.get("reentry_while_holding") not in ("ignore", "pyramid", "restart_holding"):
        errors.append("entry.reentry_while_holding invalid")
    ex = d["exit"]
    if int(ex.get("max_hold_sessions", 0)) < 1:
        errors.append("exit.max_hold_sessions must be >= 1")
    if ex.get("take_profit_pct") is not None and float(ex["take_profit_pct"]) <= 0:
        errors.append("exit.take_profit_pct must be > 0 or null")
    if ex.get("stop_loss_pct") is not None and float(ex["stop_loss_pct"]) <= 0:
        errors.append("exit.stop_loss_pct must be > 0 or null")
    pos = d["position"]
    if pos.get("sizing") not in ("fixed_lots", "pct_equity_notional", "pct_equity_margin"):
        errors.append("position.sizing invalid")
    if float(pos.get("lots", 0)) <= 0 and pos.get("sizing") == "fixed_lots":
        errors.append("position.lots must be > 0 for fixed_lots sizing")
    if float(pos.get("max_margin_utilisation", 0)) <= 0 or float(pos.get("max_margin_utilisation", 0)) > 1:
        errors.append("position.max_margin_utilisation must be in (0,1]")
    if float(pos.get("capital", 0)) <= 0:
        errors.append("position.capital must be > 0")

    # ---- costs
    cst = d["costs"]
    for k in ("fee_mode", "fee_value", "slippage_ticks", "tick_size", "multiplier",
              "margin_rate", "commission_min_per_lot"):
        if k not in cst:
            errors.append("costs.%s is required" % k)
    if cst.get("fee_mode") not in ("per_lot", "pct_notional"):
        errors.append("costs.fee_mode must be per_lot|pct_notional")
    for k in ("slippage_ticks", "tick_size", "multiplier", "margin_rate", "fee_value"):
        try:
            if float(cst.get(k, 0)) < 0:
                errors.append("costs.%s must be >= 0" % k)
        except (TypeError, ValueError):
            errors.append("costs.%s must be numeric" % k)

    # ---- data
    dat = d["data"]
    if not dat.get("indicator_file"):
        errors.append("data.indicator_file is required")
    if not dat.get("contracts_file"):
        errors.append("data.contracts_file is required")
    if dat.get("publication_mode") not in ("strict", "backfill_assumed"):
        errors.append("data.publication_mode must be strict|backfill_assumed")
    if dat.get("publication_mode") == "backfill_assumed" and not dat.get("assumed_publish_time"):
        errors.append("data.assumed_publish_time required for backfill_assumed mode")

    # ---- warnings about unverifiable assumptions
    if prov.get("contract_spec", {}).get("basis", "").startswith("assumed"):
        warnings.append("contract specification (multiplier/fee/margin) is assumed; verify with the exchange")
    if d["data"].get("publication_mode") == "backfill_assumed":
        warnings.append("publication_mode=backfill_assumed: signal availability uses an assumed clock")
    return errors, warnings


def load_spec(path: str) -> RuleSpec:
    """Load YAML or JSON rule spec."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise SpecError(
                "PyYAML not installed; convert the spec to JSON or `pip install pyyaml`") from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return RuleSpec(raw=data)


def dump_spec(spec: RuleSpec, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec.raw, f, ensure_ascii=False, indent=2)
