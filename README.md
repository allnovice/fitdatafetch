# Google Fit Data Fetcher

Fetch your Google Fit step data and store it in a **Neon/Postgres** database. Supports historical fetch and daily incremental fetch.

---

## Features

- Fetch **all historical step data** from Google Fit.
- Fetch **only new daily data** since last fetch.
- Store in **Neon/Postgres** safely: avoids duplicate entries.

---

## Dependencies

- Python 3.12+
- `requests`
- `python-dotenv`
- `psycopg2-binary`

Install dependencies:

```bash
pip install requests python-dotenv psycopg2-binary

Setup (Termux / Linux / Windows / macOS)

python -m venv venv
# Linux / macOS / Termux
git clone <repo_url>
cd <repo_folder>
source venv/bin/activate
# Windows
venv\Scripts\activate

CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
REFRESH_TOKEN=your_refresh_token
NEON_CONN=your_neon_connection_string

Getting Refresh Tokens
Set up Google Fit API and create a Web app OAuth client.
Use getoks.py to authorize and get the refresh token.
Add refresh token to .env.

