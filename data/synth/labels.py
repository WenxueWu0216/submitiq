"""Expected appetite decision for a ground-truth record.

This is written separately from submitiq/rules_engine.py on purpose. Both read
the same thresholds from rules/appetite.yaml, but the logic is implemented
twice, and tests/test_rules_engine.py checks that the two agree on every
ground-truth record. A bug in one of them then shows up as a disagreement
instead of hiding inside a circular label.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from submitiq.schema import Submission

RULES_PATH = Path(__file__).resolve().parents[2] / "rules" / "appetite.yaml"


@dataclass
class AppetiteLabels:
    cfg: dict

    @classmethod
    def load(cls, path: Path = RULES_PATH) -> "AppetiteLabels":
        return cls(yaml.safe_load(path.read_text()))

    @property
    def accept_classes(self) -> set[str]:
        return set(self.cfg["classes"]["accept"])

    @property
    def refer_classes(self) -> set[str]:
        return set(self.cfg["classes"]["refer"])

    @property
    def decline_classes(self) -> set[str]:
        return set(self.cfg["classes"]["decline"])

    @property
    def hurricane_zip3(self) -> set[str]:
        return set(self.cfg["cat_zones"]["hurricane_tier1_zip3"])

    @property
    def quake_zip3(self) -> set[str]:
        return set(self.cfg["cat_zones"]["earthquake_zip3"])

    def label(self, rec: Submission) -> tuple[str, list[str]]:
        c = self.cfg
        hits: dict[str, str] = {}

        def hit(rule: str, outcome: str) -> None:
            order = c["outcome_order"]
            if rule not in hits or order.index(outcome) > order.index(hits[rule]):
                hits[rule] = outcome

        naics = rec.insured.naics_code
        if naics is None:
            hit("MISSING_INFO", "refer")
        elif naics in self.decline_classes:
            hit("CLASS_PROHIBITED", "decline")
        elif naics in self.refer_classes:
            hit("CLASS_REFER", "refer")
        elif naics not in self.accept_classes:
            hit("CLASS_UNKNOWN", "refer")

        eff_year = rec.policy.effective_date.year if rec.policy.effective_date else None
        for loc in rec.locations:
            for f in c["required_fields"]["location"]:
                if getattr(loc, f) is None:
                    hit("MISSING_INFO", "refer")
            tiv = loc.tiv or 0
            if tiv > c["tiv"]["location_decline_above"]:
                hit("LOCATION_TIV", "decline")
            elif tiv > c["tiv"]["location_refer_above"]:
                hit("LOCATION_TIV", "refer")
            pc = loc.protection_class
            if loc.construction == "frame" and pc is not None and pc >= c["construction_protection"]["decline_frame_with_pc_at_or_above"]:
                hit("FRAME_POOR_PROTECTION", "decline")
            if pc is not None and pc >= c["construction_protection"]["refer_pc_at_or_above"]:
                hit("POOR_PROTECTION", "refer")
            z3 = (loc.zip or "")[:3]
            if z3 in self.hurricane_zip3:
                if loc.construction == "frame":
                    hit("HURRICANE_ZONE", "decline")
                elif tiv > c["cat_zones"]["hurricane_refer_location_tiv_above"]:
                    hit("HURRICANE_ZONE", "refer")
            if z3 in self.quake_zip3 and loc.construction == "joisted_masonry" and loc.year_built is not None \
                    and loc.year_built < c["cat_zones"]["earthquake_refer_jm_built_before"]:
                hit("EARTHQUAKE_ZONE", "refer")
            if loc.sprinklered is False and tiv > c["sprinklers"]["refer_unsprinklered_location_tiv_above"]:
                hit("UNSPRINKLERED", "refer")
            if loc.year_built is not None and loc.year_built < c["age"]["refer_year_built_before"]:
                hit("BUILDING_AGE", "refer")
            if loc.roof_year is not None and eff_year is not None \
                    and eff_year - loc.roof_year > c["age"]["refer_roof_age_over_years"]:
                hit("ROOF_AGE", "refer")

        total_tiv = rec.totals.total_tiv or 0
        if total_tiv > c["tiv"]["account_refer_above"]:
            hit("ACCOUNT_TIV", "refer")

        incurred = sum(cl.incurred or 0 for cl in rec.claims)
        premium = sum(ly.earned_premium or 0 for ly in rec.loss_years)
        if premium > 0:
            lr = incurred / premium
            if lr > c["losses"]["loss_ratio_decline_above"]:
                hit("LOSS_RATIO", "decline")
            elif lr > c["losses"]["loss_ratio_refer_above"]:
                hit("LOSS_RATIO", "refer")
        if len(rec.claims) >= c["losses"]["claim_count_refer_at_or_above"]:
            hit("LOSS_FREQUENCY", "refer")
        if any((cl.incurred or 0) > c["losses"]["large_loss_refer_above"] for cl in rec.claims):
            hit("LARGE_LOSS", "refer")

        if not hits:
            return "accept", []
        order = c["outcome_order"]
        decision = max(hits.values(), key=order.index)
        return decision, sorted(hits)
