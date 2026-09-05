import os
from dotenv import load_dotenv
import requests

load_dotenv(override=True)

api_key = os.getenv("FEATHERLESS_API_KEY")
url = "https://api.featherless.ai/v1/models"
headers = {"Authorization": f"Bearer {api_key}"}

try:
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status Code: {resp.status_code}")
    if resp.status_code == 200:
        models = resp.json().get('data', [])
        print(f"Found {len(models)} Featherless models:")
        for m in models[:10]:
            print(f"- {m.get('id')}")
    else:
        print(f"Response: {resp.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
