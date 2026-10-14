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
# 第十版：證交所法人說明會測試
# 支援 DOCX / PDF
# 不修改正式股票分析系統
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

API_LIST_URL = (
    "https://www.twse.com.tw/rwd/zh/news/eventList?response=json"
)
API_DETAIL_URL = (
    "https://www.twse.com.tw/rwd/zh/news/eventDetail"
)

OUTPUT_JSON = BASE_DIR / "twse_conference_v10_result.json"
OUTPUT_TXT = BASE_DIR / "twse_conference_v10_sessions.txt"
FILES_DIR = BASE_DIR / "twse_conference_v10_files"

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

session = requests.Session()
session.headers.update(HEADERS)


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


# ============================================================
# 1. 取得證交所活動列表
# ============================================================

def get_event_list():
    log("[1] 取得證交所活動列表")
    log(f"API URL: {API_LIST_URL}")

    response = session.get(
        API_LIST_URL,
        timeout=REQUEST_TIMEOUT,
    )

    log(f"HTTP Status: {response.status_code}")
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("活動列表回應不是有效 JSON") from exc

    if isinstance(payload, list):
        events = payload
    elif isinstance(payload, dict):
        events = payload.get("data", [])
        if not isinstance(events, list):
            events = []
    else:
        events = []

    log(f"回傳活動筆數: {len(events)}")

    return events


def get_event_title(event):
    if not isinstance(event, dict):
        return ""

    for key in ("活動主題", "title", "name", "eventName"):
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


def filter_conference_events(events):
    matched = []

    for event in events:
        title = get_event_title(event)
        if "法人說明會" in title:
            matched.append(event)

    return matched


# ============================================================
# 2. 從詳細資料中尋找附件連結
#    不只搜尋 DOCX，也搜尋 PDF
# ============================================================

SUPPORTED_EXTENSIONS = (".docx", ".pdf")


def collect_strings(obj, output):
    """遞迴收集 API 回應內所有字串。"""
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
    """
    從 API 回應的 HTML 或一般文字中找出 DOCX / PDF 連結。
    同時檢查 href、純文字網址及可能的 HTML entity。
    """
    strings = []
    collect_strings(detail_payload, strings)

    found = []

    for content in strings:
        soup = BeautifulSoup(content, "html.parser")

        # HTML <a href="...">
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

        # 純文字中的附件網址
        decoded = BeautifulSoup(content, "html.parser").get_text(" ")
        url_pattern = re.compile(
            r"""https?://[^\s"'<>]+""",
            re.IGNORECASE,
        )

        for match in url_pattern.findall(decoded):
            candidate = match.rstrip(".,);]}>")
            extension = extension_from_url(candidate)

            if extension:
                found.append({
                    "url": candidate,
                    "format": extension,
                    "link_text": "",
                })

    # 僅保留證交所網域，避免誤下載外部網址
    unique = []
    seen = set()

    for item in found:
        url = item["url"]
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        if host not in ("www.twse.com.tw", "twse.com.tw"):
            continue

        if url not in seen:
            seen.add(url)
            unique.append(item)

    return unique


def get_detail_title(payload):
    if isinstance(payload, dict):
        for key in ("title", "活動主題", "name"):
            value = payload.get(key)
            if value:
                return clean_text(value)

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("title", "活動主題", "name"):
                value = data.get(key)
                if value:
                    return clean_text(value)

    return ""


def get_event_detail(event_id):
    return fetch_json(
        API_DETAIL_URL,
        params={
            "id": event_id,
            "response": "json",
        },
    )


# ============================================================
# 3. 下載附件並確認檔案格式
# ============================================================

def download_attachment(attachment, event_index):
    url = attachment["url"]
    expected_format = attachment["format"]

    log(f"附件格式: {expected_format.upper()}")
    log(f"附件 URL: {url}")

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    log(f"附件 HTTP: {response.status_code}")
    log(
        "附件 Content-Type: "
        + response.headers.get("Content-Type", "")
    )
    log(f"附件大小: {len(response.content)} bytes")

    response.raise_for_status()

    content = response.content

    if not content:
        raise RuntimeError("附件內容為空")

    # DOCX 和 PDF 都是二進位檔案；以檔案內容驗證格式
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

    parsed = urlparse(url)
    original_name = Path(parsed.path).name

    if not original_name:
        original_name = f"event_{event_index}.{expected_format}"

    # 加上活動序號，避免不同活動附件同名時互相覆蓋
    filename = safe_filename(
        f"{event_index:02d}_{original_name}"
    )
    file_path = FILES_DIR / filename
    file_path.write_bytes(content)

    log(f"附件已保存: {file_path.name}")

    return file_path


