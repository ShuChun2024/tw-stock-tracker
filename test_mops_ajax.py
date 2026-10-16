
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


# ============================================================
# MOPS AJAX 詳細資料測試 V3.1
# 測試股票：2330 台積電、1101 台泥
# 本版只解析 HTML，不下載 PDF 或影音
#
# V3.1 修改：
# 1. 保留 V3 原有基本欄位與 PDF 解析方式
# 2. 修正公司網站網址可能誤抓 PDF 的問題
# 3. 公司網站、影音網址優先從標籤所在的表格列尋找
# 4. 不下載任何檔案
# ============================================================

BASE_URL = "https://mopsov.twse.com.tw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mopsov.twse.com.tw/",
}

TEST_CASES = [
    {
        "stock_id": "2330",
        "stock_name": "台積電",
        "url": (
            "https://mopsov.twse.com.tw/mops/web/ajax_t100sb07_1"
            "?parameters="
            "0eb65210d5bdc34ea16e295ccdbad1099abb362c3fc938a027aff9085fb47dba87c33f7cb1f439f0aa513445e70aaaa6f71abe605c3d23d1030108b7cc585da0d6f2b2795dd11812a141746f54089f075d68a73f1504246f412daf016f5a2118"
        ),
    },
    {
        "stock_id": "1101",
        "stock_name": "台泥",
        "url": (
            "https://mopsov.twse.com.tw/mops/web/ajax_t100sb07_1"
            "?parameters="
            "0eb65210d5bdc34ea16e295ccdbad1096cc25092fb1cb844fc81ce64c36c6b8787c33f7cb1f439f0aa513445e70aaaa6f71abe605c3d23d1030108b7cc585da0d6f2b2795dd11812a141746f54089f075d68a73f1504246f412daf016f5a2118"
        ),
    },
]


# ============================================================
# 基本文字工具
# ============================================================

def get_lines(soup):
    """取得 HTML 文字行，移除空白行。"""
    return [
        line.strip()
        for line in soup.get_text("\n", strip=True).splitlines()
        if line.strip()
    ]


def get_value_after_label(lines, label):
    """取得指定欄位標籤後的第一行內容。"""
    for i, line in enumerate(lines):
        if line == label and i + 1 < len(lines):
            return lines[i + 1]
    return ""


def get_section(lines, start_label, end_label):
    """取得兩個欄位標籤之間的文字。"""
    try:
        start = lines.index(start_label) + 1
    except ValueError:
        return ""

    try:
        end = lines.index(end_label, start)
    except ValueError:
        end = len(lines)

    return " ".join(lines[start:end]).strip()


# ============================================================
# 日期與時間轉換
# ============================================================

def roc_to_ad(date_text):
    """民國日期轉西元日期，例如 115/10/15 -> 2026-10-15。"""
    if not date_text:
        return ""

    match = re.search(
        r"(\d{2,3})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})",
        date_text,
    )

    if not match:
        return date_text.strip()

    year = int(match.group(1)) + 1911
    month = int(match.group(2))
    day = int(match.group(3))

    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_time(text):
    """將 14 點 0 分轉成 14:00。"""
    if not text:
        return ""

    match = re.search(
        r"(\d{1,2})\s*點\s*(\d{1,2})\s*分",
        text,
    )

    if not match:
        return text.strip()

    hour = int(match.group(1))
    minute = int(match.group(2))

    return f"{hour:02d}:{minute:02d}"


def get_time(lines):
    """讀取時間欄位，兼容時間文字分成多行的 HTML。"""
    try:
        index = lines.index("時間：")
    except ValueError:
        return "", ""

    parts = []

    for line in lines[index + 1:index + 8]:
        if line in (
            "召開法人說明會地點：",
            "法人說明會擇要訊息：",
        ):
            break
        parts.append(line)

    raw = " ".join(parts).strip()
    return raw, parse_time(raw)


# ============================================================
# 連結解析
# ============================================================

def find_pdf_links(soup):
    """列出 PDF 連結及完整 URL，不執行下載。"""
    results = []

    for link in soup.find_all("a"):
        href = (link.get("href") or "").strip()
        name = link.get_text(" ", strip=True)

        if ".pdf" not in href.lower():
            continue

        results.append({
            "name": name or href.rsplit("/", 1)[-1],
            "href": href,
            "url": urljoin(BASE_URL, href),
        })

    return results


def find_urls(soup):
    """取得 HTML 中的 HTTP/HTTPS 連結，保留原始連結文字。"""
    results = []

    for link in soup.find_all("a"):
        href = (link.get("href") or "").strip()

        if href.startswith(("http://", "https://")):
            results.append({
                "text": link.get_text(" ", strip=True),
                "url": href,
            })

    return results


def is_pdf_url(url):
    """判斷網址是否為 PDF，包含帶有查詢參數的網址。"""
    if not url:
        return False

    path = urlparse(url).path.lower()
    return path.endswith(".pdf")


