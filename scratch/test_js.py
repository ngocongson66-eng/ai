with open('scratch/extracted.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Let's check common JS syntax errors
# Matching brackets
stack = []
pairs = {')': '(', ']': '[', '}': '{'}
lines = js.splitlines()
for line_no, line in enumerate(lines, 1):
    in_string = False
    str_char = ''
    escape = False
    for col, ch in enumerate(line):
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if in_string:
            if ch == str_char:
                in_string = False
            continue
        if ch in ('"', "'", '`'):
            in_string = True
            str_char = ch
            continue
        if ch in ('(', '[', '{'):
            stack.append((ch, line_no, col))
        elif ch in (')', ']', '}'):
            if not stack:
                print(f'Unmatched closing {ch} at line {line_no}:{col}')
            else:
                last_ch, last_line, last_col = stack.pop()
                if last_ch != pairs[ch]:
                    print(f'Mismatched {ch} at line {line_no}:{col}, expected matching for {last_ch} from line {last_line}:{last_col}')

if stack:
    print('Unclosed open brackets:', stack[-5:])
else:
    print('Brackets check: BALANCED!')
