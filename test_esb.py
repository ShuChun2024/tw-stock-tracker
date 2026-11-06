import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import requests


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

STOCK_ID = "6750"
STOCK_NAME = "泰創工程"

# 櫃買中心興櫃個股歷史行情
BASE_URL = (
    "https://www.tpex.org.tw/"
    "zh-tw/esb/trading/info/stock-pricing.html"
)

# 查詢月份：2026 年 11 月
QUERY_DATE = "2026/11/01"

RAW_FILE = BASE_DIR / "esb_6750_response.txt"
OUTPUT_FILE = BASE_DIR / "esb_6750_test.json"

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
REQUEST_DELAY = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# 2. 預期測試資料
# ============================================================

EXPECTED_DATA = {
    "2026-11-02": {
        "volume": 62168,
        "turnover": 3584439,
        "high": 59.00,
        "low": 57.00,
        "average": 57.66,
        "trades": 48,
    },
    "2026-11-03": {
        "volume": 104415,
        "turnover": 5907576,
        "high": 59.00,
        "low": 55.80,
        "average": 56.58,
        "trades": 70,
    },
    "2026-11-04": {
        "volume": 180718,
        "turnover": 10037328,
        "high": 57.80,
        "low": 54.80,
        "average": 55.54,
        "trades": 122,
    },
    "2026-11-05": {
        "volume": 120277,
        "turnover": 6674927,
        "high": 56.80,
        "low": 54.80,
        "average": 55.50,
        "trades": 81,
    },
    "2026-11-06": {
        "volume": 138618,
        "turnover": 7382703,
        "high": 55.50,
        "low": 52.60,
        "average": 53.26,
        "trades": 113,
    },
}


# ============================================================
# 3. HTTP 請求
# ============================================================

def fetch_esb_response():

    params = {
        "type": "Monthly",
        "date": QUERY_DATE,
        "code": STOCK_ID,
        "id": "",
        "response": "json",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "application/json, text/javascript, "
            "text/html, */*"
        ),
        "Referer": BASE_URL,
    }

    session = requests.Session()

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            logger.info(
                "查詢櫃買中心興櫃行情：%s，第 %s 次",
                STOCK_ID,
                attempt
            )

            response = session.get(
                BASE_URL,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )

            # 不論成功與否，都保存原始回應
            RAW_FILE.write_text(
                response.text,
                encoding="utf-8"
            )

            logger.info("HTTP Status：%s", response.status_code)
            logger.info(
                "Content-Type：%s",
                response.headers.get("Content-Type")
            )
            logger.info("實際請求網址：%s", response.url)

            response.raise_for_status()

            if not response.text.strip():
                raise RuntimeError("櫃買中心回傳空白內容")

            return response.text

        except Exception as exc:

            last_error = exc

            logger.warning(
                "第 %s 次請求失敗：%s",
                attempt,
                exc
            )

            if attempt < MAX_RETRIES:
                time.sleep(REQUEST_DELAY)

    raise RuntimeError(
        f"櫃買中心行情查詢失敗：{last_error}"
    )


# ============================================================
# 4. 數值與日期處理
# ============================================================

