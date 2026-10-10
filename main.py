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

DEFAULT_STOCKS = [
    "2330",
    "2454",
    "2317",
    "2603"
]

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


# ============================================================
# 2. Logging
# ============================================================

def setup_logging():
    """同時將執行訊息寫入檔案及 GitHub Actions 日誌。"""

    logger = logging.getLogger()

    logger.setLevel(logging.INFO)

    if logger.handlers:
        return

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8"
    )

    console_handler = logging.StreamHandler()

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


# ============================================================
# 3. 股票代碼處理
# ============================================================

def normalize_stock_code(stock):
    """
    將 config.json 中的股票資料統一轉成股票代碼。

    支援：
        "2330"
        2330
        {"stock_id": "2330"}
        {"stock_code": "2330"}
    """

    if stock is None:
        return None

    if isinstance(stock, dict):

        code = (
            stock.get("stock_id")
            or stock.get("stock_code")
            or stock.get("code")
        )

        if code is None:
            return None

        stock = code

    text = str(stock).strip()

    if not text:
        return None

    return text


# ============================================================
# 4. 讀取設定
# ============================================================

def load_config():
    """讀取 config.json。"""

    if not CONFIG_FILE.exists():

        logging.warning(
            "找不到 config.json，使用預設股票清單。"
        )

        return {
            "stocks": DEFAULT_STOCKS,
            "settings": {}
        }

    try:

        with CONFIG_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            config = json.load(file)

        if not isinstance(config, dict):

            raise ValueError(
                "config.json 最外層必須是 JSON 物件。"
            )

        raw_stocks = config.get(
            "stocks",
            DEFAULT_STOCKS
        )

        if not isinstance(
            raw_stocks,
            list
        ):

            raise ValueError(
                "config.json 的 stocks 必須是陣列。"
            )

        stocks = []

        for stock in raw_stocks:

            code = normalize_stock_code(
                stock
            )

            if code and code not in stocks:

                stocks.append(code)

        if not stocks:

            raise ValueError(
                "config.json 沒有有效的股票代碼。"
            )

        config["stocks"] = stocks

        if not isinstance(
            config.get("settings"),
            dict
        ):

            config["settings"] = {}

        return config

    except Exception:

        logging.exception(
            "讀取 config.json 失敗。"
        )

        raise


# ============================================================
# 5. JSON 安全處理
# ============================================================

def to_json_safe(value):
    """將 Pandas、日期及缺失值轉成合法 JSON。"""

    if isinstance(value, dict):

        return {
            str(key): to_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple)
    ):

        return [
            to_json_safe(item)
            for item in value
        ]

    if value is None:
        return None

    if isinstance(
        value,
        (
            datetime.date,
            datetime.datetime
        )
    ):

        return value.isoformat()

    if hasattr(value, "item"):

        try:
            value = value.item()

        except (
            ValueError,
            TypeError
        ):

            pass

    if isinstance(
        value,
        float
    ):

        if not math.isfinite(value):
            return None

    try:

        if pd.isna(value):
            return None

    except (
        TypeError,
        ValueError
    ):

        pass

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool
        )
    ):

        return value

    return str(value)


def number_or_none(value):
    """安全轉換數字。"""

    if value is None:
        return None

    try:

        if pd.isna(value):
            return None

        number = float(value)

        if not math.isfinite(number):
            return None

        return number

    except (
        TypeError,
        ValueError
    ):

        return None


# ============================================================
# 6. 基本面：整理月營收
# ============================================================

