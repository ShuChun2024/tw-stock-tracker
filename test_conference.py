import io
import json
import re
import requests

from datetime import datetime, timedelta
from pypdf import PdfReader


# ============================================================
# 基本設定
# ============================================================

BASE_URL = "https://www.twse.com.tw"

EVENT_LIST_URL = (
    "https://www.twse.com.tw/news/eventList?response=html"
)

STOCKS = {
    "1101": "台泥",
    "2330": "台積電",
    "2454": "聯發科",
    "2317": "鴻海",
}

LOOKAHEAD_DAYS = 5

TIMEOUT = 30


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.twse.com.tw/",
}


# ============================================================
# HTTP
# ============================================================

def get_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def fetch(session, url):
    print()
    print("=" * 70)
    print("GET")
    print(url)
    print("=" * 70)

    response = session.get(
        url,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    print("HTTP:", response.status_code)
    print(
        "Content-Type:",
        response.headers.get("Content-Type"),
    )
    print(
        "Final URL:",
        response.url,
    )
    print(
        "Bytes:",
        len(response.content),
    )

    response.raise_for_status()

    return response


# ============================================================
# 民國日期
# ============================================================

def roc_to_date(year, month, day):
    try:
        return datetime(
            int(year) + 1911,
            int(month),
            int(day),
        ).date()
    except ValueError:
        return None


# ============================================================
# 從文字找日期
# ============================================================

def find_roc_dates(text):
    """
    找：
        115/10/13
        115-10-13
        115.10.13
        115年10月13日
    """

    results = []

    patterns = [
        r"(\d{3})[/-](\d{1,2})[/-](\d{1,2})",
        r"(\d{3})\.(\d{1,2})\.(\d{1,2})",
        r"(\d{3})年(\d{1,2})月(\d{1,2})日",
    ]

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            text,
        ):

            year, month, day = match.groups()

            date_value = roc_to_date(
                year,
                month,
                day,
            )

            if date_value:

                results.append(
                    {
                        "raw": match.group(0),
                        "date": date_value,
                    }
                )

    return results


# ============================================================
# 找法人說明會活動
# ============================================================

def find_conference_event(
    session,
):
    response = fetch(
        session,
        EVENT_LIST_URL,
    )

    html = response.text

    # --------------------------------------------------------
    # 找：
    # 2026年上市公司辦理法人說明會(10月1日至10月31日)
    # --------------------------------------------------------

    pattern = re.compile(
        r'href=["\']([^"\']+)["\'][^>]*>'
        r'[^<]*2026年上市公司辦理法人說明會'
        r'[^<]*10月1日至10月31日',
        re.IGNORECASE,
    )

    match = pattern.search(html)

    if not match:

        # 有些 HTML 會把 href 放在文字後面，
        # 再做一次反向搜尋。
        pattern2 = re.compile(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>'
            r'.{0,500}?'
            r'2026年上市公司辦理法人說明會'
            r'.{0,300}?'
            r'10月1日至10月31日',
            re.IGNORECASE |
            re.DOTALL,
        )

        match = pattern2.search(html)

    if not match:

        print()
        print("=" * 70)
        print("找不到 10 月法人說明會活動連結")
        print("=" * 70)

        # 把附近的關鍵字印出來
        keyword = "法人說明會"

        positions = [
            m.start()
            for m in re.finditer(
                keyword,
                html,
            )
        ]

        print(
            "頁面中法人說明會出現次數：",
            len(positions),
        )

        for position in positions[:10]:

            start = max(
                0,
                position - 300,
            )

            end = min(
                len(html),
                position + 500,
            )

            print()
            print(
                html[start:end]
            )

        raise RuntimeError(
            "找不到目前月份法人說明會活動連結"
        )

    href = match.group(1)

    if href.startswith("http"):

        event_url = href

    elif href.startswith("/"):

        event_url = BASE_URL + href

    else:

        event_url = BASE_URL + "/" + href

    print()
    print("=" * 70)
    print("找到法人說明會活動")
    print("=" * 70)

    print(event_url)

    return event_url


# ============================================================
# 從活動頁找 PDF
# ============================================================

def find_pdf_url(
    session,
    event_url,
):
    response = fetch(
        session,
        event_url,
    )

    html = response.text

    # --------------------------------------------------------
    # 找 PDF URL
    # --------------------------------------------------------

    pdf_pattern = re.compile(
        r'(?P<url>'
        r'(?:https?:)?//[^"\'>\s]+\.pdf'
        r'|'
        r'[^"\'>\s]+\.pdf'
        r')',
        re.IGNORECASE,
    )

    matches = pdf_pattern.findall(
        html
    )

    pdf_urls = []

    for href in matches:

        href = href.replace(
            "&amp;",
            "&",
        )

        if href.startswith("//"):

            href = "https:" + href

        elif href.startswith("/"):

            href = BASE_URL + href

        elif not href.startswith("http"):

            # 相對路徑
            href = (
                BASE_URL
                + "/"
                + href.lstrip("/")
            )

        if href not in pdf_urls:

            pdf_urls.append(
                href
            )

    print()
    print("=" * 70)
    print("找到 PDF")
    print("=" * 70)

    for url in pdf_urls:

        print(url)

    if not pdf_urls:

        raise RuntimeError(
            "活動頁中找不到 PDF 連結"
        )

    return pdf_urls


