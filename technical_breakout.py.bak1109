import logging

import pandas as pd

from utils import number_or_none

from technical_data import (
    exclude_incomplete_today_candle
)

from technical_indicators import calculate_kd


logger = logging.getLogger(__name__)


# ============================================================
# 1. 布林突破策略預設結果
# ============================================================

def empty_breakout_strategy(message="資料不足"):
    """
    建立布林突破策略預設結果。

    不影響原有技術面評分。
    """

    return {
        "data_available": False,

        "latest_date": None,

        "latest_high": None,

        "latest_low": None,

        "status": "inactive",

        "signal": "none",

        "message": message,

        "bollinger": {
            "period": 20,
            "std_multiplier": 2,
            "std_method": "population",
            "middle": None,
            "upper": None,
            "lower": None,
            "bandwidth": None,
            "previous_bandwidth": None,
            "bandwidth_expanding": False
        },

        "contraction": {
            "lookback": 120,
            "percentile": 20,
            "threshold": None,
            "current_bandwidth": None,
            "is_contracted": False
        },

        "sideways": {
            "observation_days": 20,
            "range_percent": None,
            "threshold_percent": 10,
            "is_sideways": False
        },

        "volume": {
            "today": None,
            "previous_avg20": None,
            "ratio": None,
            "required_multiple": 1.5,
            "qualified": False
        },

        "candle": {
            "open": None,
            "close": None,
            "bullish": False
        },

        "kd_golden_cross": {
            "occurred": False,
            "k": None,
            "d": None
        },

        "stop_condition_met": False,

        "conditions": {
            "above_upper_band": False,
            "bullish_candle": False,
            "volume_qualified": False,
            "bandwidth_expanding": False,
            "buy_signal": False
        }
    }


# ============================================================
# 2. 布林突破策略分析
# ============================================================

