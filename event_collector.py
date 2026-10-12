import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

ANALYSIS_FILE = BASE_DIR / "analysis.json"
OUTPUT_FILE = BASE_DIR / "events.json"

# ------------------------------------------------------------
# 第一次測試只抓這 4 檔
# ------------------------------------------------------------
TEST_STOCKS = [
    "1101",
    "2330",
    "2454",
    "2317",
]

# True：只測試上面 4 檔
# False：讀取 analysis.json 的全部股票
TEST_MODE = True

# ------------------------------------------------------------
# 事件保留天數
# ------------------------------------------------------------
DAYS_BACK = 30

# ------------------------------------------------------------
# API 請求間隔
# ------------------------------------------------------------
REQUEST_DELAY = 1.5

# ============================================================
# 官方 OpenAPI
# ============================================================

TWSE_API = (
    "https://openapi.twse.com.tw/v1/opendata/"
    "t187ap04_L"
)

TPEX_API = (
    "https://www.tpex.org.tw/openapi/v1/"
    "mopsfin_t187ap04_O"
)

# ============================================================
# MOPS 官方頁面
# 僅作為來源連結，不直接爬 ajax_t05st01
# ============================================================

MOPS_PAGE_URL = (
    "https://mops.twse.com.tw/mops/web/t05st01"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 2. 共用工具
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    text = str(value)

    text = (
        text
        .replace("\xa0", " ")
        .replace("\u3000", " ")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_stock_id(value):
    if value is None:
        return ""

    text = clean_text(value)

    match = re.search(r"\d{4,6}", text)

    if not match:
        return ""

    return match.group(0)


def parse_date(value):
    """
    支援：

    2026/10/12
    2026-10-12
    115/10/12
    1151012
    20261012
    """

    if value is None:
        return None

    text = clean_text(value)

    if not text:
        return None

    # --------------------------------------------------------
    # YYYY/MM/DD
    # YYYY-MM-DD
    # --------------------------------------------------------

    match = re.search(
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
        text
    )

    if match:
        try:
            return datetime(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3))
            ).date()
        except ValueError:
            return None

    # --------------------------------------------------------
    # 民國年
    # YY/MM/DD
    # YYY/MM/DD
    # --------------------------------------------------------

    match = re.search(
        r"(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})",
        text
    )

    if match:
        try:
            return datetime(
                int(match.group(1)) + 1911,
                int(match.group(2)),
                int(match.group(3))
            ).date()
        except ValueError:
            return None

    # --------------------------------------------------------
    # YYYYMMDD / YYYMMDD
    # --------------------------------------------------------

    digits = re.sub(r"\D", "", text)

    if len(digits) == 8:
        try:
            return datetime.strptime(
                digits,
                "%Y%m%d"
            ).date()
        except ValueError:
            pass

    if len(digits) == 7:
        try:
            year = int(digits[:3]) + 1911
            month = int(digits[3:5])
            day = int(digits[5:7])

            return datetime(
                year,
                month,
                day
            ).date()

        except ValueError:
            pass

    return None


def date_to_string(value):
    if isinstance(value, datetime):
        return value.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    return str(value)


# ============================================================
# 3. 事件分類
# ============================================================

def classify_event(title):

    text = clean_text(title)

    # --------------------------------------------------------
    # 法人說明會
    # --------------------------------------------------------

    if any(keyword in text for keyword in [
        "法人說明會",
        "法說會",
        "投資人說明會",
        "線上法人說明會",
        "召開法人說明會",
        "受邀參加法人說明會",
    ]):
        return "法人說明會"

    # --------------------------------------------------------
    # 庫藏股
    # --------------------------------------------------------

    if any(keyword in text for keyword in [
        "庫藏股",
        "買回本公司股份",
        "買回股份",
        "註銷庫藏股",
    ]):
        return "庫藏股"

    # --------------------------------------------------------
    # 董監 / 大股東
    # --------------------------------------------------------

    if any(keyword in text for keyword in [
        "董事長",
        "董事",
        "獨立董事",
        "監察人",
        "總經理",
        "經理人",
        "大股東",
        "持股",
        "質押",
        "設質",
        "轉讓",
    ]):
        return "董監／大股東異動"

    # --------------------------------------------------------
    # 可轉債 / 公司債
    # --------------------------------------------------------

    if any(keyword in text for keyword in [
        "可轉換公司債",
        "可轉債",
        "轉換公司債",
        "公司債",
    ]):
        return "可轉債"

    # --------------------------------------------------------
    # 增資 / 減資
    # --------------------------------------------------------

    if any(keyword in text for keyword in [
        "現金增資",
        "增資",
        "減資",
        "發行新股",
        "盈餘轉增資",
        "資本公積轉增資",
    ]):
        return "增資／減資"

    # --------------------------------------------------------
    # 重大投資 / 併購
    # --------------------------------------------------------

    if any(keyword in text for keyword in [
        "取得資產",
        "處分資產",
        "取得股份",
        "處分股份",
        "重大投資",
        "投資計畫",
        "併購",
        "合併",
        "收購",
    ]):
        return "重大投資／併購"

    # --------------------------------------------------------
    # 股利 / 除權息
    # --------------------------------------------------------

    if any(keyword in text for keyword in [
        "股利",
        "股息",
        "現金股利",
        "股票股利",
        "除權",
        "除息",
    ]):
        return "股利／除權息"

    # --------------------------------------------------------
    # 股東會
    # --------------------------------------------------------

    if any(keyword in text for keyword in [
        "股東常會",
        "股東臨時會",
        "股東會",
    ]):
        return "股東會"

    # --------------------------------------------------------
    # 財報
    # --------------------------------------------------------

    if any(keyword in text for keyword in [
        "財務報告",
        "財報",
        "財務預測",
        "自結",
        "營收",
        "損益",
    ]):
        return "財報／營運"

    # --------------------------------------------------------
    # 其他重大訊息
    # --------------------------------------------------------

    return "重大訊息"