def normalize_http_url(href):
    """將 HTTP、HTTPS 或站內相對網址轉成完整網址。"""
    href = (href or "").strip()

    if not href:
        return ""

    full_url = urljoin(BASE_URL, href)

    if urlparse(full_url).scheme.lower() not in ("http", "https"):
        return ""

    return full_url


def find_labeled_link(soup, label, exclude_pdf=True):
    """
    根據指定欄位標籤尋找連結。

    優先順序：
    1. 標籤所在的最近一個表格列
    2. 如果沒有表格列，才在有限的局部 HTML 區塊尋找

    排除 PDF，避免公司網站或影音欄位誤抓簡報網址。
    不會下載檔案。
    """

    for node in soup.find_all(
        string=re.compile(re.escape(label))
    ):
        # ----------------------------------------------------
        # 第一優先：只搜尋標籤所在的最近一個表格列
        # ----------------------------------------------------

        row = node.find_parent("tr")

        if row is not None:
            for link in row.find_all("a", href=True):
                url = normalize_http_url(link.get("href"))

                if not url:
                    continue

                if exclude_pdf and is_pdf_url(url):
                    continue

                return url

            # 已找到表格列但列內沒有合適連結。
            # 不向上搜尋整張表格，避免誤抓其他欄位。
            continue

        # ----------------------------------------------------
        # 第二優先：非表格 HTML 的局部搜尋
        # 最多向上兩層，避免掃描過大的父元素
        # ----------------------------------------------------

        parent = node.parent

        for _ in range(2):
            if parent is None:
                break

            for link in parent.find_all("a", href=True):
                url = normalize_http_url(link.get("href"))

                if not url:
                    continue

                if exclude_pdf and is_pdf_url(url):
                    continue

                return url

            parent = parent.parent

    return ""


# ============================================================
# 解析單筆 MOPS 詳細資料
# ============================================================

def parse_mops_ajax(html):
    soup = BeautifulSoup(html, "html.parser")
    lines = get_lines(soup)

    result = {
        "company_id": get_value_after_label(
            lines, "公司代號："
        ),
        "company_name": get_value_after_label(
            lines, "公司名稱："
        ),
        "date_roc": get_value_after_label(
            lines, "召開法人說明會日期："
        ),
        "date": "",
        "time_raw": "",
        "time": "",
        "location": get_value_after_label(
            lines, "召開法人說明會地點："
        ),
        "summary": get_section(
            lines,
            "法人說明會擇要訊息：",
            "法人說明會簡報內容",
        ),
        "chinese_pdf": "",
        "english_pdf": "",
        "company_website": "",
        "video_url": "",
        "other": get_value_after_label(
            lines, "其他應敘明事項："
        ),
        "pdf_links": [],
        "external_urls": [],
    }

    # 保留 V3 日期與時間解析方式
    result["date"] = roc_to_ad(result["date_roc"])

    result["time_raw"], result["time"] = get_time(lines)

    # --------------------------------------------------------
    # PDF：依檔名中的語言標記分類，不下載
    # --------------------------------------------------------

    pdf_links = find_pdf_links(soup)
    result["pdf_links"] = pdf_links

    for pdf in pdf_links:
        filename = pdf["name"].lower()
        href = pdf["href"].lower()

        if re.search(r"\d{4}\d{8}m\d+\.pdf$", filename):
            result["chinese_pdf"] = pdf["url"]

        elif re.search(r"\d{4}\d{8}e\d+\.pdf$", filename):
            result["english_pdf"] = pdf["url"]

        elif re.search(r"m\d+\.pdf$", filename):
            result["chinese_pdf"] = pdf["url"]

        elif re.search(r"e\d+\.pdf$", filename):
            result["english_pdf"] = pdf["url"]

        elif not result["chinese_pdf"] and "m" in href:
            result["chinese_pdf"] = pdf["url"]

        elif not result["english_pdf"] and "e" in href:
            result["english_pdf"] = pdf["url"]

    # --------------------------------------------------------
    # 外部連結：保留 V3 原有方式
    # --------------------------------------------------------

    result["external_urls"] = find_urls(soup)

    # --------------------------------------------------------
    # 公司網站：限定欄位附近，排除 PDF
    # --------------------------------------------------------

    result["company_website"] = find_labeled_link(
        soup,
        "公司網站是否有提供法人說明會相關資訊",
        exclude_pdf=True,
    )

    # --------------------------------------------------------
    # 影音連結：限定欄位附近，排除 PDF
    # --------------------------------------------------------

    result["video_url"] = find_labeled_link(
        soup,
        "影音連結資訊",
        exclude_pdf=True,
    )

    return result


# ============================================================
# 顯示結果
# ============================================================

