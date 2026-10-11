import datetime
import logging

import pandas as pd


# ============================================================
# 三大法人買賣超分析
# ============================================================

def _empty_result(message="資料不足"):
    """建立資料不足時的預設結果。"""

    empty_metric = {
        "latest_net_shares": None,
        "latest_net_lots": None,
        "net_5d_shares": None,
        "net_5d_lots": None,
        "net_20d_shares": None,
        "net_20d_lots": None,
        "consecutive_days": 0,
        "trend": "資料不足",
    }

    return {
        "data_available": False,
        "latest_date": None,
        "foreign": dict(empty_metric),
        "trust": dict(empty_metric),
        "dealer": dict(empty_metric),
        "summary": "資料不足",
        "message": message,
    }


def _get_trend(net_shares):
    """依買賣超判斷方向。"""

    if net_shares > 0:
        return "買超"

    if net_shares < 0:
        return "賣超"

    return "持平"


def _build_metric(series):
    """計算單一法人指標。"""

    values = series.tolist()

    if not values:
        return _empty_result()["foreign"]

    latest = int(values[-1])

    # 從最近一個交易日往前計算連續買賣超天數
    consecutive_days = 0

    if latest != 0:
        direction = 1 if latest > 0 else -1

        for value in reversed(values):
            if value * direction > 0:
                consecutive_days += 1
            else:
                break

    net_5d = int(sum(values[-5:])) if len(values) >= 5 else None
    net_20d = int(sum(values[-20:])) if len(values) >= 20 else None

    return {
        "latest_net_shares": latest,
        "latest_net_lots": round(latest / 1000, 1),
        "net_5d_shares": net_5d,
        "net_5d_lots": (
            round(net_5d / 1000, 1)
            if net_5d is not None else None
        ),
        "net_20d_shares": net_20d,
        "net_20d_lots": (
            round(net_20d / 1000, 1)
            if net_20d is not None else None
        ),
        "consecutive_days": consecutive_days,
        "trend": _get_trend(latest),
    }


def analyze_institutional(
    dl,
    stock_id,
    settings,
    today
):
    """
    分析個股三大法人買賣超。

    外資：
        Foreign_Investor
        Foreign_Dealer_Self

    投信：
        Investment_Trust

    自營商：
        Dealer_self
        Dealer_Hedging

    買賣超 = 買進股數 - 賣出股數

    近 5 日及 20 日依實際取得的交易日期計算。
    不足 5 或 20 個交易日時，不產生該期間的累計值。
    """

    try:
        # 預設回溯 90 個日曆日，以涵蓋足夠交易日。
        lookback_days = int(
            settings.get("institutional_lookback_days", 90)
        )

        start_date = (
            today - datetime.timedelta(days=lookback_days)
        ).strftime("%Y-%m-%d")

        end_date = today.strftime("%Y-%m-%d")

        logging.info(
            "%s 開始取得三大法人資料，期間：%s～%s",
            stock_id,
            start_date,
            end_date
        )

        df = dl.taiwan_stock_institutional_investors(
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date
        )

        if df is None or df.empty:
            logging.warning(
                "%s 沒有三大法人資料",
                stock_id
            )
            return _empty_result("查無三大法人資料")

        required_columns = {
            "date", "name", "buy", "sell"
        }

        if not required_columns.issubset(df.columns):
            logging.warning(
                "%s 三大法人資料缺少必要欄位",
                stock_id
            )
            return _empty_result("資料欄位不完整")

        df = df.copy()

        # 僅使用已知法人類別
        valid_names = {
            "Foreign_Investor",
            "Foreign_Dealer_Self",
            "Investment_Trust",
            "Dealer_self",
            "Dealer_Hedging",
        }

        df = df[df["name"].isin(valid_names)].copy()

        if df.empty:
            return _empty_result("沒有可辨識的法人資料")

        df["date"] = pd.to_datetime(
            df["date"], errors="coerce"
        )

        df["buy"] = pd.to_numeric(
            df["buy"], errors="coerce"
        )

        df["sell"] = pd.to_numeric(
            df["sell"], errors="coerce"
        )

        df = df.dropna(
            subset=["date", "buy", "sell"]
        )

        if df.empty:
            return _empty_result("法人資料格式異常")

        # 買賣超以股數計算
        df["net_shares"] = df["buy"] - df["sell"]

        # ----------------------------------------------------
        # 依照法人類別彙整
        # ----------------------------------------------------

        foreign_names = [
            "Foreign_Investor",
            "Foreign_Dealer_Self",
        ]

        trust_names = [
            "Investment_Trust",
        ]

        dealer_names = [
            "Dealer_self",
            "Dealer_Hedging",
        ]

        foreign = (
            df[df["name"].isin(foreign_names)]
            .groupby("date")["net_shares"]
            .sum()
            .rename("foreign")
        )

        trust = (
            df[df["name"].isin(trust_names)]
            .groupby("date")["net_shares"]
            .sum()
            .rename("trust")
        )

        dealer = (
            df[df["name"].isin(dealer_names)]
            .groupby("date")["net_shares"]
            .sum()
            .rename("dealer")
        )

        # 以實際回傳的交易日期建立時間序列。
        # 未出現的法人類別在該日期填 0。
        daily = pd.concat(
            [foreign, trust, dealer],
            axis=1
        ).fillna(0)

        daily = daily.sort_index()

        if daily.empty:
            return _empty_result("沒有有效交易日期")

        # 只保留最近分析日期以前的資料
        daily = daily[
            daily.index.date <= today
        ]

        if daily.empty:
            return _empty_result("沒有可用的最新交易資料")

        latest_date = daily.index[-1].strftime("%Y-%m-%d")

        # ----------------------------------------------------
        # 建立分析結果
        # ----------------------------------------------------

        foreign_metric = _build_metric(daily["foreign"])
        trust_metric = _build_metric(daily["trust"])
        dealer_metric = _build_metric(daily["dealer"])

        latest_values = [
            int(daily["foreign"].iloc[-1]),
            int(daily["trust"].iloc[-1]),
            int(daily["dealer"].iloc[-1]),
        ]

        if all(value > 0 for value in latest_values):
            summary = "三大法人同步買超"

        elif all(value < 0 for value in latest_values):
            summary = "三大法人同步賣超"

        elif all(value == 0 for value in latest_values):
            summary = "三大法人當日皆持平"

        else:
            summary = "三大法人方向分歧"

        result = {
            "data_available": True,
            "latest_date": latest_date,
            "foreign": foreign_metric,
            "trust": trust_metric,
            "dealer": dealer_metric,
            "summary": summary,
            "message": "分析完成",
        }

        logging.info(
            "%s 三大法人分析完成：%s",
            stock_id,
            summary
        )

        return result

    except Exception:
        logging.exception(
            "%s 三大法人分析失敗",
            stock_id
        )

        return _empty_result("取得三大法人資料失敗")
