from dotenv import load_dotenv
import os
import sqlite3
import requests
import time
import json
import psycopg2
from datetime import datetime, timedelta
load_dotenv()

# -------------------------------
# CONFIG (edit these)
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
conn_str = os.getenv("NEON_CONN")  # or os.getenv("NEON_CONN")
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
# Get last fetched timestamp
# -------------------------------
def get_last_fetch_time():
    c.execute("SELECT value FROM meta WHERE key='last_fetch'")
    row = c.fetchone()
    if row:
        return int(row[0])
    else:
        start = int((datetime.utcnow() - timedelta(days=365 * 5)).timestamp() * 1000)  # 5 years ago
        c.execute("INSERT INTO meta VALUES (%, %)", ('last_fetch', str(start)))
        conn.commit()
        return start

# -------------------------------
# Fetch step data
# -------------------------------
def fetch_fit_data(access_token, start, end):
    url = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
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

    # 👇 Add this line
    print("\n=== REQUEST BODY ===")
    print(json.dumps(body, indent=2))
    print("====================\n")

    resp = requests.post(url, headers=headers, json=body)
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

    from datetime import timezone, timedelta, datetime
    now = datetime.now(timezone.utc)
    start_ms = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    now_ms = int(now.timestamp() * 1000)

    chunk_ms = 30 * 24 * 60 * 60 * 1000  # 30 days in ms

    print(f"Fetching data from Jan 1 2024 to now in 30-day chunks...")

    current_start = start_ms
    while current_start < now_ms:
        current_end = min(current_start + chunk_ms, now_ms)
        print(f"Fetching from {datetime.fromtimestamp(current_start/1000, timezone.utc)} to {datetime.fromtimestamp(current_end/1000, timezone.utc)}")
        try:
            data = fetch_fit_data(access_token, current_start, current_end)
            save_steps(data)
        except Exception as e:
            print("⚠️ Error fetching chunk:", e)
        current_start = current_end

    # Update last fetch in meta table
    c.execute("UPDATE meta SET value=%s WHERE key='last_fetch'", (str(now_ms),))
    conn.commit()
    print("✅ All data updated")

if __name__ == "__main__":
    main()
