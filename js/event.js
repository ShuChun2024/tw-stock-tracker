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
  if (!match) {
    return text || "日期未提供";
  }
  return `${match[1]}/${match[2]}/${match[3]}`;
}
/* =====================================================
   3. 消息分類及狀態
   ===================================================== */
function getEventCategoryLabel(event) {
  const category = String(event?.category ?? "").trim();
  if (category === "法人說明會") {
    return "法人說明會";
  }
  return category || "其他消息";
}
function getEventStatusLabel(event) {
  if (
    event?.cancelled === true ||
    event?.status === "cancelled"
  ) {
    return "已取消";
  }
  if (event?.category === "法人說明會") {
    return "預定舉行";
  }
  return "";
}
/* =====================================================
   4. 單筆消息
   ===================================================== */
function renderEventItem(event) {
  const category = getEventCategoryLabel(event);
  const date = formatEventDate(event?.date);
  const time = String(event?.time ?? "").trim();
  const title = String(event?.title ?? "").trim();
  const company = String(event?.company_name ?? "").trim();
  const venue = String(event?.venue ?? "").trim();
  const status = getEventStatusLabel(event);
  return `
    <article class="event-item">
      <div class="event-header">
        <div class="event-category">
          ${escapeEventHTML(category)}
        </div>
        <div class="event-date">
          ${escapeEventHTML(date)}
        </div>
      </div>
      <div class="event-title">
        ${escapeEventHTML(title || "消息標題未提供")}
      </div>
      ${
        time || company || venue || status
          ? `
            <div class="event-meta">
              ${
                time
                  ? `<span>時間：${escapeEventHTML(time)}</span>`
                  : ""
              }
              ${
                company
                  ? `<span>公司：${escapeEventHTML(company)}</span>`
                  : ""
              }
              ${
                venue
                  ? `<span>地點：${escapeEventHTML(venue)}</span>`
                  : ""
              }
              ${
                status
                  ? `<span>狀態：${escapeEventHTML(status)}</span>`
                  : ""
              }
            </div>
          `
          : ""
      }
    </article>
  `;
}
/* =====================================================
   5. 消息列表
   ===================================================== */
function renderEventList(stockId, events) {
  const stockEvents = events
    .filter(event => {
      return normalizeEventStockCode(event?.stock_id) === stockId;
    })
    .sort((a, b) => {
      const dateA = String(a?.date ?? "");
      const dateB = String(b?.date ?? "");
      if (dateA !== dateB) {
        return dateB.localeCompare(dateA);
      }
      const timeA = String(a?.time ?? "");
      const timeB = String(b?.time ?? "");
      return timeB.localeCompare(timeA);
    });
  if (!stockEvents.length) {
    return `
      <div class="event-empty">
        目前沒有消息資料。
      </div>
    `;
  }
  return `
    <div class="event-list">
      ${stockEvents.map(renderEventItem).join("")}
    </div>
  `;
}
/* =====================================================
   6. 消息面區塊
   ===================================================== */
function renderEvents(stockId, events) {
  const container = document.getElementById(`event-panel-${stockId}`);
  if (!container) {
    return;
  }
  const stockEvents = events.filter(event => {
    return normalizeEventStockCode(event?.stock_id) === stockId;
  });
  const count = stockEvents.length;
  container.innerHTML = `
    <button
      class="event-toggle"
      type="button"
      aria-expanded="false"
    >
      <span>
        展開消息面明細
        ${
          count
            ? `（${count}）`
            : ""
        }
      </span>
      <span
        class="toggle-arrow"
        aria-hidden="true"
      >⌄</span>
    </button>
    <div class="event-details">
      ${renderEventList(stockId, events)}
    </div>
  `;
  const button = container.querySelector(".event-toggle");
  const panel = container.querySelector(".event-details");
  if (!button || !panel) {
    return;
  }
  button.addEventListener("click", () => {
    const opened = panel.classList.toggle("open");
    button.setAttribute(
      "aria-expanded",
      String(opened)
    );
    const arrow = button.querySelector(".toggle-arrow");
    if (arrow) {
      arrow.textContent = opened ? "⌃" : "⌄";
    }
    const label = button.querySelector("span:first-child");
    if (label) {
      label.textContent = opened
        ? `收合消息面明細${count ? `（${count}）` : ""}`
        : `展開消息面明細${count ? `（${count}）` : ""}`;
    }
  });
}
/* =====================================================
   7. 讀取 events.json
   ===================================================== */
async function loadEventData() {
  const response = await fetch(
    EVENT_DATA_URL + "?t=" + Date.now(),
    {
      cache: "no-store"
    }
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
   8. 初始化
   ===================================================== */
async function initEvents() {
  const containers = document.querySelectorAll(
    "[data-event-stock]"
  );
  if (!containers.length) {
    return;
  }
  try {
    const data = await loadEventData();
    containers.forEach(container => {
      const stockId = normalizeEventStockCode(
        container.dataset.eventStock
      );
      if (!stockId) {
        return;
      }
      renderEvents(
        stockId,
        data.events
      );
    });
    const updateElement =
      document.getElementById("eventUpdateTime");
    if (updateElement) {
      updateElement.textContent =
        data.generatedAt
          ? `消息資料更新時間：${data.generatedAt}`
          : "消息資料已載入";
    }
  } catch (error) {
    console.error(
      "消息面載入失敗：",
      error
    );
    containers.forEach(container => {
      container.innerHTML = `
        <div class="event-error">
          消息資料載入失敗：
          ${escapeEventHTML(error.message)}
        </div>
      `;
    });
  }
}
/* =====================================================
   9. Public API
   ===================================================== */
window.StockEvents = {
  load: initEvents,
  loadEventData,
  renderEvents
};
