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
# 第十一版 1：證交所法人說明會測試
#
# v11.1 修正：
#
# 1. 修正 TWSE eventList API 實際回傳：
#       fields + data
#       data 每筆為 list / array
#
# 2. 正確將：
#       [項次, 活動主題, zhId, enId]
#    轉換成 event dict
#
# 3. 僅處理：
#       「上市公司辦理法人說明會」
#
# 4. 排除：
#       「創新板公司法人說明會」
#
# 5. 支援 DOCX / PDF
#
# 6. DOCX：
#       解析段落、表格
#
# 7. PDF：
#       解析文字、表格
#       並將 PDF 表格完整印出
#
# 8. 公司場次：
#       優先從表格辨識
#       表格無法辨識時才使用文字備援
#
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
    BASE_DIR / "twse_conference_v11_1_result.json"
)
OUTPUT_TXT = (
    BASE_DIR / "twse_conference_v11_1_sessions.txt"
)
FILES_DIR = (
    BASE_DIR / "twse_conference_v11_1_files"
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
    value = str(value)
    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()
def safe_filename(value):
    value = re.sub(
        r'[\\/:*?"<>|]+',
        "_",
        str(value),
    )
    return value[:100]
def save_json(data):
    OUTPUT_JSON.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
def fetch_json(
    url,
    params=None,
):
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
            f"Content-Type="
            f"{response.headers.get('Content-Type', '')}，"
            f"網址={response.url}"
        ) from exc
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
    log(
        "HTTP Status: "
        f"{response.status_code}"
    )
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
    # --------------------------------------------------------
    # 情況 A：
    #
    # API：
    #
    # {
    #   "fields": [...],
    #   "data": [
    #       [...],
    #       [...]
    #   ]
    # }
    # --------------------------------------------------------
    if isinstance(payload, dict):
        fields = payload.get("fields") or []
        data = payload.get("data", [])
        if not isinstance(data, list):
            data = []
        log("")
        log(
            "fields 數量："
            f"{len(fields)}"
        )
        log(
            "data 筆數："
            f"{len(data)}"
        )
        # ----------------------------------------------------
        # 正確處理 fields + data array
        # ----------------------------------------------------
        if (
            fields
            and data
            and all(
                isinstance(row, (list, tuple))
                for row in data
            )
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
                field_names.append(
                    field_name
                )
            log("")
            log("API 欄位：")
            for index, name in enumerate(
                field_names
            ):
                log(
                    f"  [{index}] {name}"
                )
            events = []
            for row in data:
                event = dict(
                    zip(
                        field_names,
                        row,
                    )
                )
                events.append(event)
            return events
        # ----------------------------------------------------
        # 某些版本可能直接回傳 object list
        # ----------------------------------------------------
        if all(
            isinstance(item, dict)
            for item in data
        ):
            return data
        return data
    # --------------------------------------------------------
    # 情況 B：直接 list
    # --------------------------------------------------------
    if isinstance(payload, list):
        # 已經是 dict list
        if all(
            isinstance(item, dict)
            for item in payload
        ):
            return payload
        # 如果直接是：
        #
        # [
        #   [項次, 活動主題, zhId, enId],
        #   ...
        # ]
        #
        # 嘗試轉換。
        events = []
        for row in payload:
            if not isinstance(
                row,
                (list, tuple),
            ):
                continue
            if len(row) < 3:
                continue
            events.append(
                {
                    "項次": row[0],
                    "活動主題": row[1],
                    "zhId": row[2],
                    "enId": (
                        row[3]
                        if len(row) > 3
                        else ""
                    ),
                }
            )
        return events
    return []
# ============================================================
# 4. 活動欄位取得
# ============================================================
def get_event_title(event):
    if not isinstance(event, dict):
        return ""
    keys = (
        "活動主題",
        "活動名稱",
        "title",
        "name",
        "eventName",
    )
    for key in keys:
        value = event.get(key)
        if value:
            return clean_text(value)
    return ""
def get_event_id(event):
    if not isinstance(event, dict):
        return ""
    keys = (
        "zhId",
        "id",
        "eventId",
    )
    for key in keys:
        value = event.get(key)
        if value:
            return str(value).strip()
    return ""
# ============================================================
# 5. 篩選「上市公司法人說明會」
#
# 注意：
#
# 「創新板公司法人說明會」
# 不屬於本測試要抓的上市公司法人說明會。
# ============================================================
def is_listed_company_conference(
    title,
):
    title = clean_text(title)
    if not title:
        return False
    # --------------------------------------------------------
    # 明確排除創新板
    # --------------------------------------------------------
    if "創新板公司法人說明會" in title:
        return False
    if "創新板" in title:
        return False
    # --------------------------------------------------------
    # 必須是上市公司法人說明會
    # --------------------------------------------------------
    if (
        "上市公司" in title
        and "法人說明會" in title
    ):
        return True
    return False
def filter_conference_events(
    events,
):
    matched = []
    log("")
    log("=" * 72)
    log("[2] 篩選上市公司法人說明會")
    log("=" * 72)
    for event in events:
        title = get_event_title(event)
        event_id = get_event_id(event)
        if is_listed_company_conference(title):
            matched.append(event)
    return matched
# ============================================================
# 6. 顯示所有活動
#
# 這個區段是 v11.1 新增的診斷功能。
# ============================================================
def print_all_events(
    events,
):
    log("")
    log("=" * 72)
    log("===== ALL EVENTS =====")
    log("=" * 72)
    for index, event in enumerate(
        events,
        start=1,
    ):
        title = get_event_title(event)
        event_id = get_event_id(event)
        category = "其他"
        if "創新板" in title:
            category = "創新板公司法人說明會"
        elif (
            "上市公司" in title
            and "法人說明會" in title
        ):
            category = "上市公司法人說明會"
        log(
            f"[{index}] "
            f"{category} | "
            f"{title} | "
            f"zhId={event_id}"
        )
def print_selected_events(
    events,
):
    log("")
    log("=" * 72)
    log("===== SELECTED LISTED COMPANY EVENTS =====")
    log("=" * 72)
    for index, event in enumerate(
        events,
        start=1,
    ):
        title = get_event_title(event)
        event_id = get_event_id(event)
        log(
            f"[{index}] "
            f"{title}"
        )
        log(
            f"    zhId: {event_id}"
        )
# ============================================================
# 7. 附件搜尋
# ============================================================
SUPPORTED_EXTENSIONS = (
    ".docx",
    ".pdf",
)
def collect_strings(
    obj,
    output,
):
    if isinstance(obj, str):
        output.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            collect_strings(
                value,
                output,
            )
    elif isinstance(obj, list):
        for value in obj:
            collect_strings(
                value,
                output,
            )
def extension_from_url(
    url,
):
    path = urlparse(
        url
    ).path.lower()
    for extension in SUPPORTED_EXTENSIONS:
        if path.endswith(extension):
            return extension[1:]
    return ""
def find_attachment_links(
    detail_payload,
):
    strings = []
    collect_strings(
        detail_payload,
        strings,
    )
    found = []
    for content in strings:
        soup = BeautifulSoup(
            content,
            "html.parser",
        )
        # ----------------------------------------------------
        # HTML <a href="">
        # ----------------------------------------------------
        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            href = (
                anchor
                .get("href", "")
                .strip()
            )
            if not href:
                continue
            absolute_url = urljoin(
                "https://www.twse.com.tw",
                href,
            )
            extension = (
                extension_from_url(
                    absolute_url
                )
            )
            if extension:
                found.append(
                    {
                        "url": absolute_url,
                        "format": extension,
                        "link_text": clean_text(
                            anchor.get_text(" ")
                        ),
                    }
                )
        # ----------------------------------------------------
        # 純文字 URL
        # ----------------------------------------------------
        decoded = (
            BeautifulSoup(
                content,
                "html.parser",
            )
            .get_text(" ")
        )
        url_pattern = re.compile(
            r"""https?://[^\s"'<>]+""",
            re.IGNORECASE,
        )
        for match in url_pattern.findall(
            decoded
        ):
            candidate = match.rstrip(
                ".,);]}>"
            )
            extension = (
                extension_from_url(
                    candidate
                )
            )
            if extension:
                found.append(
                    {
                        "url": candidate,
                        "format": extension,
                        "link_text": "",
                    }
                )
    # --------------------------------------------------------
    # 只接受 TWSE
    # --------------------------------------------------------
    unique = []
    seen = set()
    for item in found:
        url = item["url"]
        parsed = urlparse(url)
        host = (
            parsed.hostname or ""
        ).lower()
        if host not in (
            "www.twse.com.tw",
            "twse.com.tw",
        ):
            continue
        if url in seen:
            continue
        seen.add(url)
        unique.append(item)
    return unique
def get_detail_title(
    payload,
):
    if isinstance(payload, dict):
        for key in (
            "title",
            "活動主題",
            "name",
        ):
            value = payload.get(key)
            if value:
                return clean_text(value)
        data = payload.get("data")
        if isinstance(data, dict):
            for key in (
                "title",
                "活動主題",
                "name",
            ):
                value = data.get(key)
                if value:
                    return clean_text(value)
    return ""
# ============================================================
# 8. 下載附件
# ============================================================
def download_attachment(
    attachment,
    event_index,
    attachment_index,
):
    url = attachment["url"]
    expected_format = (
        attachment["format"]
    )
    log("")
    log(
        f"附件 {attachment_index}："
        f"{expected_format.upper()}"
    )
    log(
        f"URL: {url}"
    )
    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )
    log(
        f"HTTP: {response.status_code}"
    )
    log(
        "Content-Type: "
        + response.headers.get(
            "Content-Type",
            "",
        )
    )
    log(
        f"Size: {len(response.content)} bytes"
    )
    response.raise_for_status()
    content = response.content
    if not content:
        raise RuntimeError(
            "附件內容為空"
        )
    # --------------------------------------------------------
    # DOCX 驗證
    # --------------------------------------------------------
    if expected_format == "docx":
        if not zipfile.is_zipfile(
            BytesIO(content)
        ):
            raise RuntimeError(
                "連結副檔名是 DOCX，"
                "但下載內容不是有效 ZIP/DOCX。"
            )
    # --------------------------------------------------------
    # PDF 驗證
    # --------------------------------------------------------
    elif expected_format == "pdf":
        if not content.lstrip().startswith(
            b"%PDF-"
        ):
            raise RuntimeError(
                "連結副檔名是 PDF，"
                "但檔案內容沒有 PDF 標頭。"
            )
    else:
        raise RuntimeError(
            f"不支援的附件格式："
            f"{expected_format}"
        )
    FILES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    parsed = urlparse(url)
    original_name = Path(
        parsed.path
    ).name
    if not original_name:
        original_name = (
            f"event_{event_index}."
            f"{expected_format}"
        )
    filename = safe_filename(
        f"{event_index:02d}_"
        f"{attachment_index:02d}_"
        f"{original_name}"
    )
    file_path = (
        FILES_DIR / filename
    )
    file_path.write_bytes(
        content
    )
    log(
        f"附件已保存："
        f"{file_path.name}"
    )
    return file_path
