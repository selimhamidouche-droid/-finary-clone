
import requests
import json

url = 'http://127.0.0.1:8000/api/webhook/transaction/'
headers = {'Content-Type': 'application/json'}
payload = {
    "secret": "my-secret-key-123",
    "amount": 42.00,
    "merchant": "Uber Eats",
    "card": "Amex",
    "date": "2026-01-04"
}

try:
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
