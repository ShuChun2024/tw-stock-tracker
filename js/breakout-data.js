"use strict";

/*
 * breakout_state.json 獨立資料。
 *
 * 不修改 analysisMap。
 * 不修改原有技術面評分。
 */

let breakoutStateMap = new Map();
let breakoutStateUpdateTime = "";
let breakoutStateLoadError = "";

/*
 * 讀取 breakout_state.json。
 */

async function loadBreakoutState() {
  try {
    const response = await fetch(
      "./breakout_state.json?t=" + Date.now(),
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }

    const data = await response.json();

    if (
      !data ||
      typeof data !== "object" ||
      data.schema_version !== 1 ||
      !data.stocks ||
      typeof data.stocks !== "object" ||
      Array.isArray(data.stocks)
    ) {
      throw new Error(
        "breakout_state.json 格式不正確"
      );
    }

    const nextMap = new Map();

    Object.entries(data.stocks).forEach(([key, stock]) => {
      if (
        !stock ||
        typeof stock !== "object" ||
        Array.isArray(stock)
      ) {
        return;
      }

      const code = normalizeCode(
        stock.stock_id || key
      );

      if (!code) {
        return;
      }

      nextMap.set(code, {
        ...stock,
        stock_id: code
      });
    });

    breakoutStateMap = nextMap;

    breakoutStateUpdateTime =
      data.update_time || "";

    breakoutStateLoadError = "";

    console.log(
      "突破策略資料載入完成，共 " +
      breakoutStateMap.size +
      " 檔"
    );

    return true;

  } catch (error) {
    console.error(
      "載入 breakout_state.json 失敗：",
      error
    );

    breakoutStateMap = new Map();
    breakoutStateUpdateTime = "";
    breakoutStateLoadError = error.message;

    return false;
  }
}
