import shutil
import json

src = r"C:\Users\Aratek\.gemini\antigravity-ide\brain\c715b606-e7cc-4e59-be49-2d1fc442fdeb\.system_generated\logs\transcript.jsonl"
dst = r"d:\production_test_tool\transcript_copy.jsonl"

try:
    shutil.copy(src, dst)
    print("Copy successful!")
    with open(dst, "r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"Read {len(lines)} lines from copy.")
    for i in range(len(lines) - 1, -1, -1):
        step = json.loads(lines[i])
        if "browser_subagent" in str(step):
            print(f"--- Step {i} ---")
            print(json.dumps(step, indent=2)[:3000])
            print("...\n")
            break
except Exception as e:
    print(f"Error copying/reading: {e}")
