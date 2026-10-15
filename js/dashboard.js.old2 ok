"use strict";
/* =====================================================
   9. 完整股票明細
   ===================================================== */
function renderDetails(s) {
  const revenue = s.revenue || {};
  const foreign = s.foreign_holding || {};
  const technical = s.technical || {};
  const quality = s.data_quality || {};
  const missing = normalizeMissingItems(quality.missing_items);
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
  const lines = [
    ["分析日期", s.analysis_date || analysisUpdateTime || "尚無資料"],
    ["綜合評分", `${scoreText(s.score)} / 100`],
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
    ["三大法人籌碼分數", `${scoreText(s.chip_score ?? s.score_breakdown?.chip)} / 20`],
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
    </div>`;
}
/* =====================================================
   10. 首頁卡片及展開／縮合
   ===================================================== */
function bindToggleButtons(grid, selector, panelClass, openText, closeText) {
  grid.querySelectorAll(selector).forEach(button => {
    button.addEventListener("click", () => {
      const panel = button.nextElementSibling;
      if (!panel || !panel.classList.contains(panelClass)) return;
      const opened = panel.classList.toggle("open");
      button.setAttribute("aria-expanded", String(opened));
      const label = button.querySelector("span:first-child");
      const arrow = button.querySelector(".toggle-arrow");
      if (label) label.textContent = opened ? closeText : openText;
      if (arrow) arrow.textContent = opened ? "⌃" : "⌄";
    });
  });
}
/* =====================================================
   10-1. 消息面資料
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
    if (!stockId) return;
    const container = document.getElementById(`event-panel-${stockId}`);
    if (!container) return;
    StockEvents.renderEvents(stockId, eventData);
  });
}
function render() {
  const keyword = document.getElementById("searchInput").value.trim().toLowerCase();
  const sort = document.getElementById("sortSelect").value;
  const watchlistNames = getWatchlistNames();
  let stocks = Array.from(analysisMap.values()).map(result => ({
    ...getStockDisplayInfo(result, watchlistNames),
    analysis: result
  }));
  stocks = stocks.filter(item => {
    const s = item.analysis || {};
    const text = [
      item.stock_id, item.short_name, item.company_name,
      s.stock_id, s.stock_name, s.status
    ].join(" ").toLowerCase();
    return text.includes(keyword);
  });
  stocks.sort((a, b) => {
    if (sort === "name") {
      return String(a.short_name || a.stock_id).localeCompare(
        String(b.short_name || b.stock_id), "zh-Hant"
      );
    }
    if (sort === "scoreDesc" || sort === "scoreAsc") {
      const av = validNumber(a.analysis?.score) ? Number(a.analysis.score) : null;
      const bv = validNumber(b.analysis?.score) ? Number(b.analysis.score) : null;
      if (av === null && bv !== null) return 1;
      if (av !== null && bv === null) return -1;
      if (av === null && bv === null) return a.stock_id.localeCompare(b.stock_id);
      return sort === "scoreDesc" ? bv - av : av - bv;
    }
    return a.stock_id.localeCompare(b.stock_id);
  });
  const grid = document.getElementById("stockGrid");
  if (!stocks.length) {
    grid.innerHTML = '<div class="empty">目前沒有符合搜尋條件的分析結果。</div>';
    return;
  }
  grid.innerHTML = stocks.map(item => {
    const s = item.analysis || {};
    const revenue = s.revenue || {};
    const foreign = s.foreign_holding || {};
    const quality = s.data_quality || {};
    const missing = normalizeMissingItems(quality.missing_items);
    const revenueValue = validNumber(revenue.latest_yoy)
      ? signedPercent(revenue.latest_yoy)
      : "資料不足";
    const foreignValue = validNumber(foreign.latest_percent)
      ? fmt(foreign.latest_percent) + "%"
      : "資料不足";
    const qualityText = quality.complete === false || missing.length
      ? "資料品質提醒：" + (
          missing.length ? "缺少 " + missing.join("、") : "部分資料不完整"
        )
      : "";
    return `
      <article class="stock-card">
        <div class="stock-header">
          <div>
            <div class="stock-id">${escapeHTML(item.stock_id)}</div>
            <div class="company-short">${escapeHTML(item.short_name || "名稱待確認")}</div>
            <div class="company-full">${escapeHTML(item.company_name || "公司全名待確認")}</div>
          </div>
          <span class="status">${escapeHTML(scoreStatus(s))}</span>
        </div>
        <div class="score-area">
          <div class="score ${scoreColor(s.score)}">${escapeHTML(scoreText(s.score))}</div>
          <div>
            <div class="score-label">綜合評分 / 100</div>
            <div class="score-label">${escapeHTML(s.status || scoreStatus(s))}</div>
          </div>
        </div>
        <div class="metrics">
          <div class="metric">
            <div class="metric-title">最新營收年增率</div>
            <div class="metric-value ${trendClass(revenue.trend)}">${escapeHTML(revenueValue)}</div>
            <div class="metric-sub">${escapeHTML(revenue.latest_revenue_month || "")}</div>
          </div>
          <div class="metric">
            <div class="metric-title">外資持股比例</div>
            <div class="metric-value ${trendClass(foreign.trend)}">${escapeHTML(foreignValue)}</div>
            <div class="metric-sub">${escapeHTML(foreign.latest_date || "")}</div>
          </div>
        </div>
        ${renderScoreBreakdown(s)}
        ${renderInstitutional(s)}
        ${renderTechnical(s)}
        <!-- =================================================
             消息面
             ================================================= -->
        <div
          class="event-panel"
          id="event-panel-${escapeHTML(item.stock_id)}"
          data-event-stock="${escapeHTML(item.stock_id)}"
        ></div>
        ${qualityText ? `<div class="quality">${escapeHTML(qualityText)}</div>` : ""}
        <button class="detail-button" type="button" aria-expanded="false">
          <span>查看詳細資料</span>
          <span class="toggle-arrow" aria-hidden="true">⌄</span>
        </button>
        ${renderDetails(s)}
      </article>`;
  }).join("");
  bindToggleButtons(
    grid,
    ".institutional-toggle",
    "institutional-details",
    "展開三大法人詳細資料",
    "收合三大法人詳細資料"
  );
  bindToggleButtons(
    grid,
    ".technical-toggle",
    "technical-details",
    "展開技術分析詳細資料",
    "收合技術分析詳細資料"
  );
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
   11. 讀取 analysis.json
   ===================================================== */
async function refreshAnalysis() {
  if (loading) return;
  loading = true;
  const button = document.getElementById("refreshBtn");
  const message = document.getElementById("message");
  button.disabled = true;
  button.textContent = "讀取中…";
  message.textContent = "正在讀取最新分析資料…";
  try {
    const response = await fetch("./analysis.json?t=" + Date.now(), {
      cache: "no-store"
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    const stocks = Array.isArray(data) ? data : data.stocks;
    if (!Array.isArray(stocks)) {
      throw new Error("analysis.json 格式不正確，找不到股票分析陣列。");
    }
    const nextMap = new Map();
    stocks.forEach(stock => {
      if (!stock || typeof stock !== "object") return;
      const code = normalizeCode(stock.stock_id);
      if (!code) return;
      nextMap.set(code, { ...stock, stock_id: code });
    });
    analysisMap = nextMap;
    analysisUpdateTime = (
      !Array.isArray(data) && (data.update_time || data.analysis_date)
    ) || "";
    document.getElementById("updateTime").textContent =
      "分析資料更新時間：" + (analysisUpdateTime || "資料未提供");
    const technicalCount = !Array.isArray(data) && validNumber(data.technical_count)
      ? Number(data.technical_count)
      : null;
    const completeCount = !Array.isArray(data) && validNumber(data.complete_count)
      ? Number(data.complete_count)
      : null;
    let summary =
      `已讀取 ${analysisMap.size} 檔分析結果。股票名稱資料庫共 ${stockDatabase.size} 檔。`;
    if (technicalCount !== null) {
      summary += `\n技術分析成功：${technicalCount} 檔。`;
    }
    if (completeCount !== null) {
      summary += `\n基本面、籌碼面及技術面資料完整：${completeCount} 檔。`;
    }
    message.textContent = summary;
    /*
     * 先渲染股票卡片。
     */
    render();
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
        const eventResult = await window.StockEvents.loadEventData();
        eventData = Array.isArray(eventResult?.events)
          ? eventResult.events
          : [];
        renderEventPanels();
      } catch (eventError) {
        console.error("events.json 載入失敗：", eventError);
        eventData = [];
        document.querySelectorAll("[data-event-stock]").forEach(container => {
          container.innerHTML =
            `<div class="event-error">消息資料載入失敗：${escapeHTML(eventError.message)}</div>`;
        });
      }
    }
  } catch (error) {
    message.textContent =
      "讀取分析資料失敗：" + error.message +
      "\n請確認 analysis.json 已成功發布，且 JSON 格式正確。";
    console.error("analysis.json 載入失敗：", error);
  } finally {
    loading = false;
    button.disabled = false;
    button.textContent = "↻ 重新整理";
  }
}
/* =====================================================
   12. 事件與初始化
   ===================================================== */
document.getElementById("refreshBtn").addEventListener("click", async () => {
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
      "搜尋時發生錯誤：" + error.message +
      "\n請查看瀏覽器主控台的詳細錯誤。";
  }
});
document.getElementById("sortSelect").addEventListener("change", render);
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