def prepare_revenue_data(df):

    required = {
        "date",
        "revenue"
    }

    if df is None or df.empty:
        return pd.DataFrame()

    if not required.issubset(
        df.columns
    ):

        logging.error(
            "月營收欄位不完整：%s",
            list(df.columns)
        )

        return pd.DataFrame()

    data = df.copy()

    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce"
    )

    data["revenue"] = pd.to_numeric(
        data["revenue"],
        errors="coerce"
    )

    date_year = data["date"].dt.year
    date_month = data["date"].dt.month

    if "revenue_year" in data.columns:

        year_values = pd.to_numeric(
            data["revenue_year"],
            errors="coerce"
        )

        data["period_year"] = (
            year_values.where(
                year_values.notna(),
                date_year
            )
        )

    else:

        data["period_year"] = date_year

    if "revenue_month" in data.columns:

        month_values = pd.to_numeric(
            data["revenue_month"],
            errors="coerce"
        )

        data["period_month"] = (
            month_values.where(
                month_values.notna(),
                date_month
            )
        )

    else:

        data["period_month"] = date_month

    data = data.dropna(
        subset=[
            "date",
            "revenue",
            "period_year",
            "period_month"
        ]
    )

    data["period_year"] = (
        data["period_year"].astype(int)
    )

    data["period_month"] = (
        data["period_month"].astype(int)
    )

    data = data[
        data["period_month"].between(
            1,
            12
        )
    ].copy()

    data = data.sort_values(
        "date"
    )

    data = data.drop_duplicates(
        subset=[
            "period_year",
            "period_month"
        ],
        keep="last"
    )

    return data.sort_values(
        [
            "period_year",
            "period_month"
        ]
    ).reset_index(drop=True)


# ============================================================
# 7. 基本面：月營收分析
# ============================================================

def analyze_revenue(
    dl,
    stock_id,
    settings,
    today
):

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

        start_date = (
            today -
            datetime.timedelta(days=500)
        ).strftime("%Y-%m-%d")

        df = dl.taiwan_stock_month_revenue(
            stock_id=stock_id,
            start_date=start_date
        )

        data = prepare_revenue_data(
            df
        )

        if data.empty:

            result["message"] = (
                "沒有可用的月營收資料"
            )

            logging.warning(
                "%s 月營收資料為空。",
                stock_id
            )

            return result

        latest = data.iloc[-1]

        latest_year = int(
            latest["period_year"]
        )

        latest_month = int(
            latest["period_month"]
        )

        latest_revenue = float(
            latest["revenue"]
        )

        result["latest_revenue"] = (
            latest_revenue
        )

        result["latest_revenue_month"] = (
            f"{latest_year:04d}-{latest_month:02d}"
        )

        previous = data[
            (data["period_year"] == latest_year - 1)
            &
            (data["period_month"] == latest_month)
        ]

        latest_yoy = None

        if not previous.empty:

            previous_revenue = float(
                previous.iloc[-1]["revenue"]
            )

            if previous_revenue != 0:

                latest_yoy = (
                    latest_revenue /
                    previous_revenue -
                    1
                ) * 100

        result["latest_yoy"] = (
            latest_yoy
        )

        required_months = int(
            settings.get(
                "revenue_months",
                3
            )
        )

        required_months = max(
            required_months,
            2
        )

        recent = data.tail(
            required_months
        )

        trend_available = (
            len(recent) >= required_months
        )

        trend_up = False

        if trend_available:

            revenues = (
                recent["revenue"]
                .tolist()
            )

            trend_up = all(
                revenues[index] >
                revenues[index - 1]
                for index in range(
                    1,
                    len(revenues)
                )
            )

            result["trend"] = (
                "連續增加"
                if trend_up
                else "未連續增加"
            )

        if latest_yoy is None:

            result["message"] = (
                "缺少去年同期營收，"
                "無法計算年增率"
            )

            return result

        if not trend_available:

            result["message"] = (
                "營收月份不足，"
                "無法判斷趨勢"
            )

            return result

        target = float(
            settings.get(
                "revenue_yoy_target",
                20
            )
        )

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

        trend_score = (
            15
            if trend_up
            else 0
        )

        result["score"] = (
            yoy_score +
            trend_score
        )

        result["data_available"] = True

        if (
            latest_yoy >= target
            and trend_up
        ):

            result["message"] = (
                "年增率達標且營收連續增加"
            )

        elif latest_yoy >= 0:

            result["message"] = (
                "營收年增率為正"
            )

        else:

            result["message"] = (
                "營收年增率為負"
            )

        logging.info(
            "%s 營收：%s，YoY=%.2f%%，趨勢=%s，分數=%s",
            stock_id,
            result["latest_revenue_month"],
            latest_yoy,
            result["trend"],
            result["score"]
        )

        return result

    except Exception as exc:

        result["message"] = (
            "營收資料取得失敗"
        )

        result["error"] = str(
            exc
        )

        logging.exception(
            "%s 分析月營收發生錯誤。",
            stock_id
        )

        return result


# ============================================================
# 8. 籌碼面：外資持股比例
# ============================================================

