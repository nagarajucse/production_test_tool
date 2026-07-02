import requests
import sys

def create_admin(username, password):
    url = "http://localhost:5000/register" # Adjust port to 5001 if you changed it as suggested
    payload = {
        "username": username,
        "password": password
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code == 201:
            print(f"Success: {data['message']}")
            print(f"You can now log in at http://localhost:5001/login")
        else:
            print(f"Failed ({response.status_code}): {data.get('message', 'Unknown error')}")
            
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Make sure it's running (e.g. python3 app.py) on the correct port.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 create_admin.py <username> <password>")
        print("Example: python3 create_admin.py admin mysecurepassword")
    else:
        create_admin(sys.argv[1], sys.argv[2])
