"use strict";
// ============================================================
// 三大法人資料格式化
// ============================================================
function institutionalMetricText(item) {
  if (item === null || item === undefined) {
    return "—";
  }
  if (typeof item !== "object") {
    return String(item);
  }
  const value =
    item.value ??
    item.amount ??
    item.net_buy_sell ??
    item.net ??
    item.score;
  const unit = item.unit ? String(item.unit) : "";
  if (value === null || value === undefined || value === "") {
    return item.label || item.name || item.status || "—";
  }
  const number = validNumber(value);
  if (number === null) {
    return String(value);
  }
  const prefix = number > 0 ? "+" : "";
  return prefix + fmt(number, 2) + unit;
}
// ============================================================
// 三大法人摘要
// ============================================================
function renderInstitutional(s) {
  const institutional =
    s?.institutional ||
    s?.institutional_investors ||
    s?.institutional_data ||
    {};
  const items = [
    {
      label: "外資",
      data: institutional.foreign ??
        institutional.foreign_investor ??
        institutional.foreign_net_buy
    },
    {
      label: "投信",
      data: institutional.trust ??
        institutional.investment_trust ??
        institutional.trust_net_buy
    },
    {
      label: "自營商",
      data: institutional.dealer ??
        institutional.dealers ??
        institutional.dealer_net_buy
    }
  ];
  const hasData = items.some(entry =>
    entry.data !== undefined &&
    entry.data !== null
  );
  const summary = hasData
    ? items.map(entry => {
        return metricBox(
          entry.label,
          institutionalMetricText(entry.data),
          "",
          trendClass(
            typeof entry.data === "object"
              ? entry.data?.trend ?? entry.data?.status ?? ""
              : entry.data
          )
        );
      }).join("")
    : `<div class="empty">目前沒有三大法人明細資料</div>`;
  return `
    <section class="institutional-section">
      <div class="section-title">三大法人籌碼</div>
      <div class="metric-grid">${summary}</div>
    </section>
  `;
}
