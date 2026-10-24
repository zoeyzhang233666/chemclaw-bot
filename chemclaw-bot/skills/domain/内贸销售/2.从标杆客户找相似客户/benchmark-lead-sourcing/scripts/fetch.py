#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch.py —— 联网取证 CLI（仅 Python 标准库，Windows/macOS/Linux 通用）

子命令
  cninfo  上市公司公告全文检索（巨潮资讯）：返回 代码|名称|日期|标题|高亮片段|PDF链接
  html    抓网页正文（自动去标签/压缩空白/探测编码），可只看关键词上下文
  sina    交易所/财经站公司资料页（新浪财经，按 6 位 A 股代码）
  check   链接抽检（link gate）：批量检查可达性与主体一致性，直接产出 _qa_report.json

示例
  python fetch.py cninfo -k "福莱特 纯碱" -n 8 --snippet 240
  python fetch.py html "https://www.example.com/" --grep "纯碱"
  python fetch.py sina -c 601636
  python fetch.py check --file leads_raw/_qa_todo.json --out leads_raw/_qa_report.json --sample 40
"""
import argparse
import gzip
import html as html_mod
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zlib

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 30
CNINFO_SEARCH = ("http://www.cninfo.com.cn/new/fulltextSearch/full"
                 "?searchkey={key}&isfulltext=true&sortName=nothing&sortType=desc"
                 "&pageNum=1&pageSize={size}")
SINA_CORP = ("http://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/{code}.phtml")
_TAG = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")
_COMMENT = re.compile(r"(?s)<!--.*?-->")
_ANYTAG = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
_WS = re.compile(r"\s+")


# ------------------------------------------------------------------ 基础
def fetch_raw(url, timeout=TIMEOUT):
    """返回 (status, headers, bytes)。出网异常向上抛。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        if "gzip" in enc:
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        elif "deflate" in enc:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        return resp.status, dict(resp.headers), raw


def decode(raw, headers=None):
    """尽力正确解码：响应头 charset → utf-8 → gbk/gb18030 → latin-1。"""
    charset = ""
    if headers:
        charset = headers.get("Content-Type", "") or headers.get("content-type", "")
        m = re.search(r"charset=([\w-]+)", charset, re.I)
        charset = m.group(1) if m else ""
    for enc in ([charset] if charset else []) + ["utf-8", "gb18030", "gbk"]:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1", "replace")


def to_text(html_str):
    txt = _TAG.sub(" ", html_str)
    txt = _COMMENT.sub(" ", txt)
    txt = _ANYTAG.sub(" ", txt)
    txt = html_mod.unescape(txt)
    return _WS.sub(" ", txt).strip()


def title_of(html_str):
    m = _TITLE.search(html_str)
    return _WS.sub(" ", html_mod.unescape(m.group(1))).strip() if m else ""


def norm_company(name):
    """归一化公司名，用于主体一致性判断。"""
    n = re.sub(r"[（(].*?[)）]", "", name or "")
    n = re.sub(r"(股份有限公司|有限责任公司|有限公司|集团有限公司|集团|公司|股份)", "", n)
    return re.sub(r"[\s·,，.。]", "", n)


def subject_match(company, page_text):
    """页面正文/标题是否与公司名对应（返回 (bool, 命中的关键词)）。"""
    core = norm_company(company)
    if not core:
        return (False, "")
    for cand in (core, core[:4], core[:3], core[:2]):
        if len(cand) >= 2 and cand in page_text:
            return (True, cand)
    return (False, "")


# ------------------------------------------------------------------ 子命令
def cmd_cninfo(args):
    url = CNINFO_SEARCH.format(key=urllib.parse.quote(args.key), size=min(max(args.n, 1), 10))
    try:
        _, headers, raw = fetch_raw(url, args.timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"ERR: {type(exc).__name__}: {exc}")
        return 1
    try:
        data = json.loads(decode(raw, headers))
    except ValueError as exc:
        print(f"PARSE-ERR: {exc}")
        return 1
    print(f"TOTAL={data.get('totalRecordNum')}")
    for a in data.get("announcements") or []:
        snip = re.sub(r"<[^>]+>", "", str(a.get("announcementContent") or ""))
        snip = _WS.sub(" ", html_mod.unescape(snip)).strip()
        title = _WS.sub(" ", html_mod.unescape(re.sub(r"<[^>]+>", "", str(a.get("announcementTitle") or "")))).strip()
        if len(snip) > args.snippet:
            snip = snip[:args.snippet]
        ts = a.get("announcementTime")
        day = ""
        if ts:
            import datetime
            day = datetime.datetime.fromtimestamp(int(ts) / 1000,
                                                  datetime.timezone.utc).strftime("%Y-%m-%d")
        pdf = "http://static.cninfo.com.cn/" + str(a.get("adjunctUrl") or "")
        print("|".join([str(a.get("secCode")), str(a.get("secName")), day,
                        title, snip, pdf]))
    return 0


