"""How values get printed in documents: clean formats and the messy variants
that brokers and agency systems actually produce."""
from __future__ import annotations

import random
from datetime import date

CONSTRUCTION_LABEL = {
    "frame": "Frame", "joisted_masonry": "Joisted Masonry", "non_combustible": "Non-Combustible",
    "masonry_non_combustible": "Masonry Non-Combustible", "modified_fire_resistive": "Modified Fire Resistive",
    "fire_resistive": "Fire Resistive",
}
CONSTRUCTION_MESSY = {
    "frame": ["Wood Frame", "ISO 1", "Frame (1)"],
    "joisted_masonry": ["JM", "ISO 2", "Brick/Joisted"],
    "non_combustible": ["Non-Comb.", "ISO 3", "Metal Bldg"],
    "masonry_non_combustible": ["MNC", "ISO 4", "Masonry Non-Comb."],
    "modified_fire_resistive": ["MFR", "ISO 5", "Mod. Fire Resistive"],
    "fire_resistive": ["FR", "ISO 6", "Fire-Resistive"],
}
ROOF_LABEL = {"asphalt_shingle": "Asphalt Shingle", "metal": "Metal", "built_up": "Built-Up",
              "membrane": "Membrane (TPO)", "tile": "Tile"}
ALARM_LABEL = {"none": "None", "local": "Local", "central_station": "Central Station"}
ENTITY_LABEL = {"llc": "LLC", "corporation": "Corporation", "partnership": "Partnership",
                "sole_proprietor": "Individual", "nonprofit": "Not For Profit"}
VALUATION_LABEL = {"replacement_cost": "Replacement Cost", "actual_cash_value": "Actual Cash Value"}
FORM_LABEL = {"special": "Special", "broad": "Broad", "basic": "Basic"}


def money(v: float | None, rng: random.Random, messy: bool) -> str:
    if v is None:
        return ""
    if messy and v >= 1_000_000 and rng.random() < 0.35:
        return f"${v / 1_000_000:.2f}M".replace(".00M", "M")
    if messy and rng.random() < 0.15:
        return f"{v:.0f}"
    return f"${v:,.0f}"


def money_cents(v: float | None) -> str:
    return "" if v is None else f"${v:,.2f}"


def date_str(d: date | None, rng: random.Random, messy: bool) -> str:
    if d is None:
        return ""
    if messy:
        style = rng.randint(0, 3)
        if style == 1:
            return d.strftime("%B %-d, %Y")
        if style == 2:
            return d.isoformat()
        if style == 3:
            return d.strftime("%d-%b-%Y")
    return d.strftime("%m/%d/%Y")


def construction(v: str | None, rng: random.Random, messy: bool) -> str:
    if v is None:
        return ""
    if messy and rng.random() < 0.6:
        return rng.choice(CONSTRUCTION_MESSY[v])
    return CONSTRUCTION_LABEL[v]


def yes_no(v: bool | None, rng: random.Random, messy: bool) -> str:
    if v is None:
        return ""
    if messy and rng.random() < 0.5:
        return "Yes" if v else "No"
    return "Y" if v else "N"


def intval(v: int | None) -> str:
    return "" if v is None else str(v)


def intcomma(v: int | None) -> str:
    return "" if v is None else f"{v:,}"
