import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from docx import Document


# ============================================================
# 1. 基本設定
# ============================================================

BASE_URL = "https://www.twse.com.tw"

EVENT_API = (
    "https://www.twse.com.tw"
    "/rwd/zh/news/eventDetail"
)

EVENT_ID = "8a8216d6a0bdcc0001a0c849c4ae001c"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": (
        "https://www.twse.com.tw/"
        "zh/about/news/event/content.html?"
        + EVENT_ID
    ),
}

RESULT_FILE = Path("twse_conference_v7_result.json")
DOCX_FILE = Path("twse_conference_event_v7.docx")
TEXT_FILE = Path("twse_conference_event_v7.txt")


# ============================================================
# 2. 工具函式
# ============================================================

def print_separator():
    print("-" * 70)


def save_json(data):
    RESULT_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def clean_text(value):
    if value is None:
        return ""

    value = str(value)

    # HTML → 純文字
    soup = BeautifulSoup(value, "html.parser")
    value = soup.get_text("\n")

    # 清除多餘空白
    lines = []

    for line in value.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


# ============================================================
# 3. 呼叫 TWSE eventDetail API
# ============================================================

def get_event_detail():
    print()
    print("=" * 70)
    print("[1] 取得 TWSE 法人說明會活動詳細資料")
    print("=" * 70)

    params = {
        "id": EVENT_ID,
        "response": "json",
    }

    print()
    print("API:")
    print(EVENT_API)

    print()
    print("Params:")
    print(json.dumps(
        params,
        ensure_ascii=False,
        indent=2,
    ))

    try:
        response = requests.get(
            EVENT_API,
            params=params,
            headers=HEADERS,
            timeout=30,
        )
    except Exception as e:
        print()
        print("API request error:")
        print(repr(e))

        return None

    print()
    print("HTTP Status:")
    print(response.status_code)

    print()
    print("Final URL:")
    print(response.url)

    print()
    print("Content-Type:")
    print(response.headers.get("Content-Type"))

    print()
    print("Response Length:")
    print(len(response.content))

    try:
        data = response.json()
    except Exception as e:
        print()
        print("JSON decode error:")
        print(repr(e))

        print()
        print("Response:")
        print(response.text[:5000])

        return None

    print()
    print("JSON response:")
    print(json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ))

    return data


# ============================================================
# 4. 從 eventDetail 找出 DOCX
# ============================================================

def find_docx_url(event_data):
    print()
    print("=" * 70)
    print("[2] 從 eventDetail 找出 DOCX 場次資訊")
    print("=" * 70)

    if not isinstance(event_data, dict):
        print("event_data 不是 JSON object")
        return None

    data = event_data.get("data")

    if not isinstance(data, list):
        print("找不到 data")
        return None

    html_fragments = []

    for item in data:
        if isinstance(item, list):
            for value in item:
                if isinstance(value, str):
                    html_fragments.append(value)

    combined_html = "\n".join(html_fragments)

    print()
    print("搜尋 HTML 長度:")
    print(len(combined_html))

    soup = BeautifulSoup(
        combined_html,
        "html.parser",
    )

    links = []

    for a in soup.find_all("a"):
        href = a.get("href")
        text = a.get_text(" ", strip=True)

        if not href:
            continue

        links.append({
            "text": text,
            "href": href,
        })

    print()
    print("找到連結數:")
    print(len(links))

    for index, link in enumerate(links, start=1):
        print()
        print(f"Link {index}:")
        print("  text:", link["text"])
        print("  href:", link["href"])

    docx_links = []

    for link in links:
        href = link["href"]

        if ".docx" in href.lower():
            docx_links.append(link)

    if not docx_links:
        print()
        print("沒有找到 DOCX 連結。")
        return None

    href = docx_links[0]["href"]

    if href.startswith("http://") or href.startswith("https://"):
        docx_url = href
    else:
        docx_url = BASE_URL + href

    print()
    print("找到 DOCX:")
    print(docx_url)

    return {
        "url": docx_url,
        "text": docx_links[0]["text"],
        "all_links": links,
    }


# ============================================================
# 5. 下載 DOCX
# ============================================================

def download_docx(docx_info):
    print()
    print("=" * 70)
    print("[3] 下載 DOCX 場次資訊")
    print("=" * 70)

    if not docx_info:
        print("沒有 DOCX 資訊。")
        return False

    url = docx_info["url"]

    print()
    print("DOCX URL:")
    print(url)

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=60,
        )
    except Exception as e:
        print()
        print("DOCX download error:")
        print(repr(e))

        return False

    print()
    print("HTTP Status:")
    print(response.status_code)

    print()
    print("Content-Type:")
    print(response.headers.get("Content-Type"))

    print()
    print("Content Length:")
    print(len(response.content))

    if response.status_code != 200:
        print()
        print("DOCX 下載失敗。")

        print()
        print("Response:")
        print(response.text[:3000])

        return False

    content_type = (
        response.headers.get("Content-Type") or ""
    ).lower()

    if (
        "word" not in content_type
        and "octet-stream" not in content_type
        and not response.content.startswith(b"PK")
    ):
        print()
        print("警告：回應看起來不像正常 DOCX。")

        print()
        print("前 100 bytes:")
        print(response.content[:100])

    DOCX_FILE.write_bytes(response.content)

    print()
    print("Saved:")
    print(DOCX_FILE)

    print()
    print("File Size:")
    print(DOCX_FILE.stat().st_size)

    return True


