import re

with open('docs/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the formatting part of renderVariations
old_format = r'''        const formatMoneyVar = (val) => {
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
        `;'''

new_format = r'''        const formatMoneyVar = (val) => {
          const sign = val > 0 ? "+" : (val < 0 ? "-" : "");
          return sign + compactMoney(Math.abs(val));
        };
        const formatPct = (val) => (val * 100).toFixed(1) + "%";
        const formatPctVar = (val) => (val > 0 ? "+" : "") + val.toFixed(1) + "%";
        const getClass = (val) => val > 0 ? "positive-var" : (val < 0 ? "negative-var" : "neutral-var");
        
        html += `
          <div class="variation-card">
            <div class="variation-title">${comp.label}</div>
            <div class="variation-grid">
              <div class="var-item">
                <span class="var-label">Gross Sales</span>
                <span class="var-val">${compactMoney(comp.current.gross_sales)}</span>
                <span style="font-size: 10px; color: var(--muted); font-weight: 500; margin-top: 1px;">vs ${compactMoney(comp.prev.gross_sales)}</span>
                <span class="${getClass(grossSalesVar)}" style="font-size: 12px; font-weight: 720; margin-top: 4px;">${formatMoneyVar(grossSalesVar)}</span>
              </div>
              <div class="var-item">
                <span class="var-label">Net Sales</span>
                <span class="var-val">${compactMoney(comp.current.net_sales)}</span>
                <span style="font-size: 10px; color: var(--muted); font-weight: 500; margin-top: 1px;">vs ${compactMoney(comp.prev.net_sales)}</span>
                <span class="${getClass(netSalesVar)}" style="font-size: 12px; font-weight: 720; margin-top: 4px;">${formatMoneyVar(netSalesVar)}</span>
              </div>
              <div class="var-item">
                <span class="var-label">Gross Margin</span>
                <span class="var-val">${formatPct(currentGrossMargin)}</span>
                <span style="font-size: 10px; color: var(--muted); font-weight: 500; margin-top: 1px;">vs ${formatPct(prevGrossMargin)}</span>
                <span class="${getClass(marginVar)}" style="font-size: 12px; font-weight: 720; margin-top: 4px;">${formatPctVar(marginVar)}</span>
              </div>
              <div class="var-item">
                <span class="var-label">Gross Profit</span>
                <span class="var-val">${compactMoney(comp.current.gross_profit_1)}</span>
                <span style="font-size: 10px; color: var(--muted); font-weight: 500; margin-top: 1px;">vs ${compactMoney(comp.prev.gross_profit_1)}</span>
                <span class="${getClass(grossProfitVar)}" style="font-size: 12px; font-weight: 720; margin-top: 4px;">${formatMoneyVar(grossProfitVar)}</span>
              </div>
            </div>
          </div>
        `;'''

content = content.replace(old_format, new_format)

with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
