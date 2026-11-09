import logging
import math

import pandas as pd

from utils import number_or_none

from technical_indicators import calculate_kd


logger = logging.getLogger(__name__)


# ============================================================
# 1. 數值安全處理
# ============================================================

def finite_number(value):
    """
    將數值轉換成有限的 float。

    NaN、正負無限大及無法轉換的值回傳 None。
    """

    number = number_or_none(value)

    if number is None:
        return None

    try:
        number = float(number)

        if not math.isfinite(number):
            return None

        return number

    except (TypeError, ValueError, OverflowError):
        return None


# ============================================================
# 2. 布林突破策略預設結果
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
# 3. 驗證及整理 KD 資料
# ============================================================

def get_kd_data(
    data,
    valid_price_data,
    kd_data=None,
):
    """
    取得 KD 資料。

    優先使用 technical.py 傳入的共用 KD。

    如果獨立呼叫本模組，沒有傳入 kd_data，
    則在有效價格資料上自行計算 KD。

    回傳：
        k_series
        d_series
    """

    if kd_data is not None:

        if (
            not isinstance(kd_data, (tuple, list))
            or len(kd_data) != 2
        ):

            raise ValueError(
                "kd_data 必須是包含 K、D Series 的 tuple 或 list"
            )

        k_series, d_series = kd_data

        if not isinstance(k_series, pd.Series):

            raise TypeError(
                "KD 的 K 值必須是 pandas Series"
            )

        if not isinstance(d_series, pd.Series):

            raise TypeError(
                "KD 的 D 值必須是 pandas Series"
            )

        # 共用 KD 必須依照原始行情 index 對齊。
        k_series = k_series.reindex(data.index)
        d_series = d_series.reindex(data.index)

        # 只保留有效價格交易日。
        k_series = k_series.reindex(
            valid_price_data.index
        )

        d_series = d_series.reindex(
            valid_price_data.index
        )

    else:

        # 保留獨立呼叫 technical_breakout.py 的相容性。
        k_series, d_series = calculate_kd(
            valid_price_data["max"],
            valid_price_data["min"],
            valid_price_data["close"],
        )

        if not isinstance(k_series, pd.Series):

            raise TypeError(
                "calculate_kd 回傳的 K 值必須是 pandas Series"
            )

        if not isinstance(d_series, pd.Series):

            raise TypeError(
                "calculate_kd 回傳的 D 值必須是 pandas Series"
            )

        k_series = k_series.reindex(
            valid_price_data.index
        )

        d_series = d_series.reindex(
            valid_price_data.index
        )

    return k_series, d_series


# ============================================================
# 4. 布林突破策略分析
# ============================================================

