"use strict";

// ============================================================
// 技術分析
// 實際資料：technical.ma / rsi / macd / kd / volume / breakout
// ============================================================
function renderTechnical(s) {
  const t = s?.technical || {};
  const ma = t.ma || {};
  const rsi = t.rsi || {};
  const macd = t.macd || {};
  const kd = t.kd || {};
  const volume = t.volume || {};
  const breakout = t.breakout || {};

  function indicator(name, value, sub = "") {
    return `
      <div class="indicator">
        <div class="indicator-name">${escapeHTML(name)}</div>
        <div class="indicator-value">${escapeHTML(value)}</div>
        ${sub
          ? `<div class="indicator-sub">${escapeHTML(sub)}</div>`
          : ""}
      </div>
    `;
  }

  function summaryItem(label, value) {
    return `
      <div class="technical-summary-item">
        <div class="technical-summary-label">${escapeHTML(label)}</div>
        <div class="technical-summary-value">${escapeHTML(value)}</div>
      </div>
    `;
  }

  const close = fmt(t.latest_close, 2);
  const ma5 = fmt(ma.ma5, 2);
  const ma20 = fmt(ma.ma20, 2);
  const ma60 = fmt(ma.ma60, 2);
  const rsiValue = fmt(rsi.value, 2);
  const macdValue = fmt(macd.dif, 4);
  const volumeValue = fmtVolume(volume.today);
  const trend = ma.trend || t.message || "資料不足";

  const details = `
    <div class="technical-details">
      <div class="indicator-grid">
        ${indicator("MA10", fmt(ma.ma10, 2))}
        ${indicator("RSI", rsiValue, rsi.signal || "")}
        ${indicator("MACD DIF", fmt(macd.dif, 4))}
        ${indicator("MACD DEA", fmt(macd.dea, 4))}
        ${indicator("MACD 柱狀值", fmt(macd.histogram, 4))}
        ${indicator("MACD 訊號", macd.signal || "—")}
        ${indicator("KD－K", fmt(kd.k, 2))}
        ${indicator("KD－D", fmt(kd.d, 2))}
        ${indicator("KD 訊號", kd.signal || "—")}
        ${indicator("今日成交量", volumeValue)}
        ${indicator("5 日均量", fmtVolume(volume.avg5))}
        ${indicator(
          "成交量比率",
          validNumber(volume.ratio) === null
            ? "—"
            : fmt(volume.ratio, 2) + " 倍",
          volume.signal || ""
        )}
        ${indicator("20 日最高價", fmt(breakout.high20, 2))}
        ${indicator("20 日最低價", fmt(breakout.low20, 2))}
        ${indicator(
          "距 20 日高點",
          signedPercent(breakout.distance_to_high20_percent)
        )}
        ${indicator(
          "距 20 日低點",
          signedPercent(breakout.distance_to_low20_percent)
        )}
        ${indicator("區間訊號", breakout.signal || "—")}
      </div>

      <div class="technical-details-note">
        技術訊號：${escapeHTML(t.message || trend)}
        <br>
        技術資料日期：${escapeHTML(t.latest_date || "—")}
      </div>
    </div>
  `;

  const hasData = t.data_available !== false &&
    (
      validNumber(t.latest_close) !== null ||
      validNumber(ma.ma5) !== null ||
      validNumber(rsi.value) !== null ||
      validNumber(macd.dif) !== null
    );

  if (!hasData) {
    return `
      <section class="section">
        <div class="section-title">技術面分析</div>
        <div class="empty">目前沒有足夠的技術分析資料</div>
      </section>
    `;
  }

  return `
    <section class="section">
      <div class="section-title">技術面分析</div>

      <div class="technical-summary">
        ${summaryItem("收盤價", close)}
        ${summaryItem("MA5", ma5)}
        ${summaryItem("MA20", ma20)}
        ${summaryItem("MA60", ma60)}
        ${summaryItem("RSI", rsiValue)}
        ${summaryItem("MACD DIF", macdValue)}
        ${summaryItem("成交量", volumeValue)}
        ${summaryItem("技術趨勢", trend)}
      </div>

      <div class="technical-meta">
        資料日期：${escapeHTML(t.latest_date || "—")}
      </div>

      <button
        type="button"
        class="technical-toggle"
        aria-expanded="false"
      >
        <span>查看技術指標明細</span>
        <span class="toggle-arrow">⌄</span>
      </button>

      ${details}
    </section>
  `;
}

