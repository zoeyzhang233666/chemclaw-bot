# -*- coding: utf-8 -*-
"""
render_html.py — data.json -> 单文件交互式资质核验页（HTML）

用法： python render_html.py data.json --out ./out --assets ../assets
输出： <out>/资质证照核验_<主体简称>_<产品简称>.html
说明： 所有 CSS/JS/数据均内联；扫描件以相对路径引用（与 html 放在同一输出目录）；
       示例扫描件本身是 SVG 文件，可直接嵌入，无需网络与图片库。
"""

import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qclib as L

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


# --------------------------------------------------------------- 小工具

def pill(label, tone):
    return '<span class="pill c-%s"><i class="dot"></i>%s</span>' % (tone, L.esc(label))


def tbl(head, rows, cls="t", widths=None, table_id=None):
    h = ["<div class='tw'><table class='%s'%s><thead><tr>" % (cls, (" id='%s'" % table_id) if table_id else "")]
    for i, c in enumerate(head):
        w = (" style='width:%s'" % widths[i]) if widths and widths[i] else ""
        h.append("<th%s>%s</th>" % (w, c))
    h.append("</tr></thead><tbody>")
    for r in rows:
        if r is None:
            h.append("</tbody><tbody>")
            continue
        if isinstance(r, dict) and r.get("_group"):
            h.append("<tr><td colspan='%d' style='background:#efe9da;font-weight:600'>%s</td></tr>"
                     % (len(head), r["_group"]))
            continue
        cells = r if isinstance(r, (list, tuple)) else [r]
        h.append("<tr>")
        for c in cells:
            if isinstance(c, dict):
                h.append("<td class='%s'>%s</td>" % (c.get("c", ""), c.get("h", "")))
            else:
                h.append("<td>%s</td>" % c)
        h.append("</tr>")
    h.append("</tbody></table></div>")
    return "".join(h)


def sec(no, sid, title, sub, body, badge=""):
    return ("<section class='sec' id='%s'><header><span class='no'>%s</span><div><h2>%s</h2>"
            "<div class='sub'>%s</div></div>%s</header>%s</section>"
            % (sid, no, title, sub, ("<div style='margin-left:auto'>%s</div>" % badge) if badge else "", body))


# --------------------------------------------------------------- 数据预处理

def prepare(data):
    as_of = data.get("as_of")
    for i, c in enumerate(data.get("certs", [])):
        c.setdefault("id", "C%02d" % (i + 1))
        st = L.cert_effective_state(c, as_of)
        c["state"] = st
        c["state_label"] = L.state_meta(st)["label"]
        v = L.validity(c.get("valid_to"), as_of)
        c["expiry_status"] = v["status"]
        c["expiry_label"] = v["label"]
        cv = c.get("cover") or "unknown"
        c["cover_label"] = L.cover_meta(cv)["label"]
        c["cover_key"] = cv
        c["need_label"] = "应具备" if c.get("need") == "required" else ("备选/按需" if c.get("need") == "conditional" else "不适用")
    return data


def cert_search_blob(c):
    return " ".join([str(c.get(k) or "") for k in ("name", "no", "issuer", "scope", "type", "field_source")]).lower()


# --------------------------------------------------------------- 各章节

def render_hero(data):
    s = data.get("subject", {})
    p = data.get("product", {})
    ap = data.get("assessment", {})
    m = data.get("meta", {})
    chips = []
    chips.append("<span class='chip'>供应商 <b>%s</b></span>" % L.esc(s.get("name")))
    if s.get("uscc"):
        chk = L.check_uscc(s["uscc"])
        tone = "ok" if chk["valid"] else "bad"
        chips.append("<span class='chip'>信用代码 <b class='mono'>%s</b> %s</span>"
                     % (L.esc(s["uscc"]), "✓校验通过" if chk["valid"] else "✗校验失败"))
    if p.get("name"):
        chips.append("<span class='chip'>采购品 <b>%s</b>%s</span>"
                     % (L.esc(p.get("name")), (" · " + L.esc(p.get("spec"))) if p.get("spec") else ""))
    if p.get("cas"):
        chips.append("<span class='chip'>CAS <b class='mono'>%s</b></span>" % L.esc(p["cas"]))
    if ap.get("grade"):
        chips.append("<span class='chip'>总体判定 <b>%s</b></span>" % L.esc(ap.get("grade")))
    chips.append("<span class='chip'>核验基准日 <b>%s</b></span>" % L.esc(as_of_disp(data)))
    if m.get("prepared_by"):
        chips.append("<span class='chip'>%s · %s</span>" % (L.esc(m.get("prepared_by")), L.esc(m.get("prepared_at", ""))))

    lead = ap.get("one_liner", "")
    return """
<div class="hero">
  <div class="eyebrow">试剂级合规档案 · 内贸采购前资质核验</div>
  <h1>%s</h1>
  <div class="sub">%s</div>
  <div class="chips">%s</div>
  <div class="seal"><div class="k">RECORD</div><div class="v">%s</div><div class="l">%s</div></div>
</div>""" % (
        L.esc(data.get("title") or "供应商资质证照核验"),
        L.esc(lead),
        "".join(chips),
        L.esc(ap.get("grade_code") or ap.get("grade") or "—"),
        L.esc(m.get("record_id") or ""),
    )


