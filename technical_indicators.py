import pandas as pd


# ============================================================
# 1. 計算 RSI 相對強弱指標
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

    # 只有上漲、沒有下跌。
    rsi.loc[
        (avg_loss == 0) & (avg_gain > 0)
    ] = 100.0

    # 沒有漲跌。
    rsi.loc[
        (avg_loss == 0)
        & (avg_gain == 0)
        & avg_gain.notna()
    ] = 50.0

    return rsi


# ============================================================
# 2. 計算 MACD
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
# 3. 計算 KD 隨機指標
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

    當區間最高價等於最低價時：
        RSV 使用 50，避免 KD 計算中斷。
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

    zero_range = (
        denominator.notna()
        & (denominator == 0)
    )

    rsv.loc[zero_range] = 50.0

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
        index=close.index,
        dtype="float64"
    )

    d_series = pd.Series(
        d_values,
        index=close.index,
        dtype="float64"
    )

    return k_series, d_series
