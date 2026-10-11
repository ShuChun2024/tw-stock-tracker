import logging

from revenue import analyze_revenue
from foreign_holding import analyze_foreign_holding
from technical import analyze_technical
from institutional import analyze_institutional
from utils import number_or_none


# ============================================================
# 1. 三大法人籌碼評分
# ============================================================

INSTITUTIONAL_WEIGHTS = {
    "foreign": 7.0,
    "trust": 7.0,
    "dealer": 6.0,
}

# 不同期間訊號的權重
PERIOD_WEIGHTS = {
    "daily": 0.20,
    "5d": 0.35,
    "20d": 0.45,
}


def _direction(value):
    """
    將買賣超數值轉換為方向：
     1 = 買超
     0 = 持平
    -1 = 賣超
    None = 沒有有效資料
    """
    value = number_or_none(value)

    if value is None:
        return None

    if value > 0:
        return 1

    if value < 0:
        return -1

    return 0


def _calculate_institution_score(metric, max_score):
    """
    計算單一法人分數。

    最新交易日：20%
    近 5 日累計：35%
    近 20 日累計：45%

    連續買賣超天數用於調整最新交易日訊號，
    最高增加 25%，不額外重複加分。
    """

    if not isinstance(metric, dict):
        return None

    daily_value = metric.get("latest_net_shares")

    if daily_value is None:
        daily_value = metric.get("latest_net_lots")

    daily_signal = _direction(daily_value)

    signal_5d = _direction(metric.get("net_5d_shares"))

    if signal_5d is None:
        signal_5d = _direction(metric.get("net_5d_lots"))

    signal_20d = _direction(metric.get("net_20d_shares"))

    if signal_20d is None:
        signal_20d = _direction(metric.get("net_20d_lots"))

    # 當日方向資料缺失時，不計算該法人分數。
    if daily_signal is None:
        return None

    try:
        consecutive_days = max(
            0,
            int(metric.get("consecutive_days") or 0)
        )
    except (TypeError, ValueError, OverflowError):
        consecutive_days = 0

    # 只有當日買超或賣超才套用連續天數調整。
    if daily_signal != 0 and consecutive_days > 1:
        streak_factor = min(
            1.25,
            1.0 + 0.05 * (consecutive_days - 1)
        )
        adjusted_daily = daily_signal * streak_factor
    else:
        adjusted_daily = daily_signal

    signals = {
        "daily": adjusted_daily,
        "5d": signal_5d,
        "20d": signal_20d,
    }

    # 缺少期間資料時，重新分配可用權重。
    available_weight = sum(
        PERIOD_WEIGHTS[key]
        for key, value in signals.items()
        if value is not None
    )

    if available_weight <= 0:
        return None

    weighted_signal = sum(
        PERIOD_WEIGHTS[key] * value
        for key, value in signals.items()
        if value is not None
    ) / available_weight

    weighted_signal = max(
        -1.0,
        min(1.0, weighted_signal)
    )

    score = max_score * (1.0 + weighted_signal) / 2.0

    if daily_signal > 0:
        trend = "買超"
    elif daily_signal < 0:
        trend = "賣超"
    else:
        trend = "持平"

    return {
        "score": round(score, 2),
        "max_score": max_score,
        "daily_signal": daily_signal,
        "5d_signal": signal_5d,
        "20d_signal": signal_20d,
        "consecutive_days": consecutive_days,
        "trend": trend,
    }


def calculate_chip_score(institutional):
    """
    計算籌碼面總分，最高 20 分。

    外資：7 分
    投信：7 分
    自營商：6 分

    三大法人資料不完整時，不以缺失資料直接計 0 分。
    """

    if not isinstance(institutional, dict):
        return None, {}

    if not institutional.get("data_available", False):
        return None, {}

    details = {}

    for name, max_score in INSTITUTIONAL_WEIGHTS.items():
        metric = institutional.get(name)

        result = _calculate_institution_score(
            metric,
            max_score
        )

        if result is None:
            logging.warning(
                "三大法人評分失敗：%s 缺少有效方向資料",
                name
            )
            return None, details

        details[name] = result

    total = sum(
        item["score"]
        for item in details.values()
    )

    return round(total, 1), details


# ============================================================
# 2. 計算綜合評分
# ============================================================

def calculate_overall_score(
    revenue,
    foreign_holding,
    technical,
    institutional,
):
    """
    基本面：最高 40 分
    籌碼面：最高 20 分
    技術面：最高 40 分

    外資持股比例僅作輔助分析，不納入綜合總分。
    """

    analyses = [
        revenue,
        technical,
    ]

    if not all(
        isinstance(item, dict)
        and item.get("data_available", False)
        for item in analyses
    ):
        return None

    revenue_score = number_or_none(
        revenue.get("score")
    )

    technical_score = number_or_none(
        technical.get("score")
    )

    if revenue_score is None or technical_score is None:
        return None

    chip_score, _ = calculate_chip_score(institutional)

    if chip_score is None:
        return None

    total = (
        revenue_score
        + chip_score
        + technical_score
    )

    return round(
        min(max(total, 0), 100),
        1
    )


