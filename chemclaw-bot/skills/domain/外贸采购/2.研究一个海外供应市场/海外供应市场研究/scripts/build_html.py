#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_html.py —— 海外供应市场研究 Skill 的 HTML 生成器

用法：
    python build_html.py <data.json> <template.html> <output.html>

作用：
    1. 读取 data.json（含 meta / sources / plants / trade / logistics / policy / events 等）
    2. 把数据嵌入模板为 window.MARKET_DATA（离线可用的自包含单文件）
    3. 校验关键字段，缺少必填项直接报错，避免"空报告"

模板中除少量 {{.xxx}} 占位（用于 <title> 等无 JS 场景）外，其余全部由 JS 渲染。
"""
import json, sys, os, re, html as H

REQUIRED_KEYS = ["meta", "sources", "sites", "companies", "plants", "trade",
                 "concentration", "logistics", "policy", "events", "risks"]

def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def validate(d):
    missing = [k for k in REQUIRED_KEYS if k not in d]
    if missing:
        raise SystemExit(f"[ERR] data.json 缺少必填顶层字段: {missing}")
    if not d["plants"]:
        raise SystemExit("[ERR] plants 为空：必须先完成生产企业与装置核实")
    for p in d["plants"]:
        for k in ("id", "company", "plant", "site", "capacity_kt", "cap_basis", "evidence_level"):
            if k not in p:
                raise SystemExit(f"[ERR] 装置 {p.get('id','?')} 缺少字段 {k}")
        if p["site"] not in d["sites"]:
            raise SystemExit(f"[ERR] 装置 {p['id']} 的 site={p['site']} 不在 sites 中")
    ys = [y["year"] for y in d["trade"]["by_year"]]
    if ys != sorted(ys):
        raise SystemExit("[ERR] trade.by_year 年份未升序")
    src_ids = {s["id"] for s in d["sources"]}
    # 引用完整性：装置引用的来源必须存在
    for p in d["plants"]:
        for sid in p.get("source_ids", []):
            if sid not in src_ids:
                print(f"[WARN] 装置 {p['id']} 引用不存在的来源 {sid}")
    east = sum(p["capacity_kt"] for p in d["plants"]
               if "波斯湾" in d["sites"][p["site"]].get("coast", ""))
    west = sum(p["capacity_kt"] for p in d["plants"]
               if "红海" in d["sites"][p["site"]].get("coast", ""))
    print(f"[OK] 装置 {len(d['plants'])} 套，名义产能合计 {sum(p['capacity_kt'] for p in d['plants'])} kt/a"
          f"（东海岸 {east} / 西海岸 {west}）；来源 {len(d['sources'])} 条；事件 {len(d['events'])} 个")

def build(data_path, tpl_path, out_path):
    d = load(data_path)
    validate(d)
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    # 仅替换 <title> 级别的简单占位
    for k, v in [("{{.meta.title}}", d["meta"]["title"]),
                 ("{{.meta.subtitle}}", d["meta"]["subtitle"]),
                 ("{{.meta.country_cn}}", d["meta"]["country_cn"]),
                 ("{{.meta.country}}", d["meta"]["country"]),
                 ("{{.meta.product_cn}}", d["meta"]["product_cn"]),
                 ("{{.meta.hs_code}}", d["meta"]["hs_code"]),
                 ("{{.meta.research_date}}", d["meta"]["research_date"]),
                 ("{{.meta.scale_note}}", d["meta"]["scale_note"]),
                 ("{{.meta.prepared_for}}", d["meta"]["prepared_for"]),
                 ("{{.meta.as_of_note}}", d["meta"]["as_of_note"])]:
        tpl = tpl.replace(k, v)
    payload = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    # 防 XSS：把 </script> 打断，防止数据中出现结束标签
    payload = payload.replace("</", "<\\/")
    inject = f'<script>window.MARKET_DATA = {payload};</script>\n'
    tpl = tpl.replace("<script>\n/* =========", inject + "<script>\n/* =========", 1)
    left = re.findall(r"\{\{\.[^}]+\}\}", tpl)
    if left:
        print(f"[WARN] 未替换占位: {set(left)}")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(tpl)
    print(f"[OK] 生成 {out_path} （{len(tpl)/1024:.1f} KB）")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    build(sys.argv[1], sys.argv[2], sys.argv[3])
