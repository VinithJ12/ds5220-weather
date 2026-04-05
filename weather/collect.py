import os
import io
import requests
import boto3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
S3_BUCKET     = os.environ["S3_BUCKET"]
REGION        = os.environ.get("AWS_REGION", "us-east-1")
CSV_KEY       = "data.csv"   # filename inside the S3 bucket
LAT           = 38.0336
LON           = -78.5080
LOCATION_NAME = "Charlottesville, VA"

# ── AWS clients ───────────────────────────────────────────────────────────────
s3 = boto3.client("s3", region_name=REGION)

# ── 1. Fetch current weather ──────────────────────────────────────────────────
def fetch_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":           LAT,
        "longitude":          LON,
        "current":            "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,cloud_cover,apparent_temperature",
        "temperature_unit":   "fahrenheit",
        "wind_speed_unit":    "mph",
        "precipitation_unit": "inch",
        "timezone":           "UTC",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    c = resp.json()["current"]
    return {
        "timestamp":        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location":         LOCATION_NAME,
        "temperature_f":    c["temperature_2m"],
        "feels_like_f":     c["apparent_temperature"],
        "humidity_pct":     c["relative_humidity_2m"],
        "wind_speed_mph":   c["wind_speed_10m"],
        "precipitation_in": c["precipitation"],
        "cloud_cover_pct":  c["cloud_cover"],
    }

# ── 2. Load existing CSV from S3 (or start fresh) ────────────────────────────
def load_csv():
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=CSV_KEY)
        df  = pd.read_csv(io.BytesIO(obj["Body"].read()))
        print(f"Loaded existing CSV with {len(df)} rows")
        return df
    except s3.exceptions.NoSuchKey:
        print("No existing CSV found — starting fresh")
        return pd.DataFrame()
    except Exception as e:
        # catches ClientError with code NoSuchKey on first run
        print(f"CSV not found or error ({e}) — starting fresh")
        return pd.DataFrame()

# ── 3. Append new row and save back to S3 ────────────────────────────────────
def save_csv(df: pd.DataFrame):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=CSV_KEY,
        Body=buf.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )
    print(f"CSV saved → s3://{S3_BUCKET}/{CSV_KEY} ({len(df)} rows total)")

# ── 4. Generate and upload plot ───────────────────────────────────────────────
def make_and_upload_plot(df: pd.DataFrame):
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    sns.set_theme(style="darkgrid")
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(f"Weather Tracker — {LOCATION_NAME}\n{len(df)} readings collected",
                 fontsize=13, fontweight="bold")

    # Panel 1 — Temperature
    axes[0].plot(df["timestamp"], df["temperature_f"],
                 color="#e74c3c", linewidth=1.8, label="Temp (°F)")
    axes[0].plot(df["timestamp"], df["feels_like_f"],
                 color="#e67e22", linewidth=1.2, linestyle="--", label="Feels Like (°F)")
    axes[0].set_ylabel("Temperature (°F)")
    axes[0].legend(fontsize=8)

    # Panel 2 — Humidity & Cloud Cover
    axes[1].plot(df["timestamp"], df["humidity_pct"],
                 color="#3498db", linewidth=1.8, label="Humidity (%)")
    axes[1].plot(df["timestamp"], df["cloud_cover_pct"],
                 color="#95a5a6", linewidth=1.2, linestyle="--", label="Cloud Cover (%)")
    axes[1].set_ylabel("Percent (%)")
    axes[1].set_ylim(0, 105)
    axes[1].legend(fontsize=8)

    # Panel 3 — Wind Speed
    axes[2].fill_between(df["timestamp"], df["wind_speed_mph"],
                         color="#2ecc71", alpha=0.6, label="Wind (mph)")
    axes[2].set_ylabel("Wind Speed (mph)")
    axes[2].set_xlabel("Time (UTC)")
    axes[2].legend(fontsize=8)

    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close()
    buf.seek(0)

    s3.put_object(
        Bucket=S3_BUCKET,
        Key="plot.png",
        Body=buf.read(),
        ContentType="image/png",
    )
    print(f"Plot uploaded → s3://{S3_BUCKET}/plot.png")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    weather = fetch_weather()
    print(
        f"{weather['location']} | {weather['timestamp']} | "
        f"temp={weather['temperature_f']}°F | "
        f"humidity={weather['humidity_pct']}% | "
        f"wind={weather['wind_speed_mph']} mph | "
        f"clouds={weather['cloud_cover_pct']}%"
    )

    existing_df  = load_csv()
    new_row      = pd.DataFrame([weather])
    combined_df  = pd.concat([existing_df, new_row], ignore_index=True)

    save_csv(combined_df)
    make_and_upload_plot(combined_df)