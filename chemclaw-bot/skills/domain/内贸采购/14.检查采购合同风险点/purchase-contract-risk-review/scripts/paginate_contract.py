"""给合同 DOCX 添加页码标记，并核对「声明页码」与「真实分页」是否一致。

做法（不依赖 Word）：
  1. 用 LibreOffice Kit 把 DOCX 转成 PDF（真实排版）；
  2. 用 pdfium（pypdfium2，若可用）或 pdftotext 逐页取文本；
  3. 找到每个条款的原文在 PDF 中的页序，写入 docx「页码标记」列；
  4. 与 contract.json 中的 page 字段比对，输出差异报告。

用法:
    python paginate_contract.py --docx <合同.docx> --dir <案例目录> [--apply]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

LIBREOFFICE = shutil.which('libreoffice') or shutil.which('soffice')


def to_pdf(docx: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / (docx.stem + ".pdf")
    if not LIBREOFFICE:
        raise RuntimeError('Install LibreOffice or supply a PDF; DSH installation internals are not used.')
    r = subprocess.run([LIBREOFFICE, '--headless', '--convert-to', 'pdf', '--outdir', str(out_dir), str(docx)],
                       capture_output=True, text=True)
    if not pdf.exists():
        raise RuntimeError(f"PDF 转换失败: {r.stdout} {r.stderr}")
    return pdf


def page_texts(pdf: Path) -> list[str]:
    try:
        import pypdfium2 as pdfium  # type: ignore
    except ImportError:
        pdfium = None
    if pdfium is not None:
        doc = pdfium.PdfDocument(pdf)
        return [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
    try:
        import pymupdf  # type: ignore
    except ImportError:
        pymupdf = None
    if pymupdf is not None:
        with pymupdf.open(pdf) as doc:
            return [page.get_text() for page in doc]
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        PdfReader = None
    if PdfReader is not None:
        return [p.extract_text() or "" for p in PdfReader(str(pdf)).pages]
    raise RuntimeError("缺少 pypdfium2 / pymupdf / pypdf，无法读取 PDF 文本")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--apply", action="store_true", help="把真实页码写回 contract.json")
    a = ap.parse_args()
    docx = Path(a.docx)
    pages = page_texts(to_pdf(docx, docx.parent / "pdf"))
    flat = [norm(p) for p in pages]
    cpath = next(p for p in Path(a.dir).glob("*.json") if "clauses" in json.loads(p.read_text(encoding="utf-8")))
    c = json.loads(cpath.read_text(encoding="utf-8"))
    rows, mismatch = [], []
    for cl in c["clauses"]:
        key = norm(cl["text"])[:36]
        found = next((i + 1 for i, t in enumerate(flat) if key and key in t), None)
        ok = found == cl["page"]
        rows.append({"id": cl["id"], "declared": cl["page"], "actual": found, "ok": ok})
        if not ok:
            mismatch.append(rows[-1])
    report = {"pages": len(pages), "declared_ok": len(rows) - len(mismatch), "total": len(rows),
              "mismatch": mismatch, "rows": rows}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if a.apply and mismatch:
        for cl in c["clauses"]:
            r = next(x for x in rows if x["id"] == cl["id"])
            if r["actual"]:
                cl["page"] = r["actual"]
        cpath.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已按真实分页更新 contract.json")


if __name__ == "__main__":
    main()