def analyze_breakout_strategy(data, settings):
    """
    獨立布林突破策略。

    布林通道：
        20 日
        母體標準差 ddof=0
        上下軌 ±2

    收斂：
        比較突破日前最近 120 個有效帶寬
        位於最低 20% 百分位

    盤整：
        突破日前最近 20 個交易日
        高低區間不超過前一日中軌 10%

    突破買進：
        1. 前一交易日符合收斂
        2. 突破前符合盤整
        3. 收盤價高於當日上軌
        4. 收盤價高於開盤價
        5. 成交量至少為前 20 日有效均量 1.5 倍
        6. 布林帶寬大於前一交易日

    停損：
        收盤價低於當日布林中軌

    KD 黃金交叉：
        僅作為輔助觀察，不是必要買進條件。
    """

    result = empty_breakout_strategy()

    if data is None or data.empty:
        return result

    try:

        settings = settings or {}

        # ----------------------------------------------------
        # 2.1 排除尚未完成的當日 K 棒
        # ----------------------------------------------------

        data = exclude_incomplete_today_candle(data)

        if data.empty:

            result["message"] = (
                "排除尚未完成的當日 K 棒後，"
                "沒有可用的已完成行情"
            )

            return result

        # ----------------------------------------------------
        # 2.2 驗證設定
        # ----------------------------------------------------

        period = int(
            settings.get("bollinger_period", 20)
        )

        std_multiplier = float(
            settings.get("bollinger_std", 2)
        )

        contraction_lookback = int(
            settings.get(
                "breakout_contraction_lookback",
                120
            )
        )

        contraction_percentile = float(
            settings.get(
                "breakout_contraction_percentile",
                20
            )
        )

        sideways_days = int(
            settings.get(
                "breakout_observation_days",
                20
            )
        )

        sideways_threshold = float(
            settings.get(
                "breakout_sideways_range_pct",
                10
            )
        )

        volume_multiple = float(
            settings.get(
                "breakout_volume_multiple",
                1.5
            )
        )

        if period < 2:
            raise ValueError(
                "布林週期必須大於等於 2"
            )

        if std_multiplier <= 0:
            raise ValueError(
                "布林標準差倍數必須大於 0"
            )

        if contraction_lookback < 20:
            raise ValueError(
                "收斂比較期間設定不合理"
            )

        if not 0 < contraction_percentile <= 100:
            raise ValueError(
                "收斂百分位必須介於 0 到 100"
            )

        if sideways_days < 2:
            raise ValueError(
                "盤整觀察天數必須大於等於 2"
            )

        if sideways_threshold <= 0:
            raise ValueError(
                "盤整區間百分比必須大於 0"
            )

        if volume_multiple <= 0:
            raise ValueError(
                "突破成交量倍數必須大於 0"
            )

        # ----------------------------------------------------
        # 2.3 檢查必要行情欄位
        # ----------------------------------------------------

        required_columns = {
            "date",
            "open",
            "max",
            "min",
            "close"
        }

        missing = required_columns - set(data.columns)

        if missing:
            raise ValueError(
                f"布林策略缺少行情欄位：{sorted(missing)}"
            )

        data = data.copy()

        if "Trading_Volume" not in data.columns:
            data["Trading_Volume"] = float("nan")

        data = (
            data.sort_values(
                "date",
                kind="mergesort"
            )
            .reset_index(drop=True)
        )

        # ----------------------------------------------------
        # 2.4 計算布林通道
        # ----------------------------------------------------

        close_series = data["close"]

        middle = close_series.rolling(
            period,
            min_periods=period
        ).mean()

        std = close_series.rolling(
            period,
            min_periods=period
        ).std(ddof=0)

        upper = middle + std_multiplier * std
        lower = middle - std_multiplier * std

        bandwidth = (
            (upper - lower)
            / middle.replace(0, float("nan"))
        ) * 100

        data["bollinger_middle"] = middle
        data["bollinger_upper"] = upper
        data["bollinger_lower"] = lower
        data["bollinger_bandwidth"] = bandwidth

        # ----------------------------------------------------
        # 2.5 檢查有效布林資料
        # ----------------------------------------------------

        valid_data = data.dropna(
            subset=[
                "bollinger_middle",
                "bollinger_upper",
                "bollinger_lower",
                "bollinger_bandwidth"
            ]
        )

        required_valid_bandwidth = (
            contraction_lookback + 1
        )

        if len(valid_data) < required_valid_bandwidth:

            result["message"] = (
                "布林收斂歷史資料不足，"
                f"需要至少 {required_valid_bandwidth} "
                f"個有效帶寬，目前只有 {len(valid_data)} 個"
            )

            return result

        latest = data.iloc[-1]

        if pd.isna(latest["bollinger_bandwidth"]):

            result["message"] = (
                "最新交易日布林資料不足"
            )

            return result

        # ----------------------------------------------------
        # 2.6 取得最新交易日資料
        # ----------------------------------------------------

        latest_date = pd.Timestamp(
            latest["date"]
        ).strftime("%Y-%m-%d")

        close = number_or_none(latest["close"])
        open_price = number_or_none(latest["open"])
        latest_high = number_or_none(latest["max"])
        latest_low = number_or_none(latest["min"])

        middle_value = number_or_none(
            latest["bollinger_middle"]
        )

        upper_value = number_or_none(
            latest["bollinger_upper"]
        )

        lower_value = number_or_none(
            latest["bollinger_lower"]
        )

        bandwidth_value = number_or_none(
            latest["bollinger_bandwidth"]
        )

        if any(
            value is None
            for value in [
                close,
                open_price,
                latest_high,
                latest_low,
                middle_value,
                upper_value,
                lower_value,
                bandwidth_value
            ]
        ):

            result["message"] = (
                "最新交易日策略資料不完整"
            )

            return result

        if len(data) < max(
            contraction_lookback + period,
            sideways_days + 1,
            21
        ):

            result["message"] = (
                "策略歷史行情不足"
            )

            return result

        # ----------------------------------------------------
        # 2.7 帶寬擴張判斷
        # ----------------------------------------------------

        previous_bandwidth = None

        if len(data) >= 2:

            previous_bandwidth = number_or_none(
                data.iloc[-2]["bollinger_bandwidth"]
            )

        bandwidth_expanding = (
            previous_bandwidth is not None
            and bandwidth_value > previous_bandwidth
        )

        # ----------------------------------------------------
        # 2.8 收斂判斷
        # ----------------------------------------------------

        previous_valid_data = valid_data.iloc[:-1]

        recent_bandwidth = (
            previous_valid_data[
                "bollinger_bandwidth"
            ].tail(contraction_lookback)
        )

        contraction_threshold = None
        is_contracted = False

        if len(recent_bandwidth) == contraction_lookback:

            contraction_threshold = number_or_none(
                recent_bandwidth.quantile(
                    contraction_percentile / 100
                )
            )

            is_contracted = (
                contraction_threshold is not None
                and previous_bandwidth is not None
                and previous_bandwidth <= contraction_threshold
            )

        # ----------------------------------------------------
        # 2.9 盤整區間判斷
        # ----------------------------------------------------

        sideways_data = (
            data.iloc[:-1]
            .tail(sideways_days)
        )

        sideways_range_percent = None
        is_sideways = False

        if len(sideways_data) == sideways_days:

            valid_sideways_data = sideways_data.dropna(
                subset=["max", "min"]
            )

            if len(valid_sideways_data) == sideways_days:

                sideways_high = number_or_none(
                    valid_sideways_data["max"].max()
                )

                sideways_low = number_or_none(
                    valid_sideways_data["min"].min()
                )

                previous_middle_value = number_or_none(
                    data.iloc[-2]["bollinger_middle"]
                )

                if (
                    sideways_high is not None
                    and sideways_low is not None
                    and previous_middle_value is not None
                    and previous_middle_value > 0
                ):

                    sideways_range_percent = (
                        (
                            sideways_high
                            - sideways_low
                        )
                        / previous_middle_value
                    ) * 100

                    is_sideways = (
                        sideways_range_percent
                        <= sideways_threshold
                    )

        # ----------------------------------------------------
        # 2.10 前 20 個有效交易日平均成交量
        # ----------------------------------------------------

        previous_volume_data = (
            data.iloc[:-1]["Trading_Volume"]
            .dropna()
            .tail(20)
        )

        previous_avg20 = None

        if len(previous_volume_data) == 20:

            previous_avg20 = number_or_none(
                previous_volume_data.mean()
            )

        today_volume = number_or_none(
            latest["Trading_Volume"]
        )

        volume_ratio = None

        if (
            today_volume is not None
            and previous_avg20 is not None
            and previous_avg20 > 0
        ):

            volume_ratio = (
                today_volume / previous_avg20
            )

        volume_qualified = (
            volume_ratio is not None
            and volume_ratio >= volume_multiple
        )

        # ----------------------------------------------------
        # 2.11 K 棒條件
        # ----------------------------------------------------

        bullish_candle = (
            close > open_price
        )

        # ----------------------------------------------------
        # 2.12 KD 黃金交叉輔助判斷
        # ----------------------------------------------------

        kd_golden_cross = False
        kd_k = None
        kd_d = None

        if len(data) >= 2:

            kd_k_series, kd_d_series = calculate_kd(
                data["max"],
                data["min"],
                data["close"]
            )

            current_k = number_or_none(
                kd_k_series.iloc[-1]
            )

            current_d = number_or_none(
                kd_d_series.iloc[-1]
            )

            previous_k = number_or_none(
                kd_k_series.iloc[-2]
            )

            previous_d = number_or_none(
                kd_d_series.iloc[-2]
            )

            kd_k = current_k
            kd_d = current_d

            kd_golden_cross = (
                current_k is not None
                and current_d is not None
                and previous_k is not None
                and previous_d is not None
                and current_k > current_d
                and previous_k <= previous_d
            )

        # ----------------------------------------------------
        # 2.13 突破及停損條件
        # ----------------------------------------------------

        above_upper_band = (
            close > upper_value
        )

        buy_signal = (
            is_contracted
            and is_sideways
            and above_upper_band
            and bullish_candle
            and volume_qualified
            and bandwidth_expanding
        )

        stop_condition_met = (
            close < middle_value
        )

        # ----------------------------------------------------
        # 2.14 決定目前策略訊號
        # ----------------------------------------------------

        if buy_signal:

            status = "breakout_confirmed"
            signal = "buy"
            message = "帶量突破買進訊號"

        elif is_contracted and is_sideways:

            status = "watching"
            signal = "watch"
            message = "盤整蓄勢候選股"

        else:

            status = "inactive"
            signal = "none"
            message = "目前未符合盤整或突破條件"

        # ----------------------------------------------------
        # 2.15 整理策略輸出
        # ----------------------------------------------------

        result = {

            "data_available": True,

            "latest_date": latest_date,

            "latest_high": latest_high,

            "latest_low": latest_low,

            "status": status,

            "signal": signal,

            "message": message,

            "bollinger": {

                "period": period,

                "std_multiplier": std_multiplier,

                "std_method": "population",

                "middle": round(middle_value, 4),

                "upper": round(upper_value, 4),

                "lower": round(lower_value, 4),

                "bandwidth": round(bandwidth_value, 4),

                "previous_bandwidth": (
                    round(previous_bandwidth, 4)
                    if previous_bandwidth is not None
                    else None
                ),

                "bandwidth_expanding": bandwidth_expanding
            },

            "contraction": {

                "lookback": contraction_lookback,

                "percentile": contraction_percentile,

                "threshold": (
                    round(contraction_threshold, 4)
                    if contraction_threshold is not None
                    else None
                ),

                "current_bandwidth": round(
                    bandwidth_value,
                    4
                ),

                "is_contracted": is_contracted
            },

            "sideways": {

                "observation_days": sideways_days,

                "range_percent": (
                    round(sideways_range_percent, 4)
                    if sideways_range_percent is not None
                    else None
                ),

                "threshold_percent": sideways_threshold,

                "is_sideways": is_sideways
            },

            "volume": {

                "today": today_volume,

                "previous_avg20": (
                    round(previous_avg20, 2)
                    if previous_avg20 is not None
                    else None
                ),

                "ratio": (
                    round(volume_ratio, 4)
                    if volume_ratio is not None
                    else None
                ),

                "required_multiple": volume_multiple,

                "qualified": volume_qualified
            },

            "candle": {

                "open": open_price,

                "close": close,

                "bullish": bullish_candle
            },

            "kd_golden_cross": {

                "occurred": kd_golden_cross,

                "k": (
                    round(kd_k, 2)
                    if kd_k is not None
                    else None
                ),

                "d": (
                    round(kd_d, 2)
                    if kd_d is not None
                    else None
                )
            },

            "stop_condition_met": stop_condition_met,

            "conditions": {

                "above_upper_band": above_upper_band,

                "bullish_candle": bullish_candle,

                "volume_qualified": volume_qualified,

                "bandwidth_expanding": bandwidth_expanding,

                "buy_signal": buy_signal
            }
        }

        return result

    except Exception as exc:

        logger.exception(
            "布林突破策略分析發生錯誤。"
        )

        result["message"] = (
            "布林突破策略計算失敗"
        )

        result["error"] = str(exc)

        return result
