import requests
import json

url = "https://mops.twse.com.tw/mops/api/t05st01"

payload = {
    "companyId": "2330",
    "year": "115",
    "month": "10",
    "firstDay": "01",
    "lastDay": "13"
}

headers = {
    "Content-Type": "application/json"
}

response = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=30
)

print("HTTP:", response.status_code)
print("Content-Type:", response.headers.get("Content-Type"))
print()

try:
    result = response.json()
    print(json.dumps(result, ensure_ascii=False, indent=2))
except Exception:
    print(response.text)
