import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

EVENTS_FILE = BASE_DIR / "events.json"
CONFERENCE_FILE = BASE_DIR / "twse_conference_v13_result.json"

TWSE_MAJOR_NEWS_URL = (
    "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
)

TEST_STOCKS = {
    "1101",
    "1410",
    "2330",
    "2454",
    "2317",
}

LOOKBACK_DAYS = 30
CONFERENCE_LOOKBACK_DAYS = 30
CONFERENCE_FORWARD_DAYS = 60

# 與事件收集器的日期基準一致：台灣日期
try:
    from zoneinfo import ZoneInfo

    TODAY = datetime.now(ZoneInfo("Asia/Taipei")).date()
except Exception:
    TODAY = date.today()

DATE_START = TODAY - timedelta(days=LOOKBACK_DAYS)
CONFERENCE_DATE_START = (
    TODAY - timedelta(days=CONFERENCE_LOOKBACK_DAYS)
)
CONFERENCE_DATE_END = (
    TODAY + timedelta(days=CONFERENCE_FORWARD_DAYS)
)

# 診斷輸出
ERRORS = []
WARNINGS = []
CHECK_COUNT = 0


# ============================================================
# 2. 共用驗證工具
# ============================================================

def report(condition, message):
    global CHECK_COUNT

    CHECK_COUNT += 1

    if condition:
        print(f"[PASS] {message}")
    else:
        print(f"[FAIL] {message}")
        ERRORS.append(message)


def warn(message):
    print(f"[WARN] {message}")
    WARNINGS.append(message)


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"找不到檔案：{path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_text(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        "",
        str(value).strip(),
    )


def normalize_stock_id(value):
    if value is None:
        return ""

    value = str(value).strip()

    # 保留股票代號字串，避免前導零消失
    if value.endswith(".0"):
        value = value[:-2]

    return value


def parse_date(value):
    """解析常見西元及民國日期格式。"""

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # YYYY-MM-DD、YYYY/MM/DD、YYYYMMDD
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    # 民國日期：115/10/14、115年10月14日
    roc_match = re.search(
        r"(?<!\d)(\d{2,3})\s*[年/-]\s*"
        r"(\d{1,2})\s*[月/-]\s*"
        r"(\d{1,2})",
        text,
    )

    if roc_match:
        year, month, day = map(
            int,
            roc_match.groups(),
        )

        try:
            return date(year + 1911, month, day)
        except ValueError:
            return None

    return None


def parse_conference_date(event_title, session_date):
    """由 v13 活動標題的西元年份還原 MM-DD 日期。"""

    if not session_date:
        return None

    text = str(session_date).strip()

    # 優先處理完整日期
    full_date = parse_date(text)

    if full_date:
        return full_date

    year_match = re.search(
        r"(20\d{2})年",
        str(event_title or ""),
    )

    if not year_match:
        return None

    year = int(year_match.group(1))

    match = re.search(
        r"(\d{1,2})\s*月\s*(\d{1,2})\s*日?",
        text,
    )

    if not match:
        match = re.fullmatch(
            r"\s*(\d{1,2})[-/](\d{1,2})\s*",
            text,
        )

    if not match:
        return None

    month, day = map(int, match.groups())

    try:
        return date(year, month, day)
    except ValueError:
        return None


def load_event_files():
    events_data = load_json(EVENTS_FILE)
    conference_data = load_json(CONFERENCE_FILE)

    if not isinstance(events_data, dict):
        raise ValueError("events.json 頂層不是物件")

    if not isinstance(events_data.get("events"), list):
        raise ValueError("events.json 缺少 events 陣列")

    # v13 目前主要場次位於 events[*].sessions[*]
    conference_events = conference_data.get("events")

    if not isinstance(conference_events, list):
        # 相容 v13 輸出使用 all_events 的情況
        conference_events = conference_data.get("all_events")

    if not isinstance(conference_events, list):
        raise ValueError(
            "v13 JSON 找不到 events 或 all_events 陣列"
        )

    return events_data["events"], conference_events


# ============================================================
# 3. 法人說明會來源比對
# ============================================================

def build_conference_source_index(conference_events):
    """
    將 v13 場次整理成可比對索引。
    不修改原始 JSON。
    """

    index = {}

    for activity in conference_events:
        if not isinstance(activity, dict):
            continue

        activity_title = activity.get("event_title")

        if not activity_title:
            activity_title = activity.get("title", "")

        sessions = activity.get("sessions", [])

        if not isinstance(sessions, list):
            continue

        for session in sessions:
            if not isinstance(session, dict):
                continue

            stock_id = normalize_stock_id(
                session.get("stock_code")
            )

            session_date = parse_conference_date(
                activity_title,
                session.get("date"),
            )

            if not stock_id or not session_date:
                continue

            key = (stock_id, session_date.isoformat())

            index.setdefault(key, []).append(
                {
                    "session": session,
                    "activity": activity,
                }
            )

    return index


