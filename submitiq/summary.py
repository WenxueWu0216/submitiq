"""One-page triage summary for the underwriter.

The LLM writes the narrative and nothing else. It gets the extracted fields as
`path = value` lines, the rules decision and the review flags, and it must
cite a field path in [brackets] for every fact. `validate_summary` then checks
that every cited path exists and has a value, and that every number in the
text appears among the cited values. If any check fails, or the model is
unavailable, the deterministic template summary is used instead. That
template is built from the same fields and carries the same citations.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

from .fields import flatten
from .llm import LLMClient, LLMRequest, LLMResponse
from .result import Decision, FieldProvenance
from .schema import Submission

PROMPT_VERSION = "v1"
CITE = re.compile(r"\[([a-z_]+(?:\[[^\]]+\])?(?:\.[a-z_]+)+)\]")
NUM = re.compile(r"\$?\d[\d,]*(?:\.\d+)?(?: ?[MK%])?")

SYSTEM = ("You write concise triage notes for commercial property underwriters. Use only the facts provided. "
          "Every factual statement must cite the field path it comes from in square brackets, e.g. "
          "[totals.total_tiv]. Do not compute new numbers except the loss ratio given. Do not change or "
          "second-guess the rules decision; explain it.")


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.2f}"
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _money(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"${v / 1e6:,.2f}M" if v >= 1e6 else f"${v:,.0f}"


def fact_lines(rec: Submission) -> list[str]:
    return [f"{p} = {_fmt(v)}" for p, v in flatten(rec).items() if v is not None]


def build_request(rec: Submission, decision: Decision, prov: dict[str, FieldProvenance]) -> LLMRequest:
    flags = [f"{p}: {fp.status} ({'; '.join(fp.reasons[-1:])})" for p, fp in sorted(prov.items()) if fp.status != "ok"]
    reasons = [f"{h.rule_id} ({h.outcome}): {h.message} -> fields {', '.join(h.fields)}" for h in decision.reasons]
    body = "\n".join(fact_lines(rec))
    user = (f"<fields>\n{body}\n</fields>\n\n<decision>{decision.outcome}\n" + "\n".join(reasons) + "</decision>\n\n"
            f"<review_flags>\n" + ("\n".join(flags) or "none") + "\n</review_flags>\n\n"
            "Write the triage note in under 250 words with these headings: Recommendation, Why, Account, "
            "Locations & COPE, Loss history, Needs attention. Cite field paths in [brackets] for every fact.")
    key = hashlib.sha256((body + str(decision.outcome) + "|".join(reasons) + "|".join(flags)).encode()).hexdigest()
    return LLMRequest(task="summary", prompt_version=PROMPT_VERSION, system=SYSTEM, user=user, max_tokens=8000,
                      key_material=key)


def _numbers_in(v: Any) -> set[str]:
    if isinstance(v, (int, float)):
        out = {f"{v:,.0f}", f"{v:.0f}", _money(float(v)).lstrip("$"), f"{v / 1e6:.1f}M", f"{v / 1e6:.2f}M", f"{v / 1e3:.0f}K"}
        if isinstance(v, float) and abs(v) < 100:
            out |= {f"{v:.2f}", f"{v:.1f}"}
        return out
    if isinstance(v, date):
        return {str(v.year), v.isoformat(), f"{v.month}/{v.day}/{v.year}", f"{v.month:02d}/{v.day:02d}/{v.year}"}
    return set(re.findall(r"\d+", str(v)))


def _to_number(tok: str) -> float | None:
    mult = {"M": 1e6, "K": 1e3}.get(tok[-1:], 1.0)
    try:
        return float(tok.rstrip("MK%").replace(",", "")) * mult
    except ValueError:
        return None


def validate_summary(text: str, rec: Submission, allowed_extra: set[str] | None = None) -> tuple[bool, list[str]]:
    values = flatten(rec)
    problems: list[str] = []
    cited = CITE.findall(text)
    if len(cited) < 3:
        problems.append("fewer than 3 field citations")
    for p in cited:
        if values.get(p) is None:
            problems.append(f"cites unknown or empty field [{p}]")
    supported: set[str] = set(allowed_extra or set())
    for p in cited:
        if values.get(p) is not None:
            supported |= _numbers_in(values[p])
    cited_numbers = [float(values[p]) for p in cited if isinstance(values.get(p), (int, float))
                     and not isinstance(values.get(p), bool)]
    stripped = CITE.sub("", text)
    for raw in NUM.findall(stripped):
        tok = re.sub(r"[\s$]", "", raw).rstrip(".,")
        if not tok or tok in supported or tok.rstrip("%") in supported or len(tok.replace(",", "").rstrip("%")) <= 2:
            continue
        x = _to_number(tok)
        if x is not None and any(abs(x - v) <= 0.005 * max(abs(v), 1.0) for v in cited_numbers):
            continue  # a rounded rendering of a cited value ("$56.75M" for 56,745,000)
        problems.append(f"number {raw.strip()!r} is not supported by a cited field")
    return not problems, problems


def template_summary(rec: Submission, decision: Decision, prov: dict[str, FieldProvenance]) -> str:
    ins, t = rec.insured, rec.totals
    values = flatten(rec)

    def c(path: str) -> str:
        """Citation tag, only for fields that actually have a value."""
        return f"[{path}]" if values.get(path) is not None else "(not provided)"

    lines = [f"## Triage summary: {ins.named_insured or rec.submission_id} {c('insured.named_insured')}", ""]
    lines.append(f"**Recommendation: {(decision.outcome or 'n/a').upper()}** (deterministic rules engine)")
    flagged = [(p, fp) for p, fp in sorted(prov.items()) if fp.status != "ok"]
    if flagged:
        lines.append(f"Pending human review of {len(flagged)} flagged field(s) before this is final.")
    lines += ["", "**Why**"]
    if decision.reasons:
        for h in decision.reasons:
            cites = " ".join(f"[{f}]" for f in h.fields if values.get(f) is not None)
            lines.append(f"- {h.rule_id} ({h.outcome}): {h.message} {cites}".rstrip())
    else:
        lines.append("- No appetite rule triggered.")
    lines += ["", "**Account**",
              f"- {ins.business_description or 'Operations not stated'} {c('insured.business_description')}; "
              f"NAICS {ins.naics_code or 'missing'} {c('insured.naics_code')}",
              f"- Effective {rec.policy.effective_date or 'n/a'} {c('policy.effective_date')}; broker "
              f"{rec.broker.agency_name or 'n/a'} {c('broker.agency_name')}",
              f"- {t.location_count or len(rec.locations)} location(s) {c('totals.location_count')}, total TIV "
              f"{_money(t.total_tiv)} {c('totals.total_tiv')}",
              "", "**Locations & COPE** (largest three by TIV)"]
    for loc in sorted(rec.locations, key=lambda l: -(l.tiv or 0))[:3]:
        k = f"locations[{loc.loc_number}]"
        lines.append(f"- Loc {loc.loc_number}: {loc.city or '?'}, {loc.state or '?'} {c(f'{k}.city')}; "
                     f"{(loc.construction or 'construction n/a').replace('_', ' ')} {c(f'{k}.construction')}, "
                     f"built {loc.year_built or 'n/a'} {c(f'{k}.year_built')}, PPC {loc.protection_class or 'n/a'} "
                     f"{c(f'{k}.protection_class')}, {'sprinklered' if loc.sprinklered else 'not sprinklered'} "
                     f"{c(f'{k}.sprinklered')}; TIV {_money(loc.tiv)} {c(f'{k}.tiv')}")
    premium = sum(y.earned_premium or 0 for y in rec.loss_years)
    incurred = sum(c.incurred or 0 for c in rec.claims)
    lr = f"{incurred / premium:.0%}" if premium else "n/a"
    open_n = sum(1 for c in rec.claims if c.status == "open")
    lines += ["", "**Loss history**",
              f"- {len(rec.claims)} claim(s), {_money(incurred)} incurred {c('totals.five_year_incurred')} on "
              f"{_money(premium)} earned premium {c('totals.five_year_premium')}: loss ratio {lr}; {open_n} open"]
    if rec.claims:
        big = max(rec.claims, key=lambda c: c.incurred or 0)
        from .fields import claim_key
        ck = f"claims[{claim_key(big.claim_number)}]"
        lines.append(f"- Largest: {_money(big.incurred)} {c(ck + '.incurred')} {big.cause or ''} "
                     f"{big.date_of_loss or ''} {c(ck + '.date_of_loss')}")
    lines += ["", "**Needs attention**"]
    lines += [f"- `{p}`: {fp.status}, {fp.reasons[-1] if fp.reasons else ''}" for p, fp in flagged[:12]] or ["- Nothing flagged."]
    return "\n".join(lines)


def _allowed_numbers(rec: Submission, decision: Decision, prov: dict[str, FieldProvenance]) -> set[str]:
    """Numbers the summary may use without citing a field: rule messages, flags, the loss ratio, counts."""
    text = " ".join(h.message for h in decision.reasons) + " " + " ".join(r for fp in prov.values() for r in fp.reasons)
    out = {re.sub(r"[\s$]", "", m).rstrip(".,") for m in NUM.findall(text)}
    out |= set(re.findall(r"\d+", rec.submission_id))
    premium = sum(y.earned_premium or 0 for y in rec.loss_years)
    incurred = sum(c.incurred or 0 for c in rec.claims)
    if premium:
        out |= {f"{incurred / premium:.0%}", f"{100 * incurred / premium:.0f}%"}
    out |= {_money(incurred).lstrip("$"), _money(premium).lstrip("$"), f"{incurred:,.0f}", f"{premium:,.0f}"}
    return out


def summarize(rec: Submission, decision: Decision, prov: dict[str, FieldProvenance],
              llm: LLMClient) -> tuple[LLMRequest, LLMResponse, str, str, bool]:
    """Return (request, response, summary_text, source, citations_valid)."""
    req = build_request(rec, decision, prov)
    resp = llm.complete(req)
    allowed = _allowed_numbers(rec, decision, prov)
    if resp.ok and resp.text:
        ok, _ = validate_summary(resp.text, rec, allowed)
        if ok:
            # Label replayed answers: a hand-written fixture must never pass for model output.
            return req, resp, resp.text, "llm" if resp.source == "live" else f"llm ({resp.source})", True
    text = template_summary(rec, decision, prov)
    ok, _ = validate_summary(text, rec, allowed)
    source = "template (LLM summary failed validation)" if resp.ok and resp.text else "template"
    return req, resp, text, source, ok
