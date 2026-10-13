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

OUTPUT_FILE = Path("conference_page_debug.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


# ============================================================
# 工具
# ============================================================

def print_section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def get_page(url):
    print_section("GET")
    print(url)

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    print("HTTP:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))
    print("Final URL:", response.url)
    print("Bytes:", len(response.content))

    response.raise_for_status()

    return response


def extract_event_url(html):
    """
    從法人說明會活動列找出官方 content.html URL。
    """

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

    # 備用：整頁搜尋
    pos = html.find(TARGET_TITLE)

    if pos >= 0:
        start = max(0, pos - 3000)
        end = min(len(html), pos + 5000)

        block = html[start:end]

        urls = re.findall(
            r'https://www\.twse\.com\.tw/(?:zh/)?about/news/event/content\.html\?[^"\s<]+',
            block,
            re.IGNORECASE,
        )

        if urls:
            return urls[0]

    return None


def extract_all_urls(html):
    """
    找出 HTML 裡所有完整 URL。
    """

    urls = re.findall(
        r'https?://[^"\'<>\s]+',
        html,
        re.IGNORECASE,
    )

    return sorted(set(urls))


def extract_relative_links(html):
    """
    找出 href/src 等相對路徑。
    """

    results = []

    patterns = [
        r'href\s*=\s*["\']([^"\']+)["\']',
        r'src\s*=\s*["\']([^"\']+)["\']',
        r'url\s*:\s*["\']([^"\']+)["\']',
        r'url\s*=\s*["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        results.extend(
            re.findall(
                pattern,
                html,
                re.IGNORECASE,
            )
        )

    return sorted(set(results))


def extract_scripts(html):
    """
    找出 script 標籤。
    """

    results = []

    pattern = re.compile(
        r'<script\b([^>]*)>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )

    for attrs, body in pattern.findall(html):
        results.append(
            {
                "attrs": attrs.strip(),
                "body": body.strip(),
            }
        )

    return results


def find_interesting_lines(html):
    """
    尋找可能代表資料下載/API/動態載入的關鍵字。
    """

    keywords = [
        "pdf",
        "download",
        "file",
        "iframe",
        "api",
        "ajax",
        "fetch",
        "axios",
        "event",
        "content",
        "法人說明會",
        "上市公司",
        "資料",
        "下載",
    ]

    lines = html.splitlines()

    matched = []

    for index, line in enumerate(lines, start=1):

        lower = line.lower()

        if any(keyword.lower() in lower for keyword in keywords):

            matched.append(
                {
                    "line": index,
                    "text": line.strip(),
                }
            )

    return matched


def extract_possible_resources(html, base_url):
    """
    找出所有看起來可能是下載資源的連結。
    """

    candidates = []

    # href
    hrefs = re.findall(
        r'href\s*=\s*["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )

    # src
    srcs = re.findall(
        r'src\s*=\s*["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )

    all_links = hrefs + srcs

    for link in all_links:

        absolute = urljoin(base_url, link)

        lower = absolute.lower()

        if any(
            keyword in lower
            for keyword in [
                ".pdf",
                "download",
                "file",
                "attachment",
                "event",
                "content",
                "media",
                "upload",
            ]
        ):
            candidates.append(absolute)

    return sorted(set(candidates))


# ============================================================
# 主程式
# ============================================================

def main():

    print_section("TWSE 法人說明會官方頁面結構測試")

    print("目標活動：")
    print(TARGET_TITLE)

    # --------------------------------------------------------
    # 1. 活動列表
    # --------------------------------------------------------

    response = get_page(EVENT_LIST_URL)

    event_list_html = response.text

    event_url = extract_event_url(event_list_html)

    if not event_url:
        raise RuntimeError(
            "找不到目標法人說明會活動 URL"
        )

    print_section("找到法人說明會活動")

    print("標題：")
    print(TARGET_TITLE)

    print()
    print("URL：")
    print(event_url)

    # --------------------------------------------------------
    # 2. 活動內容頁
    # --------------------------------------------------------

    response = get_page(event_url)

    html = response.text

    print_section("活動頁面基本資訊")

    print("HTML 長度：", len(html))

    # --------------------------------------------------------
    # 3. 頁面中的完整 URL
    # --------------------------------------------------------

    full_urls = extract_all_urls(html)

    print_section("HTML 中的完整 URL")

    print("數量：", len(full_urls))

    for url in full_urls:
        print(url)

    # --------------------------------------------------------
    # 4. href / src
    # --------------------------------------------------------

    relative_links = extract_relative_links(html)

    print_section("HTML 中的 href / src / URL 參數")

    print("數量：", len(relative_links))

    for link in relative_links:

        absolute = urljoin(event_url, link)

        print()
        print("原始：", link)
        print("完整：", absolute)

    # --------------------------------------------------------
    # 5. 可能的資源
    # --------------------------------------------------------

    candidates = extract_possible_resources(
        html,
        event_url,
    )

    print_section("可能的下載/API/資料資源")

    if candidates:

        for url in candidates:
            print(url)

    else:

        print("沒有找到明顯的下載資源")

    # --------------------------------------------------------
    # 6. Script
    # --------------------------------------------------------

    scripts = extract_scripts(html)

    print_section("Script 資訊")

    print("Script 數量：", len(scripts))

    for index, script in enumerate(scripts, start=1):

        print()
        print("----- SCRIPT", index, "-----")

        print("ATTRS:")
        print(script["attrs"])

        body = script["body"]

        print("BODY LENGTH:", len(body))

        if body:

            # 只顯示前 3000 字，避免 GitHub Actions Log 太大
            print(body[:3000])

    # --------------------------------------------------------
    # 7. 關鍵字行
    # --------------------------------------------------------

    interesting = find_interesting_lines(html)

    print_section("關鍵字命中行")

    print("命中數量：", len(interesting))

    for item in interesting:

        print(
            f"[LINE {item['line']}] "
            f"{item['text']}"
        )

    # --------------------------------------------------------
    # 8. 儲存完整除錯資料
    # --------------------------------------------------------

    result = {
        "target_title": TARGET_TITLE,
        "event_url": event_url,
        "html_length": len(html),
        "full_urls": full_urls,
        "links": [
            {
                "original": link,
                "absolute": urljoin(event_url, link),
            }
            for link in relative_links
        ],
        "resource_candidates": candidates,
        "scripts": scripts,
        "interesting_lines": interesting,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print_section("完成")

    print("除錯資料已輸出：")
    print(OUTPUT_FILE)

    print()
    print(
        "這一階段不下載 PDF、不解析法人說明會資料，"
        "只確認 TWSE 官方頁面的實際資料結構。"
    )


if __name__ == "__main__":
    main()
