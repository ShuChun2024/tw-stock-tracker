"use strict";

/* =====================================================
   4. 讀取 stocks.json
   ===================================================== */

function addDatabaseEntry(codeValue, shortNameValue, companyNameValue) {
  const code = normalizeCode(codeValue);
  if (!code) return;

  stockDatabase.set(code, {
    short_name: String(shortNameValue || "").trim(),
    company_name: String(companyNameValue || "").trim()
  });
}

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

async function loadStockDatabase() {
  try {
    const response = await fetch("./stocks.json?t=" + Date.now(), {
      cache: "no-store"
    });

    if (!response.ok) throw new Error("HTTP " + response.status);

    parseStockDatabase(await response.json());

    console.log(
      "股票名稱資料載入完成，共 " + stockDatabase.size + " 檔"
    );
    return true;
  } catch (error) {
    console.error("載入 stocks.json 失敗：", error);
    return false;
  }
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
    render();

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
