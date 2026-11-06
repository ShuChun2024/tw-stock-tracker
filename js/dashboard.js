"use strict";

/* =====================================================
   9. 股票估值資料
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

/* =====================================================
   10. 完整股票明細
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

/* =====================================================
   11. 首頁卡片及展開／縮合
   ===================================================== */

function bindToggleButtons(
  grid,
  selector,
  panelClass,
  openText,
  closeText
) {
  grid.querySelectorAll(selector).forEach(button => {
    button.addEventListener("click", () => {
      const panel = button.nextElementSibling;

      if (
        !panel ||
        !panel.classList.contains(panelClass)
      ) {
        return;
      }

      const opened = panel.classList.toggle("open");

      button.setAttribute(
        "aria-expanded",
        String(opened)
      );

      const label = button.querySelector("span:first-child");
      const arrow = button.querySelector(".toggle-arrow");

      if (label) {
        label.textContent = opened ? closeText : openText;
      }

      if (arrow) {
        arrow.textContent = opened ? "⌃" : "⌄";
      }
    });
  });
}

/* =====================================================
   11-1. 消息面資料
   ===================================================== */

let eventData = [];

/*
 * 將目前已載入的 events.json 資料，
 * 渲染到 render() 產生的各股票卡片。
 *
 * event.js 負責：
 * - 讀取 events.json
 * - renderEvents()
 * - 消息內容格式
 *
 * dashboard.js 只負責：
 * - 在股票卡片建立容器
 * - 把目前股票代碼交給 event.js
 */

function renderEventPanels() {
  if (
    !Array.isArray(eventData) ||
    !window.StockEvents ||
    typeof window.StockEvents.renderEvents !== "function"
  ) {
    return;
  }

  eventData.forEach(event => {
    const stockId = normalizeCode(event?.stock_id);

    if (!stockId) {
      return;
    }

    const container = document.getElementById(
      `event-panel-${stockId}`
    );

    if (!container) {
      return;
    }

    StockEvents.renderEvents(stockId, eventData);
  });
}

/* =====================================================
   11-2. 每日大盤收盤行情
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
 * 容器放在 #message 後面，不需要修改 index.html。
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

/* =====================================================
   11-3. 近 5 個交易日行情
   ===================================================== */

let stockPriceMap = new Map();
let stockPriceUpdateTime = "";

/*
 * 讀取 stock_prices.json。
 *
 * 此資料只用於股票卡片的近 5 日行情顯示，
 * 不會新增股票卡片，也不會改變 analysisMap。
 *
 * 讀取失敗時由 refreshAnalysis() 個別處理，
 * 不影響 analysis.json。
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
 * 台灣股市慣例：
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
 *
 * 注意：
 * - 以 analysis.json 的股票卡片為主。
 * - stock_prices.json 只提供行情資料。
 * - 不使用 stock_prices.json 的 stock_name 作為顯示名稱。
 * - ESB 使用成交均價，其餘市場使用收盤價。
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

/* =====================================================
   11-4. 首頁股票卡片
   ===================================================== */

