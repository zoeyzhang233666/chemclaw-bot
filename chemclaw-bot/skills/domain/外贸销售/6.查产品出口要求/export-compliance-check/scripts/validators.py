# -*- coding: utf-8 -*-
"""validators.py — export-compliance-check 数据校验器

职责
----
1. 校验 case.json 结构完整（必填字段、id 唯一、状态取值合法）。
2. 法规时效性检查：每条判定必须挂法规来源；来源须有生效日期与核验日期；
   核验日期距交付日超过 STALE_DAYS 天则标记「需复核」。
3. 不确定性规则：
   - 状态为「已核实」的条目必须有 evidence 链接（或明确的本地依据说明）；
   - 状态为「待确认」「参考信息」的条目不得同时给出确定性结论措辞；
   - 任何「待确认」项必须出现在 open_questions 中（或显式声明无需跟进）。
4. 危险化学品监管 与 危险货物运输 两类判定不得混写：检查主题分布，
   并禁止在运输条目里出现「危险化学品目录」作为危险货物分类依据等混同措辞。
5. 输出 checks.json 供 selfcheck / 出报告使用。

用法
----
python validators.py <case.json> --out checks.json --as-of 2026-10-19
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

STALE_DAYS = 180

STATUS_ALLOWED = {
    "已核实", "待确认", "参考信息", "不适用", "排除理由已记录",
    "需确认（用途声明）", "需确认（以 COA 口径为准）", "待取得", "不触发",
}
# 允许的自由文本状态：凡以这些前缀开头也视为合法
STATUS_PREFIX_OK = ("已核实", "待确认", "参考信息", "不适用", "不触发", "待取得", "需确认", "排除")

TOPICS_REQUIRED = ("中国出口", "目的国进口", "运输", "标签与包装")

# 「危险化学品监管」与「危险货物运输」混同的典型错误措辞
CONFUSION_PATTERNS = [
    (r"危险货物.*依据《?危险化学品目录", "以危化品目录作为危险货物分类依据（混同）"),
    (r"危险化学品目录.*决定.*(UN|包装类别|PG)", "以危化品目录直接推导 UN 号/包装类别（混同）"),
    (r"UN\s?\d{4}.*属于危险化学品", "以 UN 号反推危化品属性（混同）"),
]

# 「待确认」条目中不得出现的确定性结论措辞
CERTAINTY_PATTERNS = [
    r"必然适用", r"确定需要", r"一定需要", r"肯定是", r"必然是",
]


class Checker:
    def __init__(self, case: dict, as_of: _dt.date):
        self.c = case
        self.as_of = as_of
        self.errors: list[str] = []      # 阻断项
        self.warnings: list[str] = []    # 提示项
        self.items: list[dict] = []

    # ---------- 工具 ----------
    def _need(self, cond: bool, msg: str, level: str = "error") -> None:
        if cond:
            return
        (self.errors if level == "error" else self.warnings).append(msg)

    @staticmethod
    def _iter_entries(c: dict):
        for key in ("cn_export", "import_vn", "transport", "label_pkg"):
            for e in c.get(key, []):
                yield key, e

    def _parse_date(self, s: str):
        m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", s or "")
        if not m:
            m = re.search(r"(\d{4})[-/年](\d{1,2})", s or "")
            if not m:
                return None
            return _dt.date(int(m.group(1)), int(m.group(2)), 1)
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # ---------- 规则 ----------
    def run(self) -> "Checker":
        c = self.c
        meta = c.get("meta", {})
        for f in ("case_id", "title", "prepared_on"):
            self._need(bool(meta.get(f)), f"meta.{f} 缺失")
        if meta.get("prepared_on"):
            try:
                _dt.date.fromisoformat(meta["prepared_on"])
            except ValueError:
                self.errors.append("meta.prepared_on 不是 ISO 日期")

        # 1) 主题覆盖
        present = {e.get("topic") for _, e in self._iter_entries(c)}
        for t in TOPICS_REQUIRED:
            self._need(t in present, f"缺少主题：{t}")

        # 2) 输入要素
        prod = c.get("inputs", {}).get("product", {})
        for f in ("cas", "concentration", "use", "packaging", "destination", "transport_mode"):
            self._need(bool(prod.get(f)), f"inputs.product.{f} 缺失")

        # 3) HS 候选
        hs = c.get("hs_candidates", [])
        self._need(len(hs) >= 1, "至少需要 1 个 HS 候选")
        for h in hs:
            self._need(bool(h.get("basis")), f"HS 候选 {h.get('code_cn')} 缺少归类依据")
            self._need(bool(h.get("status")), f"HS 候选 {h.get('code_cn')} 缺少状态")

        # 4) 逐条检查
        regs = {r["id"]: r for r in c.get("regs", [])}
        oq_blocks = set()
        for q in c.get("open_questions", []):
            oq_blocks.update(q.get("blocks", []))

        ids = set()
        for key, e in self._iter_entries(c):
            eid = e.get("id", "")
            self._need(bool(eid), f"{key} 中存在无 id 条目")
            self._need(eid not in ids, f"id 重复：{eid}")
            ids.add(eid)

            status = e.get("status", "")
            ok_status = any(status == s or status.startswith(p) for s in STATUS_ALLOWED for p in ("",)) or \
                        status.startswith(STATUS_PREFIX_OK)
            self._need(ok_status, f"{eid} 状态取值不在允许集合：{status!r}")

            # 法规来源
            self._need(bool(e.get("reg")), f"{eid} 缺少法规依据（reg）")
            self._need(bool(e.get("effective")), f"{eid} 缺少生效/适用时间（effective）")
            self._need(bool(e.get("finding")), f"{eid} 缺少结论（finding）")
            self._need(bool(e.get("action")), f"{eid} 缺少行动项（action）")

            # 已核实须有证据
            if status.startswith("已核实"):
                self._need(bool(e.get("evidence")), f"{eid} 标注「已核实」但无 evidence 链接")

            # 待确认须进入 open_questions
            if status.startswith(("待确认", "需确认", "参考信息")):
                linked = eid in oq_blocks
                self._need(linked, f"{eid} 为不确定状态但未在 open_questions.blocks 中列出")
                txt = " ".join(str(e.get(k, "")) for k in ("finding", "item"))
                for pat in CERTAINTY_PATTERNS:
                    self._need(not re.search(pat, txt), f"{eid} 为不确定状态却使用确定性措辞：{pat}")

            # 混同检查
            blob = " ".join(str(e.get(k, "")) for k in ("item", "finding", "reg", "action"))
            for pat, why in CONFUSION_PATTERNS:
                self._need(not re.search(pat, blob), f"{eid} {why}")

            self.items.append({
                "id": eid, "topic": e.get("topic"), "section": key,
                "status": status, "reg": e.get("reg", "")[:120],
                "effective": e.get("effective", ""),
            })

        # 5) 法规时效性
        for r in c.get("regs", []):
            rid = r.get("id")
            for f in ("jurisdiction", "name", "ref", "effective", "status", "url", "verified_on"):
                self._need(bool(r.get(f)), f"regs.{rid}.{f} 缺失")
            url = r.get("url", "")
            if url and not re.match(r"^https?://", url):
                self.errors.append(f"regs.{rid}.url 不是有效 URL：{url}")
            vd = self._parse_date(r.get("verified_on", ""))
            if vd:
                age = (self.as_of - vd).days
                if age > STALE_DAYS:
                    self.warnings.append(f"regs.{rid} 核验日 {vd} 距今 {age} 天，超过 {STALE_DAYS} 天，需复核")
                elif age < -1:
                    self.errors.append(f"regs.{rid} 核验日晚于交付日")
            eff = self._parse_date(r.get("effective", ""))
            if eff and eff > self.as_of:
                self.warnings.append(f"regs.{rid} 生效日 {eff} 晚于交付日 {self.as_of}，须标注过渡安排")

        # 每条判定须显式挂接法规 ID（reg_ids），且 ID 必须存在于 regs 表
        for key, e in self._iter_entries(c):
            eid = e.get("id")
            ids_ref = e.get("reg_ids") or []
            has_inline_url = bool(e.get("evidence"))
            if not ids_ref and not has_inline_url:
                self.errors.append(f"{eid} 既无 reg_ids 也无 evidence，无法追溯法规来源")
                continue
            for rid in ids_ref:
                self._need(rid in regs, f"{eid} 引用了不存在的法规 ID：{rid}")
            if e.get("evidence") and not re.match(r"^https?://", e["evidence"]):
                self.errors.append(f"{eid}.evidence 不是有效 URL：{e['evidence']}")

        # 反向：法规 relevance 中列出、但条目未挂接的，提示
        for r in regs.values():
            for eid in re.findall(r"(?:CN|VN|TR|LB)-\d{2}", r.get("relevance", "")):
                for key, e in self._iter_entries(c):
                    if e.get("id") == eid and r["id"] not in (e.get("reg_ids") or []):
                        self.warnings.append(f"法规 {r['id']} 声明覆盖 {eid}，但 {eid} 未挂接 reg_ids")

        # 6) 单证与角色
        for d in c.get("documents", []):
            for f in ("id", "category", "name", "owner", "status"):
                self._need(bool(d.get(f)), f"documents.{d.get('id')}.{f} 缺失")
        self._need(len(c.get("roles", [])) >= 3, "角色少于 3 个（应覆盖出口方/进口方/承运方）")
        role_names = " ".join(r.get("role", "") for r in c.get("roles", []))
        for r in ("出口方", "进口方", "承运"):
            self._need(r in role_names, f"角色未覆盖：{r}")

        # 7) 时效性检查表
        for t in c.get("timeliness", []):
            self._need(bool(t.get("checked")), f"时效性条目未核实：{t.get('item')}")

        return self

    # ---------- 结果 ----------
    def summary(self) -> dict:
        by_topic: dict[str, dict] = {}
        for it in self.items:
            d = by_topic.setdefault(it["topic"] or "未分类", {"total": 0, "已核实": 0, "待确认": 0, "参考": 0})
            d["total"] += 1
            if it["status"].startswith("已核实"):
                d["已核实"] += 1
            elif it["status"].startswith("待确认") or it["status"].startswith("需确认"):
                d["待确认"] += 1
            else:
                d["参考"] += 1
        return {
            "case_id": self.c.get("meta", {}).get("case_id"),
            "as_of": self.as_of.isoformat(),
            "entries": len(self.items),
            "by_topic": by_topic,
            "open_questions": len(self.c.get("open_questions", [])),
            "regs": len(self.c.get("regs", [])),
            "errors": self.errors,
            "warnings": self.warnings,
            "ok": not self.errors,
        }


def run(case_path: str, out_path: str | None = None, as_of: str | None = None) -> dict:
    case = json.loads(Path(case_path).read_text(encoding="utf-8"))
    d = _dt.date.fromisoformat(as_of) if as_of else _dt.date.fromisoformat(case["meta"]["prepared_on"])
    chk = Checker(case, d).run()
    s = chk.summary()
    s["items"] = chk.items
    if out_path:
        Path(out_path).write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="校验出口合规 case.json")
    ap.add_argument("case")
    ap.add_argument("--out", default=None)
    ap.add_argument("--as-of", default=None, help="核验基准日 YYYY-MM-DD")
    a = ap.parse_args(argv)

    s = run(a.case, a.out, a.as_of)
    print(f"[{s['case_id']}] 条目 {s['entries']}，法规 {s['regs']}，待确认 {s['open_questions']}")
    for t, d in s["by_topic"].items():
        print(f"  - {t}: 共 {d['total']} | 已核实 {d['已核实']} | 待确认 {d['待确认']} | 参考 {d['参考']}")
    for e in s["errors"]:
        print("  ERROR  ", e)
    for w in s["warnings"]:
        print("  WARN   ", w)
    print("结果：", "通过" if s["ok"] else "未通过")
    return 0 if s["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
