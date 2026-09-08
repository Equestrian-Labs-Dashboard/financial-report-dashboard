import re

with open('docs/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add CSS
css = '''
    .variations-wrapper { display: flex; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
    .variation-card { background: var(--panel-2); border: 1px solid var(--border); border-radius: 8px; padding: 12px; flex: 1; min-width: 250px; }
    .variation-title { font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.05em; text-align: center; }
    .variation-grid { display: flex; justify-content: space-between; gap: 8px; }
    .var-item { display: flex; flex-direction: column; align-items: center; }
    .var-label { font-size: 10px; color: var(--muted-2); margin-bottom: 4px; }
    .var-val { font-size: 14px; font-weight: 720; }
    .positive-var { color: var(--green); }
    .negative-var { color: var(--red); }
    .neutral-var { color: var(--muted); }
'''
content = content.replace('</style>', css + '\n  </style>')

# 2. Add div
div = '''      <div class="section-title"><span>01 · Variaciones</span></div>
      <div id="variationsSection"></div>
      <div class="section-title"><span>02 · Shopify KPI Cards</span></div>
      <section class="kpi-grid" id="shopifyKpis"></section>'''
content = re.sub(r'<div class="section-title"><span>01 · Shopify KPI Cards</span></div>\s*<section class="kpi-grid" id="shopifyKpis"></section>', div, content)

# 3. Add to render()
content = content.replace('      renderMonthlyMatrix(selected.trendRows, selected.filters);\\n      highlightSelectedPeriod(selected.filters);\\n      renderKpis(selected.totals);', '      renderMonthlyMatrix(selected.trendRows, selected.filters);\\n      highlightSelectedPeriod(selected.filters);\\n      renderVariations(selected.filters);\\n      renderKpis(selected.totals);')

# 4. Add renderVariations function before renderKpis
func = '''
    function renderVariations(filters) {
      const allMonthlyRows = safeArray(DATA.shopify_kpis_by_brand_month);
      const isQuarter = filters.quarter !== "all";
      const isMonth = filters.month !== "all";
      const isAll = !isQuarter && !isMonth;
      const currentYear = Number(filters.year);
      let comparisons = [];
      const baseFilters = { brand: filters.brand, location: filters.location };
      
      if (isAll) {
        const currentYearRows = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear, month: "all", quarter: "all" });
        const monthsInCurrentYear = Array.from(new Set(currentYearRows.map(r => String(r.month).padStart(2, "0")))).sort();
        const isFullYear = monthsInCurrentYear.length === 12;
        const maxMonth = monthsInCurrentYear.length > 0 ? monthsInCurrentYear[monthsInCurrentYear.length - 1] : "12";
        
        if (isFullYear) {
          const currentTotals = sumRows(currentYearRows);
          const prevYearRows = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear - 1, month: "all", quarter: "all" });
          const prevTotals = sumRows(prevYearRows);
          comparisons.push({ label: FY  VS FY , current: currentTotals, prev: prevTotals });
        } else if (monthsInCurrentYear.length > 0) {
          const currentTotals = sumRows(currentYearRows);
          const prevYearRowsRaw = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear - 1, month: "all", quarter: "all" });
          const prevYearRows = prevYearRowsRaw.filter(r => String(r.month).padStart(2, "0") <= maxMonth);
          const prevTotals = sumRows(prevYearRows);
          comparisons.push({ label: YTD  VS YTD , current: currentTotals, prev: prevTotals });
        }
      } else if (isQuarter) {
        const currentQRows = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear, month: "all", quarter: filters.quarter });
        const currentTotals = sumRows(currentQRows);
        
        let prevQYear = currentYear;
        let prevQ = "Q1";
        if (filters.quarter === "Q1") { prevQYear = currentYear - 1; prevQ = "Q4"; }
        else if (filters.quarter === "Q2") { prevQ = "Q1"; }
        else if (filters.quarter === "Q3") { prevQ = "Q2"; }
        else if (filters.quarter === "Q4") { prevQ = "Q3"; }
        
        const prevQRows = filterRows(allMonthlyRows, { ...baseFilters, year: prevQYear, month: "all", quarter: prevQ });
        const prevQTotals = sumRows(prevQRows);
        comparisons.push({ label: ${filters.quarter}  VS  , current: currentTotals, prev: prevQTotals });
        
        const sameQPrevYearRows = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear - 1, month: "all", quarter: filters.quarter });
        const sameQPrevYearTotals = sumRows(sameQPrevYearRows);
        comparisons.push({ label: ${filters.quarter}  VS  , current: currentTotals, prev: sameQPrevYearTotals });
      }
      
      const container = document.getElementById("variationsSection");
      if (!container) return;
      if (comparisons.length === 0) { container.innerHTML = ""; return; }
      
      let html = <div class="variations-wrapper">;
      comparisons.forEach(comp => {
        const grossSalesVar = comp.prev.gross_sales ? ((comp.current.gross_sales - comp.prev.gross_sales) / comp.prev.gross_sales) * 100 : 0;
        const netSalesVar = comp.prev.net_sales ? ((comp.current.net_sales - comp.prev.net_sales) / comp.prev.net_sales) * 100 : 0;
        const marginVar = (comp.current.gross_margin_1 - comp.prev.gross_margin_1) * 100;
        const grossProfitVar = comp.prev.gross_profit_1 ? ((comp.current.gross_profit_1 - comp.prev.gross_profit_1) / comp.prev.gross_profit_1) * 100 : 0;
        
        const formatVar = (val) => (val > 0 ? "+" : "") + val.toFixed(1) + "%";
        const getClass = (val) => val > 0 ? "positive-var" : (val < 0 ? "negative-var" : "neutral-var");
        
        html += 
          <div class="variation-card">
            <div class="variation-title">Variación </div>
            <div class="variation-grid">
              <div class="var-item"><span class="var-label">Gross Sales</span><span class="var-val "></span></div>
              <div class="var-item"><span class="var-label">Net Sales</span><span class="var-val "></span></div>
              <div class="var-item"><span class="var-label">Gross Margin</span><span class="var-val "></span></div>
              <div class="var-item"><span class="var-label">Gross Profit</span><span class="var-val "></span></div>
            </div>
          </div>
        ;
      });
      html += </div>;
      container.innerHTML = html;
    }
'''

content = content.replace('    function highlightSelectedPeriod(filters)', func + '\\n    function highlightSelectedPeriod(filters)')

with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
