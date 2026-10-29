FIRST_NAMES = [
    "Aarav", "Maya", "Liam", "Sofia", "Noah", "Priya", "Ethan", "Zara",
    "Lucas", "Anika", "Mason", "Elena", "Rohan", "Chloe", "Daniel",
    "Fatima", "Oliver", "Isha", "Samuel", "Grace", "Arjun", "Hannah",
    "Kabir", "Lily", "Marcus", "Nina", "Omar", "Ruby", "Tariq", "Violet",
]
LAST_NAMES = [
    "Sharma", "Patel", "Johnson", "Garcia", "Chen", "Kim", "Nguyen",
    "Brown", "Martinez", "Singh", "Davis", "Lopez", "Reddy", "Wilson",
    "Khan", "Anderson", "Moore", "Rao", "Taylor", "Thomas", "Clark",
    "Lewis", "Walker", "Hall", "Young", "Allen", "King", "Wright",
    "Scott", "Green",
]

# (city, region)
CITIES = [
    ("Austin", "TX"), ("Denver", "CO"), ("Seattle", "WA"), ("Chicago", "IL"),
    ("Atlanta", "GA"), ("Boston", "MA"), ("Phoenix", "AZ"), ("Miami", "FL"),
    ("Portland", "OR"), ("Columbus", "OH"), ("Nashville", "TN"),
    ("Charlotte", "NC"),
]

# (product, number, coverage_type, description, default_limit, default_deductible)
COVERAGE_CATALOGUE = [
    ("AUTO", 1, "AUTO_COLLISION", "Collision damage to insured vehicle", 25000, 500),
    ("AUTO", 2, "THEFT", "Vehicle theft", 20000, 500),
    ("HOME", 1, "PROPERTY_DAMAGE", "Damage to insured dwelling", 150000, 1000),
    ("HOME", 2, "THEFT", "Theft of household contents", 30000, 500),
    ("HLTH", 1, "MEDICAL", "Medical and hospital expenses", 50000, 250),
    ("LIAB", 1, "LIABILITY", "Third-party liability", 100000, 1000),
]

EXCLUSIONS_BY_COVERAGE_TYPE = {
    "AUTO_COLLISION": ["RACING", "UNLICENSED_DRIVER", "INTENTIONAL_ACT"],
    "PROPERTY_DAMAGE": ["WAR", "WEAR_AND_TEAR", "INTENTIONAL_ACT"],
    "THEFT": ["INTENTIONAL_ACT", "WAR"],
    "MEDICAL": ["PRE_EXISTING", "INTENTIONAL_ACT"],
    "LIABILITY": ["INTENTIONAL_ACT", "WAR"],
}
ALL_EXCLUSIONS = {
    "WAR", "INTENTIONAL_ACT", "RACING",
    "WEAR_AND_TEAR", "PRE_EXISTING", "UNLICENSED_DRIVER",
}

PRODUCT_WEIGHTS = {"AUTO": 0.35, "HOME": 0.30, "HLTH": 0.20, "LIAB": 0.15}
BASE_PREMIUM = {"AUTO": 900.0, "HOME": 1400.0, "HLTH": 2800.0, "LIAB": 600.0}
APPROVAL_AUTHORITY = {"JUNIOR": 5000.0, "SENIOR": 25000.0, "MANAGER": 300000.0}

CLAIM_TYPE_WEIGHTS = {
    "AUTO_COLLISION": 3.0, "PROPERTY_DAMAGE": 2.0, "THEFT": 1.0,
    "MEDICAL": 3.0, "LIABILITY": 4.0,
}

DOCUMENT_TYPES = [
    "CLAIM_FORM", "POLICE_REPORT", "PHOTOS", "REPAIR_ESTIMATE",
    "MEDICAL_REPORT", "PROOF_OF_OWNERSHIP", "INVOICE",
]
REQUIRED_DOCUMENTS = {   # data dictionary, section 7
    "AUTO_COLLISION": ["CLAIM_FORM", "PHOTOS", "REPAIR_ESTIMATE"],
    "PROPERTY_DAMAGE": ["CLAIM_FORM", "PHOTOS", "REPAIR_ESTIMATE"],
    "THEFT": ["CLAIM_FORM", "POLICE_REPORT", "PROOF_OF_OWNERSHIP"],
    "MEDICAL": ["CLAIM_FORM", "MEDICAL_REPORT", "INVOICE"],
    "LIABILITY": ["CLAIM_FORM", "POLICE_REPORT", "INVOICE"],
}
OPTIONAL_DOCUMENTS = {   # never overlap with the required list
    "AUTO_COLLISION": ["POLICE_REPORT", "INVOICE"],
    "PROPERTY_DAMAGE": ["INVOICE", "POLICE_REPORT"],
    "THEFT": ["PHOTOS", "INVOICE"],
    "MEDICAL": [],
    "LIABILITY": ["PHOTOS", "REPAIR_ESTIMATE"],
}

ITEM_CATEGORIES = {
    "AUTO_COLLISION": ["REPAIR", "REPLACEMENT"],
    "PROPERTY_DAMAGE": ["REPAIR", "REPLACEMENT"],
    "THEFT": ["REPLACEMENT"],
    "MEDICAL": ["HOSPITAL", "MEDICATION"],
    "LIABILITY": ["THIRD_PARTY_DAMAGE", "REPAIR"],
}
ITEM_DESCRIPTIONS = {
    "REPAIR": ["Body and panel repair", "Structural repair", "Glass and fittings repair"],
    "REPLACEMENT": ["Replacement of damaged parts", "Replacement of lost items",
                    "Replacement of damaged contents"],
    "HOSPITAL": ["Hospital admission charges", "Emergency room treatment", "Diagnostic tests"],
    "MEDICATION": ["Prescribed medication", "Follow-up pharmacy charges"],
    "THIRD_PARTY_DAMAGE": ["Damage to third-party property", "Third-party injury compensation"],
}
INCIDENT_DESCRIPTIONS = {
    "AUTO_COLLISION": ["Rear-end collision at traffic signal", "Side impact at intersection",
                       "Collision with parked vehicle"],
    "PROPERTY_DAMAGE": ["Water damage from burst pipe", "Storm damage to roof",
                        "Fire damage in kitchen"],
    "THEFT": ["Break-in while property unattended", "Theft from insured premises or vehicle",
              "Reported theft of insured items"],
    "MEDICAL": ["Emergency hospital admission", "Surgery following injury",
                "Outpatient treatment after accident"],
    "LIABILITY": ["Visitor injured on insured premises", "Damage to neighbouring property",
                  "Third-party injury claim"],
}