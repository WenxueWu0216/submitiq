"""Generate the synthetic submission dataset.

    python data/generate.py            # writes data/submissions/{dev,test}/SUB-xxxx/

Each submission folder contains the broker email, application PDF, one or more
loss-run PDFs, an SOV (xlsx or PDF), and ground_truth.json. The output is
deterministic for a given SEED and library versions.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.synth import docs  # noqa: E402
from data.synth.labels import AppetiteLabels  # noqa: E402
from data.synth.scan import scanify  # noqa: E402
from data.synth.truth import World, make_world  # noqa: E402
from submitiq.schema import GroundTruth, GroundTruthMeta, Submission  # noqa: E402

SEED = 20261021
N_DEV, N_TEST = 80, 40
OUT = ROOT / "data" / "submissions"


def visible_record(w: World) -> Submission:
    """Ground truth = what the documents support, after source-of-truth rules."""
    rec = w.truth.model_copy(deep=True)
    for path in w.omitted:
        if path.startswith("locations["):
            num = int(path[len("locations["):path.index("]")])
            field = path.split(".", 1)[1]
            loc = next(l for l in rec.locations if l.loc_number == num)
            setattr(loc, field, None)
        else:
            group, field = path.split(".")
            setattr(getattr(rec, group), field, None)
    for loc in rec.locations:
        if loc.loc_number > 3:  # roof type and alarm only appear on the application's first three premises
            loc.roof_type = None
            loc.alarm_type = None
    return rec


def _filename(rng: random.Random, role: str, ext: str, random_names: bool, idx: int = 0) -> str:
    if random_names:
        return rng.choice(["scan", "doc", "Attachment_", "IMG_", "file"]) + f"{rng.randint(100, 99999)}{ext}"
    base = {"application": rng.choice(["application", "ACORD_125_140", "Signed_App"]),
            "loss_run": rng.choice(["loss_run", "LossRuns", "Loss_History"]) + (f"_{idx + 1}" if idx else ""),
            "sov": rng.choice(["SOV", "statement_of_values", "Property_Schedule"])}[role]
    return base + ext


def build_one(i: int, split: str, template: str, target: str, labels: AppetiteLabels) -> dict:
    rng = random.Random(SEED * 1000 + i)
    sub_id = f"SUB-{i:04d}"
    w = make_world(rng, sub_id, template, target, labels)
    gold = visible_record(w)
    folder = OUT / split / sub_id
    folder.mkdir(parents=True, exist_ok=True)
    doc_types: dict[str, str] = {}

    (folder / "email.txt").write_text(docs.render_email(w, gold, rng))
    doc_types["email.txt"] = "email"

    render_app = {"A": docs.render_application_a, "B": docs.render_application_b, "C": docs.render_application_c}[template]
    app = render_app(w, gold, rng)
    if "application" in w.scanned:
        app, _ = scanify(app, rng, pages={0, 2} if rng.random() < 0.5 else None, rotate="application" in w.rotated)
    name = _filename(rng, "application", ".pdf", w.random_filenames)
    (folder / name).write_bytes(app)
    doc_types[name] = "application"

    for k, (carrier, years) in enumerate(w.loss_run_groups):
        lr = docs.render_loss_run(w, gold, carrier, years, rng)
        if "loss_run" in w.scanned:
            lr, _ = scanify(lr, rng, rotate="loss_run" in w.rotated)
        name = _filename(rng, "loss_run", ".pdf", w.random_filenames, k)
        (folder / name).write_bytes(lr)
        doc_types[name] = "loss_run"

    if w.sov_format == "xlsx":
        sov = docs.render_sov_xlsx(w, gold, rng)
        name = _filename(rng, "sov", ".xlsx", w.random_filenames)
    else:
        sov = docs.render_sov_pdf(w, gold, rng)
        if "sov" in w.scanned:
            sov, _ = scanify(sov, rng, rotate="sov" in w.rotated)
        name = _filename(rng, "sov", ".pdf", w.random_filenames)
    (folder / name).write_bytes(sov)
    doc_types[name] = "sov"

    decision, reasons = labels.label(gold)
    gt = GroundTruth(record=gold, meta=GroundTruthMeta(
        split=split, template=template, doc_types=doc_types, expected_conflicts=sorted(set(w.expected_conflicts)),
        expected_decision=decision, expected_reasons=reasons, mess=sorted(w.mess)))
    (folder / "ground_truth.json").write_text(gt.model_dump_json(indent=2))
    return {"id": sub_id, "split": split, "template": template, "target": target, "decision": decision,
            "mess": sorted(w.mess)}


def plan(rng: random.Random) -> list[tuple[str, str, str]]:
    """(split, template, target decision) for each submission."""
    targets = ["accept"] * 50 + ["refer"] * 45 + ["decline"] * 25
    rng.shuffle(targets)
    dev_templates = ["A"] * 40 + ["B"] * 40
    test_templates = ["A"] * 15 + ["B"] * 15 + ["C"] * 10   # template C is held out from dev
    rng.shuffle(dev_templates)
    rng.shuffle(test_templates)
    out = [("dev", t, targets[k]) for k, t in enumerate(dev_templates)]
    out += [("test", t, targets[N_DEV + k]) for k, t in enumerate(test_templates)]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, default=None, help="generate a single submission index (debugging)")
    args = ap.parse_args()
    labels = AppetiteLabels.load()
    if args.only is None and OUT.exists():
        shutil.rmtree(OUT)
    rows = []
    for i, (split, template, target) in enumerate(plan(random.Random(SEED)), start=1):
        if args.only is not None and i != args.only:
            continue
        rows.append(build_one(i, split, template, target, labels))
    if args.only is None:
        (OUT / "manifest.json").write_text(json.dumps(rows, indent=1))
    by = {}
    for r in rows:
        by[r["decision"]] = by.get(r["decision"], 0) + 1
    print(f"generated {len(rows)} submissions -> {OUT}  decisions={by}")


if __name__ == "__main__":
    main()
