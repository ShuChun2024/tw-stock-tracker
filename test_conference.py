import json
import re
from urllib.parse import urljoin
import requests
# ============================================================
# TWSE 法人說明會資料測試
# 第四版
#
# 目的：
# 1. 取得 TWSE 法人說明會活動詳細頁
# 2. 取得該頁面引用的 JavaScript
# 3. 尋找真正取得 JSON / AJAX 資料的程式
# 4. 找出可能的 API endpoint
#
# 本程式只做測試
# 不修改 main.py
# 不修改 analysis.json
# 不修改正式分析流程
# ============================================================
PAGE_URL = (
    "https://www.twse.com.tw/zh/about/news/event/"
    "content.html?8a8216d6a0bdcc0001a0c849c4ae001c"
)
BASE_URL = "https://www.twse.com.tw"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.twse.com.tw/",
}
def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
def download_text(url):
    """
    下載文字內容。
    優先使用 requests 自動判斷 encoding。
    若發生 UTF-8 解碼問題，改用 UTF-8 / BIG5 嘗試。
    """
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    # requests 對 TWSE 有時會誤判 encoding。
    # TWSE 現代網站主要使用 UTF-8。
    response.encoding = "utf-8"
    return response.text, response
def find_urls(text):
    """
    從 JavaScript 找出可能的 URL。
    """
    patterns = [
        r"""["']([^"']*(?:/rwd/|/api/|ajax|json)[^"']*)["']""",
        r"""["']([^"']*\.json[^"']*)["']""",
        r"""url\s*:\s*["']([^"']+)["']""",
        r"""url\s*=\s*["']([^"']+)["']""",
        r"""ajax\s*\(\s*["']([^"']+)["']""",
    ]
    results = []
    for pattern in patterns:
        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        for item in matches:
            if item not in results:
                results.append(item)
    return results
def show_keyword_context(text, keywords, max_matches=20):
    """
    顯示關鍵字附近的 JavaScript 程式碼。
    """
    for keyword in keywords:
        print(
            f"\n--- Keyword: {keyword} ---"
        )
        matches = list(
            re.finditer(
                re.escape(keyword),
                text,
                flags=re.IGNORECASE,
            )
        )
        print(
            f"Occurrences: {len(matches)}"
        )
        for match in matches[:max_matches]:
            start = max(
                0,
                match.start() - 500,
            )
            end = min(
                len(text),
                match.end() + 1000,
            )
            print(
                text[start:end]
            )
