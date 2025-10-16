from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/fitness.activity.read']

flow = InstalledAppFlow.from_client_secrets_file(
    'AA.json',
    SCOPES,
    redirect_uri='http://localhost'
)

auth_url, _ = flow.authorization_url(prompt='consent')

print("\n1️⃣ Copy this URL and open it in your browser:")
print(auth_url)

code = input("\n2️⃣ Paste the code you got here:\n> ")

flow.fetch_token(code=code)

print("\n✅ Access Token:", flow.credentials.token)
print("✅ Refresh Token:", flow.credentials.refresh_token)
