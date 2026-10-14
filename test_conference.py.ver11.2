import datetime
import json
import re
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pdfplumber
import requests
from bs4 import BeautifulSoup
from docx import Document


# ============================================================
# 第十一版 2：證交所法人說明會測試
#
# v11.2 修正：
# 1. 保留 v11.1 活動 API 與活動篩選方式
# 2. 排除創新板法人說明會
# 3. 保留 DOCX / PDF 附件下載及表格輸出
# 4. PDF 文字備援：分離股票代碼、序號、公司名稱
# 5. 解析日期、時間、場地、備註及取消狀態
# 6. 公司名稱缺漏時保留場次，不猜測名稱
# 7. 去重時納入日期及時間，避免誤刪不同場次
# 8. 增加完整、名稱缺漏及取消場次統計
# 9. 不修改正式股票分析系統
# ============================================================


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

API_LIST_URL = (
    "https://www.twse.com.tw/rwd/zh/news/eventList?response=json"
)

API_DETAIL_URL = (
    "https://www.twse.com.tw/rwd/zh/news/eventDetail"
)

OUTPUT_JSON = (
    BASE_DIR / "twse_conference_v11_2_result.json"
)

OUTPUT_TXT = (
    BASE_DIR / "twse_conference_v11_2_sessions.txt"
)

FILES_DIR = (
    BASE_DIR / "twse_conference_v11_2_files"
)

MAX_EVENTS = 30
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/json,"
        "text/plain,"
        "text/html,"
        "*/*"
    ),
    "Referer": (
        "https://www.twse.com.tw/zh/news/eventList"
    ),
}

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 2. 共用工具
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
        url,
        params=params,
        timeout=REQUEST_TIMEOUT,
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
    """將常見的月日文字正規化為 MM-DD；無法辨識則保留原文。"""
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
        if not (1 <= month_num <= 12 and 1 <= day_num <= 31):
            return value

        if year:
            return f"{int(year):04d}-{month_num:02d}-{day_num:02d}"

        return f"{month_num:02d}-{day_num:02d}"
    except ValueError:
        return value


def parse_time(value):
    """保留時段資訊，統一常見的波浪號格式。"""
    value = clean_text(value)
    value = value.replace("～", "~").replace("〜", "~")
    value = value.replace("–", "~").replace("—", "~")
    value = re.sub(r"\s*~\s*", "~", value)
    return value


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
# 3. 取得證交所活動列表
# ============================================================