def as_of_disp(data):
    return data.get("as_of") or "未设定"


def render_kpis(data):
    certs = data.get("certs", [])
    s = L.summarize(certs, data.get("as_of"))
    cls = data.get("classification_checklist", [])
    conf = sum(1 for c in cls if c.get("verdict") == "confirmed")
    gaps = sum(1 for c in cls if c.get("verdict") in ("not_confirmed", "pending"))
    req = sum(1 for c in certs if c.get("need") == "required")
    items = [
        ("监管类别确认", "%d/%d" % (conf, len(cls)), "已确认类别数 / 待核验清单项数", "ok" if not gaps else "warn"),
        ("应具备证照 P0/P1", str(req), "由监管要求派生，见第 4、5 节", ""),
        ("已核验", str(s.get("verified", 0)), "有公开披露或官方来源直接支撑", "ok"),
        ("信息不一致", str(s.get("mismatch", 0)), "字段冲突 / 过期 / 主体不符", "bad" if s.get("mismatch") else ""),
        ("待核验", str(s.get("pending", 0)), "需原件与主管部门公示确认", "warn" if s.get("pending") else ""),
        ("无公开信息", str(s.get("no_public", 0)), "查不到 ≠ 无证，须进索证清单", "warn" if s.get("no_public") else ""),
        ("180 天内到期", str(s.get("expiring", 0)), "到期即失效力，须提前换证", "warn" if s.get("expiring") else ""),
        ("必须索取原件", str(len(data.get("request_list", []))), "第 8 节·索证清单", ""),
    ]
    return "<div class='kpis'>" + "".join(
        "<div class='kpi %s'><div class='l'>%s</div><div class='v'>%s</div><div class='n'>%s</div></div>"
        % (("bad" if c == "bad" else "ok" if c == "ok" else "warn" if c in ("warn",) else ""), L.esc(t), L.esc(v), L.esc(n))
        for t, v, n, c in items) + "</div>"


def render_identity(data):
    s = data.get("subject", {})
    rows = []
    chk = L.check_uscc(s.get("uscc"))
    uscc_tone = "ok" if chk["valid"] else ("bad" if chk["valid"] is False else "gray")
    rows.append({"k": "企业全称", "v": "<b>%s</b>" % L.esc(s.get("name"))})
    if s.get("aliases"):
        rows.append({"k": "曾用名/简称", "v": L.esc("、".join(s["aliases"]))})
    rows.append({"k": "统一社会信用代码", "v": "<span class='mono'>%s</span> %s<br><span class='muted'>%s</span>"
                 % (L.esc(s.get("uscc") or "未提供"), pill(chk["reason"], uscc_tone), L.esc(s.get("uscc_source", "")))})
    if s.get("biz_lic_no"):
        b = L.check_biz_lic_no(s["biz_lic_no"])
        rows.append({"k": "营业执照注册号", "v": "<span class='mono'>%s</span> %s" % (L.esc(s["biz_lic_no"]), pill(b["reason"], "ok" if b["valid"] else "bad"))})
    for k, lab in (("legal_rep", "法定代表人"), ("capital", "注册资本"), ("founded", "成立日期"),
                   ("types", "企业类型"), ("reg_addr", "注册地址"), ("site_addr", "生产/经营地址"),
                   ("business_scope", "经营范围（登记）"), ("credit_status", "登记状态")):
        if s.get(k):
            rows.append({"k": lab, "v": L.esc(s[k]).replace("\n", "<br>")})
    rows.append({"k": "身份核验要点", "v": L.esc(s.get("id_note", ""))})
    if s.get("chain"):
        rows.append({"k": "企业关系链", "v": L.esc(s["chain"])})
    body = "<div class='tw'><table class='t'><tbody>" + "".join(
        "<tr><td class='k'>%s</td><td>%s</td></tr>" % (L.esc(r["k"]), r["v"]) for r in rows) + "</tbody></table></div>"
    if s.get("scope_note"):
        body += "<div class='note warn'>%s</div>" % L.esc(s["scope_note"]).replace("\n", "<br>")
    return sec("01", "identity", "供应商主体识别", "先锁定「唯一法人」，再谈证照归属；同名不同主体是高频差错源",
               body, pill("主体身份 %s" % s.get("status", ""), "ok" if s.get("status") == "已核实" else "warn"))


