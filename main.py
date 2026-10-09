
import datetime
import json
import logging
import math
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

DEFAULT_STOCKS = ["2330", "2454", "2317", "2603"]

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def setup_logging():
    """同時將執行訊息寫入檔案及 GitHub Actions 日誌。"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        )

        file_handler = logging.FileHandler(
            LOG_FILE, encoding="utf-8"
        )
        console_handler = logging.StreamHandler()

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)


def load_config():
    """讀取設定；若設定檔不存在，使用預設股票清單。"""
    if not CONFIG_FILE.exists():
        logging.warning("找不到 config.json，使用預設設定。")
        return {
            "stocks": DEFAULT_STOCKS,
            "settings": {}
        }

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            config = json.load(file)

        if not isinstance(config, dict):
            raise ValueError("config.json 最外層必須是 JSON 物件。")

        stocks = config.get("stocks", DEFAULT_STOCKS)
        if not isinstance(stocks, list) or not stocks:
            raise ValueError("config.json 的 stocks 必須是非空陣列。")

        config["stocks"] = [
            str(stock).strip() for stock in stocks
            if str(stock).strip()
        ]
        config.setdefault("settings", {})

        return config

    except Exception:
        logging.exception("讀取 config.json 失敗。")
        raise


def to_json_safe(value):
    """將 Pandas、日期及缺失值轉為合法 JSON 值。"""
    if isinstance(value, dict):
        return {
            str(key): to_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]

    if value is None:
        return None

    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass

    if isinstance(value, float) and not math.isfinite(value):
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def number_or_none(value):
    """安全轉換數字；空值不會被轉成 0。"""
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


# ============================================================
# 2. 基本面：月營收及年增率
# ============================================================

def prepare_revenue_data(df):
    """
    整理月營收資料。
    優先使用 revenue_year / revenue_month，
    欄位不存在時才從 date 推導年月。
    """
    required = {"date", "revenue"}

    if df is None or df.empty:
        return pd.DataFrame()

    if not required.issubset(df.columns):
        logging.error(
            "月營收欄位不完整，實際欄位：%s",
            list(df.columns)
        )
        return pd.DataFrame()

    data = df.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["revenue"] = pd.to_numeric(
        data["revenue"], errors="coerce"
    )

    date_year = data["date"].dt.year
    date_month = data["date"].dt.month

    if "revenue_year" in data.columns:
        year_values = pd.to_numeric(
            data["revenue_year"], errors="coerce"
        )
        data["period_year"] = year_values.where(
            year_values.notna(), date_year
        )
    else:
        data["period_year"] = date_year

    if "revenue_month" in data.columns:
        month_values = pd.to_numeric(
            data["revenue_month"], errors="coerce"
        )
        data["period_month"] = month_values.where(
            month_values.notna(), date_month
        )
    else:
        data["period_month"] = date_month

    data = data.dropna(
        subset=["date", "revenue", "period_year", "period_month"]
    )

    data["period_year"] = data["period_year"].astype(int)
    data["period_month"] = data["period_month"].astype(int)

    data = data[
        data["period_month"].between(1, 12)
    ].copy()

    # 同一營收月份若有重複紀錄，保留日期較新的紀錄。
    data = data.sort_values("date")
    data = data.drop_duplicates(
        subset=["period_year", "period_month"],
        keep="last"
    )

    return data.sort_values(
        ["period_year", "period_month"]
    ).reset_index(drop=True)


def analyze_revenue(dl, stock_id, settings, today):
    """計算最新月營收、去年同期年增率及連續增長狀況。"""
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
        # 抓取約 500 天，讓去年同期營收有較高機會可供比較。
        start_date = (
            today - datetime.timedelta(days=500)
        ).strftime("%Y-%m-%d")

        df = dl.taiwan_stock_month_revenue(
            stock_id=stock_id,
            start_date=start_date
        )

        data = prepare_revenue_data(df)

        if data.empty:
            result["message"] = "沒有可用的月營收資料"
            logging.warning(
                "%s 月營收資料為空或欄位不符。",
                stock_id
            )
            return result

        latest = data.iloc[-1]

        latest_year = int(latest["period_year"])
        latest_month = int(latest["period_month"])
        latest_revenue = float(latest["revenue"])

        result["latest_revenue"] = latest_revenue
        result["latest_revenue_month"] = (
            f"{latest_year:04d}-{latest_month:02d}"
        )

        # 找去年同一營收月份，而不是直接讀取不存在的欄位。
        previous = data[
            (data["period_year"] == latest_year - 1)
            & (data["period_month"] == latest_month)
        ]

        latest_yoy = None

        if not previous.empty:
            previous_revenue = float(
                previous.iloc[-1]["revenue"]
            )

            if previous_revenue != 0:
                latest_yoy = (
                    latest_revenue / previous_revenue - 1
                ) * 100

        result["latest_yoy"] = latest_yoy

        # 使用最近三個不同營收月份判斷是否連續增加。
        required_months = int(
            settings.get("revenue_months", 3)
        )
        recent = data.tail(required_months)

        trend_available = len(recent) >= required_months
        trend_up = False

        if trend_available:
            revenues = recent["revenue"].tolist()
            trend_up = all(
                revenues[index] > revenues[index - 1]
                for index in range(1, len(revenues))
            )
            result["trend"] = (
                "連續增加" if trend_up else "未連續增加"
            )

        # 缺去年同期資料，或缺足夠月份時，不產生基本面分數。
        if latest_yoy is None:
            result["message"] = "缺少去年同期營收，無法計算年增率"
            logging.warning(
                "%s 找不到去年同期營收，年增率設為 null。",
                stock_id
            )
            return result

        if not trend_available:
            result["message"] = "營收月份不足，無法判斷趨勢"
            logging.warning(
                "%s 月營收不足 %s 期。",
                stock_id, required_months
            )
            return result

        target = float(
            settings.get("revenue_yoy_target", 20)
        )

        # 年增率分數最高 25 分。
        if latest_yoy >= 30:
            yoy_score = 25
        elif latest_yoy >= target:
            yoy_score = 20
        elif latest_yoy >= 10:
            yoy_score = 15
        elif latest_yoy >= 0:
            yoy_score = 8
        else:
            yoy_score = 0

        # 三期營收連續增加，加 15 分。
        trend_score = 15 if trend_up else 0

        result["score"] = yoy_score + trend_score
        result["data_available"] = True

        if latest_yoy >= target and trend_up:
            result["message"] = "年增率達標且營收連續增加"
        elif latest_yoy >= 0:
            result["message"] = "營收年增率為正"
        else:
            result["message"] = "營收年增率為負"

        logging.info(
            "%s 營收：最新月份=%s，年增率=%.2f%%，趨勢=%s",
            stock_id,
            result["latest_revenue_month"],
            latest_yoy,
            result["trend"]
        )

        return result

    except Exception as exc:
        result["message"] = "營收資料取得失敗"
        result["error"] = str(exc)
        logging.exception("%s 分析月營收時發生錯誤。", stock_id)
        return result


# ============================================================
# 3. 籌碼面：外資持股比例
# ============================================================

def analyze_foreign_holding(dl, stock_id, settings, today):
    """
    使用 TaiwanStockShareholding 的
    ForeignInvestmentSharesRatio 外資持股比例。

    比較最近數期的持股比例變化，不使用股東持股分級。
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
        periods = int(settings.get("foreign_periods", 4))
        periods = max(periods, 2)

        start_date = (
            today - datetime.timedelta(days=180)
        ).strftime("%Y-%m-%d")

        df = dl.taiwan_stock_shareholding(
            stock_id=stock_id,
            start_date=start_date
        )

        if df is None or df.empty:
            result["message"] = "沒有外資持股資料"
            logging.warning(
                "%s 外資持股資料為空。",
                stock_id
            )
            return result

        if "date" not in df.columns:
            result["message"] = "外資持股資料缺少 date 欄位"
            logging.error(
                "%s 外資持股欄位：%s",
                stock_id, list(df.columns)
            )
            return result

        ratio_column = "ForeignInvestmentSharesRatio"

        if ratio_column not in df.columns:
            result["message"] = (
                f"外資持股資料缺少 {ratio_column} 欄位"
            )
            logging.error(
                "%s 外資持股欄位不符，實際欄位：%s",
                stock_id, list(df.columns)
            )
            return result

        data = df[["date", ratio_column]].copy()
        data["date"] = pd.to_datetime(
            data["date"], errors="coerce"
        )
        data["ratio"] = pd.to_numeric(
            data[ratio_column], errors="coerce"
        )

        data = data.dropna(subset=["date", "ratio"])
        data = data.sort_values("date")
        data = data.drop_duplicates(
            subset=["date"], keep="last"
        ).reset_index(drop=True)

        if len(data) < periods:
            result["message"] = (
                f"外資持股資料不足，需要至少 {periods} 期，"
                f"目前只有 {len(data)} 期"
            )
            logging.warning(
                "%s 外資持股資料不足：%s/%s 期。",
                stock_id, len(data), periods
            )
            return result

        recent = data.tail(periods).reset_index(drop=True)
        ratios = recent["ratio"].astype(float).tolist()

        latest_percent = ratios[-1]
        change = latest_percent - ratios[0]

        result["latest_percent"] = latest_percent
        result["change_periods"] = change
        result["latest_date"] = (
            recent.iloc[-1]["date"].strftime("%Y-%m-%d")
        )

        # 逐期比較持股比例；只有所有相鄰期間都增加，
        # 才判定為連續增加。
        differences = [
            ratios[index] - ratios[index - 1]
            for index in range(1, len(ratios))
        ]

        all_increasing = all(value > 0 for value in differences)

        if all_increasing:
            result["trend"] = "連續增加"
            score = 20
            message = f"最近 {periods} 期外資持股比例連續增加"
        elif change > 0:
            result["trend"] = "整體增加"
            score = 15
            message = f"最近 {periods} 期外資持股比例整體增加"
        elif change == 0:
            result["trend"] = "大致持平"
            score = 8
            message = f"最近 {periods} 期外資持股比例持平"
        else:
            result["trend"] = "整體減少"
            score = 0
            message = f"最近 {periods} 期外資持股比例整體減少"

        result["score"] = score
        result["message"] = message
        result["data_available"] = True

        logging.info(
            "%s 外資持股：日期=%s，最新比例=%.4f，"
            "期間變化=%.4f，趨勢=%s",
            stock_id,
            result["latest_date"],
            latest_percent,
            change,
            result["trend"]
        )

        return result

    except Exception as exc:
        result["message"] = "外資持股資料取得失敗"
        result["error"] = str(exc)
        logging.exception(
            "%s 分析外資持股時發生錯誤。",
            stock_id
        )
        return result


