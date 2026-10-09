import os
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from FinMind.data import DataLoader


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
OUTPUT_FILE = BASE_DIR / "analysis.json"
LOG_FILE = BASE_DIR / "stock_analysis.log"

TZ = ZoneInfo("Asia/Taipei")
TODAY = datetime.now(TZ).date()

DEFAULT_STOCKS = ["2330", "2454", "2317", "2603"]

DEFAULT_SETTINGS = {
    "revenue_yoy_target": 20,
    "revenue_months": 3,
    "big_holder_periods": 4,
}

# 外資評分規則：方案 A，維持原規則
FOREIGN_SCORE_CONTINUOUS_UP = 20
FOREIGN_SCORE_OVERALL_UP = 15
FOREIGN_SCORE_FLAT = 8
FOREIGN_SCORE_OVERALL_DOWN = 0

# 綜合分數：營收最高 40 分、外資最高 20 分
MAX_REVENUE_SCORE = 40
MAX_FOREIGN_SCORE = 20
MAX_TOTAL_SCORE = MAX_REVENUE_SCORE + MAX_FOREIGN_SCORE


# ============================================================
# 2. 日誌設定
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


# ============================================================
# 3. 通用工具
# ============================================================

def load_config():
    """讀取設定檔，若不存在則使用預設設定。"""

    if not CONFIG_FILE.exists():
        logger.warning("找不到 config.json，使用預設設定。")
        return {
            "stocks": DEFAULT_STOCKS,
            "settings": DEFAULT_SETTINGS,
        }

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

        stocks = config.get("stocks", DEFAULT_STOCKS)
        settings = config.get("settings", {})

        if not isinstance(stocks, list) or not stocks:
            stocks = DEFAULT_STOCKS

        merged_settings = DEFAULT_SETTINGS.copy()
        merged_settings.update(settings)

        return {
            "stocks": [str(s).strip() for s in stocks],
            "settings": merged_settings,
        }

    except Exception:
        logger.exception("讀取 config.json 失敗，改用預設設定。")
        return {
            "stocks": DEFAULT_STOCKS,
            "settings": DEFAULT_SETTINGS,
        }


def to_float(value):
    """安全轉換數值；缺失或無效資料回傳 None。"""

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None

        result = float(value)

        if not pd.notna(result):
            return None

        return result

    except (TypeError, ValueError):
        return None


def json_safe(value):
    """將資料轉為 JSON 可序列化型態。"""

    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [json_safe(v) for v in value]

    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass

    if value is None:
        return None

    if isinstance(value, float):
        if not pd.notna(value):
            return None

    return value


def create_empty_revenue(message="資料不足"):
    return {
        "score": None,
        "latest_yoy": None,
        "trend": "資料不足",
        "latest_revenue": None,
        "latest_revenue_month": None,
        "message": message,
        "data_available": False,
    }


def create_empty_foreign(message="資料不足"):
    return {
        "score": None,
        "trend": "資料不足",
        "latest_percent": None,
        "change_periods": None,
        "latest_date": None,
        "message": message,
        "data_available": False,
    }


# ============================================================
# 4. 初始化 FinMind
# ============================================================

def create_data_loader():
    """
    若 GitHub Secrets 有設定 FINMIND_TOKEN，
    則使用 Token 登入；沒有則使用 DataLoader 預設方式。
    """

    dl = DataLoader()

    token = os.getenv("FINMIND_TOKEN", "").strip()

    if token:
        dl.login_by_token(api_token=token)
        logger.info("FinMind 已設定 Token。")
    else:
        logger.info("未設定 FINMIND_TOKEN，使用預設 API 存取方式。")

    return dl


# ============================================================
# 5. 營收資料整理
# ============================================================

def prepare_revenue_data(df):
    """依營收實際年度與月份建立月份索引。"""

    if df is None or df.empty:
        return pd.DataFrame()

    required = {"revenue"}

    if not required.issubset(df.columns):
        logger.error(
            "月營收資料缺少必要欄位，實際欄位：%s",
            list(df.columns),
        )
        return pd.DataFrame()

    data = df.copy()

    if {"revenue_year", "revenue_month"}.issubset(data.columns):
        year = pd.to_numeric(
            data["revenue_year"], errors="coerce"
        )
        month = pd.to_numeric(
            data["revenue_month"], errors="coerce"
        )

        data["period"] = pd.to_datetime(
            {
                "year": year,
                "month": month,
                "day": 1,
            },
            errors="coerce",
        )

    elif "date" in data.columns:
        data["period"] = (
            pd.to_datetime(data["date"], errors="coerce")
            .dt.to_period("M")
            .dt.to_timestamp()
        )

    else:
        logger.error("月營收資料沒有可用的日期欄位。")
        return pd.DataFrame()

    data["revenue"] = pd.to_numeric(
        data["revenue"], errors="coerce"
    )

    data = data.dropna(subset=["period", "revenue"])

    # 不採用未來月份的營收
    current_month = pd.Timestamp(TODAY).to_period("M")
    data = data[
        data["period"].dt.to_period("M") <= current_month
    ]

    # 每個營收月份只保留一筆
    data = (
        data.sort_values("period")
        .drop_duplicates(subset=["period"], keep="last")
        .reset_index(drop=True)
    )

    return data


