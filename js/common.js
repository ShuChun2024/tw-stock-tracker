"use strict";

/* =====================================================
   1. 基本設定
   ===================================================== */

const WATCHLIST_KEY = "twStockWatchlist";
const OLD_WATCHLIST_KEY = "twStockWatchlistV1";

const DEFAULT_STOCKS = [
  { stock_id: "2330", short_name: "台積電", company_name: "台灣積體電路製造股份有限公司" },
  { stock_id: "2454", short_name: "聯發科", company_name: "聯發科技股份有限公司" },
  { stock_id: "2317", short_name: "鴻海", company_name: "鴻海精密工業股份有限公司" },
  { stock_id: "2603", short_name: "長榮", company_name: "長榮海運股份有限公司" }
];

let analysisMap = new Map();
let stockDatabase = new Map();
let analysisUpdateTime = "";
let loading = false;

/* =====================================================
   2. 安全及格式處理
   ===================================================== */

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[ch]);
}

function normalizeCode(value) {
  const code = String(value ?? "").trim();
  return /^\d{4,6}$/.test(code) ? code : "";
}

function validNumber(value) {
  return value !== null &&
    value !== undefined &&
    value !== "" &&
    Number.isFinite(Number(value));
}

function fmt(value, digits = 2) {
  return validNumber(value) ? Number(value).toFixed(digits) : "—";
}

function signedPercent(value) {
  if (!validNumber(value)) return "—";
  const n = Number(value);
  return (n > 0 ? "+" : "") + n.toFixed(2) + "%";
}

function fmtVolume(value) {
  return validNumber(value)
    ? Math.round(Number(value)).toLocaleString("zh-TW")
    : "—";
}

function scoreText(value) {
  return validNumber(value) ? Number(value).toFixed(1) : "—";
}

function scoreStatus(stock) {
  if (!validNumber(stock.score)) return "資料不足";
  return stock.status || "已完成分析";
}

function scoreColor(score) {
  if (!validNumber(score)) return "neutral";
  if (Number(score) >= 70) return "positive";
  if (Number(score) < 40) return "negative";
  return "neutral";
}

function trendClass(value) {
  const text = String(value ?? "");

  if (/增加|上升|成長|多方|偏強|突破|量增|強勢|買超/.test(text)) {
    return "positive";
  }
  if (/減少|下降|衰退|空方|偏弱|跌破|量縮|弱勢|賣超/.test(text)) {
    return "negative";
  }
  if (/超買|超賣|資料不足|不完整|分歧/.test(text)) {
    return "warning";
  }
  return "neutral";
}

function normalizeMissingItems(items) {
  if (!Array.isArray(items)) return [];

  const names = {
    revenue: "營收",
    foreign_holding: "外資持股",
    institutional: "三大法人買賣超",
    technical: "技術面"
  };

  return items.map(item => names[String(item)] || String(item));
}

function metricBox(title, value, sub = "", cls = "neutral") {
  return `
    <div class="indicator">
      <div class="indicator-name">${escapeHTML(title)}</div>
      <div class="indicator-value ${cls}">${escapeHTML(value)}</div>
      <div class="indicator-sub">${escapeHTML(sub)}</div>
    </div>`;
}

/* =====================================================
   3. 讀取本機觀察清單名稱
   ===================================================== */

function getWatchlistNames() {
  const result = new Map();

  for (const key of [WATCHLIST_KEY, OLD_WATCHLIST_KEY]) {
    try {
      const saved = localStorage.getItem(key);
      if (!saved) continue;

      const list = JSON.parse(saved);
      if (!Array.isArray(list)) continue;

      list.forEach(item => {
        if (!item || typeof item !== "object") return;

        const code = normalizeCode(
          item.stock_id ?? item.code ?? item.stockCode
        );
        if (!code) return;

        const shortName =
          item.short_name ?? item.shortName ?? item.name ?? "";
        const companyName =
          item.company_name ?? item.companyName ?? "";

        const existing = result.get(code) || {};

        result.set(code, {
          short_name: String(shortName || existing.short_name || ""),
          company_name: String(companyName || existing.company_name || "")
        });
      });
    } catch (error) {
      console.warn("讀取本機觀察清單失敗：", error);
    }
  }

  return result;
}

/* =====================================================
   4. 股票名稱對應
   ===================================================== */

function getStockDisplayInfo(result, watchlistNames) {
  const code = normalizeCode(result.stock_id);
  const local = watchlistNames.get(code) || {};
  const database = stockDatabase.get(code) || {};
  const defaultItem = DEFAULT_STOCKS.find(x => x.stock_id === code) || {};

  return {
    stock_id: code,
    short_name:
      local.short_name ||
      database.short_name ||
      defaultItem.short_name ||
      result.short_name ||
      result.stock_name ||
      result.name ||
      "",
    company_name:
      local.company_name ||
      database.company_name ||
      defaultItem.company_name ||
      result.company_name ||
      result.company_full_name ||
      ""
  };
}
