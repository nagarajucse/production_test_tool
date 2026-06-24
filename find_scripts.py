with open("server/dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

import re
matches = re.finditer(r"<script[^>]*>", content, re.IGNORECASE)
for m in matches:
    print(f"Found script tag: {m.group(0)} at character position {m.start()}")
