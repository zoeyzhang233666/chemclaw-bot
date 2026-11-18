#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""来源链接抽检（link gate）：逐条实抓 leads.json 里的「来源」，判断可达性与主体一致性。

用法：
    python qa_links.py --dir <任务目录> [--limit N] [--workers 8]

输出：<任务目录>/leads_raw/_qa_report.json
      合并脚本（merge_leads.py）会读取它，把未通过的备注标注进「来源」列。

判定：
  * 来源里没有可提取的 URL        -> 可达 False，备注「来源不是URL（未抽到可访问链接）」
  * 抓到 PDF（响应以 %PDF 开头）  -> 通过，备注「PDF 直链」
  * 抓到 HTML：正文含公司主体名    -> 通过
  * 抓到 HTML：正文不含公司主体名  -> 不通过，备注「正文未见公司主体名」（多为栏目页/检索页）
  * 抓取异常                      -> 不通过，重试一次再判失败（避免瞬时抖动误判）
  * 反爬/人机验证/需登录           -> 仍按不通过记录，但备注写「疑似反爬，建议人工复核」
"""
import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# URL 在全角括号/引号/中文处截断（说明文字常紧跟在 URL 后面，不加这条会把中文并进链接）
# 注意：极少数「路径里带原始中文」的 URL 会被截断——这类 URL 通常已被百分号编码，若被截断会在抽检里报不可达，由修复环节发现。
URL_RE = re.compile(r"https?://[^\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef，。；;、）)】」》\"'（(「《]+")
ANTIBOT = re.compile(r"(?i)(human_machine|verify|验证码|安全验证|访问受限|robot|waf|登录)")
ADMIN_SUFFIX = re.compile(r"(股份有限公司|有限责任公司|有限公司|集团有限公司|集团|公司|股份)$")
ADMIN_WORDS = re.compile(r"(国际|科技|新材料|实业|化工|建材|高科|企业|工业|制造|发展)$")
REGION_PREFIX = re.compile(
    r"^(上海市|上海|江苏省|江苏|浙江省|浙江|安徽省|安徽|福建省|福建|江西省|江西|山东省|山东|"
    r"北京市|北京|天津市|天津|重庆市|重庆|广东省|广东|河北省|河北|河南省|河南|湖北省|湖北|湖南省|湖南|"
    r"四川省|四川|陕西省|陕西|辽宁省|辽宁|吉林省|吉林|黑龙江省|黑龙江|山西省|山西|内蒙古|广西|海南省|海南|"
    r"贵州省|贵州|云南省|云南|甘肃省|甘肃|青海省|青海|宁夏|新疆|西藏)")


def core_of(name):
    n = re.sub(r"[（(].*?[)）]", "", name or "")
    n = ADMIN_SUFFIX.sub("", n)
    n = REGION_PREFIX.sub("", n)
    return n.strip()


def strip_html(t):
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def fetch(url, timeout=25, limit=500000):
    req = urllib.request.Request(url, headers=UA)
    r = urllib.request.urlopen(req, context=CTX, timeout=timeout)
    return r.status, r.geturl(), (r.headers.get("Content-Type") or ""), r.read(limit)


def check(item):
    name = (item.get("公司") or "").strip()
    src = (item.get("来源") or "").strip()
    core = core_of(name)
    rec = {"i": 0, "公司": name, "core": core, "来源": src, "状态": "",
           "可达": False, "主体一致": False, "备注": "", "最终URL": ""}

    urls = URL_RE.findall(src)
    if not urls:
        rec["备注"] = "来源不是URL（未抽到可访问链接）"
        return rec

    last_err = ""
    for url in urls[:2]:
        url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%")
        data = None
        # 连接超时/被重置在小站点上很常见，最多试 3 次再判失败（避免把好链误判成坏链）
        for attempt, timeout in ((1, 25), (2, 30), (3, 40)):
            try:
                status, final, ctype, data = fetch(url, timeout=timeout)
                break
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}"
                if e.code < 500:
                    break
            except Exception as e:
                last_err = str(e)[:90]
            time.sleep(1.2 * attempt)

        if data is None:
            continue

        rec["状态"] = status
        rec["最终URL"] = final
        if data[:4] == b"%PDF":
            rec["可达"] = True
            rec["主体一致"] = True
            rec["备注"] = "PDF 直链（未做正文比对）"
            return rec

        text = ""
        for enc in ("utf-8", "gbk", "gb18030"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        body = strip_html(text)
        rec["可达"] = True
        hay = body + " " + url
        hit = False
        if len(core) >= 2 and core in hay:
            hit = True
        if not hit:
            short = ADMIN_WORDS.sub("", core)
            if len(short) >= 2 and short in hay:
                hit = True
        if not hit and len(core) >= 4 and core[:4] in hay:
            hit = True
        rec["主体一致"] = hit
        if not hit:
            rec["备注"] = "疑似反爬/需人机验证，建议人工复核" if ANTIBOT.search(body[:4000]) else "正文未见公司主体名"
            continue
        rec["备注"] = ""
        return rec

    if not rec["可达"]:
        rec["备注"] = last_err or "抓取失败"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--leads", default="leads.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    task_dir = os.path.abspath(args.dir)
    leads_path = os.path.join(task_dir, args.leads)
    out_path = os.path.join(task_dir, "leads_raw", "_qa_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    leads = json.load(open(leads_path, encoding="utf-8"))
    if args.limit:
        leads = leads[: args.limit]

    print(f"抽检 {len(leads)} 条 ...")
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, rec in enumerate(ex.map(check, leads), 1):
            rec["i"] = i
            rows.append(rec)

    json.dump(rows, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = [r for r in rows if r["可达"] and r["主体一致"]]
    bad = [r for r in rows if not (r["可达"] and r["主体一致"])]
    rate = (len(ok) / len(rows) * 100) if rows else 0
    print(f"完成：通过 {len(ok)} / 未通过 {len(bad)}，通过率 {rate:.1f}% -> {out_path}")
    for r in bad[:40]:
        print(f"  [未通过] {r['公司']} | {r['状态']} | {r['备注']} | {r['来源'][:80]}")


if __name__ == "__main__":
    main()
