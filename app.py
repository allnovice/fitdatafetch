import psycopg2
import pandas as pd
import streamlit as st
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Import prediction module
from predict_steps import predict_tomorrow

# -------------------------------
# CONFIG
# -------------------------------
load_dotenv()
conn_str = os.getenv("NEON_CONN")

st.set_page_config(page_title="Fit", layout="wide")

# -------------------------------
# HEADER (matches Streamlit default top size)
# -------------------------------
st.markdown("<h4 style='margin:0;'>Fit</h4>", unsafe_allow_html=True)

# -------------------------------
# FETCH DATA
# -------------------------------
try:
    conn = psycopg2.connect(conn_str)
    query = "SELECT end_time, steps FROM steps ORDER BY end_time DESC LIMIT 2000;"
    df = pd.read_sql(query, conn)
    conn.close()
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

if df.empty:
    st.info("No step data found.")
    st.stop()

# -------------------------------
# DATA PROCESSING
# -------------------------------
local_tz = timezone(timedelta(hours=8))
df["Date"] = df["end_time"].apply(lambda x: datetime.fromtimestamp(x / 1000, tz=local_tz).date())

# Save chronological order for Day# calculation
df_chrono = df.sort_values("Date").reset_index(drop=True)
df_chrono["Day#"] = range(1, len(df_chrono)+1)

# Merge Day# back into original df sorted latest first
df = df.sort_values("Date", ascending=False).reset_index(drop=True)
df = df.merge(df_chrono[["Date", "Day#"]], on="Date")
df = df[["Day#", "Date", "steps"]]
df.columns = ["Day#", "Date", "Steps"]

# -------------------------------
# WEEKLY AVERAGE
# -------------------------------
df["week"] = df["Date"].apply(lambda d: d.isocalendar()[1])
weekly_avg = df.groupby("week")["Steps"].mean().round(0)
latest_week = weekly_avg.iloc[-1] if not weekly_avg.empty else 0

# -------------------------------
# PREDICT TOMORROW'S STEPS
# -------------------------------
pred_steps = predict_tomorrow(df)

# -------------------------------
# ACCURACY (on historical data)
# -------------------------------
import numpy as np

df_hist = df.sort_values("Date").reset_index(drop=True)
if len(df_hist) > 1:
    preds = []
    for i in range(1, len(df_hist)):
        sub_df = df_hist.iloc[:i]
        pred = predict_tomorrow(sub_df)
        preds.append(pred)
    actual = df_hist["Steps"].iloc[1:].tolist()
    mae = mean_absolute_error(actual, preds)
    rmse = np.sqrt(mean_squared_error(actual, preds))
    st.markdown(f"📊 Historical Accuracy — MAE: {mae:.0f}, RMSE: {rmse:.0f}")
# -------------------------------
# DISPLAY
# -------------------------------
st.dataframe(df, hide_index=True, use_container_width=True)
st.markdown(f"**📅 Average Steps This Week:** {int(latest_week):,}")
st.markdown(f"🤖 **Predicted Steps for Tomorrow:** {pred_steps:,}")