def main():
    print_section(
        "TWSE 法人說明會資料測試 - 第四版"
    )
    # ========================================================
    # 1. 下載活動詳細頁
    # ========================================================
    print_section("[1] Download Event Page")
    print("URL:")
    print(PAGE_URL)
    try:
        html, response = download_text(
            PAGE_URL
        )
    except Exception as e:
        print("\n[ERROR] Page download failed")
        print(
            type(e).__name__,
            str(e),
        )
        return
    print("\nHTTP Status:")
    print(response.status_code)
    print("\nContent-Type:")
    print(
        response.headers.get(
            "Content-Type"
        )
    )
    print("\nEncoding:")
    print(response.encoding)
    print("\nHTML Length:")
    print(len(html))
    # --------------------------------------------------------
    # 儲存 HTML
    # --------------------------------------------------------
    with open(
        "twse_conference_page_v4.html",
        "w",
        encoding="utf-8",
    ) as f:
        f.write(html)
    print(
        "\nSaved:"
        " twse_conference_page_v4.html"
    )
    # ========================================================
    # 2. 搜尋活動頁內的 JavaScript
    # ========================================================
    print_section(
        "[2] Detect JavaScript Files"
    )
    script_urls = []
    script_pattern = re.compile(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        flags=re.IGNORECASE,
    )
    for match in script_pattern.finditer(
        html
    ):
        src = match.group(1)
        full_url = urljoin(
            BASE_URL,
            src,
        )
        if full_url not in script_urls:
            script_urls.append(
                full_url
            )
    print(
        f"JavaScript files: "
        f"{len(script_urls)}"
    )
    for index, url in enumerate(
        script_urls,
        start=1,
    ):
        print(
            f"{index}. {url}"
        )
    # ========================================================
    # 3. 優先下載 TWSE web-report.js
    # ========================================================
    print_section(
        "[3] Download Relevant JavaScript"
    )
    relevant_scripts = []
    for url in script_urls:
        lower_url = url.lower()
        if (
            "web-report" in lower_url
            or "web.js" in lower_url
            or "main.js" in lower_url
        ):
            relevant_scripts.append(
                url
            )
    print(
        "Relevant JavaScript:"
    )
    for url in relevant_scripts:
        print(url)
    all_js = {}
    for index, url in enumerate(
        relevant_scripts,
        start=1,
    ):
        print(
            f"\nDownloading JS {index}:"
        )
        print(url)
        try:
            js_text, js_response = (
                download_text(url)
            )
            all_js[url] = js_text
            print(
                "HTTP:",
                js_response.status_code,
            )
            print(
                "Length:",
                len(js_text),
            )
        except Exception as e:
            print(
                "[ERROR]",
                type(e).__name__,
                str(e),
            )
    # ========================================================
    # 4. 搜尋 API / AJAX / JSON 關鍵字
    # ========================================================
    print_section(
        "[4] Search JavaScript Keywords"
    )
    keywords = [
        "ajax",
        "$.ajax",
        "$.get",
        "$.post",
        "fetch(",
        "/rwd/",
        "/api/",
        ".json",
        "json",
        "onload",
        "onload-argv",
        "argv",
        "data:",
        "url:",
        "法人說明會",
        "活動訊息",
    ]
    for js_url, js_text in all_js.items():
        print(
            "\n"
            + "-" * 70
        )
        print(
            "FILE:"
        )
        print(js_url)
        print(
            "-" * 70
        )
        for keyword in keywords:
            count = len(
                re.findall(
                    re.escape(keyword),
                    js_text,
                    flags=re.IGNORECASE,
                )
            )
            if count:
                print(
                    f"{keyword}: "
                    f"{count}"
                )
    # ========================================================
    # 5. 顯示 AJAX / API 附近程式碼
    # ========================================================
    print_section(
        "[5] API / AJAX Context"
    )
    context_keywords = [
        "$.ajax",
        "ajax",
        "fetch(",
        "/rwd/",
        "/api/",
        ".json",
        "url:",
        "onload",
        "onload-argv",
    ]
    for js_url, js_text in all_js.items():
        print(
            "\n"
            + "#" * 70
        )
        print(
            "FILE:",
            js_url,
        )
        print(
            "#" * 70
        )
        show_keyword_context(
            js_text,
            context_keywords,
            max_matches=10,
        )
    # ========================================================
    # 6. 擷取可能的 URL
    # ========================================================
    print_section(
        "[6] Possible API URLs"
    )
    possible_urls = []
    for js_url, js_text in all_js.items():
        urls = find_urls(
            js_text
        )
        for url in urls:
            if url not in possible_urls:
                possible_urls.append(
                    url
                )
    print(
        f"Possible URLs: "
        f"{len(possible_urls)}"
    )
    for index, url in enumerate(
        possible_urls,
        start=1,
    ):
        print(
            f"{index}. {url}"
        )
    # ========================================================
    # 7. 搜尋 URL query parameter
    # ========================================================
    print_section(
        "[7] Query Parameter Analysis"
    )
    print(
        "Page query string:"
    )
    query_match = re.search(
        r"\?(.+)$",
        PAGE_URL,
    )
    if query_match:
        query_string = (
            query_match.group(1)
        )
        print(query_string)
        print(
            "\nSanitized ID used by "
            "pageInit():"
        )
        sanitized = re.sub(
            r"\W",
            "",
            query_string,
        )
        print(sanitized)
    # ========================================================
    # 8. 儲存 JavaScript 分析結果
    # ========================================================
    print_section(
        "[8] Save Analysis Result"
    )
    result = {
        "page_url": PAGE_URL,
        "page_status": response.status_code,
        "page_encoding": response.encoding,
        "page_length": len(html),
        "script_urls": script_urls,
        "relevant_scripts": relevant_scripts,
        "possible_urls": possible_urls,
    }
    with open(
        "twse_conference_v4_result.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(
        "Saved:"
        " twse_conference_v4_result.json"
    )
    # ========================================================
    # 9. 完成
    # ========================================================
    print_section(
        "第四版測試完成"
    )
    print(
        "請將以下區段的結果貼回："
    )
    print(
        "1. [3] Download Relevant JavaScript"
    )
    print(
        "2. [4] Search JavaScript Keywords"
    )
    print(
        "3. [5] API / AJAX Context"
    )
    print(
        "4. [6] Possible API URLs"
    )
    print(
        "尤其是 [5] 和 [6]。"
    )
if __name__ == "__main__":
    main()
