import re

with open('docs/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_format = 'const formatMoneyVar = (val) => (val > 0 ? "+" : "") + compactMoney(val);'
new_format = '''const formatMoneyVar = (val) => {
          const sign = val > 0 ? "+" : (val < 0 ? "-" : "");
          return sign + "$" + Math.abs(val).toLocaleString("en-US", { maximumFractionDigits: 0 });
        };'''

content = content.replace(old_format, new_format)

with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

