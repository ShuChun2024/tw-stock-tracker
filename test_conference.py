import json
import re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
PAGE_URL = (
    "https://www.twse.com.tw/zh/about/news/event/"
    "content.html?8a8216d6a0bdcc0001a0c849c4ae001c"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.twse.com.tw/",
}
KEYWORDS = [
    "data-api",
    "data-host",
    "apiHost",
    "cfg.apiHost",
    "rwd-table",
    "onload-argv",
    "法人說明會",
]
def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
def contexts(text, keyword, limit=8, radius=250):
    matches = list(
        re.finditer(re.escape(keyword), text, re.IGNORECASE)
    )
    print(f"\n關鍵字：{keyword}")
    print(f"出現次數：{len(matches)}")
    for match in matches[:limit]:
        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        print("-" * 50)
        print(text[start:end])
def main():
    result = {
        "page_url": PAGE_URL,
        "http_status": None,
        "forms": [],
        "api_candidates": [],
        "keyword_counts": {},
        "errors": [],
    }
    section("[1] 下載活動詳細頁")
    try:
        response = requests.get(
            PAGE_URL,
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        html = response.text
        result["http_status"] = response.status_code
        print("HTTP Status:", response.status_code)
        print("Content-Type:", response.headers.get("Content-Type"))
        print("HTML Length:", len(html))
        Path("twse_conference_page_v4.html").write_text(
            html,
            encoding="utf-8",
        )
    except Exception as exc:
        result["errors"].append(str(exc))
        print("[ERROR]", type(exc).__name__, str(exc))
        Path("twse_conference_v4_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return
    section("[2] 檢查 HTML 表單")
    soup = BeautifulSoup(html, "html.parser")
    forms = soup.find_all("form")
    print("表單數量:", len(forms))
    for index, form in enumerate(forms, start=1):
        info = {
            "index": index,
            "attributes": dict(form.attrs),
            "html": str(form)[:12000],
        }
        result["forms"].append(info)
        print(f"\n--- Form {index} ---")
        print("Attributes:")
        print(json.dumps(
            info["attributes"],
            ensure_ascii=False,
            indent=2,
        ))
        print("HTML:")
        print(info["html"])
    section("[3] 搜尋 API 設定與查詢線索")
    scripts = []
    for script in soup.find_all("script"):
        if script.get("src"):
            script_url = urljoin(PAGE_URL, script["src"])
            print("Script URL:", script_url)
            try:
                js_response = requests.get(
                    script_url,
                    headers=HEADERS,
                    timeout=30,
                )
                js_response.raise_for_status()
                scripts.append({
                    "url": script_url,
                    "text": js_response.text,
                })
            except Exception as exc:
                result["errors"].append(
                    f"{script_url}: {type(exc).__name__}: {exc}"
                )
        elif script.string:
            scripts.append({
                "url": "inline",
                "text": script.string,
            })
    for keyword in KEYWORDS:
        total = sum(
            len(re.findall(
                re.escape(keyword),
                item["text"],
                re.IGNORECASE,
            ))
            for item in scripts
        )
        result["keyword_counts"][keyword] = total
    for item in scripts:
        print("\n" + "#" * 70)
        print("來源:", item["url"])
        print("#" * 70)
        for keyword in KEYWORDS:
            if re.search(keyword, item["text"], re.IGNORECASE):
                contexts(item["text"], keyword)
    section("[4] 搜尋 HTML 本身的 API 設定")
    for keyword in [
        "data-api",
        "data-host",
        "apiHost",
        "rwd-table",
        "onload-argv",
    ]:
        contexts(html, keyword, limit=5, radius=300)
    section("[5] 表單 API 屬性整理")
    for form in forms:
        attrs = dict(form.attrs)
        if (
            "api" in attrs
            or "data-api" in attrs
            or "data-host" in attrs
            or attrs.get("id") == "form"
        ):
            print(json.dumps(
                attrs,
                ensure_ascii=False,
                indent=2,
            ))
            result["api_candidates"].append(attrs)
    section("[6] 儲存結果")
    Path("twse_conference_v4_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Saved: twse_conference_v4_result.json")
    print("Saved: twse_conference_page_v4.html")
    print("\n第五版檢查完成。")
if __name__ == "__main__":
    main()
