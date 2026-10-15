import json
import re
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# v13 共用設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

API_LIST_URL = (
    "https://www.twse.com.tw/rwd/zh/news/eventList?response=json"
)
API_DETAIL_URL = (
    "https://www.twse.com.tw/rwd/zh/news/eventDetail"
)

OUTPUT_JSON = BASE_DIR / "twse_conference_v13_result.json"
OUTPUT_TXT = BASE_DIR / "twse_conference_v13_sessions.txt"
FILES_DIR = BASE_DIR / "twse_conference_v13_files"

MAX_EVENTS = 30
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,text/html,*/*",
    "Referer": "https://www.twse.com.tw/zh/news/eventList",
}

session = requests.Session()
session.headers.update(HEADERS)

SUPPORTED_EXTENSIONS = (".docx", ".pdf")

CODE_PATTERN = re.compile(r"(?<!\d)(\d{4,6})(?!\d)")
DATE_PATTERN = re.compile(
    r"(?:(?:\d{4}\s*年\s*)?\d{1,2}\s*月\s*\d{1,2}\s*日)"
)
TIME_PATTERN = re.compile(
    r"\d{1,2}:\d{2}\s*[~～〜–—-]\s*\d{1,2}:\d{2}"
)


# ============================================================
# 共用工具
# ============================================================

def log(message=""):
    print(message, flush=True)


def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def safe_filename(value):
    value = re.sub(r'[\\/:*?"<>|]+', "_", str(value))
    return value[:100]


def save_json(data):
    OUTPUT_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_json(url, params=None):
    response = session.get(
        url, params=params, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            "伺服器回應不是有效 JSON；"
            f"HTTP={response.status_code}，"
            f"Content-Type={response.headers.get('Content-Type', '')}，"
            f"網址={response.url}"
        ) from exc


def first_nonempty(row, indices):
    for index in indices:
        if index is not None and index < len(row):
            value = clean_text(row[index])
            if value:
                return value
    return ""


def parse_date(value):
    value = clean_text(value)
    if not value:
        return ""

    match = re.search(
        r"(?:(\d{4})\s*[年/-]\s*)?"
        r"(\d{1,2})\s*月?\s*[/-]?\s*"
        r"(\d{1,2})\s*日?",
        value,
    )
    if not match:
        return value

    year, month, day = match.groups()
    try:
        month_num = int(month)
        day_num = int(day)

        if not (
            1 <= month_num <= 12
            and 1 <= day_num <= 31
        ):
            return value

        if year:
            return (
                f"{int(year):04d}-"
                f"{month_num:02d}-"
                f"{day_num:02d}"
            )

        return f"{month_num:02d}-{day_num:02d}"
    except ValueError:
        return value


def parse_time(value):
    value = clean_text(value)
    value = (
        value.replace("～", "~")
        .replace("〜", "~")
        .replace("–", "~")
        .replace("—", "~")
    )
    return re.sub(r"\s*~\s*", "~", value)


def is_cancelled(*values):
    text = " ".join(clean_text(value) for value in values)
    return bool(re.search(r"取消|停辦", text))


def make_session(
    stock_code,
    company_name,
    event_title,
    event_id,
    file_format,
    parse_method,
    raw_text="",
    sequence_no="",
    session_date="",
    session_time="",
    venue="",
    notes="",
):
    company_name = clean_text(company_name)
    notes = clean_text(notes)
    raw_text = clean_text(raw_text)
    cancelled = is_cancelled(notes, raw_text)

    return {
        "stock_code": clean_text(stock_code),
        "sequence_no": clean_text(sequence_no),
        "company_name": company_name,
        "company_name_missing": not bool(company_name),
        "date": parse_date(session_date),
        "time": parse_time(session_time),
        "venue": clean_text(venue),
        "notes": notes,
        "status": "cancelled" if cancelled else "scheduled",
        "cancelled": cancelled,
        "event_title": event_title,
        "event_id": event_id,
        "source_format": file_format,
        "raw_text": raw_text,
        "parse_method": parse_method,
    }


# ============================================================
# 活動 API 與活動篩選
# ============================================================

def get_event_list():
    log("")
    log("=" * 72)
    log("[1] 取得證交所活動列表")
    log("=" * 72)
    log(f"API URL: {API_LIST_URL}")

    response = session.get(
        API_LIST_URL, timeout=REQUEST_TIMEOUT
    )
    log(f"HTTP Status: {response.status_code}")
    log(
        "Content-Type: "
        f"{response.headers.get('Content-Type', '')}"
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("活動列表回應不是有效 JSON") from exc

    log("")
    log("API JSON 最上層型態：")
    log(type(payload).__name__)

    if isinstance(payload, dict):
        fields = payload.get("fields") or []
        data = payload.get("data", [])
        if not isinstance(data, list):
            data = []

        log(f"fields 數量：{len(fields)}")
        log(f"data 筆數：{len(data)}")

        if (
            fields
            and data
            and all(isinstance(row, (list, tuple)) for row in data)
        ):
            field_names = []
            for field in fields:
                if isinstance(field, dict):
                    field_name = (
                        field.get("name")
                        or field.get("title")
                        or field.get("field")
                        or ""
                    )
                else:
                    field_name = str(field)
                field_names.append(field_name)

            log("")
            log("API 欄位：")
            for index, name in enumerate(field_names):
                log(f"  [{index}] {name}")

            return [
                dict(zip(field_names, row))
                for row in data
            ]

        if all(isinstance(item, dict) for item in data):
            return data
        return data

    if isinstance(payload, list):
        if all(isinstance(item, dict) for item in payload):
            return payload

        events = []
        for row in payload:
            if (
                not isinstance(row, (list, tuple))
                or len(row) < 3
            ):
                continue

            events.append({
                "項次": row[0],
                "活動主題": row[1],
                "zhId": row[2],
                "enId": row[3] if len(row) > 3 else "",
            })
        return events

    return []


def get_event_title(event):
    if not isinstance(event, dict):
        return ""

    for key in (
        "活動主題", "活動名稱", "title", "name", "eventName"
    ):
        value = event.get(key)
        if value:
            return clean_text(value)
    return ""


def get_event_id(event):
    if not isinstance(event, dict):
        return ""

    for key in ("zhId", "id", "eventId"):
        value = event.get(key)
        if value:
            return str(value).strip()
    return ""


def is_listed_company_conference(title):
    title = clean_text(title)
    if not title:
        return False
    if "創新板" in title:
        return False
    return "上市公司" in title and "法人說明會" in title


def filter_conference_events(events):
    matched = []

    log("")
    log("=" * 72)
    log("[2] 篩選上市公司法人說明會")
    log("=" * 72)

    for event in events:
        title = get_event_title(event)
        if is_listed_company_conference(title):
            matched.append(event)

    return matched


def print_all_events(events):
    log("")
    log("=" * 72)
    log("===== ALL EVENTS =====")
    log("=" * 72)

    for index, event in enumerate(events, start=1):
        title = get_event_title(event)
        event_id = get_event_id(event)

        if "創新板" in title:
            category = "創新板公司法人說明會"
        elif "上市公司" in title and "法人說明會" in title:
            category = "上市公司法人說明會"
        else:
            category = "其他"

        log(
            f"[{index}] {category} | "
            f"{title} | zhId={event_id}"
        )


def print_selected_events(events):
    log("")
    log("=" * 72)
    log("===== SELECTED LISTED COMPANY EVENTS =====")
    log("=" * 72)

    for index, event in enumerate(events, start=1):
        log(f"[{index}] {get_event_title(event)}")
        log(f"    zhId: {get_event_id(event)}")


# ============================================================
# 附件搜尋、詳細標題與下載
# ============================================================

def collect_strings(obj, output):
    if isinstance(obj, str):
        output.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            collect_strings(value, output)
    elif isinstance(obj, list):
        for value in obj:
            collect_strings(value, output)


def extension_from_url(url):
    path = urlparse(url).path.lower()
    for extension in SUPPORTED_EXTENSIONS:
        if path.endswith(extension):
            return extension[1:]
    return ""


def find_attachment_links(detail_payload):
    strings = []
    collect_strings(detail_payload, strings)
    found = []

    for content in strings:
        soup = BeautifulSoup(content, "html.parser")

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "").strip()
            if not href:
                continue

            absolute_url = urljoin(
                "https://www.twse.com.tw", href
            )
            extension = extension_from_url(absolute_url)

            if extension:
                found.append({
                    "url": absolute_url,
                    "format": extension,
                    "link_text": clean_text(
                        anchor.get_text(" ")
                    ),
                })

        decoded = soup.get_text(" ")
        for candidate in re.findall(
            r"""https?://[^\s"'<>]+""",
            decoded,
            re.IGNORECASE,
        ):
            candidate = candidate.rstrip(".,);]}>")
            extension = extension_from_url(candidate)
            if extension:
                found.append({
                    "url": candidate,
                    "format": extension,
                    "link_text": "",
                })

    unique = []
    seen = set()

    for item in found:
        url = item["url"]
        host = (urlparse(url).hostname or "").lower()

        if host not in ("www.twse.com.tw", "twse.com.tw"):
            continue
        if url in seen:
            continue

        seen.add(url)
        unique.append(item)

    return unique


def get_detail_title(payload):
    if not isinstance(payload, dict):
        return ""

    for key in ("title", "活動主題", "name"):
        if payload.get(key):
            return clean_text(payload[key])

    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("title", "活動主題", "name"):
            if data.get(key):
                return clean_text(data[key])

    return ""


def download_attachment(attachment, event_index, attachment_index):
    url = attachment["url"]
    expected_format = attachment["format"]

    log("")
    log(f"附件 {attachment_index}：{expected_format.upper()}")
    log(f"URL: {url}")

    response = session.get(url, timeout=REQUEST_TIMEOUT)
    log(f"HTTP: {response.status_code}")
    log(
        "Content-Type: "
        + response.headers.get("Content-Type", "")
    )
    log(f"Size: {len(response.content)} bytes")
    response.raise_for_status()

    content = response.content
    if not content:
        raise RuntimeError("附件內容為空")

    if expected_format == "docx":
        if not zipfile.is_zipfile(BytesIO(content)):
            raise RuntimeError(
                "連結副檔名是 DOCX，但下載內容不是有效 ZIP/DOCX。"
            )
    elif expected_format == "pdf":
        if not content.lstrip().startswith(b"%PDF-"):
            raise RuntimeError(
                "連結副檔名是 PDF，但檔案內容沒有 PDF 標頭。"
            )
    else:
        raise RuntimeError(
            f"不支援的附件格式：{expected_format}"
        )

    FILES_DIR.mkdir(parents=True, exist_ok=True)
    original_name = Path(urlparse(url).path).name

    if not original_name:
        original_name = f"event_{event_index}.{expected_format}"

    filename = safe_filename(
        f"{event_index:02d}_{attachment_index:02d}_{original_name}"
    )
    file_path = FILES_DIR / filename
    file_path.write_bytes(content)

    log(f"附件已保存：{file_path.name}")
    return file_path


# ============================================================
# 表格欄位與表格場次解析
# ============================================================

def normalize_header(value):
    value = clean_text(value)
    value = re.sub(r"[\s\u3000]+", "", value)
    return value.lower()


def find_header_indices(row):
    normalized = [normalize_header(cell) for cell in row]
    code_index = None
    name_index = None

    code_keys = (
        "公司代碼", "股票代碼", "證券代號", "股票代號", "公司編號"
    )
    name_keys = (
        "公司名稱", "公司簡稱", "證券名稱", "股票名稱"
    )

    for index, cell in enumerate(normalized):
        if not cell:
            continue

        if (
            code_index is None
            and any(key in cell for key in code_keys)
        ):
            code_index = index

        if (
            name_index is None
            and any(key in cell for key in name_keys)
        ):
            name_index = index
        elif name_index is None and cell == "公司":
            name_index = index

    if (
        code_index is not None
        and name_index is not None
        and code_index != name_index
    ):
        return code_index, name_index

    return None, None


def find_optional_column(row, keywords):
    for index, cell in enumerate(row):
        normalized = normalize_header(cell)
        if any(keyword in normalized for keyword in keywords):
            return index
    return None


def find_all_header_indices(row):
    code_index, name_index = find_header_indices(row)

    return {
        "code": code_index,
        "name": name_index,
        "sequence": find_optional_column(
            row, ("項次", "序號", "編號")
        ),
        "date": find_optional_column(
            row, ("日期", "說明會日期", "舉辦日期")
        ),
        "time": find_optional_column(
            row, ("時段", "時間", "說明會時間")
        ),
        "venue": find_optional_column(
            row, ("場地", "地點", "會議地點")
        ),
        "notes": find_optional_column(
            row, ("備註", "說明")
        ),
    }


def parse_table_sessions(tables, event_title, event_id, file_format):
    sessions = []

    for table_info in tables:
        rows = (
            table_info.get("rows", [])
            if isinstance(table_info, dict)
            else table_info
        )
        headers = None

        for row in rows:
            candidate = find_all_header_indices(row)

            if (
                candidate["code"] is not None
                and candidate["name"] is not None
            ):
                headers = candidate
                log(
                    "辨識到表格標題："
                    f"代碼欄={candidate['code']}，"
                    f"名稱欄={candidate['name']}，"
                    f"標題列={row}"
                )
                continue

            if headers is None:
                continue

            code_index = headers["code"]
            name_index = headers["name"]

            if (
                code_index is None
                or code_index >= len(row)
                or name_index is None
                or name_index >= len(row)
            ):
                continue

            code_cell = clean_text(row[code_index])
            code_match = CODE_PATTERN.fullmatch(code_cell)
            if not code_match:
                continue

            stock_code = code_match.group(1)
            company_name = clean_text(row[name_index])
            normalized_name = normalize_header(company_name)

            if any(
                keyword in normalized_name
                for keyword in (
                    "公司名稱", "公司代碼", "股票代碼",
                    "證券代號", "報到時間", "法說會時間",
                )
            ):
                continue

            sequence_no = first_nonempty(
                row, [headers["sequence"]]
            )
            session_date = first_nonempty(
                row, [headers["date"]]
            )
            session_time = first_nonempty(
                row, [headers["time"]]
            )
            venue = first_nonempty(
                row, [headers["venue"]]
            )
            notes = first_nonempty(
                row, [headers["notes"]]
            )

            joined_row = " ".join(
                clean_text(cell) for cell in row
            )

            if not session_date:
                date_match = DATE_PATTERN.search(joined_row)
                if date_match:
                    session_date = date_match.group(0)

            if not session_time:
                time_match = TIME_PATTERN.search(joined_row)
                if time_match:
                    session_time = time_match.group(0)

            if not notes and is_cancelled(joined_row):
                notes = "取消"

            sessions.append(
                make_session(
                    stock_code=stock_code,
                    company_name=company_name,
                    event_title=event_title,
                    event_id=event_id,
                    file_format=file_format,
                    parse_method="table",
                    raw_text=joined_row,
                    sequence_no=sequence_no,
                    session_date=session_date,
                    session_time=session_time,
                    venue=venue,
                    notes=notes,
                )
            )

    log(
        "表格解析完成："
        f"共辨識 {len(sessions)} 筆公司場次"
    )
    return sessions


# ============================================================
# 場次去重與品質統計
# ============================================================

def deduplicate_sessions(sessions):
    output = []
    seen = set()

    for item in sessions:
        code = clean_text(item.get("stock_code"))
        name = clean_text(item.get("company_name"))
        event_id = clean_text(item.get("event_id"))
        session_date = clean_text(item.get("date"))
        session_time = clean_text(item.get("time"))
        sequence_no = clean_text(item.get("sequence_no"))
        raw_text = clean_text(item.get("raw_text"))

        if not code:
            continue

        key = (
            event_id, code, name, session_date,
            session_time, sequence_no,
        )

        if not session_date and not session_time:
            key += (raw_text,)

        if key in seen:
            continue

        seen.add(key)
        output.append(item)

    return output


def calculate_session_quality(sessions):
    total = len(sessions)

    missing_name = [
        item for item in sessions
        if (
            item.get("company_name_missing")
            or not clean_text(item.get("company_name"))
        )
    ]

    cancelled = [
        item for item in sessions
        if (
            item.get("cancelled")
            or item.get("status") == "cancelled"
        )
    ]

    complete = [
        item for item in sessions
        if (
            clean_text(item.get("stock_code"))
            and clean_text(item.get("company_name"))
            and clean_text(item.get("date"))
            and clean_text(item.get("time"))
        )
    ]

    return {
        "total_sessions": total,
        "complete_sessions": len(complete),
        "missing_company_name_sessions": len(missing_name),
        "cancelled_sessions": len(cancelled),
        "sessions_needing_review": total - len(complete),
    }
