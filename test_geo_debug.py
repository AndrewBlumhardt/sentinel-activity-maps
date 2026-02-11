"""Test geo enrichment debugging"""
import requests
import os

# Test a known IP
API_KEY = os.environ.get('AZURE_MAPS_SUBSCRIPTION_KEY')
if not API_KEY:
    raise ValueError('AZURE_MAPS_SUBSCRIPTION_KEY environment variable must be set')

# Test multiple IPs
test_ips = [
    "162.216.150.156",  # From the TSV file
    "8.8.8.8",          # Google DNS
    "1.1.1.1",          # Cloudflare DNS
    "20.62.225.143",    # Azure IP
    "40.76.4.15"        # Microsoft IP
]

for test_ip in test_ips:
    url = f"https://atlas.microsoft.com/geolocation/ip/json?api-version=1.0&ip={test_ip}"
    headers = {"subscription-key": API_KEY}
    
    response = requests.get(url, headers=headers, timeout=10)
    print(f"\nIP: {test_ip}")
    print(f"  Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        position = data.get('position', {})
        print(f"  Has position: {'Yes' if position else 'No'}")
        if position:
            print(f"  Lat/Lon: {position.get('lat')}, {position.get('lon')}")
        print(f"  Country: {data.get('countryRegion', {}).get('isoCode')}")
        print(f"  City: {data.get('city', 'N/A')}")