def analyze_foreign_holding(
    dl,
    stock_id,
    settings,
    today
):

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

        periods = int(
            settings.get(
                "foreign_periods",
                4
            )
        )

        periods = max(
            periods,
            2
        )

        start_date = (
            today -
            datetime.timedelta(days=180)
        ).strftime("%Y-%m-%d")

        df = dl.taiwan_stock_shareholding(
            stock_id=stock_id,
            start_date=start_date
        )

        if df is None or df.empty:

            result["message"] = (
                "沒有外資持股資料"
            )

            return result

        if "date" not in df.columns:

            result["message"] = (
                "外資持股資料缺少 date 欄位"
            )

            return result

        ratio_column = (
            "ForeignInvestmentSharesRatio"
        )

        if ratio_column not in df.columns:

            result["message"] = (
                f"外資持股資料缺少 "
                f"{ratio_column} 欄位"
            )

            logging.error(
                "%s 外資持股欄位：%s",
                stock_id,
                list(df.columns)
            )

            return result

        data = df[
            [
                "date",
                ratio_column
            ]
        ].copy()

        data["date"] = pd.to_datetime(
            data["date"],
            errors="coerce"
        )

        data["ratio"] = pd.to_numeric(
            data[ratio_column],
            errors="coerce"
        )

        data = data.dropna(
            subset=[
                "date",
                "ratio"
            ]
        )

        data = data.sort_values(
            "date"
        )

        data = data.drop_duplicates(
            subset=["date"],
            keep="last"
        ).reset_index(
            drop=True
        )

        if len(data) < periods:

            result["message"] = (
                f"外資持股資料不足，"
                f"需要 {periods} 期，"
                f"目前 {len(data)} 期"
            )

            return result

        recent = (
            data.tail(periods)
            .reset_index(drop=True)
        )

        ratios = (
            recent["ratio"]
            .astype(float)
            .tolist()
        )

        latest_percent = ratios[-1]

        change = (
            latest_percent -
            ratios[0]
        )

        result["latest_percent"] = (
            latest_percent
        )

        result["change_periods"] = (
            change
        )

        result["latest_date"] = (
            recent.iloc[-1]["date"]
            .strftime("%Y-%m-%d")
        )

        differences = [
            ratios[index] -
            ratios[index - 1]
            for index in range(
                1,
                len(ratios)
            )
        ]

        all_increasing = all(
            value > 0
            for value in differences
        )

        if all_increasing:

            result["trend"] = (
                "連續增加"
            )

            score = 20

            message = (
                f"最近 {periods} 期外資持股比例連續增加"
            )

        elif change > 0:

            result["trend"] = (
                "整體增加"
            )

            score = 15

            message = (
                f"最近 {periods} 期外資持股比例整體增加"
            )

        elif change == 0:

            result["trend"] = (
                "大致持平"
            )

            score = 8

            message = (
                f"最近 {periods} 期外資持股比例持平"
            )

        else:

            result["trend"] = (
                "整體減少"
            )

            score = 0

            message = (
                f"最近 {periods} 期外資持股比例整體減少"
            )

        result["score"] = score

        result["message"] = message

        result["data_available"] = True

        logging.info(
            "%s 外資持股：日期=%s，比例=%.4f，"
            "變化=%.4f，趨勢=%s，分數=%s",
            stock_id,
            result["latest_date"],
            latest_percent,
            change,
            result["trend"],
            score
        )

        return result

    except Exception as exc:

        result["message"] = (
            "外資持股資料取得失敗"
        )

        result["error"] = str(
            exc
        )

        logging.exception(
            "%s 分析外資持股發生錯誤。",
            stock_id
        )

        return result


# ============================================================
# 9. 技術面：整理每日股價
# ============================================================

def prepare_price_data(df):

    required = {
        "date",
        "Trading_Volume",
        "open",
        "max",
        "min",
        "close"
    }

    if df is None or df.empty:

        return pd.DataFrame()

    missing = (
        required -
        set(df.columns)
    )

    if missing:

        logging.error(
            "股價資料缺少欄位：%s；實際欄位：%s",
            sorted(missing),
            list(df.columns)
        )

        return pd.DataFrame()

    data = df[
        [
            "date",
            "Trading_Volume",
            "open",
            "max",
            "min",
            "close"
        ]
    ].copy()

    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce"
    )

    numeric_columns = [
        "Trading_Volume",
        "open",
        "max",
        "min",
        "close"
    ]

    for column in numeric_columns:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    data = data.dropna(
        subset=[
            "date",
            "close"
        ]
    )

    data = data.sort_values(
        "date"
    )

    data = data.drop_duplicates(
        subset=["date"],
        keep="last"
    )

    return data.reset_index(
        drop=True
    )