function render() {
  const keyword = document
    .getElementById("searchInput")
    .value
    .trim()
    .toLowerCase();

  const sort = document.getElementById("sortSelect").value;

  const watchlistNames = getWatchlistNames();

  let stocks = Array.from(analysisMap.values()).map(result => ({
    ...getStockDisplayInfo(result, watchlistNames),
    analysis: result
  }));

  /* ---------------------------------------------------
     搜尋
     --------------------------------------------------- */

  stocks = stocks.filter(item => {
    const s = item.analysis || {};

    const text = [
      item.stock_id,
      item.short_name,
      item.company_name,
      s.stock_id,
      s.stock_name,
      s.status
    ]
      .join(" ")
      .toLowerCase();

    return text.includes(keyword);
  });

  /* ---------------------------------------------------
     排序
     --------------------------------------------------- */

  stocks.sort((a, b) => {
    if (sort === "name") {
      return String(a.short_name || a.stock_id).localeCompare(
        String(b.short_name || b.stock_id),
        "zh-Hant"
      );
    }

    if (
      sort === "scoreDesc" ||
      sort === "scoreAsc"
    ) {
      const av = validNumber(a.analysis?.score)
        ? Number(a.analysis.score)
        : null;

      const bv = validNumber(b.analysis?.score)
        ? Number(b.analysis.score)
        : null;

      if (av === null && bv !== null) {
        return 1;
      }

      if (av !== null && bv === null) {
        return -1;
      }

      if (av === null && bv === null) {
        return a.stock_id.localeCompare(b.stock_id);
      }

      return sort === "scoreDesc"
        ? bv - av
        : av - bv;
    }

    return a.stock_id.localeCompare(b.stock_id);
  });

  const grid = document.getElementById("stockGrid");

  /* ---------------------------------------------------
     無資料
     --------------------------------------------------- */

  if (!stocks.length) {
    grid.innerHTML =
      '<div class="empty">目前沒有符合搜尋條件的分析結果。</div>';
    return;
  }

  /* ---------------------------------------------------
     股票卡片
     --------------------------------------------------- */

  grid.innerHTML = stocks.map(item => {
    const s = item.analysis || {};
    const revenue = s.revenue || {};
    const foreign = s.foreign_holding || {};
    const quality = s.data_quality || {};

    const missing = normalizeMissingItems(
      quality.missing_items
    );

    const revenueValue = validNumber(revenue.latest_yoy)
      ? signedPercent(revenue.latest_yoy)
      : "資料不足";

    const foreignValue = validNumber(foreign.latest_percent)
      ? fmt(foreign.latest_percent) + "%"
      : "資料不足";

    const qualityText =
      quality.complete === false ||
      missing.length
        ? "資料品質提醒：" + (
            missing.length
              ? "缺少 " + missing.join("、")
              : "部分資料不完整"
          )
        : "";

    return `
      <article class="stock-card">
        <div class="stock-header">
          <div>
            <div class="stock-id">
              ${escapeHTML(item.stock_id)}
            </div>
            <div class="company-short">
              ${escapeHTML(item.short_name || "名稱待確認")}
            </div>
            <div class="company-full">
              ${escapeHTML(item.company_name || "公司全名待確認")}
            </div>
          </div>

          <span class="status">
            ${escapeHTML(scoreStatus(s))}
          </span>
        </div>

        <div class="score-area">
          <div class="score ${scoreColor(s.score)}">
            ${escapeHTML(scoreText(s.score))}
          </div>
          <div>
            <div class="score-label">
              綜合評分 / 100
            </div>
            <div class="score-label">
              ${escapeHTML(s.status || scoreStatus(s))}
            </div>
          </div>
        </div>

        <div class="metrics">
          <div class="metric">
            <div class="metric-title">
              最新營收年增率
            </div>
            <div class="metric-value ${trendClass(revenue.trend)}">
              ${escapeHTML(revenueValue)}
            </div>
            <div class="metric-sub">
              ${escapeHTML(revenue.latest_revenue_month || "")}
            </div>
          </div>

          <div class="metric">
            <div class="metric-title">
              外資持股比例
            </div>
            <div class="metric-value ${trendClass(foreign.trend)}">
              ${escapeHTML(foreignValue)}
            </div>
            <div class="metric-sub">
              ${escapeHTML(foreign.latest_date || "")}
            </div>
          </div>
        </div>

        ${renderStockPrice(s)}

        ${renderValuation(s)}

        ${renderScoreBreakdown(s)}
        ${renderInstitutional(s)}
        ${renderTechnical(s)}

        <!-- 消息面 -->
        <div
          class="event-panel"
          id="event-panel-${escapeHTML(item.stock_id)}"
          data-event-stock="${escapeHTML(item.stock_id)}"
        ></div>

        ${
          qualityText
            ? `<div class="quality">${escapeHTML(qualityText)}</div>`
            : ""
        }

        <button
          class="detail-button"
          type="button"
          aria-expanded="false"
        >
          <span>查看詳細資料</span>
          <span
            class="toggle-arrow"
            aria-hidden="true"
          >⌄</span>
        </button>

        ${renderDetails(s)}
      </article>
    `;
  }).join("");

  /* ---------------------------------------------------
     近 5 個交易日行情
     --------------------------------------------------- */

  bindToggleButtons(
    grid,
    ".stock-price-toggle",
    "stock-price-details",
    "近 5 個交易日",
    "近 5 個交易日"
  );

  /* ---------------------------------------------------
     三大法人
     --------------------------------------------------- */

  bindToggleButtons(
    grid,
    ".institutional-toggle",
    "institutional-details",
    "展開三大法人詳細資料",
    "收合三大法人詳細資料"
  );

  /* ---------------------------------------------------
     技術分析
     --------------------------------------------------- */

  bindToggleButtons(
    grid,
    ".technical-toggle",
    "technical-details",
    "展開技術分析詳細資料",
    "收合技術分析詳細資料"
  );

  /* ---------------------------------------------------
     完整股票明細
     --------------------------------------------------- */

  bindToggleButtons(
    grid,
    ".detail-button",
    "details",
    "查看詳細資料",
    "收合詳細資料"
  );

  /*
   * render() 每次因為搜尋或排序重新建立股票卡片，
   * 因此重新把已載入的消息資料放回各股票卡片。
   */

  renderEventPanels();
}

/* =====================================================
   12. 讀取 analysis.json
   ===================================================== */