# ============================================================
# 9. DOCX 解析
# ============================================================
def docx_to_tables_and_text(
    file_path,
):
    document = Document(
        str(file_path)
    )
    paragraphs = []
    for paragraph in document.paragraphs:
        text = clean_text(
            paragraph.text
        )
        if text:
            paragraphs.append(text)
    tables = []
    for table_index, table in enumerate(
        document.tables,
        start=1,
    ):
        table_rows = []
        for row in table.rows:
            cells = [
                clean_text(
                    cell.text
                )
                for cell in row.cells
            ]
            if any(cells):
                table_rows.append(cells)
        if table_rows:
            tables.append(
                {
                    "table_index": table_index,
                    "rows": table_rows,
                }
            )
    return (
        paragraphs,
        tables,
    )
def print_docx_tables(
    tables,
):
    for table in tables:
        log("")
        log(
            "=" * 72
        )
        log(
            f"===== DOCX TABLE "
            f"{table['table_index']} ====="
        )
        log(
            "=" * 72
        )
        for row_index, row in enumerate(
            table["rows"],
            start=1,
        ):
            log(
                f"[R{row_index}] "
                + " | ".join(row)
            )
# ============================================================
# 10. PDF 解析
# ============================================================
def pdf_to_tables_and_text(
    file_path,
):
    all_tables = []
    all_text = []
    page_count = 0
    with pdfplumber.open(
        str(file_path)
    ) as pdf:
        page_count = len(
            pdf.pages
        )
        for page_number, page in enumerate(
            pdf.pages,
            start=1,
        ):
            log("")
            log(
                "-" * 72
            )
            log(
                f"PDF 第 {page_number} 頁"
            )
            log(
                "-" * 72
            )
            # ------------------------------------------------
            # PDF 文字
            # ------------------------------------------------
            text = (
                page.extract_text()
                or ""
            )
            if text.strip():
                text_block = (
                    f"[PDF 第 "
                    f"{page_number} 頁]\n"
                    f"{text.strip()}"
                )
                all_text.append(
                    text_block
                )
                log("")
                log(
                    "PDF TEXT："
                )
                log(
                    text.strip()
                )
            # ------------------------------------------------
            # PDF 表格
            # ------------------------------------------------
            try:
                page_tables = (
                    page.extract_tables()
                    or []
                )
            except Exception as exc:
                log(
                    "警告：PDF 第 "
                    f"{page_number} 頁表格擷取失敗："
                    f"{exc}"
                )
                page_tables = []
            log("")
            log(
                f"PDF 第 {page_number} 頁"
                f"表格數："
                f"{len(page_tables)}"
            )
            # ------------------------------------------------
            # 完整印出 PDF 表格
            # ------------------------------------------------
            for table_index, table in enumerate(
                page_tables,
                start=1,
            ):
                rows = []
                log("")
                log(
                    "=" * 72
                )
                log(
                    f"===== PDF TABLE "
                    f"{table_index} "
                    f"(PAGE {page_number}) ====="
                )
                log(
                    "=" * 72
                )
                for row_index, row in enumerate(
                    table,
                    start=1,
                ):
                    cells = [
                        clean_text(cell)
                        for cell in (
                            row or []
                        )
                    ]
                    if any(cells):
                        rows.append(
                            cells
                        )
                        log(
                            f"[R{row_index}] "
                            + " | ".join(
                                cells
                            )
                        )
                if rows:
                    all_tables.append(
                        {
                            "page": page_number,
                            "table_index": table_index,
                            "rows": rows,
                        }
                    )
    return (
        page_count,
        all_text,
        all_tables,
    )
