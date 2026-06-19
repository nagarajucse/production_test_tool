"""
test.py — HTTP client test script for the DMS HTTP Server.

Sends a sample sensor test result payload via HTTP POST to the DMS server
and prints the structured JSON response.

Usage:
    python test.py

Requirements:
    pip install requests

The server must be running (python server/app.py) before executing this script.
"""

import json
import sys

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is not installed.")
    print("Install it with: pip install requests")
    sys.exit(1)

# --- Server target ---
SERVER_IP = "localhost"
SERVER_PORT = 5000
URL = f"http://{SERVER_IP}:{SERVER_PORT}/"

# --- Sample payload matching the DMS server schema ---
payload = {
    "sensor_sn": "A400202401010111111",
    "model": "A400",
    "quality_score_afiq": 81,
    "nfiq_score": 81,
    "minutiae_count": 0,
    "verification_score": 333,
    "part_number": "1.17-A400-0001",
    "work_order": "MO-1-2025-0211",
    "tester_id": "1034",
    "timestamp": "2026-06-19T05:27:43Z",
    "sensor_mac": "3130313131313131",
}

print(f"Sending POST {URL}")
print(f"Payload: {json.dumps(payload, indent=2)}\n")

try:
    response = requests.post(URL, json=payload, timeout=10)
    print(f"HTTP Status : {response.status_code}")
    print(f"Response    : {json.dumps(response.json(), indent=2)}")
except requests.exceptions.ConnectionError:
    print(f"ERROR: Could not connect to {URL}")
    print("Ensure the DMS server is running: python server/app.py")
    sys.exit(1)
except requests.exceptions.Timeout:
    print(f"ERROR: Request timed out after 10 seconds.")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)