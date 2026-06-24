with open("dashboard_test.js", "r", encoding="utf-8") as f:
    lines = f.readlines()

output_lines = []
# Write lines 300 to 380 of dashboard_test.js
for idx in range(300, 380):
    if idx < len(lines):
        output_lines.append(f"Line {idx+1}: {lines[idx]}")

with open("js_lines.txt", "w", encoding="utf-8") as f:
    f.writelines(output_lines)

print("Saved output to js_lines.txt")
