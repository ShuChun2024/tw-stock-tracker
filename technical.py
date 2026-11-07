import datetime
import logging

import pandas as pd

from utils import number_or_none


# ============================================================
# 1. 整理每日股價資料
# ============================================================

def prepare_price_data(df):
    """
    整理 FinMind 每日股價資料。
    """

    required = {
        "date",
        "Trading_Volume",
        "open",
        "max",
        "min",
        "close"
    }

    if df is None or df.empty:
        return pd.DataFrame()

    missing = required - set(df.columns)

    if missing:
        logging.error(
            "股價資料缺少欄位：%s；實際欄位：%s",
            sorted(missing),
            list(df.columns)
        )
        return pd.DataFrame()

    data = df[
        [
            "date",
            "Trading_Volume",
            "open",
            "max",
            "min",
            "close"
        ]
    ].copy()

    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce"
    )

    for column in [
        "Trading_Volume",
        "open",
        "max",
        "min",
        "close"
    ]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    data = data.dropna(
        subset=["date", "close"]
    )

    data = (
        data.sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last"
        )
        .reset_index(drop=True)
    )

    return data


# ============================================================
# 2. 計算 RSI 相對強弱指標
# ============================================================

def calculate_rsi(close, period=14):
    """
    使用指數移動平均計算 RSI。
    """

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    rsi = pd.Series(
        index=close.index,
        dtype="float64"
    )

    normal = (
        (avg_loss > 0)
        & avg_gain.notna()
        & avg_loss.notna()
    )

    rsi.loc[normal] = (
        100
        - (
            100
            / (
                1
                + (
                    avg_gain.loc[normal]
                    / avg_loss.loc[normal]
                )
            )
        )
    )

    # 只有上漲、沒有下跌
    rsi.loc[
        (avg_loss == 0) & (avg_gain > 0)
    ] = 100.0

    # 沒有漲跌
    rsi.loc[
        (avg_loss == 0)
        & (avg_gain == 0)
        & avg_gain.notna()
    ] = 50.0

    return rsi


# ============================================================
# 3. 計算 MACD
# ============================================================

def calculate_macd(
    close,
    fast_period=12,
    slow_period=26,
    signal_period=9
):
    """
    回傳 DIF、DEA、MACD 柱狀圖。
    """

    dif = (
        close.ewm(
            span=fast_period,
            adjust=False
        ).mean()
        -
        close.ewm(
            span=slow_period,
            adjust=False
        ).mean()
    )

    dea = dif.ewm(
        span=signal_period,
        adjust=False
    ).mean()

    histogram = dif - dea

    return dif, dea, histogram


# ============================================================
# 4. 計算 KD 隨機指標
# ============================================================

def calculate_kd(
    high,
    low,
    close,
    period=9
):
    """
    計算 K 值與 D 值。
    初始 K、D 值設為 50。
    """

    lowest_low = low.rolling(
        period,
        min_periods=period
    ).min()

    highest_high = high.rolling(
        period,
        min_periods=period
    ).max()

    denominator = highest_high - lowest_low

    rsv = (
        (close - lowest_low)
        / denominator.replace(0, float("nan"))
    ) * 100

    k_values = []
    d_values = []

    previous_k = 50.0
    previous_d = 50.0

    for value in rsv:

        if pd.isna(value):
            k_values.append(float("nan"))
            d_values.append(float("nan"))
            continue

        k_value = (
            previous_k * 2 / 3
            + float(value) / 3
        )

        d_value = (
            previous_d * 2 / 3
            + k_value / 3
        )

        k_values.append(k_value)
        d_values.append(d_value)

        previous_k = k_value
        previous_d = d_value

    k_series = pd.Series(
        k_values,
        index=close.index
    )

    d_series = pd.Series(
        d_values,
        index=close.index
    )

    return k_series, d_series


# ============================================================
# 5. 布林突破策略預設結果
# ============================================================

