"""OCR for pages without a text layer: orientation fix, deskew, Tesseract words.

Results are cached under .cache/ocr/ keyed by file hash and page. The cache
stores the original OCR duration, so latency metrics still include OCR cost
when the cache is warm.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image

from .textlayout import Word

# One Tesseract thread per process: the eval harness parallelises across documents,
# and nested OpenMP threads oversubscribe the CPU badly.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("SUBMITIQ_CACHE", ROOT / ".cache")) / "ocr"
DPI = 300
OCR_VERSION = "v2"   # bump to invalidate the cache when this module changes


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _orientation(img: Image.Image) -> int:
    """Degrees (clockwise) Tesseract says the page must be rotated by. 0 when unsure."""
    import pytesseract
    try:
        osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT, config="--psm 0")
    except Exception:
        return 0
    if float(osd.get("orientation_conf", 0)) < 1.0:
        return 0
    return int(osd.get("rotate", 0))


def _skew_angle(img: Image.Image) -> float:
    """Projection-profile deskew: the angle whose row sums are most 'peaky'."""
    small = img.convert("L")
    scale = 1000 / max(small.size)
    small = small.resize((int(small.width * scale), int(small.height * scale)))
    best, best_score = 0.0, -1.0
    for angle in np.arange(-3.0, 3.01, 0.25):
        rot = small.rotate(float(angle), resample=Image.BILINEAR, fillcolor=255)
        ink = (np.asarray(rot) < 140).sum(axis=1).astype(float)
        score = float(np.var(ink))
        if score > best_score:
            best, best_score = float(angle), score
    return best


def ocr_page(pdf_path: Path, page_index: int, sha: str) -> tuple[list[Word], float, dict]:
    """Return (words in PDF points, mean confidence 0-1, info)."""
    key = CACHE / f"{sha[:16]}_{page_index}_{OCR_VERSION}.json"
    if key.exists():
        data = json.loads(key.read_text())
        return [Word(**w) for w in data["words"]], data["conf"], data["info"]
    if not tesseract_available():
        return [], 0.0, {"error": "tesseract not installed"}
    import pytesseract
    t0 = time.perf_counter()
    doc = pdfium.PdfDocument(str(pdf_path))
    img = doc[page_index].render(scale=DPI / 72).to_pil().convert("L")
    rotate = _orientation(img)
    if rotate:
        img = img.rotate(-rotate, expand=True, fillcolor=255)
    skew = _skew_angle(img)
    if abs(skew) > 0.1:
        img = img.rotate(skew, resample=Image.BICUBIC, expand=False, fillcolor=255)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--psm 3")
    k = 72 / DPI
    words, confs = [], []
    for i, txt in enumerate(data["text"]):
        txt = (txt or "").strip()
        conf = float(data["conf"][i])
        if not txt or conf < 0:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(Word(text=txt, x0=x * k, x1=(x + w) * k, top=y * k, bottom=(y + h) * k, conf=conf / 100))
        confs.append(conf / 100)
    mean = float(np.mean(confs)) if confs else 0.0
    info = {"rotate": rotate, "skew": round(skew, 2), "ocr_ms": round((time.perf_counter() - t0) * 1000, 1)}
    CACHE.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps({"words": [w.__dict__ for w in words], "conf": mean, "info": info}))
    return words, mean, info
