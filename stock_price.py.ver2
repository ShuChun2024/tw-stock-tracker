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

CONFIG_FILE = BASE_DIR / "config.json"
STOCK_LIST_FILE = BASE_DIR / "stocks.json"  # 僅供補充股票名稱
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

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ============================================================
# 2. HTTP Session
# ============================================================

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

    if text.upper() in (
        "--", "-", "X", "除權", "除息", "N/A"
    ):
        return None

    text = text.replace(",", "")
    text = text.replace("元", "")
    text = text.replace("＋", "+")
    text = text.replace("－", "-")

    # 處理 + 15.00 這類含空白數字
    text = re.sub(r"\s+", "", text)

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
    match = re.match(
        r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$",
        text,
    )

    if match:
        year, month, day = map(int, match.groups())
        return date(year, month, day)

    # 民國 YYY/MM/DD
    match = re.match(
        r"^(\d{2,3})/(\d{1,2})/(\d{1,2})$",
        text,
    )

    if match:
        year, month, day = map(int, match.groups())
        return date(year + 1911, month, day)

    # 民國 YYYMMDD
    match = re.match(
        r"^(\d{2,3})(\d{2})(\d{2})$",
        text,
    )

    if match:
        year, month, day = map(int, match.groups())
        return date(year + 1911, month, day)

    return None


def shift_month(year, month, offset):
    """月份往前推移。"""

    total = year * 12 + month - 1 - offset

    return total // 12, total % 12 + 1


# ============================================================
# 4. 市場名稱標準化
# ============================================================

def normalize_market(value):
    """統一上市、上櫃市場名稱。"""

    text = str(value or "").strip().upper()

    if text in ("上市", "TWSE", "TSE", "LISTED"):
        return "TWSE"

    if text in ("上櫃", "TPEX", "OTC"):
        return "TPEX"

    return None


