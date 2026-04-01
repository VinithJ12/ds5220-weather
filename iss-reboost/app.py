import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import requests
from boto3.dynamodb.conditions import Key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ISS_API      = "https://api.wheretheiss.at/v1/satellites/25544"
SATELLITE_ID = "ISS"
TABLE_NAME   = os.environ["DYNAMODB_TABLE"]
AWS_REGION   = "us-east-1"

# Altitude gain at or above this value in a single 15-minute interval is
# flagged as a reboost / orbital burn. ISS reboosts typically raise the
# orbit by 1–3 km; normal orbital decay between burns is ~0.05 km/interval.
BURN_THRESHOLD_KM = Decimal("1.0")


# ---------------------------------------------------------------------------
# Step 1 — Fetch current ISS position from wheretheiss.at
# ---------------------------------------------------------------------------
def fetch_iss() -> dict:
    """Return a DynamoDB-ready item with the current ISS state."""
    resp = requests.get(ISS_API, timeout=10)
    resp.raise_for_status()
    d = resp.json()
    return {
        "satellite_id": SATELLITE_ID,
        "timestamp":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latitude":     Decimal(str(round(d["latitude"],  6))),
        "longitude":    Decimal(str(round(d["longitude"], 6))),
        "altitude_km":  Decimal(str(round(d["altitude"],  3))),
        "velocity_kms": Decimal(str(round(d["velocity"],  3))),
        "visibility":   d.get("visibility", "unknown"),
    }


# ---------------------------------------------------------------------------
# Step 2 — Query DynamoDB for the most recent previous entry
# ---------------------------------------------------------------------------
def get_previous(table) -> dict | None:
    """Return the latest stored item for ISS, or None on first run."""
    resp = table.query(
        KeyConditionExpression=Key("satellite_id").eq(SATELLITE_ID),
        ScanIndexForward=False,   # descending timestamp order
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


# ---------------------------------------------------------------------------
# Step 3 — Compare current altitude to previous entry
# ---------------------------------------------------------------------------
def altitude_analysis(current_km: Decimal, previous: dict | None) -> tuple[str, Decimal]:
    """Return (trend_label, delta_km) comparing current to previous altitude.

    Trend labels:
      FIRST_ENTRY  — no prior data to compare against
      ASCENDING    — small natural gain (solar pressure, atmospheric variation)
      DESCENDING   — normal orbital decay due to atmospheric drag
      STABLE       — negligible change
      ORBITAL_BURN — altitude jumped >= BURN_THRESHOLD_KM; reboost likely
    """
    if previous is None:
        return "FIRST_ENTRY", Decimal("0")

    delta = current_km - Decimal(str(previous["altitude_km"]))

    if delta >= BURN_THRESHOLD_KM:
        trend = "ORBITAL_BURN"
    elif delta > Decimal("0.01"):
        trend = "ASCENDING"
    elif delta < Decimal("-0.01"):
        trend = "DESCENDING"
    else:
        trend = "STABLE"

    return trend, delta


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table    = dynamodb.Table(TABLE_NAME)

    previous         = get_previous(table)
    entry            = fetch_iss()
    trend, delta     = altitude_analysis(entry["altitude_km"], previous)

    entry["trend"]    = trend
    entry["delta_km"] = delta

    table.put_item(Item=entry)

    if trend == "FIRST_ENTRY":
        log.info(
            "ISS | alt=%.3f km | lat=%.4f | lon=%.4f | visibility=%s | FIRST ENTRY",
            entry["altitude_km"], entry["latitude"], entry["longitude"], entry["visibility"],
        )
    else:
        burn_flag = "  *** ORBITAL BURN DETECTED ***" if trend == "ORBITAL_BURN" else ""
        log.info(
            "ISS | alt=%.3f km | delta=%+.3f km | %-12s | lat=%.4f | lon=%.4f | visibility=%s%s",
            entry["altitude_km"], delta, trend,
            entry["latitude"], entry["longitude"], entry["visibility"], burn_flag,
        )


if __name__ == "__main__":
    main()
