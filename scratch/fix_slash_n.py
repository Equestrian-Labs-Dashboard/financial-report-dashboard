import re

with open('docs/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the literal backslash followed by 'n' 
content = content.replace('\\n    function highlightSelectedPeriod', '\n    function highlightSelectedPeriod')

with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
