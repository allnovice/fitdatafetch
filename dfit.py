from dotenv import load_dotenv
import os
import psycopg2
import requests
import time
import json
from datetime import datetime, timezone

load_dotenv()

# -------------------------------
# CONFIG
# -------------------------------
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
DB_CONN = os.getenv("NEON_CONN")

FIT_URL = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"

# -------------------------------
# DB setup
# -------------------------------
conn = psycopg2.connect(DB_CONN)
c = conn.cursor()

# Ensure tables exist (same as full script)
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
# Get last fetch timestamp
# -------------------------------
def get_last_fetch_time():
    c.execute("SELECT value FROM meta WHERE key='last_fetch'")
    row = c.fetchone()
    if row:
        return int(row[0])
    # fallback: 1 day ago if no meta
    fallback = int((datetime.now(timezone.utc).timestamp() - 86400) * 1000)
    c.execute("INSERT INTO meta VALUES (%s, %s)", ('last_fetch', str(fallback)))
    conn.commit()
    return fallback

# -------------------------------
# Fetch step data
# -------------------------------
def fetch_fit_data(access_token, start_ms, end_ms):
    body = {
        "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
        "bucketByTime": {"durationMillis": 86400000},  # 1 day
        "startTimeMillis": start_ms,
        "endTimeMillis": end_ms
    }
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    resp = requests.post(FIT_URL, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()

# -------------------------------
# Save data
# -------------------------------
def save_steps(data):
    for bucket in data.get("bucket", []):
        start = int(bucket["startTimeMillis"])
        end = int(bucket["endTimeMillis"])
        steps = sum(
            val.get("intVal", 0)
            for dataset in bucket.get("dataset", [])
            for point in dataset.get("point", [])
            for val in point.get("value", [])
        )
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
    start_ms = get_last_fetch_time()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    print(f"Fetching from {datetime.fromtimestamp(start_ms/1000, timezone.utc)} to {datetime.fromtimestamp(now_ms/1000, timezone.utc)}")
    data = fetch_fit_data(access_token, start_ms, now_ms)
    save_steps(data)

    # update last fetch
    c.execute("UPDATE meta SET value=%s WHERE key='last_fetch'", (str(now_ms),))
    conn.commit()
    print("✅ Daily data updated")

if __name__ == "__main__":
    main()
