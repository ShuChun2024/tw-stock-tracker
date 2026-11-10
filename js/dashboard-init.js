"use strict";

/*
 * 重新整理按鈕。
 */

document
  .getElementById("refreshBtn")
  .addEventListener("click", async () => {
    await loadStockDatabase();
    await refreshAnalysis();
  });


/*
 * 搜尋功能。
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
      "搜尋時發生錯誤：" +
      error.message +
      "\n請查看瀏覽器主控台的詳細錯誤。";
  }
});


/*
 * 排序功能。
 */

document
  .getElementById("sortSelect")
  .addEventListener("change", render);


/*
 * 跨分頁觀測清單更新。
 */

window.addEventListener("storage", event => {
  if (
    !event.key ||
    event.key === WATCHLIST_KEY ||
    event.key === OLD_WATCHLIST_KEY
  ) {
    render();
  }
});


/*
 * 首頁初始化。
 */

async function init() {
  await loadStockDatabase();
  await refreshAnalysis();
}

init();
