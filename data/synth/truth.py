"""Generate the underlying facts of one synthetic submission.

`make_world` returns the true facts (a Submission) plus the "mess plan": how
each document will deviate from the truth (stale TIV, name variants, missing
fields, scans). The ground truth written to disk is the *document-visible*
truth: anything deliberately left out of every document is null, and
conflicts are resolved by the source-of-truth rules in
docs/underwriting_workflow.md section 5.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from submitiq.schema import (
    Address, Broker, Claim, Coverage, Insured, Location, LossYear, PolicyInfo,
    Submission, Totals,
)

from . import names
from .labels import AppetiteLabels

CONSTRUCTIONS = ["frame", "joisted_masonry", "non_combustible", "masonry_non_combustible",
                 "modified_fire_resistive", "fire_resistive"]
CONSTRUCTION_W = [0.20, 0.25, 0.20, 0.20, 0.10, 0.05]


@dataclass
class World:
    truth: Submission
    template: str
    target: str
    mess: list[str] = field(default_factory=list)
    omitted: set[str] = field(default_factory=set)        # paths blanked in every document
    name_variants: dict[str, str] = field(default_factory=dict)  # doc role -> insured name as printed
    app_stated_tiv: float | None = None                   # TIV printed on the application
    app_year_built: dict[int, int] = field(default_factory=dict)  # loc -> year printed on application
    email_effective_date: date | None = None
    loss_run_groups: list[tuple[str, list[int]]] = field(default_factory=list)  # (carrier, years)
    messy_formats: bool = False
    expected_conflicts: list[str] = field(default_factory=list)
    scanned: set[str] = field(default_factory=set)        # doc roles with scanned pages
    rotated: set[str] = field(default_factory=set)
    sov_format: str = "xlsx"
    random_filenames: bool = False
    mentions_tiv_in_email: bool = False


def _money(rng: random.Random, lo: float, hi: float, step: int = 5000) -> float:
    return float(round(rng.uniform(lo, hi) / step) * step)


def _street(rng: random.Random) -> str:
    suffix = rng.choice(names.STREET_SUFFIX)[0]
    return f"{rng.randint(10, 9899)} {rng.choice(names.STREET_NAMES)} {suffix}"


def _zip(rng: random.Random, zip3s: list[str]) -> str:
    return rng.choice(zip3s) + f"{rng.randint(1, 99):02d}"


def _person(rng: random.Random) -> tuple[str, str]:
    first, last = rng.choice(names.FIRST_NAMES), rng.choice(names.LAST_NAMES)
    return first, last


def _phone(rng: random.Random) -> str:
    return f"({rng.randint(201, 989)}) {rng.randint(200, 989)}-{rng.randint(1000, 9999)}"


def _pick_class(rng: random.Random, target: str, labels: AppetiteLabels) -> str:
    if target == "decline" and rng.random() < 0.45:
        return rng.choice(sorted(labels.decline_classes))
    if target == "refer" and rng.random() < 0.30:
        return rng.choice(sorted(labels.refer_classes))
    return rng.choice(sorted(labels.accept_classes))


def _location(rng: random.Random, n: int, eff: date, city_pool: list, big: bool = False) -> Location:
    city, state, zip3s = rng.choice(city_pool)
    construction = rng.choices(CONSTRUCTIONS, CONSTRUCTION_W)[0]
    year_built = rng.randint(1955, 2021)
    stories = rng.randint(1, 3) if construction in ("frame", "joisted_masonry") else rng.randint(1, 6)
    if construction == "fire_resistive":
        stories = rng.randint(4, 14)
    building = _money(rng, 4_000_000, 18_000_000) if big else _money(rng, 350_000, 7_500_000)
    contents = _money(rng, 0.1 * building, 0.6 * building)
    bi = _money(rng, 0, 0.25 * building) if rng.random() < 0.8 else 0.0
    sprinklered = rng.random() < 0.55
    sq_ft = int(round(building / rng.uniform(120, 260) / 100) * 100)
    return Location(
        loc_number=n, street=_street(rng), city=city, state=state, zip=_zip(rng, zip3s),
        construction=construction, year_built=year_built, stories=stories, square_feet=max(sq_ft, 800),
        sprinklered=sprinklered, sprinkler_pct=(100 if rng.random() < 0.8 else rng.choice([50, 60, 75, 90])) if sprinklered else 0,
        protection_class=rng.choices(range(1, 9), [3, 6, 10, 12, 12, 10, 6, 4])[0],
        roof_type=rng.choice(["asphalt_shingle", "metal", "built_up", "membrane", "tile"]),
        roof_year=rng.randint(max(year_built, eff.year - 20), eff.year - 1),
        alarm_type=rng.choices(["none", "local", "central_station"], [0.2, 0.3, 0.5])[0],
        building_value=building, contents_value=contents, bi_value=bi, tiv=building + contents + bi,
    )


def _claim_number(rng: random.Random, carrier_code: str, year: int) -> str:
    style = rng.randint(0, 2)
    if style == 0:
        return f"{carrier_code}-{year}-{rng.randint(1, 99999):05d}"
    if style == 1:
        return f"{str(year)[2:]}{carrier_code[0]}{rng.randint(100000, 999999)}"
    return f"CL{rng.randint(1000000, 9999999)}"


def _losses(rng: random.Random, eff: date, tiv: float, carriers: list[tuple[str, list[int]]],
            target_lr: float, n_claims: int, large: bool) -> tuple[list[Claim], list[LossYear]]:
    years = sorted(y for _, ys in carriers for y in ys)
    rate = rng.uniform(0.12, 0.30) / 100.0
    premiums = {y: float(round(tiv * rate * (0.88 + 0.03 * i) / 10) * 10) for i, y in enumerate(years)}
    budget = target_lr * sum(premiums.values())
    weights = [rng.random() + 0.2 for _ in range(n_claims)]
    amounts = [max(800.0, round(budget * w / sum(weights), -1)) for w in weights] if n_claims else []
    if large and amounts:
        amounts[0] = max(amounts[0], _money(rng, 260_000, 600_000))
    if not large:
        amounts = [min(a, 240_000.0) for a in amounts]
    claims: list[Claim] = []
    code_by_year = {}
    for (carrier, ys) in carriers:
        code = next(c for n, c in names.CARRIERS if n == carrier)
        for y in ys:
            code_by_year[y] = code
    for amt in amounts:
        y = rng.choice(years)
        start = date(y, eff.month, min(eff.day, 28))
        dol = start + timedelta(days=rng.randint(5, 360))
        recent = (eff - dol).days < 540
        status = "open" if recent and rng.random() < 0.5 else "closed"
        reserve = round(amt * rng.uniform(0.2, 0.7), -1) if status == "open" else 0.0
        paid = round(amt - reserve, 2)
        claims.append(Claim(
            claim_number=_claim_number(rng, code_by_year[y], dol.year), policy_year=y,
            date_of_loss=dol, cause=rng.choice(names.LOSS_CAUSES), status=status,
            paid=paid, reserve=reserve, incurred=round(paid + reserve, 2),
        ))
    claims.sort(key=lambda c: c.date_of_loss)
    loss_years = []
    for carrier, ys in carriers:
        for y in ys:
            cs = [c for c in claims if c.policy_year == y]
            loss_years.append(LossYear(policy_year=y, carrier=carrier, earned_premium=premiums[y],
                                       claim_count=len(cs), total_incurred=round(sum(c.incurred for c in cs), 2)))
    loss_years.sort(key=lambda ly: ly.policy_year)
    return claims, loss_years


def _company_name(rng: random.Random, naics: str, entity: str) -> str:
    stem = rng.choice(names.NAME_STEMS)
    noun = rng.choice(names.CLASS_PROFILES[naics][0])
    suffix = rng.choice(names.LEGAL_SUFFIX[entity])
    return f"{stem} {noun} {suffix}".strip()


def make_world(rng: random.Random, sub_id: str, template: str, target: str,
               labels: AppetiteLabels) -> World:
    eff = date(2026, 11, 1) + timedelta(days=rng.randint(0, 150))
    eff = eff.replace(day=1 if rng.random() < 0.7 else 15)
    naics = _pick_class(rng, target, labels)
    entity = rng.choices(["llc", "corporation", "partnership", "sole_proprietor", "nonprofit"],
                         [0.5, 0.35, 0.07, 0.05, 0.03])[0]
    if naics in ("531110",) and rng.random() < 0.2:
        entity = "nonprofit"
    name = _company_name(rng, naics, entity)
    n_locs = rng.choices([1, 2, 3, 4, 5, 6, 8, 10, 12], [30, 20, 15, 9, 7, 6, 5, 4, 4])[0]

    city_pool = names.SAFE_CITIES if target == "accept" else names.CITIES
    big = target != "accept" and rng.random() < 0.15
    locs = [_location(rng, i + 1, eff, city_pool, big=big and i == 0) for i in range(n_locs)]
    for loc in locs:
        loc.occupancy = names.CLASS_PROFILES[naics][2]

    carrier_names = [c[0] for c in names.CARRIERS]
    prior = rng.choice(carrier_names)
    years = [eff.year - k for k in range(5, 0, -1)]
    if rng.random() < 0.2:
        older = rng.choice([c for c in carrier_names if c != prior])
        cut = rng.randint(1, 3)
        groups = [(older, years[:cut]), (prior, years[cut:])]
    else:
        groups = [(prior, years)]

    tiv_total = sum(loc.tiv for loc in locs)
    lr = rng.uniform(0.05, 0.40)
    n_claims = rng.choices([0, 1, 2, 3], [25, 35, 25, 15])[0]
    large = False
    world_mess: list[str] = []

    # Inject appetite triggers for refer/decline targets.
    if target in ("refer", "decline") and naics in labels.accept_classes:
        triggers_refer = ["loss_ratio", "frequency", "large_loss", "pc10", "old_building", "roof_age",
                          "unsprinklered_big", "hurricane_big", "quake_jm", "loc_tiv_refer"]
        triggers_decline = ["loss_ratio_bad", "frame_pc", "hurricane_frame", "loc_tiv_decline"]
        trig = rng.choice(triggers_decline if target == "decline" else triggers_refer)
        world_mess.append(f"trigger:{trig}")
        loc = locs[0]
        if trig == "loss_ratio":
            lr, n_claims = rng.uniform(0.7, 0.95), max(n_claims, 2)
        elif trig == "loss_ratio_bad":
            lr, n_claims = rng.uniform(1.2, 2.2), max(n_claims, 3)
        elif trig == "frequency":
            n_claims = rng.randint(5, 8)
            lr = min(lr, 0.45)
        elif trig == "large_loss":
            large, n_claims = True, max(n_claims, 1)
            lr = 0.0  # the large loss is added on top
        elif trig == "pc10":
            loc.protection_class = 10
            if loc.construction == "frame":
                loc.construction = "joisted_masonry"
        elif trig == "frame_pc":
            loc.construction, loc.protection_class = "frame", rng.choice([9, 10])
        elif trig == "old_building":
            loc.year_built = rng.randint(1905, 1948)
        elif trig == "roof_age":
            loc.roof_year = eff.year - rng.randint(27, 40)
            loc.year_built = min(loc.year_built or 2000, loc.roof_year)
        elif trig == "unsprinklered_big":
            loc.building_value = _money(rng, 9_000_000, 15_000_000)
            loc.sprinklered, loc.sprinkler_pct = False, 0
        elif trig in ("hurricane_big", "hurricane_frame"):
            city, state, zip3s = rng.choice([c for c in names.CITIES if c[2][0] in labels.hurricane_zip3])
            loc.city, loc.state, loc.zip = city, state, _zip(rng, [z for z in zip3s if z in labels.hurricane_zip3])
            if trig == "hurricane_frame":
                loc.construction = "frame"
                loc.protection_class = min(loc.protection_class or 5, 6)
            else:
                loc.building_value = _money(rng, 5_500_000, 12_000_000)
                if loc.construction == "frame":
                    loc.construction = "masonry_non_combustible"
        elif trig == "quake_jm":
            city, state, zip3s = rng.choice([c for c in names.CITIES if c[2][0] in labels.quake_zip3])
            loc.city, loc.state, loc.zip = city, state, _zip(rng, [z for z in zip3s if z in labels.quake_zip3])
            loc.construction, loc.year_built = "joisted_masonry", rng.randint(1950, 1978)
            loc.roof_year = max(loc.roof_year or 0, eff.year - 15)
        elif trig == "loc_tiv_refer":
            loc.building_value = _money(rng, 22_000_000, 32_000_000)
            loc.sprinklered, loc.sprinkler_pct = True, 100
        elif trig == "loc_tiv_decline":
            loc.building_value = _money(rng, 48_000_000, 70_000_000)
            loc.sprinklered, loc.sprinkler_pct = True, 100
        loc.roof_year = max(loc.roof_year or 0, loc.year_built or 0) if trig != "roof_age" else loc.roof_year
        loc.tiv = (loc.building_value or 0) + (loc.contents_value or 0) + (loc.bi_value or 0)
        loc.square_feet = max(800, int(round((loc.building_value or 0) / 180 / 100) * 100))
        tiv_total = sum(x.tiv for x in locs)

    claims, loss_years = _losses(rng, eff, tiv_total, groups, lr, n_claims, large)

    first, last = _person(rng)
    agency, domain = rng.choice(names.AGENCIES)
    pfirst, plast = _person(rng)
    site_stub = "".join(ch for ch in name.split(" ")[0] + name.split(" ")[1] if ch.isalnum()).lower()
    mailing = Address(street=locs[0].street, city=locs[0].city, state=locs[0].state, zip=locs[0].zip) \
        if rng.random() < 0.7 else Address(street=f"PO Box {rng.randint(100, 9999)}", city=locs[0].city,
                                           state=locs[0].state, zip=locs[0].zip)
    revenue = float(round(tiv_total * rng.uniform(0.3, 1.5), -4))
    truth = Submission(
        submission_id=sub_id,
        insured=Insured(
            named_insured=name,
            dba=(f"{name.split(' ')[0]} {names.CLASS_PROFILES[naics][2]}" if rng.random() < 0.25 else None),
            fein=f"{rng.randint(10, 99)}-{rng.randint(1000000, 9999999)}",
            entity_type=entity, mailing_address=mailing,
            business_description=names.CLASS_PROFILES[naics][1], naics_code=naics,
            years_in_business=rng.randint(2, 60), annual_revenue=revenue,
            employee_count=rng.randint(4, 400), website=f"www.{site_stub}.com",
            contact_name=f"{first} {last}", contact_phone=_phone(rng),
            contact_email=f"{first[0].lower()}{last.lower().replace(chr(39), '')}@{site_stub}.com",
        ),
        broker=Broker(agency_name=agency, producer_name=f"{pfirst} {plast}",
                      producer_email=f"{pfirst.lower()}.{plast.lower().replace(chr(39), '')}@{domain}",
                      producer_phone=_phone(rng)),
        policy=PolicyInfo(
            effective_date=eff, expiration_date=eff.replace(year=eff.year + 1),
            transaction_type="new" if rng.random() < 0.75 else "renewal",
            prior_carrier=prior, quote_needed_by=eff - timedelta(days=rng.randint(7, 21)),
            submission_received_date=eff - timedelta(days=rng.randint(25, 60)),
        ),
        coverage=Coverage(
            building_limit=sum(x.building_value for x in locs), bpp_limit=sum(x.contents_value for x in locs),
            business_income_limit=sum(x.bi_value for x in locs),
            deductible=float(rng.choice([1000, 2500, 5000, 10000, 25000])),
            valuation="replacement_cost" if rng.random() < 0.85 else "actual_cash_value",
            coinsurance_pct=rng.choice([80, 90, 100]),
            cause_of_loss_form=rng.choices(["special", "broad", "basic"], [0.8, 0.15, 0.05])[0],
            flood_requested=rng.random() < 0.15,
            earthquake_requested=any(x.state == "CA" for x in locs) and rng.random() < 0.5,
        ),
        locations=locs, claims=claims, loss_years=loss_years,
        totals=Totals(total_tiv=tiv_total, location_count=len(locs),
                      five_year_incurred=round(sum(c.incurred for c in claims), 2),
                      five_year_premium=round(sum(ly.earned_premium for ly in loss_years), 2)),
    )
    world = World(truth=truth, template=template, target=target, mess=world_mess, loss_run_groups=groups)
    _plan_mess(rng, world)
    return world


OMITTABLE_ACCOUNT = ["insured.fein", "insured.website", "insured.years_in_business",
                     "insured.employee_count", "policy.prior_carrier", "coverage.coinsurance_pct",
                     "insured.naics_code"]
OMITTABLE_LOCATION = ["protection_class", "year_built", "roof_year"]


def _plan_mess(rng: random.Random, w: World) -> None:
    t = w.truth
    name = t.insured.named_insured or ""
    stem_words = name.split(" ")
    core = " ".join(stem_words[:-1]) if stem_words[-1] in ("LLC", "L.L.C.", "Inc.", "Corp.", "Corporation", "LP") else name
    # Benign name variants (normalization should treat these as the same entity).
    variants = [name.upper(), core, core + ", " + (stem_words[-1] if stem_words[-1] != core else ""),
                " ".join(stem_words[:2]), name.replace(" and ", " & ")]
    w.name_variants = {"email": rng.choice(variants).strip(", "), "sov": rng.choice(variants).strip(", "),
                       "loss_run": rng.choice(variants).strip(", ")}
    if rng.random() < 0.15:
        w.name_variants["loss_run"] = f"{stem_words[0].upper()} {stem_words[1].upper()} HOLDINGS"
        w.mess.append("name_affiliate_variant")
    if rng.random() < 0.06:
        other_noun = "Distribution" if "Distribution" not in name else "Services"
        w.name_variants["loss_run"] = f"{stem_words[0]} {stem_words[1]} {other_noun} Inc."
        w.mess.append("name_conflict")
        w.expected_conflicts.append("insured.named_insured")

    if rng.random() < 0.30:
        k = rng.choice([1, 1, 2, 3])
        for _ in range(k):
            if rng.random() < 0.55:
                p = rng.choice(OMITTABLE_ACCOUNT[:-1] if rng.random() < 0.85 else OMITTABLE_ACCOUNT)
            else:
                loc = rng.choice(t.locations)
                p = f"locations[{loc.loc_number}].{rng.choice(OMITTABLE_LOCATION)}"
            w.omitted.add(p)
        w.mess.append("missing:" + ",".join(sorted(w.omitted)))

    if rng.random() < 0.25:
        factor = rng.uniform(0.78, 0.94)
        w.app_stated_tiv = float(round((t.totals.total_tiv or 0) * factor, -3))
        w.mess.append("tiv_conflict")
        w.expected_conflicts.append("totals.total_tiv")
    else:
        w.app_stated_tiv = t.totals.total_tiv

    if rng.random() < 0.12:
        loc = rng.choice(t.locations[:3])
        if f"locations[{loc.loc_number}].year_built" not in w.omitted and loc.year_built:
            delta = rng.choice([-1, 1]) * rng.randint(4, 25)
            w.app_year_built[loc.loc_number] = loc.year_built + delta
            w.mess.append("year_built_conflict")
            w.expected_conflicts.append(f"locations[{loc.loc_number}].year_built")

    if rng.random() < 0.15:
        eff = t.policy.effective_date
        w.email_effective_date = eff + timedelta(days=rng.choice([-31, -30, 30, 31, 14, -14]))
        w.mess.append("effective_date_conflict")
        w.expected_conflicts.append("policy.effective_date")

    w.messy_formats = rng.random() < 0.5
    if w.messy_formats:
        w.mess.append("messy_formats")
    w.sov_format = "xlsx" if rng.random() < 0.6 else "pdf"
    if rng.random() < 0.15:
        w.scanned.add("application")
    if rng.random() < 0.22:
        w.scanned.add("loss_run")
    if w.sov_format == "pdf" and rng.random() < 0.2:
        w.scanned.add("sov")
    for role in list(w.scanned):
        w.mess.append(f"scanned:{role}")
        if rng.random() < 0.2:
            w.rotated.add(role)
            w.mess.append(f"rotated:{role}")
    w.random_filenames = rng.random() < 0.3
    w.mentions_tiv_in_email = rng.random() < 0.4
