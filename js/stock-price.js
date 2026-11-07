"use strict";

/* =====================================================
   近 5 個交易日行情
   ===================================================== */

let stockPriceMap = new Map();
let stockPriceUpdateTime = "";

/*
 * 讀取 stock_prices.json。
 *
 * 此資料只用於股票卡片的近 5 日行情顯示，
 * 不會新增股票卡片，也不會改變 analysisMap。
 */

async function loadStockPrices() {
  const response = await fetch(
    "./stock_prices.json?t=" + Date.now(),
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
    !Array.isArray(data.stocks)
  ) {
    throw new Error(
      "stock_prices.json 格式不正確，找不到 stocks 陣列。"
    );
  }

  const nextMap = new Map();

  data.stocks.forEach(stock => {
    if (
      !stock ||
      typeof stock !== "object"
    ) {
      return;
    }

    const code = normalizeCode(stock.stock_id);

    if (!code) {
      return;
    }

    nextMap.set(code, stock);
  });

  stockPriceMap = nextMap;
  stockPriceUpdateTime = data.update_time || "";

  return data;
}

/*
 * 格式化行情價格。
 * null、undefined、空字串均顯示為 —，不轉成 0。
 */

function formatStockPrice(value) {
  if (!validNumber(value)) {
    return "—";
  }

  return Number(value).toLocaleString("zh-TW", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

/*
 * 格式化漲跌數值。
 */

function formatStockChange(value) {
  if (!validNumber(value)) {
    return "—";
  }

  const number = Number(value);
  const prefix = number > 0 ? "+" : "";

  return prefix + number.toFixed(2);
}

/*
 * 判斷台股漲跌顏色。
 *
 * 上漲：紅色
 * 下跌：綠色
 * 平盤：中性
 */

function getStockPriceChangeClass(record) {
  if (validNumber(record?.change)) {
    const change = Number(record.change);

    if (change > 0) {
      return "positive";
    }

    if (change < 0) {
      return "negative";
    }

    return "neutral";
  }

  if (validNumber(record?.change_percent)) {
    const percent = Number(record.change_percent);

    if (percent > 0) {
      return "positive";
    }

    if (percent < 0) {
      return "negative";
    }
  }

  return "neutral";
}

/*
 * 顯示單一股票的近 5 個交易日行情。
 */

function renderStockPrice(s) {
  const stockId = normalizeCode(s?.stock_id);

  if (!stockId) {
    return "";
  }

  const stockPrice = stockPriceMap.get(stockId);

  if (
    !stockPrice ||
    !Array.isArray(stockPrice.data) ||
    stockPrice.data.length === 0
  ) {
    return "";
  }

  const market = String(stockPrice.market || "").toUpperCase();

  let marketLabel = "市場未提供";

  if (market === "TWSE") {
    marketLabel = "上市";
  } else if (market === "TPEX") {
    marketLabel = "上櫃";
  } else if (market === "ESB") {
    marketLabel = "興櫃";
  }

  const priceLabel = market === "ESB"
    ? "成交均價"
    : "收盤價";

  const records = stockPrice.data.slice(0, 5);
  const latest = records[0];

  const latestPrice = formatStockPrice(latest.close);
  const latestChange = formatStockChange(latest.change);

  const latestPercent = validNumber(latest.change_percent)
    ? formatStockChange(latest.change_percent) + "%"
    : "—";

  const changeClass = getStockPriceChangeClass(latest);

  return `
    <section class="stock-price-section">

      <div class="stock-price-header">
        <div class="stock-price-title">
          近 5 個交易日行情
        </div>

        <div class="stock-price-market">
          ${escapeHTML(marketLabel)}
        </div>
      </div>

      <div class="stock-price-summary">
        <div class="stock-price-item stock-price-main">
          <div class="stock-price-label">
            最新${escapeHTML(priceLabel)}
          </div>

          <div class="stock-price-value">
            ${escapeHTML(latestPrice)}
          </div>
        </div>

        <div class="stock-price-item">
          <div class="stock-price-label">
            漲跌
          </div>

          <div class="stock-price-value ${changeClass}">
            ${escapeHTML(latestChange)}
          </div>
        </div>

        <div class="stock-price-item">
          <div class="stock-price-label">
            漲跌幅
          </div>

          <div class="stock-price-value ${changeClass}">
            ${escapeHTML(latestPercent)}
          </div>
        </div>
      </div>

      <button
        class="stock-price-toggle"
        type="button"
        aria-expanded="false"
      >
        <span>近 5 個交易日</span>
        <span
          class="toggle-arrow"
          aria-hidden="true"
        >⌄</span>
      </button>

      <div class="stock-price-details">

        <div class="stock-price-table-wrap">
          <table class="stock-price-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>${escapeHTML(priceLabel)}</th>
                <th>漲跌</th>
                <th>漲跌幅</th>
              </tr>
            </thead>

            <tbody>
              ${records.map(record => {
                const rowClass =
                  getStockPriceChangeClass(record);

                const price =
                  formatStockPrice(record.close);

                const change =
                  formatStockChange(record.change);

                const percent =
                  validNumber(record.change_percent)
                    ? formatStockChange(record.change_percent) + "%"
                    : "—";

                return `
                  <tr>
                    <td>
                      ${escapeHTML(record.date || "—")}
                    </td>

                    <td>
                      ${escapeHTML(price)}
                    </td>

                    <td class="${rowClass}">
                      ${escapeHTML(change)}
                    </td>

                    <td class="${rowClass}">
                      ${escapeHTML(percent)}
                    </td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        </div>

        <div class="stock-price-update">
          行情更新時間：
          ${escapeHTML(stockPriceUpdateTime || "資料未提供")}
        </div>

      </div>
    </section>
  `;
}
