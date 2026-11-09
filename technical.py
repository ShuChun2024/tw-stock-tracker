import datetime
import logging

import pandas as pd

from technical_data import (
    prepare_price_data,
    exclude_incomplete_today_candle,
)

from technical_indicators import (
    calculate_kd,
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
# 4. 計算共用 KD
# ============================================================

def calculate_shared_kd(data):
    """
    在主流程統一計算 KD。

    一般技術評分與布林突破策略共用相同 KD 結果，
    避免兩個模組重複計算。

    保留原始 DataFrame index，
    讓後續技術分析資料可以正確對齊 KD。
    """

    required_columns = [
        "max",
        "min",
        "close",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:

        raise ValueError(
            f"KD 計算缺少欄位：{missing_columns}"
        )

    k_series, d_series = calculate_kd(
        data["max"],
        data["min"],
        data["close"],
    )

    if not isinstance(k_series, pd.Series):

        raise TypeError(
            "calculate_kd 回傳的 K 值必須是 pandas Series"
        )

    if not isinstance(d_series, pd.Series):

        raise TypeError(
            "calculate_kd 回傳的 D 值必須是 pandas Series"
        )

    # 確保 KD 索引與原始行情一致。
    k_series = k_series.reindex(data.index)
    d_series = d_series.reindex(data.index)

    return k_series, d_series


# ============================================================
# 5. 每檔股票技術分析
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
        4. 計算一次共用 KD。
        5. 計算獨立布林突破策略。
        6. 依 technical_days 篩選一般技術分析資料。
        7. 計算原有技術指標及 100 分制評分。
        8. 回傳完整技術分析結果。

    歷史行情：

        一般技術分析：
            預設 180 個日曆天，最低 120 天。

        布林突破策略：
            預設 300 個日曆天，最低 300 天。

        實際 FinMind 抓取天數：
            取兩者較大值。

    注意：

        breakout_strategy 是獨立策略，
        不會加入原本 100 分制評分。

        KD 在此主流程計算一次，
        再提供兩個子模組共用。
    """

    result = create_empty_technical_result()

    try:

        # ----------------------------------------------------
        # 5.1 基本參數
        # ----------------------------------------------------

        if not isinstance(settings, dict):
            settings = {}

        today_date = normalize_today(today)

        # 一般技術分析所需歷史天數。
        technical_days = max(
            int(settings.get("technical_days", 180)),
            120
        )

        # 布林突破策略至少抓取 300 個日曆天。
        # 主要改善 6750 歷史資料不足的問題。
        breakout_history_days = max(
            int(settings.get("breakout_history_days", 300)),
            300
        )

        # 實際行情抓取天數取兩者較大值。
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
                "布林策略資料天數=%s、"
                "實際行情抓取天數=%s、"
                "行情起始日期=%s"
            ),
            stock_id,
            today_date.isoformat(),
            technical_days,
            breakout_history_days,
            history_days,
            start_date,
        )

        # ----------------------------------------------------
        # 5.2 取得 FinMind 每日行情
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
        # 5.3 整理行情資料
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
        # 5.4 排除尚未完成的當日 K 棒
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
        # 5.5 計算共用 KD
        # ----------------------------------------------------

        kd_data = calculate_shared_kd(data)

        logger.info(
            "股票 %s 共用 KD 計算完成：%s 筆",
            stock_id,
            len(kd_data[0]),
        )

        # ----------------------------------------------------
        # 5.6 計算獨立布林突破策略
        # ----------------------------------------------------

        try:

            breakout_result = analyze_breakout_strategy(
                data=data,
                settings=settings,
                kd_data=kd_data,
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
        # 5.7 篩選一般技術分析資料
        # ----------------------------------------------------

        technical_data = data[
            data["date"].dt.date >= technical_start_date
        ].copy()

        # 不重設 index。
        # 因為 kd_data 使用的是完整 data 的原始 index，
        # 必須保留索引才能正確對齊。
        logger.info(
            "股票 %s 一般技術分析有效行情筆數：%s",
            stock_id,
            len(technical_data),
        )

        if technical_data.empty:

            logger.warning(
                "股票 %s 一般技術分析期間沒有行情資料。",
                stock_id
            )

            result["message"] = "一般技術分析期間沒有有效資料"

            return result

        # ----------------------------------------------------
        # 5.8 計算原有技術指標及 100 分制評分
        # ----------------------------------------------------

        result = analyze_technical_scoring(
            technical_data=technical_data,
            result=result,
            stock_id=stock_id,
            kd_data=kd_data,
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
        # 5.9 完成紀錄
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
