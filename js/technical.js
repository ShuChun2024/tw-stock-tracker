"use strict";
// ============================================================
// 技術分析摘要
// ============================================================
function renderTechnical(s) {
  const technical =
    s?.technical ||
    s?.technical_analysis ||
    s?.technical_data ||
    {};
  const price =
    technical.close ??
    technical.price ??
    s?.close ??
    s?.price;
  const change =
    technical.change_percent ??
    technical.change_pct ??
    technical.return_pct ??
    s?.change_percent ??
    s?.change_pct;
  const volume =
    technical.volume ??
    s?.volume;
  const ma5 = technical.ma5 ?? technical.MA5 ?? s?.ma5;
  const ma20 = technical.ma20 ?? technical.MA20 ?? s?.ma20;
  const ma60 = technical.ma60 ?? technical.MA60 ?? s?.ma60;
  const rsi = technical.rsi ?? technical.RSI ?? s?.rsi;
  const macd = technical.macd ?? technical.MACD ?? s?.macd;
  const trend =
    technical.trend ??
    technical.signal ??
    technical.status ??
    "—";
  const metrics = [
    metricBox(
      "收盤價",
      fmt(price, 2),
      "",
      "neutral"
    ),
    metricBox(
      "漲跌幅",
      signedPercent(change),
      "",
      trendClass(
        validNumber(change) === null
          ? ""
          : Number(change) > 0
            ? "上漲"
            : Number(change) < 0
              ? "下跌"
              : "中性"
      )
    ),
    metricBox(
      "成交量",
      fmtVolume(volume),
      "",
      "neutral"
    ),
    metricBox(
      "MA5",
      fmt(ma5, 2),
      "",
      "neutral"
    ),
    metricBox(
      "MA20",
      fmt(ma20, 2),
      "",
      "neutral"
    ),
    metricBox(
      "MA60",
      fmt(ma60, 2),
      "",
      "neutral"
    ),
    metricBox(
      "RSI",
      fmt(rsi, 2),
      "",
      "neutral"
    ),
    metricBox(
      "MACD",
      typeof macd === "object"
        ? fmt(macd.value ?? macd.macd, 2)
        : fmt(macd, 2),
      "",
      "neutral"
    ),
    metricBox(
      "技術趨勢",
      trend,
      "",
      trendClass(trend)
    )
  ].join("");
  return `
    <section class="technical-section">
      <div class="section-title">技術面分析</div>
      <div class="metric-grid">${metrics}</div>
    </section>
  `;
}
