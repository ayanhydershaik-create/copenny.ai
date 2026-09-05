import requests
import os

url = "http://localhost:8080/personalization/upload"
user_id = "demo_user"
file_path = r"c:\Users\sabih\OneDrive\Desktop\CoPenny.Ai\test_upload.csv"

with open(file_path, "rb") as f:
    files = {"file": f}
    data = {"user_id": user_id, "overwrite": "true"}
    response = requests.post(url, files=files, data=data)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