# ============================================================
# 4. 取得 API 資料
# ============================================================

def fetch_api(url, source_name):

    print(f"    查詢：{source_name}")

    try:

        response = session.get(
            url,
            timeout=30
        )

        print(
            f"    HTTP 狀態碼："
            f"{response.status_code}"
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):

            print(
                "    [WARN] API 回傳格式不是陣列"
            )

            return []

        print(
            f"    API 回傳：{len(data)} 筆"
        )

        return data

    except requests.RequestException as error:

        print(
            f"    [ERROR] API 請求失敗：{error}"
        )

        return []

    except ValueError as error:

        print(
            f"    [ERROR] JSON 解析失敗：{error}"
        )

        return []


# ============================================================
# 5. 找股票代碼欄位
# ============================================================

def get_stock_code(row):

    possible_keys = [
        "公司代號",
        "公司代碼",
        "證券代號",
        "股票代號",
        "Code",
        "code",
    ]

    for key in possible_keys:

        if key in row:

            code = normalize_stock_id(
                row.get(key)
            )

            if code:
                return code

    return ""


# ============================================================
# 6. 找日期欄位
# ============================================================

def get_event_date(row):

    possible_keys = [
        "發言日期",
        "公告日期",
        "日期",
        "發言日",
        "Date",
        "date",
    ]

    for key in possible_keys:

        if key not in row:
            continue

        raw = row.get(key)

        parsed = parse_date(raw)

        if parsed:
            return parsed

    return None


# ============================================================
# 7. 找時間欄位
# ============================================================

def get_event_time(row):

    possible_keys = [
        "發言時間",
        "公告時間",
        "時間",
        "Time",
        "time",
    ]

    for key in possible_keys:

        if key not in row:
            continue

        value = clean_text(
            row.get(key)
        )

        if value:
            return value

    return ""


# ============================================================
# 8. 找公告主旨
# ============================================================

def get_event_title(row):

    possible_keys = [
        "主旨",
        "公告主旨",
        "標題",
        "Title",
        "title",
        "subject",
    ]

    for key in possible_keys:

        if key not in row:
            continue

        value = clean_text(
            row.get(key)
        )

        if value:
            return value

    return ""


# ============================================================
# 9. 取得公司名稱
# ============================================================

def get_company_name(row):

    possible_keys = [
        "公司名稱",
        "公司簡稱",
        "名稱",
        "CompanyName",
        "company_name",
    ]

    for key in possible_keys:

        if key in row:

            value = clean_text(
                row.get(key)
            )

            if value:
                return value

    return ""


# ============================================================
# 10. 轉換 API 公告
# ============================================================

def convert_api_record(
    row,
    expected_stock_ids,
    source_name
):

    if not isinstance(row, dict):
        return None

    stock_id = get_stock_code(row)

    if not stock_id:
        return None

    if stock_id not in expected_stock_ids:
        return None

    event_date = get_event_date(row)

    if event_date is None:
        return None

    title = get_event_title(row)

    if not title:
        return None

    event_time = get_event_time(row)

    company_name = get_company_name(row)

    category = classify_event(title)

    if event_time:

        date_text = (
            event_date.strftime("%Y-%m-%d")
            + " "
            + event_time
        )

    else:

        date_text = event_date.strftime(
            "%Y-%m-%d"
        )

    # --------------------------------------------------------
    # MOPS 官方查詢頁
    # --------------------------------------------------------

    source_url = MOPS_PAGE_URL

    return {
        "stock_id": stock_id,
        "company_name": company_name,
        "date": date_text,
        "category": category,
        "title": title,
        "source": source_name,
        "source_url": source_url,
    }


