import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from docx import Document


# ============================================================
# 第九版：自動取得法人說明會活動清單、下載 DOCX、解析場次
# 僅供測試，不修改正式股票分析系統
# ============================================================

BASE_URL = "https://www.twse.com.tw"
EVENT_LIST_API = f"{BASE_URL}/rwd/zh/news/eventList"
EVENT_DETAIL_API = f"{BASE_URL}/rwd/zh/news/eventDetail"

TIMEOUT = 30
MAX_EVENTS = 30
REQUEST_DELAY_SECONDS = 0.3

RESULT_JSON = Path("twse_conference_v9_result.json")
RESULT_TXT = Path("twse_conference_v9_sessions.txt")
DOCX_DIR = Path("twse_conference_v9_files")

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": f"{BASE_URL}/zh/about/news/event/list.html",
})


def print_section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def safe_filename(value):
    value = re.sub(r'[\\/:*?"<>|]+', "_", str(value))
    value = re.sub(r"\s+", "_", value).strip("_")
    return value[:100] or "event"


def get_json(url, params=None):
    response = session.get(
        url,
        params=params,
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError(
            f"API 未回傳有效 JSON：{response.url}\n"
            f"HTTP={response.status_code}\n"
            f"內容={response.text[:1000]}"
        ) from exc

    return response, data


def normalize_event_list(data):
    """
    支援 RWD 活動列表格式：
    data = [[項次, 活動主題, zhId, enId], ...]
    """
    rows = data.get("data", [])
    events = []

    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 4:
            continue

        try:
            number = row[0]
            title = str(row[1]).strip()
            zh_id = str(row[2]).strip()
            en_id = str(row[3]).strip()
        except Exception:
            continue

        if not title or not zh_id:
            continue

        events.append({
            "number": number,
            "title": title,
            "zhId": zh_id,
            "enId": en_id,
        })

    return events


def find_docx_links(value):
    """
    從 eventDetail JSON 的巢狀字串中找出 DOCX 連結。
    API 的 data 欄位可能包含 HTML 片段。
    """
    found = []

    def walk(item):
        if isinstance(item, dict):
            for nested in item.values():
                walk(nested)

        elif isinstance(item, (list, tuple)):
            for nested in item:
                walk(nested)

        elif isinstance(item, str):
            if ".docx" not in item.lower():
                return

            soup = BeautifulSoup(item, "html.parser")

            for anchor in soup.find_all("a", href=True):
                href = anchor.get("href", "").strip()

                if ".docx" not in href.lower():
                    continue

                absolute_url = urljoin(BASE_URL, href)

                # 僅允許從證交所網域下載，避免意外下載外部網址。
                parsed = urlparse(absolute_url)
                if parsed.scheme != "https":
                    continue

                if parsed.hostname not in {
                    "www.twse.com.tw",
                    "twse.com.tw",
                }:
                    continue

                item_result = {
                    "text": anchor.get_text(" ", strip=True),
                    "url": absolute_url,
                }

                if item_result not in found:
                    found.append(item_result)

    walk(value)
    return found


def clean_cell_text(cell):
    return re.sub(r"\s+", " ", cell.text or "").strip()


def parse_docx_tables(docx_path):
    """
    保留所有表格供檢查。
    若找到包含公司代碼、公司名稱的表格，
    同時整理成結構化場次資料。
    """
    document = Document(str(docx_path))
    tables_output = []
    sessions_output = []

    for table_index, table in enumerate(document.tables, start=1):
        rows = []

        for row in table.rows:
            cells = [clean_cell_text(cell) for cell in row.cells]
            if any(cells):
                rows.append(cells)

        tables_output.append({
            "table_number": table_index,
            "rows": rows,
        })

        header_index = None
        headers = []

        for row_index, row in enumerate(rows):
            normalized = [value.replace(" ", "") for value in row]

            has_code = any("公司代碼" in value for value in normalized)
            has_name = any("公司名稱" in value for value in normalized)

            if has_code and has_name:
                header_index = row_index
                headers = row
                break

        if header_index is None:
            continue

        # 對重複表頭名稱加上序號，避免 JSON 欄位互相覆蓋。
        unique_headers = []
        counts = {}

        for header_index_value, header in enumerate(headers):
            name = header.strip() or f"欄位{header_index_value + 1}"
            counts[name] = counts.get(name, 0) + 1

            if counts[name] > 1:
                name = f"{name}_{counts[name]}"

            unique_headers.append(name)

        code_column = next(
            (
                index
                for index, header in enumerate(unique_headers)
                if "公司代碼" in header.replace(" ", "")
            ),
            None,
        )

        for row in rows[header_index + 1:]:
            if not any(row):
                continue

            # 略過重複表頭。
            compact_row = [value.replace(" ", "") for value in row]
            if any("公司代碼" in value for value in compact_row) and any(
                "公司名稱" in value for value in compact_row
            ):
                continue

            record = {}

            for index, header in enumerate(unique_headers):
                record[header] = row[index] if index < len(row) else ""

            # 公司代碼欄位必須存在且像股票代碼，避免把說明文字
            # 或其他時間表誤判成公司場次。
            if code_column is not None:
                code_value = (
                    row[code_column].strip()
                    if code_column < len(row)
                    else ""
                )

                if not re.fullmatch(r"\d{4,6}", code_value):
                    continue

            sessions_output.append(record)

    paragraphs = [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    return {
        "paragraphs": paragraphs,
        "tables": tables_output,
        "sessions": sessions_output,
    }


def save_outputs(result, text_lines):
    RESULT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    RESULT_TXT.write_text(
        "\n".join(text_lines) + "\n",
        encoding="utf-8",
    )


def main():
    DOCX_DIR.mkdir(parents=True, exist_ok=True)

    result = {
        "version": 9,
        "event_list_api": EVENT_LIST_API,
        "event_detail_api": EVENT_DETAIL_API,
        "event_list_http_status": None,
        "event_list_total": 0,
        "matching_event_count": 0,
        "processed_event_count": 0,
        "successful_docx_count": 0,
        "total_session_count": 0,
        "events": [],
        "errors": [],
    }

    text_lines = [
        "TWSE 法人說明會測試結果（第九版）",
        "=" * 60,
        f"活動列表 API：{EVENT_LIST_API}",
        f"詳細資料 API：{EVENT_DETAIL_API}",
        "",
    ]

    # --------------------------------------------------------
    # 1. 取得活動清單
    # --------------------------------------------------------
    print_section("[1] 取得證交所活動列表")

    try:
        response, list_data = get_json(
            EVENT_LIST_API,
            params={"response": "json"},
        )

        result["event_list_http_status"] = response.status_code
        result["event_list_total"] = len(list_data.get("data", []))

        print("HTTP Status:", response.status_code)
        print("API URL:", response.url)
        print("回傳活動筆數:", result["event_list_total"])
        print("API 狀態:", list_data.get("stat"))

        if str(list_data.get("stat", "")).lower() != "ok":
            raise RuntimeError(
                "活動列表 API 的 stat 不是 ok："
                + json.dumps(list_data, ensure_ascii=False)[:2000]
            )

        all_events = normalize_event_list(list_data)

    except Exception as exc:
        message = f"取得活動列表失敗：{repr(exc)}"
        print(message)
        result["errors"].append(message)
        text_lines.append(message)
        save_outputs(result, text_lines)
        raise

    # --------------------------------------------------------
    # 2. 篩選法人說明會
    # --------------------------------------------------------
    print_section("[2] 篩選法人說明會活動")

    matching_events = [
        event
        for event in all_events
        if "法人說明會" in event["title"]
    ]

    result["matching_event_count"] = len(matching_events)

    print("活動列表總筆數:", len(all_events))
    print("符合「法人說明會」的筆數:", len(matching_events))

    for event in matching_events:
        print(
            f'項次 {event["number"]} | '
            f'{event["title"]} | '
            f'zhId={event["zhId"]}'
        )

    if not matching_events:
        message = "活動列表中沒有找到標題包含「法人說明會」的活動。"
        print(message)
        result["errors"].append(message)
        text_lines.append(message)
        save_outputs(result, text_lines)
        return

    selected_events = matching_events[:MAX_EVENTS]

    print()
    print(f"本次最多處理 {MAX_EVENTS} 筆，實際處理 {len(selected_events)} 筆。")

    # --------------------------------------------------------
    # 3. 逐筆取得詳細資料並下載 DOCX
    # --------------------------------------------------------
    print_section("[3] 查詢詳細資料、下載 DOCX 並解析")

    for index, event in enumerate(selected_events, start=1):
        event_result = {
            **event,
            "detail_http_status": None,
            "detail_title": None,
            "docx_url": None,
            "docx_http_status": None,
            "docx_content_type": None,
            "docx_size_bytes": None,
            "docx_file": None,
            "paragraphs": [],
            "tables": [],
            "sessions": [],
            "session_count": 0,
            "status": "pending",
            "error": None,
        }

        print()
        print("-" * 72)
        print(f'活動 {index}/{len(selected_events)}：{event["title"]}')
        print("zhId:", event["zhId"])

        try:
            detail_response, detail_data = get_json(
                EVENT_DETAIL_API,
                params={
                    "id": event["zhId"],
                    "response": "json",
                },
            )

            event_result["detail_http_status"] = detail_response.status_code
            event_result["detail_title"] = detail_data.get("title")

            print("詳細資料 HTTP:", detail_response.status_code)
            print("詳細資料標題:", detail_data.get("title"))

            if str(
                detail_data.get("stat", detail_data.get("status", ""))
            ).lower() != "ok":
                raise RuntimeError(
                    "詳細資料 API 狀態非 ok："
                    + json.dumps(detail_data, ensure_ascii=False)[:2000]
                )

            docx_links = find_docx_links(detail_data)

            if not docx_links:
                raise RuntimeError(
                    "詳細資料中找不到 DOCX 連結。"
                    "可能是此活動沒有 DOCX，或格式已變更。"
                )

            event_result["docx_url"] = docx_links[0]["url"]
            event_result["docx_links"] = docx_links

            print("DOCX 連結:", docx_links[0]["url"])

            # 以活動序號及 ID 命名，避免同名檔案互相覆蓋。
            filename = safe_filename(
                f'{index:02d}_{event["zhId"]}_{event["title"]}.docx'
            )
            docx_path = DOCX_DIR / filename

            docx_response = session.get(
                docx_links[0]["url"],
                timeout=TIMEOUT,
            )
            docx_response.raise_for_status()

            content_type = docx_response.headers.get("Content-Type", "")
            content = docx_response.content

            if not content:
                raise RuntimeError("DOCX 下載結果是空檔案。")

            # DOCX 是 ZIP 容器，通常以 PK 開頭。
            if not content.startswith(b"PK"):
                raise RuntimeError(
                    "下載內容不像 DOCX/ZIP 檔案。"
                    f" Content-Type={content_type}; "
                    f"前 100 字元={content[:100]!r}"
                )

            docx_path.write_bytes(content)

            event_result["docx_http_status"] = docx_response.status_code
            event_result["docx_content_type"] = content_type
            event_result["docx_size_bytes"] = len(content)
            event_result["docx_file"] = str(docx_path)

            print("DOCX HTTP:", docx_response.status_code)
            print("Content-Type:", content_type)
            print("檔案大小:", len(content), "bytes")

            parsed = parse_docx_tables(docx_path)

            event_result["paragraphs"] = parsed["paragraphs"]
            event_result["tables"] = parsed["tables"]
            event_result["sessions"] = parsed["sessions"]
            event_result["session_count"] = len(parsed["sessions"])
            event_result["status"] = "success"

            result["successful_docx_count"] += 1
            result["total_session_count"] += len(parsed["sessions"])

            print("段落數:", len(parsed["paragraphs"]))
            print("表格數:", len(parsed["tables"]))
            print("解析到的公司場次數:", len(parsed["sessions"]))

            for session_record in parsed["sessions"]:
                print(
                    "  - "
                    + json.dumps(
                        session_record,
                        ensure_ascii=False,
                    )
                )

        except Exception as exc:
            event_result["status"] = "error"
            event_result["error"] = repr(exc)

            message = (
                f'活動「{event["title"]}」'
                f'（{event["zhId"]}）處理失敗：{repr(exc)}'
            )
            print("ERROR:", message)
            result["errors"].append(message)

        result["events"].append(event_result)
        result["processed_event_count"] += 1

        # 即使中途有個別活動失敗，也保留已完成的測試結果。
        save_outputs(result, text_lines)

        time.sleep(REQUEST_DELAY_SECONDS)

    # --------------------------------------------------------
    # 4. 產生可閱讀的 TXT 報告
    # --------------------------------------------------------
    print_section("[4] 產生文字報告")

    text_lines = [
        "TWSE 法人說明會測試結果（第九版）",
        "=" * 72,
        f"活動列表 API：{EVENT_LIST_API}",
        f"詳細資料 API：{EVENT_DETAIL_API}",
        f'活動列表筆數：{result["event_list_total"]}',
        f'法人說明會活動筆數：{result["matching_event_count"]}',
        f'實際處理筆數：{result["processed_event_count"]}',
        f'成功下載 DOCX：{result["successful_docx_count"]}',
        f'解析到的公司場次總數：{result["total_session_count"]}',
        "",
    ]

    for event in result["events"]:
        text_lines.extend([
            "=" * 72,
            f'活動：{event["title"]}',
            f'項次：{event["number"]}',
            f'zhId：{event["zhId"]}',
            f'狀態：{event["status"]}',
            f'DOCX：{event.get("docx_url") or "無"}',
            f'場次數：{event["session_count"]}',
        ])

        if event.get("error"):
            text_lines.append(f'錯誤：{event["error"]}')

        if event["sessions"]:
            text_lines.append("")
            text_lines.append("公司場次：")

            for record in event["sessions"]:
                text_lines.append(
                    json.dumps(record, ensure_ascii=False)
                )

        if event["tables"]:
            text_lines.append("")
            text_lines.append("完整表格內容：")

            for table in event["tables"]:
                text_lines.append(
                    f'--- 表格 {table["table_number"]} ---'
                )

                for row in table["rows"]:
                    text_lines.append(" | ".join(row))

        if event["paragraphs"]:
            text_lines.append("")
            text_lines.append("文件段落：")
            text_lines.extend(event["paragraphs"])

        text_lines.append("")

    if result["errors"]:
        text_lines.extend([
            "=" * 72,
            "錯誤清單",
            "=" * 72,
            *result["errors"],
            "",
        ])

    save_outputs(result, text_lines)

    # --------------------------------------------------------
    # 5. 最終摘要
    # --------------------------------------------------------
    print_section("[5] 第九版測試摘要")

    print("活動列表總筆數:", result["event_list_total"])
    print("法人說明會活動筆數:", result["matching_event_count"])
    print("實際處理活動筆數:", result["processed_event_count"])
    print("成功下載 DOCX:", result["successful_docx_count"])
    print("解析到的公司場次總數:", result["total_session_count"])
    print("錯誤筆數:", len(result["errors"]))
    print()
    print("輸出檔案:")
    print("-", RESULT_JSON)
    print("-", RESULT_TXT)
    print("-", DOCX_DIR)

    print()
    print("第九版測試完成。")


if __name__ == "__main__":
    main()
