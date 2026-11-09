import datetime
import logging

import pandas as pd

from config import TAIPEI_TZ


logger = logging.getLogger(__name__)


# ============================================================
# 1. 排除尚未完成的當日 K 棒
# ============================================================

def exclude_incomplete_today_candle(data):
    """
    依台灣時間排除尚未完成的當日 K 棒。

    台股一般交易時段收盤時間：13:30。

    處理規則：
        1. 台灣時間 13:30（含）以前：
           排除日期等於今天的 K 棒。

        2. 台灣時間 13:31 起：
           允許納入今天的 K 棒。

        3. 過去交易日資料全部保留。

        4. 不修改原始 DataFrame。
    """

    if data is None or data.empty:
        return pd.DataFrame()

    if "date" not in data.columns:
        return data.copy()

    now = datetime.datetime.now(TAIPEI_TZ)
    taipei_today = now.date()

    before_daily_candle_complete = (
        (now.hour, now.minute) <= (13, 30)
    )

    if not before_daily_candle_complete:
        return data.copy().reset_index(drop=True)

    filtered_data = data.copy()

    date_series = pd.to_datetime(
        filtered_data["date"],
        errors="coerce"
    )

    if date_series.dt.tz is not None:
        date_series = (
            date_series.dt
            .tz_convert(TAIPEI_TZ)
            .dt.tz_localize(None)
        )

    completed_mask = (
        date_series.dt.date < taipei_today
    )

    excluded_count = int(
        (~completed_mask).sum()
    )

    filtered_data = (
        filtered_data.loc[completed_mask]
        .copy()
        .reset_index(drop=True)
    )

    if excluded_count > 0:
        logger.info(
            "排除尚未完成的當日 K 棒：台灣日期=%s，"
            "目前時間=%02d:%02d，排除 %s 筆，"
            "保留 %s 筆已完成行情。",
            taipei_today,
            now.hour,
            now.minute,
            excluded_count,
            len(filtered_data)
        )

    return filtered_data


# ============================================================
# 2. 整理每日股價資料
# ============================================================

def prepare_price_data(df):
    """
    整理 FinMind 每日股價資料。

    必要欄位：
        date、open、max、min、close

    Trading_Volume 可以缺少或有缺值：
        成交量缺漏不刪除價格資料。
        成交量指標另外排除缺值。

    處理原則：
        1. 日期及開高低收缺漏的 K 棒不參與指標計算。
        2. 成交量缺漏不直接刪除價格資料。
        3. 成交量不得為負數或無限值。
        4. 依日期排序，同日期保留最後一筆。
    """

    if df is None or df.empty:
        return pd.DataFrame()

    required = {
        "date",
        "open",
        "max",
        "min",
        "close"
    }

    missing = required - set(df.columns)

    if missing:
        logger.error(
            "股價資料缺少必要欄位：%s；實際欄位：%s",
            sorted(missing),
            list(df.columns)
        )
        return pd.DataFrame()

    columns = [
        "date",
        "open",
        "max",
        "min",
        "close"
    ]

    data = df[columns].copy()

    if "Trading_Volume" in df.columns:
        data["Trading_Volume"] = df[
            "Trading_Volume"
        ].copy()
    else:
        data["Trading_Volume"] = float("nan")

        logger.warning(
            "股價資料沒有 Trading_Volume 欄位，"
            "本次仍繼續計算價格技術指標。"
        )

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

        data[column] = data[column].replace(
            [float("inf"), float("-inf")],
            float("nan")
        )

    data = data.dropna(
        subset=[
            "date",
            "open",
            "max",
            "min",
            "close"
        ]
    )

    data = data[
        (data["open"] > 0)
        & (data["max"] > 0)
        & (data["min"] > 0)
        & (data["close"] > 0)
    ].copy()

    data = data[
        (data["max"] >= data["min"])
        & (data["max"] >= data["open"])
        & (data["max"] >= data["close"])
        & (data["min"] <= data["open"])
        & (data["min"] <= data["close"])
    ].copy()

    data.loc[
        data["Trading_Volume"] < 0,
        "Trading_Volume"
    ] = float("nan")

    data = (
        data.sort_values(
            "date",
            kind="mergesort"
        )
        .drop_duplicates(
            subset=["date"],
            keep="last"
        )
        .reset_index(drop=True)
    )

    return data
