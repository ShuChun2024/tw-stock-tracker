import datetime
import logging

import pandas as pd


# ============================================================
# 1. 整理月營收資料
# ============================================================

def prepare_revenue_data(df):
    """
    整理 FinMind 月營收資料。

    必要欄位：
    - date
    - revenue

    若資料包含 revenue_year、revenue_month，
    優先使用這兩個欄位判斷營收所屬年月。
    """

    if (
        df is None
        or df.empty
        or not {"date", "revenue"}.issubset(df.columns)
    ):
        if df is not None and not df.empty:
            logging.error(
                "月營收欄位不完整：%s",
                list(df.columns)
            )

        return pd.DataFrame()

    data = df.copy()

    # 日期與營收轉換
    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce"
    )

    data["revenue"] = pd.to_numeric(
        data["revenue"],
        errors="coerce"
    )

    # 從日期取得年份及月份
    date_year = data["date"].dt.year
    date_month = data["date"].dt.month

    # 優先使用 FinMind 提供的營收年月
    if "revenue_year" in data.columns:
        revenue_year = pd.to_numeric(
            data["revenue_year"],
            errors="coerce"
        )

        data["period_year"] = revenue_year.where(
            revenue_year.notna(),
            date_year
        )
    else:
        data["period_year"] = date_year

    if "revenue_month" in data.columns:
        revenue_month = pd.to_numeric(
            data["revenue_month"],
            errors="coerce"
        )

        data["period_month"] = revenue_month.where(
            revenue_month.notna(),
            date_month
        )
    else:
        data["period_month"] = date_month

    # 移除無效資料
    data = data.dropna(
        subset=[
            "date",
            "revenue",
            "period_year",
            "period_month"
        ]
    )

    data["period_year"] = data["period_year"].astype(int)
    data["period_month"] = data["period_month"].astype(int)

    # 排除不合理的月份
    data = data[
        data["period_month"].between(1, 12)
    ]

    # 同一營收年月若有重複資料，保留日期較新的紀錄
    data = (
        data.sort_values("date")
        .drop_duplicates(
            subset=["period_year", "period_month"],
            keep="last"
        )
    )

    # 按照營收年月排序
    data = data.sort_values(
        ["period_year", "period_month"]
    ).reset_index(drop=True)

    return data


# ============================================================
# 2. 分析月營收與營收年增率
# ============================================================

def analyze_revenue(dl, stock_id, settings, today):
    """
    分析個股月營收。

    評分規則：
    - 年增率 >= 30%：25 分
    - 年增率 >= 設定目標：20 分
    - 年增率 >= 10%：15 分
    - 年增率 >= 0%：8 分
    - 年增率 < 0%：0 分
    - 最近指定月份營收逐月增加：額外 15 分

    基本面最高 40 分。
    """

    result = {
        "score": None,
        "latest_yoy": None,
        "trend": "資料不足",
        "latest_revenue": None,
        "latest_revenue_month": None,
        "message": "資料不足",
        "data_available": False
    }

    try:
        # 取得最近約 500 天的月營收資料
        start_date = (
            today - datetime.timedelta(days=500)
        ).strftime("%Y-%m-%d")

        raw_data = dl.taiwan_stock_month_revenue(
            stock_id=stock_id,
            start_date=start_date
        )

        data = prepare_revenue_data(raw_data)

        if data.empty:
            result["message"] = "沒有可用的月營收資料"

            logging.warning(
                "%s 月營收資料為空。",
                stock_id
            )

            return result

        # 取得最新一筆營收
        latest = data.iloc[-1]

        year = int(latest["period_year"])
        month = int(latest["period_month"])
        revenue = float(latest["revenue"])

        result["latest_revenue"] = revenue
        result["latest_revenue_month"] = (
            f"{year:04d}-{month:02d}"
        )

        # ----------------------------------------------------
        # 計算營收年增率
        # ----------------------------------------------------

        previous_year_data = data[
            (data["period_year"] == year - 1)
            & (data["period_month"] == month)
        ]

        yoy = None

        if not previous_year_data.empty:
            previous_revenue = float(
                previous_year_data.iloc[-1]["revenue"]
            )

            if previous_revenue != 0:
                yoy = (
                    revenue / previous_revenue - 1
                ) * 100

        result["latest_yoy"] = yoy

        # ----------------------------------------------------
        # 判斷近期營收趨勢
        # ----------------------------------------------------

        months = max(
            int(settings.get("revenue_months", 3)),
            2
        )

        recent_data = data.tail(months)

        trend_available = len(recent_data) >= months
        revenue_increasing = False

        if trend_available:
            values = recent_data["revenue"].tolist()

            revenue_increasing = all(
                values[index] > values[index - 1]
                for index in range(1, len(values))
            )

            result["trend"] = (
                "連續增加"
                if revenue_increasing
                else "未連續增加"
            )

        # ----------------------------------------------------
        # 資料不足時不進行完整評分
        # ----------------------------------------------------

        if yoy is None:
            result["message"] = (
                "缺少去年同期營收，無法計算年增率"
            )
            return result

        if not trend_available:
            result["message"] = (
                "營收月份不足，無法判斷趨勢"
            )
            return result

        # ----------------------------------------------------
        # 計算營收分數
        # ----------------------------------------------------

        target_yoy = float(
            settings.get("revenue_yoy_target", 20)
        )

        if yoy >= 30:
            yoy_score = 25
        elif yoy >= target_yoy:
            yoy_score = 20
        elif yoy >= 10:
            yoy_score = 15
        elif yoy >= 0:
            yoy_score = 8
        else:
            yoy_score = 0

        trend_score = (
            15 if revenue_increasing else 0
        )

        result["score"] = yoy_score + trend_score
        result["data_available"] = True

        # ----------------------------------------------------
        # 產生分析說明
        # ----------------------------------------------------

        if yoy >= target_yoy and revenue_increasing:
            result["message"] = (
                "年增率達標且營收連續增加"
            )
        elif yoy >= 0:
            result["message"] = "營收年增率為正"
        else:
            result["message"] = "營收年增率為負"

        logging.info(
            "%s 營收：%s，YoY=%.2f%%，趨勢=%s，分數=%s",
            stock_id,
            result["latest_revenue_month"],
            yoy,
            result["trend"],
            result["score"]
        )

        return result

    except Exception as exc:
        result["message"] = "營收資料取得失敗"
        result["error"] = str(exc)

        logging.exception(
            "%s 分析月營收發生錯誤。",
            stock_id
        )

        return result
