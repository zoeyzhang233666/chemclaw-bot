"""Parse the marked-up simulated contract into a structured block list.

Markup source conventions (see templates/contract_markup.md):
    @@DOC ... @@END            front matter
    @@BANNER <text>            simulated-document banner
    @@TITLE @@SUBTITLE @@META|k|v
    @@PARTIES ... @@END
    @@ARTICLES ... @@END       body: @@H1 @@H2 @@P @@TABLE/@@TR/@@END
    @@EXECUTION ... @@END
    @@ANNEXES ... @@END        @@ANNTITLE, @@H2, @@P, @@TABLE
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BLOCK_ID_PREFIX = {
    "h1": "art",
    "h2": "clause",
    "p": "p",
    "table": "tbl",
}


def slugify(text: str) -> str:
    text = re.sub(r"[^0-9A-Za-z]+", "-", text).strip("-")
    return text.lower()


def parse(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    blocks: list[dict] = []
    doc_meta: list[dict] = []
    banner = ""
    title = subtitle = ""

    section = None
    part_label = ""
    art_no = ""
    table_rows: list[list[str]] | None = None
    table_id = ""
    table_caption = ""
    counters: dict[str, int] = {}

    def next_id(prefix_key: str, hint: str = "") -> str:
        counters[prefix_key] = counters.get(prefix_key, 0) + 1
        base = BLOCK_ID_PREFIX[prefix_key]
        if hint:
            return f"{base}-{slugify(hint)}"
        return f"{base}-{counters[prefix_key]:03d}"

    def flush_table() -> None:
        nonlocal table_rows, table_id, table_caption
        if table_rows is None:
            return
        blocks.append(
            {
                "id": table_id,
                "kind": "table",
                "caption": table_caption,
                "rows": table_rows,
                "section": section,
                "part": part_label,
                "article": art_no,
            }
        )
        table_rows = None
        table_id = ""
        table_caption = ""

    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("@@TR "):
            if table_rows is None:
                raise SystemExit("@@TR outside a table")
            table_rows.append([c.strip() for c in line[5:].split("|")])
            continue
        if line.startswith("@@"):
            body = line[2:]
            if body == "EXC":
                tag, rest = "EXC", ""
            elif body.startswith("META|"):
                tag, rest = "META", body[5:]
            elif body == "EXCLEFT":
                tag, rest = "EXCLEFT", ""
            elif body == "EXCRIGHT":
                tag, rest = "EXCRIGHT", ""
            elif body.startswith("EXCLEFT"):
                tag, rest = "EXCLEFT", body[7:].strip()
            elif body.startswith("EXCRIGHT"):
                tag, rest = "EXCRIGHT", body[8:].strip()
            elif body.startswith("EXCLINE"):
                tag, rest = "EXCLINE", body[7:].strip()
            elif body == "EXC" or body == "EXCCL":
                tag, rest = "EXC", ""
            elif body.startswith("TABLE"):
                tag, rest = "TABLE", body[5:].strip()
            else:
                tag, _, rest = body.partition(" ")
            tag = tag.strip()
            rest = rest.strip()
        else:
            tag, rest = "CONT", line.strip()

        if tag == "TABLE":
            flush_table()
            table_rows = []
            table_caption = rest
            counters["table"] = counters.get("table", 0) + 1
            table_id = f"tbl-{counters['table']:03d}"
            if art_no:
                table_id = f"tbl-{slugify(art_no)}-{counters['table']:02d}"
            continue
        if tag in ("END", "TR_END", "TABLE_END"):
            flush_table()
            continue
        if tag not in ("TR", "P", "H1", "H2", "EXCLINE", "CONT"):
            flush_table()

        if tag == "BANNER":
            banner = rest
        elif tag == "TITLE":
            title = rest
        elif tag == "SUBTITLE":
            subtitle = rest
        elif tag == "META":
            k, _, v = rest.partition("|")
            doc_meta.append({"k": k.strip(), "v": v.strip()})
        elif tag == "DOC":
            section = "doc"
        elif tag == "PARTIES":
            section = "parties"
            part_label = "PARTIES"
        elif tag == "ARTICLES":
            section = "articles"
            part_label = "ARTICLES"
        elif tag == "EXECUTION":
            section = "execution"
            part_label = "EXECUTION"
        elif tag == "ANNEXES":
            section = "annexes"
            part_label = "ANNEXES"
        elif tag == "H1":
            if section == "annexes":
                blocks.append(
                    {"id": next_id("h1", rest), "kind": "annex-title", "text": rest,
                     "section": section, "part": part_label, "article": ""}
                )
            else:
                art_no = ""
                blocks.append(
                    {"id": next_id("h1", rest), "kind": "h1", "text": rest,
                     "section": section, "part": part_label, "article": ""}
                )
                art_no = rest
        elif tag == "ANNTITLE":
            blocks.append(
                {"id": next_id("h1", rest), "kind": "annex-title", "text": rest,
                 "section": section, "part": part_label, "article": ""}
            )
            art_no = rest
        elif tag == "H2":
            blocks.append(
                {"id": next_id("h2", f"{art_no}|{rest}"), "kind": "h2", "text": rest,
                 "section": section, "part": part_label, "article": art_no}
            )
        elif tag == "P":
            counters["p"] = counters.get("p", 0) + 1
            pid = f"p-{counters['p']:03d}"
            if art_no:
                pid = f"p-{slugify(art_no)}-{counters['p']:03d}"
            blocks.append(
                {"id": pid, "kind": "p", "text": rest,
                 "section": section, "part": part_label, "article": art_no}
            )
        elif tag in ("EXEC", "EXC"):
            section = "execution"
            part_label = "EXECUTION"
        elif tag == "EXCLEFT":
            blocks.append(
                {"id": next_id("p", "exec-left"), "kind": "exec-col", "side": "left",
                 "text": "", "section": section, "part": part_label, "article": ""}
            )
        elif tag == "EXCRIGHT":
            blocks.append(
                {"id": next_id("p", "exec-col"), "kind": "exec-col", "side": "right",
                 "text": "", "section": section, "part": part_label, "article": ""}
            )
        elif tag == "EXCLINE":
            # register the line under the most recent exec-col of the current block
            target = next(
                (b for b in reversed(blocks) if b["kind"] == "exec-col"), None
            )
            counters["excline"] = counters.get("excline", 0) + 1
            lid = f"xl-{counters['excline']:03d}"
            if target is None:
                blocks.append(
                    {"id": lid, "kind": "exec-line", "text": rest,
                     "section": section, "part": part_label, "article": ""}
                )
            else:
                target.setdefault("lines", []).append({"id": lid, "text": rest})
        elif tag in ("CONT",):
            # continuation of the previous paragraph
            if blocks and blocks[-1]["kind"] in ("p", "exec-line"):
                blocks[-1]["text"] = blocks[-1]["text"] + " " + rest
            else:
                raise SystemExit(f"CONT without anchor: {rest[:40]}")
        else:
            raise SystemExit(f"unknown tag @@{tag}")

    flush_table()

    # stable ordering / ids already unique by construction; verify
    ids = []
    for b in blocks:
        ids.append(b["id"])
        for ln in b.get("lines", []):
            ids.append(ln["id"])
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"duplicate block ids: {sorted(dupes)}")

    return {
        "title": title,
        "subtitle": subtitle,
        "banner": banner,
        "meta": doc_meta,
        "blocks": blocks,
    }


def build_index(blocks: list[dict]) -> list[dict]:
    """Clause index: one row per article and per sub-clause, with block anchors."""
    index: list[dict] = []
    cur_art = None
    cur_art_blocks: list[str] = []
    for b in blocks:
        if b["kind"] in ("h1", "annex-title"):
            if cur_art:
                cur_art["blocks"] = cur_art_blocks
                index.append(cur_art)
            cur_art = {
                "id": b["id"],
                "level": 1,
                "title": b["text"],
                "article": b["text"],
                "clauses": [],
            }
            cur_art_blocks = [b["id"]]
        elif b["kind"] == "h2" and cur_art:
            cur_art["clauses"].append({"id": b["id"], "title": b["text"], "blocks": [b["id"]]})
            cur_art_blocks.append(b["id"])
        else:
            if cur_art:
                cur_art_blocks.append(b["id"])
                if cur_art["clauses"]:
                    cur_art["clauses"][-1]["blocks"].append(b["id"])
    if cur_art:
        cur_art["blocks"] = cur_art_blocks
        index.append(cur_art)
    return index


if __name__ == "__main__":
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    parsed = parse(src)
    parsed["index"] = build_index(parsed["blocks"])
    out.write_text(json.dumps(parsed, ensure_ascii=False, indent=1), encoding="utf-8")
    kinds: dict[str, int] = {}
    for b in parsed["blocks"]:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    print(f"blocks={len(parsed['blocks'])} kinds={kinds}")
    print(f"articles={sum(1 for i in parsed['index'] if i['level'] == 1)}")
    print(f"clauses={sum(len(i['clauses']) for i in parsed['index'])}")
