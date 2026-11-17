with open('server.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

start_tag = 'HTML_TEMPLATE = """'
pos = text.find(start_tag)
end_pos = text.find('"""\n\n# Render HTML_PAGE', pos)
template = text[pos + len(start_tag):end_pos]

# Tìm các trường hợp có \n hoặc \r hoặc \s trong template
lines = template.split('\n')
for idx, line in enumerate(lines):
    # Kiểm tra xem có escape nào có thể bị python nuốt không
    if "\\n" in line or "\\r" in line or "\\s" in line or "\\t" in line:
        print(f"Line {idx+1}: {line.strip()}")
