
"use strict";

/* =====================================================
   1. 讀取 stocks.json
   ===================================================== */

/*
 * 新增股票名稱資料。
 *
 * 股票代碼統一透過 normalizeCode() 處理。
 */

function addDatabaseEntry(
  codeValue,
  shortNameValue,
  companyNameValue
) {
  const code = normalizeCode(codeValue);

  if (!code) return;

  stockDatabase.set(code, {
    short_name: String(shortNameValue || "").trim(),
    company_name: String(companyNameValue || "").trim()
  });
}

/*
 * 解析 stocks.json。
 *
 * 支援：
 * 1. 陣列格式
 * 2. stocks 陣列格式
 * 3. 以股票代碼為 key 的物件格式
 */

function parseStockDatabase(data) {
  stockDatabase = new Map();

  const list = Array.isArray(data)
    ? data
    : Array.isArray(data?.stocks)
      ? data.stocks
      : null;

  if (list) {
    list.forEach(item => {
      if (!item || typeof item !== "object") return;

      addDatabaseEntry(
        item.stock_id ?? item.stockId ?? item.stock_code ??
          item.stockCode ?? item.code ?? item.symbol ?? item.id,

        item.short_name ?? item.shortName ?? item.stock_name ??
          item.stockName ?? item.name ?? item.label ?? "",

        item.company_name ?? item.companyName ??
          item.full_name ?? item.fullName ?? ""
      );
    });

    return;
  }

  if (data && typeof data === "object") {
    Object.entries(data).forEach(([code, item]) => {
      if (typeof item === "string") {
        addDatabaseEntry(code, item, "");
        return;
      }

      if (!item || typeof item !== "object") return;

      addDatabaseEntry(
        item.stock_id ?? item.stockId ?? code,

        item.short_name ?? item.shortName ?? item.stock_name ??
          item.stockName ?? item.name ?? item.label ?? "",

        item.company_name ?? item.companyName ??
          item.full_name ?? item.fullName ?? ""
      );
    });
  }
}

/*
 * 讀取 stocks.json。
 *
 * 讀取失敗時回傳 false，
 * 不影響 analysis.json 的載入流程。
 */

async function loadStockDatabase() {
  try {
    const response = await fetch(
      "./stocks.json?t=" + Date.now(),
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }

    parseStockDatabase(await response.json());

    console.log(
      "股票名稱資料載入完成，共 " +
      stockDatabase.size +
      " 檔"
    );

    return true;

  } catch (error) {
    console.error(
      "載入 stocks.json 失敗：",
      error
    );

    return false;
  }
}
