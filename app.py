# app.py
import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime, timezone

st.set_page_config(page_title="Google Fit Steps Dashboard", layout="wide")

# -------------------------------
# Connect to Neon/Postgres
# -------------------------------
conn_str = st.secrets["NEON_CONN"]
conn = psycopg2.connect(conn_str)
c = conn.cursor()

# -------------------------------
# Fetch steps data
# -------------------------------
def get_steps_data():
    query = """
    SELECT start_time, end_time, steps 
    FROM steps 
    ORDER BY start_time
    """
    df = pd.read_sql(query, conn)
    # Convert millis to datetime
    df["start_time"] = pd.to_datetime(df["start_time"], unit="ms", utc=True)
    df["end_time"] = pd.to_datetime(df["end_time"], unit="ms", utc=True)
    return df

# -------------------------------
# Streamlit UI
# -------------------------------
st.title("Google Fit Steps Dashboard")

df = get_steps_data()
if df.empty:
    st.info("No steps data found. Run `getfit.py` or `dfit.py` first.")
else:
    # Show table
    st.subheader("Steps Data")
    st.dataframe(df, use_container_width=True)

    # Show chart
    st.subheader("Steps Over Time")
    chart_df = df.groupby(df["start_time"].dt.date)["steps"].sum().reset_index()
    chart_df.rename(columns={"start_time": "date", "steps": "total_steps"}, inplace=True)
    st.line_chart(chart_df.set_index("date")["total_steps"])
