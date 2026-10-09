import datetime
import json
import logging
from pathlib import Path

import pandas as pd
from FinMind.data import DataLoader


# =========================================================
# 基本設定
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "config.json"
OUTPUT_FILE = BASE_DIR / "analysis.json"
LOG_FILE = BASE_DIR / "stock_analysis.log"


# =========================================================
# Logging
# =========================================================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

logger = logging.getLogger(__name__)


# =========================================================
# 讀取設定
# =========================================================

def load_config():

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"找不到設定檔：{CONFIG_FILE}"
        )

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# 安全轉換數字
# =========================================================

def safe_float(value, default=0):

    try:
        if pd.isna(value):
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


# =========================================================
# 基本面分析
# =========================================================

def analyze_revenue(dl, stock_id, settings):

    result = {
        "score": 0,
        "latest_yoy": None,
        "trend": "資料不足",
        "latest_revenue": None,
        "message": "資料不足"
    }

    try:

        today = datetime.date.today()

        start_date = (
            today - datetime.timedelta(days=210)
        ).strftime("%Y-%m-%d")

        df = dl.taiwan_stock_month_revenue(
            stock_id=stock_id,
            start_date=start_date
        )

        if df is None or df.empty:
            result["message"] = "無營收資料"
            return result

        df = df.sort_values("date").reset_index(drop=True)

        months_required = settings.get(
            "revenue_months",
            3
        )

        if len(df) < months_required:
            result["message"] = "營收資料不足"
            return result

        # -------------------------------------------------
        # 最新資料
        # -------------------------------------------------

        latest = df.iloc[-1]

        latest_revenue = safe_float(
            latest.get("revenue")
        )

        latest_yoy = safe_float(
            latest.get("revenue_year_growth_rate")
        )

        result["latest_revenue"] = latest_revenue
        result["latest_yoy"] = latest_yoy

        # -------------------------------------------------
        # 最近三個月營收
        # -------------------------------------------------

        recent = df.tail(months_required)

        revenues = [
            safe_float(x)
            for x in recent["revenue"].tolist()
        ]

        # -------------------------------------------------
        # 判斷是否連續增加
        # -------------------------------------------------

        increasing = True

        for i in range(1, len(revenues)):

            if revenues[i] <= revenues[i - 1]:
                increasing = False
                break

        # -------------------------------------------------
        # 計算基本面分數
        # -------------------------------------------------

        score = 0

        target_yoy = settings.get(
            "revenue_yoy_target",
            20
        )

        # YoY 評分
        if latest_yoy >= 30:
            score += 25

        elif latest_yoy >= target_yoy:
            score += 20

        elif latest_yoy >= 10:
            score += 15

        elif latest_yoy >= 0:
            score += 8

        # 趨勢評分
        if increasing:
            score += 15

            result["trend"] = (
                f"連續 {months_required} 個月增加"
            )

        else:
            result["trend"] = "未連續增加"

        result["score"] = min(score, 40)

        # -------------------------------------------------
        # 訊息
        # -------------------------------------------------

        if latest_yoy >= target_yoy and increasing:

            result["message"] = "營收成長強勢"

        elif latest_yoy >= 0:

            result["message"] = "營收溫和成長"

        else:

            result["message"] = "營收衰退"

        return result

    except Exception as e:

        logger.exception(
            f"{stock_id} 營收分析錯誤"
        )

        result["message"] = "資料錯誤"

        return result


# =========================================================
# 大戶籌碼分析
# =========================================================

def analyze_big_holder(dl, stock_id, settings):

    result = {
        "score": 0,
        "trend": "資料不足",
        "latest_percent": None,
        "message": "資料不足"
    }

    try:

        today = datetime.date.today()

        start_date = (
            today - datetime.timedelta(days=90)
        ).strftime("%Y-%m-%d")

        df = dl.taiwan_stock_holding_shares_per(
            stock_id=stock_id,
            start_date=start_date
        )

        if df is None or df.empty:

            result["message"] = "無大戶資料"

            return result

        # -------------------------------------------------
        # 篩選 HoldingSharesLevel
        # -------------------------------------------------

        df = df[
            df["HoldingSharesLevel"] == "17"
        ].copy()

        if df.empty:

            result["message"] = "無符合級距資料"

            return result

        df = (
            df
            .sort_values("date")
            .reset_index(drop=True)
        )

        periods = settings.get(
            "big_holder_periods",
            4
        )

        if len(df) < periods:

            result["message"] = "大戶資料不足"

            return result

        recent = df.tail(periods)

        percentages = [
            safe_float(x)
            for x in recent["percent"].tolist()
        ]

        result["latest_percent"] = percentages[-1]

        # -------------------------------------------------
        # 判斷趨勢
        # -------------------------------------------------

        increasing_count = 0

        for i in range(1, len(percentages)):

            if percentages[i] > percentages[i - 1]:

                increasing_count += 1

        # -------------------------------------------------
        # 評分
        # -------------------------------------------------

        if increasing_count >= 3:

            result["score"] = 20

            result["trend"] = (
                f"連續 {increasing_count} 期增加"
            )

            result["message"] = "大戶持股明顯增加"

        elif increasing_count >= 2:

            result["score"] = 15

            result["trend"] = "大戶持股增加"

            result["message"] = "大戶偏多"

        elif increasing_count == 1:

            result["score"] = 10

            result["trend"] = "近期增加"

            result["message"] = "大戶持股小幅增加"

        else:

            result["score"] = 0

            result["trend"] = "未增加"

            result["message"] = "大戶持股未增加"

        return result

    except Exception:

        logger.exception(
            f"{stock_id} 大戶分析錯誤"
        )

        result["message"] = "資料錯誤"

        return result


