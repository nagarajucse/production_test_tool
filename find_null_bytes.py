with open("server/dashboard.html", "rb") as f:
    content = f.read()

null_positions = [i for i, b in enumerate(content) if b == 0]
print(f"Total null bytes: {len(null_positions)}")
if null_positions:
    print(f"First 10 null byte positions: {null_positions[:10]}")
    # print context around the first null byte
    first = null_positions[0]
    start = max(0, first - 20)
    end = min(len(content), first + 20)
    print(f"Context: {content[start:end]}")
