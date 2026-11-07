import copy
import datetime
import logging

from FinMind.data import DataLoader

from config import TAIPEI_TZ
from utils import setup_logging, load_config
from analyzer import analyze_stock, failed_result
from output import save_analysis

from breakout import (
    normalize_stock_id,
    load_breakout_state,
    save_breakout_state,
    sync_watchlist,
    get_required_stock_ids,
    process_breakout_stock
)


# ============================================================
# 1. 執行全部股票分析
# ============================================================

def analyze_stocks():

    setup_logging()

    logging.info("=" * 60)
    logging.info("台股分析程式開始執行")

    # --------------------------------------------------------
    # 1.1 讀取設定
    # --------------------------------------------------------

    try:

        config = load_config()

        stocks = [
            normalize_stock_id(stock_id)
            for stock_id in config["stocks"]
        ]

        settings = config.get("settings", {})

    except Exception:

        logging.exception("讀取設定檔失敗，停止執行。")
        raise

    watchlist = sorted(set(stocks))
    watchlist_set = set(watchlist)

    # --------------------------------------------------------
    # 1.2 取得台灣日期
    # --------------------------------------------------------

    now = datetime.datetime.now(TAIPEI_TZ)
    today = now.date()

    logging.info("分析日期：%s", today)
    logging.info("觀察股票數量：%s", len(watchlist))
    logging.info("股票清單：%s", ", ".join(watchlist))

    # --------------------------------------------------------
    # 1.3 載入及同步布林策略狀態
    # --------------------------------------------------------

    state_file = "breakout_state.json"

    try:

        breakout_state = load_breakout_state(state_file)

        sync_watchlist(
            breakout_state,
            watchlist
        )

        required_stock_ids = get_required_stock_ids(
            breakout_state
        )

        logging.info(
            "布林策略需要分析股票數量：%s",
            len(required_stock_ids)
        )

    except Exception:

        logging.exception(
            "載入或同步布林策略狀態失敗，停止執行。"
        )

        raise

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
    # 1.5 逐檔分析
    # --------------------------------------------------------

    results = []

    for index, stock_id in enumerate(
        required_stock_ids,
        start=1
    ):

        logging.info(
            "開始處理第 %s/%s 檔股票：%s",
            index,
            len(required_stock_ids),
            stock_id
        )

        try:

            result = analyze_stock(
                dl=dl,
                stock_id=stock_id,
                settings=settings,
                today=today
            )

        except Exception:

            logging.exception(
                "分析股票 %s 發生未預期錯誤。",
                stock_id
            )

            result = failed_result(
                stock_id,
                today
            )

        # ----------------------------------------------------
        # 1.6 更新布林突破交易狀態
        # ----------------------------------------------------

        original_item = copy.deepcopy(
            breakout_state["stocks"][stock_id]
        )

        try:

            process_breakout_stock(
                state=breakout_state,
                stock_id=stock_id,
                stock_result=result
            )

        except Exception:

            # 單一股票處理失敗時，還原該股票原始狀態，
            # 避免部分更新寫入正式狀態檔。
            breakout_state["stocks"][stock_id] = original_item

            logging.exception(
                "股票 %s 布林交易狀態更新失敗，"
                "已還原該股票本次變更。",
                stock_id
            )

        # ----------------------------------------------------
        # 1.7 僅保留原自選清單股票供 analysis.json 使用
        # ----------------------------------------------------

        if stock_id in watchlist_set:
            results.append(result)

    # --------------------------------------------------------
    # 1.8 儲存 breakout_state.json
    # --------------------------------------------------------

    try:

        save_breakout_state(
            state=breakout_state,
            state_file=state_file
        )

    except Exception:

        logging.exception(
            "儲存 breakout_state.json 失敗，停止後續輸出。"
        )

        raise

    # --------------------------------------------------------
    # 1.9 原本綜合分數排序
    # --------------------------------------------------------

    results.sort(
        key=lambda item: (
            item.get("score") is None,
            -(item.get("score") or 0)
        )
    )

    # --------------------------------------------------------
    # 1.10 原本 analysis.json 輸出
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
    # 1.11 執行完成
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
        "布林策略追蹤股票：%s 檔",
        len(breakout_state["stocks"])
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
