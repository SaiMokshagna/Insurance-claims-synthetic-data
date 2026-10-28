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
APPROVAL_AUTHORITY = {"JUNIOR": 5000.0, "SENIOR": 25000.0, "MANAGER": 100000.0}