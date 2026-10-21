"""Canonical submission record.

The same model holds ground truth (written by the data generator) and the
pipeline's predictions. Per-field provenance (confidence, citations, flags) lives
next to the record, keyed by flattened field path (see `submitiq.fields`), so the
record stays easy to read and diff.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class EntityType(str, Enum):
    LLC = "llc"
    CORPORATION = "corporation"
    PARTNERSHIP = "partnership"
    SOLE_PROPRIETOR = "sole_proprietor"
    NONPROFIT = "nonprofit"


class TransactionType(str, Enum):
    NEW = "new"
    RENEWAL = "renewal"


class Valuation(str, Enum):
    REPLACEMENT_COST = "replacement_cost"
    ACTUAL_CASH_VALUE = "actual_cash_value"


class CauseOfLossForm(str, Enum):
    BASIC = "basic"
    BROAD = "broad"
    SPECIAL = "special"


class Construction(str, Enum):
    """ISO construction classes 1-6."""
    FRAME = "frame"
    JOISTED_MASONRY = "joisted_masonry"
    NON_COMBUSTIBLE = "non_combustible"
    MASONRY_NON_COMBUSTIBLE = "masonry_non_combustible"
    MODIFIED_FIRE_RESISTIVE = "modified_fire_resistive"
    FIRE_RESISTIVE = "fire_resistive"


class RoofType(str, Enum):
    ASPHALT_SHINGLE = "asphalt_shingle"
    METAL = "metal"
    BUILT_UP = "built_up"
    MEMBRANE = "membrane"
    TILE = "tile"


class AlarmType(str, Enum):
    NONE = "none"
    LOCAL = "local"
    CENTRAL_STATION = "central_station"


class ClaimStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class Address(_Model):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None


class Insured(_Model):
    named_insured: Optional[str] = None
    dba: Optional[str] = None
    fein: Optional[str] = None
    entity_type: Optional[EntityType] = None
    mailing_address: Address = Field(default_factory=Address)
    business_description: Optional[str] = None
    naics_code: Optional[str] = None
    years_in_business: Optional[int] = None
    annual_revenue: Optional[float] = None
    employee_count: Optional[int] = None
    website: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class Broker(_Model):
    agency_name: Optional[str] = None
    producer_name: Optional[str] = None
    producer_email: Optional[str] = None
    producer_phone: Optional[str] = None


class PolicyInfo(_Model):
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    transaction_type: Optional[TransactionType] = None
    prior_carrier: Optional[str] = None
    quote_needed_by: Optional[date] = None
    submission_received_date: Optional[date] = None


class Coverage(_Model):
    building_limit: Optional[float] = None
    bpp_limit: Optional[float] = None
    business_income_limit: Optional[float] = None
    deductible: Optional[float] = None
    valuation: Optional[Valuation] = None
    coinsurance_pct: Optional[int] = None
    cause_of_loss_form: Optional[CauseOfLossForm] = None
    flood_requested: Optional[bool] = None
    earthquake_requested: Optional[bool] = None


class Location(_Model):
    loc_number: int
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    occupancy: Optional[str] = None
    construction: Optional[Construction] = None
    year_built: Optional[int] = None
    stories: Optional[int] = None
    square_feet: Optional[int] = None
    sprinklered: Optional[bool] = None
    sprinkler_pct: Optional[int] = None
    protection_class: Optional[int] = None
    roof_type: Optional[RoofType] = None
    roof_year: Optional[int] = None
    alarm_type: Optional[AlarmType] = None
    building_value: Optional[float] = None
    contents_value: Optional[float] = None
    bi_value: Optional[float] = None
    tiv: Optional[float] = None


class Claim(_Model):
    claim_number: str
    policy_year: Optional[int] = None
    date_of_loss: Optional[date] = None
    cause: Optional[str] = None
    status: Optional[ClaimStatus] = None
    paid: Optional[float] = None
    reserve: Optional[float] = None
    incurred: Optional[float] = None


class LossYear(_Model):
    policy_year: int
    carrier: Optional[str] = None
    earned_premium: Optional[float] = None
    claim_count: Optional[int] = None
    total_incurred: Optional[float] = None


class Totals(_Model):
    total_tiv: Optional[float] = None
    location_count: Optional[int] = None
    five_year_incurred: Optional[float] = None
    five_year_premium: Optional[float] = None


class Submission(_Model):
    submission_id: str
    insured: Insured = Field(default_factory=Insured)
    broker: Broker = Field(default_factory=Broker)
    policy: PolicyInfo = Field(default_factory=PolicyInfo)
    coverage: Coverage = Field(default_factory=Coverage)
    locations: list[Location] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    loss_years: list[LossYear] = Field(default_factory=list)
    totals: Totals = Field(default_factory=Totals)


class DocType(str, Enum):
    EMAIL = "email"
    APPLICATION = "application"
    LOSS_RUN = "loss_run"
    SOV = "sov"
    OTHER = "other"


class GroundTruthMeta(_Model):
    """Generator-side labels that are not part of the record itself."""
    split: str
    template: str
    doc_types: dict[str, DocType]
    expected_conflicts: list[str] = Field(default_factory=list)
    expected_decision: str
    expected_reasons: list[str] = Field(default_factory=list)
    mess: list[str] = Field(default_factory=list)


class GroundTruth(_Model):
    record: Submission
    meta: GroundTruthMeta