def render_product(data):
    p = data.get("product", {})
    rows = [("物料名称", p.get("name")), ("商品名/别名", "、".join(p.get("aliases") or [])),
            ("CAS 登记号", "<span class='mono'>%s</span>" % L.esc(p.get("cas"))),
            ("拟采购规格/浓度", p.get("spec")), ("剂型/形态", p.get("form")),
            ("工业标准/等级", p.get("grade_std")), ("包装与运输方式", p.get("packing")),
            ("年用量/本次批量", p.get("qty")), ("采购用途/工艺", p.get("usage")),
            ("使用地点/储存条件", p.get("site")), ("SDS 版本", p.get("sds"))]
    t1 = "<div class='tw'><table class='t'><tbody>" + "".join(
        "<tr><td class='k'>%s</td><td>%s</td></tr>" % (L.esc(k), L.esc(v) if v else "<span class='muted'>未提供（须向供应商索取）</span>")
        for k, v in rows if v) + "</tbody></table></div>"

    frows = []
    for f in p.get("findings", []):
        frows.append([L.esc(f.get("item")),
                      L.esc(f.get("value")),
                      pill(f.get("verdict_label") or L.class_meta(f.get("verdict"))["label"],
                           {"confirmed": "ok", "not_confirmed": "bad", "pending": "warn"}.get(f.get("verdict"), "gray")),
                      L.esc(f.get("basis")), L.esc(f.get("condition"))])
    t2 = tbl(["识别项", "本产品结论", "判定", "依据（文号/条款/标准）", "适用条件与例外"], frows,
             widths=["12%", "", "12%", "30%", "26%"])

    ch = []
    for c in data.get("classification_checklist", []):
        ch.append([L.esc(c.get("id")), L.esc(c.get("item")),
                   pill(L.class_meta(c.get("verdict"))["label"],
                        {"confirmed": "ok", "not_confirmed": "bad", "pending": "warn"}.get(c.get("verdict"), "gray")),
                   L.esc(c.get("note"))])
    t3 = tbl(["#", "监管制度/目录", "判定", "本产品核对说明"], ch, widths=["5%", "26%", "16%", ""])

    body = ("<h3>1.1 物料档案（采购标的口径）</h3>" + t1 +
            "<div class='note'>浓度与规格必须写进采购合同与送货单：同一 CAS 在不同浓度、不同标准下可能落入不同目录条目或不同危险类别，"
            "只有产品名称本身不足以定性。</div>"
            "<h3>1.2 危险属性识别（危险化学品 / 特殊管理类别）</h3>" + t2 +
            "<h3>1.3 监管分类核验清单（逐项打勾，未确认一项不得下「不属于」结论）</h3>" + t3)
    if p.get("gaps"):
        body += "<div class='note warn'><b>身份/分类资料缺口：</b><br>" + "<br>".join("· " + L.esc(x) for x in p["gaps"]) + "</div>"
    return sec("02", "product", "产品身份与监管分类", "CAS + 浓度 + 剂型 + 用途四要素同时锁定，再对照目录条目", body,
               pill(p.get("verdict_summary", "分类核验"), "ok" if p.get("verdict_ok") else "warn"))


def render_supplier_req(data):
    rs = data.get("supplier_requirements", [])
    rows = []
    for r in rs:
        rows.append([L.esc(r.get("role")), L.esc(r.get("licence")), pill(r.get("required", ""), "bad" if r.get("required") == "必须" else "warn"),
                     L.esc(r.get("basis")), L.esc(r.get("scope_check"))])
    body = "<div class='lead'><p>%s</p></div>" % L.esc(data.get("supplier_lead", ""))
    body += tbl(["供应商角色", "应取得的许可/证照", "是否必需", "法规依据与适用条件", "核验要点（范围是否覆盖拟购品）"],
                rows, widths=["12%", "18%", "8%", "30%", ""])
    if data.get("supplier_notes"):
        body += "<div class='note'>" + "<br>".join("· " + L.esc(x) for x in data["supplier_notes"]) + "</div>"
    return sec("03", "supplier", "供应商侧：生产 / 经营 / 储存许可要求",
               "许可跟着「活动」走：生产要生产许可，经营要经营许可，有无储存设施决定「带储存」还是「不带储存」", body)