# ============================================================
# 4. 評分及狀態
# ============================================================

def calculate_overall_score(revenue, foreign_holding):
    """
    基本面最高 40 分，外資持股最高 20 分。
    任一項缺失時，總分設為 None，避免缺資料被當成 0 分。
    """
    if not revenue.get("data_available"):
        return None

    if not foreign_holding.get("data_available"):
        return None

    revenue_score = number_or_none(revenue.get("score"))
    foreign_score = number_or_none(foreign_holding.get("score"))

    if revenue_score is None or foreign_score is None:
        return None

    raw_score = revenue_score + foreign_score
    return round(raw_score / 60 * 100, 1)


def get_status(score):
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
# 5. 分析單一股票
# ============================================================

def analyze_stock(dl, stock_id, settings, today):
    logging.info("開始分析股票 %s", stock_id)

    revenue = analyze_revenue(
        dl, stock_id, settings, today
    )

    foreign_holding = analyze_foreign_holding(
        dl, stock_id, settings, today
    )

    score = calculate_overall_score(
        revenue, foreign_holding
    )

    missing_items = []

    if not revenue.get("data_available"):
        missing_items.append("營收")

    if not foreign_holding.get("data_available"):
        missing_items.append("外資持股")

    result = {
        "stock_id": stock_id,
        "analysis_date": today.strftime("%Y-%m-%d"),
        "revenue": revenue,
        "foreign_holding": foreign_holding,
        "score": score,
        "status": get_status(score),
        "data_quality": {
            "complete": len(missing_items) == 0,
            "missing_items": missing_items
        }
    }

    logging.info(
        "完成分析 %s：score=%s，status=%s，缺失項目=%s",
        stock_id,
        score,
        result["status"],
        missing_items
    )

    return result