# ============================================================
# 10. RSI
# ============================================================

def calculate_rsi(
    close,
    period=14
):
    """
    RSI(14)。

    修正：
    - 平均跌幅為 0 時，不回傳 NaN。
    - 完全沒有漲跌時 RSI = 50。
    - 持續上漲時 RSI = 100。
    """

    delta = close.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    average_gain = (
        gain.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        ).mean()
    )

    average_loss = (
        loss.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        ).mean()
    )

    rsi = pd.Series(
        index=close.index,
        dtype="float64"
    )

    normal = (
        (average_loss > 0)
        &
        average_gain.notna()
        &
        average_loss.notna()
    )

    rsi.loc[normal] = (
        100 -
        (
            100 /
            (
                1 +
                (
                    average_gain.loc[normal] /
                    average_loss.loc[normal]
                )
            )
        )
    )

    no_loss = (
        (average_loss == 0)
        &
        (average_gain > 0)
    )

    rsi.loc[no_loss] = 100.0

    no_change = (
        (average_loss == 0)
        &
        (average_gain == 0)
        &
        average_gain.notna()
    )

    rsi.loc[no_change] = 50.0

    return rsi


# ============================================================
# 11. MACD
# ============================================================

def calculate_macd(
    close,
    fast_period=12,
    slow_period=26,
    signal_period=9
):

    ema_fast = close.ewm(
        span=fast_period,
        adjust=False
    ).mean()

    ema_slow = close.ewm(
        span=slow_period,
        adjust=False
    ).mean()

    dif = (
        ema_fast -
        ema_slow
    )

    dea = dif.ewm(
        span=signal_period,
        adjust=False
    ).mean()

    histogram = (
        dif -
        dea
    )

    return (
        dif,
        dea,
        histogram
    )


# ============================================================
# 12. KD
# ============================================================

def calculate_kd(
    high,
    low,
    close,
    period=9
):
    """
    KD(9,3,3)。

    使用：
    RSV = (Close - LowestLow) /
          (HighestHigh - LowestLow) * 100

    K = 2/3 * 前一期K + 1/3 * RSV
    D = 2/3 * 前一期D + 1/3 * K
    """

    lowest_low = (
        low.rolling(
            window=period,
            min_periods=period
        ).min()
    )

    highest_high = (
        high.rolling(
            window=period,
            min_periods=period
        ).max()
    )

    denominator = (
        highest_high -
        lowest_low
    )

    rsv = (
        (
            close -
            lowest_low
        )
        /
        denominator.replace(
            0,
            float("nan")
        )
    ) * 100

    k_values = []

    d_values = []

    previous_k = 50.0
    previous_d = 50.0

    for value in rsv:

        if pd.isna(value):

            k_values.append(
                float("nan")
            )

            d_values.append(
                float("nan")
            )

            continue

        current_k = (
            previous_k * 2 / 3
            +
            float(value) / 3
        )

        current_d = (
            previous_d * 2 / 3
            +
            current_k / 3
        )

        k_values.append(
            current_k
        )

        d_values.append(
            current_d
        )

        previous_k = current_k
        previous_d = current_d

    return (
        pd.Series(
            k_values,
            index=close.index
        ),
        pd.Series(
            d_values,
            index=close.index
        )
    )


# ============================================================
# 13. 技術面分析
# ============================================================