# ============================================================
# 5. 解析證交所上市資料
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
        logger.debug(
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
# 6. 解析櫃買中心上櫃資料
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

    normalized_fields = [
        re.sub(
            r"\s+",
            "",
            str(field).replace("<br>", ""),
        )
        for field in fields
    ]

    date_index = None
    close_index = None
    change_index = None

    for index, field in enumerate(normalized_fields):

        if field == "日期":
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
# 7. 自動判斷股票市場
# ============================================================

def detect_stock_market(stock_id, today):
    """
    只針對指定股票查詢市場。

    不下載全市場股票清單。
    先查 TWSE，沒有該股票行情時再查 TPEx。
    由近期月份往前檢查。
    """

    logger.info(
        "開始判斷股票市場：%s",
        stock_id,
    )

    for offset in range(MAX_MONTHS_BACK):

        year, month = shift_month(
            today.year,
            today.month,
            offset,
        )

        # 先查上市市場
        try:
            logger.info(
                "市場辨識 TWSE：%s / %s-%02d",
                stock_id,
                year,
                month,
            )

            rows = fetch_twse_month(
                stock_id,
                year,
                month,
            )

            if rows:
                logger.info(
                    "市場辨識成功：%s 屬於上市 TWSE",
                    stock_id,
                )
                return "TWSE"

        except Exception as exc:
            logger.warning(
                "%s TWSE 市場辨識查詢失敗：%s",
                stock_id,
                exc,
            )

        time.sleep(REQUEST_DELAY)

        # 再查上櫃市場
        try:
            logger.info(
                "市場辨識 TPEx：%s / %s-%02d",
                stock_id,
                year,
                month,
            )

            rows = fetch_tpex_month(
                stock_id,
                year,
                month,
            )

            if rows:
                logger.info(
                    "市場辨識成功：%s 屬於上櫃 TPEx",
                    stock_id,
                )
                return "TPEX"

        except Exception as exc:
            logger.warning(
                "%s TPEx 市場辨識查詢失敗：%s",
                stock_id,
                exc,
            )

        time.sleep(REQUEST_DELAY)

    raise RuntimeError(
        f"{stock_id} 無法判斷上市或上櫃市場，"
        f"已檢查最近 {MAX_MONTHS_BACK} 個月份"
    )


# ============================================================
# 8. 取得最近交易日資料
# ============================================================

def fetch_stock_history(stock_id, market=None):
    """
    取得最近至少 6 個交易日資料。

    market 未指定時，自動判斷 TWSE 或 TPEx。

    最終輸出只會保留最近 5 個交易日。
    """

    today = datetime.now(
        ZoneInfo("Asia/Taipei")
    ).date()

    # 自動判斷市場
    if market is None:
        market = detect_stock_market(
            stock_id,
            today,
        )
    else:
        market = normalize_market(market)

    if market is None:
        raise ValueError(
            f"{stock_id} 市場資訊無效"
        )

    logger.info(
        "%s 市場：%s",
        stock_id,
        market,
    )

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
            f"{DAYS_TO_FETCH} 日，"
            f"實際取得 {len(sorted_rows)} 日"
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
    return list(
        reversed(calculated[-DAYS_TO_OUTPUT:])
    )


# ============================================================
# 9. 讀取 config.json 股票清單
# ============================================================

def load_stock_names():
    """
    可選擇讀取 stocks.json 補充中文名稱。

    stocks.json 不參與選股，也不影響查詢範圍。
    """

    names = {}

    if not STOCK_LIST_FILE.exists():
        return names

    try:
        with open(
            STOCK_LIST_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            content = json.load(file)

        for item in content.get("stocks", []):
            stock_id = str(
                item.get("stock_id", "")
            ).strip()

            if stock_id:
                names[stock_id] = (
                    item.get("short_name")
                    or item.get("company_name")
                    or stock_id
                )

    except Exception as exc:
        logger.warning(
            "讀取 stocks.json 名稱資料失敗：%s",
            exc,
        )

    return names


def load_stock_list():
    """
    唯一選股來源：config.json 的 stocks。

    支援目前使用的字串格式：
    "stocks": ["2330", "2603", "2377"]

    也相容物件格式：
    {"stock_id": "2330", "market": "TWSE"}
    """

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"找不到設定檔：{CONFIG_FILE}"
        )

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        content = json.load(file)

    stocks = content.get("stocks", [])

    if not isinstance(stocks, list) or not stocks:
        raise ValueError(
            "config.json 沒有有效的 stocks 清單"
        )

    stock_names = load_stock_names()

    output = []
    seen = set()

    for item in stocks:

        if isinstance(item, dict):
            stock_id = str(
                item.get("stock_id", "")
            ).strip()

            market = normalize_market(
                item.get("market")
            )

            stock_name = (
                item.get("short_name")
                or item.get("stock_name")
                or item.get("company_name")
                or stock_names.get(stock_id)
                or stock_id
            )

        else:
            stock_id = str(item).strip()
            market = None
            stock_name = (
                stock_names.get(stock_id)
                or stock_id
            )

        if not stock_id:
            continue

        if stock_id in seen:
            logger.warning(
                "config.json 股票代號重複，略過：%s",
                stock_id,
            )
            continue

        seen.add(stock_id)

        output.append({
            "stock_id": stock_id,
            "stock_name": stock_name,
            "market": market,
        })

    if not output:
        raise ValueError(
            "config.json 沒有可執行的股票代號"
        )

    return output


# ============================================================
# 10. 建立 JSON
# ============================================================

def build_stock_price_data(stocks):
    """只針對 config.json 指定的股票逐檔取得行情。"""

    output_stocks = []
    failed_stocks = []

    for index, stock in enumerate(stocks, start=1):

        stock_id = stock["stock_id"]
        stock_name = stock["stock_name"]
        market = stock["market"]

        logger.info("-" * 65)
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

            # 以成功取得行情的實際市場為準
            actual_market = market

            if actual_market is None:
                actual_market = detect_stock_market(
                    stock_id,
                    datetime.now(
                        ZoneInfo("Asia/Taipei")
                    ).date(),
                )

            output_stocks.append({
                "stock_id": stock_id,
                "stock_name": stock_name,
                "market": actual_market,
                "data": history,
            })

            logger.info(
                "完成：%s，取得 %s 個交易日，市場：%s",
                stock_id,
                len(history),
                actual_market,
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
# 11. 主程式
# ============================================================

def main():

    logger.info("=" * 65)
    logger.info("開始取得 config.json 指定股票近 5 個交易日行情")
    logger.info("=" * 65)

    stocks = load_stock_list()

    logger.info(
        "config.json 指定股票數量：%s",
        len(stocks),
    )

    logger.info(
        "本次只處理以下股票：%s",
        ", ".join(
            stock["stock_id"]
            for stock in stocks
        ),
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
    logger.info("設定股票數量：%s", len(stocks))
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
