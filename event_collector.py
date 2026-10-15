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

OUTPUT_FILE = BASE_DIR / "events.json"
CONFERENCE_FILE = BASE_DIR / "twse_conference_v13_result.json"

# ------------------------------------------------------------
# 測試模式
# ------------------------------------------------------------

TEST_MODE = True

TEST_STOCKS = [
    "1101",
    "1410",
    "2330",
    "2454",
    "2317",
]

# 重大訊息：保留最近幾天
LOOKBACK_DAYS = 30

# 法人說明會：
# 過去 + 未來
CONFERENCE_LOOKBACK_DAYS = 30
CONFERENCE_FORWARD_DAYS = 60

# 診斷模式
DIAGNOSTIC_MODE = True


# ============================================================
# 2. API
# ============================================================

TWSE_URL = (
    "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ============================================================
# 3. HTTP / JSON
# ============================================================

def get_json(url):
    """
    取得 JSON API。
    """

    print(f"\n取得資料：{url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError(
            f"API 回傳格式不是 list：{type(data)}"
        )

    print(f"取得資料筆數：{len(data)}")

    return data


# ============================================================
# 4. 欄位工具
# ============================================================

def normalize_key(value):
    """
    正規化欄位名稱。
    """

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        "",
        str(value),
    ).strip()


def normalize_record(record):
    """
    將 API record 的 key 做基本正規化。
    """

    if not isinstance(record, dict):
        return {}

    result = {}

    for key, value in record.items():
        normalized = normalize_key(key)
        result[normalized] = value

    return result


# ============================================================
# 5. 日期工具
# ============================================================

