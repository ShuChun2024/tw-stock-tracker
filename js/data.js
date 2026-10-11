"use strict";
// ============================================================
// 1. 將股票名稱資料加入資料庫
// ============================================================
function addDatabaseEntry(item) {
  if (!item || typeof item !== "object") {
    return;
  }
  const code = normalizeCode(
    item.stock_id ??
    item.code ??
    item.stockCode
  );
  if (!code) {
    return;
  }
  const previous = stockDatabase.get(code) || {};
  stockDatabase.set(code, {
    ...previous,
    ...item,
    stock_id: code
  });
}
// ============================================================
// 2. 解析 stocks.json
// 支援陣列，以及包含 stocks 的物件
// ============================================================
function parseStockDatabase(data) {
  const list = Array.isArray(data)
    ? data
    : Array.isArray(data?.stocks)
      ? data.stocks
      : [];
  for (const item of list) {
    addDatabaseEntry(item);
  }
}
// ============================================================
// 3. 載入股票名稱資料庫
// ============================================================
async function loadStockDatabase() {
  try {
    const response = await fetch(
      "./stocks.json?t=" + Date.now(),
      { cache: "no-store" }
    );
    if (!response.ok) {
      throw new Error(
        "stocks.json HTTP " + response.status
      );
    }
    const data = await response.json();
    // 每次重新讀取前清空舊資料，避免殘留已刪除的股票
    stockDatabase.clear();
    parseStockDatabase(data);
    console.log(
      "[股票資料] 已載入股票名稱：",
      stockDatabase.size
    );
    return true;
  } catch (error) {
    console.error("[股票資料] 載入失敗：", error);
    // 保留已經存在的資料，不讓名稱資料載入失敗
    // 直接中斷分析資料顯示
    return false;
  }
}
// ============================================================
// 4. 載入 analysis.json
// ============================================================
async function refreshAnalysis() {
  if (loading) {
    return;
  }
  loading = true;
  const message = document.getElementById("message");
  const refreshBtn = document.getElementById("refreshBtn");
  if (message) {
    message.textContent = "正在讀取分析資料…";
  }
  if (refreshBtn) {
    refreshBtn.disabled = true;
  }
  try {
    const response = await fetch(
      "./analysis.json?t=" + Date.now(),
      { cache: "no-store" }
    );
    if (!response.ok) {
      throw new Error(
        "analysis.json HTTP " + response.status
      );
    }
    const data = await response.json();
    const list = Array.isArray(data)
      ? data
      : Array.isArray(data?.stocks)
        ? data.stocks
        : [];
    const nextMap = new Map();
    for (const stock of list) {
      if (!stock || typeof stock !== "object") {
        continue;
      }
      const code = normalizeCode(
        stock.stock_id ??
        stock.code ??
        ""
      );
      if (!code) {
        continue;
      }
      nextMap.set(code, {
        ...stock,
        stock_id: code
      });
    }
    analysisMap = nextMap;
    analysisUpdateTime =
      data?.update_time ||
      data?.updated_at ||
      data?.generated_at ||
      "";
    const technicalCount = validNumber(data?.technical_count);
    const completeCount = validNumber(data?.complete_count);
    let summary = `分析資料共 ${analysisMap.size} 檔`;
    if (technicalCount !== null) {
      summary += `，技術分析 ${technicalCount} 檔`;
    }
    if (completeCount !== null) {
      summary += `，完整資料 ${completeCount} 檔`;
    }
    if (message) {
      message.textContent = summary;
    }
    const updateTime = document.getElementById("updateTime");
    if (updateTime) {
      updateTime.textContent = analysisUpdateTime
        ? "資料更新時間：" + analysisUpdateTime
        : "分析資料已載入";
    }
    console.log(
      "[分析資料] 載入完成，筆數：",
      analysisMap.size
    );
    // render() 由 dashboard.js 提供
    render();
  } catch (error) {
    console.error("[分析資料] 載入失敗：", error);
    if (message) {
      message.textContent =
        "分析資料載入失敗：" +
        error.message +
        "。請確認 analysis.json 是否存在，以及 GitHub Pages 路徑是否正確。";
    }
    const updateTime = document.getElementById("updateTime");
    if (updateTime) {
      updateTime.textContent = "分析資料載入失敗";
    }
  } finally {
    loading = false;
    if (refreshBtn) {
      refreshBtn.disabled = false;
    }
  }
}
