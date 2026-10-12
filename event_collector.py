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

# ============================================================
# 測試模式
# ============================================================
# True  = 只測試 4 檔
# False = 讀取 stocks.json / analysis.json 的全部股票
#
TEST_MODE = True

TEST_STOCKS = [
    "1101",
    "2330",
    "2454",
    "2317",
]

# 正式收集保留最近幾天
LOOKBACK_DAYS = 30

# ============================================================
# 診斷模式
# ============================================================
# True：
#   1. 印出 API 回傳筆數
#   2. 印出第一筆資料
#   3. 印出所有實際欄位名稱
#   4. 印出符合測試股票的資料
#
# 確認欄位正常後，可以改成 False
DIAGNOSTIC_MODE = True

# ============================================================
# API
# ============================================================

TWSE_URL = (
    "https://openapi.twse.com.tw/"
    "v1/opendata/t187ap04_L"
)

TPEX_URL = (
    "https://www.tpex.org.tw/"
    "openapi/v1/mopsfin_t187ap04_O"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


# ============================================================
# 2. HTTP
# ============================================================

def get_json(url):
    print()
    print("--------------------------------------------------")
    print("查詢：", url)

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    print("HTTP 狀態碼：", response.status_code)
    print("Content-Type：", response.headers.get("Content-Type"))

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError(
            "API 回傳格式不是 JSON 陣列："
            + str(type(data))
        )

    print("API 回傳：", len(data), "筆")

    return data


# ============================================================
# 3. 清理欄位名稱
# ============================================================

def normalize_key(key):
    """
    API 欄位可能出現：

        主旨
        主旨 
        公司代號
        公司代號　

    所以統一去除前後空白。
    """

    return str(key).strip()


def normalize_record(record):
    if not isinstance(record, dict):
        return {}

    return {
        normalize_key(k): v
        for k, v in record.items()
    }


# ============================================================
# 4. 民國日期轉西元
# ============================================================

def roc_to_date(value):
    """
    支援：

        1151012
        115/10/12
        115-10-12
        20261012
        2026/10/12

    回傳 datetime.date
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # 純數字
    digits = re.sub(r"\D", "", text)

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
            return None

    if len(digits) == 8:
        try:
            year = int(digits[:4])
            month = int(digits[4:6])
            day = int(digits[6:8])

            return datetime(
                year,
                month,
                day
            ).date()
        except ValueError:
            return None

    # 有分隔符號
    match = re.match(
        r"^(\d{3,4})[/-](\d{1,2})[/-](\d{1,2})$",
        text
    )

    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))

        if year < 1911:
            year += 1911

        try:
            return datetime(
                year,
                month,
                day
            ).date()
        except ValueError:
            return None

    return None


# ============================================================
# 5. 找股票代號
# ============================================================

def get_stock_code(record):
    keys = [
        "公司代號",
        "證券代號",
        "股票代號",
        "公司碼",
        "代號",
    ]

    for key in keys:
        value = record.get(key)

        if value is None:
            continue

        code = str(value).strip()

        if re.fullmatch(r"\d{4,6}", code):
            return code

    return ""


# ============================================================
# 6. 找日期
# ============================================================

def get_event_date(record):
    """
    優先使用：

    發言日期

    因為這是公司發布重大訊息的日期。

    若不存在，再依序使用：

    出表日期
    事實發生日
    """

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

    return None


# ============================================================
# 7. 找時間
# ============================================================

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


# ============================================================
# 8. 找標題
# ============================================================

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


# ============================================================
# 9. 找公司名稱
# ============================================================

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
# 10. 事件分類
# ============================================================

def classify_event(title):
    text = str(title or "")

    rules = [
        (
            "法說會",
            [
                "法人說明會",
                "法說會",
                "法人說明會",
            ]
        ),
        (
            "增資／減資",
            [
                "現金增資",
                "增資",
                "減資",
                "發行新股",
            ]
        ),
        (
            "庫藏股",
            [
                "庫藏股",
                "買回本公司股份",
                "註銷庫藏股",
            ]
        ),
        (
            "董監／大股東異動",
            [
                "董事",
                "監察人",
                "大股東",
                "持股",
                "質押",
                "轉讓",
                "法人董事",
            ]
        ),
        (
            "可轉債",
            [
                "可轉換公司債",
                "轉換公司債",
                "海外轉換公司債",
                "CB",
            ]
        ),
        (
            "重大投資／併購",
            [
                "取得資產",
                "處分資產",
                "投資",
                "併購",
                "合併",
                "收購",
            ]
        ),
        (
            "股利／除權息",
            [
                "股利",
                "除權",
                "除息",
                "配息",
            ]
        ),
        (
            "財報／財務",
            [
                "財務報告",
                "財報",
                "自結",
                "損益",
                "營業收入",
                "營收",
            ]
        ),
    ]

    for category, keywords in rules:
        for keyword in keywords:
            if keyword in text:
                return category

    return "重大訊息"


# ============================================================
# 11. 診斷：印出 API 真實資料
# ============================================================

def diagnostic_dump(source_name, records):
    print()
    print()
    print("==================================================")
    print("診斷：", source_name)
    print("==================================================")

    print("資料筆數：", len(records))

    if not records:
        print("沒有任何資料。")
        return

    first = records[0]

    print()
    print("【第一筆原始資料】")
    print(json.dumps(
        first,
        ensure_ascii=False,
        indent=2
    ))

    print()
    print("【實際欄位名稱】")

    keys = list(first.keys())

    for index, key in enumerate(keys, 1):
        print(f"{index:02d}. [{key}]")

    print()
    print("【清理後欄位名稱】")

    normalized = normalize_record(first)

    for index, key in enumerate(normalized.keys(), 1):
        print(f"{index:02d}. [{key}]")

    print()
    print("【解析結果】")

    print("公司代號：", get_stock_code(normalized))
    print("公司名稱：", get_company_name(normalized))
    print("日期：", get_event_date(normalized))
    print("時間：", get_event_time(normalized))
    print("標題：", get_title(normalized))

    print()
    print("==================================================")


# ============================================================
# 12. 正式解析
# ============================================================

def convert_record(record, source):
    record = normalize_record(record)

    stock_code = get_stock_code(record)

    if not stock_code:
        return None

    event_date = get_event_date(record)

    if not event_date:
        return None

    title = get_title(record)

    if not title:
        return None

    event_time = get_event_time(record)

    company_name = get_company_name(record)

    category = classify_event(title)

    source_name = (
        "TWSE"
        if source == "twse"
        else "TPEx"
    )

    return {
        "stock_id": stock_code,
        "company_name": company_name,
        "date": event_date.isoformat(),
        "time": event_time,
        "category": category,
        "title": title,
        "source": source_name,
        "source_url": (
            "https://mops.twse.com.tw/"
        ),
    }


# ============================================================
# 13. 取得測試股票
# ============================================================

def get_target_stocks():
    if TEST_MODE:
        print()
        print("目前為 TEST_MODE，只測試：")
        print(", ".join(TEST_STOCKS))
        return set(TEST_STOCKS)

    # --------------------------------------------------------
    # 正式模式：
    # 優先從 stocks.json 取得
    # --------------------------------------------------------

    stocks_file = BASE_DIR / "stocks.json"

    if stocks_file.exists():
        try:
            data = json.loads(
                stocks_file.read_text(
                    encoding="utf-8"
                )
            )

            result = set()

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        code = item.get("stock_id")

                        if code:
                            result.add(str(code))

            elif isinstance(data, dict):
                stocks = data.get("stocks", [])

                if isinstance(stocks, list):
                    for item in stocks:
                        if isinstance(item, dict):
                            code = item.get("stock_id")

                            if code:
                                result.add(str(code))

            if result:
                print()
                print(
                    "正式模式：從 stocks.json 取得",
                    len(result),
                    "檔股票"
                )

                return result

        except Exception as error:
            print(
                "讀取 stocks.json 失敗：",
                error
            )

    # --------------------------------------------------------
    # 若沒有 stocks.json，嘗試 analysis.json
    # --------------------------------------------------------

    analysis_file = BASE_DIR / "analysis.json"

    if analysis_file.exists():
        try:
            data = json.loads(
                analysis_file.read_text(
                    encoding="utf-8"
                )
            )

            stocks = (
                data
                if isinstance(data, list)
                else data.get("stocks", [])
            )

            result = set()

            if isinstance(stocks, list):
                for item in stocks:
                    if isinstance(item, dict):
                        code = item.get("stock_id")

                        if code:
                            result.add(str(code))

            if result:
                print()
                print(
                    "正式模式：從 analysis.json 取得",
                    len(result),
                    "檔股票"
                )

                return result

        except Exception as error:
            print(
                "讀取 analysis.json 失敗：",
                error
            )

    raise RuntimeError(
        "找不到可用的股票清單。"
    )


# ============================================================
# 14. 去除重複
# ============================================================

def deduplicate_events(events):
    result = []
    seen = set()

    for event in events:

        key = (
            event.get("stock_id"),
            event.get("date"),
            event.get("time"),
            event.get("title"),
            event.get("source"),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(event)

    return result


# ============================================================
# 15. 日期過濾
# ============================================================

def filter_recent(events):
    today = datetime.now().date()

    start_date = (
        today - timedelta(days=LOOKBACK_DAYS)
    )

    result = []

    for event in events:

        try:
            event_date = datetime.strptime(
                event["date"],
                "%Y-%m-%d"
            ).date()
        except Exception:
            continue

        if start_date <= event_date <= today:
            result.append(event)

    return result


# ============================================================
# 16. 排序
# ============================================================

def sort_events(events):
    return sorted(
        events,
        key=lambda x: (
            x.get("stock_id", ""),
            x.get("date", ""),
            x.get("time", ""),
        ),
        reverse=True
    )


# ============================================================
# 17. 主程式
# ============================================================

def main():

    print()
    print("==================================================")
    print("股票事件消息收集器")
    print("==================================================")

    print("執行時間：", datetime.now().isoformat())
    print("TEST_MODE：", TEST_MODE)
    print("DIAGNOSTIC_MODE：", DIAGNOSTIC_MODE)
    print("LOOKBACK_DAYS：", LOOKBACK_DAYS)

    target_stocks = get_target_stocks()

    print()
    print("準備處理：", len(target_stocks), "檔股票")

    # --------------------------------------------------------
    # 1. 取得 TWSE
    # --------------------------------------------------------

    twse_records = get_json(TWSE_URL)

    if DIAGNOSTIC_MODE:
        diagnostic_dump(
            "TWSE 上市重大訊息",
            twse_records
        )

    # --------------------------------------------------------
    # 2. 稍微等待
    # --------------------------------------------------------

    time.sleep(1)

    # --------------------------------------------------------
    # 3. 取得 TPEx
    # --------------------------------------------------------

    tpex_records = get_json(TPEX_URL)

    if DIAGNOSTIC_MODE:
        diagnostic_dump(
            "TPEx 上櫃重大訊息",
            tpex_records
        )

    # --------------------------------------------------------
    # 4. 正式解析
    # --------------------------------------------------------

    all_events = []

    for record in twse_records:

        normalized = normalize_record(record)

        code = get_stock_code(normalized)

        if code not in target_stocks:
            continue

        event = convert_record(
            normalized,
            "twse"
        )

        if event:
            all_events.append(event)

    for record in tpex_records:

        normalized = normalize_record(record)

        code = get_stock_code(normalized)

        if code not in target_stocks:
            continue

        event = convert_record(
            normalized,
            "tpex"
        )

        if event:
            all_events.append(event)

    print()
    print("==================================================")
    print("正式解析結果")
    print("==================================================")

    print(
        "符合測試股票的原始事件：",
        len(all_events),
        "筆"
    )

    # --------------------------------------------------------
    # 5. 顯示符合股票的資料
    # --------------------------------------------------------

    if DIAGNOSTIC_MODE and all_events:

        print()
        print("【符合股票的事件】")

        for event in all_events[:20]:

            print(
                event["stock_id"],
                event["date"],
                event["category"],
                event["title"]
            )

    # --------------------------------------------------------
    # 6. 去重
    # --------------------------------------------------------

    events = deduplicate_events(
        all_events
    )

    print(
        "去除重複後：",
        len(events),
        "筆"
    )

    # --------------------------------------------------------
    # 7. 最近 N 天
    # --------------------------------------------------------

    events = filter_recent(events)

    print(
        f"最近 {LOOKBACK_DAYS} 天：",
        len(events),
        "筆"
    )

    # --------------------------------------------------------
    # 8. 排序
    # --------------------------------------------------------

    events = sort_events(events)

    # --------------------------------------------------------
    # 9. 產生 events.json
    # --------------------------------------------------------

    output = {
        "update_time": datetime.now().isoformat(
            timespec="seconds"
        ),
        "lookback_days": LOOKBACK_DAYS,
        "stock_count": len(target_stocks),
        "event_count": len(events),
        "stocks": sorted(
            target_stocks
        ),
        "events": events,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print()
    print("==================================================")
    print("完成")
    print("==================================================")

    print(
        "已產生：",
        OUTPUT_FILE
    )

    print(
        "事件數量：",
        len(events)
    )


if __name__ == "__main__":
    main()