# ============================================================
# 11. 公司代碼辨識
# ============================================================
CODE_PATTERN = re.compile(
    r"(?<!\d)(\d{4,6})(?!\d)"
)
def normalize_header(
    value,
):
    value = clean_text(
        value
    )
    value = value.replace(
        " ",
        "",
    )
    value = value.replace(
        "\u3000",
        "",
    )
    return value.lower()
def find_header_indices(
    row,
):
    normalized = [
        normalize_header(cell)
        for cell in row
    ]
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
        "公司",
        "證券名稱",
        "股票名稱",
    )
    for index, cell in enumerate(
        normalized
    ):
        if (
            code_index is None
            and any(
                key in cell
                for key in code_keys
            )
        ):
            code_index = index
        if (
            name_index is None
            and any(
                key in cell
                for key in name_keys
            )
        ):
            name_index = index
    if (
        code_index is not None
        and name_index is not None
    ):
        return (
            code_index,
            name_index,
        )
    return (
        None,
        None,
    )
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
        # ----------------------------------------------------
        # DOCX / PDF 統一成 rows
        # ----------------------------------------------------
        if isinstance(
            table_info,
            dict,
        ):
            rows = table_info.get(
                "rows",
                [],
            )
        else:
            rows = table_info
        header_indices = None
        for row in rows:
            code_index, name_index = (
                find_header_indices(row)
            )
            if (
                code_index is not None
                and name_index is not None
            ):
                header_indices = (
                    code_index,
                    name_index,
                )
                continue
            if not header_indices:
                continue
            code_index, name_index = (
                header_indices
            )
            if max(
                code_index,
                name_index,
            ) >= len(row):
                continue
            code_cell = clean_text(
                row[code_index]
            )
            name_cell = clean_text(
                row[name_index]
            )
            code_match = (
                CODE_PATTERN.search(
                    code_cell
                )
            )
            if not code_match:
                continue
            stock_code = (
                code_match.group(1)
            )
            if not name_cell:
                continue
            if CODE_PATTERN.fullmatch(
                name_cell
            ):
                continue
            sessions.append(
                {
                    "stock_code": stock_code,
                    "company_name": name_cell,
                    "event_title": event_title,
                    "event_id": event_id,
                    "source_format": file_format,
                    "raw_row": row,
                    "parse_method": "table",
                }
            )
    return sessions
