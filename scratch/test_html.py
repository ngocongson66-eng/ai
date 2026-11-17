import re

with open('server.py', 'r', encoding='utf-8') as f:
    code = f.read()

m = re.search(r'HTML_PAGE = """([\s\S]*?)"""', code)
if not m:
    print('HTML_PAGE not found!')
else:
    html = m.group(1)
    print('Found HTML, length:', len(html))
    scripts = re.findall(r'<script>([\s\S]*?)</script>', html)
    print('Scripts count:', len(scripts))
    if scripts:
        with open('scratch/extracted.js', 'w', encoding='utf-8') as js_file:
            js_file.write(scripts[0])
        print('Wrote extracted.js')
