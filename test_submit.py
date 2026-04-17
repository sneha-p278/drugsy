import requests

url = "http://127.0.0.1:5000/generate_qr"
payload = {
    'drugId': 'DRG-123',
    'drugName': 'Aspirin',
    'serialno': 'SN-001',
    'pharmacyName': 'Health Plus',
    'email': 'test@example.com'
}

response = requests.post(url, data=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
