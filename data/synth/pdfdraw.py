"""Small reportlab helpers: labelled form fields and paginated tables."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas


@dataclass
class Column:
    header: str
    width: float
    align: str = "left"  # left | right


class PdfDoc:
    def __init__(self, landscape_first: bool = False, font: str = "Helvetica"):
        self.buf = BytesIO()
        self.font = font
        self.bold = "Courier-Bold" if font == "Courier" else "Helvetica-Bold"
        self.size = landscape(letter) if landscape_first else letter
        self.c = canvas.Canvas(self.buf, pagesize=self.size)
        self.c.setTitle("document")
        self.y = self.size[1] - 50
        self.page_count = 1

    @property
    def width(self) -> float:
        return self.size[0]

    def new_page(self, landscape_page: bool = False) -> None:
        self.c.showPage()
        self.size = landscape(letter) if landscape_page else letter
        self.c.setPageSize(self.size)
        self.y = self.size[1] - 50
        self.page_count += 1

    def text(self, x: float, s: str, size: float = 9, bold: bool = False, dy: float | None = None) -> None:
        self.c.setFont(self.bold if bold else self.font, size)
        self.c.drawString(x, self.y, s)
        self.y -= dy if dy is not None else size + 5

    def text_at(self, x: float, y: float, s: str, size: float = 9, bold: bool = False) -> None:
        self.c.setFont(self.bold if bold else self.font, size)
        self.c.drawString(x, y, s)

    def heading(self, s: str, size: float = 11) -> None:
        self.y -= 4
        self.text(40, s, size=size, bold=True)
        self.c.setLineWidth(0.6)
        self.c.line(40, self.y + size - 1, self.width - 40, self.y + size - 1)
        self.y -= 4

    def kv_line(self, pairs: list[tuple[str, str]], xs: list[float], size: float = 9) -> None:
        """One printed line with several 'Label: value' pairs at fixed x positions."""
        for (label, value), x in zip(pairs, xs):
            self.c.setFont(self.bold, size)
            self.c.drawString(x, self.y, f"{label}:")
            lw = self.c.stringWidth(f"{label}: ", self.bold, size)
            self.c.setFont(self.font, size)
            self.c.drawString(x + lw, self.y, value)
        self.y -= size + 6

    def boxes(self, items: list[tuple[str, str]], widths: list[float], size: float = 9) -> None:
        """Label-above-value boxes (the held-out template's layout)."""
        x = 40
        h = 26
        for (label, value), w in zip(items, widths):
            self.c.setLineWidth(0.5)
            self.c.rect(x, self.y - h + 10, w, h)
            self.c.setFont(self.font, 6)
            self.c.drawString(x + 3, self.y + 2, label.upper())
            self.c.setFont(self.font, size)
            self.c.drawString(x + 3, self.y - 10, value)
            x += w
        self.y -= h + 4

    def ensure(self, needed: float, landscape_page: bool = False) -> bool:
        if self.y - needed < 50:
            self.new_page(landscape_page)
            return True
        return False

    def table(self, cols: list[Column], rows: list[list[str]], size: float = 7.5, row_h: float = 12,
              repeat_header: bool = True, landscape_pages: bool = False, max_rows_first_page: int | None = None,
              x0: float = 36) -> int:
        """Draw a table, breaking across pages. Returns how many page breaks happened."""
        breaks = 0

        def header() -> None:
            x = x0
            for col in cols:
                self.c.setFont(self.bold, self._fit(col.header, col.width, size, bold=True))
                self.c.drawString(x + 2, self.y, col.header)
                x += col.width
            self.c.setLineWidth(0.4)
            self.c.line(x0, self.y - 3, x, self.y - 3)
            self.y -= row_h

        header()
        drawn_on_page = 0
        for row in rows:
            limit_hit = max_rows_first_page is not None and breaks == 0 and drawn_on_page >= max_rows_first_page
            if self.y < 60 or limit_hit:
                self.new_page(landscape_pages)
                breaks += 1
                drawn_on_page = 0
                if repeat_header:
                    header()
            x = x0
            for col, val in zip(cols, row):
                self.c.setFont(self.font, self._fit(val, col.width, size))
                if col.align == "right":
                    self.c.drawRightString(x + col.width - 4, self.y, val)
                else:
                    self.c.drawString(x + 2, self.y, val)
                x += col.width
            self.y -= row_h
            drawn_on_page += 1
        return breaks

    def _fit(self, s: str, width: float, size: float, bold: bool = False) -> float:
        """Shrink the font so a cell never runs into the next column."""
        font = self.bold if bold else self.font
        while size > 4.5 and self.c.stringWidth(s, font, size) > width - 5:
            size -= 0.25
        return size

    def finish(self) -> bytes:
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue()
