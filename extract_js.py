import os
import subprocess

def check_js():
    with open("server/dashboard.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Extract script content
    start_tag = "<script>"
    end_tag = "</script>"
    
    start_idx = content.find(start_tag)
    end_idx = content.find(end_tag)
    
    if start_idx == -1 or end_idx == -1:
        print("Script tag not found!")
        return
        
    js_code = content[start_idx + len(start_tag) : end_idx]
    
    test_file = "dashboard_test.js"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(js_code)
    print(f"Extracted JavaScript to {test_file}")
    
    try:
        # Check syntax using node (parse only, don't execute)
        result = subprocess.run(["node", "--check", test_file], capture_output=True, text=True)
        print("Node --check return code:", result.returncode)
        if result.returncode != 0:
            print("Syntax Error details from Node.js:")
            print(result.stderr)
        else:
            print("No syntax errors found by Node.js.")
    except FileNotFoundError:
        print("Node.js is not installed on this system.")

if __name__ == "__main__":
    check_js()
