import json
import re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
# ============================================================
# 1. 基本設定
# ============================================================
PAGE_URL = (
    "https://www.twse.com.tw/zh/about/news/event/"
    "content.html?8a8216d6a0bdcc0001a0c849c4ae001c"
)
EVENT_ID = "8a8216d6a0bdcc0001a0c849c4ae001c"
BASE_URL = "https://www.twse.com.tw"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": (
        "application/json,text/javascript,*/*;q=0.8"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": PAGE_URL,
}
# ============================================================
# 2. 工具
# ============================================================
def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
def save_json(filename, data):
    Path(filename).write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
def print_json(data):
    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
    )
def download(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    return response
# ============================================================
# 3. 從 TWSE JavaScript 找 apiHost.rwd
# ============================================================
def find_api_hosts():
    section("[1] 搜尋 TWSE API Host")
    script_urls = [
        "https://www.twse.com.tw/res/js/main.js",
        "https://www.twse.com.tw/res/js/web.js",
        "https://www.twse.com.tw/res/js/web-report.js",
    ]
    found = []
    for script_url in script_urls:
        print("\nJavaScript:")
        print(script_url)
        try:
            response = download(script_url)
            print("HTTP:", response.status_code)
            print("Length:", len(response.text))
            text = response.text
        except Exception as exc:
            print(
                "[ERROR]",
                type(exc).__name__,
                str(exc),
            )
            continue
        # ----------------------------------------------------
        # 搜尋 apiHost 相關內容
        # ----------------------------------------------------
        matches = list(
            re.finditer(
                r"apiHost",
                text,
                flags=re.IGNORECASE,
            )
        )
        print("apiHost occurrences:", len(matches))
        for match in matches[:20]:
            start = max(0, match.start() - 300)
            end = min(len(text), match.end() + 800)
            context = text[start:end]
            print("\n--- apiHost context ---")
            print(context)
            # ------------------------------------------------
            # 嘗試找 rwd: "..."
            # ------------------------------------------------
            patterns = [
                r'rwd\s*:\s*["\']([^"\']+)["\']',
                r'"rwd"\s*:\s*["\']([^"\']+)["\']',
                r"'rwd'\s*:\s*['\"]([^'\"]+)['\"]",
            ]
            for pattern in patterns:
                for value in re.findall(
                    pattern,
                    context,
                    flags=re.IGNORECASE,
                ):
                    if value not in found:
                        found.append(value)
    print("\n找到的 apiHost.rwd 候選值:")
    if not found:
        print("(沒有直接找到)")
    for index, value in enumerate(found, start=1):
        print(f"{index}. {value}")
    return found
# ============================================================
# 4. 直接測試 /news/eventDetail
# ============================================================
def test_event_detail(api_hosts):
    section("[2] 測試 /news/eventDetail")
    api_path = "/news/eventDetail"
    results = []
    # --------------------------------------------------------
    # 如果 JavaScript 沒有直接找到 Host，
    # 不自行假設真正結果。
    # 但 TWSE 主站本身可作為最後測試候選。
    # --------------------------------------------------------
    candidates = []
    for host in api_hosts:
        if host.startswith("http://") or host.startswith("https://"):
            candidates.append(host.rstrip("/"))
        else:
            candidates.append(
                urljoin(BASE_URL, host).rstrip("/")
            )
    # 去除重複
    candidates = list(dict.fromkeys(candidates))
    print("\nAPI Host candidates:")
    if not candidates:
        print("(沒有找到 API Host，因此不自行猜測)")
        return results
    for index, host in enumerate(candidates, start=1):
        print(f"{index}. {host}")
    # --------------------------------------------------------
    # 查詢參數
    # --------------------------------------------------------
    params = {
        "id": EVENT_ID,
        "response": "json",
    }
    print("\nQuery parameters:")
    print_json(params)
    # --------------------------------------------------------
    # 逐一測試
    # --------------------------------------------------------
    for host in candidates:
        api_url = host + "/zh" + api_path
        print("\n" + "-" * 70)
        print("Testing API:")
        print(api_url)
        print("-" * 70)
        try:
            response = requests.get(
                api_url,
                params=params,
                headers=HEADERS,
                timeout=30,
            )
            print("HTTP Status:")
            print(response.status_code)
            print("\nFinal URL:")
            print(response.url)
            print("\nContent-Type:")
            print(response.headers.get("Content-Type"))
            print("\nResponse Length:")
            print(len(response.text))
            result_item = {
                "api_url": api_url,
                "final_url": response.url,
                "status_code": response.status_code,
                "content_type": response.headers.get(
                    "Content-Type"
                ),
                "response_length": len(response.text),
            }
            # ------------------------------------------------
            # 嘗試 JSON
            # ------------------------------------------------
            try:
                data = response.json()
                result_item["json"] = data
                print("\nJSON response:")
                print_json(data)
            except Exception as exc:
                result_item["json_error"] = (
                    type(exc).__name__ + ": " + str(exc)
                )
                print("\nResponse is NOT JSON.")
                print("First 3000 characters:")
                print(response.text[:3000])
            results.append(result_item)
        except Exception as exc:
            print(
                "[ERROR]",
                type(exc).__name__,
                str(exc),
            )
            results.append({
                "api_url": api_url,
                "error": (
                    type(exc).__name__ + ": " + str(exc)
                ),
            })
    return results
# ============================================================
# 5. 同時測試不同參數形式
# ============================================================
def test_parameter_variations(api_hosts):
    section("[3] 測試事件 ID 參數形式")
    results = []
    if not api_hosts:
        print("沒有 API Host，跳過。")
        return results
    host = api_hosts[0]
    if not host.startswith("http://") and not host.startswith("https://"):
        host = urljoin(BASE_URL, host)
    host = host.rstrip("/")
    api_url = host + "/zh/news/eventDetail"
    parameter_sets = [
        {
            "id": EVENT_ID,
            "response": "json",
        },
        {
            "id": EVENT_ID,
        },
        {
            "eventId": EVENT_ID,
            "response": "json",
        },
        {
            "eventID": EVENT_ID,
            "response": "json",
        },
    ]
    for index, params in enumerate(
        parameter_sets,
        start=1,
    ):
        print("\n" + "-" * 70)
        print(f"Parameter Test {index}")
        print("-" * 70)
        print("URL:")
        print(api_url)
        print("Params:")
        print_json(params)
        try:
            response = requests.get(
                api_url,
                params=params,
                headers=HEADERS,
                timeout=30,
            )
            print("HTTP:", response.status_code)
            print("Final URL:")
            print(response.url)
            print("Content-Type:")
            print(
                response.headers.get(
                    "Content-Type"
                )
            )
            print("Length:")
            print(len(response.text))
            try:
                data = response.json()
                print("\nJSON:")
                print_json(data)
                results.append({
                    "params": params,
                    "status_code": response.status_code,
                    "final_url": response.url,
                    "json": data,
                })
            except Exception:
                print("\nNot JSON.")
                print(
                    response.text[:3000]
                )
                results.append({
                    "params": params,
                    "status_code": response.status_code,
                    "final_url": response.url,
                    "text": response.text[:3000],
                })
        except Exception as exc:
            print(
                "[ERROR]",
                type(exc).__name__,
                str(exc),
            )
            results.append({
                "params": params,
                "error": (
                    type(exc).__name__
                    + ": "
                    + str(exc)
                ),
            })
    return results
# ============================================================
# 6. 主程式
# ============================================================
def main():
    section(
        "TWSE 法人說明會 API 測試 - 第六版"
    )
    print("Event Page:")
    print(PAGE_URL)
    print("\nEvent ID:")
    print(EVENT_ID)
    # --------------------------------------------------------
    # 1. 找 API Host
    # --------------------------------------------------------
    api_hosts = find_api_hosts()
    # --------------------------------------------------------
    # 2. 測試真正 API
    # --------------------------------------------------------
    event_results = test_event_detail(
        api_hosts
    )
    # --------------------------------------------------------
    # 3. 測試不同參數
    # --------------------------------------------------------
    parameter_results = test_parameter_variations(
        api_hosts
    )
    # --------------------------------------------------------
    # 4. 保存結果
    # --------------------------------------------------------
    section("[4] 保存第六版測試結果")
    result = {
        "page_url": PAGE_URL,
        "event_id": EVENT_ID,
        "api_hosts": api_hosts,
        "event_detail_results": event_results,
        "parameter_variation_results": parameter_results,
    }
    filename = (
        "twse_conference_v6_result.json"
    )
    save_json(
        filename,
        result,
    )
    print("Saved:")
    print(filename)
    section("第六版測試完成")
    print(
        "請將以下區段貼回："
    )
    print(
        "1. [1] 搜尋 TWSE API Host"
    )
    print(
        "2. [2] 測試 /news/eventDetail"
    )
    print(
        "3. [3] 測試事件 ID 參數形式"
    )
if __name__ == "__main__":
    main()
