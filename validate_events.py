import json
import re
from datetime import datetime
from pathlib import Path
# ============================================================
# 1. 基本設定
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
EVENTS_FILE = BASE_DIR / "events.json"
REQUIRED_TOP_LEVEL_FIELDS = [
    "version",
    "generated_at",
    "stock_count",
    "event_count",
    "events",
]
COMMON_REQUIRED_FIELDS = [
    "stock_id",
    "company_name",
    "date",
    "time",
    "category",
    "title",
    "source",
]
CONFERENCE_REQUIRED_FIELDS = [
    "status",
    "cancelled",
    "source_event_id",
    "source_format",
]
MAJOR_NEWS_REQUIRED_FIELDS = [
    "source_url",
]
# 第一版已設定的測試股票
TEST_STOCKS = {
    "1101",
    "1410",
    "2330",
    "2454",
    "2317",
}
# ============================================================
# 2. 驗證工具
# ============================================================
def check(condition, message, errors):
    """記錄驗證結果。"""
    if condition:
        print(f"[PASS] {message}")
    else:
        print(f"[FAIL] {message}")
        errors.append(message)
def is_valid_date(value):
    """確認日期格式為 YYYY-MM-DD，且日期真實存在。"""
    if not isinstance(value, str):
        return False
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False
def is_valid_datetime(value):
    """確認 generated_at 是有效的 ISO 日期時間。"""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False
# ============================================================
# 3. 讀取 JSON
# ============================================================
def load_events_file():
    if not EVENTS_FILE.exists():
        raise FileNotFoundError(
            f"找不到檔案：{EVENTS_FILE}"
        )
    with EVENTS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)
# ============================================================
# 4. 驗證頂層結構
# ============================================================
def validate_top_level(data, errors):
    print("\n" + "=" * 72)
    print("一、頂層結構驗證")
    print("=" * 72)
    check(
        isinstance(data, dict),
        "頂層資料是 JSON 物件",
        errors,
    )
    if not isinstance(data, dict):
        return False
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        check(
            field in data,
            f"存在必要欄位：{field}",
            errors,
        )
    missing_fields = [
        field
        for field in REQUIRED_TOP_LEVEL_FIELDS
        if field not in data
    ]
    if missing_fields:
        return False
    check(
        isinstance(data["events"], list),
        "events 是陣列",
        errors,
    )
    check(
        isinstance(data["version"], str)
        and bool(data["version"].strip()),
        "version 是非空字串",
        errors,
    )
    check(
        is_valid_datetime(data["generated_at"]),
        "generated_at 是有效的 ISO 日期時間",
        errors,
    )
    check(
        type(data["event_count"]) is int
        and data["event_count"] >= 0,
        "event_count 是非負整數",
        errors,
    )
    check(
        type(data["stock_count"]) is int
        and data["stock_count"] >= 0,
        "stock_count 是非負整數",
        errors,
    )
    if isinstance(data["events"], list):
        check(
            data["event_count"] == len(data["events"]),
            "event_count 與實際事件筆數一致",
            errors,
        )
    return isinstance(data["events"], list)