def render_buyer(data):
    erp = data.get("erp", {})
    rows = []
    for r in erp.get("obligations", []):
        rows.append([L.esc(r.get("item")), pill(r.get("status", ""), {"必须": "bad", "视情形": "warn", "建议": "gray"}.get(r.get("status"), "gray")),
                     L.esc(r.get("basis")), L.esc(r.get("trigger")), L.esc(r.get("action"))])
    ident = ""
    chk = L.check_uscc(erp.get("uscc"))
    ident = ("<div class='note'><b>我方主体：</b>%s ｜ 统一社会信用代码 <span class='mono'>%s</span> %s<br>"
             "<b>采购用途/工艺：</b>%s<br><b>储存现状：</b>%s</div>"
             % (L.esc(erp.get("name") or "（待填）"), L.esc(erp.get("uscc") or "（待填）"),
                pill(chk["reason"], "ok" if chk["valid"] else "warn"),
                L.esc(erp.get("usage") or "（待填）"), L.esc(erp.get("storage") or "（待填）")))
    body = ident + tbl(["我方义务项", "性质", "法规依据", "触发条件", "落地动作 / 证据"], rows,
                       widths=["18%", "8%", "28%", "20%", ""])
    if erp.get("notes"):
        body += "<div class='note warn'>" + "<br>".join("· " + L.esc(x) for x in erp["notes"]) + "</div>"
    return sec("04", "buyer", "采购方（使用企业）义务", "买易制爆品不是「买东西」，而是「建立一条可追溯的合法用途链」", body)