def cmd_html(args):
    try:
        status, headers, raw = fetch_raw(args.url, args.timeout)
    except urllib.error.HTTPError as exc:
        print(f"ERR: HTTP {exc.code} {exc.reason}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERR: {type(exc).__name__}: {exc}")
        return 1
    body = decode(raw, headers)
    txt, title = to_text(body), title_of(body)
    print(f"STATUS={status} TITLE={title} LEN={len(txt)}")
    if args.grep:
        ms = re.findall(".{0,90}" + re.escape(args.grep) + ".{0,150}", txt)
        if not ms:
            print(f"NO-MATCH for: {args.grep}")
        for m in ms[:8]:
            print("..." + m + "...")
    else:
        print(txt[:args.max])
    return 0


def cmd_sina(args):
    return cmd_html(argparse.Namespace(url=SINA_CORP.format(code=args.code.strip()),
                                       max=args.max, grep=args.grep or "注册地址",
                                       timeout=args.timeout))


def cmd_check(args):
    with open(args.file, "r", encoding="utf-8-sig") as fh:
        todo = json.load(fh)
    if isinstance(todo, dict):
        todo = todo.get("items") or todo.get("leads") or []
    cn = [x for x in todo if "cninfo.com.cn" in (x.get("来源") or "")]
    other = [x for x in todo if "cninfo.com.cn" not in (x.get("来源") or "")]
    if args.sample and len(todo) > args.sample:
        keep_other = other
        quota = max(args.sample - len(keep_other), 1)
        step = max(len(cn) // quota, 1)
        todo = cn[::step][:quota] + keep_other
    out = []
    for i, item in enumerate(todo, 1):
        url, company = item.get("来源", ""), item.get("公司", "")
        row = {"公司": company, "来源": url, "可达": False, "主体一致": False, "备注": ""}
        try:
            status, headers, raw = fetch_raw(url, args.timeout)
            ctype = (headers.get("Content-Type") or "").lower()
            is_pdf = "pdf" in ctype or raw[:5] == b"%PDF-"
            if is_pdf or "cninfo.com.cn" in url:
                row["可达"] = status == 200
                row["主体一致"] = status == 200
                row["备注"] = "cninfo公告PDF可达（仅验证文件存在；PDF为二进制，正文未解析）"
            else:
                body = decode(raw, headers)
                ok, hit = subject_match(company, title_of(body) + " " + to_text(body)[:4000])
                row["可达"] = status == 200
                row["主体一致"] = ok
                row["备注"] = "正常" if ok else f"页面可达但未命中主体名（命中词={hit or '无'}），建议人工复核"
        except urllib.error.HTTPError as exc:
            anti = exc.code in (403, 401, 429)
            row["备注"] = (f"反爬拦截（HTTP {exc.code}），浏览器可访问，建议人工复核"
                           if anti else f"坏链：HTTP {exc.code}")
        except Exception as exc:  # noqa: BLE001
            row["备注"] = f"坏链/不可达：{type(exc).__name__}: {exc}"
        out.append(row)
        print(f"  [{i}/{len(todo)}] {'OK ' if row['可达'] and row['主体一致'] else 'FAIL'} "
              f"{company[:20]} {row['备注'][:40]}")
    ok_n = sum(1 for r in out if r["可达"] and r["主体一致"])
    print(f"抽检 {len(out)} 条：通过 {ok_n}，未通过 {len(out) - ok_n}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print(f"-> {args.out}")
    return 0


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="联网取证 CLI（仅标准库）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("cninfo", help="上市公司公告全文检索")
    p.add_argument("-k", "--key", required=True)
    p.add_argument("-n", "--num", type=int, default=8, dest="n", help="pageSize，必须 ≤10")
    p.add_argument("--snippet", type=int, default=240)
    p.add_argument("--timeout", type=int, default=TIMEOUT)
    p.set_defaults(func=cmd_cninfo)

    p = sub.add_parser("html", help="抓网页正文")
    p.add_argument("url")
    p.add_argument("--max", type=int, default=1200)
    p.add_argument("--grep", default="")
    p.add_argument("--timeout", type=int, default=TIMEOUT)
    p.set_defaults(func=cmd_html)

    p = sub.add_parser("sina", help="新浪财经公司资料页（6 位 A 股代码）")
    p.add_argument("-c", "--code", required=True)
    p.add_argument("--max", type=int, default=1500)
    p.add_argument("--grep", default="注册地址")
    p.add_argument("--timeout", type=int, default=TIMEOUT)
    p.set_defaults(func=cmd_sina)

    p = sub.add_parser("check", help="链接抽检（link gate）")
    p.add_argument("--file", required=True, help="待检 JSON（[{公司,来源(,类型)}]）")
    p.add_argument("--out", default="")
    p.add_argument("--sample", type=int, default=0, help="只抽 N 条（cninfo 均匀抽样，非 cninfo 全检）")
    p.add_argument("--timeout", type=int, default=TIMEOUT)
    p.set_defaults(func=cmd_check)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