# ============================================================
# 下載 PDF
# ============================================================

def download_pdf(
    session,
    pdf_url,
):
    response = fetch(
        session,
        pdf_url,
    )

    content_type = (
        response.headers
        .get("Content-Type", "")
        .lower()
    )

    print()
    print(
        "PDF Content-Type:",
        content_type,
    )

    if (
        "pdf" not in content_type
        and not response.content.startswith(
            b"%PDF"
        )
    ):

        raise RuntimeError(
            "下載結果不是 PDF"
        )

    return response.content


# ============================================================
# 解析 PDF
# ============================================================

def parse_pdf(
    pdf_bytes,
):
    print()
    print("=" * 70)
    print("解析 PDF")
    print("=" * 70)

    reader = PdfReader(
        io.BytesIO(pdf_bytes)
    )

    print(
        "PDF 頁數：",
        len(reader.pages),
    )

    all_text = []

    for index, page in enumerate(
        reader.pages,
        start=1,
    ):

        text = page.extract_text() or ""

        print(
            f"第 {index} 頁文字長度：",
            len(text),
        )

        all_text.append(text)

    return "\n".join(
        all_text
    )


# ============================================================
# 從 PDF 找測試股票
# ============================================================

def extract_stock_lines(
    text,
):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    results = []

    for index, line in enumerate(
        lines
    ):

        for stock_id, company_name in STOCKS.items():

            if stock_id in line:

                start = max(
                    0,
                    index - 1,
                )

                end = min(
                    len(lines),
                    index + 3,
                )

                context = lines[
                    start:end
                ]

                results.append(
                    {
                        "stock_id": stock_id,
                        "company_name":
                            company_name,
                        "line": line,
                        "context": context,
                    }
                )

    return results


# ============================================================
# 從 PDF 判斷未來 5 天
# ============================================================

def find_upcoming(
    text,
):
    today = datetime.now().date()

    deadline = (
        today
        + timedelta(
            days=LOOKAHEAD_DAYS
        )
    )

    dates = find_roc_dates(
        text
    )

    upcoming_dates = []

    seen = set()

    for item in dates:

        d = item["date"]

        if (
            today
            <= d
            <= deadline
        ):

            if d not in seen:

                seen.add(d)

                upcoming_dates.append(
                    {
                        "raw": item["raw"],
                        "date":
                            d.isoformat(),
                    }
                )

    return upcoming_dates


# ============================================================
# 主程式
# ============================================================

def main():

    print("=" * 70)
    print("TWSE 法人說明會官方資料測試")
    print("=" * 70)

    now = datetime.now()

    print(
        "目前時間：",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    print(
        "查詢區間：",
        now.date(),
        "～",
        now.date()
        + timedelta(
            days=LOOKAHEAD_DAYS
        ),
    )

    session = get_session()

    # --------------------------------------------------------
    # 1. 活動列表
    # --------------------------------------------------------

    event_url = find_conference_event(
        session
    )

    # --------------------------------------------------------
    # 2. 活動頁
    # --------------------------------------------------------

    pdf_urls = find_pdf_url(
        session,
        event_url,
    )

    # --------------------------------------------------------
    # 3. 下載第一個 PDF
    # --------------------------------------------------------

    pdf_url = pdf_urls[0]

    pdf_bytes = download_pdf(
        session,
        pdf_url,
    )

    # --------------------------------------------------------
    # 4. PDF 解析
    # --------------------------------------------------------

    text = parse_pdf(
        pdf_bytes
    )

    # --------------------------------------------------------
    # 5. 找測試股票
    # --------------------------------------------------------

    stock_lines = extract_stock_lines(
        text
    )

    print()
    print("=" * 70)
    print("測試股票結果")
    print("=" * 70)

    if stock_lines:

        for item in stock_lines:

            print()
            print(
                item["stock_id"],
                item["company_name"],
            )

            print(
                " | ".join(
                    item["context"]
                )
            )

    else:

        print(
            "PDF 中沒有找到 1101 / 2330 / "
            "2454 / 2317"
        )

    # --------------------------------------------------------
    # 6. 未來 5 天
    # --------------------------------------------------------

    upcoming = find_upcoming(
        text
    )

    print()
    print("=" * 70)
    print("未來 5 天 PDF 中的日期")
    print("=" * 70)

    print(
        json.dumps(
            upcoming,
            ensure_ascii=False,
            indent=2,
        )
    )

    # --------------------------------------------------------
    # 7. 儲存測試結果
    # --------------------------------------------------------

    result = {
        "source": "TWSE",
        "event_url": event_url,
        "pdf_url": pdf_url,
        "checked_at":
            now.isoformat(
                timespec="seconds"
            ),
        "lookahead_days":
            LOOKAHEAD_DAYS,
        "stock_matches":
            stock_lines,
        "upcoming_dates":
            upcoming,
        "pdf_text":
            text,
    }

    with open(
        "conference_test_result.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 70)
    print("測試完成")
    print("=" * 70)

    print(
        "結果已保存："
        "conference_test_result.json"
    )


if __name__ == "__main__":
    main()
