"""Pools of realistic-looking (fictional) values for the generator."""

NAME_STEMS = [
    "Harbor Point", "Blue Ridge", "Summit Crest", "Cedar Lane", "Ironwood", "Lakeshore",
    "Redstone", "Pioneer Valley", "Meridian", "Granite State", "Northgate", "Silver Creek",
    "Oak Hollow", "Bayview", "Prairie Wind", "Keystone", "Riverbend", "Copper Hill",
    "Westfield", "Magnolia", "Evergreen", "Stonebridge", "Clearwater", "Highland Park",
    "Falcon Ridge", "Twin Pines", "Sunrise", "Old Mill", "Brookstone", "Juniper",
]

# NAICS -> (industry nouns used in names, business description, occupancy text)
CLASS_PROFILES = {
    "531120": (["Properties", "Office Holdings", "Realty"], "Owns and leases multi-tenant office buildings", "Office"),
    "493110": (["Logistics", "Warehousing", "Distribution"], "Dry goods warehousing and third-party distribution", "Warehouse"),
    "332710": (["Machine Works", "Precision Machining", "Tool & Die"], "CNC machining of metal parts for industrial customers", "Machine Shop"),
    "445110": (["Market", "Foods", "Grocers"], "Independent grocery store with deli and bakery counter", "Grocery Store"),
    "311811": (["Bakery", "Bake Shop", "Breads"], "Retail bakery producing breads and pastries on premises", "Retail Bakery"),
    "713940": (["Fitness", "Athletic Club", "Sports Center"], "Fitness center with weights, classes and locker rooms", "Fitness Center"),
    "423710": (["Supply", "Hardware", "Industrial Supply"], "Wholesale distribution of hardware and fasteners", "Wholesale Hardware"),
    "541330": (["Engineering", "Engineering Group", "Design Partners"], "Civil and structural engineering consulting office", "Engineering Office"),
    "811111": (["Auto Care", "Automotive", "Motor Works"], "General automotive repair and maintenance garage", "Auto Repair"),
    "531110": (["Apartments", "Residential", "Living"], "Owns and operates garden-style apartment buildings", "Apartments"),
    "721110": (["Hospitality", "Inn", "Hotel Group"], "Limited-service hotel with no restaurant", "Hotel"),
    "722511": (["Grill", "Kitchen", "Restaurant Group"], "Full-service restaurant with bar and commercial cooking", "Restaurant"),
    "325998": (["Chemical", "Coatings", "Specialty Chemicals"], "Blending and packaging of industrial cleaning chemicals", "Chemical Mfg"),
    "325920": (["Pyrotechnics", "Explosives", "Blasting Supply"], "Manufacture of commercial explosives and pyrotechnics", "Explosives Mfg"),
    "423930": (["Recycling", "Scrap Metal", "Salvage"], "Scrap metal recycling yard with shredding equipment", "Scrap Yard"),
    "722410": (["Tavern", "Lounge", "Taproom"], "Bar and nightclub with live music, open until 2 a.m.", "Bar / Nightclub"),
}

LEGAL_SUFFIX = {
    "llc": ["LLC", "L.L.C.", "LLC"],
    "corporation": ["Inc.", "Corp.", "Corporation", "Inc."],
    "partnership": ["LP", "Partners LP"],
    "sole_proprietor": [""],
    "nonprofit": ["Inc."],
}

# (city, state, zip3 options)
CITIES = [
    ("Miami", "FL", ["331", "330"]), ("Tampa", "FL", ["336"]), ("Fort Lauderdale", "FL", ["333"]),
    ("Houston", "TX", ["770"]), ("Galveston", "TX", ["775"]), ("Dallas", "TX", ["752"]),
    ("New Orleans", "LA", ["701"]), ("Charleston", "SC", ["294"]), ("Atlanta", "GA", ["303"]),
    ("Chicago", "IL", ["606"]), ("Columbus", "OH", ["432"]), ("Denver", "CO", ["802"]),
    ("Phoenix", "AZ", ["850"]), ("San Francisco", "CA", ["941"]), ("Los Angeles", "CA", ["900"]),
    ("San Jose", "CA", ["951"]), ("Sacramento", "CA", ["958"]), ("Seattle", "WA", ["981"]),
    ("Nashville", "TN", ["372"]), ("Charlotte", "NC", ["282"]), ("Boston", "MA", ["021"]),
    ("Minneapolis", "MN", ["554"]), ("Kansas City", "MO", ["641"]), ("Indianapolis", "IN", ["462"]),
    ("Pittsburgh", "PA", ["152"]), ("Omaha", "NE", ["681"]), ("Salt Lake City", "UT", ["841"]),
]
SAFE_CITIES = [c for c in CITIES if c[1] not in ("FL", "LA", "SC") and c[0] not in ("Galveston",)
               and not (c[1] == "CA" and c[0] != "Sacramento")]

STREET_NAMES = ["Main", "Oak", "Industrial", "Commerce", "Harbor", "Market", "Elm", "Washington",
                "Lake", "Park", "Mill", "River", "Airport", "Enterprise", "Technology", "Cedar",
                "Maple", "Franklin", "Jefferson", "Lincoln", "Madison", "Railroad", "Center", "Pine"]
STREET_SUFFIX = [("Street", "St"), ("Avenue", "Ave"), ("Road", "Rd"), ("Boulevard", "Blvd"),
                 ("Drive", "Dr"), ("Parkway", "Pkwy"), ("Way", "Way"), ("Lane", "Ln")]

FIRST_NAMES = ["Maria", "James", "Priya", "David", "Chen", "Sarah", "Michael", "Aisha", "Robert",
               "Elena", "Daniel", "Grace", "Omar", "Laura", "Kevin", "Nina", "Thomas", "Rosa", "Brian", "Mei"]
LAST_NAMES = ["Alvarez", "Johnson", "Patel", "Kim", "Nguyen", "O'Brien", "Schmidt", "Okafor", "Rossi",
              "Levine", "Martinez", "Thompson", "Hughes", "Yamamoto", "Carter", "Silva", "Novak", "Reyes"]

AGENCIES = [
    ("Brightline Insurance Partners", "brightlineins.com"),
    ("Copperfield Risk Advisors", "copperfieldrisk.com"),
    ("Northstar Commercial Brokerage", "northstarcb.com"),
    ("Atlas & Reed Insurance Services", "atlasreed.com"),
    ("Hollis Benton Agency", "hollisbenton.com"),
    ("Granite Peak Insurance Group", "granitepeakins.com"),
    ("Tidewater Risk Partners", "tidewaterrisk.com"),
    ("Lantern Specialty Brokers", "lanternspecialty.com"),
]

CARRIERS = [
    ("Continental Mutual Insurance Co.", "CMI"), ("Great Plains Casualty", "GPC"),
    ("Harborline Indemnity Company", "HIC"), ("Sterling National Insurance", "SNI"),
    ("Pinecrest Property & Casualty", "PPC"), ("Bridgewater Assurance", "BWA"),
]

LOSS_CAUSES = ["Water Damage", "Wind/Hail", "Fire", "Theft/Burglary", "Vandalism",
               "Equipment Breakdown", "Frozen Pipes", "Roof Leak", "Smoke", "Lightning"]
