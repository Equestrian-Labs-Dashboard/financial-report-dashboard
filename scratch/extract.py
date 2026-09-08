import re

with open('docs/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

match = re.search(r'<script>(.*?)</script>', content, re.DOTALL)
if match:
    with open('scratch/test_full.js', 'w', encoding='utf-8') as f:
        f.write(match.group(1))
