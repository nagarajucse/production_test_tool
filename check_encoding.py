import os

def check_file(path):
    print(f"Checking {path}...")
    if not os.path.exists(path):
        print("File does not exist.")
        return
    
    with open(path, "rb") as f:
        content = f.read()
    
    print(f"File size in bytes: {len(content)}")
    print(f"First 50 bytes: {content[:50]}")
    
    # Check for BOM
    if content.startswith(b'\xef\xbb\xbf'):
        print("Found UTF-8 BOM.")
    elif content.startswith(b'\xff\xfe'):
        print("Found UTF-16 LE BOM.")
    elif content.startswith(b'\xfe\xff'):
        print("Found UTF-16 BE BOM.")
    else:
        print("No standard BOM found.")
        
    try:
        content.decode('utf-8')
        print("Successfully decoded as UTF-8.")
    except Exception as e:
        print(f"Failed to decode as UTF-8: {e}")
        
    try:
        content.decode('utf-16')
        print("Successfully decoded as UTF-16.")
    except Exception as e:
        print(f"Failed to decode as UTF-16: {e}")

if __name__ == "__main__":
    check_file("server/dashboard.html")