def analyze_technical(
    dl,
    stock_id,
    settings,
    today
):
    """
    技術面 40 分：

    MA 趨勢       15 分
    RSI            8 分
    MACD           8 分
    KD             5 分
    成交量         4 分
    ----------------
    合計           40 分
    """

    result = {

        "score": None,

        "data_available": False,

        "latest_date": None,

        "latest_close": None,

        "ma": {
            "ma5": None,
            "ma10": None,
            "ma20": None,
            "ma60": None,
            "trend": "資料不足",
            "score": None
        },

        "rsi": {
            "value": None,
            "signal": "資料不足",
            "score": None
        },

        "macd": {
            "dif": None,
            "dea": None,
            "histogram": None,
            "signal": "資料不足",
            "score": None
        },

        "kd": {
            "k": None,
            "d": None,
            "signal": "資料不足",
            "score": None
        },

        "volume": {
            "today": None,
            "avg5": None,
            "ratio": None,
            "signal": "資料不足",
            "score": None
        },

        "breakout": {
            "high20": None,
            "low20": None,
            "distance_to_high20_percent": None,
            "distance_to_low20_percent": None,
            "signal": "資料不足"
        },

        "message": "資料不足"
    }

    try:

        technical_days = int(
            settings.get(
                "technical_days",
                180
            )
        )

        # 至少保留 100 個日曆日，
        # 實際再額外留一些緩衝。
        technical_days = max(
            technical_days,
            120
        )

        start_date = (
            today -
            datetime.timedelta(
                days=technical_days
            )
        ).strftime("%Y-%m-%d")

        df = dl.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=start_date
        )

        data = prepare_price_data(
            df
        )

        if data.empty:

            result["message"] = (
                "沒有可用的股價資料"
            )

            logging.warning(
                "%s 股價資料為空。",
                stock_id
            )

            return result

        # ----------------------------------------------------
        # MA
        # ----------------------------------------------------

        data["ma5"] = (
            data["close"]
            .rolling(
                window=5,
                min_periods=5
            )
            .mean()
        )

        data["ma10"] = (
            data["close"]
            .rolling(
                window=10,
                min_periods=10
            )
            .mean()
        )

        data["ma20"] = (
            data["close"]
            .rolling(
                window=20,
                min_periods=20
            )
            .mean()
        )

        data["ma60"] = (
            data["close"]
            .rolling(
                window=60,
                min_periods=60
            )
            .mean()
        )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        data["rsi"] = calculate_rsi(
            data["close"],
            14
        )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        (
            data["macd_dif"],
            data["macd_dea"],
            data["macd_histogram"]
        ) = calculate_macd(
            data["close"]
        )

        # ----------------------------------------------------
        # KD
        # ----------------------------------------------------

        (
            data["kd_k"],
            data["kd_d"]
        ) = calculate_kd(
            data["max"],
            data["min"],
            data["close"]
        )

        # ----------------------------------------------------
        # 成交量
        # ----------------------------------------------------

        data["volume_ma5"] = (
            data["Trading_Volume"]
            .rolling(
                window=5,
                min_periods=5
            )
            .mean()
        )

        # ----------------------------------------------------
        # 至少需要 60 個交易日
        # ----------------------------------------------------

        if len(data) < 60:

            result["message"] = (
                "股價資料不足，需要至少 "
                f"60 個交易日，目前只有 "
                f"{len(data)} 日"
            )

            return result

        latest = data.iloc[-1]

        latest_date = pd.to_datetime(
            latest["date"]
        ).strftime(
            "%Y-%m-%d"
        )

        close = number_or_none(
            latest["close"]
        )

        ma5 = number_or_none(
            latest["ma5"]
        )

        ma10 = number_or_none(
            latest["ma10"]
        )

        ma20 = number_or_none(
            latest["ma20"]
        )

        ma60 = number_or_none(
            latest["ma60"]
        )

        rsi = number_or_none(
            latest["rsi"]
        )

        macd_dif = number_or_none(
            latest["macd_dif"]
        )

        macd_dea = number_or_none(
            latest["macd_dea"]
        )

        macd_histogram = number_or_none(
            latest["macd_histogram"]
        )

        kd_k = number_or_none(
            latest["kd_k"]
        )

        kd_d = number_or_none(
            latest["kd_d"]
        )

        volume_today = number_or_none(
            latest["Trading_Volume"]
        )

        volume_ma5 = number_or_none(
            latest["volume_ma5"]
        )

        # ----------------------------------------------------
        # 技術指標資料檢查
        # ----------------------------------------------------

        indicator_values = [
            close,
            ma5,
            ma10,
            ma20,
            ma60,
            rsi,
            macd_dif,
            macd_dea,
            macd_histogram,
            kd_k,
            kd_d,
            volume_today,
            volume_ma5
        ]

        missing_count = sum(
            value is None
            for value in indicator_values
        )

        if missing_count > 0:

            result["message"] = (
                "技術指標資料不足，"
                f"缺少 {missing_count} 項"
            )

            return result

        result["latest_date"] = (
            latest_date
        )

        result["latest_close"] = (
            close
        )

        # ====================================================
        # MA：15 分
        # ====================================================

        if (
            close > ma5
            and ma5 > ma10
            and ma10 > ma20
            and ma20 > ma60
        ):

            ma_trend = (
                "多頭排列"
            )

            ma_score = 15

        elif (
            close > ma20
            and ma20 > ma60
        ):

            ma_trend = (
                "中期偏多"
            )

            ma_score = 11

        elif close > ma60:

            ma_trend = (
                "站上60日線"
            )

            ma_score = 8

        elif (
            close < ma20
            and ma20 < ma60
        ):

            ma_trend = (
                "中期偏弱"
            )

            ma_score = 2

        else:

            ma_trend = (
                "盤整"
            )

            ma_score = 5

        result["ma"] = {

            "ma5": round(
                ma5,
                2
            ),

            "ma10": round(
                ma10,
                2
            ),

            "ma20": round(
                ma20,
                2
            ),

            "ma60": round(
                ma60,
                2
            ),

            "trend": ma_trend,

            "score": ma_score
        }

        # ====================================================
        # RSI：8 分
        # ====================================================

        if rsi >= 70:

            rsi_signal = (
                "超買"
            )

            rsi_score = 5

        elif rsi >= 60:

            rsi_signal = (
                "偏強"
            )

            rsi_score = 8

        elif rsi >= 50:

            rsi_signal = (
                "中性偏強"
            )

            rsi_score = 6

        elif rsi >= 40:

            rsi_signal = (
                "中性偏弱"
            )

            rsi_score = 4

        elif rsi >= 30:

            rsi_signal = (
                "偏弱"
            )

            rsi_score = 2

        else:

            rsi_signal = (
                "超賣"
            )

            rsi_score = 3

        result["rsi"] = {

            "value": round(
                rsi,
                2
            ),

            "signal": rsi_signal,

            "score": rsi_score
        }

        # ====================================================
        # MACD：8 分
        # ====================================================

        if (
            macd_dif > macd_dea
            and macd_histogram > 0
        ):

            macd_signal = (
                "多方"
            )

            macd_score = 8

        elif macd_dif > macd_dea:

            macd_signal = (
                "偏多"
            )

            macd_score = 6

        elif (
            macd_dif < macd_dea
            and macd_histogram < 0
        ):

            macd_signal = (
                "空方"
            )

            macd_score = 1

        else:

            macd_signal = (
                "中性"
            )

            macd_score = 4

        result["macd"] = {

            "dif": round(
                macd_dif,
                4
            ),

            "dea": round(
                macd_dea,
                4
            ),

            "histogram": round(
                macd_histogram,
                4
            ),

            "signal": macd_signal,

            "score": macd_score
        }

        # ====================================================
        # KD：5 分
        # ====================================================

        if (
            kd_k > kd_d
            and kd_k >= 50
        ):

            kd_signal = (
                "偏強"
            )

            kd_score = 5

        elif kd_k > kd_d:

            kd_signal = (
                "短線轉強"
            )

            kd_score = 4

        elif (
            kd_k < kd_d
            and kd_k < 50
        ):

            kd_signal = (
                "偏弱"
            )

            kd_score = 1

        else:

            kd_signal = (
                "中性"
            )

            kd_score = 3

        result["kd"] = {

            "k": round(
                kd_k,
                2
            ),

            "d": round(
                kd_d,
                2
            ),

            "signal": kd_signal,

            "score": kd_score
        }

        # ====================================================
        # 成交量：4 分
        # ====================================================

        if volume_ma5 == 0:

            volume_ratio = None

        else:

            volume_ratio = (
                volume_today /
                volume_ma5
            )

        if volume_ratio is None:

            volume_signal = (
                "資料不足"
            )

            volume_score = 0

        elif volume_ratio >= 1.5:

            volume_signal = (
                "明顯量增"
            )

            volume_score = 4

        elif volume_ratio >= 1.1:

            volume_signal = (
                "量增"
            )

            volume_score = 3

        elif volume_ratio >= 0.8:

            volume_signal = (
                "量能正常"
            )

            volume_score = 2

        else:

            volume_signal = (
                "量縮"
            )

            volume_score = 1

        result["volume"] = {

            "today": volume_today,

            "avg5": round(
                volume_ma5,
                2
            ),

            "ratio": (
                round(
                    volume_ratio,
                    2
                )
                if volume_ratio is not None
                else None
            ),

            "signal": volume_signal,

            "score": volume_score
        }

        # ====================================================
        # 20 日高低點
        # ====================================================

        previous_20 = (
            data.iloc[:-1]
            .tail(20)
        )

        if len(previous_20) >= 20:

            high20 = number_or_none(
                previous_20["max"].max()
            )

            low20 = number_or_none(
                previous_20["min"].min()
            )

            if (
                high20 is not None
                and low20 is not None
                and high20 > 0
                and low20 > 0
            ):

                distance_high = (
                    close /
                    high20 -
                    1
                ) * 100

                distance_low = (
                    close /
                    low20 -
                    1
                ) * 100

                if close > high20:

                    breakout_signal = (
                        "突破20日高點"
                    )

                elif close >= (
                    high20 * 0.98
                ):

                    breakout_signal = (
                        "接近20日高點"
                    )

                elif close < low20:

                    breakout_signal = (
                        "跌破20日低點"
                    )

                elif close <= (
                    low20 * 1.02
                ):

                    breakout_signal = (
                        "接近20日低點"
                    )

                else:

                    breakout_signal = (
                        "20日區間內"
                    )

                result["breakout"] = {

                    "high20": round(
                        high20,
                        2
                    ),

                    "low20": round(
                        low20,
                        2
                    ),

                    "distance_to_high20_percent": round(
                        distance_high,
                        2
                    ),

                    "distance_to_low20_percent": round(
                        distance_low,
                        2
                    ),

                    "signal": breakout_signal
                }

        # ====================================================
        # 技術總分
        # ====================================================

        technical_score = (
            ma_score
            +
            rsi_score
            +
            macd_score
            +
            kd_score
            +
            volume_score
        )

        result["score"] = (
            technical_score
        )

        result["data_available"] = True

        if technical_score >= 32:

            result["message"] = (
                "技術面強勢"
            )

        elif technical_score >= 26:

            result["message"] = (
                "技術面偏多"
            )

        elif technical_score >= 20:

            result["message"] = (
                "技術面中性"
            )

        elif technical_score >= 14:

            result["message"] = (
                "技術面偏弱"
            )

        else:

            result["message"] = (
                "技術面弱勢"
            )

        logging.info(
            "%s 技術分析："
            "收盤=%.2f，"
            "MA=%s，"
            "RSI=%.2f，"
            "MACD=%s，"
            "KD=%s，"
            "量比=%s，"
            "技術分數=%s",
            stock_id,
            close,
            ma_trend,
            rsi,
            macd_signal,
            kd_signal,
            volume_ratio,
            technical_score
        )

        return result

    except Exception as exc:

        result["message"] = (
            "技術分析資料取得失敗"
        )

        result["error"] = str(
            exc
        )

        logging.exception(
            "%s 分析技術面發生錯誤。",
            stock_id
        )

        return result