# =========================================================
# 綜合評分
# =========================================================

def calculate_score(revenue, big_holder):

    # -----------------------------------------------------
    # 第一階段：
    #
    # 營收最高 40 分
    # 大戶最高 20 分
    #
    # 目前總分最高 60
    #
    # 後續加入 EPS、ROE、法人後
    # 再正式轉換成 100 分
    # -----------------------------------------------------

    raw_score = (
        revenue["score"]
        +
        big_holder["score"]
    )

    # 暫時轉換成 100 分
    score = round(
        raw_score / 60 * 100,
        1
    )

    return score


# =========================================================
# 判斷強弱
# =========================================================

def get_status(score):

    if score >= 80:
        return "🟢 強勢"

    elif score >= 65:
        return "🟡 偏多"

    elif score >= 50:
        return "⚪ 中性"

    elif score >= 30:
        return "🟠 偏弱"

    else:
        return "🔴 弱勢"


# =========================================================
# 分析單一股票
# =========================================================

def analyze_stock(dl, stock_id, settings):

    logger.info(
        f"開始分析 {stock_id}"
    )

    revenue = analyze_revenue(
        dl,
        stock_id,
        settings
    )

    big_holder = analyze_big_holder(
        dl,
        stock_id,
        settings
    )

    score = calculate_score(
        revenue,
        big_holder
    )

    status = get_status(score)

    return {

        "stock_id": stock_id,

        "analysis_date":
            datetime.date.today().isoformat(),

        "revenue": revenue,

        "big_holder": big_holder,

        "score": score,

        "status": status

    }


# =========================================================
# 主程式
# =========================================================

def analyze_stocks():

    logger.info("========== 開始執行台股分析 ==========")

    config = load_config()

    stock_list = config.get(
        "stocks",
        []
    )

    settings = config.get(
        "settings",
        {}
    )

    if not stock_list:

        raise ValueError(
            "config.json 沒有設定股票清單"
        )

    logger.info(
        f"股票數量：{len(stock_list)}"
    )

    # -----------------------------------------------------
    # 建立 FinMind
    # -----------------------------------------------------

    dl = DataLoader()

    results = []

    # -----------------------------------------------------
    # 逐支分析
    # -----------------------------------------------------

    for stock_id in stock_list:

        try:

            result = analyze_stock(
                dl,
                stock_id,
                settings
            )

            results.append(result)

            logger.info(
                f"{stock_id} 分析完成，"
                f"分數：{result['score']}"
            )

        except Exception:

            logger.exception(
                f"{stock_id} 分析失敗"
            )

            results.append({

                "stock_id": stock_id,

                "analysis_date":
                    datetime.date.today().isoformat(),

                "revenue": {
                    "score": 0,
                    "message": "分析失敗"
                },

                "big_holder": {
                    "score": 0,
                    "message": "分析失敗"
                },

                "score": 0,

                "status": "⚠️ 分析失敗"

            })

    # -----------------------------------------------------
    # 排序
    # -----------------------------------------------------

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # -----------------------------------------------------
    # 最終 JSON
    # -----------------------------------------------------

    output = {

        "update_time":
            datetime.datetime.now().isoformat(),

        "stock_count":
            len(results),

        "stocks":
            results

    }

    # -----------------------------------------------------
    # 寫入 analysis.json
    # -----------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    logger.info(
        f"分析完成，輸出：{OUTPUT_FILE}"
    )

    logger.info(
        "========== 分析結束 =========="
    )


# =========================================================
# 程式入口
# =========================================================

if __name__ == "__main__":

    analyze_stocks()
