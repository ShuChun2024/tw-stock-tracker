import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

HISTORY_FILE = BASE_DIR / "major_news_history.json"

# 歷史資料保留天數
HISTORY_RETENTION_DAYS = 365

# TWSE OpenAPI
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

REQUEST_TIMEOUT = 30


# ============================================================
# 2. 日期工具
# ============================================================

def roc_to_date(value):
    """
    將民國日期 / 西元日期轉成 YYYY-MM-DD。

    支援：

        1151015
        115/10/15
        115-10-15

        20261015
        2026/10/15
        2026-10-15
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
    # 民國日期 YYYMMDD
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
    # 民國日期 YYY/MM/DD
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
# 3. 欄位工具
# ============================================================

def normalize_key(value):
    """
    正規化 API 欄位名稱。
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


def get_first_value(record, candidates):
    """
    依候選欄位順序取得第一個非空值。
    """

    for key in candidates:

        value = record.get(key)

        if value is None:
            continue

        text = str(value).strip()

        if text:
            return text

    return ""


# ============================================================
# 4. 重大訊息欄位解析
# ============================================================

def get_stock_code(record):
    candidates = [
        "公司代號",
        "證券代號",
        "股票代號",
        "公司碼",
        "代號",
    ]

    value = get_first_value(
        record,
        candidates,
    )

    if not value:
        return ""

    match = re.search(
        r"\d{4,6}",
        value,
    )

    if match:
        return match.group(0)

    return ""


def get_company_name(record):
    candidates = [
        "公司名稱",
        "公司簡稱",
        "證券名稱",
        "股票名稱",
    ]

    return get_first_value(
        record,
        candidates,
    )


def get_event_date(record):
    """
    事件日期優先使用發言日期。

    不使用出表日期取代發言日期，
    因為兩者語意不同。
    """

    candidates = [
        "發言日期",
        "公告日期",
        "日期",
    ]

    for key in candidates:

        value = record.get(key)

        result = roc_to_date(value)

        if result:
            return result

    return ""


def get_speech_date(record):
    """
    保留原始發言日期轉換後的值。
    """

    value = record.get("發言日期")

    return roc_to_date(value) or ""


def get_fact_date(record):
    """
    事實發生日。
    """

    value = record.get("事實發生日")

    return roc_to_date(value) or ""


def get_event_time(record):
    candidates = [
        "發言時間",
        "公告時間",
        "時間",
    ]

    return get_first_value(
        record,
        candidates,
    )


def get_title(record):
    candidates = [
        "主旨",
        "標題",
        "公告主旨",
        "訊息主旨",
        "重大訊息主旨",
    ]

    return get_first_value(
        record,
        candidates,
    )


def get_meeting_date(record):
    """
    部分 API 資料可能存在其他日期欄位。
    目前只保存，不用於主要事件日期。
    """

    return get_first_value(
        record,
        [
            "出表日期",
        ],
    )


def get_clause(record):
    return get_first_value(
        record,
        [
            "符合條款",
        ],
    )


def get_description(record):
    return get_first_value(
        record,
        [
            "說明",
        ],
    )


# ============================================================
# 5. 重大訊息分類
# ============================================================

