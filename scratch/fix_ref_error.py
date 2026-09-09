import re

with open('docs/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("} else if (monthsInCurrentYear.length > 0) {", "} else if (currentYearRows.length > 0) {")

with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