# ============================================================
# 11. 讀取股票清單
# ============================================================

def load_stock_ids():

    if TEST_MODE:

        print(
            "目前為 TEST_MODE，只測試："
            + ", ".join(TEST_STOCKS)
        )

        return TEST_STOCKS

    if not ANALYSIS_FILE.exists():

        raise FileNotFoundError(
            f"找不到：{ANALYSIS_FILE}"
        )

    with ANALYSIS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if isinstance(data, dict):

        stocks = data.get(
            "stocks",
            []
        )

    elif isinstance(data, list):

        stocks = data

    else:

        stocks = []

    result = []

    for stock in stocks:

        if not isinstance(stock, dict):
            continue

        stock_id = normalize_stock_id(
            stock.get("stock_id")
        )

        if stock_id:
            result.append(stock_id)

    return list(
        dict.fromkeys(result)
    )


# ============================================================
# 12. 過濾最近事件
# ============================================================

def filter_recent_events(events):

    today = datetime.now().date()

    start_date = (
        today
        - timedelta(days=DAYS_BACK)
    )

    result = []

    for event in events:

        event_date = parse_date(
            event.get("date")
        )

        if event_date is None:
            continue

        if start_date <= event_date <= today:

            result.append(event)

    return result


# ============================================================
# 13. 去除重複
# ============================================================

def deduplicate_events(events):

    result = []
    seen = set()

    for event in events:

        key = (
            event.get("stock_id", ""),
            event.get("date", ""),
            event.get("title", ""),
        )

        if key in seen:
            continue

        seen.add(key)

        result.append(event)

    return result


# ============================================================
# 14. 輸出 events.json
# ============================================================

def save_events(events):

    events.sort(
        key=lambda item: (
            item.get("stock_id", ""),
            item.get("date", ""),
        ),
        reverse=True
    )

    output = {
        "update_time": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "source": (
            "TWSE / TPEx 官方 OpenAPI"
        ),
        "days_back": DAYS_BACK,
        "event_count": len(events),
        "events": events,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print(
        f"已產生：{OUTPUT_FILE}"
    )

    print(
        f"事件數量：{len(events)}"
    )


# ============================================================
# 15. 主程式
# ============================================================

def main():

    print("=" * 60)
    print("台股事件／消息面資料收集器")
    print("=" * 60)

    print(
        "主要資料來源："
        "TWSE / TPEx 官方 OpenAPI"
    )

    print(
        "MOPS 僅保留為官方來源連結"
    )

    print("=" * 60)

    stock_ids = load_stock_ids()

    expected_stock_ids = set(
        stock_ids
    )

    print(
        f"準備處理 {len(stock_ids)} 檔股票"
    )

    # ========================================================
    # 1. TWSE
    # ========================================================

    twse_rows = fetch_api(
        TWSE_API,
        "TWSE 上市重大訊息"
    )

    # ========================================================
    # 2. TPEx
    # ========================================================

    time.sleep(
        REQUEST_DELAY
    )

    tpex_rows = fetch_api(
        TPEX_API,
        "TPEx 上櫃重大訊息"
    )

    # ========================================================
    # 3. 轉換資料
    # ========================================================

    all_events = []

    for row in twse_rows:

        event = convert_api_record(
            row,
            expected_stock_ids,
            "TWSE 上市重大訊息"
        )

        if event:
            all_events.append(event)

    for row in tpex_rows:

        event = convert_api_record(
            row,
            expected_stock_ids,
            "TPEx 上櫃重大訊息"
        )

        if event:
            all_events.append(event)

    print()
    print(
        f"符合測試股票的原始事件："
        f"{len(all_events)} 筆"
    )

    # ========================================================
    # 4. 去重
    # ========================================================

    all_events = deduplicate_events(
        all_events
    )

    print(
        f"去除重複後："
        f"{len(all_events)} 筆"
    )

    # ========================================================
    # 5. 日期篩選
    # ========================================================

    recent_events = filter_recent_events(
        all_events
    )

    print(
        f"最近 {DAYS_BACK} 天："
        f"{len(recent_events)} 筆"
    )

    # ========================================================
    # 6. 顯示測試結果
    # ========================================================

    print()

    for event in recent_events[:20]:

        print(
            f"[{event['stock_id']}] "
            f"{event['date']} "
            f"{event['category']} "
            f"{event['title']}"
        )

    # ========================================================
    # 7. 輸出
    # ========================================================

    save_events(
        recent_events
    )

    print()
    print("=" * 60)
    print("事件資料收集完成")
    print("=" * 60)


# ============================================================
# 16. 程式入口
# ============================================================

if __name__ == "__main__":
    main()
