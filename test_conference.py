import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# 1. 基本設定
# ============================================================

BASE_URL = "https://www.twse.com.tw"

EVENT_LIST_PAGE = (
    "https://www.twse.com.tw/zh/about/news/event/list.html"
)

# 第 7 版已確認可用的 API
EVENT_DETAIL_API = (
    "https://www.twse.com.tw/rwd/zh/news/eventDetail"
)

# OpenAPI 文件列出的活動訊息 API
OPENAPI_EVENT_LIST = (
    "https://openapi.twse.com.tw/v1/news/eventList"
)

TARGET_KEYWORD = "法人說明會"

TIMEOUT = 30

RESULT_JSON = Path("twse_conference_v8_result.json")


# ============================================================
# 2. Session
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
)


# ============================================================
# 3. 工具函式
# ============================================================

def print_separator(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def save_result(result):
    RESULT_JSON.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("Saved:")
    print(RESULT_JSON)


def safe_json_response(response):
    try:
        return response.json()
    except Exception:
        return {
            "_json_error": True,
            "status_code": response.status_code,
            "text": response.text[:5000],
        }


def collect_links_from_html(html):
    soup = BeautifulSoup(html, "html.parser")

    links = []

    for a in soup.find_all("a"):
        href = a.get("href")

        if not href:
            continue

        text = a.get_text(" ", strip=True)

        links.append(
            {
                "text": text,
                "href": href,
                "absolute_url": urljoin(BASE_URL, href),
            }
        )

    return links


def find_api_attributes(html):
    """
    找出 HTML 裡可能與 API 有關的 data-* 屬性。
    """

    soup = BeautifulSoup(html, "html.parser")

    results = []

    for tag in soup.find_all(True):
        attrs = tag.attrs

        for key, value in attrs.items():
            if not key.lower().startswith("data-"):
                continue

            key_lower = key.lower()

            if (
                "api" in key_lower
                or "host" in key_lower
                or "load" in key_lower
                or "query" in key_lower
            ):
                results.append(
                    {
                        "tag": tag.name,
                        "id": tag.get("id"),
                        "class": tag.get("class"),
                        "attribute": key,
                        "value": value,
                    }
                )

    return results


def search_text_for_event_ids(text):
    """
    從 HTML / JavaScript 文字中找可能的 TWSE Event ID。

    TWSE 目前常見 ID 格式為：
    8a8216d6xxxxxxxxxxxxxxxxxxxxxxxx
    """

    patterns = [
        r"8a8216d6[a-fA-F0-9]{24}",
        r"ff808081[a-fA-F0-9]{24}",
    ]

    found = []

    for pattern in patterns:
        for match in re.findall(pattern, text):
            if match not in found:
                found.append(match)

    return found


def print_json_preview(data, max_length=8000):
    text = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )

    if len(text) <= max_length:
        print(text)
    else:
        print(text[:max_length])
        print()
        print(
            f"... JSON 太長，僅顯示前 {max_length} 個字元 ..."
        )


# ============================================================
# 4. 取得活動列表頁
# ============================================================

print_separator(
    "[1] 取得 TWSE 活動訊息列表頁"
)

print()
print("URL:")
print(EVENT_LIST_PAGE)

result = {
    "event_list_page": {
        "url": EVENT_LIST_PAGE,
    },
    "openapi_event_list": {
        "url": OPENAPI_EVENT_LIST,
    },
    "tests": [],
}


try:
    response = session.get(
        EVENT_LIST_PAGE,
        timeout=TIMEOUT,
    )

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

    html = response.text

    result["event_list_page"].update(
        {
            "http_status": response.status_code,
            "final_url": response.url,
            "content_type": response.headers.get(
                "Content-Type"
            ),
            "length": len(response.content),
        }
    )

except Exception as exc:
    print()
    print("ERROR:")
    print(repr(exc))

    result["event_list_page"]["error"] = repr(exc)

    save_result(result)
    raise


# ============================================================
# 5. 檢查活動列表頁 HTML
# ============================================================

print_separator(
    "[2] 分析活動訊息列表頁 HTML"
)

print()
print("HTML 中是否包含「法人說明會」:")
print(TARGET_KEYWORD in html)

print()
print("HTML 長度:")
print(len(html))

# 找 data-* API
api_attributes = find_api_attributes(html)

print()
print("找到可能的 API / data-* 屬性數量:")
print(len(api_attributes))

for index, item in enumerate(
    api_attributes[:100],
    start=1,
):
    print()
    print(f"API Attribute {index}:")
    print(json.dumps(
        item,
        ensure_ascii=False,
        indent=2,
    ))

result["event_list_page"]["api_attributes"] = (
    api_attributes
)

# 找 HTML 裡的連結
links = collect_links_from_html(html)

print()
print("HTML Link 數量:")
print(len(links))

for index, link in enumerate(
    links[:100],
    start=1,
):
    print()
    print(f"Link {index}:")
    print("  text:", link["text"])
    print("  href:", link["href"])

result["event_list_page"]["links"] = links


# ============================================================
# 6. 從 HTML / JavaScript 搜尋 Event ID
# ============================================================

print_separator(
    "[3] 從活動列表頁搜尋 Event ID"
)

event_ids_from_html = search_text_for_event_ids(html)

print()
print("找到 Event ID 數量:")
print(len(event_ids_from_html))

for index, event_id in enumerate(
    event_ids_from_html,
    start=1,
):
    print()
    print(f"Event ID {index}:")
    print(event_id)

