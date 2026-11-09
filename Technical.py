import datetime
import logging

import pandas as pd

# 保留舊版 technical.py 的函式匯入相容性。
from technical_data import (
    prepare_price_data,
    exclude_incomplete_today_candle
)

from technical_indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_kd
)

from technical_breakout import (
    empty_breakout_strategy,
    analyze_breakout_strategy
)

from technical_scoring import (
    analyze_technical_scoring
)


logger = logging.getLogger(__name__)
# ============================================================
# 1. 技術面綜合分析
# ============================================================

def analyze_technical(
    dl,
    stock_id,
    settings,
    today
):
    """
    分析單一股票的技術指標。

    技術面最高 40 分：

    - 均線：15 分
    - RSI：8 分
    - MACD：8 分
    - KD：5 分
    - 成交量：4 分

    布林突破策略：

    - 獨立計算。
    - 不納入技術面分數。
    - 不影響原有評分。

    當日 K 棒處理：

    - 台灣時間 13:30（含）以前排除當日 K 棒。
    - 台灣時間 13:31 起允許使用當日 K 棒。
    - 布林策略及原有技術指標使用相同的已完成行情。

    成交量缺值處理：

    - 不影響價格技術指標計算。
    - 成交量指標只使用有效成交量。
    - 成交量資料不足時，成交量項目計 0 分，
      其他技術指標仍可正常計分。
    """

    result = {

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
            "score": None
        },

        "rsi": {
            "value": None,
            "signal": "資料不足",
            "score": None
        },

        "macd": {
            "dif": None,
            "dea": None,
            "histogram": None,
            "signal": "資料不足",
            "score": None
        },

        "kd": {
            "k": None,
            "d": None,
            "signal": "資料不足",
            "score": None
        },

        "volume": {
            "today": None,
            "avg5": None,
            "ratio": None,
            "signal": "資料不足",
            "score": None
        },

        "breakout": {
            "high20": None,
            "low20": None,
            "distance_to_high20_percent": None,
            "distance_to_low20_percent": None,
            "signal": "資料不足"
        },

        "breakout_strategy": empty_breakout_strategy(),

        "message": "資料不足"
    }

    try:

        settings = settings or {}

        # ----------------------------------------------------
        # 1.1 設定行情資料區間
        # ----------------------------------------------------

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

        start_date = (
            today - datetime.timedelta(days=history_days)
        ).strftime("%Y-%m-%d")

        technical_start_date = (
            today - datetime.timedelta(days=technical_days)
        )

        # ----------------------------------------------------
        # 1.2 取得每日股價
        # ----------------------------------------------------

        raw_data = dl.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=start_date
        )

        data = prepare_price_data(raw_data)

        if data.empty:

            result["message"] = (
                "沒有可用的股價資料"
            )

            logger.warning(
                "%s 股價資料為空。",
                stock_id
            )

            return result

        # ----------------------------------------------------
        # 1.3 排除尚未完成的當日 K 棒
        # ----------------------------------------------------

        data = exclude_incomplete_today_candle(data)

        if data.empty:

            result["message"] = (
                "排除尚未完成的當日 K 棒後，"
                "沒有可用的已完成股價資料"
            )

            logger.warning(
                "%s 排除尚未完成的當日 K 棒後，"
                "沒有可用的已完成行情。",
                stock_id
            )

            return result

        # ----------------------------------------------------
        # 1.4 獨立計算布林突破策略
        # ----------------------------------------------------

        result["breakout_strategy"] = (
            analyze_breakout_strategy(
                data=data,
                settings=settings
            )
        )

        # ----------------------------------------------------
        # 1.5 保留原有技術分析資料區間
        # ----------------------------------------------------

        technical_data = data[
            data["date"] >= pd.Timestamp(
                technical_start_date
            )
        ].copy()

        technical_data = (
            technical_data
            .reset_index(drop=True)
        )

        if technical_data.empty:

            result["message"] = (
                "技術分析資料不足"
            )

            return result

        # ----------------------------------------------------
        # 1.6 執行原有技術面評分
        # ----------------------------------------------------

        result = analyze_technical_scoring(
            technical_data=technical_data,
            result=result,
            stock_id=stock_id
        )

        # ----------------------------------------------------
        # 1.7 記錄布林策略結果
        # ----------------------------------------------------

        strategy = result["breakout_strategy"]

        logger.info(
            "%s 布林策略：日期=%s，狀態=%s，訊號=%s，"
            "中軌=%s，上軌=%s，帶寬=%s，量比=%s，"
            "最新最高價=%s，最新最低價=%s，"
            "KD黃金交叉=%s，跌破中軌=%s",
            stock_id,
            strategy.get("latest_date"),
            strategy.get("status"),
            strategy.get("signal"),
            strategy.get("bollinger", {}).get("middle"),
            strategy.get("bollinger", {}).get("upper"),
            strategy.get("bollinger", {}).get("bandwidth"),
            strategy.get("volume", {}).get("ratio"),
            strategy.get("latest_high"),
            strategy.get("latest_low"),
            strategy.get("kd_golden_cross", {}).get("occurred"),
            strategy.get("stop_condition_met")
        )

        return result

    except Exception as exc:

        result["message"] = "技術分析資料取得失敗"

        result["error"] = str(exc)

        logger.exception(
            "%s 分析技術面發生錯誤。",
            stock_id
        )

        return result
