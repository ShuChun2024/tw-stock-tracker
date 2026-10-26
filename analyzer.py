import logging
from functools import lru_cache
from pathlib import Path
import pandas as pd
from revenue import analyze_revenue
from foreign_holding import analyze_foreign_holding
from technical import analyze_technical
from institutional import analyze_institutional
from utils import number_or_none
# ============================================================
# Logger 設定
# ============================================================
logger = logging.getLogger(__name__)
# ============================================================
# 0. 估值 CSV 設定
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
VALUATION_FILE = BASE_DIR / "twse_valuation_latest.csv"
VALUATION_COLUMNS = [
    "valuation_date",
    "stock_id",
    "stock_name",
    "close_price",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield",
    "dividend_year",
    "financial_period",
]
def _normalize_stock_id(value):
    """統一股票代號格式，例如 2330、2330.0 都轉成 2330。"""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    stock_id = str(value).strip()
    if not stock_id or stock_id.lower() in {"nan", "none", "null"}:
        return None
    if stock_id.endswith(".0"):
        stock_id = stock_id[:-2]
    return stock_id.zfill(4)
def _valuation_number(value):
    """
    將估值數值轉為 int、float 或 None。
    nan、空字串、破折號及無效數值皆轉為 None。
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {
        "nan", "none", "null", "na", "n/a"
    }:
        return None
    if text in {"-", "—", "－"}:
        return None
    try:
        number = float(text.replace(",", ""))
        if pd.isna(number):
            return None
        if number.is_integer():
            return int(number)
        return number
    except (TypeError, ValueError, OverflowError):
        return None
def _valuation_text(value):
    """將 CSV 文字欄位中的空值轉成 None。"""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {
        "nan", "none", "null"
    }:
        return None
    return text
@lru_cache(maxsize=1)
def _load_valuation_csv():
    """
    載入最新估值 CSV。
    每次 Python 程序執行期間只載入一次，
    避免每分析一檔股票就重新讀取 CSV。
    回傳：
        (估值資料字典, 錯誤訊息)
    估值資料字典以股票代號為 key。
    """
    if not VALUATION_FILE.exists():
        message = f"估值 CSV 不存在：{VALUATION_FILE.name}"
        logger.warning("%s", message)
        return {}, message
    try:
        df = pd.read_csv(
            VALUATION_FILE,
            encoding="utf-8-sig",
            dtype={"stock_id": str},
            keep_default_na=True,
        )
    except Exception:
        logger.exception(
            "讀取估值 CSV 失敗：檔案=%s",
            VALUATION_FILE
        )
        message = f"讀取估值 CSV 失敗：{VALUATION_FILE.name}"
        return {}, message
    if df.empty:
        message = "估值 CSV 沒有資料"
        logger.warning("%s", message)
        return {}, message
    # --------------------------------------------------------
    # 必要欄位檢查
    # --------------------------------------------------------
    required_columns = [
        "valuation_date",
        "stock_id",
    ]
    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]
    if missing_columns:
        message = (
            "估值 CSV 缺少必要欄位："
            f"{missing_columns}"
        )
        logger.warning("%s", message)
        return {}, message
    # --------------------------------------------------------
    # 確認估值日期及股票代號
    # --------------------------------------------------------
    df["stock_id"] = df["stock_id"].apply(
        _normalize_stock_id
    )
    df["valuation_date"] = df["valuation_date"].apply(
        _valuation_text
    )
    df = df[
        df["stock_id"].notna()
        & df["valuation_date"].notna()
    ].copy()
    if df.empty:
        message = "估值 CSV 沒有有效股票代號或估值日期"
        logger.warning("%s", message)
        return {}, message
    # --------------------------------------------------------
    # 建立股票代號索引
    # --------------------------------------------------------
    valuation_index = {}
    for _, row in df.iterrows():
        stock_id = row["stock_id"]
        valuation_index[stock_id] = {
            "valuation_date": row["valuation_date"],
            "stock_name": _valuation_text(
                row.get("stock_name")
            ),
            "close_price": _valuation_number(
                row.get("close_price")
            ),
            "pe_ratio": _valuation_number(
                row.get("pe_ratio")
            ),
            "pb_ratio": _valuation_number(
                row.get("pb_ratio")
            ),
            "dividend_yield": _valuation_number(
                row.get("dividend_yield")
            ),
            "dividend_year": _valuation_number(
                row.get("dividend_year")
            ),
            "financial_period": _valuation_text(
                row.get("financial_period")
            ),
        }
    logger.info(
        "估值 CSV 載入成功：檔案=%s，股票筆數=%d",
        VALUATION_FILE.name,
        len(valuation_index),
    )
    logger.info(
        "估值資料日期：%s",
        sorted(
            {
                item["valuation_date"]
                for item in valuation_index.values()
            }
        ),
    )
    return valuation_index, ""
def analyze_valuation_from_csv(stock_id):
    """
    從 twse_valuation_latest.csv 取得單一股票估值。
    不直接呼叫 TWSE API。
    估值缺失不影響原本的評分與資料完整性。
    回傳欄位：
        valuation_date
        stock_name
        close_price
        pe_ratio
        pb_ratio
        dividend_yield
        dividend_year
        financial_period
        data_available
        message
    """
    stock_id = _normalize_stock_id(stock_id)
    result = {
        "valuation_date": None,
        "stock_name": None,
        "close_price": None,
        "pe_ratio": None,
        "pb_ratio": None,
        "dividend_yield": None,
        "dividend_year": None,
        "financial_period": None,
        "data_available": False,
        "message": "",
    }
    if stock_id is None:
        result["message"] = "股票代號無效"
        return result
    valuation_index, load_message = _load_valuation_csv()
    if not valuation_index:
        result["message"] = load_message or "估值資料不可用"
        return result
    row = valuation_index.get(stock_id)
    if row is None:
        result["message"] = (
            f"估值 CSV 查無股票 {stock_id}"
        )
        return result
    result.update(row)
    result["data_available"] = True
    result["message"] = ""
    return result
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
    # 當期間資料缺失時，重新分配可用權重。
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
            logger.warning(
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
    logger.info("=" * 60)
    logger.info("開始分析股票：%s", stock_id)
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
    # 4.5 估值資料：讀取 CSV，不呼叫 TWSE API
    # --------------------------------------------------------
    try:
        valuation = analyze_valuation_from_csv(stock_id)
    except Exception:
        # logger.exception 會保留完整例外堆疊（Traceback）。
        # 估值是獨立輔助資料，失敗不能中斷主要分析。
        logger.exception(
            "估值資料處理失敗：stock_id=%s",
            stock_id
        )
        valuation = {
            "valuation_date": None,
            "stock_name": None,
            "close_price": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "dividend_yield": None,
            "dividend_year": None,
            "financial_period": None,
            "data_available": False,
            "message": "估值資料處理失敗",
        }
    # --------------------------------------------------------
    # 4.6 計算籌碼面分數
    # --------------------------------------------------------
    chip_score, chip_details = calculate_chip_score(
        institutional
    )
    # --------------------------------------------------------
    # 4.7 計算綜合分數
    # --------------------------------------------------------
    score = calculate_overall_score(
        revenue,
        foreign_holding,
        technical,
        institutional,
    )
    # --------------------------------------------------------
    # 4.8 記錄缺少的分析資料
    #     注意：估值不加入 missing_items
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
    # 4.9 資料完整性標記
    #     維持原本規則，不將估值納入
    # --------------------------------------------------------
    data_complete = len(missing_items) == 0
    score_complete = score is not None
    # --------------------------------------------------------
    # 4.10 組合分析結果
    # --------------------------------------------------------
    result = {
        "stock_id": stock_id,
        "analysis_date": today.strftime("%Y-%m-%d"),
        "revenue": revenue,
        "foreign_holding": foreign_holding,
        "institutional": institutional,
        "technical": technical,
        # 估值資料：獨立輔助欄位
        "valuation": valuation,
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
            "complete": data_complete,
            "data_complete": data_complete,
            "score_complete": score_complete,
            "missing_items": missing_items
        }
    }
    logger.info(
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
    logger.info(
        "估值資料：%s，日期=%s，是否可用=%s，訊息=%s",
        stock_id,
        valuation.get("valuation_date"),
        valuation.get("data_available"),
        valuation.get("message"),
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
        # 失敗結果也保留一致的估值結構
        "valuation": {
            "valuation_date": None,
            "stock_name": None,
            "close_price": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "dividend_yield": None,
            "dividend_year": None,
            "financial_period": None,
            "data_available": False,
            "message": "主要分析失敗",
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
