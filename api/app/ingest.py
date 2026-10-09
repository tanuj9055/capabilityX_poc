"""Upload -> numbered text blocks. .docx: paragraphs + table rows in body order.
PDF: text lines per page (pymupdf); scanned PDFs / images: Gemini transcribes."""
from __future__ import annotations

import io

import docx
import fitz  # pymupdf
from docx.oxml.ns import qn

from . import gemini


def to_blocks(data: bytes, filename: str) -> list[dict]:
    name = filename.lower()
    if name.endswith(".docx"):
        blocks = _docx(data)
    elif name.endswith(".pdf"):
        blocks = _pdf(data)
        if sum(len(b["text"]) for b in blocks) < 200:  # scanned
            blocks = _vision(data, "application/pdf")
    elif name.endswith((".png", ".jpg", ".jpeg")):
        blocks = _vision(data, "image/png" if name.endswith(".png") else "image/jpeg")
    elif name.endswith((".txt", ".md")):
        blocks = [{"text": ln.strip()} for ln in data.decode("utf-8", "ignore").splitlines() if ln.strip()]
    else:
        raise ValueError("Unsupported file type — upload .docx, .pdf, .png/.jpg or .txt")
    for i, b in enumerate(blocks, 1):
        b["id"] = i
    return blocks


def _docx(data: bytes) -> list[dict]:
    d = docx.Document(io.BytesIO(data))
    out = []
    for el in d.element.body.iterchildren():
        if el.tag == qn("w:p"):
            t = "".join(x.text or "" for x in el.iter(qn("w:t"))).strip()
            if t:
                st = el.find(".//" + qn("w:pStyle"))
                style = st.get(qn("w:val")) if st is not None else ""
                out.append({"text": t, "kind": "heading" if style.lower().startswith(("heading", "title")) else "p"})
        elif el.tag == qn("w:tbl"):
            for tr in el.iter(qn("w:tr")):
                cells = ["".join(x.text or "" for x in tc.iter(qn("w:t"))).strip() for tc in tr.iter(qn("w:tc"))]
                cells = [c for c in cells if c]
                if cells:
                    out.append({"text": " | ".join(cells), "kind": "row"})
    return out


def _pdf(data: bytes) -> list[dict]:
    out = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for pno, page in enumerate(doc, 1):
            for b in page.get_text("blocks"):
                t = " ".join(b[4].split())
                if t:
                    out.append({"text": t, "kind": "p", "page": pno})
    return out


def _vision(data: bytes, mime: str) -> list[dict]:
    r = gemini.generate_json(
        "Transcribe this RFQ document into reading-order text blocks (one paragraph, heading, list item or "
        'table row per block; join table cells with " | "). Return JSON: {"blocks": [str]}',
        parts=[gemini.file_part(data, mime)], temperature=0, tag="ocr")
    return [{"text": str(t).strip(), "kind": "p"} for t in r.get("blocks", []) if str(t).strip()]
