"use strict";
// ============================================================
// 1. 完整股票明細
// ============================================================
function renderDetails(s) {
  const quality = s?.quality || {};
  const missingItems = normalizeMissingItems(
    quality.missing_items
  );
  const foreignHolding =
    s?.foreign_holding ??
    s?.foreignHolding ??
    s?.institutional?.foreign_holding;
  const details = [
    {
      title: "資料更新時間",
      value:
        s?.update_time ??
        s?.updated_at ??
        s?.date ??
        "—"
    },
    {
      title: "資料完整度",
      value: scoreStatus(s)
    },
    {
      title: "外資持股（輔助指標）",
      value: institutionalMetricText(foreignHolding)
    }
  ];
  const detailRows = details.map(item => `
    <div class="detail-row">
      <span>${escapeHTML(item.title)}</span>
      <strong>${escapeHTML(item.value)}</strong>
    </div>
  `).join("");
  const missingHTML = missingItems.length
    ? `
      <div class="detail-row">
        <span>缺少資料</span>
        <strong>${escapeHTML(missingItems.join("、"))}</strong>
      </div>
    `
    : "";
  return `
    <div class="stock-details">
      ${renderScoreBreakdown(s)}
      ${renderInstitutional(s)}
      ${renderTechnical(s)}
      <section class="detail-section">
        <div class="section-title">其他資料</div>
        ${detailRows}
        ${missingHTML}
      </section>
    </div>
  `;
}
// ============================================================
// 2. 展開／收合按鈕
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
      if (!card) {
        return;
      }
      const panel = card.querySelector("." + panelClass);
      if (!panel) {
        return;
      }
      const isHidden =
        panel.hidden ||
        getComputedStyle(panel).display === "none";
      panel.hidden = !isHidden;
      if (isHidden) {
        panel.style.display = "";
        button.textContent = closeText;
        button.setAttribute("aria-expanded", "true");
      } else {
        button.textContent = openText;
        button.setAttribute("aria-expanded", "false");
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
    stock.stock_name ||
    "名稱待確認";
  const companyName = info.company_name;
  const totalScore = validNumber(
    stock?.total_score ??
    stock?.totalScore ??
    stock?.score?.total ??
    stock?.score?.total_score ??
    stock?.score_total ??
    (typeof stock?.score === "number" ? stock.score : null)
  );
  const scoreDisplay = scoreText(totalScore);
  const status = scoreStatus(stock);
  const summary = [
    metricBox(
      "總評分",
      scoreDisplay,
      "滿分 100",
      scoreColor(totalScore)
    ),
    metricBox(
      "基本面／營收",
      scoreText(
        stock?.score_breakdown?.fundamental ??
        stock?.score_breakdown?.revenue ??
        stock?.score_details?.fundamental ??
        stock?.scores?.fundamental ??
        stock?.fundamental_score
      ),
      "滿分 40",
      "neutral"
    ),
    metricBox(
      "法人籌碼",
      scoreText(
        stock?.score_breakdown?.institutional ??
        stock?.score_breakdown?.chip ??
        stock?.score_details?.institutional ??
        stock?.scores?.institutional ??
        stock?.institutional_score ??
        stock?.chip_score
      ),
      "滿分 20",
      "neutral"
    ),
    metricBox(
      "技術面",
      scoreText(
        stock?.score_breakdown?.technical ??
        stock?.score_details?.technical ??
        stock?.scores?.technical ??
        stock?.technical_score
      ),
      "滿分 40",
      "neutral"
    )
  ].join("");
  const searchText = [
    code,
    shortName,
    companyName,
    stock.stock_name,
    status
  ].join(" ").toLowerCase();
  return `
    <article
      class="stock-card"
      data-code="${escapeHTML(code)}"
      data-name="${escapeHTML(shortName)}"
      data-score="${totalScore === null ? "" : totalScore}"
      data-search="${escapeHTML(searchText)}"
    >
      <div class="stock-card-header">
        <div>
          <div class="stock-name">${escapeHTML(shortName)}</div>
          <div class="stock-code">
            ${escapeHTML(code)}
            ${companyName
              ? " · " + escapeHTML(companyName)
              : ""}
          </div>
        </div>
        <div class="score-badge ${escapeHTML(scoreColor(totalScore))}">
          ${escapeHTML(scoreDisplay)}
        </div>
      </div>
      <div class="stock-status">
        ${escapeHTML(status)}
      </div>
      <div class="metric-grid">
        ${summary}
      </div>
      <button
        type="button"
        class="toggle-details"
        aria-expanded="false"
      >
        查看完整分析
      </button>
      <div class="details-panel" hidden>
        ${renderDetails(stock)}
      </div>
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
    if (sortMode === "scoreDesc" || sortMode === "scoreAsc") {
      const scoreA = validNumber(
        a?.total_score ??
        a?.totalScore ??
        a?.score?.total ??
        a?.score?.total_score ??
        a?.score_total ??
        (typeof a?.score === "number" ? a.score : null)
      );
      const scoreB = validNumber(
        b?.total_score ??
        b?.totalScore ??
        b?.score?.total ??
        b?.score?.total_score ??
        b?.score_total ??
        (typeof b?.score === "number" ? b.score : null)
      );
      const valueA = scoreA ?? -Infinity;
      const valueB = scoreB ?? -Infinity;
      return sortMode === "scoreDesc"
        ? valueB - valueA
        : valueA - valueB;
    }
    return String(infoA.stock_id)
      .localeCompare(String(infoB.stock_id), "zh-TW");
  });
  if (stocks.length === 0) {
    grid.innerHTML = `
      <div class="empty">
        ${analysisMap.size === 0
          ? "目前沒有可顯示的分析資料。"
          : "找不到符合條件的股票。"}
      </div>
    `;
    if (message && analysisMap.size > 0) {
      message.textContent =
        `共 ${analysisMap.size} 檔分析資料，目前顯示 0 檔`;
    }
    return;
  }
  grid.innerHTML = stocks
    .map(stock => renderStockCard(stock, watchlistNames))
    .join("");
  bindToggleButtons(
    grid,
    ".toggle-details",
    "details-panel",
    "查看完整分析",
    "收合完整分析"
  );
  if (message) {
    message.textContent =
      `目前顯示 ${stocks.length} 檔股票` +
      `，分析資料共 ${analysisMap.size} 檔`;
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
    if (loading) {
      return;
    }
    await loadStockDatabase();
    await refreshAnalysis();
  });
}
const searchInput = document.getElementById("searchInput");
if (searchInput) {
  searchInput.addEventListener("input", () => {
    try {
      // 保留搜尋診斷紀錄
      console.log("[搜尋] 關鍵字：", searchInput.value);
      console.log("[搜尋] 分析資料筆數：", analysisMap.size);
      render();
    } catch (error) {
      console.error("[搜尋] 渲染失敗：", error);
      const message = document.getElementById("message");
      if (message) {
        message.textContent =
          "搜尋時發生錯誤：" +
          error.message +
          "。請查看瀏覽器主控台的詳細錯誤。";
      }
    }
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
// 所有 JavaScript 檔案已依 index.html 的順序載入後才初始化
init();
