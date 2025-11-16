from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/fitness.activity.read']

flow = InstalledAppFlow.from_client_secrets_file(
    'AA.json',
    SCOPES,
    redirect_uri='urn:ietf:wg:oauth:2.0:oob'  # out-of-band flow
)

auth_url, _ = flow.authorization_url(prompt='consent')

print("\n1️⃣ Open this URL in your browser on your local machine:")
print(auth_url)

code = input("\n2️⃣ Paste the code you got here:\n> ")

flow.fetch_token(code=code)

print("\n✅ Access Token:", flow.credentials.token)
print("✅ Refresh Token:", flow.credentials.refresh_token)