def validate_conference_event(event, index, number):
    stock_id = normalize_stock_id(event.get("stock_id"))
    event_date = parse_date(event.get("date"))

    if not stock_id or not event_date:
        report(
            False,
            f"法人說明會 #{number} 缺少有效股票代號或日期",
        )
        return

    key = (stock_id, event_date.isoformat())
    candidates = index.get(key, [])

    if not candidates:
        report(
            False,
            f"法人說明會 #{number} "
            f"{stock_id} {event_date} 在 v13 找不到對應場次",
        )
        return

    # 先以股票與日期找出候選，再比對時間、公司名稱及場地。
    event_time = normalize_text(event.get("time"))
    event_company = normalize_text(event.get("company_name"))
    event_venue = normalize_text(event.get("venue"))

    matched = None

    for candidate in candidates:
        session = candidate["session"]

        source_time = normalize_text(session.get("time"))
        source_company = normalize_text(
            session.get("company_name")
        )
        source_venue = normalize_text(session.get("venue"))

        time_match = (
            not event_time
            or not source_time
            or event_time == source_time
        )

        company_match = (
            not event_company
            or not source_company
            or event_company == source_company
        )

        venue_match = (
            not event_venue
            or not source_venue
            or event_venue == source_venue
        )

        if time_match and company_match and venue_match:
            matched = candidate
            break

    if matched is None:
        report(
            False,
            f"法人說明會 #{number} "
            f"{stock_id} {event_date} "
            "找到同日場次，但時間、公司名稱或場地不一致",
        )
        return

    report(
        True,
        f"法人說明會 #{number} "
        f"{stock_id} {event_date} 與 v13 原始場次相符",
    )

    source_session = matched["session"]

    # 狀態欄位存在時，才進行狀態比對
    if "status" in source_session:
        report(
            event.get("status") == source_session.get("status"),
            f"法人說明會 #{number} status 與來源一致",
        )

    if "cancelled" in source_session:
        report(
            event.get("cancelled") == source_session.get("cancelled"),
            f"法人說明會 #{number} cancelled 與來源一致",
        )

    # 日期範圍
    report(
        CONFERENCE_DATE_START
        <= event_date
        <= CONFERENCE_DATE_END,
        f"法人說明會 #{number} 日期位於設定範圍內",
    )


# ============================================================
# 4. TWSE 重大訊息來源比對
# ============================================================

def normalize_key(value):
    return re.sub(
        r"[\s_\-（）()：:／/]",
        "",
        str(value).strip().lower(),
    )


def normalize_record(record):
    if not isinstance(record, dict):
        return {}

    return {
        normalize_key(key): value
        for key, value in record.items()
    }


def find_value(record, aliases):
    """依欄位別名查找原始 API 欄位。"""

    normalized = normalize_record(record)

    for alias in aliases:
        key = normalize_key(alias)

        if key in normalized:
            value = normalized[key]

            if value is not None and str(value).strip():
                return value

    return None


def extract_major_news_fields(record):
    """
    依 TWSE OpenAPI 常見欄位名稱提取資料。
    若 API 欄位名稱改變，應依實際回應調整別名。
    """

    stock_id = find_value(
        record,
        [
            "公司代號",
            "股票代號",
            "公司代碼",
            "證券代號",
            "公司代號 ",
        ],
    )

    company_name = find_value(
        record,
        [
            "公司名稱",
            "公司簡稱",
            "證券名稱",
        ],
    )

    raw_date = find_value(
        record,
        [
            "發言日期",
            "公告日期",
            "日期",
            "發布日期",
        ],
    )

    raw_time = find_value(
        record,
        [
            "發言時間",
            "公告時間",
            "時間",
        ],
    )

    title = find_value(
        record,
        [
            "主旨",
            "公告主旨",
            "重大訊息主旨",
            "標題",
        ],
    )

    return {
        "stock_id": normalize_stock_id(stock_id),
        "company_name": str(company_name or "").strip(),
        "date": parse_date(raw_date),
        "time": str(raw_time or "").strip(),
        "title": str(title or "").strip(),
        "raw": record,
    }


