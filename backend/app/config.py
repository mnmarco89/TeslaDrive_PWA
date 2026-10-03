import os

TESLA_CLIENT_ID = os.getenv("TESLA_CLIENT_ID")
TESLA_CLIENT_SECRET = os.getenv("TESLA_CLIENT_SECRET")
TESLA_REDIRECT_URI = os.getenv("TESLA_REDIRECT_URI")
TESLA_AUDIENCE = os.getenv(
    "TESLA_AUDIENCE",
    "https://fleet-api.prd.eu.vn.cloud.tesla.com",
)
TESLA_PRIVATE_KEY = os.getenv("TESLA_PRIVATE_KEY")

MIN_CHARGING_AMPS = 10
MAX_CHARGING_AMPS = 20