# ============================================================
# 13. 文字備援辨識
# ============================================================
def parse_text_sessions(
    text_blocks,
    event_title,
    event_id,
    file_format,
):
    sessions = []
    for block in text_blocks:
        for line in block.splitlines():
            line = clean_text(
                line
            )
            if not line:
                continue
            match = (
                CODE_PATTERN.search(
                    line
                )
            )
            if not match:
                continue
            code = match.group(1)
            rest = (
                line[:match.start()]
                + " "
                + line[match.end():]
            )
            rest = clean_text(
                rest.strip(
                    " |｜\t,，:：-"
                )
            )
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
            if not company_name:
                continue
            sessions.append(
                {
                    "stock_code": code,
                    "company_name": company_name,
                    "event_title": event_title,
                    "event_id": event_id,
                    "source_format": file_format,
                    "raw_line": line,
                    "parse_method": "text_fallback",
                }
            )
    return sessions
# ============================================================
# 14. 場次去重
# ============================================================
def deduplicate_sessions(
    sessions,
):
    output = []
    seen = set()
    for item in sessions:
        code = clean_text(
            item.get(
                "stock_code"
            )
        )
        name = clean_text(
            item.get(
                "company_name"
            )
        )
        event_id = clean_text(
            item.get(
                "event_id"
            )
        )
        key = (
            event_id,
            code,
            name,
        )
        if (
            not code
            or not name
            or key in seen
        ):
            continue
        seen.add(key)
        output.append(item)
    return output
