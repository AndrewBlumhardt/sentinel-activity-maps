"""Direct test of Azure Maps Geolocation API"""
import requests
import json
import os

API_KEY = os.environ.get('AZURE_MAPS_SUBSCRIPTION_KEY')
if not API_KEY:
    raise ValueError('AZURE_MAPS_SUBSCRIPTION_KEY environment variable must be set')

# Test multiple IPs
test_ips = [
    '8.8.8.8',           # Google DNS
    '162.216.150.156',   # From threat intel
    '24.48.0.1',         # Residential
    '40.76.4.15',        # Microsoft
]

for ip in test_ips:
    print(f"\n{'='*60}")
    print(f"Testing IP: {ip}")
    print('='*60)
    
    url = f"https://atlas.microsoft.com/geolocation/ip/json?api-version=1.0&ip={ip}"
    headers = {"subscription-key": API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"\nRaw Response:")
        print(json.dumps(response.json(), indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
