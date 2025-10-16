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
CONN_STR = os.getenv("NEON_CONN")

FIT_URL = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"

# -------------------------------
# DB setup
# -------------------------------
conn = psycopg2.connect(CONN_STR)
c = conn.cursor()

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
# Get last fetched timestamp (UTC)
# -------------------------------
def get_last_fetched_day():
    c.execute("SELECT value FROM meta WHERE key='last_fetch'")
    row = c.fetchone()
    if row:
        return int(row[0])
    else:
        # default: fetch from 5 years ago
        start = int((datetime.utcnow() - timedelta(days=365 * 5)).timestamp() * 1000)
        c.execute("INSERT INTO meta VALUES (%s, %s)", ('last_fetch', str(start)))
        conn.commit()
        return start

# -------------------------------
# Fetch Fit data
# -------------------------------
def fetch_fit_data(access_token, start_ms, end_ms):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
        "bucketByTime": {"durationMillis": 86400000},  # 1 day
        "startTimeMillis": start_ms,
        "endTimeMillis": end_ms
    }
    resp = requests.post(FIT_URL, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()

# -------------------------------
# Save to DB
# -------------------------------
def save_steps(data):
    for bucket in data.get("bucket", []):
        start = int(bucket["startTimeMillis"])
        end = int(bucket["endTimeMillis"])
        steps = 0
        for dataset in bucket.get("dataset", []):
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
# Main: Daily Catch-up (-1 day)
# -------------------------------
def main():
    access_token = get_access_token()
    last_fetch_ms = get_last_fetched_day()

    # Local timezone (UTC+8)
    tz = timezone(timedelta(hours=8))

    # Convert last_fetch_ms to local time
    last_fetch_dt = datetime.fromtimestamp(last_fetch_ms / 1000, tz=timezone.utc).astimezone(tz)

    # Start from last_fetch midnight
    start_dt = last_fetch_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    # End = today midnight (so we fetch full yesterday)
    today_dt = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = today_dt

    print("🕒 last_fetch_dt:", last_fetch_dt)
    print("🕒 start_dt:", start_dt)
    print("🕒 end_dt:", end_dt)

    if start_dt >= end_dt:
        print("✅ No new data to fetch (already up to yesterday)")
        return

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    print(f"📦 Fetching steps from {start_dt.date()} to {end_dt.date() - timedelta(days=1)}")

    chunk_ms = 30 * 24 * 60 * 60 * 1000  # 30 days
    current_start = start_ms

    while current_start < end_ms:
        current_end = min(current_start + chunk_ms, end_ms)
        try:
            data = fetch_fit_data(access_token, current_start, current_end)
            save_steps(data)
        except Exception as e:
            print("⚠️ Error fetching chunk:", e)
        current_start = current_end

    # Update last_fetch to end_dt
    c.execute("UPDATE meta SET value=%s WHERE key='last_fetch'", (str(end_ms),))
    conn.commit()
    print("✅ Daily catch-up fetch complete")

if __name__ == "__main__":
    main()
