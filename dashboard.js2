"use strict";

// ============================================================
// 1. 完整股票明細
// ============================================================
function renderDetails(s) {
  const quality = s?.data_quality || {};
  const missingItems = normalizeMissingItems(quality.missing_items);
  const revenue = s?.revenue || {};
  const holding = s?.foreign_holding || {};

  const detailRows = [
    ["分析日期", s?.analysis_date || "—"],
    ["分析資料更新時間", analysisUpdateTime || "—"],
    ["技術資料日期", s?.technical?.latest_date || "—"],
    ["資料完整度", scoreStatus(s)],
    [
      "最新營收月份",
      revenue.latest_revenue_month || "—"
    ],
    [
      "最新營收",
      validNumber(revenue.latest_revenue) === null
        ? "—"
        : fmt(revenue.latest_revenue / 100000000, 2) + " 億元"
    ],
    [
      "營收年增率",
      signedPercent(revenue.latest_yoy)
    ],
    [
      "營收趨勢",
      revenue.trend || "—"
    ],
    [
      "外資持股比例",
      validNumber(holding.latest_percent) === null
        ? "資料不足"
        : fmt(holding.latest_percent, 2) + "%"
    ],
    [
      "外資持股日期",
      holding.latest_date || "—"
    ],
    [
      "外資持股趨勢",
      holding.trend || "—"
    ],
    [
      "外資持股變化",
      validNumber(holding.change_periods) === null
        ? "—"
        : signedPercent(holding.change_periods)
    ]
  ];

  return `
    <div class="details">
      ${renderScoreBreakdown(s)}
      ${renderInstitutional(s)}
      ${renderTechnical(s)}

      <section class="section">
        <div class="section-title">其他資料</div>

        ${detailRows.map(([label, value]) => `
          <div class="detail-line">
            <span>${escapeHTML(label)}：</span>
            <strong>${escapeHTML(value)}</strong>
          </div>
        `).join("")}

        ${
          missingItems.length
            ? `
              <div class="quality">
                缺少資料：${escapeHTML(missingItems.join("、"))}
              </div>
            `
            : ""
        }

        ${
          quality.score_complete === true
            ? `<div class="detail-line">評分資料：完整</div>`
            : `<div class="detail-line">評分資料：待確認</div>`
        }

        <div class="detail-line">
          營收說明：${escapeHTML(revenue.message || "—")}
        </div>
      </section>
    </div>
  `;
}

// ============================================================
// 2. 展開／收合按鈕
// 使用 style.css 現有的 .open 樣式
// ============================================================
function bindToggleButtons(
  grid,
  selector,
  panelClass,
  openText,
  closeText
) {
  grid.querySelectorAll(selector).forEach(button => {
    button.addEventListener("click", () => {
      const card = button.closest(".stock-card");
      if (!card) return;

      const panel = card.querySelector("." + panelClass);
      if (!panel) return;

      const opening = !panel.classList.contains("open");
      panel.classList.toggle("open", opening);

      button.setAttribute("aria-expanded", String(opening));

      const label = button.querySelector("span");
      if (label) {
        label.textContent = opening ? closeText : openText;
      } else {
        button.textContent = opening ? closeText : openText;
      }

      const arrow = button.querySelector(".toggle-arrow");
      if (arrow) {
        arrow.textContent = opening ? "⌃" : "⌄";
      }
    });
  });
}

// ============================================================
// 3. 股票卡片
// ============================================================
function renderStockCard(stock, watchlistNames) {
  const info = getStockDisplayInfo(stock, watchlistNames);
  const code = info.stock_id;

  const shortName =
    info.short_name ||
    stock.short_name ||
    stock.stock_name ||
    "名稱待確認";

  const companyName = info.company_name;

  // analysis.json 的 score 是數字，不是物件
  const totalScore = validNumber(stock?.score);
  const breakdown = stock?.score_breakdown || {};
  const revenue = stock?.revenue || {};
  const holding = stock?.foreign_holding || {};

  const status = scoreStatus(stock);
  const qualityClass =
    status === "資料完整" ? "positive" :
    status === "資料不完整" ? "warning" : "neutral";

  const summary = [
    metricBox(
      "基本面／營收",
      scoreText(breakdown.fundamental),
      "滿分 40",
      "neutral"
    ),
    metricBox(
      "法人籌碼",
      scoreText(breakdown.chip ?? stock?.chip_score),
      "滿分 20",
      "neutral"
    ),
    metricBox(
      "技術面",
      scoreText(breakdown.technical ?? stock?.technical?.score),
      "滿分 40",
      "neutral"
    ),
    metricBox(
      "營收年增率",
      signedPercent(revenue.latest_yoy),
      revenue.latest_revenue_month
        ? "月份：" + revenue.latest_revenue_month
        : "",
      trendClass(revenue.message)
    ),
    metricBox(
      "外資持股",
      validNumber(holding.latest_percent) === null
        ? "資料不足"
        : fmt(holding.latest_percent, 2) + "%",
      holding.latest_date || holding.trend || "",
      trendClass(holding.trend)
    )
  ].join("");

  const searchText = [
    code,
    shortName,
    companyName,
    stock.stock_name,
    stock.status
  ].join(" ").toLowerCase();

  return `
    <article
      class="stock-card"
      data-code="${escapeHTML(code)}"
      data-name="${escapeHTML(shortName)}"
      data-score="${totalScore === null ? "" : totalScore}"
      data-search="${escapeHTML(searchText)}"
    >
      <div class="stock-header">
        <div>
          <div class="stock-id">${escapeHTML(code)}</div>
          <div class="company-short">${escapeHTML(shortName)}</div>
          <div class="company-full">${escapeHTML(companyName || "")}</div>
        </div>

        <div class="status ${qualityClass}">
          ${escapeHTML(status)}
        </div>
      </div>

      <div class="score-area">
        <div class="score ${escapeHTML(scoreColor(totalScore))}">
          ${escapeHTML(scoreText(totalScore))}
        </div>
        <div>
          <div class="score-label">總評分</div>
          <div class="score-label">滿分 100</div>
        </div>
      </div>

      <div class="metrics">
        ${summary}
      </div>

      <button
        type="button"
        class="detail-button"
        aria-expanded="false"
      >
        <span>查看完整分析</span>
        <span class="toggle-arrow">⌄</span>
      </button>

      ${renderDetails(stock)}
    </article>
  `;
}

