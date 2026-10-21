"""Load some dataset packages into the service database so the review UI has content.

    python scripts/seed_demo.py [--n 12]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service.app import SessionLocal, ingest  # noqa: E402

DEMO = ["SUB-0003", "SUB-0016", "SUB-0025", "SUB-0038", "SUB-0059", "SUB-0082", "SUB-0010", "SUB-0053",
        "SUB-0071", "SUB-0007", "SUB-0104", "SUB-0118"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=len(DEMO))
    args = ap.parse_args()
    with SessionLocal() as db:
        for sid in DEMO[: args.n]:
            pkg = next((ROOT / "data" / "submissions").glob(f"*/{sid}"))
            row = ingest(pkg, db)
            print(f"{row.id:10} {row.status:13} {row.result['decision']['outcome']}")


if __name__ == "__main__":
    main()
