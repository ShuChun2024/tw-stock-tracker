"use strict";

/* =====================================================
   股票估值資料
   ===================================================== */

function renderValuation(s) {
  const valuation = s.valuation || {};

  const available = valuation.data_available === true;

  // 沒有估值資料時，顯示提示而不影響其他分析。
  if (!available) {
    return `
      <section class="section valuation-section">
        <div class="section-title">股票估值</div>
        <div class="valuation-message">
          ${escapeHTML(
            valuation.message || "目前沒有估值資料"
          )}
        </div>
      </section>
    `;
  }

  const closePrice = validNumber(valuation.close_price)
    ? Number(valuation.close_price).toLocaleString("zh-TW", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
      })
    : "—";

  const peRatio = validNumber(valuation.pe_ratio)
    ? fmt(valuation.pe_ratio, 2) + " 倍"
    : "—";

  const pbRatio = validNumber(valuation.pb_ratio)
    ? fmt(valuation.pb_ratio, 2) + " 倍"
    : "—";

  const dividendYield = validNumber(valuation.dividend_yield)
    ? fmt(valuation.dividend_yield, 2) + "%"
    : "—";

  return `
    <section class="section valuation-section">
      <div class="valuation-header">
        <div class="section-title">股票估值</div>
        <div class="valuation-date">
          資料日期：${escapeHTML(
            valuation.valuation_date || "日期未提供"
          )}
        </div>
      </div>

      <div class="metrics">
        <div class="metric">
          <div class="metric-title">收盤價</div>
          <div class="metric-value">
            ${escapeHTML(closePrice)}
          </div>
          <div class="metric-sub">元</div>
        </div>

        <div class="metric">
          <div class="metric-title">本益比（PE）</div>
          <div class="metric-value">
            ${escapeHTML(peRatio)}
          </div>
          <div class="metric-sub">本益比</div>
        </div>

        <div class="metric">
          <div class="metric-title">股價淨值比（PB）</div>
          <div class="metric-value">
            ${escapeHTML(pbRatio)}
          </div>
          <div class="metric-sub">股價淨值比</div>
        </div>

        <div class="metric">
          <div class="metric-title">現金殖利率</div>
          <div class="metric-value">
            ${escapeHTML(dividendYield)}
          </div>
          <div class="metric-sub">
            股利年度：${escapeHTML(
              valuation.dividend_year ?? "—"
            )}
          </div>
        </div>
      </div>

      <div class="valuation-meta">
        財務期別：${escapeHTML(
          valuation.financial_period || "—"
        )}
      </div>
    </section>
  `;
}
