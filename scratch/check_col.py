import sys
sys.path.insert(0, 'C:/New folder (2)')
from server import HTML_PAGE

lines = HTML_PAGE.split('\n')
for idx in range(3025, 3036):
    if idx < len(lines):
        l = lines[idx]
        print(f"Line {idx+1}: {repr(l)}")
        if len(l) >= 50:
            print(f"   Len: {len(l)}, char at 55: {repr(l[55])}")
