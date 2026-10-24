#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""边界守卫自证：故意把好案例改成错的，确认每种错都会被拦下。

移植到别的机器/别的 agent 之后，第一件事跑这个——它证明拦截真的在工作，
而不是"看起来在工作"。

用法:
  python selftest.py [--case examples/01-.../case.json]
退出码: 0 = 全部按预期拦截；1 = 有漏拦或误报
"""
from __future__ import annotations

import argparse
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caselib as C  # noqa: E402

DEFAULT_CASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "examples", "01-纯碱-浮法玻璃-报价跟进", "case.json")


def codes(case):
    return {p[1] for p in C.guard(case)}


def expect(case, code, name):
    """改坏一处，断言指定代码出现。"""
    got = codes(case)
    if code in got:
        print("  ✓ %-46s → %s" % (name, code))
        return True
    print("  ✗ %-46s → 未拦截（期望 %s，实际 %s）" % (name, code, sorted(got) or "无"))
    return False


def mutate(base, fn):
    c = copy.deepcopy(base)
    fn(c)
    C.normalize(c)
    return c


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default=DEFAULT_CASE)
    args = ap.parse_args(argv)

    if not os.path.exists(args.case):
        print("找不到基准案例：%s" % args.case)
        return 1
    base = C.load_case(args.case)

    ok = True
    print("[0] 基准案例必须是干净的")
    got = codes(base)
    if got:
        print("  ✗ 基准案例本身有告警/错误：%s" % sorted(got))
        ok = False
    else:
        print("  ✓ 0 ERROR / 0 WARN")

    def add_para(key, text):
        def f(c):
            c["versions"][key]["para"] = list(c["versions"][key]["para"]) + [text]
        return f

    print("[1] 新增未经提供的数字")
    ok &= expect(mutate(base, add_para("A", "单价【删掉】2600 元/吨，量大从优。")),
                 "UNSOURCED_NUMBER", "价格数字 2600 元/吨")

    print("[2] 越权让价")
    ok &= expect(mutate(base, add_para("B", "价格可以再谈，您开口就行。")),
                 "BANNED_PROMISE", "“价格可以再谈”")

    print("[3] 无限承诺")
    ok &= expect(mutate(base, add_para("D", "您有什么要求都可以提，我们一定配合。")),
                 "BANNED_PROMISE", "“一定配合”")

    print("[4] 无据稀缺话术")
    ok &= expect(mutate(base, add_para("A", "另外最近货源紧张，最好这周就定。")),
                 "FAKE_SCARCITY", "“货源紧张尽快定”")

    print("[5] 命中本品类禁语")
    ok &= expect(mutate(base, add_para("A", "我们的货绝对不结块，放一整年都没事。")),
                 "BANNED_PHRASE", "product_profile.ban_phrases")

    print("[6] 占位符未登记")
    def no_reg(c):
        # 基准案例正文共 4 处【待填】、清单 10 条；加到 12 处即超出登记
        c["versions"]["B"]["para"] = list(c["versions"]["B"]["para"]) + [
            "【待填】金额、【待填】日期、【待填】账号、【待填】单号、【待填】批次、"
            "【待填】口径、【待填】期限、【待填】联系人"]
    ok &= expect(mutate(base, no_reg), "PLACEHOLDER_MISMATCH", "正文【待填】多于清单条目")

    print("[7] 占位符没有确认人")
    def no_owner(c):
        c["placeholders"][0]["owner"] = "  "
    ok &= expect(mutate(base, no_owner), "PLACEHOLDER_NO_OWNER", "缺 owner 的占位符")

    print("[8] 事实漏进审计")
    def drop_audit(c):
        c["audit"].pop()
    ok &= expect(mutate(base, drop_audit), "AUDIT_INCOMPLETE", "删掉一行审计")

    print("[9] 审计格留空")
    def blank_symbol(c):
        c["audit"][0]["v"]["C"] = ""
    ok &= expect(mutate(base, blank_symbol), "AUDIT_SYMBOL_MISSING", "某格判定为空")

    print("[10] 新增项计数不为 0")
    def nonzero(c):
        for it in c["audit_summary"]:
            if "价格" in it["k"]:
                it["v"] = "1"
    ok &= expect(mutate(base, nonzero), "BOUNDARY_NOT_ZERO", "“新增价格”写成 1")

    print("[11] 邮件版没有主题行")
    def no_subject(c):
        c["email"]["subject"] = ""
    ok &= expect(mutate(base, no_subject), "EMAIL_NO_SUBJECT", "email.subject 为空")

    print("[12] 版本不全")
    def drop_version(c):
        c["versions"].pop("D", None)
    ok &= expect(mutate(base, drop_version), "VERSION_INCOMPLETE", "删掉 D 版")

    print("[13] 缺必需字段")
    def drop_field(c):
        c.pop("scenarios", None)
    ok &= expect(mutate(base, drop_field), "SCHEMA_MISSING", "删掉 scenarios")

    print("-" * 66)
    print("自证结果：%s" % ("全部按预期拦截" if ok else "存在漏拦或误报，先修守卫再交付"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