# ============================================================
# 6. 營收評分
# ============================================================

def score_revenue_yoy(yoy, target):
    """
    營收年增率評分，最高 25 分。

    >= 目標值：25 分
    >= 10%：20 分
    >= 0%：15 分
    >= -10%：8 分
    < -10%：0 分
    """

    if yoy is None:
        return None

    if yoy >= target:
        return 25
    if yoy >= 10:
        return 20
    if yoy >= 0:
        return 15
    if yoy >= -10:
        return 8

    return 0


def analyze_revenue(dl, stock_id, settings):
    """分析個股月營收、年增率及最近月份趨勢。"""

    logger.info("[%s] 開始分析月營收。", stock_id)

    result = create_empty_revenue()

    try:
        start_date = (
            TODAY - timedelta(days=500)
        ).isoformat()

        df = dl.taiwan_stock_month_revenue(
            stock_id=stock_id,
            start_date=start_date,
            end_date=TODAY.isoformat(),
        )

        data = prepare_revenue_data(df)

        if data.empty:
            result["message"] = "月營收資料為空或欄位無效"
            logger.warning("[%s] %s", stock_id, result["message"])
            return result

        latest = data.iloc[-1]
        latest_period = latest["period"]
        latest_revenue = to_float(latest["revenue"])

        latest_month = latest_period.strftime("%Y-%m")

        # 尋找去年同月份營收
        previous_year_period = (
            latest_period - pd.DateOffset(years=1)
        )

        previous_rows = data[
            data["period"] == previous_year_period
        ]

        latest_yoy = None

        if not previous_rows.empty:
            previous_revenue = to_float(
                previous_rows.iloc[-1]["revenue"]
            )

            if (
                previous_revenue is not None
                and previous_revenue != 0
                and latest_revenue is not None
            ):
                latest_yoy = (
                    (latest_revenue - previous_revenue)
                    / abs(previous_revenue)
                    * 100
                )

        # 取最近指定月份，檢查是否為連續月份
        periods_required = max(
            2,
            int(settings.get("revenue_months", 3)),
        )

        recent = data.tail(periods_required).copy()

        trend = "資料不足"
        trend_score = None

        if len(recent) >= periods_required:
            period_list = recent["period"].tolist()
            revenue_list = recent["revenue"].tolist()

            consecutive_months = all(
                period_list[i].to_period("M")
                - period_list[i - 1].to_period("M")
                == 1
                for i in range(1, len(period_list))
            )

            if consecutive_months:
                increasing = all(
                    revenue_list[i] > revenue_list[i - 1]
                    for i in range(1, len(revenue_list))
                )

                if increasing:
                    trend = "連續增加"
                    trend_score = 15
                else:
                    trend = "未連續增加"
                    trend_score = 0

        yoy_target = float(
            settings.get("revenue_yoy_target", 20)
        )

        yoy_score = score_revenue_yoy(
            latest_yoy,
            yoy_target,
        )

        # 缺少年增率或趨勢所需資料時，不計算營收總分
        if yoy_score is None or trend_score is None:
            result.update({
                "latest_yoy": (
                    round(latest_yoy, 4)
                    if latest_yoy is not None
                    else None
                ),
                "trend": trend,
                "latest_revenue": latest_revenue,
                "latest_revenue_month": latest_month,
                "score": None,
                "data_available": False,
                "message": "營收必要資料不足，未計算營收分數",
            })

            logger.warning(
                "[%s] 營收資料不足：yoy_score=%s, trend_score=%s",
                stock_id,
                yoy_score,
                trend_score,
            )

            return result

        total_revenue_score = yoy_score + trend_score

        if latest_yoy >= yoy_target and trend == "連續增加":
            message = "年增率達標且營收連續增加"
        elif latest_yoy >= yoy_target:
            message = "營收年增率達標"
        elif trend == "連續增加":
            message = "營收連續增加"
        else:
            message = "營收尚未同時達成年增率及連續成長條件"

        result.update({
            "score": int(total_revenue_score),
            "latest_yoy": round(latest_yoy, 4),
            "trend": trend,
            "latest_revenue": latest_revenue,
            "latest_revenue_month": latest_month,
            "message": message,
            "data_available": True,
        })

        logger.info(
            "[%s] 營收分析完成：score=%s, yoy=%s, trend=%s",
            stock_id,
            result["score"],
            result["latest_yoy"],
            result["trend"],
        )

        return result

    except Exception as exc:
        logger.exception(
            "[%s] 月營收分析失敗：%s",
            stock_id,
            exc,
        )
        result["message"] = "月營收 API 或分析發生錯誤"
        return result


