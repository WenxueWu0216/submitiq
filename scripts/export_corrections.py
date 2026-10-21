"""Turn approved, human-reviewed submissions into new eval cases.

    python scripts/export_corrections.py            # writes data/reviewed/<id>/ (package copy + ground_truth.json)
    python -m evals.run --pipeline final --split reviewed

Each reviewed package keeps the original documents, and the reviewer's corrected
record becomes its ground truth. The eval harness picks up the 'reviewed' split,
so every correction an underwriter makes becomes a regression test.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from service.app import SessionLocal, _result  # noqa: E402
from service.db import CorrectionRow, SubmissionRow  # noqa: E402
from service.review import to_eval_case  # noqa: E402

OUT = ROOT / "data" / "reviewed"


def main() -> None:
    n = 0
    with SessionLocal() as db:
        for row in db.scalars(select(SubmissionRow).where(SubmissionRow.status == "approved")):
            dest = OUT / row.id
            dest.mkdir(parents=True, exist_ok=True)
            for f in Path(row.package_dir).iterdir():
                if f.is_file() and f.name != "ground_truth.json":
                    shutil.copy2(f, dest / f.name)
            (dest / "ground_truth.json").write_text(to_eval_case(_result(row)).model_dump_json(indent=2))
            k = len(db.scalars(select(CorrectionRow).where(CorrectionRow.submission_id == row.id)).all())
            print(f"{row.id}: {k} correction(s) -> {dest.relative_to(ROOT)}")
            n += 1
    print(f"exported {n} reviewed submission(s)")


if __name__ == "__main__":
    main()
