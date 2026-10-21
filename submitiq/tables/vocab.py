"""Header vocabularies: how column headers are spelled in the wild."""

SOV_COLUMNS: dict[str, list[str]] = {
    "loc_number": ["loc #", "loc#", "location no", "location #", "loc no", "loc"],
    "building_number": ["bldg #", "bldg no", "building #"],
    "street": ["street address", "location address", "address", "street"],
    "city": ["city"],
    "state": ["state", "st"],
    "zip": ["zip code", "zip", "postal code", "postal"],
    "occupancy": ["occupancy / use", "occupancy", "building use", "use"],
    "construction": ["iso construction", "const type", "construction", "const"],
    "year_built": ["year built", "yr built", "yr blt", "yearbuilt", "yrbuilt"],
    "stories": ["# stories", "no. of floors", "stories", "floors", "# floors"],
    "square_feet": ["square footage", "area (sf)", "sq ft", "sqft", "sq. ft.", "area"],
    "sprinklered": ["sprinklered (y/n)", "sprk y/n", "sprinklered", "sprk", "sprinkler"],
    "sprinkler_pct": ["% sprinklered", "sprinkler %", "sprk %", "% sprk"],
    "protection_class": ["protection class", "prot. class", "prot class", "ppc", "pc"],
    "roof_year": ["roof year", "roof updated", "roof upd", "yr roof", "roof yr"],
    "building_value": ["building value", "building limit", "bldg value", "bldg limit", "building"],
    "contents_value": ["contents value", "contents", "bpp"],
    "bi_value": ["bi value", "business income", "bi/ee", "bi"],
    "tiv": ["total insured value", "total value", "tiv"],
}

LOSS_COLUMNS: dict[str, list[str]] = {
    "claim_number": ["claim no.", "claim no", "claim #", "claim number"],
    "date_of_loss": ["date of loss", "loss date", "dol"],
    "cause": ["cause of loss", "loss description", "cause"],
    "status": ["status"],
    "paid": ["total paid", "paid"],
    "reserve": ["o/s reserve", "outstanding", "reserve"],
    "incurred": ["total incurred", "incurred"],
}

PREMISES_COLUMNS: dict[str, list[str]] = {
    "loc_number": ["loc #", "loc#", "loc"],
    "street": ["street address", "address"],
    "city": ["city"],
    "state": ["st", "state"],
    "zip": ["zip"],
    "construction": ["construction"],
    "year_built": ["yr built", "yrbuilt", "year built"],
    "stories": ["stories"],
    "square_feet": ["sq ft", "sqft"],
    "sprinklered": ["sprk"],
    "protection_class": ["pc"],
    "roof_type": ["roof type"],
    "roof_year": ["roof yr"],
    "alarm_type": ["alarm"],
}
