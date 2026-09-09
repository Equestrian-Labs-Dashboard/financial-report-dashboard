import re

with open('docs/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_logic = r'''      if (isAll) {
        const currentYearRows = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear, month: "all", quarter: "all" });
        const monthsInCurrentYear = Array.from(new Set(currentYearRows.map(r => String(r.month).padStart(2, "0")))).sort();
        const isFullYear = monthsInCurrentYear.length === 12;
        const maxMonth = monthsInCurrentYear.length > 0 ? monthsInCurrentYear[monthsInCurrentYear.length - 1] : "12";
        
        if (isFullYear) {'''

new_logic = r'''      if (isAll) {
        const currentYearRows = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear, month: "all", quarter: "all" });
        
        const today = new Date();
        let isFullYear = true;
        let maxMonth = "12";
        
        if (currentYear === today.getFullYear()) {
            isFullYear = false;
            maxMonth = String(today.getMonth() + 1).padStart(2, "0");
        }
        
        if (isFullYear) {'''

content = content.replace(old_logic, new_logic)

with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
