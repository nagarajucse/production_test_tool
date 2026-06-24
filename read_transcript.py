import json

def read_last_steps():
    path = r"C:\Users\Aratek\.gemini\antigravity-ide\brain\c715b606-e7cc-4e59-be49-2d1fc442fdeb\.system_generated\logs\transcript.jsonl"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    print(f"Total steps in transcript: {len(lines)}")
    # Scan backwards for browser subagent tool output
    for i in range(len(lines) - 1, -1, -1):
        step = json.loads(lines[i])
        # look for browser subagent tool output
        if "browser_subagent" in str(step):
            print(f"--- Step {i} ---")
            print(json.dumps(step, indent=2)[:2000])
            print("...\n")

if __name__ == "__main__":
    read_last_steps()
