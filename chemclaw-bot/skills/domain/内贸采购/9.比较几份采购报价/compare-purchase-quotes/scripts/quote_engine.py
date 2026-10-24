#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quote_engine.py —— 采购报价「到厂成本」计算引擎（零依赖，纯标准库）

用法：
    from quote_engine import QuoteEngine
    eng = QuoteEngine(quotes, assumptions)
    result = eng.compute_all()          # -> {code: {...}}
    eng.sensitivity()                   # 参数敏感性
    eng.scenarios([...])                # 情景
    eng.price_sweep(4800, 6800, 21)     # 市场压力

输入结构（L1+L2 合并字典，见 references/field-mapping.md）：
    {
      "code": "A",
      "price_raw": 6.20, "unit_raw": "元/公斤",   # 或 "元/吨" / "元/桶"
      "barrel_kg": 220,                            # 桶/袋净重（元/桶时必须）
      "tax_included": True, "tax_rate": 0.13, "invoice": "special",  # special / normal / unknown
      "purity": 0.9992,
      "spec_ok": True,
      "tiers": [[22, 6.20], [110, 6.17]],
      "pack_cost_single": 0.0,
      "freight_by": "buyer",          # buyer / seller
      "freight_key": "hz_zhangjiagang",
      "capital_days": 21.0,
      "deposit": None,                # 或 {"amount": 300000, "days": 180}
      "pack_deposit_per_unit": None,  # 或 {"amount": 30, "unit_kg": 220}
      "vehicle_cleanup": False        # 散装自提是否发生槽车清洗
    }