def classify_event(title):
    """
    與目前 event_collector.py 保持相同分類邏輯。
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
# 6. 轉換 API 資料
# ============================================================

def convert_record(record):
    """
    將 TWSE API record 轉成歷史資料格式。
    """

    record = normalize_record(record)

    stock_id = get_stock_code(record)

    if not stock_id:
        return None

    event_date = get_event_date(record)

    if not event_date:
        return None

    event_time = get_event_time(record)
    title = get_title(record)

    company_name = get_company_name(record)

    return {
        "stock_id": stock_id,
        "company_name": company_name,
        "date": event_date,
        "time": event_time,
        "category": classify_event(title),
        "title": title,

        # ----------------------------------------------------
        # 保留 TWSE 重要原始欄位的標準化結果
        # ----------------------------------------------------

        "speech_date": get_speech_date(record),
        "fact_date": get_fact_date(record),
        "published_date": get_meeting_date(record),
        "clause": get_clause(record),
        "description": get_description(record),

        # ----------------------------------------------------
        # 來源
        # ----------------------------------------------------

        "source": "TWSE",
        "source_url": TWSE_URL,

        # ----------------------------------------------------
        # 實際收集時間
        # ----------------------------------------------------

        "collected_at": datetime.now().isoformat(),
    }


# ============================================================
# 7. 取得 TWSE API
# ============================================================

def fetch_twse_records():
    """
    取得 TWSE 重大訊息。

    API 失敗直接 raise，
    不讓主流程覆寫既有歷史檔。
    """

    print("\n" + "=" * 72)
    print("取得 TWSE 上市公司重大訊息")
    print("=" * 72)

    print(
        f"API：{TWSE_URL}"
    )

    response = requests.get(
        TWSE_URL,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError(
            "TWSE API 回傳格式不是 list："
            f"{type(data)}"
        )

    print(
        f"API 原始資料筆數：{len(data)}"
    )

    return data


# ============================================================
# 8. 讀取歷史檔
# ============================================================

def load_history():
    """
    讀取 major_news_history.json。

    檔案不存在時建立空歷史。
    """

    if not HISTORY_FILE.exists():

        print(
            "\n歷史檔不存在，建立新的歷史資料。"
        )

        return []

    try:

        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

    except Exception as exc:

        raise RuntimeError(
            "讀取歷史檔失敗，"
            "為避免破壞既有資料，本次停止："
            f"{exc}"
        ) from exc

    if not isinstance(data, dict):

        raise ValueError(
            "歷史檔格式錯誤：最外層不是 object。"
        )

    events = data.get(
        "events",
        [],
    )

    if not isinstance(events, list):

        raise ValueError(
            "歷史檔格式錯誤：events 不是 list。"
        )

    print(
        f"既有歷史資料：{len(events)} 筆"
    )

    return events


# ============================================================
# 9. 事件識別鍵
# ============================================================

def event_key(event):
    """
    重大訊息唯一識別鍵。

    公司代號 + 發言日期 + 發言時間 + 主旨
    """

    return (
        str(event.get(
            "stock_id",
            "",
        )).strip(),

        str(event.get(
            "speech_date",
            event.get(
                "date",
                "",
            ),
        )).strip(),

        str(event.get(
            "time",
            "",
        )).strip(),

        re.sub(
            r"\s+",
            "",
            str(event.get(
                "title",
                "",
            )).strip(),
        ),
    )


# ============================================================
# 10. 去重
# ============================================================

def deduplicate_events(events):
    """
    歷史資料去重。

    如果同一事件重複出現，
    保留最後一筆。

    這樣可以讓後續 API 資料修正時，
    新資料覆蓋舊資料。
    """

    event_map = {}

    for event in events:

        if not isinstance(event, dict):
            continue

        key = event_key(event)

        if not any(key):
            continue

        event_map[key] = event

    return list(event_map.values())


# ============================================================
# 11. 清除過期資料
# ============================================================

def filter_history_by_retention(events):
    """
    只保留 HISTORY_RETENTION_DAYS 內的重大訊息。

    例如：

        HISTORY_RETENTION_DAYS = 365

    就保留今天往前 365 天的資料。
    """

    today = datetime.now().date()

    cutoff_date = (
        today
        - timedelta(
            days=HISTORY_RETENTION_DAYS
        )
    )

    result = []

    removed = 0
    invalid_date = 0

    for event in events:

        date_text = str(
            event.get(
                "date",
                "",
            )
        ).strip()

        try:

            event_date = datetime.strptime(
                date_text,
                "%Y-%m-%d",
            ).date()

        except Exception:

            invalid_date += 1

            # 日期無法解析的資料不自動刪除，
            # 避免因格式問題誤刪歷史資料。
            result.append(event)

            continue

        if event_date >= cutoff_date:

            result.append(event)

        else:

            removed += 1

    print(
        f"\n歷史保留期限："
        f"{HISTORY_RETENTION_DAYS} 天"
    )

    print(
        f"保留起始日期："
        f"{cutoff_date}"
    )

    print(
        f"清除過期資料："
        f"{removed} 筆"
    )

    if invalid_date:

        print(
            f"日期無法解析資料："
            f"{invalid_date} 筆"
        )

    return result


# ============================================================
# 12. 排序
# ============================================================

def sort_events(events):
    """
    最新日期優先。
    """

    def sort_key(event):

        return (
            str(
                event.get(
                    "date",
                    "",
                )
            ),
            str(
                event.get(
                    "time",
                    "",
                )
            ),
            str(
                event.get(
                    "stock_id",
                    "",
                )
            ),
        )

    return sorted(
        events,
        key=sort_key,
        reverse=True,
    )


# ============================================================
# 13. 儲存歷史檔
# ============================================================

def save_history(events):
    """
    寫入 major_news_history.json。
    """

    stock_ids = {
        event.get(
            "stock_id",
            "",
        )
        for event in events
        if event.get(
            "stock_id",
            "",
        )
    }

    output = {
        "version": "1.0",

        "generated_at": (
            datetime.now().isoformat()
        ),

        "retention_days": (
            HISTORY_RETENTION_DAYS
        ),

        "stock_count": len(stock_ids),

        "event_count": len(events),

        "events": events,
    }

    temp_file = HISTORY_FILE.with_suffix(
        ".tmp"
    )

    with open(
        temp_file,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # 成功寫完後才取代正式檔
    temp_file.replace(
        HISTORY_FILE
    )

    print(
        f"\n已寫入歷史檔："
        f"{HISTORY_FILE}"
    )


# ============================================================
# 14. 統計
# ============================================================

def print_statistics(
    api_count,
    converted_count,
    old_count,
    merged_count,
    final_count,
):
    """
    顯示收集統計。
    """

    print("\n" + "=" * 72)
    print("重大訊息歷史資料統計")
    print("=" * 72)

    print(
        f"TWSE API 原始資料："
        f"{api_count}"
    )

    print(
        f"本次成功轉換："
        f"{converted_count}"
    )

    print(
        f"既有歷史資料："
        f"{old_count}"
    )

    print(
        f"合併後去重："
        f"{merged_count}"
    )

    print(
        f"保留期限篩選後："
        f"{final_count}"
    )


# ============================================================
# 15. 主流程
# ============================================================

def main():

    print("=" * 72)
    print("TWSE 上市公司重大訊息每日歷史收集器")
    print("=" * 72)

    print(
        f"歷史保留天數："
        f"{HISTORY_RETENTION_DAYS}"
    )

    print(
        "收集範圍：所有 TWSE API 回傳的上市公司"
    )

    # ========================================================
    # A. 先取得 API
    #
    # API 失敗時直接停止。
    # 此時不讀取、不修改歷史檔。
    # ========================================================

    try:

        records = fetch_twse_records()

    except Exception as exc:

        print("\n" + "=" * 72)
        print("ERROR")
        print("=" * 72)

        print(
            f"TWSE 重大訊息取得失敗：{exc}"
        )

        print(
            "本次不修改 major_news_history.json。"
        )

        raise

    # ========================================================
    # B. 轉換所有上市公司資料
    # ========================================================

    new_events = []

    skipped = 0

    for record in records:

        event = convert_record(record)

        if event:

            new_events.append(event)

        else:

            skipped += 1

    print(
        f"\n本次成功轉換："
        f"{len(new_events)} 筆"
    )

    print(
        f"無法轉換而略過："
        f"{skipped} 筆"
    )

    # ========================================================
    # C. 讀取歷史資料
    # ========================================================

    old_events = load_history()

    # ========================================================
    # D. 合併
    # ========================================================

    merged_events = (
        old_events
        + new_events
    )

    print(
        f"\n合併前："
        f"{len(merged_events)} 筆"
    )

    # ========================================================
    # E. 去重
    # ========================================================

    merged_events = deduplicate_events(
        merged_events
    )

    print(
        f"去重後："
        f"{len(merged_events)} 筆"
    )

    # ========================================================
    # F. 歷史保留期限
    # ========================================================

    final_events = (
        filter_history_by_retention(
            merged_events
        )
    )

    # ========================================================
    # G. 排序
    # ========================================================

    final_events = sort_events(
        final_events
    )

    # ========================================================
    # H. 統計
    # ========================================================

    print_statistics(
        api_count=len(records),
        converted_count=len(new_events),
        old_count=len(old_events),
        merged_count=len(merged_events),
        final_count=len(final_events),
    )

    # ========================================================
    # I. 儲存
    # ========================================================

    save_history(
        final_events
    )

    print("\n" + "=" * 72)
    print("每日重大訊息收集完成")
    print("=" * 72)


# ============================================================
# 16. Entry Point
# ============================================================

if __name__ == "__main__":
    main()
