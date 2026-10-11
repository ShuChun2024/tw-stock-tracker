"use strict";
// ============================================================
// 1. 共用設定與狀態
// ============================================================
const WATCHLIST_KEY = "twStockWatchlist";
const OLD_WATCHLIST_KEY = "twStockWatchlistV1";
const DEFAULT_STOCKS = [
  {
    stock_id: "2330",
    short_name: "台積電",
    company_name: "台灣積體電路製造股份有限公司"
  },
  {
    stock_id: "2454",
    short_name: "聯發科",
    company_name: "聯發科技股份有限公司"
  },
  {
    stock_id: "2317",
    short_name: "鴻海",
    company_name: "鴻海精密工業股份有限公司"
  },
  {
    stock_id: "2603",
    short_name: "長榮",
    company_name: "長榮海運股份有限公司"
  }
];
let analysisMap = new Map();
let stockDatabase = new Map();
let analysisUpdateTime = "";
let loading = false;
// ============================================================
// 2. 通用格式與安全處理
// ============================================================
function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);
}
function normalizeCode(value) {
  const code = String(value ?? "").trim();
  return /^\d{4,6}$/.test(code) ? code : "";
}
function validNumber(value) {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    typeof value === "boolean"
  ) {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}
function fmt(value, digits = 2) {
  const number = validNumber(value);
  if (number === null) {
    return "—";
  }
  return number.toLocaleString("zh-TW", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
}
function signedPercent(value) {
  const number = validNumber(value);
  if (number === null) {
    return "—";
  }
  const prefix = number > 0 ? "+" : "";
  return prefix + fmt(number, 2) + "%";
}
function fmtVolume(value) {
  const number = validNumber(value);
  if (number === null) {
    return "—";
  }
  return number.toLocaleString("zh-TW", {
    maximumFractionDigits: 0
  });
}
function scoreText(value) {
  const number = validNumber(value);
  return number === null ? "—" : fmt(number, 1);
}
function scoreStatus(stock) {
  const quality = stock?.quality || {};
  if (quality.complete === true) {
    return "資料完整";
  }
  const missing = normalizeMissingItems(quality.missing_items);
  if (missing.length > 0) {
    return "資料不完整";
  }
  return "資料待確認";
}
function scoreColor(score) {
  const number = validNumber(score);
  if (number === null) {
    return "neutral";
  }
  if (number >= 80) {
    return "good";
  }
  if (number >= 60) {
    return "neutral";
  }
  return "bad";
}
function trendClass(value) {
  const text = String(value ?? "").toLowerCase();
  if (/上漲|偏多|多頭|正向|強勢|買超|bull|positive|up/.test(text)) {
    return "good";
  }
  if (/下跌|偏空|空頭|負向|弱勢|賣超|bear|negative|down/.test(text)) {
    return "bad";
  }
  if (/注意|警示|震盪|中性偏空|風險|warning|caution/.test(text)) {
    return "warning";
  }
  return "neutral";
}
function normalizeMissingItems(items) {
  if (!Array.isArray(items)) {
    return [];
  }
  const labels = {
    revenue: "營收",
    foreign_holding: "外資持股",
    institutional: "三大法人買賣超",
    technical: "技術面"
  };
  return items.map(item => {
    const key = String(item ?? "").trim();
    return labels[key] || key;
  });
}
// ============================================================
// 3. 共用指標卡片
// ============================================================
function metricBox(title, value, sub = "", cls = "neutral") {
  return `
    <div class="metric">
      <div class="metric-title">${escapeHTML(title)}</div>
      <div class="metric-value ${escapeHTML(cls)}">
        ${escapeHTML(value)}
      </div>
      ${
        sub
          ? `<div class="metric-sub">${escapeHTML(sub)}</div>`
          : ""
      }
    </div>
  `;
}
// ============================================================
// 4. 取得觀測清單名稱
// ============================================================
function getWatchlistNames() {
  const result = new Map();
  for (const key of [WATCHLIST_KEY, OLD_WATCHLIST_KEY]) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) {
        continue;
      }
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        continue;
      }
      for (const item of parsed) {
        if (!item || typeof item !== "object") {
          continue;
        }
        const code = normalizeCode(
          item.stock_id ??
          item.code ??
          item.stockCode
        );
        if (!code) {
          continue;
        }
        const shortName = String(
          item.short_name ??
          item.shortName ??
          item.name ??
          ""
        ).trim();
        const companyName = String(
          item.company_name ??
          item.companyName ??
          ""
        ).trim();
        if (shortName || companyName) {
          result.set(code, {
            short_name: shortName,
            company_name: companyName
          });
        }
      }
    } catch (error) {
      console.warn("[觀測清單] 讀取失敗：", key, error);
    }
  }
  return result;
}
// ============================================================
// 5. 股票顯示名稱
// 名稱優先順序：觀測清單 → stocks.json → 預設清單 → 分析資料
// ============================================================
function getStockDisplayInfo(result, watchlistNames) {
  const code = normalizeCode(
    result?.stock_id ??
    result?.code ??
    ""
  );
  const watch = watchlistNames.get(code) || {};
  const database = stockDatabase.get(code) || {};
  const defaults = DEFAULT_STOCKS.find(
    item => item.stock_id === code
  ) || {};
  const shortName =
    watch.short_name ||
    database.short_name ||
    database.stock_name ||
    defaults.short_name ||
    result?.short_name ||
    result?.stock_name ||
    result?.name ||
    "";
  const companyName =
    watch.company_name ||
    database.company_name ||
    defaults.company_name ||
    result?.company_name ||
    "";
  return {
    stock_id: code,
    short_name: shortName,
    company_name: companyName
  };
}