# ============================================================
# 6. 解析 DOCX
# ============================================================

def parse_docx():
    print()
    print("=" * 70)
    print("[4] 解析 DOCX")
    print("=" * 70)

    if not DOCX_FILE.exists():
        print("DOCX 檔案不存在。")
        return None

    try:
        document = Document(DOCX_FILE)
    except Exception as e:
        print()
        print("DOCX parse error:")
        print(repr(e))

        return None

    paragraphs = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()

        if text:
            paragraphs.append(text)

    tables = []

    for table_index, table in enumerate(
        document.tables,
        start=1,
    ):
        rows = []

        for row in table.rows:
            cells = []

            for cell in row.cells:
                cells.append(
                    cell.text.strip()
                )

            rows.append(cells)

        tables.append({
            "table_index": table_index,
            "rows": rows,
        })

    print()
    print("Paragraph Count:")
    print(len(paragraphs))

    print()
    print("Table Count:")
    print(len(tables))

    # --------------------------------------------------------
    # 印出段落
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DOCX 段落")
    print("=" * 70)

    for index, text in enumerate(
        paragraphs,
        start=1,
    ):
        print(f"[P{index}] {text}")

    # --------------------------------------------------------
    # 印出表格
    # --------------------------------------------------------

    for table in tables:
        print()
        print("=" * 70)
        print(
            f"DOCX Table "
            f"{table['table_index']}"
        )
        print("=" * 70)

        for row_index, row in enumerate(
            table["rows"],
            start=1,
        ):
            print(
                f"[R{row_index}] "
                + " | ".join(row)
            )

    # --------------------------------------------------------
    # 建立純文字輸出
    # --------------------------------------------------------

    text_lines = []

    text_lines.append(
        "===== DOCX PARAGRAPHS ====="
    )

    for text in paragraphs:
        text_lines.append(text)

    for table in tables:
        text_lines.append("")
        text_lines.append(
            f"===== TABLE "
            f"{table['table_index']} ====="
        )

        for row in table["rows"]:
            text_lines.append(
                " | ".join(row)
            )

    TEXT_FILE.write_text(
        "\n".join(text_lines),
        encoding="utf-8",
    )

    print()
    print("Saved:")
    print(TEXT_FILE)

    return {
        "paragraphs": paragraphs,
        "tables": tables,
    }


# ============================================================
# 7. 主程式
# ============================================================

def main():
    result = {
        "event_api": EVENT_API,
        "event_id": EVENT_ID,
        "event_detail": None,
        "docx": None,
        "document": None,
        "errors": [],
    }

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    event_data = get_event_detail()

    if event_data is None:
        result["errors"].append(
            "eventDetail API 取得失敗"
        )

        save_json(result)

        print()
        print("=" * 70)
        print("第七版測試失敗")
        print("=" * 70)

        return

    result["event_detail"] = event_data

    # --------------------------------------------------------
    # DOCX URL
    # --------------------------------------------------------

    docx_info = find_docx_url(
        event_data
    )

    if docx_info is None:
        result["errors"].append(
            "eventDetail 中沒有找到 DOCX"
        )

        save_json(result)

        print()
        print("=" * 70)
        print("第七版測試完成，但沒有找到 DOCX")
        print("=" * 70)

        return

    result["docx"] = {
        "url": docx_info["url"],
        "text": docx_info["text"],
        "all_links": docx_info["all_links"],
    }

    # --------------------------------------------------------
    # Download DOCX
    # --------------------------------------------------------

    if not download_docx(docx_info):
        result["errors"].append(
            "DOCX 下載失敗"
        )

        save_json(result)

        print()
        print("=" * 70)
        print("第七版測試完成，但 DOCX 下載失敗")
        print("=" * 70)

        return

    # --------------------------------------------------------
    # Parse DOCX
    # --------------------------------------------------------

    document_data = parse_docx()

    if document_data is None:
        result["errors"].append(
            "DOCX 解析失敗"
        )

        save_json(result)

        print()
        print("=" * 70)
        print("第七版測試完成，但 DOCX 解析失敗")
        print("=" * 70)

        return

    result["document"] = document_data

    # --------------------------------------------------------
    # Save JSON
    # --------------------------------------------------------

    save_json(result)

    print()
    print("=" * 70)
    print("[5] 保存第七版測試結果")
    print("=" * 70)

    print()
    print("Saved:")
    print(RESULT_FILE)

    print()
    print("=" * 70)
    print("第七版測試完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
