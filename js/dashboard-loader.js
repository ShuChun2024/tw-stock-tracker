"use strict";

/*
 * 讀取 analysis.json。
 */

async function refreshAnalysis() {
  if (loading) {
    return;
  }

  loading = true;

  const button = document.getElementById("refreshBtn");
  const message = document.getElementById("message");

  button.disabled = true;
  button.textContent = "讀取中…";
  message.textContent = "正在讀取最新分析資料…";
  message.style.display = "";

  try {
    const response = await fetch(
      "./analysis.json?t=" + Date.now(),
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }

    const data = await response.json();

    const stocks = Array.isArray(data)
      ? data
      : data.stocks;

    if (!Array.isArray(stocks)) {
      throw new Error(
        "analysis.json 格式不正確，找不到股票分析陣列。"
      );
    }

    const nextMap = new Map();

    stocks.forEach(stock => {
      if (
        !stock ||
        typeof stock !== "object"
      ) {
        return;
      }

      const code = normalizeCode(stock.stock_id);

      if (!code) {
        return;
      }

      nextMap.set(code, {
        ...stock,
        stock_id: code
      });
    });

    analysisMap = nextMap;

    analysisUpdateTime = (
      !Array.isArray(data) &&
      (
        data.update_time ||
        data.analysis_date
      )
    ) || "";

    document.getElementById("updateTime").textContent =
      "分析資料更新時間：" +
      (analysisUpdateTime || "資料未提供");

    message.textContent = "";
    message.style.display = "none";

    /*
     * 讀取行情資料。
     */

    try {
      await loadStockPrices();
    } catch (priceError) {
      console.error(
        "stock_prices.json 載入失敗：",
        priceError
      );

      stockPriceMap = new Map();
      stockPriceUpdateTime = "";
    }

    /*
     * 讀取布林突破策略資料。
     *
     * 失敗不影響 analysis.json。
     */

    await loadBreakoutState();

    /*
     * 股票分析、行情、突破策略資料準備完成。
     */

    render();

    /*
     * 讀取大盤資料。
     */

    try {
      await loadMarketIndex();
    } catch (marketError) {
      console.error(
        "market_index.json 載入失敗：",
        marketError
      );

      marketData = null;

      const marketContainer = ensureMarketIndexContainer();

      if (marketContainer) {
        marketContainer.innerHTML = `
          <div class="market-index-panel">
            <div class="market-index-title">
              台股大盤
            </div>
            <div class="market-index-error">
              大盤資料載入失敗：
              ${escapeHTML(marketError.message)}
            </div>
          </div>
        `;
      }
    }

    /*
     * 讀取消息資料。
     */

    if (
      window.StockEvents &&
      typeof window.StockEvents.loadEventData === "function"
    ) {
      try {
        const eventResult =
          await window.StockEvents.loadEventData();

        eventData = Array.isArray(eventResult?.events)
          ? eventResult.events
          : [];

        renderEventPanels();

      } catch (eventError) {
        console.error(
          "events.json 載入失敗：",
          eventError
        );

        eventData = [];

        document
          .querySelectorAll("[data-event-stock]")
          .forEach(container => {
            container.innerHTML =
              `<div class="event-error">消息資料載入失敗：${escapeHTML(eventError.message)}</div>`;
          });
      }
    }

  } catch (error) {
    message.style.display = "";

    message.textContent =
      "讀取分析資料失敗：" +
      error.message +
      "\n請確認 analysis.json 已成功發布，且 JSON 格式正確。";

    console.error("analysis.json 載入失敗：", error);

  } finally {
    loading = false;
    button.disabled = false;
    button.textContent = "↻ 重新整理";
  }
}