def get_event_list():
    log("")
    log("=" * 72)
    log("[1] 取得證交所活動列表")
    log("=" * 72)
    log(f"API URL: {API_LIST_URL}")

    response = session.get(
        API_LIST_URL,
        timeout=REQUEST_TIMEOUT,
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
        raise RuntimeError(
            "活動列表回應不是有效 JSON"
        ) from exc

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
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue

            events.append({
                "項次": row[0],
                "活動主題": row[1],
                "zhId": row[2],
                "enId": row[3] if len(row) > 3 else "",
            })

        return events

    return []


# ============================================================
# 4. 活動欄位取得
# ============================================================

def get_event_title(event):
    if not isinstance(event, dict):
        return ""

    for key in (
        "活動主題",
        "活動名稱",
        "title",
        "name",
        "eventName",
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


# ============================================================
# 5. 篩選上市公司法人說明會
# ============================================================

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


# ============================================================
# 6. 活動清單輸出
# ============================================================

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
        elif (
            "上市公司" in title
            and "法人說明會" in title
        ):
            category = "上市公司法人說明會"
        else:
            category = "其他"

        log(
            f"[{index}] {category} | {title} | "
            f"zhId={event_id}"
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
# 7. 附件搜尋
# ============================================================

SUPPORTED_EXTENSIONS = (".docx", ".pdf")


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
                "https://www.twse.com.tw",
                href,
            )

            extension = extension_from_url(absolute_url)

            if extension:
                found.append({
                    "url": absolute_url,
                    "format": extension,
                    "link_text": clean_text(anchor.get_text(" ")),
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


# ============================================================
# 8. 下載附件
# ============================================================

def download_attachment(attachment, event_index, attachment_index):
    url = attachment["url"]
    expected_format = attachment["format"]

    log("")
    log(f"附件 {attachment_index}：{expected_format.upper()}")
    log(f"URL: {url}")

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

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
        raise RuntimeError(f"不支援的附件格式：{expected_format}")

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
# 9. DOCX 解析
# ============================================================

def docx_to_tables_and_text(file_path):
    document = Document(str(file_path))

    paragraphs = []

    for paragraph in document.paragraphs:
        text = clean_text(paragraph.text)

        if text:
            paragraphs.append(text)

    tables = []

    for table_index, table in enumerate(document.tables, start=1):
        table_rows = []

        for row in table.rows:
            cells = [clean_text(cell.text) for cell in row.cells]

            if any(cells):
                table_rows.append(cells)

        if table_rows:
            tables.append({
                "table_index": table_index,
                "rows": table_rows,
            })

    return paragraphs, tables


def print_docx_tables(tables):
    for table in tables:
        log("")
        log("=" * 72)
        log(f"===== DOCX TABLE {table['table_index']} =====")
        log("=" * 72)

        for row_index, row in enumerate(table["rows"], start=1):
            log(f"[R{row_index}] " + " | ".join(row))


# ============================================================
# 10. PDF 解析
# ============================================================

def pdf_to_tables_and_text(file_path):
    all_tables = []
    all_text = []

    with pdfplumber.open(str(file_path)) as pdf:
        page_count = len(pdf.pages)

        for page_number, page in enumerate(pdf.pages, start=1):
            log("")
            log("-" * 72)
            log(f"PDF 第 {page_number} 頁")
            log("-" * 72)

            text = page.extract_text() or ""

            if text.strip():
                text_block = (
                    f"[PDF 第 {page_number} 頁]\n"
                    f"{text.strip()}"
                )
                all_text.append(text_block)

                log("")
                log("PDF TEXT：")
                log(text.strip())

            try:
                page_tables = page.extract_tables() or []
            except Exception as exc:
                log(
                    f"警告：PDF 第 {page_number} 頁表格擷取失敗："
                    f"{exc}"
                )
                page_tables = []

            log("")
            log(
                f"PDF 第 {page_number} 頁表格數："
                f"{len(page_tables)}"
            )

            for table_index, table in enumerate(page_tables, start=1):
                rows = []

                log("")
                log("=" * 72)
                log(
                    f"===== PDF TABLE {table_index} "
                    f"(PAGE {page_number}) ====="
                )
                log("=" * 72)

                for row_index, row in enumerate(table, start=1):
                    cells = [clean_text(cell) for cell in (row or [])]

                    if any(cells):
                        rows.append(cells)
                        log(f"[R{row_index}] " + " | ".join(cells))

                if rows:
                    all_tables.append({
                        "page": page_number,
                        "table_index": table_index,
                        "rows": rows,
                    })

    return page_count, all_text, all_tables


# ============================================================
# 11. 欄位及表格標題辨識
# ============================================================

CODE_PATTERN = re.compile(r"(?<!\d)(\d{4,6})(?!\d)")

DATE_PATTERN = re.compile(
    r"(?:(?:\d{4}\s*年\s*)?"
    r"\d{1,2}\s*月\s*\d{1,2}\s*日)"
)

TIME_PATTERN = re.compile(
    r"\d{1,2}:\d{2}\s*[~～〜–—-]\s*\d{1,2}:\d{2}"
)


def normalize_header(value):
    value = clean_text(value)
    value = re.sub(r"[\s\u3000]+", "", value)
    return value.lower()


def find_header_indices(row):
    normalized = [normalize_header(cell) for cell in row]

    code_index = None
    name_index = None

    code_keys = (
        "公司代碼",
        "股票代碼",
        "證券代號",
        "股票代號",
        "公司編號",
    )

    name_keys = (
        "公司名稱",
        "公司簡稱",
        "證券名稱",
        "股票名稱",
    )

    for index, cell in enumerate(normalized):
        if not cell:
            continue

        if code_index is None and any(
            key in cell for key in code_keys
        ):
            code_index = index

        if name_index is None and any(
            key in cell for key in name_keys
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


# ============================================================
# 12. 從表格辨識公司場次
# ============================================================

def parse_table_sessions(
    tables,
    event_title,
    event_id,
    file_format,
):
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
                    "公司名稱",
                    "公司代碼",
                    "股票代碼",
                    "證券代號",
                    "報到時間",
                    "法說會時間",
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

            # 某些 PDF 的表格擷取會把日期、時間或備註放在
            # 不明確的欄位中；只從該列補找可辨識的值。
            joined_row = " ".join(clean_text(cell) for cell in row)

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

    log(f"表格解析完成：共辨識 {len(sessions)} 筆公司場次")

    return sessions


# ============================================================
# 13. 文字備援辨識
# ============================================================

def parse_pdf_schedule_line(
    line,
    event_title,
    event_id,
):
    """
    解析 PDF 排程文字，例如：
    1456 1 怡華 9 月 3 日 14:00~15:30 101 1F
    6550 9 12 月 11 日 14:00~15:30 101 1F

    不猜測缺漏的公司名稱。
    """

    line = clean_text(line)

    if not line:
        return None

    date_match = DATE_PATTERN.search(line)
    time_match = TIME_PATTERN.search(line)
    code_match = CODE_PATTERN.search(line)

    # PDF 備援必須同時有股票代碼、日期及時段，
    # 避免將頁碼、標題或其他數字列誤認成場次。
    if not code_match or not date_match or not time_match:
        return None

    stock_code = code_match.group(1)

    # 只解析股票代碼與日期之間的區段，
    # 避免把日期、時間、場地納入公司名稱。
    before_date = line[:date_match.start()].strip()
    after_code = before_date[code_match.end():].strip()
    before_code = before_date[:code_match.start()].strip()

    sequence_no = ""
    company_name = ""

    # 格式 A：股票代碼、序號、公司名稱、日期
    # 例如：1456 1 怡華 9 月 3 日 ...
    if after_code:
        tokens = after_code.split()

        if tokens and re.fullmatch(r"\d{1,3}", tokens[0]):
            sequence_no = tokens[0]
            company_name = " ".join(tokens[1:]).strip()
        else:
            company_name = after_code

    # 格式 B：序號、股票代碼、公司名稱、日期
    # 例如：1 1456 怡華 9 月 3 日 ...
    if before_code and re.fullmatch(r"\d{1,3}", before_code):
        sequence_no = before_code
        company_name = after_code

    # 有些資料列在代碼後只有序號，後面直接接日期；
    # 這種情況 company_name 必須維持空字串。
    company_name = clean_text(company_name)

    # 防止序號被錯當成公司名稱。
    if re.fullmatch(r"\d{1,3}", company_name):
        company_name = ""

    session_date = date_match.group(0)
    session_time = time_match.group(0)

    # 取出時間之後的內容作為場地／備註候選文字。
    tail = line[time_match.end():].strip()
    cancelled = is_cancelled(line)

    notes = "取消" if cancelled else ""
    venue = tail

    if cancelled:
        venue = re.sub(r"取消|停辦", "", venue).strip()

    return make_session(
        stock_code=stock_code,
        company_name=company_name,
        event_title=event_title,
        event_id=event_id,
        file_format="pdf",
        parse_method="text_fallback",
        raw_text=line,
        sequence_no=sequence_no,
        session_date=session_date,
        session_time=session_time,
        venue=venue,
        notes=notes,
    )


def parse_text_sessions(
    text_blocks,
    event_title,
    event_id,
    file_format,
):
    sessions = []

    for block in text_blocks:
        for raw_line in block.splitlines():
            line = clean_text(raw_line)

            if not line:
                continue

            # PDF：使用較嚴格的排程列解析器。
            if file_format == "pdf":
                parsed = parse_pdf_schedule_line(
                    line,
                    event_title,
                    event_id,
                )

                if parsed:
                    sessions.append(parsed)

                continue

            # DOCX 文字備援：保留 v11.1 原本的寬鬆方式。
            match = CODE_PATTERN.search(line)

            if not match:
                continue

            code = match.group(1)

            rest = clean_text(
                line[:match.start()]
                + " "
                + line[match.end():]
            ).strip(" |｜\t,，:：-")

            if not rest:
                continue

            if any(
                keyword in rest
                for keyword in (
                    "公司名稱",
                    "公司代碼",
                    "股票代碼",
                    "證券代號",
                    "報名",
                    "場地",
                    "時間",
                    "日期",
                )
            ):
                continue

            company_name = re.split(
                r"\s{2,}|[|｜\t]",
                rest,
                maxsplit=1,
            )[0].strip()

            if re.fullmatch(r"\d{1,3}", company_name):
                company_name = ""

            sessions.append(
                make_session(
                    stock_code=code,
                    company_name=company_name,
                    event_title=event_title,
                    event_id=event_id,
                    file_format=file_format,
                    parse_method="text_fallback",
                    raw_text=line,
                )
            )

    return sessions


# ============================================================
# 14. 場次去重
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

        # 不以股票代碼單獨去重。
        # 同公司不同日期／時間必須保留。
        key = (
            event_id,
            code,
            name,
            session_date,
            session_time,
            sequence_no,
        )

        # 缺少日期及時間時，以原始列輔助判斷，
        # 避免缺漏公司名稱的不同場次被錯誤合併。
        if not session_date and not session_time:
            key += (raw_text,)

        if key in seen:
            continue

        seen.add(key)
        output.append(item)

    return output


# ============================================================
# 15. 處理單一活動
# ============================================================

def process_event(event, event_index):
    title = get_event_title(event)
    event_id = get_event_id(event)

    result = {
        "event_index": event_index,
        "event_title": title,
        "event_id": event_id,
        "detail_http_status": None,
        "attachments": [],
        "attachment_formats": [],
        "downloaded_files": [],
        "page_count": None,
        "paragraph_count": 0,
        "table_count": 0,
        "session_count": 0,
        "sessions": [],
        "status": "failed",
        "errors": [],
    }

    log("")
    log("=" * 72)
    log(f"處理活動 {event_index}")
    log("=" * 72)
    log(f"活動：{title}")
    log(f"zhId：{event_id}")

    if not event_id:
        result["errors"].append("活動缺少 zhId")
        return result

    try:
        detail_response = session.get(
            API_DETAIL_URL,
            params={
                "id": event_id,
                "response": "json",
            },
            timeout=REQUEST_TIMEOUT,
        )

        result["detail_http_status"] = detail_response.status_code

        log(f"詳細資料 HTTP：{detail_response.status_code}")
        detail_response.raise_for_status()

        try:
            detail_payload = detail_response.json()
        except ValueError as exc:
            raise RuntimeError("詳細資料不是有效 JSON") from exc

        detail_title = get_detail_title(detail_payload)

        if detail_title:
            result["detail_title"] = detail_title
            log(f"詳細資料標題：{detail_title}")

        attachments = find_attachment_links(detail_payload)

        if not attachments:
            raise RuntimeError(
                "詳細資料中找不到 DOCX 或 PDF 連結。"
            )

        result["attachments"] = attachments
        result["attachment_formats"] = [
            item["format"] for item in attachments
        ]

        log("")
        log(f"找到附件：{len(attachments)}")

        for attachment in attachments:
            log(
                f"  {attachment['format'].upper()} "
                f"{attachment['url']}"
            )

        combined_sessions = []

        for attachment_index, attachment in enumerate(
            attachments,
            start=1,
        ):
            try:
                file_path = download_attachment(
                    attachment,
                    event_index,
                    attachment_index,
                )

                result["downloaded_files"].append({
                    "path": str(file_path.relative_to(BASE_DIR)),
                    "format": attachment["format"],
                    "url": attachment["url"],
                })

                file_format = attachment["format"]

                # ------------------------------------------------
                # DOCX
                # ------------------------------------------------
                if file_format == "docx":
                    paragraphs, tables = docx_to_tables_and_text(
                        file_path
                    )

                    result["paragraph_count"] += len(paragraphs)
                    result["table_count"] += len(tables)

                    log("")
                    log(f"DOCX 段落：{len(paragraphs)}")
                    log(f"DOCX 表格：{len(tables)}")

                    print_docx_tables(tables)

                    table_sessions = parse_table_sessions(
                        tables,
                        title,
                        event_id,
                        file_format,
                    )

                    # 僅在表格完全未辨識到場次時使用文字備援。
                    if not table_sessions:
                        table_sessions = parse_text_sessions(
                            paragraphs,
                            title,
                            event_id,
                            file_format,
                        )

                    combined_sessions.extend(table_sessions)

                    log(f"DOCX 辨識場次：{len(table_sessions)}")

                # ------------------------------------------------
                # PDF
                # ------------------------------------------------
                elif file_format == "pdf":
                    page_count, text_blocks, tables = (
                        pdf_to_tables_and_text(file_path)
                    )

                    result["page_count"] = (
                        (result["page_count"] or 0) + page_count
                    )
                    result["table_count"] += len(tables)

                    log("")
                    log(f"PDF 頁數：{page_count}")
                    log(f"PDF 表格：{len(tables)}")

                    table_sessions = parse_table_sessions(
                        tables,
                        title,
                        event_id,
                        file_format,
                    )

                    # 表格未辨識到場次才使用 PDF 文字備援。
                    if not table_sessions:
                        table_sessions = parse_text_sessions(
                            text_blocks,
                            title,
                            event_id,
                            file_format,
                        )

                    combined_sessions.extend(table_sessions)

                    log(f"PDF 辨識場次：{len(table_sessions)}")

                    if not any(block.strip() for block in text_blocks):
                        result["errors"].append(
                            "PDF 未擷取到可搜尋文字；可能是掃描影像。"
                        )

            except Exception as exc:
                error = (
                    f"附件處理失敗（"
                    f"{attachment.get('format', 'unknown')}）："
                    f"{type(exc).__name__}: {exc}"
                )

                result["errors"].append(error)
                log("ERROR：" + error)

        result["sessions"] = deduplicate_sessions(combined_sessions)
        result["session_count"] = len(result["sessions"])

        if result["downloaded_files"] and result["session_count"] > 0:
            result["status"] = "success"

        elif result["downloaded_files"]:
            result["status"] = "downloaded_but_no_sessions"
            result["errors"].append(
                "附件下載成功，但尚未辨識到公司場次。"
            )

        else:
            result["status"] = "failed"

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        result["errors"].append(error)
        log("ERROR：" + error)

    log("")
    log(f"活動狀態：{result['status']}")
    log(f"辨識公司場次：{result['session_count']}")

    return result


# ============================================================
# 16. 場次品質統計
# ============================================================

def calculate_session_quality(sessions):
    total = len(sessions)

    missing_name = [
        item for item in sessions
        if item.get("company_name_missing")
        or not clean_text(item.get("company_name"))
    ]

    cancelled = [
        item for item in sessions
        if item.get("cancelled")
        or item.get("status") == "cancelled"
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


# ============================================================
# 17. TXT 報告
# ============================================================

def write_text_report(report):
    lines = [
        "證交所法人說明會測試報告（第十一版 2）",
        f"產生時間：{report['generated_at']}",
        "",
        f"活動列表總筆數：{report['total_event_count']}",
        f"上市公司法人說明會活動筆數：{report['conference_event_count']}",
        f"實際處理活動筆數：{report['processed_event_count']}",
        f"成功處理活動：{report['success_event_count']}",
        f"成功下載附件活動：{report['downloaded_event_count']}",
        f"成功下載 DOCX：{report['docx_event_count']}",
        f"成功下載 PDF：{report['pdf_event_count']}",
        f"辨識法人說明會表格：{report['conference_table_count']}",
        f"辨識公司場次總數：{report['total_session_count']}",
        f"處理錯誤活動：{report['error_event_count']}",
        "",
        "===== 場次資料品質 =====",
        f"完整場次：{report['session_quality']['complete_sessions']}",
        (
            "公司名稱缺漏："
            f"{report['session_quality']['missing_company_name_sessions']}"
        ),
        f"取消場次：{report['session_quality']['cancelled_sessions']}",
        (
            "需要檢查的場次："
            f"{report['session_quality']['sessions_needing_review']}"
        ),
        "",
        "=" * 72,
        "===== ALL EVENTS =====",
        "=" * 72,
        "",
    ]

    for index, event in enumerate(report["all_events"], start=1):
        title = get_event_title(event)
        event_id = get_event_id(event)

        if is_listed_company_conference(title):
            category = "上市公司法人說明會"
        elif "創新板" in title:
            category = "創新板公司法人說明會"
        else:
            category = "其他"

        lines.append(
            f"[{index}] {category} | {title} | zhId={event_id}"
        )

    lines.extend([
        "",
        "=" * 72,
        "===== SELECTED EVENTS =====",
        "=" * 72,
    ])

    for item in report["events"]:
        lines.extend([
            "",
            f"活動：{item['event_title']}",
            f"zhId：{item['event_id']}",
            f"狀態：{item['status']}",
            "附件格式：" + ", ".join(item.get("attachment_formats", [])),
            f"辨識場次：{item['session_count']}",
        ])

        for session_item in item["sessions"]:
            name = session_item.get("company_name") or "【公司名稱缺漏】"
            cancelled_mark = (
                "【取消】" if session_item.get("cancelled") else ""
            )

            lines.append(
                "  "
                f"{session_item.get('sequence_no', '')} "
                f"{session_item['stock_code']} "
                f"{name} "
                f"{session_item.get('date', '')} "
                f"{session_item.get('time', '')} "
                f"{session_item.get('venue', '')} "
                f"{cancelled_mark} "
                f"[{session_item['source_format'].upper()}] "
                f"[{session_item.get('parse_method', '')}]"
            )

            if session_item.get("company_name_missing"):
                lines.append(
                    f"    待確認原始資料：{session_item.get('raw_text', '')}"
                )

        for error in item["errors"]:
            lines.append(f"  錯誤／警告：{error}")

    lines.extend([
        "",
        "=" * 72,
        "===== ALL SESSIONS =====",
        "=" * 72,
    ])

    for item in report["sessions"]:
        name = item.get("company_name") or "【公司名稱缺漏】"
        cancelled_mark = "【取消】" if item.get("cancelled") else ""

        lines.append(
            f"{item.get('sequence_no', '')} "
            f"{item['stock_code']} "
            f"{name} | "
            f"{item.get('date', '')} | "
            f"{item.get('time', '')} | "
            f"{item.get('venue', '')} | "
            f"{item.get('notes', '')} "
            f"{cancelled_mark} | "
            f"{item['event_title']} | "
            f"{item['source_format'].upper()}"
        )

    lines.extend([
        "",
        "=" * 72,
        "===== SUMMARY =====",
        "=" * 72,
        f"活動列表總筆數：{report['total_event_count']}",
        f"上市公司法人說明會活動筆數：{report['conference_event_count']}",
        f"實際處理活動筆數：{report['processed_event_count']}",
        f"成功處理活動：{report['success_event_count']}",
        f"成功下載附件活動：{report['downloaded_event_count']}",
        f"成功下載 DOCX：{report['docx_event_count']}",
        f"成功下載 PDF：{report['pdf_event_count']}",
        f"辨識法人說明會表格：{report['conference_table_count']}",
        f"辨識公司場次總數：{report['total_session_count']}",
        f"處理錯誤活動：{report['error_event_count']}",
        f"完整場次：{report['session_quality']['complete_sessions']}",
        (
            "公司名稱缺漏："
            f"{report['session_quality']['missing_company_name_sessions']}"
        ),
        f"取消場次：{report['session_quality']['cancelled_sessions']}",
        (
            "需要檢查的場次："
            f"{report['session_quality']['sessions_needing_review']}"
        ),
    ])

    OUTPUT_TXT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


# ============================================================
# 18. 主程式
# ============================================================

def main():
    log("")
    log("=" * 72)
    log("證交所法人說明會測試：第十一版 2")
    log("支援 DOCX / PDF")
    log("排除創新板公司法人說明會")
    log("=" * 72)

    report = {
        "version": "11.2",
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "list_api_url": API_LIST_URL,
        "total_event_count": 0,
        "conference_event_count": 0,
        "processed_event_count": 0,
        "success_event_count": 0,
        "downloaded_event_count": 0,
        "docx_event_count": 0,
        "pdf_event_count": 0,
        "conference_table_count": 0,
        "total_session_count": 0,
        "error_event_count": 0,
        "session_quality": {
            "total_sessions": 0,
            "complete_sessions": 0,
            "missing_company_name_sessions": 0,
            "cancelled_sessions": 0,
            "sessions_needing_review": 0,
        },
        "all_events": [],
        "events": [],
        "sessions": [],
    }

    try:
        # ----------------------------------------------------
        # [1] 取得活動列表
        # ----------------------------------------------------
        events = get_event_list()

        report["total_event_count"] = len(events)
        report["all_events"] = events

        log("")
        log(f"回傳活動筆數：{len(events)}")

        print_all_events(events)

        # ----------------------------------------------------
        # [2] 篩選上市公司法人說明會
        # ----------------------------------------------------
        conference_events = filter_conference_events(events)

        report["conference_event_count"] = len(conference_events)

        log("")
        log(
            "上市公司法人說明會活動筆數："
            f"{len(conference_events)}"
        )

        print_selected_events(conference_events)

        conference_events = conference_events[:MAX_EVENTS]

        log("")
        log(f"本次最多處理：{MAX_EVENTS} 個活動")

        # ----------------------------------------------------
        # [3] 處理活動
        # ----------------------------------------------------
        log("")
        log("=" * 72)
        log("[3] 查詢詳細資料、下載 DOCX/PDF 並解析")
        log("=" * 72)

        for index, event in enumerate(conference_events, start=1):
            result = process_event(event, index)
            report["events"].append(result)

        report["processed_event_count"] = len(report["events"])

        # ----------------------------------------------------
        # 統計活動處理結果
        # ----------------------------------------------------
        report["success_event_count"] = sum(
            1 for item in report["events"]
            if item["status"] == "success"
        )

        report["downloaded_event_count"] = sum(
            1 for item in report["events"]
            if item["downloaded_files"]
        )

        report["docx_event_count"] = sum(
            1 for item in report["events"]
            if any(
                attachment["format"] == "docx"
                for attachment in item["downloaded_files"]
            )
        )

        report["pdf_event_count"] = sum(
            1 for item in report["events"]
            if any(
                attachment["format"] == "pdf"
                for attachment in item["downloaded_files"]
            )
        )

        # ----------------------------------------------------
        # 合併所有場次
        # ----------------------------------------------------
        for item in report["events"]:
            report["sessions"].extend(item["sessions"])

        report["total_session_count"] = len(report["sessions"])

        # ----------------------------------------------------
        # 表格活動統計
        # ----------------------------------------------------
        report["conference_table_count"] = sum(
            1 for item in report["events"]
            if item["table_count"] > 0
        )

        report["error_event_count"] = sum(
            1 for item in report["events"]
            if item["status"] != "success"
        )

        # ----------------------------------------------------
        # 資料品質統計
        # ----------------------------------------------------
        report["session_quality"] = calculate_session_quality(
            report["sessions"]
        )

    except Exception as exc:
        report["fatal_error"] = f"{type(exc).__name__}: {exc}"

        log("")
        log("程式發生重大錯誤：" + report["fatal_error"])

    finally:
        # ----------------------------------------------------
        # [4] 儲存 JSON 與 TXT
        # ----------------------------------------------------
        log("")
        log("=" * 72)
        log("[4] 產生 JSON 與文字報告")
        log("=" * 72)

        save_json(report)
        write_text_report(report)

        # ----------------------------------------------------
        # [5] Summary
        # ----------------------------------------------------
        log("")
        log("=" * 72)
        log("[5] 第十一版 2 測試摘要")
        log("=" * 72)

        for key, label in (
            ("total_event_count", "活動列表總筆數"),
            ("conference_event_count", "上市公司法人說明會活動筆數"),
            ("processed_event_count", "實際處理活動筆數"),
            ("success_event_count", "成功處理活動"),
            ("downloaded_event_count", "成功下載附件活動"),
            ("docx_event_count", "成功下載 DOCX"),
            ("pdf_event_count", "成功下載 PDF"),
            ("conference_table_count", "辨識法人說明會表格"),
            ("total_session_count", "辨識公司場次總數"),
            ("error_event_count", "處理錯誤活動"),
        ):
            log(f"{label}：{report[key]}")

        log("")
        log("場次資料品質：")

        for key, label in (
            ("complete_sessions", "完整場次"),
            ("missing_company_name_sessions", "公司名稱缺漏"),
            ("cancelled_sessions", "取消場次"),
            ("sessions_needing_review", "需要檢查的場次"),
        ):
            log(f"{label}：{report['session_quality'][key]}")

        log("")
        log("輸出檔案：")
        log(f"- {OUTPUT_JSON.name}")
        log(f"- {OUTPUT_TXT.name}")
        log(f"- {FILES_DIR.name}/")
        log("")
        log("第十一版 2 測試完成。")


if __name__ == "__main__":
    main()
