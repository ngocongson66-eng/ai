with open('server.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Tìm vị trí HTML_TEMPLATE
start_tag = 'HTML_TEMPLATE = """'
pos = text.find(start_tag)
if pos == -1:
    print('HTML_TEMPLATE not found')
else:
    end_pos = text.find('"""', pos + len(start_tag))
    template = text[pos + len(start_tag):end_pos]
    print('Template len:', len(template))

    # Tìm các trường hợp split('\n') hoặc replace('\r', '') hoặc tương tự
    for m in re.finditer(r"split\(['\"]\n['\"]\)", template):
        print("Found unescaped newline in split:", m.group(0))
    for m in re.finditer(r"replace\(['\"]\r['\"]", template):
        print("Found unescaped return in replace:", m.group(0))
