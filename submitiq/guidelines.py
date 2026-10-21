"""Load rules/appetite.yaml and render it as plain text for prompts."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "appetite.yaml"


@lru_cache(maxsize=1)
def load_rules(path: str = str(RULES_PATH)) -> dict:
    return yaml.safe_load(Path(path).read_text())


def rules_text() -> str:
    c = load_rules()
    cls = c["classes"]
    fmt = lambda d: ", ".join(f"{k} ({v})" for k, v in d.items())
    return "\n".join([
        f"Appetite guidelines version {c['version']}. Most severe outcome wins: decline > refer > accept.",
        f"- Accept classes (NAICS): {fmt(cls['accept'])}",
        f"- Refer classes: {fmt(cls['refer'])}. Any other NAICS: refer.",
        f"- Prohibited classes (decline): {fmt(cls['decline'])}",
        f"- Location TIV > ${c['tiv']['location_refer_above']:,}: refer; > ${c['tiv']['location_decline_above']:,}: decline. "
        f"Account TIV > ${c['tiv']['account_refer_above']:,}: refer.",
        f"- 5-year loss ratio (incurred / earned premium) > {c['losses']['loss_ratio_refer_above']:.0%}: refer; "
        f"> {c['losses']['loss_ratio_decline_above']:.0%}: decline. {c['losses']['claim_count_refer_at_or_above']}+ claims: refer. "
        f"Any claim incurred > ${c['losses']['large_loss_refer_above']:,}: refer.",
        f"- Frame construction with protection class >= {c['construction_protection']['decline_frame_with_pc_at_or_above']}: decline. "
        f"Protection class {c['construction_protection']['refer_pc_at_or_above']}: refer.",
        f"- Hurricane zone (ZIP prefixes {', '.join(c['cat_zones']['hurricane_tier1_zip3'])}): frame -> decline; "
        f"location TIV > ${c['cat_zones']['hurricane_refer_location_tiv_above']:,} -> refer.",
        f"- Earthquake zone (ZIP prefixes {', '.join(c['cat_zones']['earthquake_zip3'])}): joisted masonry built before "
        f"{c['cat_zones']['earthquake_refer_jm_built_before']} -> refer.",
        f"- Unsprinklered location with TIV > ${c['sprinklers']['refer_unsprinklered_location_tiv_above']:,}: refer.",
        f"- Year built before {c['age']['refer_year_built_before']}: refer. Roof older than {c['age']['refer_roof_age_over_years']} years "
        f"at the effective date: refer.",
        f"- Missing NAICS code, or any location missing construction, year built, protection class or TIV: refer.",
    ])