def parse_number(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text or text in ("-", "---", "—"):
        return None

    text = text.replace(",", "")
    text = text.replace("元", "")
    text = text.replace("股", "")
    text = text.replace("筆", "")
    text = text.strip()

    try:
        number = float(text)

        if number.is_integer():
            return int(number)

        return number

    except (ValueError, TypeError):
        return None


def parse_date(value):

    text = str(value).strip()

    # 民國日期，例如 115/11/02
    roc_match = re.search(
        r"(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})",
        text
    )

    if roc_match:
        year = int(roc_match.group(1)) + 1911
        month = int(roc_match.group(2))
        day = int(roc_match.group(3))

        return (
            f"{year:04d}-{month:02d}-{day:02d}"
        )

    # 西元日期，例如 2026/11/02
    western_match = re.search(
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
        text
    )

    if western_match:
        year = int(western_match.group(1))
        month = int(western_match.group(2))
        day = int(western_match.group(3))

        return (
            f"{year:04d}-{month:02d}-{day:02d}"
        )

    return None


# ============================================================
# 5. 解析櫃買中心 JSON 表格
# ============================================================

def flatten_fields(fields):

    result = []

    for item in fields:

        if isinstance(item, list):
            result.extend(flatten_fields(item))

        else:
            result.append(str(item).strip())

    return result


def find_column(fields, keyword, occurrence=0):

    matches = []

    for index, field in enumerate(fields):

        normalized = (
            str(field)
            .replace(" ", "")
            .replace("\n", "")
            .replace("\r", "")
        )

        if keyword in normalized:
            matches.append(index)

    if len(matches) <= occurrence:
        return None

    return matches[occurrence]


def find_table(payload):

    candidates = []

    def walk(obj):

        if isinstance(obj, dict):

            fields = obj.get("fields")
            data = obj.get("data")

            if (
                isinstance(fields, list)
                and isinstance(data, list)
                and len(fields) > 0
            ):
                candidates.append((fields, data))

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):

            for item in obj:
                walk(item)

    walk(payload)

    for raw_fields, data in candidates:

        fields = flatten_fields(raw_fields)

        date_index = find_column(fields, "日期")
        average_index = find_column(
            fields, "成交均價", occurrence=0
        )

        if date_index is not None and average_index is not None:
            return fields, data

    return None, None


# ============================================================
# 6. 解析每日成交資料
# ============================================================

def parse_esb_data(raw_text):

    try:
        payload = json.loads(raw_text)

    except json.JSONDecodeError as exc:

        logger.error(
            "回應不是有效 JSON，請檢查原始回應檔"
        )

        logger.error(
            "回應開頭：%s",
            raw_text[:500]
        )

        raise RuntimeError(
            "櫃買中心回應格式不是 JSON"
        ) from exc

    logger.info(
        "JSON 最外層欄位：%s",
        list(payload.keys())
        if isinstance(payload, dict)
        else type(payload).__name__
    )

    fields, rows = find_table(payload)

    if fields is None:

        logger.error(
            "找不到包含日期與成交均價的資料表"
        )

        if isinstance(payload, dict):
            logger.error(
                "JSON 欄位：%s",
                list(payload.keys())
            )

        raise RuntimeError(
            "無法辨識櫃買中心回傳的資料表結構"
        )

    logger.info("成功找到資料表")
    logger.info("欄位：%s", fields)

    # 只取第一組「電腦議價點選成交」
    # 第二組才是「系統外議價成交」
    columns = {
        "date": find_column(fields, "日期"),
        "volume": find_column(fields, "成交股數", 0),
        "turnover": find_column(fields, "成交金額", 0),
        "high": find_column(fields, "成交最高", 0),
        "low": find_column(fields, "成交最低", 0),
        "average": find_column(fields, "成交均價", 0),
        "trades": find_column(fields, "筆數", 0),
    }

    logger.info("欄位索引：%s", columns)

    if any(value is None for value in columns.values()):
        raise RuntimeError(
            f"資料欄位不完整：{columns}"
        )

    results = []

    for row in rows:

        if not isinstance(row, (list, tuple)):
            continue

        required_index = max(columns.values())

        if len(row) <= required_index:
            continue

        date_value = parse_date(
            row[columns["date"]]
        )

        if not date_value:
            continue

        average = parse_number(
            row[columns["average"]]
        )

        # 沒有成交均價的日期不納入有效行情
        if average is None or average <= 0:
            continue

        item = {
            "date": date_value,
            "volume": parse_number(
                row[columns["volume"]]
            ),
            "turnover": parse_number(
                row[columns["turnover"]]
            ),
            "high": parse_number(
                row[columns["high"]]
            ),
            "low": parse_number(
                row[columns["low"]]
            ),
            "average": average,
            "trades": parse_number(
                row[columns["trades"]]
            ),
        }

        results.append(item)

    results.sort(key=lambda x: x["date"])

    if not results:
        raise RuntimeError(
            "成功取得 JSON，但沒有解析出有效成交資料"
        )

    return results