def fetch_major_news():
    print("\n正在取得 TWSE 重大訊息原始資料...")

    response = requests.get(
        TWSE_MAJOR_NEWS_URL,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError(
            "TWSE 重大訊息 API 回傳格式不是 JSON 陣列"
        )

    print(f"TWSE 原始資料筆數：{len(data)}")

    return [
        extract_major_news_fields(record)
        for record in data
        if isinstance(record, dict)
    ]


def validate_major_news_event(event, source_records, number):
    stock_id = normalize_stock_id(event.get("stock_id"))
    event_date = parse_date(event.get("date"))
    event_title = normalize_text(event.get("title"))
    event_time = normalize_text(event.get("time"))
    event_company = normalize_text(event.get("company_name"))

    if not stock_id or not event_date or not event_title:
        report(
            False,
            f"重大訊息 #{number} 缺少股票代號、日期或標題",
        )
        return

    # 先以股票、日期和標題找來源
    candidates = []

    for source in source_records:
        if source["stock_id"] != stock_id:
            continue

        if source["date"] != event_date:
            continue

        source_title = normalize_text(source["title"])

        if source_title != event_title:
            continue

        candidates.append(source)

    if not candidates:
        report(
            False,
            f"重大訊息 #{number} "
            f"{stock_id} {event_date} "
            "在目前 TWSE API 回應中找不到完全相符的資料",
        )
        return

    report(
        True,
        f"重大訊息 #{number} "
        f"{stock_id} {event_date} 標題與 TWSE 相符",
    )

    # 公司名稱
    source_names = {
        normalize_text(item["company_name"])
        for item in candidates
        if item["company_name"]
    }

    if event_company and source_names:
        report(
            event_company in source_names,
            f"重大訊息 #{number} 公司名稱與 TWSE 相符",
        )
    else:
        warn(
            f"重大訊息 #{number} 無法比對公司名稱，"
            "原始 API 可能未提供可辨識欄位"
        )

    # 時間可能存在格式差異，先正規化後比對
    source_times = {
        normalize_text(item["time"])
        for item in candidates
        if item["time"]
    }

    if event_time and source_times:
        report(
            event_time in source_times,
            f"重大訊息 #{number} 時間與 TWSE 相符",
        )
    else:
        warn(
            f"重大訊息 #{number} 無法比對時間，"
            "原始 API 欄位可能缺少或格式不同"
        )

    # 重大訊息過去 30 天
    report(
        DATE_START <= event_date <= TODAY,
        f"重大訊息 #{number} 日期位於過去 30 天範圍內",
    )


# ============================================================
# 5. 主程式
# ============================================================

def main():
    print("=" * 72)
    print("台股事件內容與來源獨立驗證")
    print("=" * 72)

    print(f"台灣日期：{TODAY}")
    print(
        f"重大訊息日期範圍：{DATE_START} ～ {TODAY}"
    )
    print(
        "法人說明會日期範圍："
        f"{CONFERENCE_DATE_START} ～ {CONFERENCE_DATE_END}"
    )

    # --------------------------------------------------------
    # 讀取本機檔案
    # --------------------------------------------------------

    try:
        events, conference_activities = load_event_files()

    except (
        FileNotFoundError,
        json.JSONDecodeError,
        ValueError,
        OSError,
    ) as exc:
        print(f"[FAIL] 無法讀取驗證資料：{exc}")
        return 1

    print(f"\nevents.json 事件筆數：{len(events)}")

    # --------------------------------------------------------
    # 法人說明會比對
    # --------------------------------------------------------

    print("\n" + "=" * 72)
    print("一、法人說明會來源核對")
    print("=" * 72)

    conference_index = build_conference_source_index(
        conference_activities
    )

    conference_events = [
        (index, event)
        for index, event in enumerate(events, start=1)
        if isinstance(event, dict)
        and event.get("category") == "法人說明會"
    ]

    print(f"待核對法人說明會：{len(conference_events)} 筆")

    for number, event in conference_events:
        validate_conference_event(
            event,
            conference_index,
            number,
        )

    # --------------------------------------------------------
    # 取得重大訊息原始 API
    # --------------------------------------------------------

    major_news_events = [
        (index, event)
        for index, event in enumerate(events, start=1)
        if isinstance(event, dict)
        and event.get("category") != "法人說明會"
    ]

    print("\n" + "=" * 72)
    print("二、TWSE 重大訊息來源核對")
    print("=" * 72)

    source_records = None

    if major_news_events:
        try:
            source_records = fetch_major_news()

        except (
            requests.RequestException,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            report(
                False,
                f"無法取得 TWSE 重大訊息 API：{exc}",
            )

    if source_records is not None:
        for number, event in major_news_events:
            validate_major_news_event(
                event,
                source_records,
                number,
            )

    elif not major_news_events:
        print("沒有需要核對的重大訊息。")

    # --------------------------------------------------------
    # 測試股票範圍
    # --------------------------------------------------------

    print("\n" + "=" * 72)
    print("三、測試股票範圍核對")
    print("=" * 72)

    for number, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            report(False, f"事件 #{number} 不是物件")
            continue

        stock_id = normalize_stock_id(
            event.get("stock_id")
        )

        report(
            stock_id in TEST_STOCKS,
            f"事件 #{number} 股票 {stock_id} 屬於測試清單",
        )

    # --------------------------------------------------------
    # 最終摘要
    # --------------------------------------------------------

    print("\n" + "=" * 72)
    print("四、驗證摘要")
    print("=" * 72)

    print(f"檢查項目：{CHECK_COUNT}")
    print(f"錯誤數量：{len(ERRORS)}")
    print(f"警告數量：{len(WARNINGS)}")

    if ERRORS:
        print("\n驗證結果：FAIL")

        for error in ERRORS:
            print(f"  - {error}")

        return 1

    if WARNINGS:
        print("\n驗證結果：PASS WITH WARNINGS")
        print("部分欄位無法核對，請檢查 WARN 訊息。")
        return 0

    print("\n驗證結果：PASS")
    print("事件內容與來源核對全部通過。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