# ============================================================
# 4. 解析 DOCX
# ============================================================

def docx_to_tables_and_text(file_path):
    document = Document(str(file_path))

    paragraphs = [
        clean_text(paragraph.text)
        for paragraph in document.paragraphs
        if clean_text(paragraph.text)
    ]

    tables = []

    for table in document.tables:
        table_rows = []

        for row in table.rows:
            cells = [clean_text(cell.text) for cell in row.cells]
            if any(cells):
                table_rows.append(cells)

        if table_rows:
            tables.append(table_rows)

    return paragraphs, tables


# ============================================================
# 5. 解析 PDF
# ============================================================

def pdf_to_tables_and_text(file_path):
    """
    先使用 pdfplumber 擷取表格，再擷取頁面文字。
    不執行 OCR；掃描型 PDF 可能需要後續另行處理。
    """
    all_tables = []
    all_text = []
    page_count = 0

    with pdfplumber.open(str(file_path)) as pdf:
        page_count = len(pdf.pages)

        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""

            if text.strip():
                all_text.append(
                    f"[PDF 第 {page_number} 頁]\n{text.strip()}"
                )

            try:
                page_tables = page.extract_tables() or []
            except Exception as exc:
                log(
                    f"警告：PDF 第 {page_number} 頁表格擷取失敗："
                    f"{exc}"
                )
                page_tables = []

            for table in page_tables:
                rows = []

                for row in table:
                    cells = [
                        clean_text(cell)
                        for cell in (row or [])
                    ]
                    if any(cells):
                        rows.append(cells)

                if rows:
                    all_tables.append(rows)

    return page_count, all_text, all_tables


# ============================================================
# 6. 從表格或文字中辨識公司場次
# ============================================================

CODE_PATTERN = re.compile(r"(?<!\d)(\d{4,6})(?!\d)")


def normalize_header(value):
    value = clean_text(value).replace(" ", "")
    return value.lower()


def find_header_indices(row):
    """
    找出表格中的公司代碼及公司名稱欄位。
    不假設欄位固定在第 1、2 欄。
    """
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
        "公司",
        "證券名稱",
        "股票名稱",
    )

    for index, cell in enumerate(normalized):
        if code_index is None and any(
            key in cell for key in code_keys
        ):
            code_index = index

        if name_index is None and any(
            key in cell for key in name_keys
        ):
            name_index = index

    if code_index is not None and name_index is not None:
        return code_index, name_index

    return None, None


def parse_table_sessions(tables, event_title, event_id, file_format):
    sessions = []

    for table in tables:
        header_indices = None

        for row in table:
            code_index, name_index = find_header_indices(row)

            if code_index is not None and name_index is not None:
                header_indices = (code_index, name_index)
                continue

            if not header_indices:
                continue

            code_index, name_index = header_indices

            if max(code_index, name_index) >= len(row):
                continue

            code_cell = clean_text(row[code_index])
            name_cell = clean_text(row[name_index])

            code_match = CODE_PATTERN.search(code_cell)

            # 有些表格的代碼欄位可能包含其他字元
            if not code_match:
                code_match = CODE_PATTERN.search(
                    " ".join(row)
                )

            if not code_match:
                continue

            stock_code = code_match.group(1)

            if code_cell and CODE_PATTERN.search(code_cell):
                stock_code = CODE_PATTERN.search(code_cell).group(1)
            elif name_cell and CODE_PATTERN.search(name_cell):
                # 代碼出現在名稱欄位時，不直接把名稱欄當代碼
                continue

            company_name = name_cell

            # 防止名稱欄位實際是代碼
            if CODE_PATTERN.fullmatch(company_name):
                continue

            if not company_name:
                continue

            sessions.append({
                "stock_code": stock_code,
                "company_name": company_name,
                "event_title": event_title,
                "event_id": event_id,
                "source_format": file_format,
                "raw_row": row,
            })

    return sessions


def parse_text_sessions(text_blocks, event_title, event_id, file_format):
    """
    表格解析不到時，從 PDF/DOCX 文字中嘗試辨識包含公司代碼的行。
    這是備援解析，不保證能識別所有非表格排版。
    """
    sessions = []

    for block in text_blocks:
        for line in block.splitlines():
            line = clean_text(line)

            if not line:
                continue

            match = CODE_PATTERN.search(line)
            if not match:
                continue

            code = match.group(1)
            rest = (
                line[:match.start()] + " " + line[match.end():]
            )
            rest = clean_text(rest.strip(" |｜\t,，:：-"))

            if not rest:
                continue

            # 排除只有日期、時間、頁碼或表頭的行
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

            # 取出代碼後的第一段文字作為可能的公司名稱
            company_name = re.split(
                r"\s{2,}|[|｜\t]",
                rest,
                maxsplit=1,
            )[0].strip()

            if not company_name:
                continue

            sessions.append({
                "stock_code": code,
                "company_name": company_name,
                "event_title": event_title,
                "event_id": event_id,
                "source_format": file_format,
                "raw_line": line,
                "parse_method": "text_fallback",
            })

    return sessions