def render_certs(data):
    certs = data.get("certs", [])
    s = L.summarize(certs, data.get("as_of"))
    chips = [("<button class='fchip' data-f='st' data-v='all'>全部 <span class='n'>%d</span></button>" % len(certs))]
    for k, lab, _ in L.CERT_STATES:
        chips.append("<button class='fchip' data-f='st' data-v='%s'>%s <span class='n'>%d</span></button>"
                     % (k, lab, s.get(k, 0)))
    chips.append("<span class='lbl' style='margin-left:8px'>覆盖：</span>")
    chips.append("<button class='fchip' data-f='cov' data-v='all'>全部</button>")
    for k, lab, _ in L.COVER_VERDICTS:
        chips.append("<button class='fchip' data-f='cov' data-v='%s'>%s</button>" % (k, lab))
    chips.append("<input type='search' id='certSearch' placeholder='搜索证照名称 / 编号 / 发证机关 / 范围关键词'>")
    head = ("<div class='filters'>%s</div><div class='legend'>当前显示 <b id='certCount'>%d</b> 张证照 · 点击卡片查看证载范围、字段来源与交叉核验记录；"
            "状态含义见下表。筛选条件不改变任何判定。</div>" % ("".join(chips), len(certs)))

    legend = tbl(["状态", "定义", "本单中的判断口径"],
                 [["<span class='pill c-ok'><i class='dot'></i>已核验</span>", "证件字段能被一手/官方公开来源直接支撑",
                   "证载编号、发证机关、范围与公示一致；仅代表「该证存在且有效」，不代表企业全部合规"],
                  ["<span class='pill c-bad'><i class='dot'></i>信息不一致</span>", "字段冲突、过期、主体不符或范围不匹配",
                   "须暂停下单，书面澄清并取得更正后的证照"],
                  ["<span class='pill c-warn'><i class='dot'></i>待核验</span>", "仅凭供应商提供，尚无公开来源可比对",
                   "进入索证清单，要求原件/盖章件 + 来源链接"],
                  ["<span class='pill c-gray'><i class='dot'></i>无公开信息</span>", "经定向检索未发现公开记录",
                   "不得推断为「无证」；材料缺口必须转入索证清单"],
                  ["<span class='pill c-bad'><i class='dot'></i>已过期</span>", "证载有效期早于核验基准日", "失效即视为当前无证可用"]],
                 widths=["16%", "30%", ""])

    cards = []
    for c in certs:
        cov = "<span class='cov' style='background:%s'>%s</span>" % (
            {"cover": "var(--ok)", "partial": "var(--warn)", "not_cover": "var(--bad)"}.get(c["cover_key"], "var(--gray)"),
            L.esc(c["cover_label"]))
        src = c.get("field_source", "")
        ps = c.get("public_state") or ""
        ps_cls = "bad" if ("未发现" in ps) else ("ok" if ("官网公开" in ps or "公开" == ps.strip()) else "warn")
        ps_pill = (" " + pill(ps, ps_cls)) if ps else ""
        scan_btn = ("<button data-cert='%s'>查看原件/详情</button>" % c["id"]) if c.get("scan") else ("<button data-cert='%s'>查看核验详情</button>" % c["id"])
        url_btn = ("<a href='%s' target='_blank' rel='noopener'>公开来源 ↗</a>" % L.esc(c["url"])) if c.get("url") else ""
        cards.append("""
<article class="cert" data-state="%s" data-cov="%s" data-cert="%s" data-q="%s">%s
  <div class="ch"><div><div class="nm">%s</div><div class="no">%s</div></div>%s</div>
  <div class="meta">
    <span class="k">发证机关</span><span>%s</span>
    <span class="k">有效期</span><span>%s → %s <span class="muted">(%s)</span></span>
    <span class="k">范围</span><span>%s</span>
    <span class="k">证据</span><span>%s%s</span>
  </div>
  <div class="foot"><div class="src">%s</div><div class="acts">%s %s</div></div>
</article>""" % (
            c["state"], c["cover_key"], c["id"], L.esc(cert_search_blob(c)), cov,
            L.esc(c.get("name")), L.esc(c.get("no") or "编号待核验"),
            pill(c["state_label"], {"verified": "ok", "mismatch": "bad", "pending": "warn", "expired": "bad"}.get(c["state"], "gray")),
            L.esc(c.get("issuer") or "—"), L.esc(c.get("valid_from") or c.get("issue_date") or "—"),
            L.esc(c.get("valid_to") or "—"), L.esc(c["expiry_label"]),
            L.esc(L.clip(c.get("scope") or c.get("coverage") or "—", 70)),
            L.esc(c.get("evidence_id") or "—"), ps_pill,
            L.esc(src), scan_btn, url_btn))

    body = (head + legend + "<div class='certgrid'>" + "".join(cards) + "</div>"
            + "<div class='empty' id='certEmpty' style='display:none'>没有符合条件的证照——请放宽筛选；"
              "没有显示不等于没有证，请回到第 8 节索证清单。</div>")

    # 汇总表
    rows = []
    for c in certs:
        rows.append([L.esc(c["id"]), L.esc(c.get("name")), L.esc(c.get("no") or "待核验"), L.esc(c.get("issuer")),
                     L.esc(c.get("valid_to")), pill(c["state_label"], {"verified": "ok", "mismatch": "bad", "pending": "warn", "expired": "bad"}.get(c["state"], "gray")),
                     L.esc(c["expiry_label"]), pill(c["cover_label"], {"cover": "ok", "partial": "warn", "not_cover": "bad"}.get(c["cover_key"], "gray")),
                     L.esc(c.get("public_state") or "—"), L.esc(c.get("evidence_id") or "—")])
    body += "<h3>5.2 证照总表（可复制进供应商档案）</h3>" + tbl(
        ["编号", "证照类型", "证书编号", "发证机关", "有效期至", "核验状态", "有效期判定", "范围覆盖", "公开状态", "证据"], rows,
        widths=["5%", "17%", "18%", "13%", "8%", "8%", "9%", "7%", "10%", "5%"])
    return sec("05", "certs", "证照核验表", "按证书状态 / 有效期 / 许可范围筛选；四种状态互斥且不得混写", body,
               pill("已核验 %d · 不一致 %d · 待核验 %d" % (s.get("verified", 0), s.get("mismatch", 0), s.get("pending", 0) + s.get("no_public", 0)), "warn"))


def render_crosscheck(data):
    rows = []
    for x in data.get("crosscheck", []):
        rows.append([L.esc(x.get("item")), L.esc(x.get("left")), L.esc(x.get("right")),
                     pill(x.get("result", ""), {"一致": "ok", "不一致": "bad", "部分一致": "warn"}.get(x.get("result"), "gray")),
                     L.esc(x.get("note"))])
    body = "<div class='lead'><p>%s</p></div>" % L.esc(data.get("crosscheck_lead", ""))
    body += tbl(["比对项", "证照/供应商材料（A）", "公开来源/主管部门记录（B）", "结论", "处理意见"], rows,
                widths=["14%", "28%", "28%", "8%", ""])
    if data.get("crosscheck_notes"):
        body += "<div class='note warn'>" + "<br>".join("· " + L.esc(x) for x in data["crosscheck_notes"]) + "</div>"
    return sec("06", "crosscheck", "公开信息交叉核验", "证照字段 × 主管部门公示 × 工商身份，三方对不上就是「不一致」", body)