result["event_list_page"]["event_ids_found"] = (
    event_ids_from_html
)


# ============================================================
# 7. 測試 OpenAPI /news/eventList
# ============================================================

print_separator(
    "[4] 測試 TWSE OpenAPI /news/eventList"
)

print()
print("API:")
print(OPENAPI_EVENT_LIST)

openapi_headers = {
    "Accept": "application/json",
}

try:
    openapi_response = session.get(
        OPENAPI_EVENT_LIST,
        headers=openapi_headers,
        timeout=TIMEOUT,
    )

    print()
    print("HTTP Status:")
    print(openapi_response.status_code)

    print()
    print("Final URL:")
    print(openapi_response.url)

    print()
    print("Content-Type:")
    print(
        openapi_response.headers.get(
            "Content-Type"
        )
    )

    print()
    print("Response Length:")
    print(len(openapi_response.content))

    openapi_data = safe_json_response(
        openapi_response
    )

    print()
    print("JSON / Response:")
    print_json_preview(openapi_data)

    result["tests"].append(
        {
            "name": "openapi_event_list",
            "url": OPENAPI_EVENT_LIST,
            "http_status": openapi_response.status_code,
            "content_type": openapi_response.headers.get(
                "Content-Type"
            ),
            "length": len(openapi_response.content),
            "response": openapi_data,
        }
    )

except Exception as exc:
    print()
    print("ERROR:")
    print(repr(exc))

    result["tests"].append(
        {
            "name": "openapi_event_list",
            "url": OPENAPI_EVENT_LIST,
            "error": repr(exc),
        }
    )


# ============================================================
# 8. 嘗試 RWD /news/eventList
# ============================================================

print_separator(
    "[5] 測試 TWSE RWD /news/eventList"
)

RWD_EVENT_LIST = (
    "https://www.twse.com.tw/rwd/zh/news/eventList"
)

print()
print("API:")
print(RWD_EVENT_LIST)

rwd_params_list = [
    {
        "response": "json",
    },
    {
        "response": "json",
        "lang": "zh",
    },
]

for index, params in enumerate(
    rwd_params_list,
    start=1,
):

    print()
    print("-" * 70)
    print(f"RWD 測試 {index}")
    print("-" * 70)

    print()
    print("Params:")
    print(json.dumps(
        params,
        ensure_ascii=False,
        indent=2,
    ))

    try:
        rwd_response = session.get(
            RWD_EVENT_LIST,
            params=params,
            timeout=TIMEOUT,
        )

        print()
        print("HTTP Status:")
        print(rwd_response.status_code)

        print()
        print("Final URL:")
        print(rwd_response.url)

        print()
        print("Content-Type:")
        print(
            rwd_response.headers.get(
                "Content-Type"
            )
        )

        print()
        print("Response Length:")
        print(len(rwd_response.content))

        rwd_data = safe_json_response(
            rwd_response
        )

        print()
        print("Response:")
        print_json_preview(rwd_data)

        result["tests"].append(
            {
                "name": f"rwd_event_list_{index}",
                "url": RWD_EVENT_LIST,
                "params": params,
                "http_status": rwd_response.status_code,
                "final_url": rwd_response.url,
                "content_type": rwd_response.headers.get(
                    "Content-Type"
                ),
                "length": len(rwd_response.content),
                "response": rwd_data,
            }
        )

    except Exception as exc:
        print()
        print("ERROR:")
        print(repr(exc))

        result["tests"].append(
            {
                "name": f"rwd_event_list_{index}",
                "url": RWD_EVENT_LIST,
                "params": params,
                "error": repr(exc),
            }
        )


# ============================================================
# 9. 如果 HTML 已經直接找到 Event ID，
#    測試 eventDetail
# ============================================================

print_separator(
    "[6] 測試找到的 Event ID"
)

if not event_ids_from_html:

    print()
    print("活動列表 HTML 中沒有直接找到 Event ID。")
    print()
    print(
        "這不是錯誤，代表 Event ID 可能由 JavaScript "
        "API 動態載入。"
    )

else:

    for index, event_id in enumerate(
        event_ids_from_html[:20],
        start=1,
    ):

        print()
        print("-" * 70)
        print(f"Event ID 測試 {index}")
        print("-" * 70)

        print()
        print("Event ID:")
        print(event_id)

        params = {
            "id": event_id,
            "response": "json",
        }

        try:
            detail_response = session.get(
                EVENT_DETAIL_API,
                params=params,
                timeout=TIMEOUT,
            )

            print()
            print("HTTP Status:")
            print(detail_response.status_code)

            print()
            print("Final URL:")
            print(detail_response.url)

            detail_data = safe_json_response(
                detail_response
            )

            print()
            print("Response:")
            print_json_preview(detail_data)

            result["tests"].append(
                {
                    "name": (
                        f"event_detail_{index}"
                    ),
                    "event_id": event_id,
                    "params": params,
                    "http_status": (
                        detail_response.status_code
                    ),
                    "final_url": detail_response.url,
                    "response": detail_data,
                }
            )

        except Exception as exc:

            print()
            print("ERROR:")
            print(repr(exc))

            result["tests"].append(
                {
                    "name": (
                        f"event_detail_{index}"
                    ),
                    "event_id": event_id,
                    "params": params,
                    "error": repr(exc),
                }
            )


# ============================================================
# 10. 儲存結果
# ============================================================

print_separator(
    "[7] 保存第八版測試結果"
)

save_result(result)

print()
print("第八版測試完成")
