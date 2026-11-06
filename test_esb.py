import re
import requests
from pathlib import Path
from urllib.parse import urljoin

BASE_DIR = Path(__file__).resolve().parent

PAGE_URL = (
    "https://www.tpex.org.tw/"
    "zh-tw/esb/trading/info/stock-pricing.html"
)

PARAMS = {
    "type": "Monthly",
    "date": "2026/11/01",
    "code": "6750",
    "id": "",
}

JS_FILES = {
    "main.js": "https://www.tpex.org.tw/rsrc/js/main.js",
    "global.js": "https://www.tpex.org.tw/rsrc/asset/js/global.js",
    "tables.js": "https://www.tpex.org.tw/rsrc/js/tables.js",
}

KEYWORDS = [
    "API_PATTERN",
    "emerging/historical",
    "emerging",
    "historical",
    "tables.init",
    "$.ajax",
    "$.get",
    "$.post",
    "ajax(",
    "fetch(",
    "XMLHttpRequest",
    "dataType",
    "contentType",
    "response",
    "action:",
    "pattern:",
    "FormData",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/javascript,*/*",
}


def save_text(filename, content):
    path = BASE_DIR / filename
    path.write_text(content, encoding="utf-8")
    print(f"已保存：{filename} ({len(content)} 字元)")


def inspect_content(name, content):
    print("\n" + "=" * 75)
    print(f"檢查檔案：{name}")
    print("=" * 75)

    print(f"內容長度：{len(content)} 字元")
    print("\n[檔案開頭]")
    print(content[:1500])

    for keyword in KEYWORDS:
        positions = []
        start = 0

        while True:
            pos = content.lower().find(keyword.lower(), start)
            if pos < 0:
                break

            positions.append(pos)
            start = pos + len(keyword)

            if len(positions) >= 5:
                break

        if not positions:
            continue

        print(f"\n[關鍵字：{keyword}] 共找到至少 {len(positions)} 個位置")

        for index, pos in enumerate(positions, 1):
            left = max(0, pos - 500)
            right = min(len(content), pos + 1200)

            print(f"\n--- 命中 {index} ---")
            print(content[left:right])


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    print("=" * 75)
    print("櫃買中心興櫃行情 API 深度診斷")
    print("測試股票：6750")
    print("=" * 75)

    # 1. 取得行情頁面
    print("\n[1] 取得興櫃歷史行情頁面")

    response = session.get(
        PAGE_URL,
        params=PARAMS,
        timeout=30,
    )

    print("HTTP：", response.status_code)
    print("URL：", response.url)
    print("Content-Type：", response.headers.get("Content-Type"))

    response.raise_for_status()

    response.encoding = "utf-8"
    html = response.text

    save_text("esb_6750_response.txt", html)

    # 2. 檢查 HTML 中的 API_PATTERN 與 tables.init
    print("\n[2] 檢查 HTML 內嵌 JavaScript")

    scripts = re.findall(
        r"<script\b[^>]*>(.*?)</script>",
        html,
        flags=re.I | re.S,
    )

    inline_text = "\n\n".join(scripts)
    save_text("esb_inline_scripts.txt", inline_text)

    inspect_content("HTML inline scripts", inline_text)

    # 3. 下載並保存指定 JS
    print("\n[3] 下載 main.js、global.js、tables.js")

    downloaded = {}

    for filename, url in JS_FILES.items():
        print(f"\n下載：{url}")

        try:
            js_response = session.get(
                url,
                headers={"Referer": response.url},
                timeout=30,
            )

            print("HTTP：", js_response.status_code)
            print("Content-Type：", js_response.headers.get("Content-Type"))

            js_response.raise_for_status()

            js_response.encoding = "utf-8"
            content = js_response.text

            downloaded[filename] = content

            output_name = "esb_" + filename + ".txt"
            save_text(output_name, content)

            inspect_content(filename, content)

        except Exception as exc:
            print(f"下載失敗：{exc}")

    # 4. 建立集中診斷報告
    print("\n[4] 建立集中診斷報告")

    report = []

    report.append("櫃買中心興櫃行情 API 診斷報告")
    report.append("=" * 75)

    report.append("\n[HTML inline scripts]")
    report.append(inline_text)

    for filename, content in downloaded.items():
        report.append("\n\n" + "=" * 75)
        report.append(f"[{filename}]")
        report.append("=" * 75)
        report.append(content)

    save_text(
        "esb_6750_full_js_diagnostic.txt",
        "\n".join(report),
    )

    print("\n" + "=" * 75)
    print("診斷完成")
    print("請下載 GitHub Actions Artifact 查看以下檔案：")
    print("1. esb_6750_full_js_diagnostic.txt")
    print("2. esb_tables.js.txt")
    print("3. esb_main.js.txt")
    print("4. esb_global.js.txt")
    print("5. esb_inline_scripts.txt")
    print("=" * 75)


if __name__ == "__main__":
    main()
