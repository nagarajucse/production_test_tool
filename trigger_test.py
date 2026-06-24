import json
import base64
import requests

URL = "http://localhost:5000/"

# 1x1 pixel BMP image base64
bmp_base64 = "Qk1GAAAAAAAAADYAAAAoAAAAAQAAAAEAAAABABgAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP8A"

payload = {
    "sensor_sn": "TEST_SN_123456",
    "model": "A400",
    "quality_score_afiq": 85,
    "nfiq_score": 85,
    "minutiae_count": 12,
    "verification_score": 90,
    "part_number": "PART-123-ABC",
    "work_order": "WO-2026-9999",
    "tester_id": "TESTER-99",
    "timestamp": "2026-06-23T18:00:00Z",
    "sensor_mac": "A1B2C3D4E5F6",
    "image_name": "test_fingerprint.bmp",
    "image_format": "BMP",
    "image": bmp_base64
}

print(f"Sending POST to {URL}...")
try:
    response = requests.post(URL, json=payload, timeout=5)
    print(f"Status Code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error triggering request: {e}")
