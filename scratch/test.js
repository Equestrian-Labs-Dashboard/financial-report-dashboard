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
          comparisons.push({ label: \FY \ VS FY \\, current: currentTotals, prev: prevTotals });
        } else if (monthsInCurrentYear.length > 0) {
          const currentTotals = sumRows(currentYearRows);
          const prevYearRowsRaw = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear - 1, month: "all", quarter: "all" });
          const prevYearRows = prevYearRowsRaw.filter(r => String(r.month).padStart(2, "0") <= maxMonth);
          const prevTotals = sumRows(prevYearRows);
          comparisons.push({ label: \YTD \ VS YTD \\, current: currentTotals, prev: prevTotals });
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
        comparisons.push({ label: \\ \ VS \ \\, current: currentTotals, prev: prevQTotals });
        
        const sameQPrevYearRows = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear - 1, month: "all", quarter: filters.quarter });
        const sameQPrevYearTotals = sumRows(sameQPrevYearRows);
        comparisons.push({ label: \\ \ VS \ \\, current: currentTotals, prev: sameQPrevYearTotals });
      }
      
      const container = document.getElementById("variationsSection");
      if (!container) return;
      if (comparisons.length === 0) { container.innerHTML = ""; return; }
      
      let html = \<div class="variations-wrapper">\;
      comparisons.forEach(comp => {
        const grossSalesVar = comp.current.gross_sales - comp.prev.gross_sales;
        const netSalesVar = comp.current.net_sales - comp.prev.net_sales;
        
        const currentGrossMargin = comp.current.net_sales ? comp.current.gross_profit_1 / comp.current.net_sales : 0;
        const prevGrossMargin = comp.prev.net_sales ? comp.prev.gross_profit_1 / comp.prev.net_sales : 0;
        const marginVar = (currentGrossMargin - prevGrossMargin) * 100; // in percentage points
        
        const grossProfitVar = comp.current.gross_profit_1 - comp.prev.gross_profit_1;
        
        const formatMoneyVar = (val) => {
          const sign = val > 0 ? "+" : (val < 0 ? "-" : "");
          return sign + "$" + Math.abs(val).toLocaleString("en-US", { maximumFractionDigits: 0 });
        };
        const formatPctVar = (val) => (val > 0 ? "+" : "") + val.toFixed(1) + "%";
        const getClass = (val) => val > 0 ? "positive-var" : (val < 0 ? "negative-var" : "neutral-var");
        
        html += \
          <div class="variation-card">
            <div class="variation-title">\</div>
            <div class="variation-grid">
              <div class="var-item"><span class="var-label">Gross Sales</span><span class="var-val \">\</span></div>
              <div class="var-item"><span class="var-label">Net Sales</span><span class="var-val \">\</span></div>
              <div class="var-item"><span class="var-label">Gross Margin</span><span class="var-val \">\</span></div>
              <div class="var-item"><span class="var-label">Gross Profit</span><span class="var-val \">\</span></div>
            </div>
          </div>
        \;
      });
      html += \</div>\;
      container.innerHTML = html;
    }
