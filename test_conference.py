import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests


# ============================================================
# 基本設定
# ============================================================

EVENT_LIST_URL = "https://www.twse.com.tw/news/eventList?response=html"

TARGET_TITLE = "2026年上市公司辦理法人說明會(10月1日至10月31日)"

OUTPUT_FILE = Path("conference_event_detail.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": EVENT_LIST_URL,
}


# ============================================================
# 顯示工具
# ============================================================

def print_section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ============================================================
# 取得活動列表
# ============================================================

def get_event_list():

    print_section("取得 TWSE 活動列表")

    response = requests.get(
        EVENT_LIST_URL,
        headers=HEADERS,
        timeout=30,
    )

    print("HTTP:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))
    print("Bytes:", len(response.content))

    response.raise_for_status()

    return response.text


# ============================================================
# 找法人說明會活動 URL
# ============================================================

def find_event_url(html):

    pattern = re.compile(
        r'<tr[^>]*>.*?'
        + re.escape(TARGET_TITLE)
        + r'.*?'
        + r'(https://www\.twse\.com\.tw/(?:zh/)?about/news/event/content\.html\?[^"\s<]+)'
        + r'.*?</tr>',
        re.IGNORECASE | re.DOTALL,
    )

    match = pattern.search(html)

    if match:
        return match.group(1)

    # 備用搜尋
    pos = html.find(TARGET_TITLE)

    if pos >= 0:

        block = html[
            max(0, pos - 3000):
            min(len(html), pos + 5000)
        ]

        urls = re.findall(
            r'https://www\.twse\.com\.tw/(?:zh/)?about/news/event/content\.html\?[^"\s<]+',
            block,
            re.IGNORECASE,
        )

        if urls:
            return urls[0]

    return None


# ============================================================
# 從 content URL 取得 ID
# ============================================================

def extract_event_id(event_url):

    if "?" not in event_url:
        return None

    query = event_url.split("?", 1)[1]

    # 與 TWSE pageInit() 相同概念：
    # window.location.search.substr(1).replace(/\W/g,"")
    event_id = re.sub(r"\W", "", query)

    return event_id


# ============================================================
# 呼叫 TWSE eventDetail
# ============================================================

def get_event_detail(event_id, event_url):

    api_url = "https://www.twse.com.tw/news/eventDetail"

    print_section("呼叫 TWSE 法人說明會資料 API")

    print("API：")
    print(api_url)

    print()
    print("ID：")
    print(event_id)

    api_headers = dict(HEADERS)
    api_headers["Referer"] = event_url

    # --------------------------------------------------------
    # 第一種：GET ?id=
    # --------------------------------------------------------

    print()
    print("嘗試 GET ?id=")

    response = requests.get(
        api_url,
        params={"id": event_id},
        headers=api_headers,
        timeout=30,
    )

    print("HTTP:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))
    print("Final URL:", response.url)
    print("Bytes:", len(response.content))

    print()
    print("前 1000 字：")
    print(response.text[:1000])

    if response.status_code == 200:

        try:
            data = response.json()

            print()
            print("GET JSON 解析成功")

            return data

        except Exception as exc:

            print()
            print("GET 不是 JSON：", exc)

    # --------------------------------------------------------
    # 第二種：POST
    # --------------------------------------------------------

    print()
    print("GET 沒有得到 JSON，嘗試 POST")

    response = requests.post(
        api_url,
        data={"id": event_id},
        headers=api_headers,
        timeout=30,
    )

    print("HTTP:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))
    print("Bytes:", len(response.content))

    print()
    print("前 1000 字：")
    print(response.text[:1000])

    response.raise_for_status()

    try:
        return response.json()

    except Exception as exc:

        raise RuntimeError(
            f"TWSE eventDetail 沒有回傳 JSON：{exc}"
        )


# ============================================================
# 遞迴列出 JSON 結構
# ============================================================

def inspect_json(value, path="root", depth=0):

    if depth > 6:
        return

    indent = "  " * depth

    if isinstance(value, dict):

        print(
            f"{indent}{path}: "
            f"dict ({len(value)} keys)"
        )

        for key, child in value.items():

            print(
                f"{indent}  KEY: {key}"
            )

            inspect_json(
                child,
                f"{path}.{key}",
                depth + 1,
            )

    elif isinstance(value, list):

        print(
            f"{indent}{path}: "
            f"list ({len(value)} items)"
        )

        for index, child in enumerate(value[:5]):

            inspect_json(
                child,
                f"{path}[{index}]",
                depth + 1,
            )

    else:

        text = str(value)

        if len(text) > 500:
            text = text[:500] + "..."

        print(
            f"{indent}{path}: "
            f"{text}"
        )


# ============================================================
# 搜尋附件資訊
# ============================================================

def find_attachment_candidates(value, path="root"):

    results = []

    if isinstance(value, dict):

        for key, child in value.items():

            key_lower = str(key).lower()

            # key 本身看起來可能與檔案有關
            if any(
                word in key_lower
                for word in [
                    "file",
                    "download",
                    "attachment",
                    "url",
                    "link",
                    "document",
                ]
            ):

                results.append(
                    {
                        "path": f"{path}.{key}",
                        "value": child,
                    }
                )

            results.extend(
                find_attachment_candidates(
                    child,
                    f"{path}.{key}",
                )
            )

    elif isinstance(value, list):

        for index, child in enumerate(value):

            results.extend(
                find_attachment_candidates(
                    child,
                    f"{path}[{index}]",
                )
            )

    elif isinstance(value, str):

        lower = value.lower()

        # 副檔名
        extensions = [
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".csv",
            ".zip",
            ".ppt",
            ".pptx",
        ]

        if any(ext in lower for ext in extensions):

            results.append(
                {
                    "path": path,
                    "value": value,
                }
            )

        # URL
        if (
            value.startswith("http://")
            or value.startswith("https://")
            or value.startswith("/")
        ):

            results.append(
                {
                    "path": path,
                    "value": value,
                }
            )

    return results


# ============================================================
# 搜尋公司代號
# ============================================================

def find_stock_matches(value, path="root"):

    stock_ids = {
        "1101": "台泥",
        "2330": "台積電",
        "2454": "聯發科",
        "2317": "鴻海",
    }

    results = []

    if isinstance(value, dict):

        for key, child in value.items():

            results.extend(
                find_stock_matches(
                    child,
                    f"{path}.{key}",
                )
            )

    elif isinstance(value, list):

        for index, child in enumerate(value):

            results.extend(
                find_stock_matches(
                    child,
                    f"{path}[{index}]",
                )
            )

    elif isinstance(value, str):

        for stock_id, company in stock_ids.items():

            if stock_id in value:

                results.append(
                    {
                        "stock_id": stock_id,
                        "company": company,
                        "path": path,
                        "value": value,
                    }
                )

    return results


# ============================================================
# 主程式
# ============================================================

def main():

    print_section("TWSE 法人說明會 eventDetail API 測試")

    print("目標活動：")
    print(TARGET_TITLE)

    # --------------------------------------------------------
    # 1. 活動列表
    # --------------------------------------------------------

    html = get_event_list()

    event_url = find_event_url(html)

    if not event_url:
        raise RuntimeError(
            "找不到法人說明會活動 URL"
        )

    print_section("找到法人說明會活動")

    print("標題：")
    print(TARGET_TITLE)

    print()
    print("URL：")
    print(event_url)

    # --------------------------------------------------------
    # 2. 取得 ID
    # --------------------------------------------------------

    event_id = extract_event_id(event_url)

    if not event_id:
        raise RuntimeError(
            "無法從活動 URL 取得 event ID"
        )

    print_section("活動 ID")

    print(event_id)

    # --------------------------------------------------------
    # 3. eventDetail
    # --------------------------------------------------------

    data = get_event_detail(
        event_id,
        event_url,
    )

    # --------------------------------------------------------
    # 4. 儲存原始 JSON
    # --------------------------------------------------------

    OUTPUT_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print_section("TWSE JSON 結構")

    inspect_json(data)

    # --------------------------------------------------------
    # 5. 附件候選
    # --------------------------------------------------------

    print_section("附件 / URL 候選")

    attachments = find_attachment_candidates(data)

    if not attachments:

        print("沒有找到明顯的附件資訊")

    else:

        print(
            "找到",
            len(attachments),
            "個候選項目"
        )

        for item in attachments:

            print()
            print("PATH:")
            print(item["path"])

            print("VALUE:")
            print(item["value"])

    # --------------------------------------------------------
    # 6. 測試股票
    # --------------------------------------------------------

    print_section("測試股票")

    matches = find_stock_matches(data)

    unique = {}

    for item in matches:

        key = (
            item["stock_id"],
            item["path"],
            item["value"],
        )

        unique[key] = item

    if not unique:

        print("沒有找到 1101 / 2330 / 2454 / 2317")

    else:

        for item in unique.values():

            print()
            print(
                item["stock_id"],
                item["company"]
            )

            print(
                "PATH:",
                item["path"]
            )

            print(
                "VALUE:",
                item["value"]
            )

    # --------------------------------------------------------
    # 7. 完成
    # --------------------------------------------------------

    print_section("完成")

    print("原始 JSON 已儲存：")
    print(OUTPUT_FILE)

    print()
    print(
        "目前只測試 TWSE eventDetail 資料來源，"
        "尚未下載任何附件，也尚未修改正式系統。"
    )


if __name__ == "__main__":
    main()
