import logging

from revenue import analyze_revenue
from foreign_holding import analyze_foreign_holding
from technical import analyze_technical
from utils import number_or_none


# ============================================================
# 1. 計算綜合評分
# ============================================================

def calculate_overall_score(
    revenue,
    foreign_holding,
    technical
):
    """
    計算個股綜合分數。

    基本面：最高 40 分
    籌碼面：最高 20 分
    技術面：最高 40 分

    三項分析資料都完整時，才計算綜合分數。
    """

    analyses = [
        revenue,
        foreign_holding,
        technical
    ]

    # 任一項資料不足，就不產生完整綜合分數
    if not all(
        item.get("data_available", False)
        for item in analyses
    ):
        return None

    scores = [
        number_or_none(item.get("score"))
        for item in analyses
    ]

    if any(score is None for score in scores):
        return None

    total = sum(scores)

    # 綜合分數最高為 100 分
    return round(min(max(total, 0), 100), 1)


# ============================================================
# 2. 依照分數判斷股票狀態
# ============================================================

def get_status(score):
    """
    將綜合分數轉換成狀態文字。
    """

    if score is None:
        return "⚪ 資料不足"

    if score >= 80:
        return "🟢 強勢"

    if score >= 65:
        return "🟡 偏多"

    if score >= 50:
        return "⚪ 中性"

    if score >= 30:
        return "🟠 偏弱"

    return "🔴 弱勢"


# ============================================================
# 3. 分析單一股票
# ============================================================

def analyze_stock(
    dl,
    stock_id,
    settings,
    today
):
    """
    執行單一股票的完整分析。

    包含：
    1. 月營收基本面分析
    2. 外資持股籌碼面分析
    3. 技術指標分析
    4. 綜合評分與資料完整度判斷
    """

    logging.info("=" * 60)
    logging.info("開始分析股票：%s", stock_id)

    # --------------------------------------------------------
    # 3.1 基本面
    # --------------------------------------------------------

    revenue = analyze_revenue(
        dl,
        stock_id,
        settings,
        today
    )

    # --------------------------------------------------------
    # 3.2 籌碼面
    # --------------------------------------------------------

    foreign_holding = analyze_foreign_holding(
        dl,
        stock_id,
        settings,
        today
    )

    # --------------------------------------------------------
    # 3.3 技術面
    # --------------------------------------------------------

    technical = analyze_technical(
        dl,
        stock_id,
        settings,
        today
    )

    # --------------------------------------------------------
    # 3.4 計算綜合分數
    # --------------------------------------------------------

    score = calculate_overall_score(
        revenue,
        foreign_holding,
        technical
    )

    # --------------------------------------------------------
    # 3.5 記錄缺少的分析資料
    # --------------------------------------------------------

    missing_items = []

    if not revenue.get("data_available", False):
        missing_items.append("營收")

    if not foreign_holding.get("data_available", False):
        missing_items.append("外資持股")

    if not technical.get("data_available", False):
        missing_items.append("技術面")

    # --------------------------------------------------------
    # 3.6 組合分析結果
    # --------------------------------------------------------

    result = {
        "stock_id": stock_id,
        "analysis_date": today.strftime("%Y-%m-%d"),

        "revenue": revenue,

        "foreign_holding": foreign_holding,

        "technical": technical,

        "score": score,

        "status": get_status(score),

        "data_quality": {
            "complete": len(missing_items) == 0,
            "missing_items": missing_items
        }
    }

    logging.info(
        "完成分析：%s，綜合分數=%s，狀態=%s，缺少資料=%s",
        stock_id,
        score,
        result["status"],
        missing_items
    )

    return result


# ============================================================
# 4. 建立分析失敗時的預設結果
# ============================================================

def failed_result(stock_id, today):
    """
    當單一股票分析發生未預期錯誤時，
    建立欄位完整的預設結果，避免整批股票中斷。
    """

    return {
        "stock_id": stock_id,

        "analysis_date": today.strftime("%Y-%m-%d"),

        "revenue": {
            "score": None,
            "latest_yoy": None,
            "trend": "資料不足",
            "latest_revenue": None,
            "latest_revenue_month": None,
            "message": "分析失敗",
            "data_available": False
        },

        "foreign_holding": {
            "score": None,
            "trend": "資料不足",
            "latest_percent": None,
            "change_periods": None,
            "latest_date": None,
            "message": "分析失敗",
            "data_available": False
        },

        "technical": {
            "score": None,
            "data_available": False,
            "latest_date": None,
            "latest_close": None,
            "message": "分析失敗"
        },

        "score": None,

        "status": "⚪ 資料不足",

        "data_quality": {
            "complete": False,
            "missing_items": [
                "營收",
                "外資持股",
                "技術面"
            ]
        }
    }
