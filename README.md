# DS5220 Data Project 2 — Weather Tracker

## Data Source
This pipeline uses the [Open-Meteo API](https://open-meteo.com/), a free, 
no-API-key-required weather service that provides real-time meteorological 
data for any location on Earth. Data is collected for Charlottesville, VA 
(latitude 38.0336, longitude -78.5080) and updated every hour.

## Scheduled Process
A containerized Python script runs inside a Kubernetes CronJob on an AWS EC2 
instance every hour. On each run, the script:
1. Fetches current weather conditions from the Open-Meteo API including 
   temperature, feels-like temperature, humidity, wind speed, precipitation, 
   and cloud cover
2. Downloads the existing `data.csv` file from S3 (or starts fresh on the 
   first run)
3. Appends the new reading as a new row and uploads the updated CSV back to S3
4. Generates an updated time-series plot and uploads it to S3 as `plot.png`

The Docker image is built automatically via GitHub Actions and hosted on 
GitHub Container Registry (GHCR). Kubernetes pulls the image and runs it 
on schedule without any manual intervention.

## Output Data
- **`data.csv`** — A cumulative CSV file stored in S3 containing all hourly 
  readings. Each row represents one hourly observation with the following columns:
  - `timestamp` — UTC time of the reading (ISO 8601 format)
  - `location` — Location name (Charlottesville, VA)
  - `temperature_f` — Air temperature in degrees Fahrenheit
  - `feels_like_f` — Apparent/feels-like temperature in degrees Fahrenheit
  - `humidity_pct` — Relative humidity as a percentage
  - `wind_speed_mph` — Wind speed in miles per hour
  - `precipitation_in` — Precipitation in inches
  - `cloud_cover_pct` — Cloud cover as a percentage

## Output Plot
- **`plot.png`** — A three-panel time-series chart updated on every run showing:
  - **Panel 1:** Temperature and feels-like temperature over time (°F)
  - **Panel 2:** Humidity and cloud cover over time (%)
  - **Panel 3:** Wind speed over time (mph)

The plot shows how weather conditions in Charlottesville, VA evolve over the 
72+ hour collection window, capturing patterns like overnight temperature drops, 
daytime warming, and shifting wind and humidity levels.

## Live Outputs
- 📊 [View Plot](http://vinith-ds5220.s3-website-us-east-1.amazonaws.com/plot.png)
- 📄 [View Data CSV](http://vinith-ds5220.s3-website-us-east-1.amazonaws.com/data.csv)