# ============================================================
# 3. 依照分數判斷股票狀態
# ============================================================

def get_status(score):
    score = number_or_none(score)

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
# 4. 分析單一股票
# ============================================================

def analyze_stock(
    dl,
    stock_id,
    settings,
    today
):
    logging.info("=" * 60)
    logging.info("開始分析股票：%s", stock_id)

    # --------------------------------------------------------
    # 4.1 基本面
    # --------------------------------------------------------

    revenue = analyze_revenue(
        dl,
        stock_id,
        settings,
        today
    )

    # --------------------------------------------------------
    # 4.2 外資持股比例：輔助資訊
    # --------------------------------------------------------

    foreign_holding = analyze_foreign_holding(
        dl,
        stock_id,
        settings,
        today
    )

    # --------------------------------------------------------
    # 4.3 三大法人買賣超
    # --------------------------------------------------------

    institutional = analyze_institutional(
        dl,
        stock_id,
        settings,
        today
    )

    # --------------------------------------------------------
    # 4.4 技術面
    # --------------------------------------------------------

    technical = analyze_technical(
        dl,
        stock_id,
        settings,
        today
    )

    # --------------------------------------------------------
    # 4.5 計算籌碼面分數
    # --------------------------------------------------------

    chip_score, chip_details = calculate_chip_score(
        institutional
    )

    # --------------------------------------------------------
    # 4.6 計算綜合分數
    # --------------------------------------------------------

    score = calculate_overall_score(
        revenue,
        foreign_holding,
        technical,
        institutional,
    )

    # --------------------------------------------------------
    # 4.7 記錄缺少的分析資料
    # --------------------------------------------------------

    missing_items = []

    if (
        not isinstance(revenue, dict)
        or not revenue.get("data_available", False)
    ):
        missing_items.append("營收")

    if (
        not isinstance(foreign_holding, dict)
        or not foreign_holding.get("data_available", False)
    ):
        missing_items.append("外資持股")

    if (
        not isinstance(institutional, dict)
        or not institutional.get("data_available", False)
    ):
        missing_items.append("三大法人買賣超")

    elif chip_score is None:
        missing_items.append("三大法人評分資料")

    if (
        not isinstance(technical, dict)
        or not technical.get("data_available", False)
    ):
        missing_items.append("技術面")

    # --------------------------------------------------------
    # 4.8 資料完整性標記
    # --------------------------------------------------------

    data_complete = len(missing_items) == 0
    score_complete = score is not None

    # --------------------------------------------------------
    # 4.9 組合分析結果
    # --------------------------------------------------------

    result = {
        "stock_id": stock_id,

        "analysis_date": today.strftime("%Y-%m-%d"),

        "revenue": revenue,

        "foreign_holding": foreign_holding,

        "institutional": institutional,

        "technical": technical,

        "chip_score": chip_score,

        "chip_score_details": chip_details,

        "score_breakdown": {
            "fundamental": (
                number_or_none(revenue.get("score"))
                if isinstance(revenue, dict)
                else None
            ),
            "chip": chip_score,
            "technical": (
                number_or_none(technical.get("score"))
                if isinstance(technical, dict)
                else None
            ),
        },

        "score": score,

        "status": get_status(score),

        "data_quality": {
            # 保留舊欄位及其原有意義
            "complete": data_complete,

            # 新增：所有檢查項目是否完整
            "data_complete": data_complete,

            # 新增：是否有有效的綜合總分
            "score_complete": score_complete,

            # 保留原本的缺漏資料清單
            "missing_items": missing_items
        }
    }

    logging.info(
        "完成分析：%s，基本面=%s，籌碼面=%s，"
        "技術面=%s，綜合分數=%s，狀態=%s，缺少資料=%s",
        stock_id,
        result["score_breakdown"]["fundamental"],
        chip_score,
        result["score_breakdown"]["technical"],
        score,
        result["status"],
        missing_items
    )

    return result


# ============================================================
# 5. 建立分析失敗時的預設結果
# ============================================================

def failed_result(stock_id, today):
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

        "institutional": {
            "data_available": False,
            "latest_date": None,
            "foreign": {
                "trend": "資料不足"
            },
            "trust": {
                "trend": "資料不足"
            },
            "dealer": {
                "trend": "資料不足"
            },
            "summary": "資料不足",
            "message": "分析失敗"
        },

        "technical": {
            "score": None,
            "data_available": False,
            "latest_date": None,
            "latest_close": None,
            "message": "分析失敗"
        },

        "chip_score": None,

        "chip_score_details": {},

        "score_breakdown": {
            "fundamental": None,
            "chip": None,
            "technical": None,
        },

        "score": None,

        "status": "⚪ 資料不足",

        "data_quality": {
            "complete": False,
            "data_complete": False,
            "score_complete": False,
            "missing_items": [
                "營收",
                "外資持股",
                "三大法人買賣超",
                "技術面"
            ]
        }
    }
