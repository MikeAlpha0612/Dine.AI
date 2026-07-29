"""Configuration for the data layer."""

from __future__ import annotations

DATASET_NAME = "ManikaSaini/zomato-restaurant-recommendation"
DATASET_SPLIT = "train"

# India-wide Swiggy listings (~148k restaurants, 800+ city labels)
INDIA_DATASET_NAME = "GowthamD03/Swiggy"
INDIA_DATASET_SPLIT = "train"

# Multi-city Zomato supplement (New Delhi, Mumbai, Bangalore, Hyderabad, …)
METRO_DATASET_URL = (
    "https://raw.githubusercontent.com/KG-GitHubRepo/Zomato-EDA-Python/main/zomato_dataset.csv"
)
METRO_DATASET_CACHE = "data/cache/zomato_metro.csv"

# Hugging Face column names (as published on the dataset card)
COL_NAME = "name"
COL_ADDRESS = "address"
COL_RATE = "rate"
COL_VOTES = "votes"
COL_LOCATION = "location"
COL_REST_TYPE = "rest_type"
COL_CUISINES = "cuisines"
COL_COST = "approx_cost(for two people)"
COL_LISTED_CITY = "listed_in(city)"

REQUIRED_COLUMNS = (
    COL_NAME,
    COL_ADDRESS,
    COL_LOCATION,
    COL_CUISINES,
    COL_COST,
    COL_RATE,
)

# Canonical city aliases (lowercase key -> canonical name)
LOCATION_ALIASES: dict[str, str] = {
    "bengaluru": "Bangalore",
    "bangalore": "Bangalore",
    "bombay": "Mumbai",
    "mumbai": "Mumbai",
    "new delhi": "New Delhi",
    "delhi": "New Delhi",
    "gurgaon": "Gurgaon",
    "gurugram": "Gurgaon",
    "ncr": "New Delhi",
    "madras": "Chennai",
    "chennai": "Chennai",
    "calcutta": "Kolkata",
    "kolkata": "Kolkata",
    "poona": "Pune",
    "pune": "Pune",
    "trivandrum": "Thiruvananthapuram",
    "tvm": "Thiruvananthapuram",
    "cochin": "Kochi",
    "kochi": "Kochi",
    "benaras": "Varanasi",
    "banaras": "Varanasi",
    "varanasi": "Varanasi",
    "baroda": "Vadodara",
    "vadodara": "Vadodara",
    "vizag": "Visakhapatnam",
    "visakhapatnam": "Visakhapatnam",
    "secunderabad": "Hyderabad",
    "hyd": "Hyderabad",
}

# Cost-for-two thresholds (INR) for budget tiers
BUDGET_LOW_MAX = 400
BUDGET_MEDIUM_MAX = 800

# Loader retry settings
LOAD_MAX_RETRIES = 3
LOAD_RETRY_BASE_DELAY_SEC = 2.0

MIN_RATING = 0.0
MAX_RATING = 5.0