"""
from __future__ import annotations
import copy


class QuoteEngine:
    DEFAULT_ASSUMPTIONS = {
        "qty_ton": 200.0,
        "fund_rate": 0.045,
        "year_days": 360.0,
        "freight": {                     # 元/吨（含税），税率 9%
            "hz_zhangjiagang": 42.0,
            "default": 42.0,
        },
        "freight_tax": 0.09,
        "unload_fee_per_ton": 25.0,     # 含税
        "service_tax": 0.06,
        "inspection_per_batch": 1800.0,
        "inspection_batches_year": 6.0,
        "annual_volume_ton": 2400.0,
        "vehicle_prep_per_trip": 600.0,
        "vehicle_prep_trips_year": 8.0,
        "deposit_days_default": 180.0,
        "pack_deposit_refund_days": 10.0,
        "pack_deposit_unreturned": 0.10,
        "assume_unknown_as_special": False,
        "accept_below_spec": False,
        "max_iter": 40,
        "tol": 1e-9,
    }

    def __init__(self, quotes, assumptions=None):
        self.assumptions = copy.deepcopy(self.DEFAULT_ASSUMPTIONS)
        if assumptions:
            for k, v in assumptions.items():
                if k == "freight" and isinstance(v, dict):
                    self.assumptions["freight"].update(v)
                else:
                    self.assumptions[k] = v
        self.quotes = {q["code"]: q for q in quotes}

    # ---------------- 单价：单位换算 + 数量阶梯 + 税费分离 ----------------
    def goods_price(self, q):
        a = self.assumptions
        price = q["price_raw"]
        if q.get("tiers"):
            price = q["price_raw"]
            for lo, p in sorted(q["tiers"], key=lambda x: x[0]):
                if a["qty_ton"] >= lo:
                    price = p
        unit = q["unit_raw"]
        if "公斤" in unit or "kg" in unit.lower():
            per_ton = price * 1000
        elif "桶" in unit or "袋" in unit or "包" in unit:
            kg = q.get("barrel_kg")
            if not kg:
                raise ValueError(f"[{q['code']}] 以「{unit}」计价但缺少净重 barrel_kg —— 必须列为待确认")
            per_ton = price / (kg / 1000.0)
        elif "升" in unit or unit.lower().endswith("l"):
            dens = q.get("density_t_per_l")
            if not dens:
                raise ValueError(f"[{q['code']}] 以「{unit}」计价但缺少密度")
            per_ton = price / dens
        else:
            per_ton = price
        inv = q.get("invoice", "unknown")
        rate = q.get("tax_rate")
        if q.get("tax_included", True):
            if inv == "special" and rate:
                cost = per_ton / (1 + rate)
            elif inv == "normal":
                cost = per_ton
            elif inv == "unknown":
                cost = per_ton / (1 + rate) if (rate and a["assume_unknown_as_special"]) else per_ton
            else:
                cost = per_ton
        else:
            cost = per_ton
        return {"per_ton_incl": per_ton, "cost_basis": cost, "hit_price": price}

    # ---------------- 单家到厂成本 ----------------
    def compute(self, code):
        a = self.assumptions
        q = self.quotes[code]
        g = self.goods_price(q)

        pack = float(q.get("pack_cost_single") or 0.0)

        if q.get("freight_by") == "seller":
            freight_base, freight_paid = 0.0, 0.0
        else:
            freight_paid = float(a["freight"].get(q.get("freight_key"), a["freight"]["default"]))
            freight_base = freight_paid / (1 + a["freight_tax"])

        unload = a["unload_fee_per_ton"] / (1 + a["service_tax"])
        inspect = a["inspection_per_batch"] * a["inspection_batches_year"] / a["annual_volume_ton"] / (1 + a["service_tax"])
        vehicle = 0.0
        if q.get("vehicle_cleanup"):
            vehicle = a["vehicle_prep_per_trip"] * a["vehicle_prep_trips_year"] / a["annual_volume_ton"] / (1 + a["service_tax"])

        base = g["cost_basis"] + pack + freight_base + unload + inspect + vehicle
        r = a["fund_rate"] / a["year_days"]
        d = float(q.get("capital_days") or 0.0)
        cap = 0.0
        iters = 0
        for _ in range(a["max_iter"]):
            iters += 1
            nx = (base + cap) * r * d
            if abs(nx - cap) < a["tol"]:
                cap = nx
                break
            cap = nx

        deposit = 0.0
        dep = q.get("deposit")
        if dep and dep.get("amount"):
            days = float(dep.get("days") or a["deposit_days_default"])
            deposit += dep["amount"] * a["fund_rate"] * days / 360.0 / a["qty_ton"]
        pd = q.get("pack_deposit_per_unit")
        if pd and pd.get("amount"):
            units = a["qty_ton"] / (pd.get("unit_kg", 220) / 1000.0)
            total = units * pd["amount"]
            un = a["pack_deposit_unreturned"]
            deposit += total * (un * 1.0 + (1 - un) * a["fund_rate"] * a["pack_deposit_refund_days"] / 360.0) / a["qty_ton"]

        landed = base + cap + deposit
        purity = float(q.get("purity") or 1.0)
        return {
            "code": code, "hit_price": g["hit_price"], "price_incl": g["per_ton_incl"],
            "goods": g["cost_basis"], "purity": purity, "goods_purity": g["cost_basis"] / purity,
            "pack": pack, "freight_base": freight_base, "freight_paid": freight_paid,
            "unload": unload, "inspect": inspect, "vehicle": vehicle,
            "capital": cap, "iters": iters, "base": base,
            "deposit": deposit, "landed": landed, "landed_purity": landed / purity,
            "spec_ok": bool(q.get("spec_ok", True)),
        }

    def compute_all(self):
        out = {c: self.compute(c) for c in self.quotes}
        a = self.assumptions
        elig = [c for c, r in out.items() if r["spec_ok"] or a["accept_below_spec"]]
        ranked = sorted(elig, key=lambda c: out[c]["landed"])
        for i, c in enumerate(ranked, 1):
            out[c]["rank"] = i
            out[c]["gap"] = out[c]["landed"] - out[ranked[0]]["landed"]
        for c in out:
            out[c].setdefault("rank", None)
            out[c].setdefault("gap", None)
        return out

    # ---------------- 敏感性：单参数扰动 ----------------
    def sensitivity(self, param, values):
        keys = {
            "freight": lambda a, v: a["freight"].update({k: v for k in a["freight"]}),
            "fund_rate": lambda a, v: a.__setitem__("fund_rate", v),
            "unload": lambda a, v: a.__setitem__("unload_fee_per_ton", v),
            "qty": lambda a, v: a.__setitem__("qty_ton", v),
            "trips": lambda a, v: a.__setitem__("vehicle_prep_trips_year", v),
        }
        base = self.compute_all()
        rows = []
        for v in values:
            saved = copy.deepcopy(self.assumptions)
            keys[param](self.assumptions, v)
            r = self.compute_all()
            rows.append({"value": v, "landed": {c: r[c]["landed"] for c in r},
                         "delta": {c: r[c]["landed"] - base[c]["landed"] for c in r},
                         "best": min((c for c in r if r[c]["rank"]), key=lambda c: r[c]["landed"], default=None)})
            self.assumptions = saved
        return rows

    # ---------------- 情景分析 ----------------
    def scenarios(self, patches):
        """patches: [{"name":..., "assumptions": {...}, "note":...}]"""
        out = []
        for p in patches:
            saved = copy.deepcopy(self.assumptions)
            for k, v in (p.get("assumptions") or {}).items():
                if k == "freight" and isinstance(v, dict):
                    self.assumptions["freight"].update(v)
                else:
                    self.assumptions[k] = v
            r = self.compute_all()
            out.append({"name": p["name"], "note": p.get("note", ""),
                        "rows": {c: {"landed": r[c]["landed"], "rank": r[c]["rank"]} for c in r}})
            self.assumptions = saved
        return out

    # ---------------- 市场压力测试 ----------------
    def price_sweep(self, lo, hi, n=21, target="A"):
        """市场压力：把「target 家」的裸价设为市场价 p，其他各家保持与 target 的相对价差，
        重新计算到厂成本曲线 —— 用于看「若市场价处于 X，各家到厂成本是多少、排名是否翻转」。

        说明：绝对价格水平由市场决定；供应商之间的相对价差（品牌、规格、服务）由报价体现。
        因此把相对价差按「裸价比」保持不变是最贴近现实的假设。
        """
        base = self.compute_all()
        ref = base[target]["goods"]
        rows = []
        for i in range(n):
            p = lo + (hi - lo) * i / (n - 1)
            k = p / ref
            row = {"price": round(p, 2)}
            for c, b in base.items():
                # 裸价按 k 缩放；不折纯口径直接加差；折纯口径按含量放大
                goods_delta = b["goods"] * (k - 1.0)
                rate = self.assumptions["fund_rate"] / self.assumptions["year_days"]
                d = float(self.quotes[c].get("capital_days") or 0.0)
                cap_delta = goods_delta * rate * d
                row[c] = round(b["landed"] + goods_delta + cap_delta, 2)
            rows.append(row)
        return rows

    # ---------------- 盈亏平衡 ----------------
    def breakeven_qty(self, c1, c2, lo=20.0, hi=400.0, step=0.5):
        """求两家到厂成本相等的采购量（用于数量阶梯切换点）"""
        import math
        best = None
        q = lo
        prev = None
        while q <= hi:
            saved = copy.deepcopy(self.assumptions)
            self.assumptions["qty_ton"] = q
            r = self.compute_all()
            diff = r[c1]["landed"] - r[c2]["landed"]
            if prev is not None and prev[1] * diff <= 0:
                best = round(q - step / 2, 1)
                break
            prev = (q, diff)
            self.assumptions = saved
            q += step
        return best


if __name__ == "__main__":
    # 自检：用三份示例报价跑一遍
    quotes = [
        {"code": "A", "price_raw": 6.20, "unit_raw": "元/公斤", "tiers": [[22, 6.20], [110, 6.17]],
         "tax_included": True, "tax_rate": 0.13, "invoice": "special", "purity": 0.9992,
         "freight_by": "buyer", "freight_key": "hz_zhangjiagang", "capital_days": 21.0},
        {"code": "B", "price_raw": 4850.0, "unit_raw": "元/吨", "tiers": [[30, 4850.0], [120, 4800.0]],
         "tax_included": False, "tax_rate": 0.13, "invoice": "special", "purity": 0.9990,
         "freight_by": "buyer", "freight_key": "hz_zhangjiagang", "capital_days": 46.0,
         "deposit": {"amount": 300000, "days": 180}, "vehicle_cleanup": True},
        {"code": "C", "price_raw": 6300.0, "unit_raw": "元/桶", "barrel_kg": 220,
         "tax_included": True, "invoice": "unknown", "purity": 0.995, "spec_ok": False,
         "freight_by": "seller", "capital_days": 0.0,
         "pack_deposit_per_unit": {"amount": 30, "unit_kg": 220}},
    ]
    eng = QuoteEngine(quotes)
    res = eng.compute_all()
    for c, r in res.items():
        print(f"{c}: 到厂 {r['landed']:.2f}  折纯 {r['landed_purity']:.2f}  迭代 {r['iters']} 次  排名 {r['rank']}")
    print("敏感性(资金成本):", [(x['value'], round(x['landed']['B'], 2), x['best']) for x in eng.sensitivity("fund_rate", [0.0, 0.045, 0.10])])
    print("盈亏平衡量 A=B:", eng.breakeven_qty("A", "B"))
