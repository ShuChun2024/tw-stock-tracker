import json
import logging
import re
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

STOCK_LIST_FILE = BASE_DIR / "stocks.json"
OUTPUT_FILE = BASE_DIR / "stock_prices.json"

DAYS_TO_OUTPUT = 5
DAYS_TO_FETCH = 6
MAX_MONTHS_BACK = 4

REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.5
MAX_RETRIES = 3

TWSE_URL = (
    "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
)

TPEX_URL = (
    "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
)

WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# 2. HTTP Session
# ============================================================

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def request_json(url, params):
    """取得 JSON，失敗時重試。"""

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = SESSION.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            result = response.json()

            if not isinstance(result, dict):
                raise ValueError("API 回傳格式不是 JSON 物件")

            return result

        except Exception as exc:
            last_error = exc

            logger.warning(
                "API 請求失敗，第 %s/%s 次：%s",
                attempt,
                MAX_RETRIES,
                exc,
            )

            if attempt < MAX_RETRIES:
                time.sleep(attempt * 2)

    raise RuntimeError(
        f"API 請求失敗：{last_error}"
    )


# ============================================================
# 3. 日期及數字處理
# ============================================================

def parse_number(value):
    """將 API 數值轉成 float，無效值回傳 None。"""

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if text in ("--", "-", "X", "x", "除權", "除息", "N/A"):
        return None

    text = text.replace(",", "").replace("元", "")

    text = text.replace("＋", "+").replace("－", "-")

    try:
        return float(text)
    except ValueError:
        return None


def format_number(value):
    """整數不顯示小數，其他數字最多保留兩位。"""

    if value is None:
        return None

    value = round(float(value), 2)

    if value.is_integer():
        return int(value)

    return value


def parse_api_date(value):
    """
    支援：
    115/11/06
    115/11/6
    1151106
    2026-11-06
    """

    text = str(value).strip()

    text = re.sub(r"\s+", "", text)

    if not text:
        return None

    # 西元 YYYY-MM-DD
    match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", text)

    if match:
        year, month, day = map(int, match.groups())
        return date(year, month, day)

    # 民國 YYY/MM/DD
    match = re.match(r"^(\d{2,3})/(\d{1,2})/(\d{1,2})$", text)

    if match:
        year, month, day = map(int, match.groups())
        return date(year + 1911, month, day)

    # 民國 YYYMMDD
    match = re.match(r"^(\d{2,3})(\d{2})(\d{2})$", text)

    if match:
        year, month, day = map(int, match.groups())
        return date(year + 1911, month, day)

    return None


def shift_month(year, month, offset):
    """月份往前推移。"""

    total = year * 12 + month - 1 - offset

    return total // 12, total % 12 + 1


def normalize_market(value):
    """統一上市、上櫃市場名稱。"""

    text = str(value or "").strip().upper()

    if text in ("上市", "TWSE", "TSE", "LISTED"):
        return "TWSE"

    if text in ("上櫃", "TPEx", "TPEX", "OTC"):
        return "TPEX"

    return None


# ============================================================
# 4. 解析證交所上市資料
# ============================================================

def fetch_twse_month(stock_id, year, month):
    """取得上市股票指定月份的每日行情。"""

    params = {
        "date": f"{year}{month:02d}01",
        "stockNo": stock_id,
        "response": "json",
    }

    result = request_json(TWSE_URL, params)

    if result.get("stat") != "OK":
        logger.warning(
            "TWSE 無有效資料：%s / %s-%s / %s",
            stock_id,
            year,
            month,
            result.get("stat"),
        )
        return []

    fields = result.get("fields", [])
    rows = result.get("data", [])

    if not fields or not rows:
        return []

    field_map = {
        str(name).strip(): index
        for index, name in enumerate(fields)
    }

    date_index = field_map.get("日期")
    close_index = field_map.get("收盤價")
    change_index = field_map.get("漲跌價差")

    if date_index is None or close_index is None:
        raise ValueError(
            f"TWSE 欄位不完整：{fields}"
        )

    output = []

    for row in rows:
        try:
            trading_date = parse_api_date(row[date_index])
            close_price = parse_number(row[close_index])

            change = None

            if change_index is not None:
                change = parse_number(row[change_index])

            if trading_date is None or close_price is None:
                continue

            output.append({
                "date": trading_date,
                "close": close_price,
                "change": change,
            })

        except (IndexError, TypeError):
            continue

    return output


