with open('scratch/extracted.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if 'document.' in stripped and not stripped.startswith('//'):
        print(f'Line {i}: {stripped}')
