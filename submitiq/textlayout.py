"""Words with positions, grouped into lines. Same representation for text-layer and OCR pages."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    conf: float = 1.0

    @property
    def yc(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Line:
    words: list[Word]

    @property
    def top(self) -> float:
        return min(w.top for w in self.words)

    @property
    def yc(self) -> float:
        return median(w.yc for w in self.words)

    def text(self, gap: float = 9.0) -> str:
        """Join words; a wide horizontal gap becomes three spaces (keeps columns apart)."""
        out = []
        prev = None
        for w in self.words:
            if prev is not None:
                out.append("   " if w.x0 - prev.x1 > gap else " ")
            out.append(w.text)
            prev = w
        return "".join(out)

    @property
    def conf(self) -> float:
        return sum(w.conf for w in self.words) / len(self.words)


def group_lines(words: list[Word]) -> list[Line]:
    if not words:
        return []
    heights = [w.bottom - w.top for w in words if w.bottom > w.top]
    tol = 0.55 * (median(heights) if heights else 8.0)
    lines: list[list[Word]] = []
    for w in sorted(words, key=lambda w: (w.yc, w.x0)):
        if lines and abs(median(x.yc for x in lines[-1]) - w.yc) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [Line(sorted(ws, key=lambda w: w.x0)) for ws in lines]
