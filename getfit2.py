from dotenv import load_dotenv
import os
import requests
import psycopg2
from datetime import datetime, timedelta, timezone

load_dotenv()

# -------------------------------
# CONFIG
# -------------------------------
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
DB_FILE = "fitdata.db"

# Google Fit endpoint
FIT_URL = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"

# -------------------------------
# DB setup
# -------------------------------
conn_str = os.getenv("NEON_CONN")
conn = psycopg2.connect(conn_str)
c = conn.cursor()

# Create tables if they don't exist
c.execute('''
CREATE TABLE IF NOT EXISTS steps (
    start_time BIGINT,
    end_time BIGINT,
    steps INT,
    PRIMARY KEY (start_time, end_time)
)
''')
c.execute('''
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
)
''')
conn.commit()

# -------------------------------
# Token refresh
# -------------------------------
def get_access_token():
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

# -------------------------------
# Fetch step data
# -------------------------------
def fetch_fit_data(access_token, start, end):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "aggregateBy": [
            {"dataTypeName": "com.google.step_count.delta"}
        ],
        "bucketByTime": {"durationMillis": 86400000},  # 1 day
        "startTimeMillis": start,
        "endTimeMillis": end
    }

    print("\n=== REQUEST BODY ===")
    print(body)
    print("====================\n")

    resp = requests.post(FIT_URL, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()

# -------------------------------
# Save data to DB
# -------------------------------
def save_steps(data):
    for bucket in data.get("bucket", []):
        start = int(bucket["startTimeMillis"])
        end = int(bucket["endTimeMillis"])
        steps = 0
        for dataset in bucket["dataset"]:
            for point in dataset.get("point", []):
                for val in point.get("value", []):
                    steps += val.get("intVal", 0)
        if steps > 0:
            c.execute(
                "INSERT INTO steps (start_time, end_time, steps) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (start, end, steps)
            )
    conn.commit()

# -------------------------------
# Main logic
# -------------------------------
def main():
    access_token = get_access_token()

    # Explicit UTC+8 timezone
    local_tz = timezone(timedelta(hours=8))

    # Ask user for start year/month
    try:
        year = int(input("Enter start year (YYYY): "))
        month = int(input("Enter start month (1-12): "))
        start_date = datetime(year, month, 1, tzinfo=local_tz)
    except:
        print("Invalid input, defaulting to Jan 2024")
        start_date = datetime(2024, 1, 1, tzinfo=local_tz)

    # 🕛 End time = yesterday midnight (stop before today)
    today_midnight = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = today_midnight

    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)

    chunk_ms = 30 * 24 * 60 * 60 * 1000  # 30 days in ms

    print(f"📦 Fetching data from {start_date.date()} to {(end_date - timedelta(days=1)).date()} in 30-day chunks...")

    current_start = start_ms
    while current_start < end_ms:
        current_end = min(current_start + chunk_ms, end_ms)
        print(f"Fetching from {datetime.fromtimestamp(current_start/1000, local_tz)} "
              f"to {datetime.fromtimestamp(current_end/1000, local_tz)}")
        try:
            data = fetch_fit_data(access_token, current_start, current_end)
            save_steps(data)
        except Exception as e:
            print("⚠️ Error fetching chunk:", e)
        current_start = current_end

    # Update last fetch in meta table
    c.execute("UPDATE meta SET value=%s WHERE key='last_fetch'", (str(end_ms),))
    conn.commit()
    print("✅ All data updated (up to yesterday midnight)")

if __name__ == "__main__":
    main()
