import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("127.0.0.1", 5000))

# Send a valid JSON payload ending with a newline
s.sendall(b'{"device_id": "DEV-001", "result": "PASS"}\n')
print(s.recv(1024).decode())
# Output: {"status": "success", "message": "Stored Successfully", "id": "..."}

# Send a malformed JSON payload
s.sendall(b'invalid data string\n')
print(s.recv(1024).decode())
# Output: {"status": "failed", "errors": ["Invalid JSON format"]}

s.close()