async function refreshAnalysis() {
  if (loading) {
    return;
  }

  loading = true;

  const button = document.getElementById("refreshBtn");
  const message = document.getElementById("message");

  button.disabled = true;
  button.textContent = "讀取中…";
  message.textContent = "正在讀取最新分析資料…";

  /*
   * 每次重新整理時，先暫時顯示載入訊息。
   */

  message.style.display = "";

  try {
    const response = await fetch(
      "./analysis.json?t=" + Date.now(),
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }

    const data = await response.json();

    const stocks = Array.isArray(data)
      ? data
      : data.stocks;

    if (!Array.isArray(stocks)) {
      throw new Error(
        "analysis.json 格式不正確，找不到股票分析陣列。"
      );
    }

    const nextMap = new Map();

    stocks.forEach(stock => {
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

      nextMap.set(code, {
        ...stock,
        stock_id: code
      });
    });

    analysisMap = nextMap;

    analysisUpdateTime = (
      !Array.isArray(data) &&
      (
        data.update_time ||
        data.analysis_date
      )
    ) || "";

    document.getElementById("updateTime").textContent =
      "分析資料更新時間：" +
      (analysisUpdateTime || "資料未提供");

    /*
     * 隱藏原本的分析統計訊息。
     */

    message.textContent = "";
    message.style.display = "none";

    /*
     * 讀取 stock_prices.json。
     *
     * 行情資料失敗不影響 analysis.json。
     * 如果讀取失敗，清空行情 Map，
     * 避免畫面繼續顯示舊的行情資料。
     */

    try {
      await loadStockPrices();
    } catch (priceError) {
      console.error(
        "stock_prices.json 載入失敗：",
        priceError
      );

      stockPriceMap = new Map();
      stockPriceUpdateTime = "";
    }

    /*
     * 股票分析及行情資料準備完成後，
     * 一次渲染股票卡片。
     *
     * 每次 render() 都會重新建立卡片，
     * 所有展開面板自然回到預設收合狀態。
     */

    render();

    /*
     * 讀取 market_index.json。
     *
     * 大盤資料讀取失敗不影響原本股票分析的顯示。
     */

    try {
      await loadMarketIndex();
    } catch (marketError) {
      console.error(
        "market_index.json 載入失敗：",
        marketError
      );

      marketData = null;

      const marketContainer = ensureMarketIndexContainer();

      if (marketContainer) {
        marketContainer.innerHTML = `
          <div class="market-index-panel">
            <div class="market-index-title">
              台股大盤
            </div>
            <div class="market-index-error">
              大盤資料載入失敗：
              ${escapeHTML(marketError.message)}
            </div>
          </div>
        `;
      }
    }

    /*
     * 再讀取 events.json。
     *
     * 消息面讀取失敗不影響原本 analysis.json 的顯示。
     */

    if (
      window.StockEvents &&
      typeof window.StockEvents.loadEventData === "function"
    ) {
      try {
        const eventResult =
          await window.StockEvents.loadEventData();

        eventData = Array.isArray(eventResult?.events)
          ? eventResult.events
          : [];

        renderEventPanels();
      } catch (eventError) {
        console.error(
          "events.json 載入失敗：",
          eventError
        );

        eventData = [];

        document
          .querySelectorAll("[data-event-stock]")
          .forEach(container => {
            container.innerHTML =
              `<div class="event-error">消息資料載入失敗：${escapeHTML(eventError.message)}</div>`;
          });
      }
    }
  } catch (error) {
    message.style.display = "";

    message.textContent =
      "讀取分析資料失敗：" +
      error.message +
      "\n請確認 analysis.json 已成功發布，且 JSON 格式正確。";

    console.error("analysis.json 載入失敗：", error);
  } finally {
    loading = false;
    button.disabled = false;
    button.textContent = "↻ 重新整理";
  }
}

/* =====================================================
   13. 事件與初始化
   ===================================================== */

document
  .getElementById("refreshBtn")
  .addEventListener("click", async () => {
    await loadStockDatabase();
    await refreshAnalysis();
  });

/*
document.getElementById("searchInput").addEventListener("input", render);
*/

const searchInput = document.getElementById("searchInput");

searchInput.addEventListener("input", () => {
  try {
    console.log("[搜尋] 關鍵字：", searchInput.value);
    console.log("[搜尋] 分析資料筆數：", analysisMap.size);

    render();
  } catch (error) {
    console.error("[搜尋] 渲染失敗：", error);

    document.getElementById("message").textContent =
      "搜尋時發生錯誤：" +
      error.message +
      "\n請查看瀏覽器主控台的詳細錯誤。";
  }
});

document
  .getElementById("sortSelect")
  .addEventListener("change", render);

window.addEventListener("storage", event => {
  if (
    !event.key ||
    event.key === WATCHLIST_KEY ||
    event.key === OLD_WATCHLIST_KEY
  ) {
    render();
  }
});

async function init() {
  await loadStockDatabase();
  await refreshAnalysis();
}

init();
