import datetime
import logging

import pandas as pd


# ============================================================
# 1. 外資持股分析
# ============================================================

def analyze_foreign_holding(dl, stock_id, settings, today):
    """
    分析外資持股比例與近期趨勢。

    評分規則：
    - 最近數期持股比例連續增加：20 分
    - 整體增加：15 分
    - 大致持平：8 分
    - 整體減少：0 分

    籌碼面最高 20 分。
    """

    result = {
        "score": None,
        "trend": "資料不足",
        "latest_percent": None,
        "change_periods": None,
        "latest_date": None,
        "message": "資料不足",
        "data_available": False
    }

    try:
        # ----------------------------------------------------
        # 2. 設定分析期間
        # ----------------------------------------------------

        periods = max(
            int(settings.get("foreign_periods", 4)),
            2
        )

        start_date = (
            today - datetime.timedelta(days=180)
        ).strftime("%Y-%m-%d")

        # ----------------------------------------------------
        # 3. 取得 FinMind 外資持股資料
        # ----------------------------------------------------

        df = dl.taiwan_stock_shareholding(
            stock_id=stock_id,
            start_date=start_date
        )
        print(
            f"[外資持股] {stock_id} 最後日期：",
            df["date"].max() if df is not None and not df.empty else "無資料"
        )

        if df is None or df.empty:
            result["message"] = "沒有外資持股資料"
            return result

        required_columns = [
            "date",
            "ForeignInvestmentSharesRatio"
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            result["message"] = (
                "外資持股資料缺少必要欄位："
                + ", ".join(missing_columns)
            )

            logging.error(
                "%s 外資持股欄位不完整，實際欄位：%s",
                stock_id,
                list(df.columns)
            )

            return result

        # ----------------------------------------------------
        # 4. 整理資料
        # ----------------------------------------------------

        data = df[
            ["date", "ForeignInvestmentSharesRatio"]
        ].copy()

        data["date"] = pd.to_datetime(
            data["date"],
            errors="coerce"
        )

        data["ratio"] = pd.to_numeric(
            data["ForeignInvestmentSharesRatio"],
            errors="coerce"
        )

        data = data.dropna(
            subset=["date", "ratio"]
        )

        data = (
            data.sort_values("date")
            .drop_duplicates(
                subset=["date"],
                keep="last"
            )
            .reset_index(drop=True)
        )

        if len(data) < periods:
            result["message"] = (
                f"外資持股資料不足，需要 {periods} 期，"
                f"目前只有 {len(data)} 期"
            )
            return result

        # ----------------------------------------------------
        # 5. 計算最近數期的持股變化
        # ----------------------------------------------------

        recent = data.tail(periods).reset_index(drop=True)

        ratios = recent["ratio"].astype(float).tolist()

        latest = ratios[-1]
        change = latest - ratios[0]

        result["latest_percent"] = latest
        result["change_periods"] = change
        result["latest_date"] = (
            recent.iloc[-1]["date"].strftime("%Y-%m-%d")
        )

        # 計算每一期的持股比例變化
        differences = [
            ratios[index] - ratios[index - 1]
            for index in range(1, len(ratios))
        ]

        # ----------------------------------------------------
        # 6. 判斷外資持股趨勢及評分
        # ----------------------------------------------------

        if all(value > 0 for value in differences):
            trend = "連續增加"
            score = 20
            message = (
                f"最近 {periods} 期外資持股比例連續增加"
            )

        elif change > 0:
            trend = "整體增加"
            score = 15
            message = (
                f"最近 {periods} 期外資持股比例整體增加"
            )

        elif change == 0:
            trend = "大致持平"
            score = 8
            message = (
                f"最近 {periods} 期外資持股比例大致持平"
            )

        else:
            trend = "整體減少"
            score = 0
            message = (
                f"最近 {periods} 期外資持股比例整體減少"
            )

        result.update({
            "trend": trend,
            "score": score,
            "message": message,
            "data_available": True
        })

        logging.info(
            "%s 外資持股：日期=%s，比例=%.4f，"
            "變化=%.4f，趨勢=%s，分數=%s",
            stock_id,
            result["latest_date"],
            latest,
            change,
            trend,
            score
        )

        return result

    except Exception as exc:
        result["message"] = "外資持股資料取得失敗"
        result["error"] = str(exc)

        logging.exception(
            "%s 分析外資持股發生錯誤。",
            stock_id
        )

        return result