def render_oddities(data):
    if not data.get("oddities"):
        return ""
    rows = [[L.esc(o.get("item")), L.esc(o.get("found")), L.esc(o.get("meaning")), L.esc(o.get("verify"))] for o in data["oddities"]]
    body = "<div class='lead'><p>%s</p></div>" % L.esc(data.get("oddities_lead", ""))
    body += tbl(["疑点/观察", "已查到的事实", "可能解读（不作结论）", "如何核实"], rows, widths=["16%", "26%", "30%", ""])
    return sec("07", "oddities", "疑点与异常观察", "只陈述事实与可能解读，不倒推企业合规状态", body)


def render_request(data):
    items = list(data.get("request_list", []))
    auto, notices = L.pending_derivation(data)
    have = set((i.get("cert") or "").strip() for i in items)
    for a in auto:
        if (a.get("cert") or "").strip() not in have:
            items.append(a)
    items.sort(key=lambda x: (L.PRIORITIES.index(x.get("priority", "P1")) if x.get("priority", "P1") in L.PRIORITIES else 2,
                              x.get("auto") is True, x.get("code", "")))
    lis = []
    for it in items:
        pc = it.get("priority", "P1")
        lis.append("<li><input type='checkbox' class='ck' data-k='%s'><span class='c'>%s &nbsp;%s</span>"
                   "<div><b>%s</b>%s<div class='q'>%s</div></div>"
                   "<span>%s</span></li>" % (
                       L.esc(it.get("code")), L.esc(it.get("code")),
                       pill(pc, {"P0": "c-p0", "P1": "c-p1", "P2": "c-p2"}.get(pc, "c-gray")).replace("pill c-", "pill c-"),
                       L.esc(it.get("cert")),
                       (" <span class='tag'>AUTO</span>" if it.get("auto") else ""),
                       L.esc(it.get("ask") or it.get("reason")),
                       L.esc("/".join(x for x in [it.get("issuer"), it.get("reason")] if x))[:160]))
    body = ("<div class='clwrap'><div style='font-size:12.5px;color:var(--muted)'>勾选表示已索取并归档；勾选状态保存在本机浏览器，"
            "同时可用于「保存核验记录」。</div><div style='display:flex;align-items:center;gap:10px'><div class='prog'><i id='clProg'></i></div>"
            "<b id='clProgTxt' style='font-size:12px'>0 / 0 项</b></div></div>")
    body += "<ul class='cl'>" + "".join(lis) + "</ul>"
    body += "<div class='note'>%s</div>" % "".join(L.esc(n) + "<br>" for n in notices)

    if data.get("manual_check"):
        rows = [[L.esc(m.get("item")), L.esc(m.get("why")), L.esc(m.get("method")), L.esc(m.get("owner", ""))] for m in data["manual_check"]]
        body += "<h3>8.2 仍需人工核验的事项（无法自动化）</h3>" + tbl(["事项", "为什么必须人工", "核实方法", "责任人/时限"], rows,
                                                              widths=["18%", "26%", "38%", ""])
    return sec("08", "request", "索证清单（Material To Request）", "按优先级取证；查不到即入清单，绝不写「已确认无证」", body,
               pill("P0 %d 项" % sum(1 for i in items if i.get("priority") == "P0"), "bad"))


def render_draft(data):
    d = data.get("draft", {})
    body = ("<div class='lead'><p>%s</p></div>" % L.esc(d.get("intro", "")))
    body += ("<div style='display:flex;gap:8px;margin-bottom:8px'><button class='btn solid' data-act='copy' data-copy='#draftBody'>"
             "<svg class='ic'><use href='#i-mail'/></svg>复制草稿</button></div>")
    body += "<div class='draft' id='draftBody'>%s</div>" % L.esc(d.get("body", "")).replace("\n", "<br>")
    return sec("09", "draft", "发送给供应商的补充资料请求（草稿）", "把索证清单转成对方能直接回复的邮件/公函", body)


