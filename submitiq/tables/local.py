"""Local table extractor: rebuilds tables from word positions.

1. Header detection: a line whose words spell at least three known column
   names (longest phrase first, tolerant of one-letter OCR slips such as "Bidg").
2. Column bands: each header column owns the x-range up to the next column.
   Unknown header words get their own band, so their values cannot bleed into
   a neighbouring known column.
3. Rows: following lines are cut into the bands. The bands carry over a page
   break, so a table split across pages without a repeated header still parses.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..documents import Document
from ..textlayout import Line, Word
from .base import Block

STOP_PREFIXES = ("total", "policy period", "period total", "no losses", "additional locations",
                 "number of locations", "remaining locations", "this report", "prepared by")


def _norm(tok: str) -> str:
    return re.sub(r"[.:,]", "", tok.lower()).strip()


def _tok_eq(a: str, b: str) -> bool:
    if a == b:
        return True
    return len(a) >= 4 and len(b) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.75


@dataclass
class Column:
    field: str
    x0: float


def _phrases(vocab: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    out = [(f, [_norm(t) for t in syn.split()]) for f, syns in vocab.items() for syn in syns]
    return sorted(out, key=lambda p: -len(p[1]))


def match_header(words: list[Word], vocab: dict[str, list[str]]) -> list[Column] | None:
    toks = [_norm(w.text) for w in words]
    phrases = _phrases(vocab)
    cols: list[Column] = []
    used: set[str] = set()
    matched_words = 0
    i, unknown = 0, 0
    while i < len(toks):
        hit = None
        # Exact phrases first; fuzzy (OCR slips like "Bidg") only if nothing matches exactly.
        # Otherwise "Sprinklered %" fuzzily matches "sprinkler %" and shifts two columns.
        for eq in (str.__eq__, _tok_eq):
            for field, ph in phrases:
                k = len(ph)
                if field not in used and i + k <= len(toks) and all(eq(toks[i + j], ph[j]) for j in range(k)):
                    hit = (field, k)
                    break
            if hit:
                break
        if hit:
            cols.append(Column(hit[0], words[i].x0))
            used.add(hit[0])
            matched_words += hit[1]
            i += hit[1]
            continue
        # Unknown word: glue to the previous header word if they touch, else start an unknown band.
        if cols and i > 0 and words[i].x0 - words[i - 1].x1 < 3.0:
            i += 1
            continue
        cols.append(Column(f"_unknown{unknown}", words[i].x0))
        unknown += 1
        i += 1
    known = [c for c in cols if not c.field.startswith("_")]
    if len(known) < 3 or matched_words < 0.6 * len(toks):
        return None
    return cols


def cut_row(line: Line, cols: list[Column]) -> dict[str, str]:
    cells: dict[str, list[str]] = {}
    for w in line.words:
        j = 0
        for k, c in enumerate(cols):
            if w.xc >= c.x0 - 2.0:
                j = k
        cells.setdefault(cols[j].field, []).append(w.text)
    return {f: " ".join(v) for f, v in cells.items() if not f.startswith("_")}


class LocalTableExtractor:
    name = "local"

    def blocks(self, doc: Document, vocabulary: dict[str, list[str]]) -> list[Block]:
        if doc.sheets:
            return self._sheet_blocks(doc, vocabulary)
        out: list[Block] = []
        cols: list[Column] | None = None
        for page in doc.pages:
            for n, line in enumerate(page.lines, start=1):
                text = line.text()
                loc = f"page {page.number} line {n}"
                conf = line.conf if page.ocr else 1.0
                header = match_header(line.words, vocabulary)
                if header:
                    cols = header
                    out.append(Block("header", page.number, text, {c.field: c.field for c in header}, conf, loc))
                    continue
                low = text.lower().lstrip()
                if cols and not low.startswith(STOP_PREFIXES):
                    cells = cut_row(line, cols)
                    if len(cells) >= min(3, len(cols)):
                        out.append(Block("row", page.number, text, cells, conf, loc))
                        continue
                out.append(Block("text", page.number, text, {}, conf, loc))
        return out

    def _sheet_blocks(self, doc: Document, vocabulary: dict[str, list[str]]) -> list[Block]:
        out: list[Block] = []
        phrases = _phrases(vocabulary)
        for sh in doc.sheets:
            colmap: dict[int, str] | None = None
            for r, row in enumerate(sh.rows, start=1):
                loc = f"{sh.name}!R{r}"
                cells = ["" if v is None else str(v).strip() for v in row]
                text = " | ".join(c for c in cells if c)
                if not text:
                    continue
                if colmap is None:
                    cand: dict[int, str] = {}
                    for j, c in enumerate(cells):
                        toks = [_norm(t) for t in c.split()]
                        for field, ph in phrases:
                            if field not in cand.values() and len(toks) == len(ph) and all(_tok_eq(a, b) for a, b in zip(toks, ph)):
                                cand[j] = field
                                break
                    if len(cand) >= 3:
                        colmap = cand
                        out.append(Block("header", None, text, {f: f for f in cand.values()}, 1.0, loc))
                    else:
                        out.append(Block("text", None, text, {}, 1.0, loc))
                    continue
                first = next((c for c in cells if c), "")
                if first.lower().startswith("total"):
                    out.append(Block("text", None, text, {colmap[j]: row[j] for j in colmap if j < len(row)}, 1.0, loc))
                    continue
                out.append(Block("row", None, text, {colmap[j]: row[j] for j in colmap if j < len(row) and row[j] not in (None, "")}, 1.0, loc))
        return out
