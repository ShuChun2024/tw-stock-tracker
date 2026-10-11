"use strict";

// ============================================================
// 三大法人資料
// 實際資料：institutional.foreign / trust / dealer
// 金額單位：張
// ============================================================
function renderInstitutional(s) {
  const data = s?.institutional || {};

  const investors = [
    { key: "foreign", label: "外資" },
    { key: "trust", label: "投信" },
    { key: "dealer", label: "自營商" }
  ];

  function netText(value) {
    const number = validNumber(value);

    if (number === null) {
      return "—";
    }

    const prefix = number > 0 ? "+" : "";
    return prefix + fmt(number, 1) + " 張";
  }

  function investorCard(investor) {
    const item = data[investor.key] || {};
    const trend = item.trend || "資料不足";

    return `
      <div class="institutional-item">
        <div class="institutional-label">
          ${escapeHTML(investor.label)}
        </div>
        <div class="institutional-value ${trendClass(trend)}">
          ${escapeHTML(netText(item.latest_net_lots))}
        </div>
        <div class="institutional-sub">
          ${escapeHTML(trend)}
        </div>
      </div>
    `;
  }

  const hasData = data.data_available !== false &&
    investors.some(({ key }) => {
      const item = data[key];
      return item && (
        validNumber(item.latest_net_lots) !== null ||
        validNumber(item.net_5d_lots) !== null ||
        validNumber(item.net_20d_lots) !== null
      );
    });

  if (!hasData) {
    return `
      <section class="section">
        <div class="section-title">三大法人籌碼</div>
        <div class="empty">目前沒有三大法人明細資料</div>
      </section>
    `;
  }

  const tableRows = investors.map(investor => {
    const item = data[investor.key] || {};

    return `
      <tr>
        <td>${escapeHTML(investor.label)}</td>
        <td>${escapeHTML(netText(item.latest_net_lots))}</td>
        <td>${escapeHTML(netText(item.net_5d_lots))}</td>
        <td>${escapeHTML(netText(item.net_20d_lots))}</td>
      </tr>
    `;
  }).join("");

  const details = `
    <div class="institutional-details">
      <table class="institutional-table">
        <thead>
          <tr>
            <th>法人</th>
            <th>最新</th>
            <th>近 5 日</th>
            <th>近 20 日</th>
          </tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>

      <div class="institutional-meta">
        資料日期：${escapeHTML(data.latest_date || "—")}
      </div>

      ${investors.map(investor => {
        const item = data[investor.key] || {};

        return `
          <div class="detail-line">
            ${escapeHTML(investor.label)}：
            ${escapeHTML(item.trend || "資料不足")}
            ／連續買賣超 ${escapeHTML(
              item.consecutive_days == null
                ? "—"
                : String(item.consecutive_days)
            )} 日
          </div>
        `;
      }).join("")}

      <div class="institutional-summary-text">
        ${escapeHTML(data.summary || data.message || "—")}
      </div>

      <div class="institutional-note">
        買賣超正數代表買超，負數代表賣超。法人數據以 analysis.json 為準。
      </div>
    </div>
  `;

  return `
    <section class="section">
      <div class="section-title">三大法人籌碼</div>

      <div class="institutional-summary">
        ${investors.map(investorCard).join("")}
      </div>

      <button
        type="button"
        class="institutional-toggle"
        aria-expanded="false"
      >
        <span>查看法人明細</span>
        <span class="toggle-arrow">⌄</span>
      </button>

      ${details}
    </section>
  `;
}
