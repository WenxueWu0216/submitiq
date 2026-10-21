"""SubmitIQ HTTP service and review UI.

    uvicorn service.app:app --port 8000      (or: make serve)

API
    POST /submissions                  multipart upload of a package (files=...)
    GET  /submissions/{id}             full result: record, provenance, decision, summary
    GET  /review-queue                 submissions waiting for a human, most flagged first
    POST /submissions/{id}/review      {"reviewer", "action": "approve"|"correct", "corrections": [...]}
    GET  /submissions/{id}/eval-case   reviewed record as a ground-truth eval case
    GET  /corrections                  every stored correction
UI
    GET  /                             review queue
    GET  /ui/submissions/{id}          field-by-field review page (HTMX)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from submitiq.fields import GROUPS, as_jsonable, flatten, spec
from submitiq.pipeline import build_pipeline
from submitiq.result import PipelineResult

from .db import CorrectionRow, SubmissionRow, make_session_factory
from .review import Correction, InvalidCorrection, apply_corrections, approve, to_eval_case

ROOT = Path(__file__).resolve().parents[1]
STORAGE = Path(os.environ.get("SUBMITIQ_STORAGE", ROOT / ".cache" / "uploads"))
SessionLocal = make_session_factory()
templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))
app = FastAPI(title="SubmitIQ", version="0.1.0")


def get_db():
    with SessionLocal() as db:
        yield db


# ---------------------------------------------------------------------------- core operations

def ingest(pkg_dir: Path, db: Session, sub_id: str | None = None) -> SubmissionRow:
    """Run the final pipeline on a package directory and store the result."""
    sub_id = sub_id or pkg_dir.name
    pipe = build_pipeline("final", backend=os.environ.get("SUBMITIQ_BACKEND", "replay"))
    try:
        res = pipe.run(pkg_dir)
        status = "needs_review" if res.needs_review else "auto_cleared"
    except Exception as exc:  # never lose a submission: store it as failed and surface it
        from submitiq.schema import Submission
        res = PipelineResult(submission_id=sub_id, pipeline="final", record=Submission(submission_id=sub_id),
                             needs_review=True, errors=[repr(exc)], review_reasons=[f"pipeline error: {exc}"])
        status = "failed"
    res.submission_id = sub_id
    data = json.loads(res.model_dump_json())
    row = db.get(SubmissionRow, sub_id)
    if row is None:
        row = SubmissionRow(id=sub_id, status=status, package_dir=str(pkg_dir), result=data, original_result=data)
        db.add(row)
    else:
        row.status, row.result, row.original_result, row.package_dir = status, data, data, str(pkg_dir)
    db.commit()
    return row


def _result(row: SubmissionRow) -> PipelineResult:
    return PipelineResult.model_validate(row.result)


def _store_review(row: SubmissionRow, res: PipelineResult, applied, reviewer: str, db: Session, approved: bool) -> None:
    for a in applied:
        db.add(CorrectionRow(submission_id=row.id, field_path=a.path, old_value=json.dumps(a.old_value),
                             new_value=json.dumps(a.new_value), field_status=a.field_status, extractor=a.extractor,
                             reviewer=reviewer, comment=a.comment))
    row.result = json.loads(res.model_dump_json())
    row.status = "approved" if approved else ("needs_review" if res.needs_review else "auto_cleared")
    row.reviewed_by = reviewer
    db.commit()


# ---------------------------------------------------------------------------- JSON API

class CorrectionIn(BaseModel):
    path: str
    value: Any = None
    comment: str | None = None


class ReviewIn(BaseModel):
    reviewer: str
    action: str = "correct"          # correct | approve
    corrections: list[CorrectionIn] = []


@app.post("/submissions")
async def create_submission(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    sub_id = f"UP-{uuid.uuid4().hex[:10].upper()}"
    folder = STORAGE / sub_id
    folder.mkdir(parents=True, exist_ok=True)
    for f in files:
        name = Path(f.filename or "file").name            # no path traversal
        if name == "ground_truth.json":
            continue
        with open(folder / name, "wb") as out:
            shutil.copyfileobj(f.file, out)
    row = ingest(folder, db, sub_id)
    res = _result(row)
    return {"id": row.id, "status": row.status, "decision": res.decision.outcome,
            "needs_review": res.needs_review, "flagged_fields": len(res.flagged_paths())}


@app.get("/submissions/{sub_id}")
def get_submission(sub_id: str, db: Session = Depends(get_db)):
    row = db.get(SubmissionRow, sub_id)
    if row is None:
        raise HTTPException(404, "unknown submission")
    return {"id": row.id, "status": row.status, "reviewed_by": row.reviewed_by, "result": row.result}


@app.get("/review-queue")
def review_queue(db: Session = Depends(get_db)):
    rows = db.scalars(select(SubmissionRow).where(SubmissionRow.status.in_(["needs_review", "failed"]))).all()
    items = []
    for r in rows:
        res = _result(r)
        items.append({"id": r.id, "status": r.status, "insured": res.record.insured.named_insured,
                      "decision": res.decision.outcome, "flagged_fields": len(res.flagged_paths()),
                      "reasons": res.review_reasons[:5], "created_at": r.created_at.isoformat()})
    return sorted(items, key=lambda i: -i["flagged_fields"])


@app.post("/submissions/{sub_id}/review")
def review(sub_id: str, body: ReviewIn, db: Session = Depends(get_db)):
    row = db.get(SubmissionRow, sub_id)
    if row is None:
        raise HTTPException(404, "unknown submission")
    try:
        res, applied = apply_corrections(_result(row), [Correction(c.path, c.value, c.comment) for c in body.corrections],
                                         body.reviewer)
    except InvalidCorrection as exc:
        raise HTTPException(422, str(exc))
    if body.action == "approve":
        res = approve(res, body.reviewer)
    _store_review(row, res, applied, body.reviewer, db, approved=body.action == "approve")
    return {"id": row.id, "status": row.status, "decision": res.decision.outcome, "corrections": len(applied)}


@app.get("/submissions/{sub_id}/eval-case")
def eval_case(sub_id: str, db: Session = Depends(get_db)):
    row = db.get(SubmissionRow, sub_id)
    if row is None or row.status != "approved":
        raise HTTPException(409, "only approved submissions become eval cases")
    return json.loads(to_eval_case(_result(row)).model_dump_json())


@app.get("/corrections")
def corrections(db: Session = Depends(get_db)):
    rows = db.scalars(select(CorrectionRow).order_by(CorrectionRow.created_at)).all()
    return [{"submission_id": r.submission_id, "field": r.field_path, "old": json.loads(r.old_value or "null"),
             "new": json.loads(r.new_value or "null"), "field_status": r.field_status, "extractor": r.extractor,
             "reviewer": r.reviewer, "comment": r.comment, "at": r.created_at.isoformat()} for r in rows]


@app.get("/submissions/{sub_id}/documents/{name}")
def document(sub_id: str, name: str, db: Session = Depends(get_db)):
    row = db.get(SubmissionRow, sub_id)
    path = Path(row.package_dir) / Path(name).name if row else None
    if path is None or not path.exists() or path.name == "ground_truth.json":
        raise HTTPException(404, "no such document")
    return FileResponse(path)


# ---------------------------------------------------------------------------- HTML UI

def _render_md(text: str | None) -> Markup:
    """Tiny markdown subset for the summary; field citations become highlighted links."""
    out = []
    for line in (text or "").splitlines():
        h = escape(line)
        h = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(h))
        h = re.sub(r"`(.+?)`", r"<code>\1</code>", h)
        h = re.sub(r"\[([a-z_]+(?:\[[^\]]+\])?(?:\.[a-z_]+)+)\]", r'<a class="cite" href="#f-\1">\1</a>', h)
        if line.startswith("## "):
            out.append(f"<h3>{h[3:]}</h3>")
        elif line.startswith("- "):
            out.append(f"<li>{h[2:]}</li>")
        elif line.strip():
            out.append(f"<p>{h}</p>")
    return Markup("\n".join(out))


def _rows(res: PipelineResult) -> list[dict]:
    values = flatten(res.record)
    paths = set(values) | set(res.provenance)
    rows = []
    for p in paths:
        fp = res.provenance.get(p)
        v = values.get(p)
        if v is None and fp is None:
            continue
        cite = fp.citations[0] if fp and fp.citations else None
        rows.append({"path": p, "group": spec(p).group, "critical": spec(p).critical,
                     "value": "" if v is None else as_jsonable(v), "confidence": fp.confidence if fp else None,
                     "status": fp.status if fp else "ok", "extractor": fp.extractor if fp else None,
                     "doc": cite.doc if cite else None, "page": cite.page if cite else None,
                     "locator": cite.locator if cite else None, "snippet": cite.snippet if cite else None,
                     "reasons": fp.reasons if fp else [],
                     "alternatives": [(a.value, a.citation.doc, a.extractor) for a in (fp.alternatives if fp else [])][:3]})
    order = {g: i for i, g in enumerate(GROUPS)}
    return sorted(rows, key=lambda r: (r["status"] == "ok", order[r["group"]], r["path"]))


@app.get("/", response_class=HTMLResponse)
def ui_queue(request: Request, db: Session = Depends(get_db)):
    rows = db.scalars(select(SubmissionRow).order_by(SubmissionRow.updated_at.desc())).all()
    items = []
    for r in rows:
        res = _result(r)
        items.append({"id": r.id, "status": r.status, "insured": res.record.insured.named_insured or "(name not read)",
                      "decision": res.decision.outcome, "flags": len(res.flagged_paths()),
                      "tiv": res.record.totals.total_tiv, "reviewed_by": r.reviewed_by})
    items.sort(key=lambda i: (i["status"] != "needs_review", -i["flags"]))
    return templates.TemplateResponse(request, "queue.html", {"items": items})


@app.get("/ui/submissions/{sub_id}", response_class=HTMLResponse)
def ui_detail(sub_id: str, request: Request, db: Session = Depends(get_db)):
    row = db.get(SubmissionRow, sub_id)
    if row is None:
        raise HTTPException(404, "unknown submission")
    res = _result(row)
    return templates.TemplateResponse(request, "detail.html", {
        "row": row, "res": res, "rows": _rows(res), "summary": _render_md(res.summary),
        "docs": sorted(res.doc_types.items())})


@app.post("/ui/submissions/{sub_id}/fields", response_class=HTMLResponse)
def ui_correct_field(sub_id: str, request: Request, path: str = Form(...), value: str = Form(""),
                     reviewer: str = Form("underwriter"), comment: str = Form(""), db: Session = Depends(get_db)):
    row = db.get(SubmissionRow, sub_id)
    if row is None:
        raise HTTPException(404, "unknown submission")
    try:
        res, applied = apply_corrections(_result(row), [Correction(path, value, comment or None)], reviewer)
    except InvalidCorrection as exc:
        return HTMLResponse(f'<tr><td colspan="7" class="err">{escape(str(exc))}</td></tr>', status_code=422)
    _store_review(row, res, applied, reviewer, db, approved=False)
    r = next(x for x in _rows(res) if x["path"] == path)
    return templates.TemplateResponse(request, "_row.html", {"r": r, "row": row})


@app.post("/ui/submissions/{sub_id}/approve")
def ui_approve(sub_id: str, reviewer: str = Form("underwriter"), db: Session = Depends(get_db)):
    row = db.get(SubmissionRow, sub_id)
    if row is None:
        raise HTTPException(404, "unknown submission")
    _store_review(row, approve(_result(row), reviewer), [], reviewer, db, approved=True)
    return RedirectResponse("/", status_code=303)
