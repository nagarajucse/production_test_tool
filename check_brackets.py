def check_js_syntax():
    with open("dashboard_test.js", "r", encoding="utf-8") as f:
        js = f.read()
        
    print(f"JS code length: {len(js)} characters")
    
    # Balanced brackets check
    stack = []
    pairs = {')': '(', '}': '{', ']': '['}
    
    # We need to ignore characters inside comments and strings
    in_single_line_comment = False
    in_multi_line_comment = False
    in_string = None  # None, "'", '"', or '`'
    escaped = False
    
    line_num = 1
    col_num = 1
    
    for idx, char in enumerate(js):
        if char == '\n':
            line_num += 1
            col_num = 1
        else:
            col_num += 1
            
        if escaped:
            escaped = False
            continue
            
        if in_single_line_comment:
            if char == '\n':
                in_single_line_comment = False
            continue
            
        if in_multi_line_comment:
            if char == '/' and js[idx-1] == '*':
                in_multi_line_comment = False
            continue
            
        if in_string:
            if char == '\\':
                escaped = True
                continue
            if char == in_string:
                in_string = None
            continue
            
        # Check for comments
        if char == '/' and idx + 1 < len(js):
            if js[idx+1] == '/':
                in_single_line_comment = True
                continue
            elif js[idx+1] == '*':
                in_multi_line_comment = True
                continue
                
        # Check for strings
        if char in ["'", '"', '`']:
            in_string = char
            continue
            
        # Check brackets
        if char in ['(', '{', '[']:
            stack.append((char, line_num, col_num))
        elif char in [')', '}', ']']:
            if not stack:
                print(f"Unmatched closing bracket '{char}' at line {line_num}, col {col_num}")
            else:
                top, t_line, t_col = stack.pop()
                if pairs[char] != top:
                    print(f"Mismatched bracket: expected '{char}' to match '{top}' from line {t_line}, col {t_col}, but got '{char}' at line {line_num}, col {col_num}")

    while stack:
        top, t_line, t_col = stack.pop()
        print(f"Unclosed opening bracket '{top}' from line {t_line}, col {t_col}")
        
    print("Bracket check complete.")

if __name__ == "__main__":
    check_js_syntax()
