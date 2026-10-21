"""Make PDF pages look scanned: rasterize, skew/rotate, add noise, drop the text layer."""
from __future__ import annotations

import random
from io import BytesIO

import pypdfium2 as pdfium
from PIL import Image, ImageFilter

DPI = 200


def _degrade(img: Image.Image, rng: random.Random, rotate90: int) -> Image.Image:
    img = img.convert("L")
    skew = rng.uniform(-1.6, 1.6)
    img = img.rotate(skew, resample=Image.BICUBIC, expand=True, fillcolor=255)
    if rotate90:
        img = img.rotate(rotate90, expand=True)
    w, h = img.size
    px = img.load()
    # Sparse speckle noise and a faint gray cast, like a cheap office scanner.
    for _ in range(int(w * h * 0.0015)):
        x, y = rng.randrange(w), rng.randrange(h)
        px[x, y] = rng.choice((0, 60, 120))
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    img = img.point(lambda v: min(255, int(v * 0.93 + 10)))
    return img


def scanify(pdf_bytes: bytes, rng: random.Random, pages: set[int] | None = None,
            rotate: bool = False) -> tuple[bytes, list[int]]:
    """Return (new_pdf_bytes, scanned_page_indexes). Unscanned pages keep their text layer."""
    src = pdfium.PdfDocument(pdf_bytes)
    n = len(src)
    targets = set(range(n)) if pages is None else {p for p in pages if p < n}
    rotate_page = rng.choice(sorted(targets)) if rotate and targets else None
    out = pdfium.PdfDocument.new()
    for i in range(n):
        if i not in targets:
            out.import_pages(src, [i])
            continue
        page = src[i]
        w_pt, h_pt = page.get_size()
        img = page.render(scale=DPI / 72).to_pil()
        img = _degrade(img, rng, rotate90=rng.choice([90, 180, 270]) if i == rotate_page else 0)
        buf = BytesIO()
        img.save(buf, format="PDF", resolution=DPI, quality=55)
        tmp = pdfium.PdfDocument(buf.getvalue())
        out.import_pages(tmp, [0])
    res = BytesIO()
    out.save(res)
    return res.getvalue(), sorted(targets)
