#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the interactive studio HTML from templates + a data JSON.

Usage:
  python scripts/build_studio_html.py --data build/demo-ex001-soda-ash-indonesia.json \
      --out build/xxx.html

The engine (templates/engine.js) is embedded so the page is self-contained and
works offline from file://; the demo data (if any) is embedded as
window.__DEMO_DATA__ and the document is initially loaded as DRAFT.
"""
import argparse, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "templates")

MARKERS = {
    "/*ENGINE_START*/": os.path.join(TPL, "engine.js"),
    "/*APP_START*/": os.path.join(TPL, "studio.app.js"),
}


def read(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def build(data_path, out_path, title=None, initial_state="DRAFT"):
    html = read(os.path.join(TPL, "studio.template.html"))
    for marker, src in MARKERS.items():
        code = read(src)
        if "</script" in code.replace("</script>", "").lower():
            sys.exit("script contains a literal </script")
        html = html.replace("<script>" + marker + "</script>", "<script>\n" + code + "\n</script>", 1)

    data = {}
    if data_path:
        data = json.loads(read(data_path))
        if initial_state == "DRAFT":
            data.setdefault("state", {})
            data["state"]["stage"] = "DRAFT"
            data["state"]["reviewConfirmed"] = False
            data.pop("review", None)
        elif initial_state == "FORMAL":
            data.setdefault("state", {})
            data["state"]["stage"] = "FORMAL"
            data["state"]["reviewConfirmed"] = True
            data.setdefault("view", {})["watermark"] = False
    embed = ('<script>window.__DEMO_DATA__ = ' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + ';</script>')
    # place the embedded data before the engine so the app can read it on boot
    if "/*DATA_EMBED*/" not in html:
        sys.exit("DATA_EMBED placeholder missing — template changed?")
    html = html.replace("<script>/*DATA_EMBED*/</script>", embed, 1)
    if title:
        html = html.replace("<title>", "<title>" + title + " — ", 1)
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("wrote", out_path, "%.1f KB" % (os.path.getsize(out_path) / 1024))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    build(a.data, a.out, a.title or None)


if __name__ == "__main__":
    main()
