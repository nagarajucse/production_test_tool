with open("server/dashboard.html", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Inspect lines 1500 to 1515 (1-based index is lines[1499] to lines[1514])
for idx in range(1500, 1515):
    line = lines[idx]
    print(f"Line {idx+1}: {repr(line)}")
    for pos, char in enumerate(line):
        print(f"  Col {pos+1}: {repr(char)} (code: {ord(char)})")