# ============================================================
# 14. 綜合評分
# ============================================================

def calculate_overall_score(
    revenue,
    foreign_holding,
    technical
):
    """
    基本面：40 分
    籌碼面：20 分
    技術面：40 分

    合計：100 分。
    """

    if not revenue.get(
        "data_available"
    ):

        return None

    if not foreign_holding.get(
        "data_available"
    ):

        return None

    if not technical.get(
        "data_available"
    ):

        return None

    revenue_score = number_or_none(
        revenue.get("score")
    )

    foreign_score = number_or_none(
        foreign_holding.get("score")
    )

    technical_score = number_or_none(
        technical.get("score")
    )

    if (
        revenue_score is None
        or foreign_score is None
        or technical_score is None
    ):

        return None

    total = (
        revenue_score
        +
        foreign_score
        +
        technical_score
    )

    return round(
        total,
        1
    )


# ============================================================
# 15. 狀態
# ============================================================

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
# 16. 單一股票分析
# ============================================================

def analyze_stock(
    dl,
    stock_id,
    settings,
    today
):

    logging.info(
        "=================================================="
    )

    logging.info(
        "開始分析股票 %s",
        stock_id
    )

    revenue = analyze_revenue(
        dl,
        stock_id,
        settings,
        today
    )

    foreign_holding = (
        analyze_foreign_holding(
            dl,
            stock_id,
            settings,
            today
        )
    )

    technical = analyze_technical(
        dl,
        stock_id,
        settings,
        today
    )

    score = calculate_overall_score(
        revenue,
        foreign_holding,
        technical
    )

    missing_items = []

    if not revenue.get(
        "data_available"
    ):

        missing_items.append(
            "營收"
        )

    if not foreign_holding.get(
        "data_available"
    ):

        missing_items.append(
            "外資持股"
        )

    if not technical.get(
        "data_available"
    ):

        missing_items.append(
            "技術面"
        )

    result = {

        "stock_id": stock_id,

        "analysis_date": (
            today.strftime(
                "%Y-%m-%d"
            )
        ),

        "revenue": revenue,

        "foreign_holding": foreign_holding,

        "technical": technical,

        "score": score,

        "status": get_status(
            score
        ),

        "data_quality": {

            "complete": (
                len(missing_items) == 0
            ),

            "missing_items": (
                missing_items
            )
        }
    }

    logging.info(
        "完成分析 %s："
        "score=%s，"
        "status=%s，"
        "缺失=%s",
        stock_id,
        score,
        result["status"],
        missing_items
    )

    return result