# ============================================================
# 7. 建立測試行情
# ============================================================

def build_test_data(rows):

    output_rows = []

    previous_average = None

    for row in rows:

        average = row["average"]

        change = None
        change_percent = None

        if previous_average is not None:

            change = round(
                average - previous_average,
                2
            )

            if previous_average != 0:

                change_percent = round(
                    change / previous_average * 100,
                    2
                )

        output_rows.append({
            "date": row["date"],

            # 興櫃沒有一般意義的收盤價。
            # 此欄位為相容既有 JSON 結構，
            # 實際代表電腦議價點選成交均價。
            "close": average,

            "change": change,
            "change_percent": change_percent,

            "volume": row["volume"],
            "turnover": row["turnover"],
            "high": row["high"],
            "low": row["low"],
            "average": average,
            "trades": row["trades"],
        })

        previous_average = average

    return output_rows[-5:]


# ============================================================
# 8. 與使用者提供的資料比對
# ============================================================

def compare_expected(rows):

    logger.info("=" * 65)
    logger.info("6750 興櫃行情資料比對")
    logger.info("=" * 65)

    passed = 0
    failed = 0

    actual_map = {
        row["date"]: row
        for row in rows
    }

    for date, expected in EXPECTED_DATA.items():

        actual = actual_map.get(date)

        if actual is None:

            logger.error(
                "%s：查無該日資料",
                date
            )

            failed += 1
            continue

        differences = []

        for field, expected_value in expected.items():

            actual_value = actual.get(field)

            if actual_value is None:
                differences.append(
                    f"{field}: 實際值為空"
                )
                continue

            if isinstance(expected_value, float):

                if abs(
                    float(actual_value) - expected_value
                ) > 0.001:

                    differences.append(
                        f"{field}: "
                        f"預期 {expected_value}，"
                        f"實際 {actual_value}"
                    )

            elif actual_value != expected_value:

                differences.append(
                    f"{field}: "
                    f"預期 {expected_value}，"
                    f"實際 {actual_value}"
                )

        if differences:

            logger.error(
                "%s：比對不一致",
                date
            )

            for difference in differences:
                logger.error("  %s", difference)

            failed += 1

        else:

            logger.info(
                "%s：比對成功，成交均價 %.2f",
                date,
                actual["average"]
            )

            passed += 1

    logger.info("-" * 65)
    logger.info("比對成功：%s 天", passed)
    logger.info("比對失敗：%s 天", failed)

    return passed, failed


# ============================================================
# 9. 主程式
# ============================================================

def main():

    logger.info("=" * 65)
    logger.info("興櫃歷史行情測試")
    logger.info("股票：%s %s", STOCK_ID, STOCK_NAME)
    logger.info("查詢月份：2026 年 11 月")
    logger.info("價格定義：電腦議價點選成交均價")
    logger.info("=" * 65)

    raw_text = fetch_esb_response()

    rows = parse_esb_data(raw_text)

    logger.info(
        "成功解析每日行情：%s 筆",
        len(rows)
    )

    test_rows = build_test_data(rows)

    passed, failed = compare_expected(rows)

    output = {
        "stock_id": STOCK_ID,
        "stock_name": STOCK_NAME,
        "market": "ESB",
        "price_definition": "電腦議價點選成交均價",
        "update_time": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "stock_count": 1,
        "days": len(test_rows),
        "comparison": {
            "passed": passed,
            "failed": failed,
        },
        "data": test_rows,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    logger.info("=" * 65)
    logger.info("測試完成")
    logger.info("原始回應：%s", RAW_FILE.name)
    logger.info("測試結果：%s", OUTPUT_FILE.name)
    logger.info("=" * 65)

    if failed > 0:
        raise RuntimeError(
            f"行情資料比對失敗：{failed} 天"
        )

    if passed != 5:
        raise RuntimeError(
            f"預期比對 5 天，實際成功 {passed} 天"
        )

    logger.info("全部五個交易日比對成功")


if __name__ == "__main__":
    main()