def analyze_breakout_strategy(
    data,
    settings,
    kd_data=None,
):
    """
    獨立布林突破策略。

    布林通道：
        20 日
        母體標準差 ddof=0
        上下軌 ±2

    收斂：
        使用突破日前的 120 個有效布林帶寬作為比較樣本。
        比較前一交易日帶寬是否位於最低 20% 百分位。

    盤整：
        突破日前最近 20 個有效交易日。
        高低區間不超過前一交易日布林中軌 10%。

    突破買進：
        1. 前一交易日符合收斂。
        2. 突破前符合盤整。
        3. 收盤價高於當日上軌。
        4. 收盤價高於開盤價。
        5. 成交量至少為前 20 筆有效成交量均量 1.5 倍。
        6. 當日布林帶寬大於前一交易日。

    停損：
        收盤價低於當日布林中軌。

    KD 黃金交叉：
        僅作為輔助觀察，不是必要買進條件。

    注意：
        當日未完成 K 棒由 technical.py 統一排除。
        本模組不再重複排除。
        KD 優先使用 technical.py 傳入的共用結果。
    """

    result = empty_breakout_strategy()

    try:

        # ----------------------------------------------------
        # 4.1 檢查輸入資料
        # ----------------------------------------------------

        if not isinstance(data, pd.DataFrame):

            raise TypeError(
                "布林策略輸入資料必須是 pandas DataFrame"
            )

        if data.empty:

            result["message"] = "沒有可用的行情資料"

            return result

        if not isinstance(settings, dict):
            settings = {}

        # ----------------------------------------------------
        # 4.2 驗證設定
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

        if (
            not math.isfinite(std_multiplier)
            or std_multiplier <= 0
        ):

            raise ValueError(
                "布林標準差倍數必須大於 0"
            )

        if contraction_lookback < 20:

            raise ValueError(
                "收斂比較期間設定不合理"
            )

        if (
            not math.isfinite(contraction_percentile)
            or not 0 < contraction_percentile <= 100
        ):

            raise ValueError(
                "收斂百分位必須介於 0 到 100"
            )

        if sideways_days < 2:

            raise ValueError(
                "盤整觀察天數必須大於等於 2"
            )

        if (
            not math.isfinite(sideways_threshold)
            or sideways_threshold <= 0
        ):

            raise ValueError(
                "盤整區間百分比必須大於 0"
            )

        if (
            not math.isfinite(volume_multiple)
            or volume_multiple <= 0
        ):

            raise ValueError(
                "突破成交量倍數必須大於 0"
            )

        # ----------------------------------------------------
        # 4.3 檢查必要行情欄位
        # ----------------------------------------------------

        required_columns = {
            "date",
            "open",
            "max",
            "min",
            "close",
        }

        missing = (
            required_columns
            - set(data.columns)
        )

        if missing:

            raise ValueError(
                f"布林策略缺少行情欄位：{sorted(missing)}"
            )

        data = data.copy()

        # 沒有成交量欄位時保留 NaN。
        # 不因成交量缺值而刪除價格資料。
        if "Trading_Volume" not in data.columns:

            data["Trading_Volume"] = float("nan")

        # ----------------------------------------------------
        # 4.4 排序及數值轉換
        # ----------------------------------------------------

        data["date"] = pd.to_datetime(
            data["date"],
            errors="coerce"
        )

        numeric_columns = [
            "open",
            "max",
            "min",
            "close",
            "Trading_Volume",
        ]

        for column in numeric_columns:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce"
            )

        data = data.sort_values(
            "date",
            kind="mergesort"
        )

        # ----------------------------------------------------
        # 4.5 篩選有效價格資料
        # ----------------------------------------------------

        # OHLC 必須全部存在、有限且大於 0。
        # 成交量不列入價格資料有效性判斷。

        valid_price_mask = (
            data["date"].notna()
            & data["open"].notna()
            & data["max"].notna()
            & data["min"].notna()
            & data["close"].notna()
            & data["open"].map(
                lambda x: math.isfinite(float(x))
                if pd.notna(x) else False
            )
            & data["max"].map(
                lambda x: math.isfinite(float(x))
                if pd.notna(x) else False
            )
            & data["min"].map(
                lambda x: math.isfinite(float(x))
                if pd.notna(x) else False
            )
            & data["close"].map(
                lambda x: math.isfinite(float(x))
                if pd.notna(x) else False
            )
            & (data["open"] > 0)
            & (data["max"] > 0)
            & (data["min"] > 0)
            & (data["close"] > 0)
            & (data["max"] >= data["min"])
        )

        valid_price_data = data.loc[
            valid_price_mask
        ].copy()

        if valid_price_data.empty:

            result["message"] = (
                "沒有有效的 OHLC 價格資料"
            )

            return result

        # ----------------------------------------------------
        # 4.6 計算布林通道
        # ----------------------------------------------------

        close_series = valid_price_data["close"]

        middle = close_series.rolling(
            period,
            min_periods=period
        ).mean()

        std = close_series.rolling(
            period,
            min_periods=period
        ).std(ddof=0)

        upper = (
            middle
            + std_multiplier * std
        )

        lower = (
            middle
            - std_multiplier * std
        )

        bandwidth = (
            (upper - lower)
            / middle.replace(0, float("nan"))
        ) * 100

        valid_price_data["bollinger_middle"] = middle

        valid_price_data["bollinger_upper"] = upper

        valid_price_data["bollinger_lower"] = lower

        valid_price_data["bollinger_bandwidth"] = bandwidth

        # ----------------------------------------------------
        # 4.7 篩選有效布林帶寬資料
        # ----------------------------------------------------

        valid_band_data = valid_price_data.dropna(
            subset=[
                "bollinger_middle",
                "bollinger_upper",
                "bollinger_lower",
                "bollinger_bandwidth",
            ]
        ).copy()

        # 排除無限大等異常數值。
        valid_band_mask = (
            valid_band_data["bollinger_middle"].map(
                lambda x: math.isfinite(float(x))
            )
            & valid_band_data["bollinger_upper"].map(
                lambda x: math.isfinite(float(x))
            )
            & valid_band_data["bollinger_lower"].map(
                lambda x: math.isfinite(float(x))
            )
            & valid_band_data["bollinger_bandwidth"].map(
                lambda x: math.isfinite(float(x))
            )
            & (valid_band_data["bollinger_middle"] > 0)
        )

        valid_band_data = valid_band_data.loc[
            valid_band_mask
        ]

        # ----------------------------------------------------
        # 4.8 檢查有效布林歷史資料
        # ----------------------------------------------------

        # 需要：
        #   1. 前 120 個有效帶寬作為歷史比較樣本。
        #   2. 前一交易日帶寬作為收斂判斷對象。
        #   3. 最新交易日帶寬作為突破判斷對象。
        #
        # 因此至少需要 lookback + 2 個有效帶寬。

        required_valid_bandwidth = (
            contraction_lookback + 2
        )

        if len(valid_band_data) < required_valid_bandwidth:

            result["message"] = (
                "布林收斂歷史資料不足，"
                f"需要至少 {required_valid_bandwidth} "
                f"個有效帶寬，目前只有 "
                f"{len(valid_band_data)} 個"
            )

            return result

        # ----------------------------------------------------
        # 4.9 取得最新及前一交易日資料
        # ----------------------------------------------------

        latest = valid_price_data.iloc[-1]

        latest_band = valid_band_data.iloc[-1]

        previous_band = valid_band_data.iloc[-2]

        # 最新有效價格日必須有完整布林資料。
        if latest.name != latest_band.name:

            result["message"] = (
                "最新有效交易日布林資料不足"
            )

            return result

        latest_date = pd.Timestamp(
            latest["date"]
        ).strftime("%Y-%m-%d")

        close = finite_number(
            latest["close"]
        )

        open_price = finite_number(
            latest["open"]
        )

        latest_high = finite_number(
            latest["max"]
        )

        latest_low = finite_number(
            latest["min"]
        )

        middle_value = finite_number(
            latest_band["bollinger_middle"]
        )

        upper_value = finite_number(
            latest_band["bollinger_upper"]
        )

        lower_value = finite_number(
            latest_band["bollinger_lower"]
        )

        bandwidth_value = finite_number(
            latest_band["bollinger_bandwidth"]
        )

        previous_bandwidth = finite_number(
            previous_band["bollinger_bandwidth"]
        )

        previous_middle_value = finite_number(
            previous_band["bollinger_middle"]
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
                bandwidth_value,
                previous_bandwidth,
                previous_middle_value,
            ]
        ):

            result["message"] = (
                "最新或前一交易日布林資料不完整"
            )

            return result

        # ----------------------------------------------------
        # 4.10 帶寬擴張判斷
        # ----------------------------------------------------

        bandwidth_expanding = (
            bandwidth_value > previous_bandwidth
        )

        # ----------------------------------------------------
        # 4.11 收斂判斷
        # ----------------------------------------------------

        # 取前一交易日之前的 120 個有效帶寬。
        # 不包含前一交易日及最新交易日。
        historical_bandwidth = (
            valid_band_data[
                "bollinger_bandwidth"
            ].iloc[
                -(contraction_lookback + 2):-2
            ]
        )

        contraction_threshold = None

        is_contracted = False

        if len(historical_bandwidth) == contraction_lookback:

            contraction_threshold = finite_number(
                historical_bandwidth.quantile(
                    contraction_percentile / 100
                )
            )

            # 以前一交易日帶寬判斷是否收斂。
            is_contracted = (
                contraction_threshold is not None
                and previous_bandwidth <= contraction_threshold
            )

        # ----------------------------------------------------
        # 4.12 盤整區間判斷
        # ----------------------------------------------------

        # 使用最新交易日前的 20 個有效價格交易日。
        sideways_data = (
            valid_price_data.iloc[:-1]
            .tail(sideways_days)
        )

        sideways_range_percent = None

        is_sideways = False

        if len(sideways_data) == sideways_days:

            sideways_high = finite_number(
                sideways_data["max"].max()
            )

            sideways_low = finite_number(
                sideways_data["min"].min()
            )

            if (
                sideways_high is not None
                and sideways_low is not None
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
        # 4.13 前 20 筆有效成交量平均
        # ----------------------------------------------------

        # 先排除最新交易日。
        # 再排除缺值、負值及無限大。
        # 最後取最近 20 筆有效成交量。
        #
        # 成交量缺值不會刪除對應的價格 K 棒。

        previous_volume_data = (
            valid_price_data.iloc[:-1][
                "Trading_Volume"
            ]
        )

        previous_volume_data = previous_volume_data[
            previous_volume_data.notna()
        ]

        previous_volume_data = previous_volume_data[
            previous_volume_data >= 0
        ]

        previous_volume_data = previous_volume_data[
            previous_volume_data.map(
                lambda x: math.isfinite(float(x))
            )
        ]

        previous_volume_data = previous_volume_data.tail(20)

        previous_avg20 = None

        if len(previous_volume_data) == 20:

            previous_avg20 = finite_number(
                previous_volume_data.mean()
            )

        today_volume = finite_number(
            latest["Trading_Volume"]
        )

        volume_ratio = None

        if (
            today_volume is not None
            and today_volume >= 0
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
        # 4.14 K 棒條件
        # ----------------------------------------------------

        bullish_candle = (
            close > open_price
        )

        # ----------------------------------------------------
        # 4.15 KD 黃金交叉輔助判斷
        # ----------------------------------------------------

        kd_golden_cross = False

        kd_k = None

        kd_d = None

        k_series, d_series = get_kd_data(
            data=data,
            valid_price_data=valid_price_data,
            kd_data=kd_data,
        )

        if len(valid_price_data) >= 2:

            current_k = finite_number(
                k_series.iloc[-1]
            )

            current_d = finite_number(
                d_series.iloc[-1]
            )

            previous_k = finite_number(
                k_series.iloc[-2]
            )

            previous_d = finite_number(
                d_series.iloc[-2]
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
        # 4.16 突破及停損條件
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
        # 4.17 決定目前策略訊號
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
        # 4.18 整理策略輸出
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

                "previous_bandwidth": round(
                    previous_bandwidth,
                    4
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
