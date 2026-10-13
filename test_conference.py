import io
import json
import re
import requests

from datetime import datetime, timedelta
from html import unescape
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

RESULT_FILE = "conference_test_result.json"


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
# HTTP Session
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
# 清理 HTML 文字
# ============================================================

def clean_html_text(text):
    if not text:
        return ""

    text = unescape(text)

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# 找目前月份法人說明會活動
#
# 注意：
# TWSE 目前頁面實際結構是：
#
# <td>2026年上市公司辦理法人說明會(...)</td>
# <td>https://www.twse.com.tw/...</td>
#
# URL 不是 href。
# ============================================================

def find_conference_event(session):

    response = fetch(
        session,
        EVENT_LIST_URL,
    )

    html = response.text

    # --------------------------------------------------------
    # 目前日期
    # --------------------------------------------------------

    now = datetime.now()

    year = now.year
    month = now.month

    target_title = (
        f"{year}年上市公司辦理法人說明會"
    )

    target_month = (
        f"{month}月1日至{month}月"
    )

    # --------------------------------------------------------
    # 先找所有包含「上市公司辦理法人說明會」的區塊
    # --------------------------------------------------------

    pattern = re.compile(
        r"<tr[^>]*>"
        r"(.*?)"
        r"</tr>",
        re.IGNORECASE | re.DOTALL,
    )

    rows = pattern.findall(html)

    print()
    print("=" * 70)
    print("找到法人說明會相關列")
    print("=" * 70)

    candidates = []

    for row in rows:

        row_text = clean_html_text(row)

        if "上市公司辦理法人說明會" not in row_text:
            continue

        # ----------------------------------------------------
        # 找日期月份
        # ----------------------------------------------------

        title_match = re.search(
            rf"{re.escape(target_title)}"
            rf"\({month}月1日至{month}月\d+日\)",
            row_text,
        )

        if not title_match:
            continue

        title = title_match.group(0)

        # ----------------------------------------------------
        # 找 TWSE content URL
        # ----------------------------------------------------

        url_match = re.search(
            r"https://www\.twse\.com\.tw/"
            r"(?:zh/)?about/news/event/content\.html"
            r"\?[^<\s]+",
            row_text,
        )

        if not url_match:
            continue

        event_url = url_match.group(0)

        # 清除可能的 HTML entity
        event_url = unescape(
            event_url
        )

        candidate = {
            "title": title,
            "url": event_url,
            "raw_row": row_text,
        }

        candidates.append(candidate)

        print()
        print("標題：", title)
        print("URL：", event_url)

    if not candidates:

        print()
        print("=" * 70)
        print("找不到目前月份法人說明會")
        print("=" * 70)

        raise RuntimeError(
            "找不到目前月份法人說明會活動"
        )

    # --------------------------------------------------------
    # 理論上應該只有一筆
    # --------------------------------------------------------

    selected = candidates[0]

    print()
    print("=" * 70)
    print("選定法人說明會活動")
    print("=" * 70)

    print(
        "標題：",
        selected["title"],
    )

    print(
        "URL：",
        selected["url"],
    )

    return selected


# ============================================================
# 找活動頁中的 PDF
# ============================================================

def find_pdf_urls(
    session,
    event_url,
):

    response = fetch(
        session,
        event_url,
    )

    html = response.text

    # --------------------------------------------------------
    # 搜尋 PDF
    # --------------------------------------------------------

    patterns = [
        r'https?://[^"\'>\s]+\.pdf(?:\?[^"\'>\s]*)?',
        r'["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',
    ]

    pdf_urls = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            re.IGNORECASE,
        )

        for match in matches:

            if isinstance(match, tuple):
                href = match[0]
            else:
                href = match

            href = unescape(
                href
            )

            href = href.strip()

            if href.startswith("//"):
                href = "https:" + href

            elif href.startswith("/"):
                href = BASE_URL + href

            elif not href.startswith("http"):
                href = (
                    BASE_URL
                    + "/"
                    + href.lstrip("/")
                )

            if href not in pdf_urls:
                pdf_urls.append(href)

    print()
    print("=" * 70)
    print("法人說明會頁面 PDF")
    print("=" * 70)

    if pdf_urls:

        for url in pdf_urls:
            print(url)

    else:

        print("沒有找到 PDF")

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
        "Content-Type:",
        content_type,
    )

    # --------------------------------------------------------
    # PDF 判斷
    # --------------------------------------------------------

    if (
        "pdf" not in content_type
        and not response.content.startswith(
            b"%PDF"
        )
    ):
        raise RuntimeError(
            "下載內容不是 PDF"
        )

    return response.content


# ============================================================
# 解析 PDF
# ============================================================

