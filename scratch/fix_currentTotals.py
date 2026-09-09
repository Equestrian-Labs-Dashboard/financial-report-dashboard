import re

with open('docs/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_ytd = r'''        } else if (currentYearRows.length > 0) {
          const currentTotals = sumRows(currentYearRows);
          const prevYearRowsRaw = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear - 1, month: "all", quarter: "all" });'''

new_ytd = r'''        } else if (currentYearRows.length > 0) {
          const currentYearRowsYTD = currentYearRows.filter(r => String(r.month).padStart(2, "0") <= maxMonth);
          const currentTotals = sumRows(currentYearRowsYTD);
          const prevYearRowsRaw = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear - 1, month: "all", quarter: "all" });'''

content = content.replace(old_ytd, new_ytd)

with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