def empty_breakout_strategy(message="資料不足"):
    """
    建立布林突破策略預設結果。
    不影響原有技術面評分。
    """

    return {
        "data_available": False,

        "latest_date": None,

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
# 6. 布林突破策略分析
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
        5. 成交量至少為前 20 日均量 1.5 倍
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

        period = int(
            settings.get("bollinger_period", 20)
        )

        std_multiplier = float(
            settings.get("bollinger_std", 2)
        )

        contraction_lookback = int(
            settings.get("breakout_contraction_lookback", 120)
        )

        contraction_percentile = float(
            settings.get(
                "breakout_contraction_percentile",
                20
            )
        )

        sideways_days = int(
            settings.get("breakout_observation_days", 20)
        )

        sideways_threshold = float(
            settings.get("breakout_sideways_range_pct", 10)
        )

        volume_multiple = float(
            settings.get("breakout_volume_multiple", 1.5)
        )

        # ----------------------------------------------------
        # 6.1 驗證設定
        # ----------------------------------------------------

        if period < 2:
            raise ValueError("布林週期必須大於等於 2")

        if std_multiplier <= 0:
            raise ValueError("布林標準差倍數必須大於 0")

        if contraction_lookback < 20:
            raise ValueError("收斂比較期間設定不合理")

        if not 0 < contraction_percentile <= 100:
            raise ValueError("收斂百分位必須介於 0 到 100")

        if sideways_days < 2:
            raise ValueError("盤整觀察天數必須大於等於 2")

        if sideways_threshold <= 0:
            raise ValueError("盤整區間百分比必須大於 0")

        if volume_multiple <= 0:
            raise ValueError("突破成交量倍數必須大於 0")

        # ----------------------------------------------------
        # 6.2 計算布林通道
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

        data = data.copy()

        data["bollinger_middle"] = middle
        data["bollinger_upper"] = upper
        data["bollinger_lower"] = lower
        data["bollinger_bandwidth"] = bandwidth

        # ----------------------------------------------------
        # 6.3 取得最新交易日資料及歷史資料檢查
        # ----------------------------------------------------

        valid_data = data.dropna(
            subset=[
                "bollinger_middle",
                "bollinger_upper",
                "bollinger_lower",
                "bollinger_bandwidth"
            ]
        )

        # 收斂判斷使用前一交易日之前的 120 個有效帶寬，
        # 因此至少需要 121 個有效帶寬。
        required_valid_bandwidth = (
            contraction_lookback + 1
        )

        if len(valid_data) < required_valid_bandwidth:

            result["message"] = (
                "布林收斂歷史資料不足，"
                f"需要至少 {required_valid_bandwidth} 個有效帶寬，"
                f"目前只有 {len(valid_data)} 個"
            )

            return result

        latest = data.iloc[-1]

        if pd.isna(latest["bollinger_bandwidth"]):
            result["message"] = "最新交易日布林資料不足"
            return result

        if len(data) < max(
            contraction_lookback + period,
            sideways_days + 1,
            21
        ):

            result["message"] = "策略歷史行情不足"
            return result

        latest_date = latest["date"].strftime("%Y-%m-%d")

        close = number_or_none(latest["close"])

        open_price = number_or_none(
            latest["open"]
        )

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
                middle_value,
                upper_value,
                lower_value,
                bandwidth_value
            ]
        ):

            result["message"] = "最新交易日策略資料不完整"
            return result

        # ----------------------------------------------------
        # 6.4 帶寬擴張判斷
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
        # 6.5 收斂判斷
        # ----------------------------------------------------

        # 排除最新交易日。
        # 使用前一交易日之前最近 120 個有效帶寬。
        # 判斷前一交易日帶寬是否位於最低 20% 百分位。

        previous_valid_data = valid_data.iloc[:-1]

        recent_bandwidth = (
            previous_valid_data["bollinger_bandwidth"]
            .tail(contraction_lookback)
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
        # 6.6 盤整區間判斷
        # ----------------------------------------------------

        # 排除最新交易日。
        # 使用突破日前最近 20 個交易日。
        # 以突破日前一交易日的布林中軌作為分母。

        sideways_data = (
            data.iloc[:-1]
            .tail(sideways_days)
        )

        sideways_high = None
        sideways_low = None
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
                        (sideways_high - sideways_low)
                        / previous_middle_value
                    ) * 100

                    is_sideways = (
                        sideways_range_percent <= sideways_threshold
                    )

        # ----------------------------------------------------
        # 6.7 前 20 日平均成交量
        # ----------------------------------------------------

        # 排除最新交易日。

        previous_volume_data = (
            data.iloc[:-1].tail(20)
        )

        previous_avg20 = None

        if len(previous_volume_data) == 20:

            previous_avg20 = number_or_none(
                previous_volume_data["Trading_Volume"].mean()
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
        # 6.8 K 棒條件
        # ----------------------------------------------------

        bullish_candle = close > open_price

        # ----------------------------------------------------
        # 6.9 KD 黃金交叉輔助判斷
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
        # 6.10 突破及停損條件
        # ----------------------------------------------------

        above_upper_band = close > upper_value

        # 必須先符合收斂及盤整，
        # 再同時符合四項突破條件。

        buy_signal = (
            is_contracted
            and is_sideways
            and above_upper_band
            and bullish_candle
            and volume_qualified
            and bandwidth_expanding
        )

        # 停損條件：
        # 收盤價低於當日布林中軌。
        # 實際是否執行停損由 breakout.py 判斷持倉狀態。

        stop_condition_met = close < middle_value

        # ----------------------------------------------------
        # 6.11 決定目前策略訊號
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
        # 6.12 整理策略輸出
        # ----------------------------------------------------

        result = {

            "data_available": True,

            "latest_date": latest_date,

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

        logging.exception(
            "布林突破策略分析發生錯誤。"
        )

        result["message"] = "布林突破策略計算失敗"

        result["error"] = str(exc)

        return result


# ============================================================
# 7. 技術面綜合分析
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

    - 獨立計算
    - 不納入技術面分數
    - 不影響原有評分
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

        # ----------------------------------------------------
        # 7.1 設定行情資料區間
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
        # 7.2 取得每日股價
        # ----------------------------------------------------

        raw_data = dl.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=start_date
        )

        data = prepare_price_data(raw_data)

        if data.empty:

            result["message"] = "沒有可用的股價資料"

            logging.warning(
                "%s 股價資料為空。",
                stock_id
            )

            return result

        # ----------------------------------------------------
        # 7.3 獨立計算布林突破策略
        # ----------------------------------------------------

        result["breakout_strategy"] = (
            analyze_breakout_strategy(
                data=data,
                settings=settings
            )
        )

        # ----------------------------------------------------
        # 7.4 保留原有技術分析資料區間
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

            result["message"] = "技術分析資料不足"

            return result

        # 原有技術指標只使用 technical_data，
        # 避免延長布林策略行情後改變原有評分。

        # ----------------------------------------------------
        # 7.5 計算均線
        # ----------------------------------------------------

        for period in [5, 10, 20, 60]:

            technical_data[f"ma{period}"] = (
                technical_data["close"].rolling(
                    period,
                    min_periods=period
                ).mean()
            )

        # ----------------------------------------------------
        # 7.6 計算 RSI、MACD、KD、成交量均線
        # ----------------------------------------------------

        technical_data["rsi"] = calculate_rsi(
            technical_data["close"],
            14
        )

        (
            technical_data["macd_dif"],
            technical_data["macd_dea"],
            technical_data["macd_histogram"]
        ) = calculate_macd(
            technical_data["close"]
        )

        (
            technical_data["kd_k"],
            technical_data["kd_d"]
        ) = calculate_kd(
            technical_data["max"],
            technical_data["min"],
            technical_data["close"]
        )

        technical_data["volume_ma5"] = (
            technical_data["Trading_Volume"].rolling(
                5,
                min_periods=5
            ).mean()
        )

        if len(technical_data) < 60:

            result["message"] = (
                f"股價資料不足，需要至少 60 個交易日，"
                f"目前只有 {len(technical_data)} 日"
            )

            return result

        # ----------------------------------------------------
        # 7.7 取得最新一個交易日的指標
        # ----------------------------------------------------

        latest = technical_data.iloc[-1]

        field_names = [
            "close",
            "ma5",
            "ma10",
            "ma20",
            "ma60",
            "rsi",
            "macd_dif",
            "macd_dea",
            "macd_histogram",
            "kd_k",
            "kd_d",
            "Trading_Volume",
            "volume_ma5"
        ]

        values = {
            name: number_or_none(latest[name])
            for name in field_names
        }

        missing_count = sum(
            value is None
            for value in values.values()
        )

        if missing_count:

            result["message"] = (
                f"技術指標資料不足，缺少 "
                f"{missing_count} 項"
            )

            return result

        (
            close,
            ma5,
            ma10,
            ma20,
            ma60,
            rsi,
            dif,
            dea,
            histogram,
            k,
            d,
            volume,
            volume_ma5
        ) = [
            values[name]
            for name in field_names
        ]

        result["latest_date"] = (
            latest["date"].strftime("%Y-%m-%d")
        )

        result["latest_close"] = close

        # ----------------------------------------------------
        # 7.8 均線分析：最高 15 分
        # ----------------------------------------------------

        if close > ma5 > ma10 > ma20 > ma60:

            ma_trend = "多頭排列"
            ma_score = 15

        elif close > ma20 and ma20 > ma60:

            ma_trend = "中期偏多"
            ma_score = 11

        elif close > ma60:

            ma_trend = "站上60日線"
            ma_score = 8

        elif close < ma20 and ma20 < ma60:

            ma_trend = "中期偏弱"
            ma_score = 2

        else:

            ma_trend = "盤整"
            ma_score = 5

        result["ma"] = {

            "ma5": round(ma5, 2),

            "ma10": round(ma10, 2),

            "ma20": round(ma20, 2),

            "ma60": round(ma60, 2),

            "trend": ma_trend,

            "score": ma_score
        }

        # ----------------------------------------------------
        # 7.9 RSI 分析：最高 8 分
        # ----------------------------------------------------

        if rsi >= 70:

            rsi_signal = "超買"
            rsi_score = 5

        elif rsi >= 60:

            rsi_signal = "偏強"
            rsi_score = 8

        elif rsi >= 50:

            rsi_signal = "中性偏強"
            rsi_score = 6

        elif rsi >= 40:

            rsi_signal = "中性偏弱"
            rsi_score = 4

        elif rsi >= 30:

            rsi_signal = "偏弱"
            rsi_score = 2

        else:

            rsi_signal = "超賣"
            rsi_score = 3

        result["rsi"] = {

            "value": round(rsi, 2),

            "signal": rsi_signal,

            "score": rsi_score
        }

        # ----------------------------------------------------
        # 7.10 MACD 分析：最高 8 分
        # ----------------------------------------------------

        if dif > dea and histogram > 0:

            macd_signal = "多方"
            macd_score = 8

        elif dif > dea:

            macd_signal = "偏多"
            macd_score = 6

        elif dif < dea and histogram < 0:

            macd_signal = "空方"
            macd_score = 1

        else:

            macd_signal = "中性"
            macd_score = 4

        result["macd"] = {

            "dif": round(dif, 4),

            "dea": round(dea, 4),

            "histogram": round(histogram, 4),

            "signal": macd_signal,

            "score": macd_score
        }

        # ----------------------------------------------------
        # 7.11 KD 分析：最高 5 分
        # ----------------------------------------------------

        if k > d and k >= 50:

            kd_signal = "偏強"
            kd_score = 5

        elif k > d:

            kd_signal = "短線轉強"
            kd_score = 4

        elif k < d and k < 50:

            kd_signal = "偏弱"
            kd_score = 1

        else:

            kd_signal = "中性"
            kd_score = 3

        result["kd"] = {

            "k": round(k, 2),

            "d": round(d, 2),

            "signal": kd_signal,

            "score": kd_score
        }

        # ----------------------------------------------------
        # 7.12 成交量分析：最高 4 分
        # ----------------------------------------------------

        volume_ratio = (
            volume / volume_ma5
            if volume_ma5
            else None
        )

        if volume_ratio is None:

            volume_signal = "資料不足"
            volume_score = 0

        elif volume_ratio >= 1.5:

            volume_signal = "明顯量增"
            volume_score = 4

        elif volume_ratio >= 1.1:

            volume_signal = "量增"
            volume_score = 3

        elif volume_ratio >= 0.8:

            volume_signal = "量能正常"
            volume_score = 2

        else:

            volume_signal = "量縮"
            volume_score = 1

        result["volume"] = {

            "today": volume,

            "avg5": round(volume_ma5, 2),

            "ratio": (
                round(volume_ratio, 2)
                if volume_ratio is not None
                else None
            ),

            "signal": volume_signal,

            "score": volume_score
        }

        # ----------------------------------------------------
        # 7.13 20 日高低點突破分析
        # ----------------------------------------------------

        # 排除最新交易日，
        # 以前 20 個交易日為比較區間。

        previous_data = (
            technical_data.iloc[:-1].tail(20)
        )

        if len(previous_data) >= 20:

            high20 = number_or_none(
                previous_data["max"].max()
            )

            low20 = number_or_none(
                previous_data["min"].min()
            )

            if (
                high20 is not None
                and low20 is not None
                and high20 > 0
                and low20 > 0
            ):

                if close > high20:

                    breakout_signal = "突破20日高點"

                elif close >= high20 * 0.98:

                    breakout_signal = "接近20日高點"

                elif close < low20:

                    breakout_signal = "跌破20日低點"

                elif close <= low20 * 1.02:

                    breakout_signal = "接近20日低點"

                else:

                    breakout_signal = "20日區間內"

                result["breakout"] = {

                    "high20": round(high20, 2),

                    "low20": round(low20, 2),

                    "distance_to_high20_percent": round(
                        (close / high20 - 1) * 100,
                        2
                    ),

                    "distance_to_low20_percent": round(
                        (close / low20 - 1) * 100,
                        2
                    ),

                    "signal": breakout_signal
                }

        # ----------------------------------------------------
        # 7.14 計算技術面總分
        # ----------------------------------------------------

        total_score = (
            ma_score
            + rsi_score
            + macd_score
            + kd_score
            + volume_score
        )

        result["score"] = total_score

        result["data_available"] = True

        if total_score >= 32:

            result["message"] = "技術面強勢"

        elif total_score >= 26:

            result["message"] = "技術面偏多"

        elif total_score >= 20:

            result["message"] = "技術面中性"

        elif total_score >= 14:

            result["message"] = "技術面偏弱"

        else:

            result["message"] = "技術面弱勢"

        logging.info(
            "%s 技術分析：收盤=%.2f，MA=%s，"
            "RSI=%.2f，MACD=%s，KD=%s，"
            "量比=%s，技術分數=%s",
            stock_id,
            close,
            ma_trend,
            rsi,
            macd_signal,
            kd_signal,
            volume_ratio,
            total_score
        )

        strategy = result["breakout_strategy"]

        logging.info(
            "%s 布林策略：日期=%s，狀態=%s，訊號=%s，"
            "中軌=%s，上軌=%s，帶寬=%s，量比=%s，"
            "KD黃金交叉=%s，跌破中軌=%s",
            stock_id,
            strategy.get("latest_date"),
            strategy.get("status"),
            strategy.get("signal"),
            strategy.get("bollinger", {}).get("middle"),
            strategy.get("bollinger", {}).get("upper"),
            strategy.get("bollinger", {}).get("bandwidth"),
            strategy.get("volume", {}).get("ratio"),
            strategy.get("kd_golden_cross", {}).get("occurred"),
            strategy.get("stop_condition_met")
        )

        return result

    except Exception as exc:

        result["message"] = "技術分析資料取得失敗"

        result["error"] = str(exc)

        logging.exception(
            "%s 分析技術面發生錯誤。",
            stock_id
        )

        return result
