"use strict";

/* =====================================================
   每日大盤收盤行情
   ===================================================== */

let marketData = null;

/*
 * 讀取 market_index.json。
 */

async function loadMarketIndex() {
  const response = await fetch(
    "./market_index.json?t=" + Date.now(),
    {
      cache: "no-store"
    }
  );

  if (!response.ok) {
    throw new Error("HTTP " + response.status);
  }

  const data = await response.json();

  if (
    !data ||
    typeof data !== "object" ||
    !data.market ||
    typeof data.market !== "object"
  ) {
    throw new Error(
      "market_index.json 格式不正確，找不到 market 資料。"
    );
  }

  marketData = data.market;
  renderMarketIndex();

  return data;
}

/*
 * 建立大盤顯示容器。
 * 容器放在 #message 後面，不需要修改 HTML 結構。
 */

function ensureMarketIndexContainer() {
  let container = document.getElementById("marketIndexPanel");

  if (container) {
    return container;
  }

  const message = document.getElementById("message");

  if (!message) {
    return null;
  }

  container = document.createElement("div");
  container.id = "marketIndexPanel";

  message.insertAdjacentElement("afterend", container);

  return container;
}

/*
 * 格式化大盤數值。
 */

function formatMarketNumber(value) {
  if (!validNumber(value)) {
    return "—";
  }

  return Number(value).toLocaleString("zh-TW", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

/*
 * 顯示每日大盤收盤行情。
 */

function renderMarketIndex() {
  const container = ensureMarketIndexContainer();

  if (!container) {
    return;
  }

  if (
    !marketData ||
    typeof marketData !== "object"
  ) {
    container.innerHTML = `
      <div class="market-index-panel">
        <div class="market-index-title">
          台股大盤
        </div>
        <div class="market-index-error">
          大盤資料尚未取得。
        </div>
      </div>
    `;
    return;
  }

  const close = formatMarketNumber(marketData.close);

  const change = validNumber(marketData.change)
    ? (
        Number(marketData.change) > 0 ? "+" : ""
      ) + formatMarketNumber(marketData.change)
    : "—";

  const changePercent = validNumber(marketData.change_percent)
    ? (
        Number(marketData.change_percent) > 0 ? "+" : ""
      ) + Number(marketData.change_percent).toFixed(2) + "%"
    : "—";

  let changeClass = "neutral";

  if (validNumber(marketData.change)) {
    if (Number(marketData.change) > 0) {
      changeClass = "positive";
    } else if (Number(marketData.change) < 0) {
      changeClass = "negative";
    }
  }

  container.innerHTML = `
    <section class="market-index-panel">
      <div class="market-index-header">
        <div>
          <div class="market-index-title">
            台股大盤
          </div>
          <div class="market-index-name">
            ${escapeHTML(marketData.name || "加權指數")}
          </div>
        </div>
        <div class="market-index-date">
          ${escapeHTML(marketData.date || "日期未提供")}
        </div>
      </div>

      <div class="market-index-content">
        <div class="market-index-item market-index-main">
          <div class="market-index-label">
            收盤指數
          </div>
          <div class="market-index-value">
            ${escapeHTML(close)}
          </div>
        </div>

        <div class="market-index-item">
          <div class="market-index-label">
            漲跌點數
          </div>
          <div class="market-index-change-value ${changeClass}">
            ${escapeHTML(change)}
          </div>
        </div>

        <div class="market-index-item">
          <div class="market-index-label">
            漲跌幅
          </div>
          <div class="market-index-change-value ${changeClass}">
            ${escapeHTML(changePercent)}
          </div>
        </div>
      </div>
    </section>
  `;
}