# ============================================================
# 7. 外資持股資料整理
# ============================================================

def prepare_foreign_data(df):
    """整理外資持股比例資料，並依日期排序。"""

    if df is None or df.empty:
        return pd.DataFrame()

    if "date" not in df.columns:
        logger.error(
            "外資資料缺少 date 欄位，實際欄位：%s",
            list(df.columns),
        )
        return pd.DataFrame()

    ratio_column = "ForeignInvestmentSharesRatio"

    if ratio_column not in df.columns:
        logger.error(
            "外資資料缺少 %s 欄位，實際欄位：%s",
            ratio_column,
            list(df.columns),
        )
        return pd.DataFrame()

    data = df.copy()

    data["date"] = pd.to_datetime(
        data["date"], errors="coerce"
    )

    data[ratio_column] = pd.to_numeric(
        data[ratio_column], errors="coerce"
    )

    data = data.dropna(
        subset=["date", ratio_column]
    )

    # 不採用未來日期
    data = data[
        data["date"].dt.date <= TODAY
    ]

    data = (
        data.sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )

    return data


# ============================================================
# 8. 外資持股評分：方案 A
# ============================================================

def analyze_foreign_holding(dl, stock_id, settings):
    """
    外資評分規則維持方案 A：

    最近 N 期每一期都增加：20 分
    最近 N 期整體增加：15 分
    最近 N 期整體持平：8 分
    最近 N 期整體減少：0 分

    N 預設為 4 期。

    change_periods = 最新一期比例 - N 期前比例。
    單位為「百分點」，不是相對百分比。
    """

    logger.info("[%s] 開始分析外資持股。", stock_id)

    result = create_empty_foreign()

    try:
        start_date = (
            TODAY - timedelta(days=180)
        ).isoformat()

        df = dl.taiwan_stock_shareholding(
            stock_id=stock_id,
            start_date=start_date,
            end_date=TODAY.isoformat(),
        )

        data = prepare_foreign_data(df)

        if data.empty:
            result["message"] = "外資持股資料為空或欄位無效"
            logger.warning("[%s] %s", stock_id, result["message"])
            return result

        periods_required = max(
            2,
            int(settings.get("big_holder_periods", 4)),
        )

        recent = data.tail(periods_required).copy()

        if len(recent) < periods_required:
            result["message"] = (
                f"外資持股有效資料不足，需要 {periods_required} 期，"
                f"目前只有 {len(recent)} 期"
            )

            logger.warning(
                "[%s] %s",
                stock_id,
                result["message"],
            )

            return result

        ratio_column = "ForeignInvestmentSharesRatio"

        ratios = [
            float(value)
            for value in recent[ratio_column].tolist()
        ]

        dates = recent["date"].tolist()

        if not all(pd.notna(value) for value in ratios):
            result["message"] = "外資持股比例包含無效數值"
            return result

        # 比例均以百分比數值表示，例如 25.69 代表 25.69%
        # 四捨五入到小數點後 6 位，消除浮點表示誤差。
        ratios = [round(value, 6) for value in ratios]

        latest_ratio = ratios[-1]
        first_ratio = ratios[0]

        change = round(latest_ratio - first_ratio, 6)

        consecutive_increase = all(
            ratios[i] > ratios[i - 1]
            for i in range(1, len(ratios))
        )

        # 方案 A：不加入額外變化門檻
        if consecutive_increase:
            foreign_score = FOREIGN_SCORE_CONTINUOUS_UP
            trend = "連續增加"
            message = f"最近 {periods_required} 期外資持股比例連續增加"

        elif change > 0:
            foreign_score = FOREIGN_SCORE_OVERALL_UP
            trend = "整體增加"
            message = f"最近 {periods_required} 期外資持股比例整體增加"

        elif change == 0:
            foreign_score = FOREIGN_SCORE_FLAT
            trend = "持平"
            message = f"最近 {periods_required} 期外資持股比例整體持平"

        else:
            foreign_score = FOREIGN_SCORE_OVERALL_DOWN
            trend = "整體減少"
            message = f"最近 {periods_required} 期外資持股比例整體減少"

        result.update({
            "score": int(foreign_score),
            "trend": trend,
            "latest_percent": round(latest_ratio, 4),
            "change_periods": change,
            "latest_date": dates[-1].strftime("%Y-%m-%d"),
            "message": message,
            "data_available": True,
        })

        logger.info(
            "[%s] 外資分析完成：score=%s, latest_percent=%s, "
            "change_periods=%s, trend=%s, dates=%s",
            stock_id,
            result["score"],
            result["latest_percent"],
            result["change_periods"],
            result["trend"],
            [d.strftime("%Y-%m-%d") for d in dates],
        )

        return result

    except Exception:
        logger.exception("[%s] 外資持股分析失敗。", stock_id)
        result["message"] = "外資持股 API 或分析發生錯誤"
        return result