def print_result(stock, data):
    print()
    print("=" * 72)
    print(
        f"{stock['stock_id']} "
        f"{stock['stock_name']}：結構化解析結果"
    )
    print("=" * 72)

    print(f"公司代號       : {data['company_id']}")
    print(f"公司名稱       : {data['company_name']}")
    print(f"民國日期       : {data['date_roc']}")
    print(f"西元日期       : {data['date']}")
    print(f"原始時間       : {data['time_raw']}")
    print(f"標準時間       : {data['time']}")
    print(f"地點           : {data['location']}")

    print("\n法人說明會摘要")
    print("-" * 72)
    print(data["summary"] or "(未解析到摘要)")

    print("\nPDF 連結（僅列出，未下載）")

    for pdf in data["pdf_links"]:
        print(f"  檔名：{pdf['name']}")
        print(f"  URL ：{pdf['url']}")

    print(f"\n中文 PDF       : {data['chinese_pdf']}")
    print(f"英文 PDF       : {data['english_pdf']}")
    print(f"公司網站       : {data['company_website']}")
    print(f"影音連結       : {data['video_url']}")
    print(f"其他事項       : {data['other']}")

    print("\nHTML 外部連結")

    for item in data["external_urls"]:
        print(f"  {item['text'] or '(無連結文字)'}")
        print(f"    {item['url']}")


# ============================================================
# 驗證
# ============================================================

def validate(stock, data, http_ok):
    checks = {
        "HTTP 200": http_ok,
        "公司代號符合預期": (
            data["company_id"] == stock["stock_id"]
        ),
        "公司名稱非空": bool(data["company_name"]),
        "日期可轉換": bool(
            re.fullmatch(
                r"\d{4}-\d{2}-\d{2}",
                data["date"],
            )
        ),
        "時間可解析": bool(
            re.fullmatch(
                r"\d{2}:\d{2}",
                data["time"],
            )
        ),
        "地點非空": bool(data["location"]),
        "摘要非空": bool(data["summary"]),
        "至少找到一個 PDF": bool(data["pdf_links"]),
    }

    print("\n基本驗證")

    for name, passed in checks.items():
        print(f"  {'PASS' if passed else 'FAIL'} : {name}")

    # 額外檢查網址類型
    for field, label in (
        ("chinese_pdf", "中文 PDF 欄位"),
        ("english_pdf", "英文 PDF 欄位"),
    ):
        url = data[field]
        passed = bool(url) and is_pdf_url(url)
        print(f"  {'PASS' if passed else 'WARN'} : {label}")

    website = data["company_website"]
    website_ok = bool(website) and not is_pdf_url(website)

    print(
        f"  {'PASS' if website_ok else 'WARN'}"
        " : 公司網站不是 PDF 網址"
    )

    video = data["video_url"]
    video_ok = bool(video) and not is_pdf_url(video)

    print(
        f"  {'PASS' if video_ok else 'WARN'}"
        " : 影音網址不是 PDF 網址"
    )

    # 公司網站及影音網址缺漏屬於警告，
    # 不改變 V3 原本核心欄位的驗證規則。
    return all(checks.values())


# ============================================================
# 主程式
# ============================================================

def main():
    print("=" * 72)
    print("MOPS AJAX 詳細資料測試 V3.1")
    print("測試股票：2330 台積電、1101 台泥")
    print("模式：只解析 HTML，不下載 PDF 或影音")
    print("=" * 72)

    session = requests.Session()
    session.headers.update(HEADERS)

    all_passed = True

    for stock in TEST_CASES:
        print()
        print("#" * 72)
        print(
            f"開始測試：{stock['stock_id']} "
            f"{stock['stock_name']}"
        )
        print("#" * 72)

        try:
            response = session.get(
                stock["url"],
                timeout=30,
            )

        except requests.RequestException as exc:
            print(
                f"Request 失敗："
                f"{type(exc).__name__}: {exc}"
            )
            all_passed = False
            continue

        print("HTTP Status:", response.status_code)
        print(
            "Content-Type:",
            response.headers.get("Content-Type"),
        )

        if response.status_code != 200:
            print("HTTP 失敗，略過解析。")
            print(response.text[:1000])
            all_passed = False
            continue

        response.encoding = (
            response.apparent_encoding or "utf-8"
        )

        data = parse_mops_ajax(response.text)

        print_result(stock, data)

        passed = validate(stock, data, True)

        if (
            data["company_name"]
            and stock["stock_name"] not in data["company_name"]
        ):
            print(
                f"  FAIL : 公司名稱與測試設定不符，"
                f"預期包含「{stock['stock_name']}」"
            )
            passed = False

        if not passed:
            all_passed = False

    print()
    print("=" * 72)

    if all_passed:
        print("V3.1 測試：兩家公司核心欄位皆通過")
    else:
        print("V3.1 測試：有項目失敗，請依各股票輸出檢查")

    print("PDF 下載：未執行")
    print("影音下載：未執行")
    print("V3.1 測試完成")
    print("=" * 72)


if __name__ == "__main__":
    main()