# ============================================================
# 17. 主程式
# ============================================================

def analyze_stocks():

    setup_logging()

    logging.info(
        "=" * 60
    )

    logging.info(
        "台股分析程式開始執行"
    )

    config = load_config()

    stocks = config["stocks"]

    settings = config.get(
        "settings",
        {}
    )

    now = datetime.datetime.now(
        TAIPEI_TZ
    )

    today = now.date()

    logging.info(
        "分析日期：%s",
        today
    )

    logging.info(
        "觀察股票數量：%s",
        len(stocks)
    )

    logging.info(
        "股票清單：%s",
        ", ".join(stocks)
    )

    try:

        dl = DataLoader()

    except Exception:

        logging.exception(
            "建立 FinMind DataLoader 失敗。"
        )

        raise

    results = []

    # --------------------------------------------------------
    # 逐檔分析
    # --------------------------------------------------------

    for stock_id in stocks:

        try:

            result = analyze_stock(
                dl,
                stock_id,
                settings,
                today
            )

            results.append(
                result
            )

        except Exception:

            logging.exception(
                "分析股票 %s 發生未預期錯誤。",
                stock_id
            )

            results.append({

                "stock_id": stock_id,

                "analysis_date": (
                    today.strftime(
                        "%Y-%m-%d"
                    )
                ),

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
            })

    # --------------------------------------------------------
    # 排序
    # --------------------------------------------------------

    results.sort(
        key=lambda item: (
            item["score"] is None,
            -(item["score"] or 0)
        )
    )

    # --------------------------------------------------------
    # 統計
    # --------------------------------------------------------

    complete_count = sum(
        1
        for item in results
        if item.get(
            "data_quality",
            {}
        ).get(
            "complete"
        )
    )

    technical_count = sum(
        1
        for item in results
        if item.get(
            "technical",
            {}
        ).get(
            "data_available"
        )
    )

    # --------------------------------------------------------
    # analysis.json
    # --------------------------------------------------------

    output = {

        "update_time": (
            now.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ),

        "stock_count": (
            len(results)
        ),

        "complete_count": (
            complete_count
        ),

        "technical_count": (
            technical_count
        ),

        "score_description": {

            "revenue": 40,

            "foreign_holding": 20,

            "technical": 40,

            "total": 100
        },

        "stocks": results
    }

    safe_output = to_json_safe(
        output
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            safe_output,
            file,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        )

    # --------------------------------------------------------
    # 完成紀錄
    # --------------------------------------------------------

    logging.info(
        "=============================================="
    )

    logging.info(
        "分析股票數量：%s",
        len(results)
    )

    logging.info(
        "完整資料股票數量：%s",
        complete_count
    )

    logging.info(
        "技術分析成功數量：%s",
        technical_count
    )

    logging.info(
        "已輸出：%s",
        OUTPUT_FILE
    )

    logging.info(
        "台股分析程式執行完成"
    )

    logging.info(
        "=" * 60
    )


# ============================================================
# 18. Entry Point
# ============================================================

if __name__ == "__main__":
    analyze_stocks()
