import datetime
import logging

import pandas as pd

from technical_data import (
    prepare_price_data,
    exclude_incomplete_today_candle,
)

from technical_breakout import (
    empty_breakout_strategy,
    analyze_breakout_strategy,
)

from technical_scoring import (
    analyze_technical_scoring,
)


logger = logging.getLogger(__name__)


# ============================================================
# 1. 建立預設技術分析結果
# ============================================================

def create_empty_technical_result():
    """
    建立完整的預設技術分析結果。

    保留原本技術分析欄位及資料結構。
    breakout_strategy 獨立存在，不納入原本 100 分評分。
    """

    return {
        "score": None,
        "data_available": False,
        "latest_date": None,
        "latest_close": None,

        "ma": {
            "ma5": None,
            "ma10": None,
            "ma20": None,
            "ma60": None,
            "trend": "資料不足",
            "score": None,
        },

        "rsi": {
            "value": None,
            "signal": "資料不足",
            "score": None,
        },

        "macd": {
            "dif": None,
            "dea": None,
            "histogram": None,
            "signal": "資料不足",
            "score": None,
        },

        "kd": {
            "k": None,
            "d": None,
            "signal": "資料不足",
            "score": None,
        },

        "volume": {
            "today": None,
            "avg5": None,
            "ratio": None,
            "signal": "資料不足",
            "score": None,
        },

        "breakout": {
            "high20": None,
            "low20": None,
            "distance_to_high20_percent": None,
            "distance_to_low20_percent": None,
            "signal": "資料不足",
        },

        "breakout_strategy": empty_breakout_strategy(),

        "message": "資料不足",
    }


# ============================================================
# 2. 日期轉換
# ============================================================

def normalize_today(today):
    """
    將 today 統一轉換成 datetime.date。
    """

    if isinstance(today, datetime.datetime):
        return today.date()

    if isinstance(today, datetime.date):
        return today

    if isinstance(today, str):
        return datetime.date.fromisoformat(today)

    raise ValueError(
        f"無效的分析日期：{today!r}"
    )


# ============================================================
# 3. 布林突破策略診斷日誌
# ============================================================

def log_breakout_diagnostics(
    stock_id,
    raw_count,
    prepared_count,
    filtered_count,
    strategy,
):
    """
    記錄布林突破策略的資料筆數及計算結果。

    用來區分：
        1. 原始行情不足
        2. 整理後行情不足
        3. 排除未完成 K 棒後資料不足
        4. 有效布林資料不足
        5. 策略計算發生錯誤
    """

    if not isinstance(strategy, dict):
        logger.warning(
            "股票 %s 布林策略結果格式錯誤。",
            stock_id
        )
        return

    logger.info(
        (
            "股票 %s 布林策略診斷："
            "raw=%s、prepared=%s、filtered=%s、"
            "data_available=%s、latest_date=%s、"
            "status=%s、signal=%s、message=%s、error=%s"
        ),
        stock_id,
        raw_count,
        prepared_count,
        filtered_count,
        strategy.get("data_available"),
        strategy.get("latest_date"),
        strategy.get("status"),
        strategy.get("signal"),
        strategy.get("message"),
        strategy.get("error"),
    )


# ============================================================
# 4. 每檔股票技術分析
# ============================================================