def extract_pdf_text(
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

    pages = []

    for index, page in enumerate(
        reader.pages,
        start=1,
    ):

        try:
            text = page.extract_text() or ""
        except Exception as exc:
            print(
                f"第 {index} 頁解析失敗：",
                exc,
            )
            text = ""

        print(
            f"第 {index} 頁文字長度：",
            len(text),
        )

        pages.append(text)

    return "\n".join(pages)


# ============================================================
# 民國日期轉西元
# ============================================================

def roc_date_to_iso(
    year,
    month,
    day,
):

    try:

        date_value = datetime(
            int(year) + 1911,
            int(month),
            int(day),
        ).date()

        return date_value

    except ValueError:

        return None


# ============================================================
# 找 PDF 裡的民國日期
# ============================================================

def find_roc_dates(
    text,
):

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

            year, month, day = (
                match.groups()
            )

            date_value = roc_date_to_iso(
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
# 找測試股票
# ============================================================

def find_stock_matches(
    text,
):

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    matches = []

    for index, line in enumerate(
        lines
    ):

        for stock_id, company_name in STOCKS.items():

            # 避免把其他數字中的 4 碼誤判成股票代號
            if re.search(
                rf"(?<!\d){re.escape(stock_id)}(?!\d)",
                line,
            ):

                start = max(
                    0,
                    index - 2,
                )

                end = min(
                    len(lines),
                    index + 3,
                )

                context = lines[
                    start:end
                ]

                matches.append(
                    {
                        "stock_id": stock_id,
                        "company_name":
                            company_name,
                        "matched_line":
                            line,
                        "context":
                            context,
                    }
                )

    return matches


# ============================================================
# 找未來 5 天法說會日期
# ============================================================

def find_upcoming_dates(
    text,
):

    today = datetime.now().date()

    deadline = (
        today
        + timedelta(
            days=LOOKAHEAD_DAYS
        )
    )

    all_dates = find_roc_dates(
        text
    )

    upcoming = []

    seen = set()

    for item in all_dates:

        d = item["date"]

        if (
            today
            <= d
            <= deadline
        ):

            key = d.isoformat()

            if key in seen:
                continue

            seen.add(key)

            upcoming.append(
                {
                    "raw": item["raw"],
                    "date": key,
                }
            )

    upcoming.sort(
        key=lambda x: x["date"]
    )

    return upcoming


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
        (
            now.date()
            + timedelta(
                days=LOOKAHEAD_DAYS
            )
        ),
    )

    session = get_session()

    # ========================================================
    # 1. 找目前月份法人說明會
    # ========================================================

    event = find_conference_event(
        session
    )

    event_url = event["url"]

    # ========================================================
    # 2. 進入法人說明會活動頁
    # ========================================================

    pdf_urls = find_pdf_urls(
        session,
        event_url,
    )

    if not pdf_urls:

        raise RuntimeError(
            "法人說明會活動頁沒有找到 PDF"
        )

    # ========================================================
    # 3. 測試所有 PDF
    # ========================================================

    all_pdf_results = []

    for pdf_index, pdf_url in enumerate(
        pdf_urls,
        start=1,
    ):

        print()
        print("=" * 70)
        print(
            f"測試 PDF {pdf_index}/{len(pdf_urls)}"
        )
        print("=" * 70)

        try:

            pdf_bytes = download_pdf(
                session,
                pdf_url,
            )

            text = extract_pdf_text(
                pdf_bytes
            )

            stock_matches = (
                find_stock_matches(
                    text
                )
            )

            upcoming_dates = (
                find_upcoming_dates(
                    text
                )
            )

            result = {
                "pdf_url": pdf_url,
                "pdf_size": len(pdf_bytes),
                "stock_matches":
                    stock_matches,
                "upcoming_dates":
                    upcoming_dates,
                "text_length":
                    len(text),
            }

            all_pdf_results.append(
                result
            )

            print()
            print(
                "PDF 大小：",
                len(pdf_bytes),
                "bytes",
            )

            print(
                "文字長度：",
                len(text),
            )

            print()
            print(
                "測試股票："
            )

            if stock_matches:

                for item in stock_matches:

                    print(
                        item["stock_id"],
                        item["company_name"],
                        ":",
                        item["matched_line"],
                    )

            else:

                print(
                    "1101 / 2330 / 2454 / 2317 "
                    "皆未找到"
                )

            print()
            print(
                "未來 5 天日期："
            )

            if upcoming_dates:

                print(
                    json.dumps(
                        upcoming_dates,
                        ensure_ascii=False,
                        indent=2,
                    )
                )

            else:

                print(
                    "沒有找到未來 5 天日期"
                )

        except Exception as exc:

            print()
            print(
                "此 PDF 測試失敗：",
                exc,
            )

            all_pdf_results.append(
                {
                    "pdf_url": pdf_url,
                    "error": str(exc),
                }
            )

    # ========================================================
    # 4. 儲存結果
    # ========================================================

    final_result = {
        "source": "TWSE",
        "event_title": event["title"],
        "event_url": event_url,
        "checked_at":
            now.isoformat(
                timespec="seconds"
            ),
        "lookahead_days":
            LOOKAHEAD_DAYS,
        "pdf_count":
            len(pdf_urls),
        "pdf_results":
            all_pdf_results,
    }

    with open(
        RESULT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            final_result,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # ========================================================
    # 5. 完成
    # ========================================================

    print()
    print("=" * 70)
    print("測試完成")
    print("=" * 70)

    print(
        "測試結果：",
        RESULT_FILE,
    )


if __name__ == "__main__":
    main()
