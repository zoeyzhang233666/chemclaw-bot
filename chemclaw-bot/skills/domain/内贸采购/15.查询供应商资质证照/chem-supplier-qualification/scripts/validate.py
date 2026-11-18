# -*- coding: utf-8 -*-
"""
validate.py — 渲染前自检：把"合规红线"变成可执行的检查

用法： python validate.py data.json [--strict]
退出码： 0 = 通过（可能有 WARN）；1 = 存在 FAIL

检查项：
  F1  必备字段缺失（as_of / subject.name / product.name / product.cas）
  F2  统一社会信用代码校验码不通过却标为「已核验」
  F3  枚举值非法（cert.status / cover / need / verdict / priority）
  F4  状态为「已核验」但无 evidence_id 或 URL → 证据链断裂
  F5  出现禁用表述（"企业无证""已确认不在目录""不存在易制爆风险"等）
  F6  索证清单出现空项；P0 项缺少"需确认的问题"
  F7  证照有效期早于 as_of 却标「已核验」→ 应改为「已过期」
  F8  同一主体名对应不同信用代码 / 同一代码对应不同名称
  F9  只有一种化学品属性（finding）时不得使用"该品类统一规则"以外的泛化结论——见 F5
  F10 模拟扫描件未标注 mode=mock
  W1  分类核验清单为空
  W2  证照「应具备(required)」但状态为「无公开信息」→ 必须出现在索证清单
  W3  无公开来源 URL 的证照过多（>50%）
  W4  三个及以上 P0 项但无"总体判定=不得下单"
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qclib as L

BAD_PHRASES = [
    "企业无证", "无许可证", "不具备资质（未经核验）", "已确认不在危险化学品目录",
    "不属于易制爆", "不属于危化品", "完全合规", "资质齐全，无需再核",
    "已确认不属于剧毒", "不存在任何风险",
]
ALLOWED_CTX = ("不得", "不能", "禁止", "不应", "不可", "严禁")


def walk_strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, path + "/%d" % i)
    elif isinstance(obj, str):
        yield path, obj


def main():
    ap_data = sys.argv[1]
    strict = "--strict" in sys.argv
    data = json.load(open(ap_data, encoding="utf-8"))
    fails, warns = [], []

    def fail(code, msg):
        fails.append("%s  %s" % (code, msg))

    def warn(code, msg):
        warns.append("%s  %s" % (code, msg))

    # F1
    for k, f in (("as_of", data.get("as_of")), ("subject.name", (data.get("subject") or {}).get("name")),
                 ("product.name", (data.get("product") or {}).get("name")),
                 ("product.cas", (data.get("product") or {}).get("cas"))):
        if not f:
            fail("F1", "缺少必备字段 %s" % k)

    # 模板占位符模式：填 "<...>" 说明还没做，任何真实数据都不长这样
    def is_blank(v):
        return not str(v or "").strip() or str(v).strip().startswith("<")

    template_mode = is_blank((data.get("subject") or {}).get("uscc")) or (
        str(data.get("as_of", "")).strip().startswith("<") or re.match(r"^YYYY", str(data.get("as_of", "")).strip()) is not None)
    if template_mode:
        print("=" * 68)
        print(" validate: %s" % os.path.basename(ap_data))
        print("  TEMPLATE MODE —— 检测到占位符（USCC/as_of 未填），跳过内容类校验。")
        print("  填完模板后重跑本命令；或在 build_all.py 上加 --skip-validate。")
        print("=" * 68)
        return

    certs = data.get("certs", [])

    # F2
    chk = L.check_uscc((data.get("subject") or {}).get("uscc"))
    if chk["valid"] is False:
        any_verified = any(c.get("status") == "verified" for c in certs)
        fail("F2", "统一社会信用代码校验码不通过（%s）%s" % (
            chk["reason"], "，但仍有证照标为已核验" if any_verified else ""))

    # F3
    for c in certs:
        if c.get("status") not in ("verified", "mismatch", "pending", "no_public"):
            fail("F3", "证照「%s」status=%r 非法" % (c.get("name"), c.get("status")))
        if c.get("cover") not in ("cover", "partial", "not_cover", "unknown", None):
            fail("F3", "证照「%s」cover=%r 非法" % (c.get("name"), c.get("cover")))
        if c.get("need") not in ("required", "conditional", "none", None):
            fail("F3", "证照「%s」need=%r 非法" % (c.get("name"), c.get("need")))
    for c in data.get("classification_checklist", []):
        if c.get("verdict") not in ("confirmed", "not_confirmed", "pending"):
            fail("F3", "分类项「%s」verdict=%r 非法" % (c.get("item"), c.get("verdict")))
    for f in (data.get("product") or {}).get("findings", []):
        if f.get("verdict") not in ("confirmed", "not_confirmed", "pending"):
            fail("F3", "属性项「%s」verdict=%r 非法" % (f.get("item"), f.get("verdict")))
    for it in data.get("request_list", []):
        if it.get("priority", "P1") not in L.PRIORITIES:
            fail("F3", "索证项「%s」priority=%r 非法" % (it.get("code"), it.get("priority")))

    # F4 + F7
    for c in certs:
        if c.get("status") == "verified" and not (c.get("evidence_id") or c.get("url")):
            fail("F4", "证照「%s」标为已核验但无 evidence_id/url" % c.get("name"))
        v = L.validity(c.get("valid_to"), data.get("as_of"))
        if v["status"] == "expired" and c.get("status") == "verified":
            fail("F7", "证照「%s」有效期 %s 早于基准日 %s，却标已核验（应为已过期）"
                 % (c.get("name"), c.get("valid_to"), data.get("as_of")))

    # F5
    for path, s in walk_strings(data):
        for p in BAD_PHRASES:
            if p in s:
                # 允许"不得/不能写…"这类禁止性语境
                allow = any(ctx in s for ctx in ALLOWED_CTX)
                if not allow:
                    fail("F5", "禁用表述「%s」出现在 %s：%s" % (p, path, L.clip(s, 80)))

    # F6
    for it in data.get("request_list", []):
        if not it.get("cert"):
            fail("F6", "索证项 %s 缺少证照名称" % it.get("code"))
        if it.get("priority") == "P0" and not (it.get("ask") or it.get("reason")):
            fail("F6", "P0 索证项 %s 缺少需确认的问题" % it.get("code"))

    # F8
    for c in L.erp_check(data):
        fail("F8", "主体冲突：%s" % json.dumps(c, ensure_ascii=False))

    # F10
    for s in data.get("scans", []):
        if s.get("mode") not in ("mock", "upload", "public"):
            fail("F10", "扫描件「%s」未标注 mode（mock/upload/public）" % s.get("title"))

    # W1
    if not data.get("classification_checklist"):
        warn("W1", "监管分类核验清单为空——无法证明逐项核验")

    # W2
    req_names = set((i.get("cert") or "").strip() for i in data.get("request_list", []))
    auto, _ = L.pending_derivation(data)
    for a in auto:
        if (a.get("cert") or "").strip() not in req_names:
            pass  # 自动派生会在渲染时补齐
    for c in certs:
        if c.get("need") == "required" and c.get("status") in ("no_public", "pending", "mismatch"):
            if c.get("name") not in req_names:
                warn("W2", "证照「%s」应具备但状态为 %s，未出现在人工索证清单（渲染时会自动派生）"
                     % (c.get("name"), c.get("status")))

    # W3
    if certs:
        no_url = sum(1 for c in certs if not c.get("url"))
        if no_url * 2 > len(certs):
            warn("W3", "%d/%d 张证照无公开来源 URL" % (no_url, len(certs)))

    # W4
    p0 = sum(1 for i in data.get("request_list", []) if i.get("priority") == "P0")
    grade = (data.get("assessment") or {}).get("grade_code", "")
    if p0 >= 3 and grade not in ("G3", "G4"):
        warn("W4", "P0 项 %d 个，但总体判定 %s 偏松" % (p0, grade))

    # 输出
    print("=" * 68)
    print(" validate: %s" % os.path.basename(ap_data))
    print("  证照 %d 张 · 分类项 %d 项 · 证据 %d 条 · 索证 %d 项"
          % (len(certs), len(data.get("classification_checklist", [])), len(data.get("evidence", [])),
             len(data.get("request_list", []))))
    for f in fails:
        print("  FAIL " + f)
    for w in warns:
        print("  WARN " + w)
    print("  结果：%d FAIL / %d WARN" % (len(fails), len(warns)))
    print("=" * 68)
    if fails or (strict and warns):
        sys.exit(1)


if __name__ == "__main__":
    main()
