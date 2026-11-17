import re

with open('server.py', 'r', encoding='utf-8') as f:
    text = f.read()

print("File size:", len(text))
matches = [m.start() for m in re.finditer(r'customer_name:\s*"Khách Hàng \(', text)]
print("Found matches:", len(matches))
for m in matches:
    print(text[m-50:m+100])
