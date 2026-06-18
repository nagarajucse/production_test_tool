import socket
import json

HOST = "127.0.0.1"
PORT = 5000

payload = {
    "device_id": "DEV001",
    "serial_number": "SN000003",
    "operator": "Nagaraju",
    "machine": "Station-01",
    "firmware": "1.0.5",
    "result": "PASS",
    "execution_time": 12.45,
    "timestamp": "2026-06-18T15:40:00Z",
    "tests": [
        {
            "name": "Camera",
            "status": "PASS",
            "value": "OK"
        }
    ]
}

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall((json.dumps(payload) + "\n").encode())

    response = s.recv(4096)
    print(response.decode())