# ============================================================
# 15. 處理單一活動
# ============================================================
def process_event(
    event,
    event_index,
):
    title = get_event_title(
        event
    )
    event_id = get_event_id(
        event
    )
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
    log(
        f"處理活動 {event_index}"
    )
    log("=" * 72)
    log(
        f"活動：{title}"
    )
    log(
        f"zhId：{event_id}"
    )
    if not event_id:
        result["errors"].append(
            "活動缺少 zhId"
        )
        return result
    try:
        # ----------------------------------------------------
        # 取得詳細資料
        # ----------------------------------------------------
        detail_response = session.get(
            API_DETAIL_URL,
            params={
                "id": event_id,
                "response": "json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        result[
            "detail_http_status"
        ] = detail_response.status_code
        log(
            "詳細資料 HTTP："
            f"{detail_response.status_code}"
        )
        detail_response.raise_for_status()
        try:
            detail_payload = (
                detail_response.json()
            )
        except ValueError as exc:
            raise RuntimeError(
                "詳細資料不是有效 JSON"
            ) from exc
        detail_title = (
            get_detail_title(
                detail_payload
            )
        )
        if detail_title:
            result[
                "detail_title"
            ] = detail_title
            log(
                f"詳細資料標題："
                f"{detail_title}"
            )
        # ----------------------------------------------------
        # 搜尋附件
        # ----------------------------------------------------
        attachments = (
            find_attachment_links(
                detail_payload
            )
        )
        if not attachments:
            raise RuntimeError(
                "詳細資料中找不到 DOCX 或 PDF 連結。"
            )
        result[
            "attachments"
        ] = attachments
        result[
            "attachment_formats"
        ] = [
            item["format"]
            for item in attachments
        ]
        log("")
        log(
            "找到附件："
            f"{len(attachments)}"
        )
        for attachment in attachments:
            log(
                f"  "
                f"{attachment['format'].upper()} "
                f"{attachment['url']}"
            )
        combined_sessions = []
        combined_text = []
        # ----------------------------------------------------
        # 逐一處理附件
        # ----------------------------------------------------
        for attachment_index, attachment in enumerate(
            attachments,
            start=1,
        ):
            try:
                file_path = (
                    download_attachment(
                        attachment,
                        event_index,
                        attachment_index,
                    )
                )
                result[
                    "downloaded_files"
                ].append(
                    {
                        "path": str(
                            file_path.relative_to(
                                BASE_DIR
                            )
                        ),
                        "format": attachment[
                            "format"
                        ],
                        "url": attachment[
                            "url"
                        ],
                    }
                )
                file_format = (
                    attachment[
                        "format"
                    ]
                )
                # ====================================================
                # DOCX
                # ====================================================
                if file_format == "docx":
                    (
                        paragraphs,
                        tables,
                    ) = (
                        docx_to_tables_and_text(
                            file_path
                        )
                    )
                    result[
                        "paragraph_count"
                    ] += len(
                        paragraphs
                    )
                    result[
                        "table_count"
                    ] += len(
                        tables
                    )
                    log("")
                    log(
                        f"DOCX 段落："
                        f"{len(paragraphs)}"
                    )
                    log(
                        f"DOCX 表格："
                        f"{len(tables)}"
                    )
                    # 印出 DOCX 表格
                    print_docx_tables(
                        tables
                    )
                    combined_text.extend(
                        paragraphs
                    )
                    table_sessions = (
                        parse_table_sessions(
                            tables,
                            title,
                            event_id,
                            file_format,
                        )
                    )
                    # ------------------------------------------------
                    # 表格辨識不到才使用文字備援
                    # ------------------------------------------------
                    if not table_sessions:
                        table_sessions = (
                            parse_text_sessions(
                                paragraphs,
                                title,
                                event_id,
                                file_format,
                            )
                        )
                    combined_sessions.extend(
                        table_sessions
                    )
                    log(
                        "DOCX 辨識場次："
                        f"{len(table_sessions)}"
                    )
                # ====================================================
                # PDF
                # ====================================================
                elif file_format == "pdf":
                    (
                        page_count,
                        text_blocks,
                        tables,
                    ) = (
                        pdf_to_tables_and_text(
                            file_path
                        )
                    )
                    result[
                        "page_count"
                    ] = (
                        (
                            result[
                                "page_count"
                            ]
                            or 0
                        )
                        + page_count
                    )
                    result[
                        "table_count"
                    ] += len(
                        tables
                    )
                    log("")
                    log(
                        f"PDF 頁數："
                        f"{page_count}"
                    )
                    log(
                        f"PDF 表格："
                        f"{len(tables)}"
                    )
                    combined_text.extend(
                        text_blocks
                    )
                    table_sessions = (
                        parse_table_sessions(
                            tables,
                            title,
                            event_id,
                            file_format,
                        )
                    )
                    if not table_sessions:
                        table_sessions = (
                            parse_text_sessions(
                                text_blocks,
                                title,
                                event_id,
                                file_format,
                            )
                        )
                    combined_sessions.extend(
                        table_sessions
                    )
                    log(
                        "PDF 辨識場次："
                        f"{len(table_sessions)}"
                    )
                    if not any(
                        block.strip()
                        for block in text_blocks
                    ):
                        result[
                            "errors"
                        ].append(
                            "PDF 未擷取到可搜尋文字；"
                            "可能是掃描影像。"
                        )
            except Exception as exc:
                error = (
                    "附件處理失敗（"
                    f"{attachment.get('format', 'unknown')}"
                    "）："
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )
                result[
                    "errors"
                ].append(
                    error
                )
                log(
                    "ERROR："
                    + error
                )
        # ----------------------------------------------------
        # 去重
        # ----------------------------------------------------
        result[
            "sessions"
        ] = deduplicate_sessions(
            combined_sessions
        )
        result[
            "session_count"
        ] = len(
            result[
                "sessions"
            ]
        )
        # ----------------------------------------------------
        # 活動狀態
        # ----------------------------------------------------
        if (
            result[
                "downloaded_files"
            ]
            and result[
                "session_count"
            ] > 0
        ):
            result[
                "status"
            ] = "success"
        elif result[
            "downloaded_files"
        ]:
            result[
                "status"
            ] = (
                "downloaded_but_no_sessions"
            )
            result[
                "errors"
            ].append(
                "附件下載成功，但尚未辨識到公司場次。"
            )
        else:
            result[
                "status"
            ] = "failed"
    except Exception as exc:
        error = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        result[
            "errors"
        ].append(
            error
        )
        log(
            "ERROR："
            + error
        )
    log("")
    log(
        f"活動狀態："
        f"{result['status']}"
    )
    log(
        f"辨識公司場次："
        f"{result['session_count']}"
    )
    return result
# ============================================================
# 16. TXT 報告
# ============================================================
def write_text_report(
    report,
):
    lines = [
        "證交所法人說明會測試報告（第十一版 1）",
        (
            "產生時間："
            + report["generated_at"]
        ),
        "",
        (
            "活動列表總筆數："
            f"{report['total_event_count']}"
        ),
        (
            "上市公司法人說明會活動筆數："
            f"{report['conference_event_count']}"
        ),
        (
            "實際處理活動筆數："
            f"{report['processed_event_count']}"
        ),
        (
            "成功處理活動："
            f"{report['success_event_count']}"
        ),
        (
            "成功下載附件活動："
            f"{report['downloaded_event_count']}"
        ),
        (
            "成功下載 DOCX："
            f"{report['docx_event_count']}"
        ),
        (
            "成功下載 PDF："
            f"{report['pdf_event_count']}"
        ),
        (
            "辨識法人說明會表格："
            f"{report['conference_table_count']}"
        ),
        (
            "辨識公司場次總數："
            f"{report['total_session_count']}"
        ),
        (
            "處理錯誤活動："
            f"{report['error_event_count']}"
        ),
        "",
        "=" * 72,
        "===== ALL EVENTS =====",
        "=" * 72,
        "",
    ]
    for index, event in enumerate(
        report["all_events"],
        start=1,
    ):
        title = get_event_title(
            event
        )
        event_id = get_event_id(
            event
        )
        if is_listed_company_conference(
            title
        ):
            category = (
                "上市公司法人說明會"
            )
        elif "創新板" in title:
            category = (
                "創新板公司法人說明會"
            )
        else:
            category = "其他"
        lines.append(
            f"[{index}] "
            f"{category} | "
            f"{title} | "
            f"zhId={event_id}"
        )
    lines.extend(
        [
            "",
            "=" * 72,
            "===== SELECTED EVENTS =====",
            "=" * 72,
        ]
    )
    for item in report[
        "events"
    ]:
        lines.extend(
            [
                "",
                f"活動：{item['event_title']}",
                f"zhId：{item['event_id']}",
                f"狀態：{item['status']}",
                (
                    "附件格式："
                    + ", ".join(
                        item.get(
                            "attachment_formats",
                            [],
                        )
                    )
                ),
                (
                    "辨識場次："
                    f"{item['session_count']}"
                ),
            ]
        )
        for session_item in item[
            "sessions"
        ]:
            lines.append(
                "  "
                f"{session_item['stock_code']} "
                f"{session_item['company_name']} "
                f"["
                f"{session_item['source_format'].upper()}"
                f"] "
                f"["
                f"{session_item.get('parse_method', '')}"
                f"]"
            )
        for error in item[
            "errors"
        ]:
            lines.append(
                f"  錯誤／警告：{error}"
            )
    lines.extend(
        [
            "",
            "=" * 72,
            "===== ALL SESSIONS =====",
            "=" * 72,
        ]
    )
    for session_item in report[
        "sessions"
    ]:
        lines.append(
            f"{session_item['stock_code']} "
            f"{session_item['company_name']} "
            f"| "
            f"{session_item['event_title']} "
            f"| "
            f"{session_item['source_format'].upper()}"
        )
    lines.extend(
        [
            "",
            "=" * 72,
            "===== SUMMARY =====",
            "=" * 72,
            (
                "活動列表總筆數："
                f"{report['total_event_count']}"
            ),
            (
                "上市公司法人說明會活動筆數："
                f"{report['conference_event_count']}"
            ),
            (
                "實際處理活動筆數："
                f"{report['processed_event_count']}"
            ),
            (
                "成功處理活動："
                f"{report['success_event_count']}"
            ),
            (
                "成功下載附件活動："
                f"{report['downloaded_event_count']}"
            ),
            (
                "成功下載 DOCX："
                f"{report['docx_event_count']}"
            ),
            (
                "成功下載 PDF："
                f"{report['pdf_event_count']}"
            ),
            (
                "辨識法人說明會表格："
                f"{report['conference_table_count']}"
            ),
            (
                "辨識公司場次總數："
                f"{report['total_session_count']}"
            ),
            (
                "處理錯誤活動："
                f"{report['error_event_count']}"
            ),
        ]
    )
    OUTPUT_TXT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
# ============================================================
# 17. 主程式
# ============================================================
def main():
    log("")
    log("=" * 72)
    log(
        "證交所法人說明會測試："
        "第十一版 1"
    )
    log(
        "支援 DOCX / PDF"
    )
    log(
        "排除創新板公司法人說明會"
    )
    log("=" * 72)
    report = {
        "version": "11.1",
        "generated_at": (
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        ),
        "list_api_url":
            API_LIST_URL,
        "total_event_count":
            0,
        "conference_event_count":
            0,
        "processed_event_count":
            0,
        "success_event_count":
            0,
        "downloaded_event_count":
            0,
        "docx_event_count":
            0,
        "pdf_event_count":
            0,
        "conference_table_count":
            0,
        "total_session_count":
            0,
        "error_event_count":
            0,
        "all_events":
            [],
        "events":
            [],
        "sessions":
            [],
    }
    try:
        # ====================================================
        # [1] 取得活動列表
        # ====================================================
        events = get_event_list()
        report[
            "total_event_count"
        ] = len(events)
        report[
            "all_events"
        ] = events
        log("")
        log(
            f"回傳活動筆數："
            f"{len(events)}"
        )
        # ====================================================
        # 顯示全部活動
        # ====================================================
        print_all_events(
            events
        )
        # ====================================================
        # [2] 篩選上市公司法人說明會
        # ====================================================
        conference_events = (
            filter_conference_events(
                events
            )
        )
        report[
            "conference_event_count"
        ] = len(
            conference_events
        )
        log("")
        log(
            "上市公司法人說明會活動筆數："
            f"{len(conference_events)}"
        )
        print_selected_events(
            conference_events
        )
        # ====================================================
        # 限制最多處理 MAX_EVENTS
        # ====================================================
        conference_events = (
            conference_events[:MAX_EVENTS]
        )
        log("")
        log(
            f"本次最多處理："
            f"{MAX_EVENTS} 個活動"
        )
        # ====================================================
        # [3] 處理活動
        # ====================================================
        log("")
        log("=" * 72)
        log(
            "[3] 查詢詳細資料、"
            "下載 DOCX/PDF 並解析"
        )
        log("=" * 72)
        for index, event in enumerate(
            conference_events,
            start=1,
        ):
            result = process_event(
                event,
                index,
            )
            report[
                "events"
            ].append(
                result
            )
        report[
            "processed_event_count"
        ] = len(
            report["events"]
        )
        # ====================================================
        # 統計
        # ====================================================
        report[
            "success_event_count"
        ] = sum(
            1
            for item in report[
                "events"
            ]
            if item[
                "status"
            ] == "success"
        )
        report[
            "downloaded_event_count"
        ] = sum(
            1
            for item in report[
                "events"
            ]
            if item[
                "downloaded_files"
            ]
        )
        report[
            "docx_event_count"
        ] = sum(
            1
            for item in report[
                "events"
            ]
            if any(
                attachment[
                    "format"
                ] == "docx"
                for attachment in item[
                    "downloaded_files"
                ]
            )
        )
        report[
            "pdf_event_count"
        ] = sum(
            1
            for item in report[
                "events"
            ]
            if any(
                attachment[
                    "format"
                ] == "pdf"
                for attachment in item[
                    "downloaded_files"
                ]
            )
        )
        # ====================================================
        # 所有公司場次
        # ====================================================
        for item in report[
            "events"
        ]:
            report[
                "sessions"
            ].extend(
                item[
                    "sessions"
                ]
            )
        report[
            "total_session_count"
        ] = len(
            report[
                "sessions"
            ]
        )
        # ====================================================
        # 辨識到法人說明會表格
        #
        # 有 table_count 且至少有場次，
        # 或附件成功下載後有表格。
        # ====================================================
        conference_table_count = 0
        for item in report[
            "events"
        ]:
            if (
                item[
                    "table_count"
                ] > 0
            ):
                conference_table_count += (
                    1
                )
        report[
            "conference_table_count"
        ] = conference_table_count
        report[
            "error_event_count"
        ] = sum(
            1
            for item in report[
                "events"
            ]
            if item[
                "status"
            ] != "success"
        )
    except Exception as exc:
        report[
            "fatal_error"
        ] = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )
        log("")
        log(
            "程式發生重大錯誤："
            + report[
                "fatal_error"
            ]
        )
    finally:
        # ====================================================
        # [4] 儲存結果
        # ====================================================
        log("")
        log("=" * 72)
        log(
            "[4] 產生 JSON 與文字報告"
        )
        log("=" * 72)
        save_json(
            report
        )
        write_text_report(
            report
        )
        # ====================================================
        # [5] Summary
        # ====================================================
        log("")
        log("=" * 72)
        log(
            "[5] 第十一版 1 測試摘要"
        )
        log("=" * 72)
        log(
            "活動列表總筆數："
            f"{report['total_event_count']}"
        )
        log(
            "上市公司法人說明會活動筆數："
            f"{report['conference_event_count']}"
        )
        log(
            "實際處理活動筆數："
            f"{report['processed_event_count']}"
        )
        log(
            "成功處理活動："
            f"{report['success_event_count']}"
        )
        log(
            "成功下載附件活動："
            f"{report['downloaded_event_count']}"
        )
        log(
            "成功下載 DOCX："
            f"{report['docx_event_count']}"
        )
        log(
            "成功下載 PDF："
            f"{report['pdf_event_count']}"
        )
        log(
            "辨識法人說明會表格："
            f"{report['conference_table_count']}"
        )
        log(
            "辨識公司場次總數："
            f"{report['total_session_count']}"
        )
        log(
            "處理錯誤活動："
            f"{report['error_event_count']}"
        )
        log("")
        log(
            "輸出檔案："
        )
        log(
            f"- {OUTPUT_JSON.name}"
        )
        log(
            f"- {OUTPUT_TXT.name}"
        )
        log(
            f"- {FILES_DIR.name}/"
        )
        log("")
        log(
            "第十一版 1 測試完成。"
        )
if __name__ == "__main__":
    main()