# ============================================================
# 9. 綜合評分與狀態
# ============================================================

def calculate_overall_score(revenue, foreign_holding):
    """
    營收分數最高 40 分，外資分數最高 20 分。
    任一必要指標缺失時，綜合分數回傳 None。
    """

    revenue_score = revenue.get("score")
    foreign_score = foreign_holding.get("score")

    if (
        not revenue.get("data_available", False)
        or not foreign_holding.get("data_available", False)
        or revenue_score is None
        or foreign_score is None
    ):
        return None

    total = float(revenue_score) + float(foreign_score)

    # 換算為百分制
    normalized = total / MAX_TOTAL_SCORE * 100

    return round(normalized, 1)


def get_status(score):
    """依百分制綜合分數回傳狀態。"""

    if score is None:
        return "⚪ 資料不足"

    if score >= 80:
        return "🟢 強勢"

    if score >= 60:
        return "🟡 偏多"

    if score >= 40:
        return "🟠 中性"

    return "🔴 弱勢"


# ============================================================
# 10. 單檔股票分析
# ============================================================

def analyze_stock(dl, stock_id, settings):
    logger.info("=" * 60)
    logger.info("開始分析股票：%s", stock_id)

    revenue = analyze_revenue(
        dl,
        stock_id,
        settings,
    )

    foreign_holding = analyze_foreign_holding(
        dl,
        stock_id,
        settings,
    )

    overall_score = calculate_overall_score(
        revenue,
        foreign_holding,
    )

    missing_items = []

    if not revenue.get("data_available", False):
        missing_items.append("revenue")

    if not foreign_holding.get("data_available", False):
        missing_items.append("foreign_holding")

    data_complete = len(missing_items) == 0

    result = {
        "stock_id": str(stock_id),
        "analysis_date": TODAY.isoformat(),
        "revenue": revenue,
        "foreign_holding": foreign_holding,
        "score": overall_score,
        "status": get_status(overall_score),
        "data_quality": {
            "complete": data_complete,
            "missing_items": missing_items,
        },
    }

    logger.info(
        "[%s] 分析完成：score=%s, status=%s, data_quality=%s",
        stock_id,
        overall_score,
        result["status"],
        result["data_quality"],
    )

    return result


# ============================================================
# 11. 執行全部股票並輸出 JSON
# ============================================================

def analyze_stocks():
    config = load_config()
    stocks = config["stocks"]
    settings = config["settings"]

    logger.info("台股分析開始，日期：%s", TODAY.isoformat())
    logger.info("股票清單：%s", stocks)
    logger.info("分析設定：%s", settings)

    try:
        dl = create_data_loader()
    except Exception:
        logger.exception("初始化 FinMind 失敗。")
        raise

    results = []

    for stock_id in stocks:
        try:
            result = analyze_stock(
                dl,
                stock_id,
                settings,
            )
            results.append(result)

        except Exception:
            logger.exception(
                "[%s] 股票分析發生未預期錯誤。",
                stock_id,
            )

            results.append({
                "stock_id": str(stock_id),
                "analysis_date": TODAY.isoformat(),
                "revenue": create_empty_revenue(
                    "股票分析發生未預期錯誤"
                ),
                "foreign_holding": create_empty_foreign(
                    "股票分析發生未預期錯誤"
                ),
                "score": None,
                "status": "⚪ 資料不足",
                "data_quality": {
                    "complete": False,
                    "missing_items": [
                        "revenue",
                        "foreign_holding",
                    ],
                },
            })

    complete_count = sum(
        1
        for item in results
        if item["data_quality"]["complete"]
    )

    output = {
        "update_time": datetime.now(TZ).isoformat(
            timespec="seconds"
        ),
        "stock_count": len(results),
        "complete_count": complete_count,
        "stocks": results,
    }

    output = json_safe(output)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )

    logger.info("分析完成。")
    logger.info("總股票數：%s", len(results))
    logger.info("資料完整股票數：%s", complete_count)
    logger.info("輸出檔案：%s", OUTPUT_FILE)

    for item in results:
        foreign = item["foreign_holding"]

        logger.info(
            "摘要 stock_id=%s score=%s foreign_score=%s "
            "foreign_change=%s foreign_trend=%s complete=%s",
            item["stock_id"],
            item["score"],
            foreign["score"],
            foreign["change_periods"],
            foreign["trend"],
            item["data_quality"]["complete"],
        )

    return output


if __name__ == "__main__":
    analyze_stocks()