def deduplicate_sessions(sessions):
    output = []
    seen = set()

    for item in sessions:
        code = clean_text(item.get("stock_code"))
        name = clean_text(item.get("company_name"))
        event_id = clean_text(item.get("event_id"))

        key = (event_id, code, name)

        if not code or not name or key in seen:
            continue

        seen.add(key)
        output.append(item)

    return output


# ============================================================
# 7. 處理單一活動
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
    log("-" * 72)
    log(f"活動 {event_index}：{title}")
    log(f"zhId: {event_id}")

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

        log(f"詳細資料 HTTP: {detail_response.status_code}")
        detail_response.raise_for_status()

        try:
            detail_payload = detail_response.json()
        except ValueError as exc:
            raise RuntimeError("詳細資料不是有效 JSON") from exc

        detail_title = get_detail_title(detail_payload)

        if detail_title:
            log(f"詳細資料標題: {detail_title}")
            result["detail_title"] = detail_title

        attachments = find_attachment_links(detail_payload)

        if not attachments:
            raise RuntimeError(
                "詳細資料中找不到 DOCX 或 PDF 連結。"
                "可能是活動沒有附件、附件格式不同，"
                "或 API 回應的連結結構已變更。"
            )

        result["attachments"] = attachments
        result["attachment_formats"] = [
            item["format"] for item in attachments
        ]

        combined_sessions = []
        combined_text = []

        for attachment_index, attachment in enumerate(
            attachments,
            start=1,
        ):
            try:
                file_path = download_attachment(
                    attachment,
                    event_index * 100 + attachment_index,
                )

                result["downloaded_files"].append({
                    "path": str(file_path.relative_to(BASE_DIR)),
                    "format": attachment["format"],
                    "url": attachment["url"],
                })

                file_format = attachment["format"]

                if file_format == "docx":
                    paragraphs, tables = docx_to_tables_and_text(
                        file_path
                    )

                    result["paragraph_count"] += len(paragraphs)
                    result["table_count"] += len(tables)

                    combined_text.extend(paragraphs)

                    table_sessions = parse_table_sessions(
                        tables,
                        title,
                        event_id,
                        file_format,
                    )

                    if not table_sessions:
                        table_sessions = parse_text_sessions(
                            paragraphs,
                            title,
                            event_id,
                            file_format,
                        )

                    combined_sessions.extend(table_sessions)

                    log(
                        f"DOCX 段落: {len(paragraphs)}，"
                        f"表格: {len(tables)}，"
                        f"辨識場次: {len(table_sessions)}"
                    )

                elif file_format == "pdf":
                    page_count, text_blocks, tables = (
                        pdf_to_tables_and_text(file_path)
                    )

                    result["page_count"] = (
                        (result["page_count"] or 0) + page_count
                    )
                    result["table_count"] += len(tables)

                    combined_text.extend(text_blocks)

                    table_sessions = parse_table_sessions(
                        tables,
                        title,
                        event_id,
                        file_format,
                    )

                    if not table_sessions:
                        table_sessions = parse_text_sessions(
                            text_blocks,
                            title,
                            event_id,
                            file_format,
                        )

                    combined_sessions.extend(table_sessions)

                    log(
                        f"PDF 頁數: {page_count}，"
                        f"表格: {len(tables)}，"
                        f"辨識場次: {len(table_sessions)}"
                    )

                    if not any(block.strip() for block in text_blocks):
                        result["errors"].append(
                            "PDF 未擷取到可搜尋文字；"
                            "可能是掃描影像，需另行評估 OCR。"
                        )

            except Exception as exc:
                error = (
                    f"附件處理失敗（{attachment.get('format', 'unknown')}）："
                    f"{type(exc).__name__}: {exc}"
                )
                result["errors"].append(error)
                log("ERROR: " + error)

        result["sessions"] = deduplicate_sessions(
            combined_sessions
        )
        result["session_count"] = len(result["sessions"])

        if result["downloaded_files"] and result["session_count"] > 0:
            result["status"] = "success"

        elif result["downloaded_files"]:
            result["status"] = "downloaded_but_no_sessions"
            result["errors"].append(
                "附件下載成功，但尚未辨識到公司場次；"
                "需要檢查實際版面與欄位格式。"
            )

        else:
            result["status"] = "failed"

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        result["errors"].append(error)
        log("ERROR: " + error)

    log(f"活動狀態: {result['status']}")
    log(f"辨識場次: {result['session_count']}")

    return result