def analyze_technical(
    dl,
    stock_id,
    settings,
    today,
):
    """
    執行單一股票技術分析。

    分析流程：

        1. 取得 FinMind 每日行情。
        2. 整理行情資料。
        3. 排除尚未完成的當日 K 棒。
        4. 計算獨立布林突破策略。
        5. 依 technical_days 篩選一般技術分析資料。
        6. 計算原有技術指標及 100 分制評分。
        7. 回傳完整技術分析結果。

    注意：

        breakout_strategy 是獨立策略，
        不會加入原本 100 分制評分。

        一般技術分析及布林策略共用整理後的行情資料，
        但兩個子模組目前仍各自計算 KD。
    """

    result = create_empty_technical_result()

    try:

        # ----------------------------------------------------
        # 4.1 基本參數
        # ----------------------------------------------------

        if not isinstance(settings, dict):
            settings = {}

        today_date = normalize_today(today)

        technical_days = max(
            int(settings.get("technical_days", 180)),
            120
        )

        breakout_history_days = max(
            int(settings.get("breakout_history_days", 240)),
            240
        )

        history_days = max(
            technical_days,
            breakout_history_days
        )

        technical_start_date = (
            today_date
            - datetime.timedelta(days=technical_days)
        )

        start_date = (
            today_date
            - datetime.timedelta(days=history_days)
        ).isoformat()

        logger.info(
            (
                "股票 %s 技術分析開始："
                "分析日期=%s、一般技術資料天數=%s、"
                "布林策略資料天數=%s、行情起始日期=%s"
            ),
            stock_id,
            today_date.isoformat(),
            technical_days,
            breakout_history_days,
            start_date,
        )

        # ----------------------------------------------------
        # 4.2 取得 FinMind 每日行情
        # ----------------------------------------------------

        raw_data = dl.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=start_date,
        )

        if raw_data is None:

            logger.warning(
                "股票 %s FinMind 未取得行情資料。",
                stock_id
            )

            result["message"] = "無法取得股價資料"

            return result

        if not isinstance(raw_data, pd.DataFrame):

            logger.error(
                "股票 %s FinMind 回傳資料格式錯誤：%s",
                stock_id,
                type(raw_data).__name__,
            )

            result["message"] = "股價資料格式錯誤"

            return result

        raw_count = len(raw_data)

        logger.info(
            "股票 %s 原始行情筆數：%s",
            stock_id,
            raw_count,
        )

        if raw_data.empty:

            logger.warning(
                "股票 %s 沒有原始行情資料。",
                stock_id
            )

            result["message"] = "沒有股價資料"

            return result

        # ----------------------------------------------------
        # 4.3 整理行情資料
        # ----------------------------------------------------

        data = prepare_price_data(raw_data)

        if not isinstance(data, pd.DataFrame):

            raise TypeError(
                "prepare_price_data 必須回傳 pandas DataFrame"
            )

        prepared_count = len(data)

        logger.info(
            "股票 %s 整理後行情筆數：%s",
            stock_id,
            prepared_count,
        )

        if data.empty:

            logger.warning(
                "股票 %s 整理後沒有有效行情資料。",
                stock_id
            )

            result["message"] = "沒有有效股價資料"

            return result

        # ----------------------------------------------------
        # 4.4 排除尚未完成的當日 K 棒
        # ----------------------------------------------------

        data = exclude_incomplete_today_candle(data)

        if not isinstance(data, pd.DataFrame):

            raise TypeError(
                "exclude_incomplete_today_candle "
                "必須回傳 pandas DataFrame"
            )

        filtered_count = len(data)

        logger.info(
            (
                "股票 %s 排除未完成當日 K 棒後："
                "剩餘 %s 筆行情"
            ),
            stock_id,
            filtered_count,
        )

        if data.empty:

            logger.warning(
                "股票 %s 排除未完成當日 K 棒後沒有資料。",
                stock_id
            )

            result["message"] = "排除未完成 K 棒後沒有有效資料"

            return result

        # ----------------------------------------------------
        # 4.5 計算獨立布林突破策略
        # ----------------------------------------------------

        try:

            breakout_result = analyze_breakout_strategy(
                data=data,
                settings=settings,
            )

            if not isinstance(breakout_result, dict):

                raise TypeError(
                    "analyze_breakout_strategy "
                    "必須回傳 dict"
                )

            result["breakout_strategy"] = breakout_result

        except Exception as exc:

            logger.exception(
                "股票 %s 布林突破策略計算失敗。",
                stock_id
            )

            breakout_result = empty_breakout_strategy(
                message="布林突破策略計算失敗"
            )

            breakout_result["error"] = str(exc)

            result["breakout_strategy"] = breakout_result

        # 記錄策略資料筆數及結果。
        log_breakout_diagnostics(
            stock_id=stock_id,
            raw_count=raw_count,
            prepared_count=prepared_count,
            filtered_count=filtered_count,
            strategy=result["breakout_strategy"],
        )

        # ----------------------------------------------------
        # 4.6 篩選一般技術分析資料
        # ----------------------------------------------------

        technical_data = data[
            data["date"].dt.date >= technical_start_date
        ].copy()

        technical_data = technical_data.reset_index(
            drop=True
        )

        logger.info(
            "股票 %s 一般技術分析有效行情筆數：%s",
            stock_id,
            len(technical_data),
        )

        # ----------------------------------------------------
        # 4.7 計算原有技術指標及 100 分制評分
        # ----------------------------------------------------

        result = analyze_technical_scoring(
            technical_data=technical_data,
            result=result,
            stock_id=stock_id,
        )

        # 確保評分模組沒有意外覆蓋獨立布林策略。
        if not isinstance(result.get("breakout_strategy"), dict):

            logger.error(
                "股票 %s 技術評分後 breakout_strategy 欄位遺失，"
                "恢復原始策略結果。",
                stock_id
            )

            result["breakout_strategy"] = breakout_result

        # ----------------------------------------------------
        # 4.8 完成紀錄
        # ----------------------------------------------------

        strategy = result.get("breakout_strategy", {})

        logger.info(
            (
                "股票 %s 技術分析完成："
                "技術分數=%s、資料可用=%s、"
                "布林資料可用=%s、布林狀態=%s、布林訊號=%s"
            ),
            stock_id,
            result.get("score"),
            result.get("data_available"),
            strategy.get("data_available"),
            strategy.get("status"),
            strategy.get("signal"),
        )

        return result

    except Exception as exc:

        logger.exception(
            "股票 %s 技術分析資料取得或計算失敗。",
            stock_id
        )

        result["message"] = "技術分析資料取得失敗"
        result["error"] = str(exc)

        return result
