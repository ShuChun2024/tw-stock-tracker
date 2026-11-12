"use strict";

/*
 * 消息面資料。
 */

let eventData = [];


/*
 * 原有展開／縮合功能。
 *
 * 保留 button 與 panel 的相鄰 DOM 結構。
 */

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


/*
 * 渲染消息面板。
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


/*
 * 首頁股票卡片。
 */

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


  /* =====================================================
     搜尋
     ===================================================== */

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


  /* =====================================================
     排序
     ===================================================== */

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

      if (av === null && bv !== null) return 1;
      if (av !== null && bv === null) return -1;

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


  /* =====================================================
     無資料
     ===================================================== */

  if (!stocks.length) {
    grid.innerHTML =
      '<div class="empty">目前沒有符合搜尋條件的分析結果。</div>';

    return;
  }


  /* =====================================================
     股票卡片
     ===================================================== */

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

        <!-- =================================================
             1. 股票識別及綜合評分
             ================================================= -->

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


        <!-- =================================================
             2. 核心基本面指標
             ================================================= -->

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


        <!-- =================================================
             3. 股票估值
             ================================================= -->

        ${renderValuation(s)}


        <!-- =================================================
             4. 個股收盤行情及近 5 個交易日
             ================================================= -->

        ${renderStockPrice(s)}


        <!-- =================================================
             5. 評分明細
             ================================================= -->

        ${renderScoreBreakdown(s)}


        <!-- =================================================
             6. 布林突破策略
             獨立於原本 100 分評分系統
             ================================================= -->

        ${renderBreakoutPanel(item.stock_id)}


        <!-- =================================================
             7. 三大法人籌碼
             ================================================= -->

        ${renderInstitutional(s)}


        <!-- =================================================
             8. 技術面分析
             ================================================= -->

        ${renderTechnical(s)}


        <!-- =================================================
             9. 消息面
             ================================================= -->

        <div
          class="event-panel"
          id="event-panel-${escapeHTML(item.stock_id)}"
          data-event-stock="${escapeHTML(item.stock_id)}"
        ></div>


        <!-- =================================================
             10. 資料品質提醒
             ================================================= -->

        ${
          qualityText
            ? `<div class="quality">${escapeHTML(qualityText)}</div>`
            : ""
        }


        <!-- =================================================
             11. 完整資料明細
             按鈕必須緊鄰 .details
             ================================================= -->

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


  /* =====================================================
     展開／縮合事件綁定
     ===================================================== */


  /*
   * 近 5 個交易日行情
   */

  bindToggleButtons(
    grid,
    ".stock-price-toggle",
    "stock-price-details",
    "近 5 個交易日",
    "近 5 個交易日"
  );


  /*
   * 三大法人
   */

  bindToggleButtons(
    grid,
    ".institutional-toggle",
    "institutional-details",
    "展開三大法人詳細資料",
    "收合三大法人詳細資料"
  );


  /*
   * 技術分析
   */

  bindToggleButtons(
    grid,
    ".technical-toggle",
    "technical-details",
    "展開技術分析詳細資料",
    "收合技術分析詳細資料"
  );


  /*
   * 完整股票明細
   */

  bindToggleButtons(
    grid,
    ".detail-button",
    "details",
    "查看詳細資料",
    "收合詳細資料"
  );


  /*
   * 消息面
   */

  renderEventPanels();
}
