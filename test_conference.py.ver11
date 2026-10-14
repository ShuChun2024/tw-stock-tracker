import datetime
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pdfplumber
import requests
from bs4 import BeautifulSoup
from docx import Document


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

BASE_URL = "https://www.twse.com.tw"

API_LIST_URL = (
    "https://www.twse.com.tw/rwd/zh/news/eventList?response=json"
)

API_DETAIL_URL = (
    "https://www.twse.com.tw/rwd/zh/news/eventDetail"
)

OUTPUT_JSON = BASE_DIR / "twse_conference_v11_result.json"
OUTPUT_TXT = BASE_DIR / "twse_conference_v11_sessions.txt"
FILES_DIR = BASE_DIR / "twse_conference_v11_files"

MAX_EVENTS = 30
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,*/*",
}

# 僅允許 4 位數股票代碼
CODE_PATTERN = re.compile(
    r"(?<!\d)(\d{4})(?!\d)"
)

DATE_PATTERN = re.compile(
    r"\d{1,2}\s*月\s*\d{1,2}\s*日"
)

TIME_PATTERN = re.compile(
    r"\d{1,2}\s*:\s*\d{2}\s*[~～\-–—]\s*"
    r"\d{1,2}\s*:\s*\d{2}"
)


# ============================================================
# 2. 文字工具
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
    )

    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def normalize_text(value):
    text = clean_text(value)

    replacements = {
        "：": ":",
        "～": "~",
        "－": "-",
        "–": "-",
        "—": "-",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def normalize_header(value):
    text = normalize_text(value)

    text = (
        text
        .replace(" ", "")
        .replace("\t", "")
        .replace("\n", "")
        .replace("（", "(")
        .replace("）", ")")
    )

    return text


def normalize_date(value):
    text = normalize_text(value)

    text = re.sub(
        r"(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        r"\1月\2日",
        text,
    )

    return text


def normalize_time(value):
    text = normalize_text(value)

    text = re.sub(r"\s+", "", text)

    return text


def extract_stock_code(value):
    text = clean_text(value)

    match = CODE_PATTERN.search(text)

    if not match:
        return None

    return match.group(1)


def is_valid_stock_code(value):
    if not value:
        return False

    return bool(
        re.fullmatch(r"\d{4}", str(value))
    )


def extract_date(value):
    text = normalize_date(value)

    match = DATE_PATTERN.search(text)

    if not match:
        return None

    return match.group(0)


def extract_time(value):
    text = normalize_time(value)

    match = TIME_PATTERN.search(text)

    if not match:
        return None

    return match.group(0)


def table_to_text(table):
    lines = []

    for row in table:
        cells = [
            clean_text(cell)
            for cell in row
        ]

        while cells and cells[-1] == "":
            cells.pop()

        if not cells:
            continue

        lines.append(
            " | ".join(cells)
        )

    return "\n".join(lines)


# ============================================================
# 3. 活動資訊
# ============================================================

def get_event_title(event):
    if not isinstance(event, dict):
        return ""

    possible_keys = [
        "title",
        "eventTitle",
        "event_title",
        "name",
        "subject",
        "eventName",
    ]

    for key in possible_keys:
        value = event.get(key)

        if value:
            return clean_text(value)

    return ""


def get_event_id(event):
    if not isinstance(event, dict):
        return ""

    possible_keys = [
        "eventId",
        "event_id",
        "id",
        "EVENT_ID",
    ]

    for key in possible_keys:
        value = event.get(key)

        if value:
            return str(value).strip()

    return ""


# ============================================================
# 4. 只保留「上市公司辦理法人說明會」
# ============================================================

def filter_conference_events(events):
    matched = []

    for event in events:
        title = get_event_title(event)

        # 只抓上市公司每月法人說明會
        #
        # 例如：
        # 2026年上市公司辦理法人說明會
        # [更新]2026年上市公司辦理法人說明會
        #
        # 不抓：
        # 創新板公司法人說明會
        if "上市公司辦理法人說明會" in title:
            matched.append(event)

    return matched


# ============================================================
# 5. TWSE 活動列表
# ============================================================

def fetch_event_list():
    print()
    print("===== FETCH EVENT LIST =====")

    response = requests.get(
        API_LIST_URL,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        possible_keys = [
            "data",
            "result",
            "events",
            "list",
        ]

        for key in possible_keys:
            value = data.get(key)

            if isinstance(value, list):
                return value

    raise RuntimeError(
        "無法從 TWSE eventList 找到活動列表。"
    )


# ============================================================
# 6. TWSE 活動詳細資料
# ============================================================

def fetch_event_detail(event_id):

    params = {
        "eventId": event_id,
        "response": "json",
    }

    response = requests.get(
        API_DETAIL_URL,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    text = response.text

    if "json" in content_type:
        try:
            return (
                response.json(),
                response.status_code,
            )
        except Exception:
            pass

    try:
        return (
            response.json(),
            response.status_code,
        )
    except Exception:
        return (
            text,
            response.status_code,
        )


# ============================================================
# 7. 找 DOCX / PDF 附件
# ============================================================

def find_attachment_links(data):

    found = []

    def walk(value):

        if isinstance(value, dict):

            for key, item in value.items():

                if isinstance(item, str):

                    lower = item.lower()

                    if (
                        ".docx" in lower
                        or ".pdf" in lower
                    ):
                        found.append({
                            "url": item,
                            "key": key,
                        })

                walk(item)

        elif isinstance(value, list):

            for item in value:
                walk(item)

        elif isinstance(value, str):

            urls = re.findall(
                r'https?://[^\s"\'<>]+',
                value,
            )

            for url in urls:

                lower = url.lower()

                if (
                    ".docx" in lower
                    or ".pdf" in lower
                ):
                    found.append({
                        "url": url,
                        "key": "",
                    })

    walk(data)

    return found


def find_attachment_links_from_html(
    html,
    base_url,
):

    found = []

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for tag in soup.find_all("a"):

        href = tag.get("href")

        if not href:
            continue

        url = urljoin(
            base_url,
            href,
        )

        lower = url.lower()

        if (
            ".docx" in lower
            or ".pdf" in lower
        ):

            found.append({
                "url": url,
                "link_text": clean_text(
                    tag.get_text()
                ),
            })

    return found


def deduplicate_attachments(
    attachments
):

    result = []
    seen = set()

    for item in attachments:

        url = item.get("url")

        if not url:
            continue

        if url in seen:
            continue

        seen.add(url)

        result.append(item)

    return result


# ============================================================
# 8. 判斷附件格式
# ============================================================

def detect_file_format(
    url,
    content,
):

    path = urlparse(url).path.lower()

    if path.endswith(".docx"):
        return "docx"

    if path.endswith(".pdf"):
        return "pdf"

    # DOCX 本質上是 ZIP
    if content.startswith(b"PK"):
        return "docx"

    # PDF Magic Number
    if content.startswith(b"%PDF"):
        return "pdf"

    return None


# ============================================================
# 9. 下載附件
# ============================================================

def download_attachment(
    url,
    output_path,
):

    print(
        f"    下載：{url}"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    content = response.content

    file_format = detect_file_format(
        url,
        content,
    )

    if not file_format:
        raise RuntimeError(
            "無法判斷附件格式。"
        )

    output_path.write_bytes(
        content
    )

    return {
        "format": file_format,
        "size": len(content),
    }


# ============================================================
# 10. DOCX 讀取
# ============================================================

def extract_docx(
    document_path
):

    document = Document(
        document_path
    )

    paragraphs = []

    for paragraph in document.paragraphs:

        text = clean_text(
            paragraph.text
        )

        if text:
            paragraphs.append(text)

    tables = []

    for table in document.tables:

        rows = []

        for row in table.rows:

            cells = [
                clean_text(
                    cell.text
                )
                for cell in row.cells
            ]

            rows.append(cells)

        tables.append(rows)

    return {
        "paragraphs": paragraphs,
        "tables": tables,
    }


# ============================================================
# 11. 法說會表格欄位定義
# ============================================================

CODE_HEADERS = {
    "公司代碼",
    "股票代碼",
    "股票代號",
    "證券代號",
    "證券代碼",
}

NAME_HEADERS = {
    "公司名稱",
    "公司簡稱",
    "證券名稱",
}

DATE_HEADERS = {
    "日期",
    "日期(月/日)",
    "日期(月／日)",
    "日期（月／日）",
    "日期(月／日)",
}

TIME_HEADERS = {
    "時段",
    "時間",
}


# ============================================================
# 12. 找表格標題
# ============================================================

def find_header_indices(row):

    code_index = None
    name_index = None
    date_index = None
    time_index = None

    for index, cell in enumerate(row):

        header = normalize_header(
            cell
        )

        if header in CODE_HEADERS:
            code_index = index

        elif header in NAME_HEADERS:
            name_index = index

        elif header in DATE_HEADERS:
            date_index = index

        elif header in TIME_HEADERS:
            time_index = index

    return (
        code_index,
        name_index,
        date_index,
        time_index,
    )


def is_schedule_header(row):

    (
        code_index,
        name_index,
        date_index,
        time_index,
    ) = find_header_indices(row)

    return (
        code_index is not None
        and name_index is not None
        and date_index is not None
        and time_index is not None
    )


# ============================================================
# 13. 解析正式法人說明會表格
# ============================================================

def parse_schedule_table(
    table,
    event_title,
    event_id,
    file_format,
    source_name,
    source_page=None,
    source_table=None,
):

    sessions = []

    header = None
    header_row_index = None

    # --------------------------------------------------------
    # 尋找真正的法人說明會表頭
    # --------------------------------------------------------

    for row_index, row in enumerate(table):

        if is_schedule_header(row):

            header = find_header_indices(
                row
            )

            header_row_index = row_index

            break

    # 沒有完整表頭
    if not header:

        return {
            "is_schedule_table": False,
            "sessions": [],
            "header_row_index": None,
        }

    (
        code_index,
        name_index,
        date_index,
        time_index,
    ) = header

    # --------------------------------------------------------
    # 解析表頭以下資料
    # --------------------------------------------------------

    for row in table[
        header_row_index + 1:
    ]:

        if not row:
            continue

        cells = [
            clean_text(cell)
            for cell in row
        ]

        required_indexes = [
            code_index,
            name_index,
            date_index,
            time_index,
        ]

        if any(
            index >= len(cells)
            for index in required_indexes
        ):
            continue

        code_cell = cells[
            code_index
        ]

        name_cell = cells[
            name_index
        ]

        date_cell = cells[
            date_index
        ]

        time_cell = cells[
            time_index
        ]

        stock_code = extract_stock_code(
            code_cell
        )

        company_name = clean_text(
            name_cell
        )

        date_value = extract_date(
            date_cell
        )

        time_value = extract_time(
            time_cell
        )

        # ----------------------------------------------------
        # 嚴格驗證
        # ----------------------------------------------------

        if not is_valid_stock_code(
            stock_code
        ):
            continue

        if not company_name:
            continue

        if not date_value:
            continue

        if not time_value:
            continue

        # ----------------------------------------------------
        # 嘗試找場地
        # ----------------------------------------------------

        venue = ""

        for index, cell in enumerate(
            cells
        ):

            if index in (
                code_index,
                name_index,
                date_index,
                time_index,
            ):
                continue

            value = clean_text(
                cell
            )

            if not value:
                continue

            if (
                "1F" in value
                or "2F" in value
                or "3F" in value
                or "4F" in value
                or "5F" in value
                or "樓" in value
                or "館" in value
                or "會議" in value
                or "城中" in value
            ):
                venue = value
                break

        sessions.append({
            "stock_code": stock_code,
            "company_name": company_name,
            "date": date_value,
            "time": time_value,
            "venue": venue,
            "event_title": event_title,
            "event_id": event_id,
            "source_format": file_format,
            "source_name": source_name,
            "source_page": source_page,
            "source_table": source_table,
            "parse_method": "table",
            "raw_row": cells,
        })

    return {
        "is_schedule_table": True,
        "sessions": sessions,
        "header_row_index": header_row_index,
    }


# ============================================================
# 14. DOCX 解析
# ============================================================

def parse_docx_file(
    file_path,
    event_title,
    event_id,
):

    data = extract_docx(
        file_path
    )

    tables = data["tables"]

    sessions = []

    schedule_table_count = 0

    table_reports = []

    # --------------------------------------------------------
    # 印出所有 DOCX 表格
    # --------------------------------------------------------

    for table_index, table in enumerate(
        tables,
        start=1,
    ):

        print()
        print(
            f"===== DOCX TABLE "
            f"{table_index} ====="
        )

        print(
            table_to_text(table)
        )

        parsed = parse_schedule_table(
            table=table,
            event_title=event_title,
            event_id=event_id,
            file_format="docx",
            source_name=file_path.name,
            source_page=None,
            source_table=table_index,
        )

        if parsed[
            "is_schedule_table"
        ]:
            schedule_table_count += 1

        sessions.extend(
            parsed["sessions"]
        )

        table_reports.append({
            "table_index": table_index,
            "is_schedule_table":
                parsed[
                    "is_schedule_table"
                ],
            "session_count":
                len(
                    parsed["sessions"]
                ),
            "rows": table,
        })

    return {
        "paragraphs":
            data["paragraphs"],

        "tables":
            data["tables"],

        "table_reports":
            table_reports,

        "schedule_table_count":
            schedule_table_count,

        "sessions":
            sessions,
    }


# ============================================================
# 15. PDF 表格讀取
# ============================================================

def extract_pdf_tables(
    file_path
):

    pages = []

    with pdfplumber.open(
        file_path
    ) as pdf:

        for page_index, page in enumerate(
            pdf.pages,
            start=1,
        ):

            tables = page.extract_tables()

            page_text = (
                page.extract_text()
                or ""
            )

            pages.append({
                "page_number":
                    page_index,
                "text":
                    page_text,
                "tables":
                    tables or [],
            })

    return pages


# ============================================================
# 16. PDF 嚴格文字 fallback
# ============================================================

def parse_pdf_text_fallback(
    page_text,
    page_number,
    file_path,
    event_title,
    event_id,
):

    sessions = []

    if not page_text:
        return sessions

    # --------------------------------------------------------
    # 非常重要：
    #
    # 只有這一頁同時出現正式表頭，
    # 才允許使用文字 fallback。
    # --------------------------------------------------------

    normalized_page = normalize_header(
        page_text
    )

    has_schedule_header = (
        "公司代碼" in normalized_page
        and "公司名稱" in normalized_page
        and "日期" in normalized_page
        and "時段" in normalized_page
    )

    if not has_schedule_header:
        return sessions

    lines = [
        clean_text(line)
        for line in page_text.splitlines()
    ]

    for line in lines:

        if not line:
            continue

        # 必須同時存在：
        #
        # 4 位股票代碼
        # 日期
        # 時段
        #
        # 才允許繼續。
        stock_code = extract_stock_code(
            line
        )

        date_value = extract_date(
            line
        )

        time_value = extract_time(
            line
        )

        if not stock_code:
            continue

        if not date_value:
            continue

        if not time_value:
            continue

        if not is_valid_stock_code(
            stock_code
        ):
            continue

        code_match = CODE_PATTERN.search(
            line
        )

        if not code_match:
            continue

        # ----------------------------------------------------
        # 股票代碼後面的內容
        # ----------------------------------------------------

        after_code = line[
            code_match.end():
        ].strip()

        date_match = DATE_PATTERN.search(
            after_code
        )

        if not date_match:
            continue

        company_name = after_code[
            :date_match.start()
        ].strip()

        # PDF 有時會把前面的序號一起留下
        company_name = re.sub(
            r"^\d{1,3}\s+",
            "",
            company_name,
        ).strip()

        if not company_name:
            continue

        # 排除表頭
        if (
            "公司名稱" in company_name
            or "公司代碼" in company_name
            or "法人說明會" in company_name
        ):
            continue

        # ----------------------------------------------------
        # 找時間之後的場地
        # ----------------------------------------------------

        after_date = after_code[
            date_match.end():
        ]

        time_match = TIME_PATTERN.search(
            after_date
        )

        if not time_match:
            continue

        venue = after_date[
            time_match.end():
        ].strip()

        sessions.append({
            "stock_code":
                stock_code,

            "company_name":
                company_name,

            "date":
                date_value,

            "time":
                time_value,

            "venue":
                venue,

            "event_title":
                event_title,

            "event_id":
                event_id,

            "source_format":
                "pdf",

            "source_name":
                file_path.name,

            "source_page":
                page_number,

            "source_table":
                None,

            "parse_method":
                "pdf_text_fallback",

            "raw_row":
                [line],
        })

    return sessions


# ============================================================
# 17. PDF 解析
# ============================================================

def parse_pdf_file(
    file_path,
    event_title,
    event_id,
):

    pages = extract_pdf_tables(
        file_path
    )

    sessions = []

    schedule_table_count = 0

    table_reports = []

    fallback_sessions = []

    # --------------------------------------------------------
    # 每一頁
    # --------------------------------------------------------

    for page in pages:

        page_number = page[
            "page_number"
        ]

        page_text = page[
            "text"
        ]

        tables = page[
            "tables"
        ]

        print()
        print(
            f"===== PDF PAGE "
            f"{page_number} ====="
        )

        if not tables:

            print(
                "[沒有偵測到 PDF 表格]"
            )

        # ----------------------------------------------------
        # 印出所有 PDF 表格
        # ----------------------------------------------------

        for table_index, table in enumerate(
            tables,
            start=1,
        ):

            print()
            print(
                f"===== PDF PAGE "
                f"{page_number} "
                f"TABLE {table_index} ====="
            )

            print(
                table_to_text(table)
            )

            parsed = parse_schedule_table(
                table=table,
                event_title=event_title,
                event_id=event_id,
                file_format="pdf",
                source_name=file_path.name,
                source_page=page_number,
                source_table=table_index,
            )

            if parsed[
                "is_schedule_table"
            ]:
                schedule_table_count += 1

            sessions.extend(
                parsed["sessions"]
            )

            table_reports.append({
                "page_number":
                    page_number,

                "table_index":
                    table_index,

                "is_schedule_table":
                    parsed[
                        "is_schedule_table"
                    ],

                "session_count":
                    len(
                        parsed["sessions"]
                    ),

                "rows":
                    table,
            })

        # ----------------------------------------------------
        # PDF 文字 fallback
        # ----------------------------------------------------

        page_fallback_sessions = (
            parse_pdf_text_fallback(
                page_text=page_text,
                page_number=page_number,
                file_path=file_path,
                event_title=event_title,
                event_id=event_id,
            )
        )

        fallback_sessions.extend(
            page_fallback_sessions
        )

    # --------------------------------------------------------
    # 如果正式表格已抓到資料
    # 就不採用 fallback，避免重複。
    #
    # 如果正式表格完全沒有抓到資料，
    # 才使用嚴格 fallback。
    # --------------------------------------------------------

    if sessions:
        final_sessions = sessions
    else:
        final_sessions = fallback_sessions

    return {
        "pages":
            pages,

        "table_reports":
            table_reports,

        "schedule_table_count":
            schedule_table_count,

        "fallback_session_count":
            len(
                fallback_sessions
            ),

        "sessions":
            final_sessions,
    }


# ============================================================
# 18. 場次去重
# ============================================================

def deduplicate_sessions(
    sessions
):

    result = []
    seen = set()

    for session in sessions:

        key = (
            session.get(
                "stock_code"
            ),
            session.get(
                "company_name"
            ),
            session.get(
                "date"
            ),
            session.get(
                "time"
            ),
            session.get(
                "venue"
            ),
        )

        if key in seen:
            continue

        seen.add(key)

        result.append(
            session
        )

    return result


# ============================================================
# 19. TXT 報告
# ============================================================

def write_text_report(
    report_lines
):

    OUTPUT_TXT.write_text(
        "\n".join(
            report_lines
        ),
        encoding="utf-8",
    )


# ============================================================
# 20. 主程式
# ============================================================

def main():

    FILES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "============================================================"
    )

    print(
        "TWSE 法人說明會測試程式 v11"
    )

    print(
        "============================================================"
    )

    generated_at = (
        datetime.datetime.now(
            datetime.timezone.utc
        )
        .astimezone()
        .isoformat()
    )

    report_lines = []

    report_lines.append(
        "證交所法人說明會測試報告（第十一版）"
    )

    report_lines.append(
        f"產生時間：{generated_at}"
    )

    report_lines.append("")

    # ========================================================
    # 取得活動列表
    # ========================================================

    events = fetch_event_list()

    conference_events = (
        filter_conference_events(
            events
        )
    )

    print(
        f"活動列表總筆數："
        f"{len(events)}"
    )

    print(
        "上市公司法人說明會活動筆數："
        f"{len(conference_events)}"
    )

    report_lines.append(
        f"活動列表總筆數："
        f"{len(events)}"
    )

    report_lines.append(
        "上市公司法人說明會活動筆數："
        f"{len(conference_events)}"
    )

    # ========================================================
    # 限制最多處理 MAX_EVENTS
    # ========================================================

    process_events = (
        conference_events[
            :MAX_EVENTS
        ]
    )

    print(
        "實際處理活動筆數："
        f"{len(process_events)}"
    )

    report_lines.append(
        "實際處理活動筆數："
        f"{len(process_events)}"
    )

    # ========================================================
    # JSON 基本結構
    # ========================================================

    result = {
        "version": "v11",
        "generated_at":
            generated_at,

        "event_count":
            len(events),

        "conference_event_count":
            len(conference_events),

        "processed_event_count":
            len(process_events),

        "events": [],
    }

    total_sessions = []

    successful_events = 0
    downloaded_attachment_events = 0
    downloaded_docx = 0
    downloaded_pdf = 0
    error_events = 0
    total_schedule_tables = 0

    # ========================================================
    # 逐一處理活動
    # ========================================================

    for event_index, event in enumerate(
        process_events,
        start=1,
    ):

        title = get_event_title(
            event
        )

        event_id = get_event_id(
            event
        )

        print()
        print(
            "============================================================"
        )

        print(
            f"活動 {event_index}"
        )

        print(
            f"標題：{title}"
        )

        print(
            f"EVENT ID：{event_id}"
        )

        event_result = {
            "event_index":
                event_index,

            "event_title":
                title,

            "event_id":
                event_id,

            "detail_http_status":
                None,

            "attachments":
                [],

            "attachment_formats":
                [],

            "downloaded_files":
                [],

            "page_count":
                None,

            "paragraph_count":
                None,

            "table_count":
                None,

            "schedule_table_count":
                0,

            "session_count":
                0,

            "sessions":
                [],

            "status":
                "",

            "errors":
                [],
        }

        try:

            if not event_id:
                raise RuntimeError(
                    "找不到 event_id"
                )

            # ------------------------------------------------
            # 活動詳細資料
            # ------------------------------------------------

            detail_data, status_code = (
                fetch_event_detail(
                    event_id
                )
            )

            event_result[
                "detail_http_status"
            ] = status_code

            # ------------------------------------------------
            # 找附件
            # ------------------------------------------------

            attachments = (
                find_attachment_links(
                    detail_data
                )
            )

            # API 如果回 HTML
            if isinstance(
                detail_data,
                str,
            ):

                attachments.extend(
                    find_attachment_links_from_html(
                        detail_data,
                        BASE_URL,
                    )
                )

            attachments = (
                deduplicate_attachments(
                    attachments
                )
            )

            event_result[
                "attachments"
            ] = attachments

            if attachments:
                downloaded_attachment_events += 1

            all_event_sessions = []

            # ------------------------------------------------
            # 下載附件
            # ------------------------------------------------

            for attachment_index, attachment in enumerate(
                attachments,
                start=1,
            ):

                url = attachment.get(
                    "url"
                )

                if not url:
                    continue

                parsed_url = urlparse(
                    url
                )

                suffix = Path(
                    parsed_url.path
                ).suffix.lower()

                if suffix not in (
                    ".docx",
                    ".pdf",
                ):
                    continue

                if suffix == ".docx":
                    file_format = "docx"
                else:
                    file_format = "pdf"

                filename = (
                    f"{event_index:03d}_"
                    f"{attachment_index:02d}_"
                    f"{event_id}"
                    f"{suffix}"
                )

                output_path = (
                    FILES_DIR /
                    filename
                )

                try:

                    download_info = (
                        download_attachment(
                            url,
                            output_path,
                        )
                    )

                    event_result[
                        "downloaded_files"
                    ].append({
                        "path":
                            str(
                                output_path
                            ),

                        "format":
                            download_info[
                                "format"
                            ],

                        "size":
                            download_info[
                                "size"
                            ],

                        "url":
                            url,
                    })

                    event_result[
                        "attachment_formats"
                    ].append(
                        file_format
                    )

                    if file_format == "docx":
                        downloaded_docx += 1

                    elif file_format == "pdf":
                        downloaded_pdf += 1

                    # ========================================
                    # DOCX
                    # ========================================

                    if file_format == "docx":

                        parsed_data = (
                            parse_docx_file(
                                output_path,
                                title,
                                event_id,
                            )
                        )

                        event_result[
                            "paragraph_count"
                        ] = len(
                            parsed_data[
                                "paragraphs"
                            ]
                        )

                        event_result[
                            "table_count"
                        ] = len(
                            parsed_data[
                                "tables"
                            ]
                        )

                        event_result[
                            "schedule_table_count"
                        ] += (
                            parsed_data[
                                "schedule_table_count"
                            ]
                        )

                        all_event_sessions.extend(
                            parsed_data[
                                "sessions"
                            ]
                        )

                        # 寫入 TXT
                        report_lines.append(
                            ""
                        )

                        report_lines.append(
                            "============================================================"
                        )

                        report_lines.append(
                            f"活動 {event_index}："
                            f"{title}"
                        )

                        report_lines.append(
                            f"DOCX："
                            f"{output_path.name}"
                        )

                        report_lines.append(
                            ""
                        )

                        report_lines.append(
                            "===== DOCX PARAGRAPHS ====="
                        )

                        report_lines.extend(
                            parsed_data[
                                "paragraphs"
                            ]
                        )

                        for table_report in (
                            parsed_data[
                                "table_reports"
                            ]
                        ):

                            report_lines.append(
                                ""
                            )

                            report_lines.append(
                                "===== DOCX TABLE "
                                f"{table_report['table_index']}"
                                " ====="
                            )

                            report_lines.append(
                                table_to_text(
                                    table_report[
                                        "rows"
                                    ]
                                )
                            )

                            report_lines.append(
                                "是否為法人說明會場次表："
                                f"{table_report['is_schedule_table']}"
                            )

                            report_lines.append(
                                "辨識場次數："
                                f"{table_report['session_count']}"
                            )

                    # ========================================
                    # PDF
                    # ========================================

                    elif file_format == "pdf":

                        parsed_data = (
                            parse_pdf_file(
                                output_path,
                                title,
                                event_id,
                            )
                        )

                        event_result[
                            "page_count"
                        ] = len(
                            parsed_data[
                                "pages"
                            ]
                        )

                        event_result[
                            "schedule_table_count"
                        ] += (
                            parsed_data[
                                "schedule_table_count"
                            ]
                        )

                        all_event_sessions.extend(
                            parsed_data[
                                "sessions"
                            ]
                        )

                        for table_report in (
                            parsed_data[
                                "table_reports"
                            ]
                        ):

                            report_lines.append(
                                ""
                            )

                            report_lines.append(
                                "===== PDF PAGE "
                                f"{table_report['page_number']}"
                                " TABLE "
                                f"{table_report['table_index']}"
                                " ====="
                            )

                            report_lines.append(
                                table_to_text(
                                    table_report[
                                        "rows"
                                    ]
                                )
                            )

                            report_lines.append(
                                "是否為法人說明會場次表："
                                f"{table_report['is_schedule_table']}"
                            )

                            report_lines.append(
                                "辨識場次數："
                                f"{table_report['session_count']}"
                            )

                except Exception as attachment_error:

                    message = (
                        "附件處理失敗："
                        f"{url}；"
                        f"{type(attachment_error).__name__}: "
                        f"{attachment_error}"
                    )

                    print(
                        f"    {message}"
                    )

                    event_result[
                        "errors"
                    ].append(
                        message
                    )

            # ------------------------------------------------
            # 活動內去重
            # ------------------------------------------------

            all_event_sessions = (
                deduplicate_sessions(
                    all_event_sessions
                )
            )

            event_result[
                "sessions"
            ] = all_event_sessions

            event_result[
                "session_count"
            ] = len(
                all_event_sessions
            )

            total_schedule_tables += (
                event_result[
                    "schedule_table_count"
                ]
            )

            total_sessions.extend(
                all_event_sessions
            )

            # ------------------------------------------------
            # 活動狀態
            # ------------------------------------------------

            if event_result[
                "session_count"
            ] > 0:

                event_result[
                    "status"
                ] = "success"

                successful_events += 1

            elif event_result[
                "downloaded_files"
            ]:

                event_result[
                    "status"
                ] = (
                    "downloaded_but_no_sessions"
                )

                event_result[
                    "errors"
                ].append(
                    "附件下載成功，但尚未辨識到法人說明會場次。"
                    "請檢查 TXT 中的實際表格內容。"
                )

            else:

                event_result[
                    "status"
                ] = "no_attachment"

                event_result[
                    "errors"
                ].append(
                    "未找到可下載的 DOCX/PDF 附件。"
                )

            print(
                "辨識場次："
                f"{event_result['session_count']}"
            )

        except Exception as error:

            error_events += 1

            event_result[
                "status"
            ] = "error"

            message = (
                f"{type(error).__name__}: "
                f"{error}"
            )

            event_result[
                "errors"
            ].append(
                message
            )

            print(
                f"處理失敗：{message}"
            )

        result[
            "events"
        ].append(
            event_result
        )

    # ========================================================
    # 全部場次去重
    # ========================================================

    total_sessions = (
        deduplicate_sessions(
            total_sessions
        )
    )

    # ========================================================
    # 所有場次
    # ========================================================

    report_lines.append(
        ""
    )

    report_lines.append(
        "============================================================"
    )

    report_lines.append(
        "===== ALL SESSIONS ====="
    )

    for index, session in enumerate(
        total_sessions,
        start=1,
    ):

        report_lines.append(
            f"{index}. "
            f"{session.get('stock_code', '')} | "
            f"{session.get('company_name', '')} | "
            f"{session.get('date', '')} | "
            f"{session.get('time', '')} | "
            f"{session.get('venue', '')} | "
            f"{session.get('parse_method', '')}"
        )

    # ========================================================
    # Summary
    # ========================================================

    result[
        "successful_event_count"
    ] = successful_events

    result[
        "downloaded_attachment_event_count"
    ] = downloaded_attachment_events

    result[
        "downloaded_docx_count"
    ] = downloaded_docx

    result[
        "downloaded_pdf_count"
    ] = downloaded_pdf

    result[
        "schedule_table_count"
    ] = total_schedule_tables

    result[
        "session_count"
    ] = len(
        total_sessions
    )

    result[
        "error_event_count"
    ] = error_events

    report_lines.append(
        ""
    )

    report_lines.append(
        "============================================================"
    )

    report_lines.append(
        "===== SUMMARY ====="
    )

    report_lines.append(
        f"活動列表總筆數："
        f"{len(events)}"
    )

    report_lines.append(
        "上市公司法人說明會活動筆數："
        f"{len(conference_events)}"
    )

    report_lines.append(
        "實際處理活動筆數："
        f"{len(process_events)}"
    )

    report_lines.append(
        f"成功處理活動："
        f"{successful_events}"
    )

    report_lines.append(
        "成功下載附件活動："
        f"{downloaded_attachment_events}"
    )

    report_lines.append(
        f"成功下載 DOCX："
        f"{downloaded_docx}"
    )

    report_lines.append(
        f"成功下載 PDF："
        f"{downloaded_pdf}"
    )

    report_lines.append(
        "辨識法人說明會表格："
        f"{total_schedule_tables}"
    )

    report_lines.append(
        "辨識公司場次總數："
        f"{len(total_sessions)}"
    )

    report_lines.append(
        f"處理錯誤活動："
        f"{error_events}"
    )

    # ========================================================
    # 寫入 JSON
    # ========================================================

    OUTPUT_JSON.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ========================================================
    # 寫入 TXT
    # ========================================================

    write_text_report(
        report_lines
    )

    # ========================================================
    # 最後輸出
    # ========================================================

    print()
    print(
        "============================================================"
    )

    print(
        "v11 測試完成"
    )

    print(
        f"活動列表總筆數："
        f"{len(events)}"
    )

    print(
        "上市公司法人說明會："
        f"{len(conference_events)}"
    )

    print(
        f"實際處理："
        f"{len(process_events)}"
    )

    print(
        f"成功活動："
        f"{successful_events}"
    )

    print(
        f"DOCX："
        f"{downloaded_docx}"
    )

    print(
        f"PDF："
        f"{downloaded_pdf}"
    )

    print(
        "法人說明會表格："
        f"{total_schedule_tables}"
    )

    print(
        f"辨識場次："
        f"{len(total_sessions)}"
    )

    print(
        f"錯誤活動："
        f"{error_events}"
    )

    print()
    print(
        f"JSON：{OUTPUT_JSON}"
    )

    print(
        f"TXT：{OUTPUT_TXT}"
    )

    print(
        f"附件：{FILES_DIR}"
    )

    # 即使部分活動沒有附件，
    # 也讓 Actions 保留測試結果。
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