# ============================================================
# 6. 主程式：輸出 analysis.json
# ============================================================

def analyze_stocks():
    setup_logging()

    logging.info("=" * 60)
    logging.info("台股分析程式開始執行")

    config = load_config()
    stocks = config["stocks"]
    settings = config.get("settings", {})

    now = datetime.datetime.now(TAIPEI_TZ)
    today = now.date()

    results = []

    try:
        dl = DataLoader()
    except Exception:
        logging.exception("建立 FinMind DataLoader 失敗。")
        raise

    for stock_id in stocks:
        try:
            result = analyze_stock(
                dl, stock_id, settings, today
            )
            results.append(result)

        except Exception:
            logging.exception(
                "分析股票 %s 時發生未預期錯誤。",
                stock_id
            )

            results.append({
                "stock_id": stock_id,
                "analysis_date": today.strftime("%Y-%m-%d"),
                "revenue": {
                    "score": None,
                    "latest_yoy": None,
                    "trend": "資料不足",
                    "latest_revenue": None,
                    "message": "分析失敗",
                    "data_available": False
                },
                "foreign_holding": {
                    "score": None,
                    "trend": "資料不足",
                    "latest_percent": None,
                    "change_periods": None,
                    "message": "分析失敗",
                    "data_available": False
                },
                "score": None,
                "status": "⚪ 資料不足",
                "data_quality": {
                    "complete": False,
                    "missing_items": ["營收", "外資持股"]
                }
            })

    # 只有資料完整的股票才參與分數排序；
    # 資料不足的股票排在最後。
    results.sort(
        key=lambda item: (
            item["score"] is None,
            -(item["score"] or 0)
        )
    )

    complete_count = sum(
        1 for item in results
        if item.get("data_quality", {}).get("complete")
    )

    output = {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "stock_count": len(results),
        "complete_count": complete_count,
        "stocks": results
    }

    safe_output = to_json_safe(output)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            safe_output,
            file,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        )

    logging.info("分析股票數量：%s", len(results))
    logging.info("資料完整股票數量：%s", complete_count)
    logging.info("已輸出：%s", OUTPUT_FILE)
    logging.info("台股分析程式執行完成")
    logging.info("=" * 60)


if __name__ == "__main__":
    analyze_stocks()