# ============================================================
# 5. 解析櫃買中心上櫃資料
# ============================================================

def extract_tpex_table(result):
    """取得 TPEx API 的欄位及資料。"""

    tables = result.get("tables")

    if isinstance(tables, list) and tables:
        table = tables[0]

        if isinstance(table, dict):
            return (
                table.get("fields", []),
                table.get("data", []),
            )

    # 相容其他可能的 JSON 結構
    if "fields" in result and "data" in result:
        return result["fields"], result["data"]

    return [], []


def fetch_tpex_month(stock_id, year, month):
    """取得上櫃股票指定月份的每日行情。"""

    params = {
        "code": stock_id,
        "date": f"{year}/{month:02d}/01",
        "response": "json",
    }

    result = request_json(TPEX_URL, params)

    fields, rows = extract_tpex_table(result)

    if not fields or not rows:
        return []

    # 欄位名稱去除空白
    normalized_fields = [
        re.sub(r"\s+", "", str(field).replace("<br>", ""))
        for field in fields
    ]

    date_index = None
    close_index = None
    change_index = None

    for index, field in enumerate(normalized_fields):

        if field in ("日期", "日期"):
            date_index = index

        elif field in ("收盤", "收盤價"):
            close_index = index

        elif field in ("漲跌", "漲跌價差"):
            change_index = index

    if date_index is None or close_index is None:
        raise ValueError(
            f"TPEx 欄位無法辨識：{fields}"
        )

    output = []

    for row in rows:
        try:
            trading_date = parse_api_date(row[date_index])
            close_price = parse_number(row[close_index])

            change = None

            if change_index is not None:
                change = parse_number(row[change_index])

            if trading_date is None or close_price is None:
                continue

            output.append({
                "date": trading_date,
                "close": close_price,
                "change": change,
            })

        except (IndexError, TypeError):
            continue

    return output


# ============================================================
# 6. 取得最近交易日資料
# ============================================================

def fetch_stock_history(stock_id, market):
    """
    取得最近至少 6 個交易日資料。

    最終輸出只會保留最近 5 個交易日。
    """

    market = normalize_market(market)

    if market is None:
        raise ValueError(
            f"{stock_id} 市場資訊不明確，無法判斷資料來源"
        )

    today = datetime.now(
        ZoneInfo("Asia/Taipei")
    ).date()

    all_rows = {}

    for offset in range(MAX_MONTHS_BACK):

        year, month = shift_month(
            today.year,
            today.month,
            offset,
        )

        logger.info(
            "查詢 %s %s：%s-%02d",
            market,
            stock_id,
            year,
            month,
        )

        if market == "TWSE":
            rows = fetch_twse_month(
                stock_id,
                year,
                month,
            )

        else:
            rows = fetch_tpex_month(
                stock_id,
                year,
                month,
            )

        for row in rows:
            if row["date"] <= today:
                all_rows[row["date"]] = row

        sorted_rows = sorted(
            all_rows.values(),
            key=lambda item: item["date"],
        )

        if len(sorted_rows) >= DAYS_TO_FETCH:
            break

        time.sleep(REQUEST_DELAY)

    sorted_rows = sorted(
        all_rows.values(),
        key=lambda item: item["date"],
    )

    if len(sorted_rows) < DAYS_TO_FETCH:
        raise RuntimeError(
            f"{stock_id} 有效交易日不足 "
            f"{DAYS_TO_FETCH} 日，實際取得 {len(sorted_rows)} 日"
        )

    # 由舊到新，計算漲跌
    calculated = []

    for index, row in enumerate(sorted_rows):

        close_price = row["close"]
        change = row["change"]

        # 官方漲跌價差無效時，使用前一交易日收盤價計算
        if change is None and index > 0:
            previous_close = sorted_rows[index - 1]["close"]
            change = close_price - previous_close

        change_percent = None

        if change is not None:
            reference_price = close_price - change

            if reference_price > 0:
                change_percent = (
                    change / reference_price
                ) * 100

        trading_date = row["date"]

        calculated.append({
            "date": trading_date.strftime("%Y-%m-%d"),
            "weekday": WEEKDAYS[trading_date.weekday()],
            "close": format_number(close_price),
            "change": format_number(change),
            "change_percent": (
                round(change_percent, 2)
                if change_percent is not None
                else None
            ),
        })

    # 只保留最近 5 日，由新到舊
    return list(reversed(calculated[-DAYS_TO_OUTPUT:]))


