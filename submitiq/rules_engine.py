"""Deterministic appetite rules over rules/appetite.yaml.

The LLM never decides appetite. Each triggered rule returns a RuleHit naming the
fields it relied on, so the decision is auditable and the UI can show
"this decline depends on locations[2].construction". When one of those fields
is still flagged for review, the decision gets a caveat.
"""
from __future__ import annotations

from typing import Callable

from .fields import claim_key
from .guidelines import load_rules
from .result import Decision, FieldProvenance, RuleHit
from .schema import Location, Submission

ORDER = ["accept", "refer", "decline"]


class RulesEngine:
    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or load_rules()
        self.version = self.cfg["version"]
        c = self.cfg["classes"]
        self.accept, self.refer, self.decline = set(c["accept"]), set(c["refer"]), set(c["decline"])
        self.loc_rules: list[Callable[[Submission, Location], list[RuleHit]]] = [
            self._missing_location, self._location_tiv, self._construction_protection, self._hurricane,
            self._earthquake, self._sprinklers, self._age,
        ]

    # ------------------------------------------------------------------ account level
    def _class(self, rec: Submission) -> list[RuleHit]:
        naics = rec.insured.naics_code
        f = ["insured.naics_code"]
        if naics is None:
            return [RuleHit(rule_id="MISSING_INFO", outcome="refer", message="NAICS code missing", fields=f)]
        if naics in self.decline:
            return [RuleHit(rule_id="CLASS_PROHIBITED", outcome="decline",
                            message=f"NAICS {naics} ({self.cfg['classes']['decline'][naics]}) is prohibited", fields=f)]
        if naics in self.refer:
            return [RuleHit(rule_id="CLASS_REFER", outcome="refer",
                            message=f"NAICS {naics} ({self.cfg['classes']['refer'][naics]}) requires referral", fields=f)]
        if naics not in self.accept:
            return [RuleHit(rule_id="CLASS_UNKNOWN", outcome="refer", message=f"NAICS {naics} not in appetite guide", fields=f)]
        return []

    def _account_tiv(self, rec: Submission) -> list[RuleHit]:
        tiv = rec.totals.total_tiv
        lim = self.cfg["tiv"]["account_refer_above"]
        if tiv is not None and tiv > lim:
            return [RuleHit(rule_id="ACCOUNT_TIV", outcome="refer", message=f"account TIV ${tiv:,.0f} > ${lim:,.0f}",
                            fields=["totals.total_tiv"])]
        return []

    def _losses(self, rec: Submission) -> list[RuleHit]:
        L = self.cfg["losses"]
        hits: list[RuleHit] = []
        incurred = sum(c.incurred or 0 for c in rec.claims)
        premium = sum(y.earned_premium or 0 for y in rec.loss_years)
        lr_fields = ["totals.five_year_incurred", "totals.five_year_premium"]
        if premium > 0:
            lr = incurred / premium
            if lr > L["loss_ratio_decline_above"]:
                hits.append(RuleHit(rule_id="LOSS_RATIO", outcome="decline",
                                    message=f"5-year loss ratio {lr:.0%} > {L['loss_ratio_decline_above']:.0%}", fields=lr_fields))
            elif lr > L["loss_ratio_refer_above"]:
                hits.append(RuleHit(rule_id="LOSS_RATIO", outcome="refer",
                                    message=f"5-year loss ratio {lr:.0%} > {L['loss_ratio_refer_above']:.0%}", fields=lr_fields))
        n = len(rec.claims)
        if n >= L["claim_count_refer_at_or_above"]:
            hits.append(RuleHit(rule_id="LOSS_FREQUENCY", outcome="refer", message=f"{n} claims in 5 years",
                                fields=[f"loss_years[{y.policy_year}].claim_count" for y in rec.loss_years]))
        for c in rec.claims:
            if (c.incurred or 0) > L["large_loss_refer_above"]:
                hits.append(RuleHit(rule_id="LARGE_LOSS", outcome="refer",
                                    message=f"claim {c.claim_number} incurred ${c.incurred:,.0f} ({c.cause or 'cause n/a'})",
                                    fields=[f"claims[{claim_key(c.claim_number)}].incurred"]))
        return hits

    # ------------------------------------------------------------------ location level
    def _missing_location(self, rec: Submission, loc: Location) -> list[RuleHit]:
        miss = [f for f in self.cfg["required_fields"]["location"] if getattr(loc, f) is None]
        if miss:
            return [RuleHit(rule_id="MISSING_INFO", outcome="refer",
                            message=f"location {loc.loc_number}: missing {', '.join(miss)}",
                            fields=[f"locations[{loc.loc_number}].{f}" for f in miss])]
        return []

    def _location_tiv(self, rec: Submission, loc: Location) -> list[RuleHit]:
        t, T = loc.tiv or 0, self.cfg["tiv"]
        f = [f"locations[{loc.loc_number}].tiv"]
        if t > T["location_decline_above"]:
            return [RuleHit(rule_id="LOCATION_TIV", outcome="decline",
                            message=f"location {loc.loc_number} TIV ${t:,.0f} > ${T['location_decline_above']:,.0f}", fields=f)]
        if t > T["location_refer_above"]:
            return [RuleHit(rule_id="LOCATION_TIV", outcome="refer",
                            message=f"location {loc.loc_number} TIV ${t:,.0f} > ${T['location_refer_above']:,.0f}", fields=f)]
        return []

    def _construction_protection(self, rec: Submission, loc: Location) -> list[RuleHit]:
        cp, pc, k = self.cfg["construction_protection"], loc.protection_class, loc.loc_number
        hits = []
        if pc is None:
            return hits
        if loc.construction == "frame" and pc >= cp["decline_frame_with_pc_at_or_above"]:
            hits.append(RuleHit(rule_id="FRAME_POOR_PROTECTION", outcome="decline",
                                message=f"location {k}: frame construction with protection class {pc}",
                                fields=[f"locations[{k}].construction", f"locations[{k}].protection_class"]))
        if pc >= cp["refer_pc_at_or_above"]:
            hits.append(RuleHit(rule_id="POOR_PROTECTION", outcome="refer", message=f"location {k}: protection class {pc}",
                                fields=[f"locations[{k}].protection_class"]))
        return hits

    def _hurricane(self, rec: Submission, loc: Location) -> list[RuleHit]:
        z = self.cfg["cat_zones"]
        k = loc.loc_number
        if (loc.zip or "")[:3] not in z["hurricane_tier1_zip3"]:
            return []
        if loc.construction == "frame":
            return [RuleHit(rule_id="HURRICANE_ZONE", outcome="decline",
                            message=f"location {k}: frame building in tier-1 hurricane zone (ZIP {loc.zip})",
                            fields=[f"locations[{k}].zip", f"locations[{k}].construction"])]
        if (loc.tiv or 0) > z["hurricane_refer_location_tiv_above"]:
            return [RuleHit(rule_id="HURRICANE_ZONE", outcome="refer",
                            message=f"location {k}: TIV ${loc.tiv:,.0f} in tier-1 hurricane zone (ZIP {loc.zip})",
                            fields=[f"locations[{k}].zip", f"locations[{k}].tiv"])]
        return []

    def _earthquake(self, rec: Submission, loc: Location) -> list[RuleHit]:
        z, k = self.cfg["cat_zones"], loc.loc_number
        if ((loc.zip or "")[:3] in z["earthquake_zip3"] and loc.construction == "joisted_masonry"
                and loc.year_built is not None and loc.year_built < z["earthquake_refer_jm_built_before"]):
            return [RuleHit(rule_id="EARTHQUAKE_ZONE", outcome="refer",
                            message=f"location {k}: joisted masonry built {loc.year_built} in earthquake zone",
                            fields=[f"locations[{k}].zip", f"locations[{k}].construction", f"locations[{k}].year_built"])]
        return []

    def _sprinklers(self, rec: Submission, loc: Location) -> list[RuleHit]:
        lim, k = self.cfg["sprinklers"]["refer_unsprinklered_location_tiv_above"], loc.loc_number
        if loc.sprinklered is False and (loc.tiv or 0) > lim:
            return [RuleHit(rule_id="UNSPRINKLERED", outcome="refer",
                            message=f"location {k}: unsprinklered with TIV ${loc.tiv:,.0f}",
                            fields=[f"locations[{k}].sprinklered", f"locations[{k}].tiv"])]
        return []

    def _age(self, rec: Submission, loc: Location) -> list[RuleHit]:
        a, k = self.cfg["age"], loc.loc_number
        hits = []
        if loc.year_built is not None and loc.year_built < a["refer_year_built_before"]:
            hits.append(RuleHit(rule_id="BUILDING_AGE", outcome="refer", message=f"location {k}: built {loc.year_built}",
                                fields=[f"locations[{k}].year_built"]))
        eff = rec.policy.effective_date
        if loc.roof_year is not None and eff is not None and eff.year - loc.roof_year > a["refer_roof_age_over_years"]:
            hits.append(RuleHit(rule_id="ROOF_AGE", outcome="refer",
                                message=f"location {k}: roof {eff.year - loc.roof_year} years old at inception",
                                fields=[f"locations[{k}].roof_year", "policy.effective_date"]))
        return hits

    # ------------------------------------------------------------------ public
    def evaluate(self, rec: Submission, provenance: dict[str, FieldProvenance] | None = None) -> Decision:
        hits = self._class(rec) + self._account_tiv(rec) + self._losses(rec)
        for loc in rec.locations:
            for rule in self.loc_rules:
                hits += rule(rec, loc)
        outcome = max((h.outcome for h in hits), key=ORDER.index, default="accept")
        decision = Decision(outcome=outcome, source="rules", reasons=hits)  # type: ignore[arg-type]
        if provenance:
            flagged = {p for p, fp in provenance.items() if fp.status != "ok"}
            for h in hits:
                dep = sorted(set(h.fields) & flagged)
                if dep:
                    h.message += f" (depends on fields under review: {', '.join(dep)})"
        return decision