# ============================================================
# 5. 驗證事件欄位
# ============================================================
def validate_event(event, index, errors):
    prefix = f"事件 #{index}"
    if not isinstance(event, dict):
        check(False, f"{prefix} 是 JSON 物件", errors)
        return None
    check(True, f"{prefix} 是 JSON 物件", errors)
    # 共同必要欄位
    for field in COMMON_REQUIRED_FIELDS:
        value = event.get(field)
        check(
            isinstance(value, str) and bool(value.strip()),
            f"{prefix} 欄位 {field} 存在且非空",
            errors,
        )
    # 股票代號
    stock_id = event.get("stock_id")
    check(
        isinstance(stock_id, str)
        and bool(re.fullmatch(r"\d{4,6}", stock_id)),
        f"{prefix} 股票代號格式正確",
        errors,
    )
    if isinstance(stock_id, str) and stock_id:
        check(
            stock_id in TEST_STOCKS,
            f"{prefix} 股票代號屬於目前測試清單",
            errors,
        )
    # 日期
    check(
        is_valid_date(event.get("date")),
        f"{prefix} 日期有效且格式為 YYYY-MM-DD",
        errors,
    )
    # 法人說明會
    if event.get("category") == "法人說明會":
        for field in CONFERENCE_REQUIRED_FIELDS:
            check(
                field in event,
                f"{prefix} 法人說明會欄位存在：{field}",
                errors,
            )
        check(
            isinstance(event.get("cancelled"), bool),
            f"{prefix} cancelled 是布林值",
            errors,
        )
        if "status" in event:
            check(
                isinstance(event["status"], str),
                f"{prefix} status 是字串",
                errors,
            )
        if "source_event_id" in event:
            check(
                isinstance(event["source_event_id"], str),
                f"{prefix} source_event_id 是字串",
                errors,
            )
        if "source_format" in event:
            check(
                event["source_format"] in ("pdf", "docx", ""),
                f"{prefix} source_format 值有效",
                errors,
            )
    # TWSE 重大訊息
    elif event.get("source_url") is not None:
        check(
            isinstance(event["source_url"], str)
            and event["source_url"].startswith("https://"),
            f"{prefix} source_url 是 HTTPS 網址",
            errors,
        )
    return event
# ============================================================
# 6. 驗證統計與重複事件
# ============================================================
def validate_statistics(data, valid_events, errors):
    print("\n" + "=" * 72)
    print("二、統計與重複資料驗證")
    print("=" * 72)
    unique_stocks = {
        event.get("stock_id")
        for event in valid_events
        if isinstance(event.get("stock_id"), str)
        and event.get("stock_id")
    }
    check(
        data.get("stock_count") == len(unique_stocks),
        "stock_count 與實際不同股票數一致",
        errors,
    )
    # 使用來源、股票、日期、時間、類別、標題識別完全相同事件。
    # 不直接比較整筆 JSON，避免其他欄位差異影響判斷。
    seen = set()
    duplicates = []
    for index, event in enumerate(valid_events, start=1):
        key = (
            event.get("source"),
            event.get("stock_id"),
            event.get("date"),
            event.get("time"),
            event.get("category"),
            event.get("title"),
        )
        if key in seen:
            duplicates.append(index)
        else:
            seen.add(key)
    check(
        not duplicates,
        "沒有完全相同的事件識別組合",
        errors,
    )
    if duplicates:
        print(
            "  重複事件所在序號："
            + ", ".join(map(str, duplicates))
        )
# ============================================================
# 7. 主程式
# ============================================================
def main():
    print("=" * 72)
    print("events.json 格式驗證程式")
    print("=" * 72)
    print(f"檢查檔案：{EVENTS_FILE}")
    errors = []
    try:
        data = load_events_file()
    except FileNotFoundError as exc:
        print(f"[FAIL] {exc}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"[FAIL] JSON 格式錯誤：{exc}")
        return 1
    except OSError as exc:
        print(f"[FAIL] 無法讀取檔案：{exc}")
        return 1
    if not validate_top_level(data, errors):
        print("\n驗證中止：頂層結構不完整或 events 不是陣列。")
        return 1
    print("\n" + "=" * 72)
    print("三、事件內容驗證")
    print("=" * 72)
    valid_events = []
    for index, event in enumerate(data["events"], start=1):
        result = validate_event(event, index, errors)
        if result is not None:
            valid_events.append(result)
    validate_statistics(data, valid_events, errors)
    print("\n" + "=" * 72)
    print("驗證摘要")
    print("=" * 72)
    print(f"事件筆數：{len(data['events'])}")
    print(f"不同股票數：{len(set(
        event.get('stock_id')
        for event in valid_events
        if isinstance(event.get('stock_id'), str)
    ))}")
    print(f"錯誤數量：{len(errors)}")
    if errors:
        print("\n驗證結果：FAIL")
        print("請依照上方 [FAIL] 訊息檢查資料。")
        return 1
    print("\n驗證結果：PASS")
    print("events.json 通過本程式的格式與基本一致性檢查。")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