# ============================================================
# 7. 讀取股票清單
# ============================================================

def load_stock_list():
    """讀取現有 stocks.json。"""

    if not STOCK_LIST_FILE.exists():
        raise FileNotFoundError(
            f"找不到股票清單：{STOCK_LIST_FILE}"
        )

    with open(
        STOCK_LIST_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        content = json.load(file)

    stocks = content.get("stocks", [])

    if not isinstance(stocks, list) or not stocks:
        raise ValueError(
            "stocks.json 沒有有效的 stocks 清單"
        )

    output = []

    for item in stocks:
        stock_id = str(
            item.get("stock_id", "")
        ).strip()

        if not stock_id:
            continue

        market = normalize_market(
            item.get("market")
        )

        if market is None:
            raise ValueError(
                f"股票 {stock_id} 缺少有效市場欄位："
                f"{item.get('market')}"
            )

        output.append({
            "stock_id": stock_id,
            "stock_name": (
                item.get("short_name")
                or item.get("company_name")
                or stock_id
            ),
            "market": market,
        })

    return output


# ============================================================
# 8. 建立 JSON
# ============================================================

def build_stock_price_data(stocks):
    """逐檔取得行情，整理輸出資料。"""

    output_stocks = []
    failed_stocks = []

    for index, stock in enumerate(stocks, start=1):

        stock_id = stock["stock_id"]
        stock_name = stock["stock_name"]
        market = stock["market"]

        logger.info(
            "[%s/%s] 開始處理：%s %s",
            index,
            len(stocks),
            stock_id,
            stock_name,
        )

        try:
            history = fetch_stock_history(
                stock_id,
                market,
            )

            output_stocks.append({
                "stock_id": stock_id,
                "stock_name": stock_name,
                "market": market,
                "data": history,
            })

            logger.info(
                "完成：%s，取得 %s 個交易日",
                stock_id,
                len(history),
            )

        except Exception as exc:
            logger.exception(
                "股票 %s 處理失敗",
                stock_id,
            )

            failed_stocks.append({
                "stock_id": stock_id,
                "stock_name": stock_name,
                "error": str(exc),
            })

        time.sleep(REQUEST_DELAY)

    now = datetime.now(
        ZoneInfo("Asia/Taipei")
    )

    return {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "stock_count": len(output_stocks),
        "failed_count": len(failed_stocks),
        "failed_stocks": failed_stocks,
        "days": DAYS_TO_OUTPUT,
        "stocks": output_stocks,
    }


# ============================================================
# 9. 主程式
# ============================================================

def main():
    logger.info("=" * 65)
    logger.info("開始取得台股近 5 個交易日收盤行情")
    logger.info("=" * 65)

    stocks = load_stock_list()

    logger.info(
        "股票清單筆數：%s",
        len(stocks),
    )

    result = build_stock_price_data(stocks)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

    logger.info("=" * 65)
    logger.info("行情資料處理完成")
    logger.info("成功股票：%s", result["stock_count"])
    logger.info("失敗股票：%s", result["failed_count"])
    logger.info("輸出檔案：%s", OUTPUT_FILE)
    logger.info("=" * 65)

    if result["failed_stocks"]:
        logger.warning("以下股票未成功取得資料：")

        for item in result["failed_stocks"]:
            logger.warning(
                "%s %s：%s",
                item["stock_id"],
                item["stock_name"],
                item["error"],
            )


if __name__ == "__main__":
    main()
