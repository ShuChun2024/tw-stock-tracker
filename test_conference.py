import json
import re
import requests
from bs4 import BeautifulSoup
# ============================================================
# TWSE 法人說明會資料測試
# 第三版
#
# 目的：
# 1. 直接取得 TWSE「2026年上市公司辦理法人說明會」
#    活動詳細頁
# 2. 檢查 HTML 是否包含實際法人說明會資料
# 3. 找出可能的 API / JSON / JavaScript 資料來源
#
# 本程式只做測試
# 不修改 analysis.json
# 不修改 main.py
# 不接入正式分析流程
# ============================================================
URL = (
    "https://www.twse.com.tw/zh/about/news/event/"
    "content.html?8a8216d6a0bdcc0001a0c849c4ae001c"
)
def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
def main():
    print_section("TWSE 法人說明會資料測試 - 第三版")
    headers = {
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
    print_section("[1] Request")
    print("URL:")
    print(URL)
    try:
        response = requests.get(
            URL,
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as e:
        print("\n[ERROR] HTTP request failed")
        print(type(e).__name__)
        print(str(e))
        return
    print("\nHTTP Status:")
    print(response.status_code)
    print("\nContent-Type:")
    print(response.headers.get("Content-Type"))
    print("\nResponse Length:")
    print(len(response.text))
    if response.status_code != 200:
        print("\n[ERROR] HTTP status is not 200")
        print(response.text[:2000])
        return
    html = response.text
    # --------------------------------------------------------
    # 儲存原始 HTML
    # --------------------------------------------------------
    raw_file = "twse_conference_page.html"
    with open(raw_file, "w", encoding="utf-8") as f:
        f.write(html)
    print("\nRaw HTML saved:")
    print(raw_file)
    # --------------------------------------------------------
    # HTML Parser
    # --------------------------------------------------------
    print_section("[2] HTML Parser")
    soup = BeautifulSoup(html, "html.parser")
    print("Title:")
    print(soup.title.get_text(" ", strip=True) if soup.title else "None")
    # --------------------------------------------------------
    # 取得頁面文字
    # --------------------------------------------------------
    text = soup.get_text("\n", strip=True)
    text_file = "twse_conference_text.txt"
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(text)
    print("\nText saved:")
    print(text_file)
    # --------------------------------------------------------
    # 搜尋法人說明會關鍵字
    # --------------------------------------------------------
    print_section("[3] Keyword Check")
    keywords = [
        "法人說明會",
        "上市公司",
        "公司代號",
        "公司名稱",
        "日期",
        "時間",
        "地點",
        "說明會",
        "簡報",
        "網路轉播",
        "webpro.twse.com.tw",
    ]
    for keyword in keywords:
        count = text.count(keyword)
        print(
            f"{keyword}: {count} occurrence(s)"
        )
    # --------------------------------------------------------
    # 顯示包含「法人說明會」的文字附近內容
    # --------------------------------------------------------
    print_section("[4] Conference Keyword Context")
    matches = list(
        re.finditer(
            "法人說明會",
            text,
        )
    )
    print(f"Found: {len(matches)}")
    for index, match in enumerate(matches[:20], start=1):
        start = max(0, match.start() - 300)
        end = min(len(text), match.end() + 800)
        print(
            f"\n--- Match {index} ---"
        )
        print(text[start:end])
    # --------------------------------------------------------
    # 搜尋 JavaScript / JSON
    # --------------------------------------------------------
    print_section("[5] JavaScript / JSON Detection")
    scripts = soup.find_all("script")
    print(f"Script count: {len(scripts)}")
    possible_urls = []
    for index, script in enumerate(scripts, start=1):
        src = script.get("src")
        if src:
            print(
                f"\nScript {index} external:"
            )
            print(src)
            if (
                "api" in src.lower()
                or "event" in src.lower()
                or "conference" in src.lower()
                or "twse" in src.lower()
            ):
                possible_urls.append(src)
        else:
            script_text = script.get_text(
                "\n",
                strip=True,
            )
            if not script_text:
                continue
            lower_text = script_text.lower()
            keywords_found = []
            for keyword in [
                "api",
                "json",
                "ajax",
                "event",
                "conference",
                "法人說明會",
                "webpro",
            ]:
                if keyword.lower() in lower_text:
                    keywords_found.append(keyword)
            if keywords_found:
                print(
                    f"\nScript {index} "
                    f"contains: "
                    f"{keywords_found}"
                )
                print(
                    script_text[:3000]
                )
    # --------------------------------------------------------
    # 搜尋所有 HTML links
    # --------------------------------------------------------
    print_section("[6] Links Related To Conference")
    links = soup.find_all("a")
    related_links = []
    for link in links:
        href = link.get("href")
        label = link.get_text(
            " ",
            strip=True,
        )
        if not href:
            continue
        combined = (
            f"{label} {href}"
        ).lower()
        if any(
            keyword.lower()
            in combined
            for keyword in [
                "法人",
                "說明會",
                "conference",
                "webpro",
                "簡報",
                "轉播",
            ]
        ):
            related_links.append(
                {
                    "text": label,
                    "href": href,
                }
            )
    print(
        f"Related links: "
        f"{len(related_links)}"
    )
    for item in related_links:
        print("\nTEXT:")
        print(item["text"])
        print("HREF:")
        print(item["href"])
    # --------------------------------------------------------
    # 搜尋 HTML table
    # --------------------------------------------------------
    print_section("[7] HTML Tables")
    tables = soup.find_all("table")
    print(
        f"Table count: "
        f"{len(tables)}"
    )
    for table_index, table in enumerate(
        tables,
        start=1,
    ):
        print(
            f"\n--- Table {table_index} ---"
        )
        rows = table.find_all("tr")
        print(
            f"Rows: {len(rows)}"
        )
        for row in rows[:10]:
            cells = row.find_all(
                ["th", "td"]
            )
            values = [
                cell.get_text(
                    " ",
                    strip=True,
                )
                for cell in cells
            ]
            if values:
                print(values)
    # --------------------------------------------------------
    # 儲存測試結果
    # --------------------------------------------------------
    result = {
        "url": URL,
        "status_code": response.status_code,
        "content_type": response.headers.get(
            "Content-Type"
        ),
        "html_length": len(html),
        "text_length": len(text),
        "keyword_counts": {
            keyword: text.count(keyword)
            for keyword in keywords
        },
        "script_count": len(scripts),
        "table_count": len(tables),
        "related_links": related_links,
    }
    result_file = (
        "twse_conference_test_result.json"
    )
    with open(
        result_file,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2,
        )
    print_section("[8] Test Result")
    print(
        f"Result saved: "
        f"{result_file}"
    )
    print("\n測試完成。")
if __name__ == "__main__":
    main()
