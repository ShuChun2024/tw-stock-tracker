"use strict";
/* =====================================================
   1. 基本設定
   ===================================================== */
const EVENT_DATA_URL = "./events.json";
/* =====================================================
   2. 安全及格式處理
   ===================================================== */
function escapeEventHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[ch]);
}
function normalizeEventStockCode(value) {
  const code = String(value ?? "").trim();
  return /^\d{4,6}$/.test(code) ? code : "";
}
function formatEventDate(value) {
  const text = String(value ?? "").trim();
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return text || "日期未提供";
  return `${match[1]}/${match[2]}/${match[3]}`;
}
/* =====================================================
   3. 事件分類
   ===================================================== */
function getEventCategoryLabel(event) {
  const category = String(event?.category ?? "").trim();
  if (category === "法人說明會") {
    return "法人說明會";
  }
  return category || "其他消息";
}
function getEventStatusLabel(event) {
  if (event?.cancelled === true || event?.status === "cancelled") {
    return "已取消";
  }
  if (event?.category === "法人說明會") {
    return "預定舉行";
  }
  return "";
}
/* =====================================================
   4. 單筆事件顯示
   ===================================================== */
function renderEventItem(event) {
  const category = getEventCategoryLabel(event);
  const date = formatEventDate(event?.date);
  const time = String(event?.time ?? "").trim();
  const title = String(event?.title ?? "").trim();
  const companyName = String(event?.company_name ?? "").trim();
  const venue = String(event?.venue ?? "").trim();
  const status = getEventStatusLabel(event);
  const isCancelled =
    event?.cancelled === true ||
    event?.status === "cancelled";
  return `
    <article class="event-item${isCancelled ? " event-cancelled" : ""}">
      <div class="event-item-header">
        <span class="event-category">${escapeEventHTML(category)}</span>
        <span class="event-date">${escapeEventHTML(date)}</span>
      </div>
      <div class="event-title">
        ${escapeEventHTML(title || "未提供事件標題")}
      </div>
      <div class="event-meta">
        ${time
          ? `<div><strong>時間：</strong>${escapeEventHTML(time)}</div>`
          : ""}
        ${companyName
          ? `<div><strong>公司：</strong>${escapeEventHTML(companyName)}</div>`
          : ""}
        ${venue
          ? `<div><strong>地點：</strong>${escapeEventHTML(venue)}</div>`
          : ""}
        ${status
          ? `<div><strong>狀態：</strong>${escapeEventHTML(status)}</div>`
          : ""}
      </div>
    </article>
  `;
}
/* =====================================================
   5. 消息面區塊
   ===================================================== */
function renderEvents(stockId, events) {
  const container = document.getElementById(
    `event-panel-${stockId}`
  );
  if (!container) return;
  const stockEvents = events
    .filter(event =>
      normalizeEventStockCode(event?.stock_id) === stockId
    )
    .sort((a, b) => {
      const dateA = String(a?.date ?? "");
      const dateB = String(b?.date ?? "");
      if (dateA !== dateB) {
        return dateB.localeCompare(dateA);
      }
      return String(b?.time ?? "").localeCompare(
        String(a?.time ?? "")
      );
    });
  if (!stockEvents.length) {
    container.innerHTML = `
      <div class="event-empty">
        目前沒有符合日期範圍的事件資料。
      </div>
    `;
    return;
  }
  container.innerHTML = `
    <div class="event-list">
      ${stockEvents.map(renderEventItem).join("")}
    </div>
  `;
}
/* =====================================================
   6. 載入 events.json
   ===================================================== */
async function loadEventData() {
  const response = await fetch(
    EVENT_DATA_URL + "?t=" + Date.now(),
    { cache: "no-store" }
  );
  if (!response.ok) {
    throw new Error(
      `讀取 events.json 失敗：HTTP ${response.status}`
    );
  }
  const data = await response.json();
  const events = Array.isArray(data)
    ? data
    : data?.events;
  if (!Array.isArray(events)) {
    throw new Error(
      "events.json 格式錯誤，找不到 events 陣列。"
    );
  }
  return {
    events,
    generatedAt: data?.generated_at ?? "",
    eventCount: events.length
  };
}
/* =====================================================
   7. 消息面初始化
   ===================================================== */
async function initEvents() {
  const containers = document.querySelectorAll(
    "[data-event-stock]"
  );
  if (!containers.length) return;
  try {
    const data = await loadEventData();
    containers.forEach(container => {
      const stockId = normalizeEventStockCode(
        container.dataset.eventStock
      );
      if (!stockId) return;
      renderEvents(stockId, data.events);
    });
    const updateElement = document.getElementById(
      "eventUpdateTime"
    );
    if (updateElement) {
      updateElement.textContent = data.generatedAt
        ? `消息資料更新時間：${data.generatedAt}`
        : "消息資料已載入";
    }
  } catch (error) {
    console.error("消息面載入失敗：", error);
    containers.forEach(container => {
      container.innerHTML = `
        <div class="event-error">
          消息資料載入失敗：${escapeEventHTML(error.message)}
        </div>
      `;
    });
  }
}
/* =====================================================
   8. 對外介面
   ===================================================== */
window.StockEvents = {
  load: initEvents,
  loadEventData,
  renderEvents
};
