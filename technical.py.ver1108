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

    必要欄位：
    date、Trading_Volume、open、max、min、close
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

    RSI 通常介於 0 至 100。
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
    回傳：
    DIF、DEA、MACD 柱狀圖。
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
# 5. 技術面綜合分析
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

        "message": "資料不足"
    }

    try:
        # ----------------------------------------------------
        # 5.1 取得每日股價
        # ----------------------------------------------------

        days = max(
            int(settings.get("technical_days", 180)),
            120
        )

        start_date = (
            today - datetime.timedelta(days=days)
        ).strftime("%Y-%m-%d")

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
        # 5.2 計算均線
        # ----------------------------------------------------

        for period in [5, 10, 20, 60]:
            data[f"ma{period}"] = (
                data["close"].rolling(
                    period,
                    min_periods=period
                ).mean()
            )

        # ----------------------------------------------------
        # 5.3 計算 RSI、MACD、KD、成交量均線
        # ----------------------------------------------------

        data["rsi"] = calculate_rsi(
            data["close"],
            14
        )

        (
            data["macd_dif"],
            data["macd_dea"],
            data["macd_histogram"]
        ) = calculate_macd(
            data["close"]
        )

        data["kd_k"], data["kd_d"] = calculate_kd(
            data["max"],
            data["min"],
            data["close"]
        )

        data["volume_ma5"] = (
            data["Trading_Volume"].rolling(
                5,
                min_periods=5
            ).mean()
        )

        if len(data) < 60:
            result["message"] = (
                f"股價資料不足，需要至少 60 個交易日，"
                f"目前只有 {len(data)} 日"
            )
            return result

        # ----------------------------------------------------
        # 5.4 取得最新一個交易日的指標
        # ----------------------------------------------------

        latest = data.iloc[-1]

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
        # 5.5 均線分析：最高 15 分
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
        # 5.6 RSI 分析：最高 8 分
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
        # 5.7 MACD 分析：最高 8 分
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
        # 5.8 KD 分析：最高 5 分
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
        # 5.9 成交量分析：最高 4 分
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
        # 5.10 20 日高低點突破分析
        # ----------------------------------------------------

        # 排除最新交易日，以前 20 個交易日為比較區間
        previous_data = data.iloc[:-1].tail(20)

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
        # 5.11 計算技術面總分
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

        return result

    except Exception as exc:
        result["message"] = "技術分析資料取得失敗"
        result["error"] = str(exc)

        logging.exception(
            "%s 分析技術面發生錯誤。",
            stock_id
        )

        return result
