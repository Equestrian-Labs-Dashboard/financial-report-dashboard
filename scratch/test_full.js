
    let DATA = null;

    let salesTrendChart = null;
    let discountReturnsChart = null;
    let marginTrendChart = null;

    const MONTHS = {
      "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
      "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
    };

    const MONTH_ORDER = [
      "01", "02", "03", "04", "05", "06",
      "07", "08", "09", "10", "11", "12"
    ];

    const QUARTERS = {
      Q1: ["01", "02", "03"], Q2: ["04", "05", "06"],
      Q3: ["07", "08", "09"], Q4: ["10", "11", "12"]
    };

    const QUARTER_LABELS = {
      Q1: "Q1 · Jan–Mar", Q2: "Q2 · Apr–Jun",
      Q3: "Q3 · Jul–Sep", Q4: "Q4 · Oct–Dec"
    };

    const GENERAL_OPEX_PAYROLL_MONTHLY = 40000;
    const GENERAL_OPEX_GA_MONTHLY = 45000;
    const GENERAL_OPEX_SALES_MARKETING_PCT = 0.0662;
    const GENERAL_OPEX_TECHNOLOGY_MONTHLY = 0;
    const CAVALI_OPEX_PAYROLL_QUARTERLY = 14000;
    const CAVALI_OPEX_APPS_QUARTERLY = 3327;
    const CAVALI_OPEX_QUARTERLY = CAVALI_OPEX_PAYROLL_QUARTERLY + CAVALI_OPEX_APPS_QUARTERLY;
    const CHANNEL_OPEX_POOL_ANNUAL = 70000;
    const CONCIERGE_OPEX_BASE_PCT = 0.60;
    const WELLINGTON_OPEX_BASE_PCT = 0.40;
    const CONCIERGE_COMMISSION_PCT = 0.10;
    const WELLINGTON_COMMISSION_PCT = 0.01;
    const WELLINGTON_RENT_MONTHLY = 15000;
    const WELLINGTON_RENT_STORE_SHARE = 0.50;
    const WELLINGTON_PERMIT_ANNUAL = 9000;
    const WELLINGTON_INSURANCE_ANNUAL = 20000;

    function rowHasFinancialActivity(row) {
      return Number(row.total_sales || 0) !== 0 ||
             Number(row.gross_sales || 0) !== 0 ||
             Number(row.net_sales || 0) !== 0;
    }

    function rowSplitName(row) {
      return String((row && (row.location_filter || row.split_filter || row.location_name)) || "").trim().toLowerCase();
    }

    function wellingtonFixedOpex(row) {
      const isMonthlyRow = !!(row && row.month);
      if (isMonthlyRow) {
        return (CHANNEL_OPEX_POOL_ANNUAL * WELLINGTON_OPEX_BASE_PCT / 12) +
               (WELLINGTON_RENT_MONTHLY * WELLINGTON_RENT_STORE_SHARE) +
               (WELLINGTON_PERMIT_ANNUAL / 12) +
               (WELLINGTON_INSURANCE_ANNUAL / 12);
      }

      return (CHANNEL_OPEX_POOL_ANNUAL * WELLINGTON_OPEX_BASE_PCT) +
             (WELLINGTON_RENT_MONTHLY * WELLINGTON_RENT_STORE_SHARE * 12) +
             WELLINGTON_PERMIT_ANNUAL +
             WELLINGTON_INSURANCE_ANNUAL;
    }

    function opexDefinitionForRow(row) {
      const split = rowSplitName(row);
      const viewType = String(row && row.view_type || "brand").toLowerCase();
      if (viewType === "location" && split === "concierge") {
        return "Concierge OPEX estimate: 60% of the $70k annual channel support pool + 10% of Concierge Net Sales as commission estimate.";
      }
      if (viewType === "location" && split === "wellington") {
        return "Wellington OPEX estimate: 40% of the $70k annual channel support pool + 1% of Wellington Net Sales + rent $15k/month x 50% store allocation ($7.5k/month) + permit $9k/year ($750/month) + insurance $20k/year ($1.67k/month).";
      }
      if (viewType === "brand" && isCavaliBrand(row)) {
        return "Cavali OPEX: $17,327 per quarter (approximately $17.5k): Payroll $14,000 + Apps $3,327. Apps combines GSuite, Smartrr, Smartrr Fee, Klaviyo, Shopify and the other recurring apps.";
      }
      return "Main business OPEX estimate: Payroll $40k/month + G&A $45k/month + Sales & Marketing at 6.62% of Gross Sales + Technology $0 for now. Monthly variation comes from Sales & Marketing as a % of revenue.";
    }

    function estimatedMonthlyOpexForRow(row) {
      if (!rowHasFinancialActivity(row)) return 0;

      const viewType = String(row.view_type || "brand").toLowerCase();
      const split = rowSplitName(row);
      const netSales = Number(row.net_sales || 0);

      if (viewType === "location") {
        if (split === "concierge") {
          return (CHANNEL_OPEX_POOL_ANNUAL * CONCIERGE_OPEX_BASE_PCT / 12) + (netSales * CONCIERGE_COMMISSION_PCT);
        }
        if (split === "wellington") {
          return wellingtonFixedOpex(row) + (netSales * WELLINGTON_COMMISSION_PCT);
        }
        return 0;
      }

      // Cavali finance-approved OPEX: $17,327 per quarter.
      if (isCavaliBrand(row)) {
        return CAVALI_OPEX_QUARTERLY / 3;
      }

      // Fallback only. The JSON normally already contains the allocated OPEX.
      return GENERAL_OPEX_PAYROLL_MONTHLY +
             GENERAL_OPEX_GA_MONTHLY +
             GENERAL_OPEX_TECHNOLOGY_MONTHLY +
             (Number(row.gross_sales || 0) * GENERAL_OPEX_SALES_MARKETING_PCT);
    }


    function estimatedNoiForRow(row) {
      const jsonValue = Number(row.estimated_net_operating_income || 0);

      if (jsonValue !== 0) {
        return jsonValue;
      }

      return Number(row.gross_profit_3 || 0) - estimatedMonthlyOpexForRow(row);
    }


    function isCavaliBrand(rowOrBrand) {
      const value = typeof rowOrBrand === "string" ? rowOrBrand : (rowOrBrand && rowOrBrand.brand);
      return String(value || "").toLowerCase() === "cavali";
    }

    function isLocationRow(row) {
      return String((row && row.view_type) || "").toLowerCase() === "location";
    }

    function isWellingtonRow(row) {
      return isLocationRow(row) && String((row && row.location_filter) || "").toLowerCase() === "wellington";
    }

    function displayShippingCharges(row) {
      return Number(row.shipping_charges || 0);
    }

    function displayShippingCost(row) {
      return Number(row.shipping_cost || row.applied_shipping || 0);
    }

    function displayAdsStats(row) {
      if (isCavaliBrand(row) && !isLocationRow(row)) return 0;
      return Number(row.ads_stats_spend || row.marketing_allocated || 0);
    }

    function displayGrossProfit2(row) {
      const direct = Number(row.gross_profit_2 || 0);
      if (direct) return direct;
      return Number(row.gross_profit_1 || 0) - displayShippingCost(row);
    }

    function displayGrossProfit3(row) {
      if (isCavaliBrand(row) && !isLocationRow(row)) {
        return displayGrossProfit2(row);
      }

      const direct = Number(row.gross_profit_3 || 0);
      if (direct) return direct;

      return displayGrossProfit2(row) - displayAdsStats(row);
    }

    function splitIdValues(value) {
      if (!value) return [];
      if (Array.isArray(value)) return value.map(v => String(v || "").trim()).filter(Boolean);
      return String(value || "")
        .replace(/,/g, "|")
        .split("|")
        .map(v => v.trim())
        .filter(v => v && !["0", "nan", "none", "undefined"].includes(v.toLowerCase()));
    }

    function uniqueCountFromRows(rows, field, fallbackField) {
      const values = new Set();
      rows.forEach(row => splitIdValues(row[field]).forEach(v => values.add(v)));
      if (values.size) return values.size;
      return rows.reduce((sum, row) => sum + Number(row[fallbackField] || 0), 0);
    }

    function displayCogs(row) {
      const direct = Number(row.cogs || 0);
      if (direct) return direct;
      const derived = Number(row.net_sales || 0) - Number(row.gross_profit_1 || 0);
      return derived > 0 ? derived : 0;
    }

    function setupTheme() {
      const savedTheme = localStorage.getItem("financialReportTheme") || "dark";
      document.documentElement.setAttribute("data-theme", savedTheme);
      updateThemeButton(savedTheme);

      document.getElementById("themeToggle").addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") || "dark";
        const next = current === "dark" ? "light" : "dark";

        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("financialReportTheme", next);
        updateThemeButton(next);
        renderChartsAgain();
      });
    }

    function updateThemeButton(theme) {
      const button = document.getElementById("themeToggle");
      button.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
    }

    function setupMatrixToggle() {
      const button = document.getElementById("matrixToggle");
      const table = document.getElementById("monthlyTable");

      button.addEventListener("click", () => {
        const isCollapsed = table.classList.toggle("is-collapsed");
        button.textContent = isCollapsed ? "Expand months" : "Collapse months";
      });
    }

    function renderChartsAgain() {
      if (DATA) {
        const selected = getSelectedRows();
        renderSalesTrend(selected.trendRows);
        renderDiscountReturns(selected.trendRows);
        renderMarginTrend(selected.trendRows);
      }
    }

    function money(value) {
      return "$" + Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
    }

    function compactMoney(value) {
      const numberValue = Number(value || 0);
      const absValue = Math.abs(numberValue);
      if (absValue >= 1000000) return "$" + (numberValue / 1000000).toLocaleString("en-US", { maximumFractionDigits: 0 }) + "M";
      if (absValue >= 1000) return "$" + (numberValue / 1000).toLocaleString("en-US", { maximumFractionDigits: 0 }) + "K";
      return "$" + numberValue.toLocaleString("en-US", { maximumFractionDigits: 0 });
    }

    function number(value) {
      return Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
    }

    function compactNumber(value) {
      const numberValue = Number(value || 0);
      const absValue = Math.abs(numberValue);

      if (absValue >= 1000000) {
        return (numberValue / 1000000).toLocaleString("en-US", { maximumFractionDigits: 0 }) + "M";
      }

      if (absValue >= 1000) {
        return (numberValue / 1000).toLocaleString("en-US", { maximumFractionDigits: 0 }) + "K";
      }

      return numberValue.toLocaleString("en-US", { maximumFractionDigits: 0 });
    }

    function percent(value) {
      return Number((Number(value || 0) * 100)).toLocaleString("en-US", { maximumFractionDigits: 0 }) + "%";
    }


    function formatRoas(value) {
      const n = Number(value || 0);
      if (!Number.isFinite(n) || n <= 0) return "0.0x";
      return `${n.toFixed(1)}x`;
    }

    function safeArray(value) {
      return Array.isArray(value) ? value : [];
    }

    function firstNumber(row, keys) {
      for (const key of keys) {
        const value = Number(row && row[key]);
        if (!Number.isNaN(value) && value !== 0) return value;
      }
      return 0;
    }

    function rowReachedCheckout(row) {
      return firstNumber(row, ["sessions_reached_checkout", "reached_checkout", "checkout_reached", "sessions_that_reached_checkout"]);
    }

    function rowCompletedCheckout(row) {
      return firstNumber(row, ["sessions_completed_checkout", "completed_checkout", "checkout_completed", "sessions_that_reached_and_completed_checkout"]);
    }

    function rowCheckoutAbandonments(row) {
      const direct = firstNumber(row, ["checkout_abandonments", "abandoned_checkout_count"]);
      if (direct) return direct;
      return Math.max(rowReachedCheckout(row) - rowCompletedCheckout(row), 0);
    }

    async function loadData() {
      try {
        const response = await fetch("financial_report.json?t=" + Date.now());
        if (!response.ok) throw new Error("Could not load financial_report.json");
        DATA = await response.json();
        document.getElementById("updatedAt").textContent = "Financial Report Dashboard · Last updated: " + new Date(DATA.generated_at).toLocaleString();
        setupFilters();
        setupBrandNav();
        render();
      } catch (error) {
        document.getElementById("dateStrip").textContent = "Error loading report data.";
        document.getElementById("shopifyKpis").innerHTML = `<div class="empty">Could not load docs/financial_report.json. Check GitHub Actions.</div>`;
        console.error(error);
      }
    }


    function normalizeLabel(value) {
      return String(value || "").trim().toLowerCase();
    }

    function rowSplitLabel(row) {
      return String((row && (row.split_filter || row.location_filter || row.location_name)) || "").trim();
    }

    function setupFilters() {
      const brandFilter = document.getElementById("brandFilter");
      const locationFilter = document.getElementById("locationFilter");
      const yearFilter = document.getElementById("yearFilter");
      const monthFilter = document.getElementById("monthFilter");
      const quarterFilter = document.getElementById("quarterFilter");
      const quarterFilterGroup = document.getElementById("quarterFilterGroup");

      brandFilter.innerHTML = `<option value="all">All Brands</option>` + safeArray(DATA.brands_available).map(b => `<option value="${b}">${b}</option>`).join("");
      const availableSplits = Array.from(new Set(["Wellington", "Concierge"]
        .concat(safeArray(DATA.splits_available || []))
        .concat(safeArray(DATA.locations_available || []))))
        .filter(Boolean);
      locationFilter.innerHTML = `<option value="all">All Splits</option>` + availableSplits.map(l => `<option value="${l}">${l}</option>`).join("");
      yearFilter.innerHTML = safeArray(DATA.years_available).map(y => `<option value="${y}">${y}</option>`).join("");
      if (safeArray(DATA.years_available).length > 0) yearFilter.value = Math.max(...safeArray(DATA.years_available));

      monthFilter.innerHTML = `<option value="all">All Months / YTD</option>` + MONTH_ORDER.map(v => `<option value="${v}">${MONTHS[v]}</option>`).join("");
      monthFilter.value = "all";
      quarterFilter.value = "all";
      locationFilter.value = "all";

      function syncFilterVisibility() {
        const isCavali = brandFilter.value === "Cavali";
        const locationGroup = locationFilter.closest(".filter-group");

        quarterFilterGroup.style.display = isCavali ? "flex" : "none";
        if (!isCavali) quarterFilter.value = "all";

        // Wellington and Concierge are Corro-only. Hide Split when Cavali is selected.
        if (locationGroup) locationGroup.style.display = isCavali ? "none" : "flex";
        if (isCavali) locationFilter.value = "all";
      }

      brandFilter.addEventListener("change", () => { syncFilterVisibility(); render(); });
      locationFilter.addEventListener("change", render);
      yearFilter.addEventListener("change", render);
      monthFilter.addEventListener("change", () => { if (monthFilter.value !== "all") quarterFilter.value = "all"; render(); });
      quarterFilter.addEventListener("change", () => { if (quarterFilter.value !== "all") monthFilter.value = "all"; render(); });
      syncFilterVisibility();
    }

    function setupBrandNav() {
      document.querySelectorAll(".brand-nav, .location-nav, .dashboard-nav").forEach(item => {
        item.addEventListener("click", event => {
          event.preventDefault();
          const brandFilter = document.getElementById("brandFilter");
          const locationFilter = document.getElementById("locationFilter");

          if (item.classList.contains("dashboard-nav")) {
            brandFilter.value = "all";
            locationFilter.value = "all";
          } else if (item.classList.contains("brand-nav")) {
            brandFilter.value = item.dataset.brand;
            locationFilter.value = "all";
          } else if (item.classList.contains("location-nav")) {
            // Wellington and Concierge are Corro-only.
            brandFilter.value = "Corro";
            locationFilter.value = item.dataset.location;
          }

          brandFilter.dispatchEvent(new Event("change"));
          locationFilter.dispatchEvent(new Event("change"));
        });
      });
    }

    function updateBrandNavActive(selectedBrand, selectedLocation) {
      const dbNav = document.querySelector(".dashboard-nav");
      if (dbNav) dbNav.classList.toggle("active-view", selectedBrand === "all" && selectedLocation === "all");

      document.querySelectorAll(".brand-nav").forEach(item => {
        item.classList.toggle("active-brand", selectedBrand !== "all" && item.dataset.brand === selectedBrand);
      });

      document.querySelectorAll(".location-nav").forEach(item => {
        item.classList.toggle("active-location", selectedLocation !== "all" && item.dataset.location === selectedLocation);
      });
    }

    function selectedFilters() {
      return {
        brand: document.getElementById("brandFilter").value,
        location: document.getElementById("brandFilter").value === "Cavali"
          ? "all"
          : document.getElementById("locationFilter").value,
        year: Number(document.getElementById("yearFilter").value),
        month: document.getElementById("monthFilter").value,
        quarter: document.getElementById("quarterFilter").value
      };
    }

    function filterRows(rows, filters) {
      const selectedBrand = filters.brand || "all";
      const selectedSplit = filters.location || "all";
      const selectedMonth = filters.month || "all";
      const selectedQuarter = filters.quarter || "all";

      const selectedSplitNorm = normalizeLabel(selectedSplit);

      return rows.filter(row => {
        const rowMonth = String(row.month).padStart(2, "0");
        const viewType = String(row.view_type || "brand").trim().toLowerCase();
        const rowBrand = String(row.brand || "").trim();
        const rowSplit = rowSplitLabel(row);
        const rowSplitNorm = normalizeLabel(rowSplit);

        const brandMatch = selectedBrand === "all" || rowBrand === selectedBrand;
        const splitMatch = selectedSplit === "all"
          ? viewType !== "location"
          : viewType === "location" && rowSplitNorm === selectedSplitNorm;

        return brandMatch &&
               splitMatch &&
               (Number(row.year) === Number(filters.year)) &&
               (selectedMonth === "all" || rowMonth === selectedMonth) &&
               (selectedQuarter === "all" || QUARTERS[selectedQuarter].includes(rowMonth));
      });
    }

    function sumRows(rows) {
      const result = {
        total_sales: 0,
        gross_sales: 0,
        discounts: 0,
        returns: 0,
        discounts_returns: 0,
        discount_pct: 0,
        shipping_charges: 0,
        taxes: 0,
        net_sales: 0,
        cogs: 0,
        gross_profit_1: 0,
        shipping_cost: 0,
        gross_profit_2: 0,
        ads_stats_spend: 0,
        roas: 0,
        gross_profit_3: 0,
        estimated_average_opex: 0,
        estimated_net_operating_income: 0,
        estimated_net_operating_income_pct: 0,
        transactions: 0,
        orders: 0,
        units_sold: 0,
        customers: 0,
        new_customers: 0,
        returning_customers: 0,
        net_gross_ratio: 0,
        sessions_reached_checkout: 0,
        sessions_completed_checkout: 0,
        checkout_abandonments: 0,
        checkout_abandonment_rate: 0,
        _gross_margin_1_weight: 0
      };

      rows.forEach(row => {
        result.total_sales += Number(row.total_sales || 0);
        result.gross_sales += Number(row.gross_sales || 0);
        result.discounts += Number(row.discounts || 0);
        result.returns += Number(row.returns || 0);
        result.discounts_returns += Number(row.discounts_returns || 0);
        result.shipping_charges += displayShippingCharges(row);
        result.taxes += Number(row.taxes || 0);
        result.net_sales += Number(row.net_sales || 0);
        result.cogs += displayCogs(row);
        result.gross_profit_1 += Number(row.gross_profit_1 || 0);
        result._gross_margin_1_weight += Number(row.gross_margin_1 || 0) * Number(row.net_sales || 0);
        result.shipping_cost += displayShippingCost(row);
        result.gross_profit_2 += displayGrossProfit2(row);
        result.ads_stats_spend += displayAdsStats(row);
        result.gross_profit_3 += displayGrossProfit3(row);

        // Use JSON values if they exist; otherwise calculate provisional OPEX live.
        const jsonOpex = Number(row.estimated_average_opex || 0);
        const rowOpex = jsonOpex !== 0 ? jsonOpex : estimatedMonthlyOpexForRow(row);
        result.estimated_average_opex += rowOpex;
        result.estimated_net_operating_income += displayGrossProfit3(row) - rowOpex;

        result.transactions += Number(row.transactions || 0);
        result.orders += Number(row.orders || row.transactions || 0);
        result.units_sold += Number(row.units_sold || 0);
        result.customers += Number(row.customers || 0);
        result.new_customers += Number(row.new_customers || 0);
        result.returning_customers += Number(row.returning_customers || 0);

        result.sessions_reached_checkout += rowReachedCheckout(row);
        result.sessions_completed_checkout += rowCompletedCheckout(row);
        result.checkout_abandonments += rowCheckoutAbandonments(row);
      });

      result.customers = uniqueCountFromRows(rows, "customer_ids", "customers");
      result.new_customers = uniqueCountFromRows(rows, "new_customer_ids", "new_customers");
      result.returning_customers = uniqueCountFromRows(rows, "returning_customer_ids", "returning_customers");

      if (result.sessions_reached_checkout) {
        result.checkout_abandonments = Math.max(
          result.sessions_reached_checkout - result.sessions_completed_checkout,
          0
        );
      }

      result.discount_pct = result.gross_sales ? result.discounts / result.gross_sales : 0;
      result.discounts_returns_pct = result.gross_sales ? result.discounts_returns / result.gross_sales : 0;
      result.gross_margin_1 = result.net_sales ? result._gross_margin_1_weight / result.net_sales : 0;
      result.gross_margin_2 = result.net_sales ? result.gross_profit_2 / result.net_sales : 0;
      result.gross_margin_3 = result.net_sales ? result.gross_profit_3 / result.net_sales : 0;
      result.roas = result.ads_stats_spend ? result.net_sales / result.ads_stats_spend : 0;
      result.net_gross_ratio = result.gross_sales ? result.net_sales / result.gross_sales : 0;
      result.checkout_abandonment_rate = result.sessions_reached_checkout
        ? result.checkout_abandonments / result.sessions_reached_checkout
        : 0;
      result.estimated_net_operating_income_pct = result.net_sales
        ? result.estimated_net_operating_income / result.net_sales
        : 0;

      delete result._gross_margin_1_weight;
      return result;
    }

    function getSelectedRows() {
      const filters = selectedFilters();
      const monthlyRows = safeArray(DATA.shopify_kpis_by_brand_month);
      const yearRows = safeArray(DATA.shopify_kpis_by_brand_year);
      const selectedRows = (filters.month !== "all" || filters.quarter !== "all") ? filterRows(monthlyRows, filters) : filterRows(yearRows, filters);
      const yearlyMonthlyRows = filterRows(monthlyRows, {
        brand: filters.brand,
        location: filters.location,
        year: filters.year,
        month: "all",
        quarter: "all"
      });

      if (filters.location !== "all" && selectedRows.length === 0) {
        const availableForSplit = monthlyRows.filter(row =>
          String(row.brand || "").trim() === filters.brand &&
          normalizeLabel(rowSplitLabel(row)) === normalizeLabel(filters.location) &&
          Number(row.year) === Number(filters.year)
        );
        console.warn("No selected rows for split", filters.location, "available raw monthly split rows:", availableForSplit.length);
      }

      return { filters, selectedRows, trendRows: yearlyMonthlyRows, totals: sumRows(selectedRows) };
    }

    function render() {
      const selected = getSelectedRows();
      const brandText = selected.filters.brand === "all" ? "All Brands" : selected.filters.brand;
      const locationText = selected.filters.location === "all" ? "All Locations" : selected.filters.location;
      const viewText = selected.filters.location === "all" ? brandText : `${brandText} · ${locationText}`;
      updateBrandNavActive(selected.filters.brand, selected.filters.location);

      let periodText = "YTD / All Months";
      if (selected.filters.quarter !== "all") periodText = QUARTER_LABELS[selected.filters.quarter];
      else if (selected.filters.month !== "all") periodText = MONTHS[selected.filters.month];

      document.getElementById("dateStrip").textContent = `${viewText} · ${selected.filters.year} · ${periodText} · Shopify KPIs ✓`;
      document.getElementById("matrixMeta").textContent = `${viewText} · ${selected.filters.year}`;

      renderMonthlyMatrix(selected.trendRows, selected.filters);
      highlightSelectedPeriod(selected.filters);
      renderVariations(selected.filters);
      renderKpis(selected.totals);
      renderSalesTrend(selected.trendRows);
      renderDiscountReturns(selected.trendRows);
      renderMarginTrend(selected.trendRows);
      renderNotes(selected);
      if (selected.filters.location !== "all" && selected.trendRows.length === 0) {
        document.getElementById("notes").innerHTML = `<div class="empty">No data found for ${selected.filters.location}. Check Actions log for Financial transform ${selected.filters.location} rows.</div>`;
      }
    }


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
          comparisons.push({ label: `FY ${currentYear} VS FY ${currentYear - 1}`, current: currentTotals, prev: prevTotals });
        } else if (monthsInCurrentYear.length > 0) {
          const currentTotals = sumRows(currentYearRows);
          const prevYearRowsRaw = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear - 1, month: "all", quarter: "all" });
          const prevYearRows = prevYearRowsRaw.filter(r => String(r.month).padStart(2, "0") <= maxMonth);
          const prevTotals = sumRows(prevYearRows);
          comparisons.push({ label: `YTD ${currentYear} VS YTD ${currentYear - 1}`, current: currentTotals, prev: prevTotals });
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
        comparisons.push({ label: `${filters.quarter} ${currentYear} VS ${prevQ} ${prevQYear}`, current: currentTotals, prev: prevQTotals });
        
        const sameQPrevYearRows = filterRows(allMonthlyRows, { ...baseFilters, year: currentYear - 1, month: "all", quarter: filters.quarter });
        const sameQPrevYearTotals = sumRows(sameQPrevYearRows);
        comparisons.push({ label: `${filters.quarter} ${currentYear} VS ${filters.quarter} ${currentYear - 1}`, current: currentTotals, prev: sameQPrevYearTotals });
      }
      
      const container = document.getElementById("variationsSection");
      if (!container) return;
      if (comparisons.length === 0) { container.innerHTML = ""; return; }
      
      let html = `<div class="variations-wrapper">`;
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
        
        html += `
          <div class="variation-card">
            <div class="variation-title">${comp.label}</div>
            <div class="variation-grid">
              <div class="var-item"><span class="var-label">Gross Sales</span><span class="var-val ${getClass(grossSalesVar)}">${formatMoneyVar(grossSalesVar)}</span></div>
              <div class="var-item"><span class="var-label">Net Sales</span><span class="var-val ${getClass(netSalesVar)}">${formatMoneyVar(netSalesVar)}</span></div>
              <div class="var-item"><span class="var-label">Gross Margin</span><span class="var-val ${getClass(marginVar)}">${formatPctVar(marginVar)}</span></div>
              <div class="var-item"><span class="var-label">Gross Profit</span><span class="var-val ${getClass(grossProfitVar)}">${formatMoneyVar(grossProfitVar)}</span></div>
            </div>
          </div>
        `;
      });
      html += `</div>`;
      container.innerHTML = html;
    }

    function highlightSelectedPeriod(filters) {
      document.querySelectorAll(".month-head").forEach(cell => {
        cell.classList.remove("selected-month");
        if (filters.month !== "all" && cell.dataset.month === filters.month) cell.classList.add("selected-month");
        if (filters.quarter !== "all" && QUARTERS[filters.quarter].includes(cell.dataset.month)) cell.classList.add("selected-month");
      });
    }

    function renderKpis(totals) {
      document.getElementById("shopifyKpis").innerHTML = `
        <div class="kpi-card"><div class="kpi-label">Orders</div><div class="kpi-value">${compactNumber(totals.orders || totals.transactions)}</div><div class="kpi-chip">Shopify</div><div class="kpi-note">Order count</div></div>
        <div class="kpi-card"><div class="kpi-label">Units Sold</div><div class="kpi-value">${compactNumber(totals.units_sold)}</div><div class="kpi-chip">Orders API</div><div class="kpi-note">Line item quantity</div></div>
        <div class="kpi-card"><div class="kpi-label">Customers</div><div class="kpi-value">${compactNumber(totals.customers)}</div><div class="kpi-chip">Unique</div><div class="kpi-note">Unique selected period</div></div>
        <div class="kpi-card"><div class="kpi-label">New Customers</div><div class="kpi-value">${compactNumber(totals.new_customers)}</div><div class="kpi-chip">Calculated</div><div class="kpi-note">First purchase in selected year</div></div>
        <div class="kpi-card"><div class="kpi-label">Returning Customers</div><div class="kpi-value">${compactNumber(totals.returning_customers)}</div><div class="kpi-chip">Calculated</div><div class="kpi-note">Purchased again in selected year</div></div>

        <div class="kpi-card"><div class="kpi-label">Gross Sales</div><div class="kpi-value">${compactMoney(totals.gross_sales)}</div><div class="kpi-chip">Shopify</div><div class="kpi-note">Price × Qty</div></div>
        <div class="kpi-card warning"><div class="kpi-label">Discounts</div><div class="kpi-value-row"><div class="kpi-value">${compactMoney(totals.discounts)}</div><div class="kpi-secondary-value">${percent(totals.discount_pct)}</div></div><div class="kpi-chip">Shopify</div><div class="kpi-note">Amount + % of Gross Sales</div></div>
        <div class="kpi-card warning"><div class="kpi-label">Returns</div><div class="kpi-value">${compactMoney(totals.returns)}</div><div class="kpi-chip">Shopify</div><div class="kpi-note">Returns amount</div></div>
        <div class="kpi-card warning"><div class="kpi-label">Discounts + Returns</div><div class="kpi-value-row"><div class="kpi-value">${compactMoney(totals.discounts_returns)}</div><div class="kpi-secondary-value">${percent(totals.discounts_returns_pct)}</div></div><div class="kpi-chip">Risk</div><div class="kpi-note">Combined amount + %</div></div>
        <div class="kpi-card"><div class="kpi-label">Shipping Income</div><div class="kpi-value">${compactMoney(totals.shipping_charges)}</div><div class="kpi-chip">Shopify</div><div class="kpi-note">Customer-paid shipping</div></div>

        <div class="kpi-card negative"><div class="kpi-label">COGS</div><div class="kpi-value">${compactMoney(totals.cogs)}</div><div class="kpi-chip red">Cost</div><div class="kpi-note">Product cost</div></div>
        <div class="kpi-card positive"><div class="kpi-label">Gross Profit 1</div><div class="kpi-value">${compactMoney(totals.gross_profit_1)}</div><div class="kpi-chip green">Shopify</div><div class="kpi-note">Net Sales - COGS</div></div>
        <div class="kpi-card purple"><div class="kpi-label">Gross Margin 1</div><div class="kpi-value">${percent(totals.gross_margin_1)}</div><div class="kpi-chip">Shopify-derived</div><div class="kpi-note">GP1 / Net Sales</div></div>
        <div class="kpi-card positive"><div class="kpi-label">Gross Profit 2</div><div class="kpi-value">${compactMoney(totals.gross_profit_2)}</div><div class="kpi-chip green">Calculated</div><div class="kpi-note">GP1 - Shipping Cost</div></div>
        <div class="kpi-card purple"><div class="kpi-label">Gross Margin 2 (GM2)</div><div class="kpi-value">${percent(totals.gross_margin_2)}</div><div class="kpi-chip">Calculated</div><div class="kpi-note">GP2 / Net Sales</div></div>

        <div class="kpi-card negative"><div class="kpi-label">Ads / Stats</div><div class="kpi-value">${compactMoney(totals.ads_stats_spend)}</div><div class="kpi-chip red">Spend</div><div class="kpi-note">Marketing spend</div></div>
        <div class="kpi-card purple"><div class="kpi-label">ROAS</div><div class="kpi-value">${formatRoas(totals.roas)}</div><div class="kpi-chip">Calculated</div><div class="kpi-note">Net Sales / Ads Spend</div></div>
        <div class="kpi-card positive"><div class="kpi-label">Gross Profit 3</div><div class="kpi-value">${compactMoney(totals.gross_profit_3)}</div><div class="kpi-chip green">Calculated</div><div class="kpi-note">GP2 - Ads / Stats</div></div>
        <div class="kpi-card purple"><div class="kpi-label">Gross Margin 3 (GM3)</div><div class="kpi-value">${percent(totals.gross_margin_3)}</div><div class="kpi-chip">Calculated</div><div class="kpi-note">GP3 / Net Sales</div></div>
        <div class="kpi-card purple"><div class="kpi-label">Net / Gross Ratio</div><div class="kpi-value">${percent(totals.net_gross_ratio)}</div><div class="kpi-chip">Calculated</div><div class="kpi-note">Net Sales / Gross Sales</div></div>
        <div class="kpi-card purple"><div class="kpi-label">Checkout Abandonment</div><div class="kpi-value">${percent(totals.checkout_abandonment_rate)}</div><div class="kpi-chip">ShopifyQL</div><div class="kpi-note">Reached - Completed / Reached</div></div>
        <div class="kpi-card"><div class="kpi-label">Taxes</div><div class="kpi-value">${compactMoney(totals.taxes)}</div><div class="kpi-chip">Shopify</div><div class="kpi-note">Moved to final row</div></div>
      `;
    }

    function groupByMonth(rows) {
      const grouped = {};

      rows.forEach(row => {
        const month = String(row.month).padStart(2, "0");

        if (!grouped[month]) {
          grouped[month] = {
            month,
            total_sales: 0,
            gross_sales: 0,
            discounts: 0,
            returns: 0,
            discounts_returns: 0,
            discount_pct: 0,
            shipping_charges: 0,
            taxes: 0,
            net_sales: 0,
            cogs: 0,
            gross_profit_1: 0,
            shipping_cost: 0,
            gross_profit_2: 0,
            ads_stats_spend: 0,
            gross_profit_3: 0,
            estimated_average_opex: 0,
            estimated_net_operating_income: 0,
            estimated_net_operating_income_pct: 0,
            transactions: 0,
            orders: 0,
            units_sold: 0,
            customers: 0,
            new_customers: 0,
            returning_customers: 0,
            sessions_reached_checkout: 0,
            sessions_completed_checkout: 0,
            checkout_abandonments: 0,
            checkout_abandonment_rate: 0,
            _customer_ids: new Set(),
            _new_customer_ids: new Set(),
            _returning_customer_ids: new Set()
          };
        }

        grouped[month].total_sales += Number(row.total_sales || 0);
        grouped[month].gross_sales += Number(row.gross_sales || 0);
        grouped[month].discounts += Number(row.discounts || 0);
        grouped[month].returns += Number(row.returns || 0);
        grouped[month].discounts_returns += Number(row.discounts_returns || 0);
        grouped[month].shipping_charges += displayShippingCharges(row);
        grouped[month].taxes += Number(row.taxes || 0);
        grouped[month].net_sales += Number(row.net_sales || 0);
        grouped[month].cogs += displayCogs(row);
        grouped[month].gross_profit_1 += Number(row.gross_profit_1 || 0);
        grouped[month]._gross_margin_1_weight = (grouped[month]._gross_margin_1_weight || 0) + Number(row.gross_margin_1 || 0) * Number(row.net_sales || 0);
        grouped[month].shipping_cost += displayShippingCost(row);
        grouped[month].gross_profit_2 += displayGrossProfit2(row);
        grouped[month].ads_stats_spend += displayAdsStats(row);
        grouped[month].gross_profit_3 += displayGrossProfit3(row);

        const jsonOpex = Number(row.estimated_average_opex || 0);
        const rowOpex = jsonOpex !== 0 ? jsonOpex : estimatedMonthlyOpexForRow(row);
        grouped[month].estimated_average_opex += rowOpex;
        grouped[month].estimated_net_operating_income += displayGrossProfit3(row) - rowOpex;

        grouped[month].transactions += Number(row.transactions || 0);
        grouped[month].orders += Number(row.orders || row.transactions || 0);
        grouped[month].units_sold += Number(row.units_sold || 0);
        grouped[month].customers += Number(row.customers || 0);
        grouped[month].new_customers += Number(row.new_customers || 0);
        grouped[month].returning_customers += Number(row.returning_customers || 0);
        splitIdValues(row.customer_ids).forEach(v => grouped[month]._customer_ids.add(v));
        splitIdValues(row.new_customer_ids).forEach(v => grouped[month]._new_customer_ids.add(v));
        splitIdValues(row.returning_customer_ids).forEach(v => grouped[month]._returning_customer_ids.add(v));

        grouped[month].sessions_reached_checkout += rowReachedCheckout(row);
        grouped[month].sessions_completed_checkout += rowCompletedCheckout(row);
        grouped[month].checkout_abandonments += rowCheckoutAbandonments(row);
      });

      return Object.values(grouped)
        .sort((a, b) => a.month.localeCompare(b.month))
        .map(row => {
          if (row.sessions_reached_checkout) {
            row.checkout_abandonments = Math.max(
              row.sessions_reached_checkout - row.sessions_completed_checkout,
              0
            );
          }

          if (row._customer_ids && row._customer_ids.size) row.customers = row._customer_ids.size;
          if (row._new_customer_ids && row._new_customer_ids.size) row.new_customers = row._new_customer_ids.size;
          if (row._returning_customer_ids && row._returning_customer_ids.size) row.returning_customers = row._returning_customer_ids.size;

          const cleanRow = { ...row };
          delete cleanRow._customer_ids;
          delete cleanRow._new_customer_ids;
          delete cleanRow._returning_customer_ids;

          return {
            ...cleanRow,
            gross_margin_1: row.net_sales ? (row._gross_margin_1_weight || 0) / row.net_sales : 0,
            gross_margin_2: row.net_sales ? row.gross_profit_2 / row.net_sales : 0,
            gross_margin_3: row.net_sales ? row.gross_profit_3 / row.net_sales : 0,
            net_gross_ratio: row.gross_sales ? row.net_sales / row.gross_sales : 0,
            checkout_abandonment_rate: row.sessions_reached_checkout
              ? row.checkout_abandonments / row.sessions_reached_checkout
              : 0,
            estimated_net_operating_income_pct: row.net_sales
              ? row.estimated_net_operating_income / row.net_sales
              : 0,
            discount_pct: row.gross_sales ? row.discounts / row.gross_sales : 0,
            discounts_returns_pct: row.gross_sales ? row.discounts_returns / row.gross_sales : 0
          };
        });
    }

    function renderSalesTrend(rows) {
      if (salesTrendChart) salesTrendChart.destroy();
      const monthly = groupByMonth(rows);
      salesTrendChart = new Chart(document.getElementById("salesTrendChart"), {
        type: "bar",
        data: {
          labels: monthly.map(row => MONTHS[row.month] || row.month),
          datasets: [
            { label: "Gross Sales", data: monthly.map(row => row.gross_sales), backgroundColor: "#3b82f6", borderRadius: 5, maxBarThickness: 36, yAxisID: "y" },
            { label: "Net Sales", data: monthly.map(row => row.net_sales), backgroundColor: "#22c55e", borderRadius: 5, maxBarThickness: 36, yAxisID: "y" },
            { type: "line", label: "Net / Gross Ratio", data: monthly.map(row => row.net_gross_ratio * 100), borderColor: "#a78bfa", backgroundColor: "#a78bfa", tension: 0.35, pointRadius: 2, borderWidth: 2, yAxisID: "y1" }
          ]
        },
        options: chartOptionsMoneyWithRatio()
      });
    }

    function renderDiscountReturns(rows) {
      if (discountReturnsChart) discountReturnsChart.destroy();
      const monthly = groupByMonth(rows);
      discountReturnsChart = new Chart(document.getElementById("discountReturnsChart"), {
        type: "line",
        data: {
          labels: monthly.map(row => MONTHS[row.month] || row.month),
          datasets: [
            { label: "Discounts", data: monthly.map(row => row.discounts), borderColor: "#f59e0b", backgroundColor: "#f59e0b", tension: 0.35, pointRadius: 2, borderWidth: 2, yAxisID: "y" },
            { label: "% Discounts", data: monthly.map(row => row.discount_pct * 100), borderColor: "#22c55e", backgroundColor: "#22c55e", tension: 0.35, pointRadius: 2, borderWidth: 2, yAxisID: "y1" },
            { label: "% Discount + Returns", data: monthly.map(row => row.discounts_returns_pct * 100), borderColor: "#a78bfa", backgroundColor: "#a78bfa", tension: 0.35, pointRadius: 2, borderWidth: 2, yAxisID: "y1" }
          ]
        },
        options: chartOptionsMoneyWithRatio(true)
      });
    }

    function renderMarginTrend(rows) {
      if (marginTrendChart) marginTrendChart.destroy();
      const monthly = groupByMonth(rows);
      marginTrendChart = new Chart(document.getElementById("marginTrendChart"), {
        type: "line",
        data: {
          labels: monthly.map(row => MONTHS[row.month] || row.month),
          datasets: [
            { label: "Gross Margin 1", data: monthly.map(row => row.gross_margin_1 * 100), borderColor: "#3b82f6", backgroundColor: "#3b82f6", tension: 0.35, pointRadius: 2, borderWidth: 2 },
            { label: "Gross Margin 2 (GM2)", data: monthly.map(row => row.gross_margin_2 * 100), borderColor: "#22c55e", backgroundColor: "#22c55e", tension: 0.35, pointRadius: 2, borderWidth: 2 },
            { label: "Gross Margin 3 (GM3)", data: monthly.map(row => row.gross_margin_3 * 100), borderColor: "#a78bfa", backgroundColor: "#a78bfa", tension: 0.35, pointRadius: 2, borderWidth: 2 }
          ]
        },
        options: chartOptionsPercent()
      });
    }

    function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

    function chartOptionsMoneyWithRatio(showLegend = true) {
      return {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: showLegend, position: "bottom", labels: { color: cssVar("--muted"), font: { size: 10 }, boxWidth: 10 } },
          tooltip: { callbacks: { label: c => c.dataset.yAxisID === "y1" ? `${c.dataset.label}: ${Number(c.raw || 0).toFixed(0)}%` : `${c.dataset.label}: ${money(c.raw)}` } }
        },
        scales: {
          x: { grid: { color: "rgba(127,154,183,0.10)" }, ticks: { color: cssVar("--muted"), font: { size: 10 } } },
          y: { beginAtZero: true, position: "left", grid: { color: "rgba(127,154,183,0.14)" }, ticks: { color: cssVar("--muted"), font: { size: 10 }, callback: v => compactMoney(v) } },
          y1: { beginAtZero: true, position: "right", grid: { drawOnChartArea: false }, ticks: { color: cssVar("--muted"), font: { size: 10 }, callback: v => v + "%" } }
        }
      };
    }

    function chartOptionsPercent() {
      return {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { color: cssVar("--muted"), font: { size: 10 }, boxWidth: 10 } } },
        scales: {
          x: { grid: { color: "rgba(127,154,183,0.10)" }, ticks: { color: cssVar("--muted"), font: { size: 10 } } },
          y: { beginAtZero: true, grid: { color: "rgba(127,154,183,0.14)" }, ticks: { color: cssVar("--muted"), font: { size: 10 }, callback: v => v + "%" } }
        }
      };
    }

    function renderMonthlyMatrix(rows, filters) {
      const lookup = {};
      groupByMonth(rows).forEach(r => { lookup[r.month] = r; });
      const isQuarterSelected = filters && filters.quarter !== "all";
      const monthKeys = isQuarterSelected ? QUARTERS[filters.quarter] : MONTH_ORDER;
      const quarterKeys = isQuarterSelected ? [filters.quarter] : ["Q1", "Q2", "Q3", "Q4"];

      const table = document.getElementById("monthlyTable");
      const toggle = document.getElementById("matrixToggle");
      if (isQuarterSelected) { table.classList.remove("is-collapsed"); toggle.style.display = "none"; }
      else { toggle.style.display = "inline-flex"; }

      const monthHeaders = monthKeys.map(k => `<th class="right month-head monthly-detail${(isQuarterSelected || filters.month === k) ? ' selected-month' : ''}" data-month="${k}">${MONTHS[k]}</th>`).join("");
      const quarterHeaders = quarterKeys.map(k => `<th class="right quarter-col${(isQuarterSelected && k === filters.quarter) ? ' selected-month' : ''}">${k}</th>`).join("");

      document.getElementById("monthlyMatrixHead").innerHTML = `<tr><th class="sticky-kpi">KPI</th>${monthHeaders}<th class="right total-col">YTD</th>${quarterHeaders}</tr>`;

      const metrics = [
        { key: "gross_sales", label: "Gross Sales", formatter: money },
        { key: "discounts", label: "Discounts", formatter: money },
        { key: "discount_pct", label: "% Discounts", formatter: percent },
        { key: "returns", label: "Returns", formatter: money },
        { key: "discounts_returns_pct", label: "% Discount + Returns", formatter: percent },
        { key: "shipping_charges", label: "Shipping Income", formatter: money },
        { key: "net_sales", label: "Net Sales", formatter: money },
        { key: "cogs", label: "COGS", formatter: money },
        { key: "gross_profit_1", label: "Gross Profit 1", formatter: money },
        { key: "gross_margin_1", label: "Gross Margin 1", formatter: percent },
        { key: "shipping_cost", label: "Shipping Cost", formatter: money },
        { key: "gross_profit_2", label: "Gross Profit 2", formatter: money },
        { key: "gross_margin_2", label: "Gross Margin 2 (GM2)", formatter: percent },
        { key: "ads_stats_spend", label: "Ads / Stats", formatter: money },
        { key: "roas", label: "ROAS", formatter: formatRoas },
        { key: "gross_profit_3", label: "Gross Profit 3", formatter: money },
        { key: "gross_margin_3", label: "Gross Margin 3 (GM3)", formatter: percent },
        { key: "net_gross_ratio", label: "Net / Gross Ratio", formatter: percent },
        { key: "checkout_abandonment_rate", label: "Checkout Abandonment Rate", formatter: percent },
        { key: "estimated_average_opex", label: "Estimated Average OPEX", formatter: money },
        { key: "estimated_net_operating_income", label: "Estimated Net Operating Income", formatter: money },
        { key: "estimated_net_operating_income_pct", label: "Estimated Net Operating Income %", formatter: percent },
        { key: "taxes", label: "Taxes", formatter: money },
        { key: "opex_definition", label: "OPEX Assumptions", formatter: value => value, isNote: true }
      ];

      const ytyTotals = sumRows(rows);
      const html = metrics.map(m => {
        if (m.isNote) {
          const note = opexDefinitionForRow(rows[0] || {});
          const colspan = monthKeys.length + quarterKeys.length + 2;
          return `<tr class="opex-definition-row"><td class="sticky-kpi"><strong>${m.label}</strong></td><td colspan="${colspan - 1}">${note}</td></tr>`;
        }

        const monthCells = monthKeys.map(k => {
          const r = lookup[k];
          const v = r ? r[m.key] : 0;
          return `<td class="right monthly-detail${(isQuarterSelected || filters.month === k) ? ' selected-month' : ''}">${m.formatter(v)}</td>`;
        }).join("");

        const ytyValue = ytyTotals[m.key];
        const quarterCells = quarterKeys.map(qk => {
          const qRows = rows.filter(row => QUARTERS[qk].includes(String(row.month).padStart(2, "0")));
          const qTotals = sumRows(qRows);
          return `<td class="right quarter-col${(isQuarterSelected && qk === filters.quarter) ? ' selected-month' : ''}">${m.formatter(qTotals[m.key])}</td>`;
        }).join("");

        return `<tr><td class="sticky-kpi">${m.label}</td>${monthCells}<td class="right total-col">${m.formatter(ytyValue)}</td>${quarterCells}</tr>`;
      }).join("");

      document.getElementById("monthlyMatrix").innerHTML = html;
    }

    function renderNotes(selected) {
      const totals = selected.totals;
      const brandText = selected.filters.brand === "all" ? "all brands" : selected.filters.brand;
      const locationText = selected.filters.location === "all" ? "all locations" : selected.filters.location;
      const viewText = selected.filters.location === "all" ? brandText : `${brandText} · ${locationText}`;
      let periodText = "all months";
      if (selected.filters.quarter !== "all") periodText = QUARTER_LABELS[selected.filters.quarter];
      else if (selected.filters.month !== "all") periodText = MONTHS[selected.filters.month];

      document.getElementById("executiveNotes").innerHTML = `
        <li><span class="note-dot"></span><span>Selected Shopify view: <strong>${viewText}</strong>, <strong>${selected.filters.year}</strong>, <strong>${periodText}</strong>.</span></li>
        <li><span class="note-dot"></span><span>Gross Sales are <strong>${money(totals.gross_sales)}</strong> and Net Sales are <strong>${money(totals.net_sales)}</strong>.</span></li>
        <li><span class="note-dot"></span><span>Orders: <strong>${number(totals.orders || totals.transactions)}</strong>, Units Sold: <strong>${number(totals.units_sold)}</strong>, Customers: <strong>${number(totals.customers)}</strong>.</span></li>
        <li><span class="note-dot"></span><span>Discounts + Returns represent <strong>${percent(totals.discounts_returns_pct)}</strong> of Gross Sales.</span></li>
        <li><span class="note-dot"></span><span>Net / Gross Ratio is <strong>${percent(totals.net_gross_ratio)}</strong>. Checkout Abandonment Rate is <strong>${percent(totals.checkout_abandonment_rate)}</strong>.</span></li>
        <li><span class="note-dot"></span><span>OPEX assumption: <strong>${opexDefinitionForRow((selected.selectedRows || [])[0] || {})}</strong></span></li>
      `;
    }

    setupTheme();
    setupMatrixToggle();
    loadData();
  