# ============================================================
# 8. 產生 TXT 報告
# ============================================================

def write_text_report(report):
    lines = [
        "證交所法人說明會測試報告（第十版）",
        f"產生時間：{datetime.datetime.now().isoformat(timespec='seconds')}",
        "",
        f"活動列表總筆數：{report['total_event_count']}",
        f"法人說明會活動筆數：{report['conference_event_count']}",
        f"實際處理活動筆數：{report['processed_event_count']}",
        f"成功處理活動：{report['success_event_count']}",
        f"成功下載附件活動：{report['downloaded_event_count']}",
        f"成功下載 DOCX：{report['docx_event_count']}",
        f"成功下載 PDF：{report['pdf_event_count']}",
        f"辨識公司場次總數：{report['total_session_count']}",
        f"處理錯誤活動：{report['error_event_count']}",
        "",
        "=" * 72,
        "活動詳細結果",
        "=" * 72,
    ]

    for item in report["events"]:
        lines.extend([
            "",
            f"活動：{item['event_title']}",
            f"zhId：{item['event_id']}",
            f"狀態：{item['status']}",
            f"附件格式：{', '.join(item.get('attachment_formats', []))}",
            f"辨識場次：{item['session_count']}",
        ])

        for session_item in item["sessions"]:
            lines.append(
                "  "
                f"{session_item['stock_code']} "
                f"{session_item['company_name']} "
                f"[{session_item['source_format'].upper()}]"
            )

        for error in item["errors"]:
            lines.append(f"  錯誤／警告：{error}")

    OUTPUT_TXT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


# ============================================================
# 9. 主程式
# ============================================================

def main():
    log("=" * 72)
    log("證交所法人說明會測試：第十版")
    log("支援 DOCX / PDF")
    log("=" * 72)

    report = {
        "version": 10,
        "generated_at": datetime.datetime.now().isoformat(
            timespec="seconds"
        ),
        "list_api_url": API_LIST_URL,
        "total_event_count": 0,
        "conference_event_count": 0,
        "processed_event_count": 0,
        "success_event_count": 0,
        "downloaded_event_count": 0,
        "docx_event_count": 0,
        "pdf_event_count": 0,
        "total_session_count": 0,
        "error_event_count": 0,
        "events": [],
        "sessions": [],
    }

    try:
        events = get_event_list()
        report["total_event_count"] = len(events)

        log("")
        log("[2] 篩選法人說明會活動")

        conference_events = filter_conference_events(events)
        report["conference_event_count"] = len(conference_events)

        log(f"活動列表總筆數: {len(events)}")
        log(
            "符合「法人說明會」的筆數: "
            f"{len(conference_events)}"
        )

        conference_events = conference_events[:MAX_EVENTS]

        log("")
        log("[3] 查詢詳細資料、下載 DOCX/PDF 並解析")

        for index, event in enumerate(conference_events, start=1):
            result = process_event(event, index)
            report["events"].append(result)

        report["processed_event_count"] = len(report["events"])

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

        for item in report["events"]:
            report["sessions"].extend(item["sessions"])

        report["total_session_count"] = len(report["sessions"])

        report["error_event_count"] = sum(
            1 for item in report["events"]
            if item["status"] != "success"
        )

    except Exception as exc:
        report["fatal_error"] = (
            f"{type(exc).__name__}: {exc}"
        )
        log("")
        log("程式發生重大錯誤：" + report["fatal_error"])

    finally:
        log("")
        log("=" * 72)
        log("[4] 產生 JSON 與文字報告")
        save_json(report)
        write_text_report(report)

        log("")
        log("=" * 72)
        log("[5] 第十版測試摘要")
        log("=" * 72)
        log(f"活動列表總筆數: {report['total_event_count']}")
        log(f"法人說明會活動筆數: {report['conference_event_count']}")
        log(f"實際處理活動筆數: {report['processed_event_count']}")
        log(f"成功處理活動: {report['success_event_count']}")
        log(f"有下載附件的活動: {report['downloaded_event_count']}")
        log(f"成功下載 DOCX 的活動: {report['docx_event_count']}")
        log(f"成功下載 PDF 的活動: {report['pdf_event_count']}")
        log(f"辨識公司場次總數: {report['total_session_count']}")
        log(f"未完全成功的活動: {report['error_event_count']}")

        log("")
        log("輸出檔案:")
        log(f"- {OUTPUT_JSON.name}")
        log(f"- {OUTPUT_TXT.name}")
        log(f"- {FILES_DIR.name}/")
        log("")
        log("第十版測試完成。")


if __name__ == "__main__":
    main()
