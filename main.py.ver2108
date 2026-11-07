import datetime
import logging

from FinMind.data import DataLoader

from config import TAIPEI_TZ
from utils import setup_logging, load_config
from analyzer import analyze_stock, failed_result
from output import save_analysis


# ============================================================
# 1. 執行全部股票分析
# ============================================================

def analyze_stocks():
    """
    台股分析系統主流程。
    """

    # --------------------------------------------------------
    # 1.1 初始化日誌
    # --------------------------------------------------------

    setup_logging()

    logging.info("=" * 60)
    logging.info("台股分析程式開始執行")

    # --------------------------------------------------------
    # 1.2 讀取設定
    # --------------------------------------------------------

    try:
        config = load_config()

        stocks = config["stocks"]
        settings = config.get("settings", {})

    except Exception:
        logging.exception("讀取設定檔失敗，停止執行。")
        raise

    # --------------------------------------------------------
    # 1.3 取得台灣日期及時間
    # --------------------------------------------------------

    now = datetime.datetime.now(TAIPEI_TZ)
    today = now.date()

    logging.info("分析日期：%s", today)
    logging.info("觀察股票數量：%s", len(stocks))
    logging.info("股票清單：%s", ", ".join(stocks))

    # --------------------------------------------------------
    # 1.4 初始化 FinMind
    # --------------------------------------------------------

    try:
        dl = DataLoader()

        logging.info("FinMind DataLoader 初始化完成。")

    except Exception:
        logging.exception(
            "建立 FinMind DataLoader 失敗，停止執行。"
        )
        raise

    # --------------------------------------------------------
    # 1.5 逐檔分析股票
    # --------------------------------------------------------

    results = []

    for index, stock_id in enumerate(stocks, start=1):
        logging.info(
            "開始處理第 %s/%s 檔股票：%s",
            index,
            len(stocks),
            stock_id
        )

        try:
            result = analyze_stock(
                dl=dl,
                stock_id=stock_id,
                settings=settings,
                today=today
            )

            results.append(result)

        except Exception:
            logging.exception(
                "分析股票 %s 發生未預期錯誤。",
                stock_id
            )

            results.append(
                failed_result(stock_id, today)
            )

    # --------------------------------------------------------
    # 1.6 依照綜合分數排序
    # --------------------------------------------------------

    # 有分數的股票優先，分數高者排前面。
    # 無法完整評分的股票排在最後。
    results.sort(
        key=lambda item: (
            item.get("score") is None,
            -(item.get("score") or 0)
        )
    )

    # --------------------------------------------------------
    # 1.7 輸出 analysis.json
    # --------------------------------------------------------

    try:
        save_analysis(
            results=results,
            now=now
        )

    except Exception:
        logging.exception(
            "儲存 analysis.json 失敗。"
        )
        raise

    # --------------------------------------------------------
    # 1.8 執行完成
    # --------------------------------------------------------

    successful_count = sum(
        1
        for item in results
        if item.get("score") is not None
    )

    logging.info(
        "成功取得完整綜合分數的股票：%s/%s",
        successful_count,
        len(results)
    )

    logging.info(
        "分析結果已更新，時間：%s",
        now.strftime("%Y-%m-%d %H:%M:%S")
    )

    logging.info("台股分析程式執行完成")
    logging.info("=" * 60)


# ============================================================
# 2. 程式入口
# ============================================================

if __name__ == "__main__":
    analyze_stocks()

