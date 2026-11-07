"use strict";

/* =====================================================
   完整股票明細
   ===================================================== */

function renderDetails(s) {
  const revenue = s.revenue || {};
  const foreign = s.foreign_holding || {};
  const technical = s.technical || {};
  const valuation = s.valuation || {};
  const quality = s.data_quality || {};

  const missing = normalizeMissingItems(
    quality.missing_items
  );

  const revenueAmount = validNumber(revenue.latest_revenue)
    ? Number(revenue.latest_revenue).toLocaleString("zh-TW")
    : "—";

  const foreignPercent = validNumber(foreign.latest_percent)
    ? fmt(foreign.latest_percent, 2) + "%"
    : "—";

  const changePeriods = validNumber(foreign.change_periods)
    ? fmt(foreign.change_periods, 4) + " 個百分點"
    : "—";

  const completeness = quality.complete === true
    ? "完整"
    : quality.complete === false
      ? "不完整"
      : "未標示";

  const valuationStatus = valuation.data_available === true
    ? "可用"
    : (valuation.message || "尚無估值資料");

  const lines = [
    ["分析日期", s.analysis_date || analysisUpdateTime || "尚無資料"],
    ["綜合評分", `${scoreText(s.score)} / 100`],

    ["估值資料日期", valuation.valuation_date || "—"],
    [
      "估值收盤價",
      validNumber(valuation.close_price)
        ? fmt(valuation.close_price, 2) + " 元"
        : "—"
    ],
    [
      "本益比（PE）",
      validNumber(valuation.pe_ratio)
        ? fmt(valuation.pe_ratio, 2) + " 倍"
        : "—"
    ],
    [
      "股價淨值比（PB）",
      validNumber(valuation.pb_ratio)
        ? fmt(valuation.pb_ratio, 2) + " 倍"
        : "—"
    ],
    [
      "現金殖利率",
      validNumber(valuation.dividend_yield)
        ? fmt(valuation.dividend_yield, 2) + "%"
        : "—"
    ],
    ["股利年度", valuation.dividend_year ?? "—"],
    ["財務期別", valuation.financial_period || "—"],
    ["估值資料狀態", valuationStatus],

    ["營收最新月份", revenue.latest_revenue_month || "—"],
    ["營收最新金額", revenueAmount],
    ["營收年增率", signedPercent(revenue.latest_yoy)],
    ["營收趨勢", revenue.trend || "—"],
    ["營收說明", revenue.message || "尚無分析資料"],
    ["營收分數", `${scoreText(revenue.score)} / 40`],

    ["外資持股比例", foreignPercent],
    ["外資持股日期", foreign.latest_date || "—"],
    ["外資期間變化", changePeriods],
    ["外資持股趨勢", foreign.trend || "—"],
    ["外資說明", foreign.message || "尚無分析資料"],
    ["外資持股參考分數", `${scoreText(foreign.score)} / 20`],

    [
      "三大法人籌碼分數",
      `${scoreText(s.chip_score ?? s.score_breakdown?.chip)} / 20`
    ],

    ["技術分數", `${scoreText(technical.score)} / 40`],
    ["技術分析說明", technical.message || "尚無分析資料"],

    ["資料完整性", completeness],
    ["缺少項目", missing.join("、") || "無明確缺項"]
  ];

  return `
    <div class="details">
      ${lines.map(([label, value]) => `
        <div class="detail-line">
          <strong>${escapeHTML(label)}：</strong>
          ${escapeHTML(value)}
        </div>
      `).join("")}
    </div>
  `;
}