def roc_to_date(value):
    """
    將民國日期 / 西元日期轉成 YYYY-MM-DD。

    支援：
        1151012
        115/10/12
        115-10-12
        2026/10/12
        2026-10-12
        20261012
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # --------------------------------------------------------
    # YYYY-MM-DD / YYYY/MM/DD
    # --------------------------------------------------------

    match = re.match(
        r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$",
        text,
    )

    if match:
        year, month, day = map(
            int,
            match.groups(),
        )

        try:
            return datetime(
                year,
                month,
                day,
            ).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # --------------------------------------------------------
    # YYYYMMDD
    # --------------------------------------------------------

    match = re.match(
        r"^(\d{4})(\d{2})(\d{2})$",
        text,
    )

    if match:
        year, month, day = map(
            int,
            match.groups(),
        )

        try:
            return datetime(
                year,
                month,
                day,
            ).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # --------------------------------------------------------
    # 民國日期：YYYMMDD
    # --------------------------------------------------------

    match = re.match(
        r"^(\d{3})(\d{2})(\d{2})$",
        text,
    )

    if match:
        year, month, day = map(
            int,
            match.groups(),
        )

        year += 1911

        try:
            return datetime(
                year,
                month,
                day,
            ).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # --------------------------------------------------------
    # 民國日期：YYY/MM/DD
    # --------------------------------------------------------

    match = re.match(
        r"^(\d{3})[/-](\d{1,2})[/-](\d{1,2})$",
        text,
    )

    if match:
        year, month, day = map(
            int,
            match.groups(),
        )

        year += 1911

        try:
            return datetime(
                year,
                month,
                day,
            ).strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


# ============================================================
# 6. 重大訊息欄位解析
# ============================================================

def get_stock_code(record):
    candidates = [
        "公司代號",
        "證券代號",
        "股票代號",
        "公司碼",
        "代號",
    ]

    for key in candidates:
        value = record.get(key)

        if value is None:
            continue

        text = str(value).strip()

        if text:
            match = re.search(
                r"\d{4,6}",
                text,
            )

            if match:
                return match.group(0)

    return ""


def get_event_date(record):
    candidates = [
        "發言日期",
        "出表日期",
        "事實發生日",
        "日期",
        "公告日期",
    ]

    for key in candidates:
        value = record.get(key)

        result = roc_to_date(value)

        if result:
            return result

    return ""


def get_event_time(record):
    candidates = [
        "發言時間",
        "公告時間",
        "時間",
    ]

    for key in candidates:
        value = record.get(key)

        if value is None:
            continue

        text = str(value).strip()

        if text:
            return text

    return ""


def get_title(record):
    candidates = [
        "主旨",
        "標題",
        "公告主旨",
        "訊息主旨",
    ]

    for key in candidates:
        value = record.get(key)

        if value is None:
            continue

        text = str(value).strip()

        if text:
            return text

    return ""


def get_company_name(record):
    candidates = [
        "公司名稱",
        "公司簡稱",
        "證券名稱",
        "股票名稱",
    ]

    for key in candidates:
        value = record.get(key)

        if value is None:
            continue

        text = str(value).strip()

        if text:
            return text

    return ""


# ============================================================
# 7. 重大訊息分類
# ============================================================

def classify_event(title):
    """
    重大訊息分類。

    法人說明會不在這裡分類。
    法人說明會由 v13 資料直接指定：
        法人說明會
    """

    text = title or ""

    if any(
        keyword in text
        for keyword in [
            "法人說明會",
            "法說會",
            "法人說明",
        ]
    ):
        return "法人說明會"

    if any(
        keyword in text
        for keyword in [
            "增資",
            "減資",
            "現金增資",
            "私募",
        ]
    ):
        return "增減資"

    if any(
        keyword in text
        for keyword in [
            "庫藏股",
            "買回本公司股份",
        ]
    ):
        return "庫藏股"

    if any(
        keyword in text
        for keyword in [
            "董監",
            "董事",
            "監察人",
            "大股東",
            "持股",
        ]
    ):
        return "董監/大股東異動"

    if any(
        keyword in text
        for keyword in [
            "可轉債",
            "轉換公司債",
        ]
    ):
        return "可轉債"

    if any(
        keyword in text
        for keyword in [
            "投資",
            "併購",
            "合併",
            "收購",
        ]
    ):
        return "重大投資/併購"

    if any(
        keyword in text
        for keyword in [
            "股利",
            "除權",
            "除息",
            "配息",
        ]
    ):
        return "股利/除權息"

    if any(
        keyword in text
        for keyword in [
            "財報",
            "財務",
            "營收",
            "獲利",
        ]
    ):
        return "財報/財務"

    return "其他"


# ============================================================
# 8. 重大訊息轉換
# ============================================================

def convert_record(record, source):
    """
    將 TWSE 重大訊息轉成統一事件格式。
    """

    record = normalize_record(record)

    stock_id = get_stock_code(record)

    if not stock_id:
        return None

    company_name = get_company_name(record)
    date = get_event_date(record)
    event_time = get_event_time(record)
    title = get_title(record)

    if not date:
        return None

    return {
        "stock_id": stock_id,
        "company_name": company_name,
        "date": date,
        "time": event_time,
        "category": classify_event(title),
        "title": title,
        "source": source,
        "source_url": (
            "https://openapi.twse.com.tw/"
            "v1/opendata/t187ap04_L"
        ),
    }


# ============================================================
# 9. v13 法人說明會
# ============================================================

def extract_year_from_title(event_title):
    """
    從 v13 event_title 取得年份。

    例如：
        2026年上市公司辦理法人說明會(10月1日至10月31日)

    回傳：
        2026
    """

    if not event_title:
        return None

    match = re.search(
        r"(20\d{2})年",
        str(event_title),
    )

    if match:
        return int(match.group(1))

    return None


def normalize_conference_date(
    date_value,
    event_title,
):
    """
    將 v13 的 MM-DD 轉成 YYYY-MM-DD。

    年份優先從 event_title 取得。
    """

    if not date_value:
        return None

    text = str(date_value).strip()

    # 已經是完整日期
    normalized = roc_to_date(text)

    if normalized:
        return normalized

    # MM-DD
    match = re.match(
        r"^(\d{1,2})-(\d{1,2})$",
        text,
    )

    if not match:
        return None

    month = int(match.group(1))
    day = int(match.group(2))

    year = extract_year_from_title(
        event_title
    )

    if year is None:
        return None

    try:
        return datetime(
            year,
            month,
            day,
        ).strftime("%Y-%m-%d")

    except ValueError:
        return None


def load_conference_events(target_stocks):
    """
    讀取 v13：

        twse_conference_v13_result.json

    並轉成統一事件格式。
    """

    print("\n" + "=" * 72)
    print("讀取法人說明會 v13 資料")
    print("=" * 72)

    if not CONFERENCE_FILE.exists():
        print(
            f"找不到法人說明會資料："
            f"{CONFERENCE_FILE}"
        )
        return []

    try:
        with open(
            CONFERENCE_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

    except Exception as exc:
        print(
            f"讀取法人說明會 JSON 失敗：{exc}"
        )
        return []

    events = data.get("events", [])

    if not isinstance(events, list):
        print("v13 JSON 的 events 不是 list")
        return []

    result = []

    total_sessions = 0
    matched_sessions = 0
    skipped_no_code = 0
    skipped_no_date = 0
    skipped_bad_date = 0

    for event in events:

        if not isinstance(event, dict):
            continue

        event_title = event.get(
            "event_title",
            "",
        )

        event_id = event.get(
            "event_id",
            "",
        )

        source_format = event.get(
            "source_format",
            "",
        )

        sessions = event.get(
            "sessions",
            [],
        )

        if not isinstance(sessions, list):
            continue

        for session in sessions:

            if not isinstance(session, dict):
                continue

            total_sessions += 1

            stock_id = str(
                session.get(
                    "stock_code",
                    "",
                )
            ).strip()

            if not stock_id:
                skipped_no_code += 1
                continue

            if stock_id not in target_stocks:
                continue

            matched_sessions += 1

            company_name = str(
                session.get(
                    "company_name",
                    "",
                )
            ).strip()

            raw_date = session.get(
                "date",
                "",
            )

            normalized_date = (
                normalize_conference_date(
                    raw_date,
                    event_title,
                )
            )

            if not raw_date:
                skipped_no_date += 1
                print(
                    f"[法人說明會] "
                    f"{stock_id} 缺少日期"
                )
                continue

            if not normalized_date:
                skipped_bad_date += 1

                print(
                    f"[法人說明會] "
                    f"{stock_id} 日期無法解析："
                    f"{raw_date} / "
                    f"{event_title}"
                )

                continue

            event_time = str(
                session.get(
                    "time",
                    "",
                )
            ).strip()

            venue = str(
                session.get(
                    "venue",
                    "",
                )
            ).strip()

            status = str(
                session.get(
                    "status",
                    "",
                )
            ).strip()

            cancelled = bool(
                session.get(
                    "cancelled",
                    False,
                )
            )

            # ------------------------------------------------
            # 若 v13 已明確標示取消，
            # 優先保留 cancelled 狀態。
            # ------------------------------------------------

            if cancelled:
                status = "cancelled"

            if not status:
                status = (
                    "cancelled"
                    if cancelled
                    else "scheduled"
                )

            result.append(
                {
                    "stock_id": stock_id,
                    "company_name": company_name,
                    "date": normalized_date,
                    "time": event_time,
                    "category": "法人說明會",
                    "title": event_title,
                    "venue": venue,
                    "status": status,
                    "cancelled": cancelled,
                    "source": "TWSE",
                    "source_event_id": event_id,
                    "source_format": source_format,
                }
            )

    print(
        f"v13 活動數：{len(events)}"
    )

    print(
        f"v13 場次總數：{total_sessions}"
    )

    print(
        f"符合測試股票場次：{matched_sessions}"
    )

    print(
        f"無股票代號：{skipped_no_code}"
    )

    print(
        f"無日期：{skipped_no_date}"
    )

    print(
        f"日期無法解析：{skipped_bad_date}"
    )

    print(
        f"成功轉換法人說明會：{len(result)}"
    )
print()
print("法人說明會轉換結果：")
for event in conference_events:
    print(
        f"  {event.get('stock_id')} | "
        f"{event.get('company_name')} | "
        f"{event.get('date')} | "
        f"{event.get('time')} | "
        f"status={event.get('status')} | "
        f"cancelled={event.get('cancelled')}"
    )
    
    return result


# ============================================================
# 10. 測試股票
# ============================================================

def get_target_stocks():
    """
    取得本次要處理的股票。
    """

    if TEST_MODE:
        return TEST_STOCKS.copy()

    # --------------------------------------------------------
    # 正式模式目前仍保留原有邏輯：
    # 優先 stocks.json，再 analysis.json
    # --------------------------------------------------------

    stocks_file = BASE_DIR / "stocks.json"

    if stocks_file.exists():

        try:
            with open(
                stocks_file,
                "r",
                encoding="utf-8",
            ) as f:
                data = json.load(f)

            if isinstance(data, list):

                result = []

                for item in data:

                    if isinstance(item, str):
                        code = item.strip()

                    elif isinstance(item, dict):
                        code = str(
                            item.get(
                                "stock_id",
                                item.get(
                                    "代號",
                                    "",
                                ),
                            )
                        ).strip()

                    else:
                        continue

                    if code:
                        result.append(code)

                if result:
                    return result

        except Exception as exc:
            print(
                f"讀取 stocks.json 失敗：{exc}"
            )

    analysis_file = BASE_DIR / "analysis.json"

    if analysis_file.exists():

        try:
            with open(
                analysis_file,
                "r",
                encoding="utf-8",
            ) as f:
                data = json.load(f)

            stocks = data.get(
                "stocks",
                [],
            )

            result = []

            for item in stocks:

                if not isinstance(item, dict):
                    continue

                code = str(
                    item.get(
                        "stock_id",
                        "",
                    )
                ).strip()

                if code:
                    result.append(code)

            return result

        except Exception as exc:
            print(
                f"讀取 analysis.json 失敗：{exc}"
            )

    return []


# ============================================================
# 11. 去重
# ============================================================

def deduplicate_events(events):
    """
    去除完全相同事件。

    注意：
    第一版不做過度的跨來源智慧合併。
    """

    seen = set()
    result = []

    for event in events:

        key = (
            event.get("stock_id", ""),
            event.get("date", ""),
            event.get("time", ""),
            event.get("category", ""),
            event.get("title", ""),
            event.get("venue", ""),
            event.get("source", ""),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(event)

    return result


# ============================================================
# 12. 日期範圍
# ============================================================

def filter_recent_events(events):
    """
    重大訊息：
        過去 LOOKBACK_DAYS 天

    法人說明會：
        過去 CONFERENCE_LOOKBACK_DAYS 天
        到未來 CONFERENCE_FORWARD_DAYS 天
    """

    today = datetime.now().date()

    message_start = (
        today
        - timedelta(days=LOOKBACK_DAYS)
    )

    conference_start = (
        today
        - timedelta(
            days=CONFERENCE_LOOKBACK_DAYS
        )
    )

    conference_end = (
        today
        + timedelta(
            days=CONFERENCE_FORWARD_DAYS
        )
    )

    result = []

    for event in events:

        date_text = event.get(
            "date",
            "",
        )

        try:
            event_date = datetime.strptime(
                date_text,
                "%Y-%m-%d",
            ).date()

        except Exception:
            continue

        category = event.get(
            "category",
            "",
        )

        if category == "法人說明會":

            if (
                conference_start
                <= event_date
                <= conference_end
            ):
                result.append(event)

        else:

            if (
                message_start
                <= event_date
                <= today
            ):
                result.append(event)

    return result


# ============================================================
# 13. 排序
# ============================================================

def sort_events(events):
    """
    最新日期優先。

    法人說明會與重大訊息統一依日期排序。
    """

    def sort_key(event):

        date_text = event.get(
            "date",
            "",
        )

        time_text = event.get(
            "time",
            "",
        )

        return (
            date_text,
            time_text,
            event.get(
                "stock_id",
                "",
            ),
        )

    return sorted(
        events,
        key=sort_key,
        reverse=True,
    )


# ============================================================
# 14. 診斷輸出
# ============================================================

def diagnostic_dump(
    records,
    source,
):
    """
    顯示 API 基本診斷資訊。
    """

    if not DIAGNOSTIC_MODE:
        return

    print("\n" + "-" * 72)
    print(f"{source} API 診斷")
    print("-" * 72)

    print(
        f"原始資料筆數：{len(records)}"
    )

    stock_counter = {}

    for record in records:

        normalized = normalize_record(
            record
        )

        stock_id = get_stock_code(
            normalized
        )

        if not stock_id:
            continue

        stock_counter[stock_id] = (
            stock_counter.get(
                stock_id,
                0,
            )
            + 1
        )

    for stock_id in TEST_STOCKS:

        print(
            f"{stock_id}："
            f"{stock_counter.get(stock_id, 0)} 筆"
        )


# ============================================================
# 15. 統計
# ============================================================

def print_event_statistics(events):
    """
    顯示最後事件統計。
    """

    print("\n" + "=" * 72)
    print("事件統計")
    print("=" * 72)

    total = len(events)

    print(
        f"事件總數：{total}"
    )

    category_counter = {}

    stock_counter = {}

    source_counter = {}

    for event in events:

        category = event.get(
            "category",
            "",
        )

        stock_id = event.get(
            "stock_id",
            "",
        )

        source = event.get(
            "source",
            "",
        )

        category_counter[category] = (
            category_counter.get(
                category,
                0,
            )
            + 1
        )

        stock_counter[stock_id] = (
            stock_counter.get(
                stock_id,
                0,
            )
            + 1
        )

        source_counter[source] = (
            source_counter.get(
                source,
                0,
            )
            + 1
        )

    print("\n依來源：")

    for source, count in sorted(
        source_counter.items()
    ):
        print(
            f"  {source}: {count}"
        )

    print("\n依類別：")

    for category, count in sorted(
        category_counter.items()
    ):
        print(
            f"  {category}: {count}"
        )

    print("\n依股票：")

    for stock_id in TEST_STOCKS:

        print(
            f"  {stock_id}: "
            f"{stock_counter.get(stock_id, 0)}"
        )


# ============================================================
# 16. 輸出 events.json
# ============================================================

def save_events(events):
    """
    輸出 events.json。
    """

    output = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "stock_count": len(
            set(
                event.get(
                    "stock_id",
                    "",
                )
                for event in events
            )
        ),
        "event_count": len(events),
        "events": events,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"\n已輸出：{OUTPUT_FILE}"
    )


# ============================================================
# 17. 主流程
# ============================================================

def main():

    print("=" * 72)
    print("台股事件資料收集器")
    print("=" * 72)

    print(
        f"TEST_MODE：{TEST_MODE}"
    )

    print(
        f"測試股票：{', '.join(TEST_STOCKS)}"
    )

    target_stocks = set(
        get_target_stocks()
    )

    if not target_stocks:
        print("沒有可處理股票。")
        return

    print(
        f"\n實際處理股票數："
        f"{len(target_stocks)}"
    )

    # ========================================================
    # A. TWSE 重大訊息
    # ========================================================

    print("\n" + "=" * 72)
    print("取得 TWSE 重大訊息")
    print("=" * 72)

    message_events = []

    try:

        twse_records = get_json(
            TWSE_URL
        )

        diagnostic_dump(
            twse_records,
            "TWSE 重大訊息",
        )

        for record in twse_records:

            normalized = normalize_record(
                record
            )

            stock_id = get_stock_code(
                normalized
            )

            if stock_id not in target_stocks:
                continue

            event = convert_record(
                normalized,
                "TWSE",
            )

            if event:
                message_events.append(
                    event
                )

    except Exception as exc:

        print(
            f"TWSE 重大訊息取得失敗："
            f"{exc}"
        )

    print(
        f"\n符合測試股票的重大訊息："
        f"{len(message_events)}"
    )

    # --------------------------------------------------------
    # API 請求間隔
    # --------------------------------------------------------

    time.sleep(1)

    # ========================================================
    # B. 法人說明會
    # ========================================================

    conference_events = (
        load_conference_events(
            target_stocks
        )
    )

    # ========================================================
    # C. 合併
    # ========================================================

    all_events = (
        message_events
        + conference_events
    )

    print("\n" + "=" * 72)
    print("合併事件")
    print("=" * 72)

    print(
        f"重大訊息："
        f"{len(message_events)}"
    )

    print(
        f"法人說明會："
        f"{len(conference_events)}"
    )

    print(
        f"合併前："
        f"{len(all_events)}"
    )

    # ========================================================
    # D. 去重
    # ========================================================

    all_events = deduplicate_events(
        all_events
    )

    print(
        f"去重後："
        f"{len(all_events)}"
    )

    # ========================================================
    # E. 日期篩選
    # ========================================================

    all_events = filter_recent_events(
        all_events
    )

    print(
        f"日期篩選後："
        f"{len(all_events)}"
    )

    # ========================================================
    # F. 排序
    # ========================================================

    all_events = sort_events(
        all_events
    )

    # ========================================================
    # G. 統計
    # ========================================================

    print_event_statistics(
        all_events
    )

    # ========================================================
    # H. 輸出
    # ========================================================

    save_events(
        all_events
    )

    print("\n" + "=" * 72)
    print("完成")
    print("=" * 72)


# ============================================================
# 18. Entry Point
# ============================================================

if __name__ == "__main__":
    main()