def render_risks(data):
    out = []
    for r in data.get("risks", []):
        lvl = {"高": "", "中": "mid", "低": "low"}.get(r.get("level"), "low")
        out.append("""<div class="risk %s">
  <div class="rh"><h4>%s</h4>%s%s</div>
  <div class="row"><div class="lb">事实</div><div>%s</div></div>
  <div class="row"><div class="lb">后果</div><div>%s</div></div>
  <div class="row"><div class="lb">处置</div><div>%s</div></div>
</div>""" % (lvl, L.esc(r.get("title")),
             pill("风险 %s" % r.get("level", ""), "bad" if r.get("level") == "高" else "warn" if r.get("level") == "中" else "gray"),
             ("<span class='tag'>%s</span>" % L.esc(r.get("ref"))) if r.get("ref") else "",
             L.esc(r.get("fact")), L.esc(r.get("impact")), L.esc(r.get("action"))))
    return sec("10", "risks", "风险与处置", "按「事实—后果—处置」写，不写「存在风险」这类空话", "".join(out))


def render_conclusion(data):
    ap = data.get("assessment", {})
    gates = "".join("""<div class="gate"><div class="code">%s</div><div class="nm">%s</div><div class="tx">%s</div></div>"""
                    % (L.esc(g.get("code")), L.esc(g.get("name")), L.esc(g.get("text"))) for g in ap.get("gates", []))
    v = ap.get("verdict", {})
    rows = "".join("<tr><td class='k'>%s</td><td>%s</td></tr>" % (L.esc(k), L.esc(val)) for k, val in v.items())
    body = """<div class="verdict">
  <div class="kicker">总体判定 · %s</div>
  <h3>%s</h3>
  <div class="txt">%s</div>
  <table><tbody>%s</tbody></table>
</div>
<h3>11.1 放行闸门（全部关闭才可下单）</h3><div class="gates">%s</div>""" % (
        L.esc(ap.get("grade_code", "")), L.esc(ap.get("grade", "")), L.esc(ap.get("summary", "")), rows, gates)
    if ap.get("statements"):
        body += "<h3>11.2 本报告能说什么 / 不能说什么</h3>" + tbl(["可以说", "不能说（禁止表述）"], [
            [L.esc(a), L.esc(b)] for a, b in ap["statements"]], widths=["50%", "50%"])
    if ap.get("next_steps"):
        tl = "".join("<div class='it'><div class='d'>%s</div><div class='x'>%s</div></div>" % (L.esc(d), L.esc(t)) for d, t in ap["next_steps"])
        body += "<h3>11.3 下一步时间表</h3><div class='tl'>%s</div>" % tl
    return sec("11", "conclusion", "总体判定与放行条件", "一份证件不能证明完全合规；本判定只针对「本次采购该产品该规格」", body)


def render_evidence(data):
    rows = []
    for e in data.get("evidence", []):
        rows.append("<div class='row'><div class='id'>%s<div class='muted' style='font-size:10.5px'>%s</div></div><div>"
                    "<div class='t'>%s</div><div class='muted'>%s ｜ %s</div><div class='u'>%s</div><div style='font-size:12px'>%s</div>"
                    "</div></div>" % (L.esc(e.get("id")), L.esc(e.get("kind", "")), L.esc(e.get("title")),
                                       L.esc(e.get("publisher", "")), L.esc(e.get("date", "")), L.esc(e.get("url", "")),
                                       L.esc(e.get("supports", ""))))
    body = "<div class='ev'>" + "".join(rows) + "</div>"
    return sec("12", "evidence", "证据与来源登记", "每条结论都能回溯到具体文号/条款/页面；无证据的一律只能写「无公开信息」", body)


def render_scans(data):
    sc = data.get("scans", [])
    if not sc:
        return ""
    g = []
    for s in sc:
        g.append("<a href='%s' target='_blank' rel='noopener'><img src='%s' alt='%s'><div class='g'>%s<em>%s</em></div></a>"
                 % (L.esc(s.get("file")), L.esc(s.get("file")), L.esc(s.get("title")), L.esc(s.get("title")), L.esc(s.get("kind", ""))))
    live = [s for s in sc if s.get("mode") != "mock"]
    mode_note = ("<div class='note bad clamp'>" + L.esc(data.get("scan_note", "")) + "</div>") if any(
        s.get("mode") == "mock" for s in sc) else ("<div class='note ok'>" + L.esc(data.get("scan_note", "")) + "</div>")
    body = mode_note + "<div class='gallery'>" + "".join(g) + "</div>"
    body += ("<div class='note'>扫描件是「上传提取」的对象；其提取结果只作 A 侧材料，"
             "必须与第 06 节的主管部门公示记录逐字段比对后才可能判定为「已核验」。</div>")
    return sec("13", "scans", "上传件与扫描件", "OCR 提取结果必须与第 06 节公开记录逐字段比对", body)


