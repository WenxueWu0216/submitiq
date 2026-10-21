"""Amazon Textract backend (AnalyzeDocument, FeatureTypes=TABLES), behind the same interface.

Each page is rendered to PNG and sent synchronously. Textract is the better
choice for heavily degraded scans. The cost is roughly $0.015 per page for TABLES
(check current AWS pricing) plus a network round trip, which is why `local` is
the default. Spreadsheets never go to Textract.

Untested against the live service in this repo (no AWS account). The response
parsing is covered by tests/test_tables.py with a recorded-shape fixture.
"""
from __future__ import annotations

import io
from typing import Any

from ..documents import Document
from .base import Block
from .local import LocalTableExtractor, _norm, _phrases, _tok_eq


def _text_of(block: dict, by_id: dict[str, dict]) -> str:
    words = []
    for rel in block.get("Relationships", []):
        if rel["Type"] == "CHILD":
            for cid in rel["Ids"]:
                child = by_id[cid]
                if child["BlockType"] == "WORD":
                    words.append(child["Text"])
                elif child["BlockType"] == "SELECTION_ELEMENT" and child.get("SelectionStatus") == "SELECTED":
                    words.append("X")
    return " ".join(words)


def blocks_from_response(resp: dict[str, Any], page_number: int, vocabulary: dict[str, list[str]]) -> list[Block]:
    """Convert one AnalyzeDocument response into reading-order blocks."""
    by_id = {b["Id"]: b for b in resp.get("Blocks", [])}
    phrases = _phrases(vocabulary)
    table_word_ids: set[str] = set()
    items: list[tuple[float, Block]] = []

    for t in (b for b in by_id.values() if b["BlockType"] == "TABLE"):
        cells = [by_id[cid] for rel in t.get("Relationships", []) if rel["Type"] == "CHILD"
                 for cid in rel["Ids"] if by_id[cid]["BlockType"] == "CELL"]
        for c in cells:
            for rel in c.get("Relationships", []):
                table_word_ids.update(rel["Ids"])
        grid: dict[int, dict[int, str]] = {}
        for c in cells:
            grid.setdefault(c["RowIndex"], {})[c["ColumnIndex"]] = _text_of(c, by_id)
        colmap: dict[int, str] = {}
        for r in sorted(grid):
            row = grid[r]
            top = min(c["Geometry"]["BoundingBox"]["Top"] for c in cells if c["RowIndex"] == r)
            text = " | ".join(row[k] for k in sorted(row) if row[k])
            if not colmap:
                for j, val in row.items():
                    toks = [_norm(x) for x in val.split()]
                    for field, ph in phrases:
                        if field not in colmap.values() and len(toks) == len(ph) and all(_tok_eq(a, b) for a, b in zip(toks, ph)):
                            colmap[j] = field
                            break
                if len(colmap) >= 3:
                    items.append((top, Block("header", page_number, text, {f: f for f in colmap.values()}, 1.0, f"page {page_number} table row {r}")))
                    continue
                colmap = {}
                items.append((top, Block("text", page_number, text, {}, 1.0, f"page {page_number} table row {r}")))
                continue
            conf = min((c.get("Confidence", 100.0) for c in cells if c["RowIndex"] == r), default=100.0) / 100
            kind = "text" if text.lower().startswith("total") else "row"
            items.append((top, Block(kind, page_number, text, {colmap[j]: v for j, v in row.items() if j in colmap and v}, conf,
                                     f"page {page_number} table row {r}")))

    for ln in (b for b in by_id.values() if b["BlockType"] == "LINE"):
        ids = {cid for rel in ln.get("Relationships", []) for cid in rel["Ids"]}
        if ids and ids <= table_word_ids:
            continue
        items.append((ln["Geometry"]["BoundingBox"]["Top"],
                      Block("text", page_number, ln.get("Text", ""), {}, ln.get("Confidence", 100.0) / 100, f"page {page_number}")))
    return [b for _, b in sorted(items, key=lambda x: x[0])]


class TextractTableExtractor:
    name = "textract"

    def __init__(self, client=None):
        import boto3
        self.client = client or boto3.client("textract")
        self.local = LocalTableExtractor()

    def blocks(self, doc: Document, vocabulary: dict[str, list[str]]) -> list[Block]:
        if doc.sheets:
            return self.local.blocks(doc, vocabulary)
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(doc.path))
        out: list[Block] = []
        for i in range(len(pdf)):
            img = pdf[i].render(scale=200 / 72).to_pil()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            resp = self.client.analyze_document(Document={"Bytes": buf.getvalue()}, FeatureTypes=["TABLES"])
            out += blocks_from_response(resp, i + 1, vocabulary)
        return out