// ============================================================
// 4. 首頁搜尋與排序
// ============================================================
function render() {
  const grid = document.getElementById("stockGrid");
  const searchInput = document.getElementById("searchInput");
  const sortSelect = document.getElementById("sortSelect");
  const message = document.getElementById("message");

  if (!grid) {
    console.error("[首頁] 找不到 stockGrid");
    return;
  }

  const keyword = String(searchInput?.value || "")
    .trim()
    .toLowerCase();

  const sortMode = sortSelect?.value || "code";
  const watchlistNames = getWatchlistNames();

  let stocks = Array.from(analysisMap.values());

  stocks = stocks.filter(stock => {
    const info = getStockDisplayInfo(stock, watchlistNames);
    const searchText = [
      info.stock_id,
      info.short_name,
      info.company_name,
      stock.stock_name,
      stock.status
    ].join(" ").toLowerCase();

    return !keyword || searchText.includes(keyword);
  });

  stocks.sort((a, b) => {
    const infoA = getStockDisplayInfo(a, watchlistNames);
    const infoB = getStockDisplayInfo(b, watchlistNames);

    if (sortMode === "name") {
      return String(infoA.short_name || "")
        .localeCompare(String(infoB.short_name || ""), "zh-TW");
    }

    const scoreA = validNumber(a?.score);
    const scoreB = validNumber(b?.score);

    if (sortMode === "scoreDesc") {
      return (scoreB ?? -Infinity) - (scoreA ?? -Infinity);
    }

    if (sortMode === "scoreAsc") {
      return (scoreA ?? Infinity) - (scoreB ?? Infinity);
    }

    return String(infoA.stock_id)
      .localeCompare(String(infoB.stock_id), "zh-TW");
  });

  if (stocks.length === 0) {
    grid.innerHTML = `
      <div class="empty">
        ${
          analysisMap.size === 0
            ? "目前沒有可顯示的分析資料。"
            : "找不到符合條件的股票。"
        }
      </div>
    `;

    if (message) {
      message.textContent = analysisMap.size === 0
        ? "目前沒有可顯示的分析資料。"
        : `共 ${analysisMap.size} 檔分析資料，目前顯示 0 檔`;
    }

    return;
  }

  grid.innerHTML = stocks
    .map(stock => renderStockCard(stock, watchlistNames))
    .join("");

  bindToggleButtons(
    grid,
    ".detail-button",
    "details",
    "查看完整分析",
    "收合完整分析"
  );

  bindToggleButtons(
    grid,
    ".institutional-toggle",
    "institutional-details",
    "查看法人明細",
    "收合法人明細"
  );

  bindToggleButtons(
    grid,
    ".technical-toggle",
    "technical-details",
    "查看技術指標明細",
    "收合技術指標明細"
  );

  if (message) {
    message.textContent =
      `目前顯示 ${stocks.length} 檔股票，` +
      `分析資料共 ${analysisMap.size} 檔`;
  }
}

// ============================================================
// 5. 初始化與事件
// ============================================================
async function init() {
  await loadStockDatabase();
  await refreshAnalysis();
}

const refreshBtn = document.getElementById("refreshBtn");

if (refreshBtn) {
  refreshBtn.addEventListener("click", async () => {
    if (loading) return;

    await loadStockDatabase();
    await refreshAnalysis();
  });
}

const searchInput = document.getElementById("searchInput");

if (searchInput) {
  searchInput.addEventListener("input", () => {
    render();
  });
}

const sortSelect = document.getElementById("sortSelect");

if (sortSelect) {
  sortSelect.addEventListener("change", render);
}

window.addEventListener("storage", event => {
  if (
    !event.key ||
    event.key === WATCHLIST_KEY ||
    event.key === OLD_WATCHLIST_KEY
  ) {
    render();
  }
});

// 所有依賴模組載入後初始化
init();
