"""Table extraction interface.

An extractor turns a document into a reading-order stream of blocks:
  header  a recognised table header (column field names)
  row     one table row, cells keyed by field name
  text    any other line (period headings, totals, notes)
Domain parsers (sov.py, loss_run.py) consume the stream. Backends:
  local     word positions from pdfplumber/Tesseract, vocabulary-driven headers (default)
  textract  Amazon Textract AnalyzeDocument TABLES (SUBMITIQ_TABLES=textract)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..documents import Document


@dataclass
class Block:
    kind: str                           # header | row | text
    page: int | None
    text: str
    cells: dict[str, Any] = field(default_factory=dict)
    conf: float = 1.0
    locator: str | None = None          # "page 2 line 14", "SOV!R7"


class TableExtractor(Protocol):
    name: str

    def blocks(self, doc: Document, vocabulary: dict[str, list[str]]) -> list[Block]: ...


def get_table_extractor(name: str | None = None) -> TableExtractor:
    name = name or os.environ.get("SUBMITIQ_TABLES", "local")
    if name == "local":
        from .local import LocalTableExtractor
        return LocalTableExtractor()
    if name == "textract":
        from .textract import TextractTableExtractor
        return TextractTableExtractor()
    raise ValueError(f"unknown table extractor {name!r}")