# --------------------------------------------------------------- 组装

def build_side(data):
    secs = [("01", "identity", "供应商主体识别"), ("02", "product", "产品身份与监管分类"),
            ("03", "supplier", "供应商侧许可要求"), ("04", "buyer", "采购方义务"),
            ("05", "certs", "证照核验表"), ("06", "crosscheck", "公开信息交叉核验")]
    if data.get("oddities"):
        secs.append(("07", "oddities", "疑点与异常观察"))
    secs += [("08", "request", "索证清单"), ("09", "draft", "供应商补充资料请求"),
             ("10", "risks", "风险与处置"), ("11", "conclusion", "总体判定"), ("12", "evidence", "证据登记")]
    if data.get("scans"):
        secs.append(("13", "scans", "上传件与扫描件"))
    out = ["<div class='grp'>核验流程</div>"]
    for no, sid, t in secs:
        out.append("<a href='#%s'><span class='n'>%s</span>%s</a>" % (sid, no, t))
    return "".join(out)


def build(data, assets_dir):
    data = prepare(data)
    with open(os.path.join(assets_dir, "report.css"), encoding="utf-8") as f:
        css = f.read()
    with open(os.path.join(assets_dir, "report.js"), encoding="utf-8") as f:
        js = f.read()
    with open(os.path.join(ROOT, "templates", "report.html"), encoding="utf-8") as f:
        tpl = f.read()

    main = [render_hero(data), render_kpis(data)]
    main.append(render_identity(data))
    main.append(render_product(data))
    main.append(render_supplier_req(data))
    kind = data.get("supplier_kind_note")
    if kind:
        main.append("<div class='note'>%s</div>" % L.esc(kind))
    main.append(render_buyer(data))
    main.append(render_certs(data))
    main.append(render_crosscheck(data))
    o = render_oddities(data)
    if o:
        main.append(o)
    main.append(render_request(data))
    main.append(render_draft(data))
    main.append(render_risks(data))
    main.append(render_conclusion(data))
    main.append(render_evidence(data))
    s = render_scans(data)
    if s:
        main.append(s)
    m = data.get("meta", {})
    main.append("<div class='foot-note'>本文件由 <code>chem-supplier-qualification</code> 技能按 data.json 自动生成 · 记录号 %s · 基准日 %s · "
                "生成于 %s<br>监管分类与资质要求以主管部门公示与证照原件为最终核验依据；本文件不构成法律意见，也不代表对企业合规状态的最终认定。</div>"
                % (L.esc(m.get("record_id", "")), L.esc(data.get("as_of", "")), L.esc(m.get("generated_at", ""))))

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    meta_el = ("基准日 <b>%s</b> · 记录号 <b>%s</b> · 证据 <b>%s</b> 条 · 证照 <b>%s</b> 张"
               % (L.esc(data.get("as_of")), L.esc(m.get("record_id", "—")), len(data.get("evidence", [])), len(data.get("certs", []))))
    html = (tpl.replace("__PAGE_TITLE__", L.esc(data.get("title") or "供应商资质证照核验"))
               .replace("__CSS__", css)
               .replace("__TOPBAR_META__", meta_el)
               .replace("__SIDE__", build_side(data))
               .replace("__MAIN__", "".join(main))
               .replace("__DATA__", "window.QC_DATA = " + payload + ";")
               .replace("__JS__", js))
    return html


def safe_name(s):
    for ch in '\\/:*?"<>|\n\r\t':
        s = s.replace(ch, "")
    return s.strip()[:60] or "report"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", default="out")
    ap.add_argument("--assets", default=os.path.join(ROOT, "assets"))
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    with open(a.data, encoding="utf-8") as f:
        data = json.load(f)
    html = build(data, a.assets)
    os.makedirs(a.out, exist_ok=True)
    subj = (data.get("subject") or {}).get("name", "主体")
    prod = (data.get("product") or {}).get("name", "产品")
    fn = a.name or ("资质证照核验_%s_%s.html" % (safe_name(subj), safe_name(prod)))
    path = os.path.join(a.out, fn)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML -> %s (%.1f KB)" % (path, len(html.encode("utf-8")) / 1024.0))


if __name__ == "__main__":
    main()
