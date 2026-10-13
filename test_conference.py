import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path


# ============================================================
# 基本設定
# ============================================================

BASE_URL = "https://www.twse.com.tw"
EVENT_LIST_URL = (
    "https://www.twse.com.tw/news/eventList?response=html"
)

# 目前要測試的股票
STOCKS = {
    "1101": "台泥",
    "2330": "台積電",
    "2454": "聯發科",
    "2317": "鴻海",
}

LOOKAHEAD_DAYS = 5

TIMEOUT = 20

OUTPUT_FILE = Path("conference_test_result.json")
RAW_HTML_FILE = Path("conference_raw.html")


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
    "Referer": BASE_URL + "/",
}


# ============================================================
# HTTP
# ============================================================

def get_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def fetch_page(session, url):
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
    print("Content-Type:", response.headers.get("Content-Type"))
    print("Final URL:", response.url)
    print("Bytes:", len(response.content))

    response.raise_for_status()

    return response


# ============================================================
# 日期
# ============================================================

def roc_to_date(value):
    """
    將：
        115/10/13
        115-10-13
        1151013
    轉成 date
    """

    if value is None:
        return None

    text = str(value).strip()

    # 115/10/13
    m = re.fullmatch(r"(\d{3})[/-](\d{1,2})[/-](\d{1,2})", text)

    if m:
        y, month, day = map(int, m.groups())

        try:
            return datetime(
                y + 1911,
                month,
                day,
            ).date()
        except ValueError:
            return None

    # 1151013
    m = re.fullmatch(r"(\d{3})(\d{2})(\d{2})", text)

    if m:
        y, month, day = map(int, m.groups())

        try:
            return datetime(
                y + 1911,
                month,
                day,
            ).date()
        except ValueError:
            return None

    return None


def date_to_roc(value):
    if value is None:
        return ""

    return (
        f"{value.year - 1911:03d}/"
        f"{value.month:02d}/"
        f"{value.day:02d}"
    )


# ============================================================
# 找目前月份的法人說明會活動頁
# ============================================================

def find_current_month_conference_page(session):
    response = fetch_page(
        session,
        EVENT_LIST_URL,
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    current = datetime.now()

    year = current.year
    month = current.month

    target_patterns = [
        f"{year}年上市公司辦理法人說明會",
        f"{year}年上市公司辦理法人說明會",
    ]

    candidates = []

    for a in soup.find_all("a"):
        text = a.get_text(" ", strip=True)

        href = a.get("href")

        if not href:
            continue

        if any(pattern in text for pattern in target_patterns):

            if (
                str(year) in text
                and f"{month}月" in text
            ):
                candidates.append(
                    {
                        "title": text,
                        "href": href,
                    }
                )

    print()
    print("找到目前月份法人說明會活動頁：")
    print(json.dumps(
        candidates,
        ensure_ascii=False,
        indent=2,
    ))

    if not candidates:
        raise RuntimeError(
            "找不到目前月份的法人說明會活動頁。"
        )

    href = candidates[0]["href"]

    if href.startswith("/"):
        url = BASE_URL + href
    elif href.startswith("http"):
        url = href
    else:
        url = BASE_URL + "/" + href.lstrip("/")

    return url, candidates[0]["title"]


# ============================================================
# 清理 HTML 文字
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = value.replace("\xa0", " ")

    value = re.sub(
        r"[ \t]+",
        " ",
        value,
    )

    value = re.sub(
        r"\n+",
        "\n",
        value,
    )

    return value.strip()


# ============================================================
# 從頁面中找股票代號
# ============================================================

def find_stock_ids(text):
    result = []

    for stock_id in STOCKS:
        if stock_id in text:
            result.append(stock_id)

    return result


# ============================================================
# 嘗試解析一段日期
# ============================================================

def find_dates(text):
    """
    找：
        115/10/13
        115-10-13
        115.10.13
    """

    patterns = [
        r"\b\d{3}/\d{1,2}/\d{1,2}\b",
        r"\b\d{3}-\d{1,2}-\d{1,2}\b",
        r"\b\d{3}\.\d{1,2}\.\d{1,2}\b",
    ]

    results = []

    for pattern in patterns:
        for match in re.findall(pattern, text):
            value = match.replace(".", "/").replace("-", "/")

            date_value = roc_to_date(value)

            if date_value:
                results.append(
                    {
                        "raw": match,
                        "date": date_value,
                    }
                )

    return results


# ============================================================
# 嘗試解析時間
# ============================================================

def find_times(text):
    patterns = [
        r"\b\d{1,2}:\d{2}\b",
        r"\b\d{1,2}:\d{2}:\d{2}\b",
    ]

    result = []

    for pattern in patterns:
        for value in re.findall(pattern, text):
            if value not in result:
                result.append(value)

    return result


# ============================================================
# 分析活動頁
# ============================================================

def analyze_conference_page(
    session,
    url,
):
    response = fetch_page(
        session,
        url,
    )

    html = response.text

    # 保存原始 HTML
    RAW_HTML_FILE.write_text(
        html,
        encoding="utf-8",
    )

    print()
    print("已保存原始 HTML：")
    print(RAW_HTML_FILE.resolve())

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    # --------------------------------------------------------
    # 取得完整文字
    # --------------------------------------------------------

    text = soup.get_text(
        "\n",
        strip=True,
    )

    text = clean_text(text)

    # --------------------------------------------------------
    # 顯示測試股票是否出現在頁面
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("測試股票")
    print("=" * 70)

    stock_hits = []

    for stock_id, company_name in STOCKS.items():

        if stock_id in text:

            print(
                f"找到：{stock_id} {company_name}"
            )

            stock_hits.append(
                {
                    "stock_id": stock_id,
                    "company_name": company_name,
                }
            )

        else:

            print(
                f"未找到：{stock_id} {company_name}"
            )

    # --------------------------------------------------------
    # 找所有表格
    # --------------------------------------------------------

    tables = []

    for table_index, table in enumerate(
        soup.find_all("table")
    ):

        rows = []

        for tr in table.find_all("tr"):

            cells = tr.find_all(
                ["th", "td"]
            )

            values = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell in cells
            ]

            if values:
                rows.append(values)

        if rows:
            tables.append(
                {
                    "table_index": table_index,
                    "rows": rows,
                }
            )

    print()
    print("=" * 70)
    print("HTML 表格數量")
    print("=" * 70)

    print(len(tables))

    # --------------------------------------------------------
    # 顯示與測試股票相關的表格內容
    # --------------------------------------------------------

    relevant_rows = []

    for table in tables:

        for row in table["rows"]:

            row_text = " | ".join(row)

            if find_stock_ids(row_text):

                relevant_rows.append(
                    {
                        "table_index":
                            table["table_index"],
                        "row": row,
                    }
                )

    print()
    print("=" * 70)
    print("與測試股票相關的原始表格資料")
    print("=" * 70)

    for item in relevant_rows:

        print(
            f"\n[Table {item['table_index']}]"
        )

        print(
            " | ".join(item["row"])
        )

    # --------------------------------------------------------
    # 全頁日期
    # --------------------------------------------------------

    dates = find_dates(text)

    unique_dates = []

    seen = set()

    for item in dates:

        key = item["date"]

        if key not in seen:

            seen.add(key)

            unique_dates.append(
                item
            )

    unique_dates.sort(
        key=lambda x: x["date"]
    )

    # --------------------------------------------------------
    # 全頁時間
    # --------------------------------------------------------

    times = find_times(text)

    # --------------------------------------------------------
    # 結果
    # --------------------------------------------------------

    result = {
        "source": "TWSE",
        "source_url": url,
        "checked_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "stock_hits": stock_hits,
        "relevant_rows": relevant_rows,
        "all_dates": [
            {
                "raw": item["raw"],
                "date": item["date"].isoformat(),
            }
            for item in unique_dates
        ],
        "all_times": times,
    }

    return result


# ============================================================
# 嘗試從相關列建立「未來法說會」
# ============================================================

def extract_upcoming_from_rows(
    relevant_rows,
    lookahead_days=5,
):
    today = datetime.now().date()

    deadline = today + timedelta(
        days=lookahead_days
    )

    upcoming = []

    for item in relevant_rows:

        row = item["row"]

        row_text = " | ".join(row)

        stock_ids = find_stock_ids(
            row_text
        )

        if not stock_ids:
            continue

        dates = find_dates(
            row_text
        )

        if not dates:
            continue

        times = find_times(
            row_text
        )

        # 找落在未來區間的日期
        candidate_dates = []

        for date_info in dates:

            d = date_info["date"]

            if today <= d <= deadline:

                candidate_dates.append(
                    date_info
                )

        if not candidate_dates:
            continue

        for stock_id in stock_ids:

            company_name = STOCKS[
                stock_id
            ]

            for date_info in candidate_dates:

                upcoming.append(
                    {
                        "stock_id": stock_id,
                        "company_name": company_name,
                        "conference_date":
                            date_info["date"].isoformat(),
                        "conference_date_roc":
                            date_to_roc(
                                date_info["date"]
                            ),
                        "times": times,
                        "raw_row": row,
                    }
                )

    return upcoming


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("=" * 70)
    print("TWSE 法人說明會資料測試")
    print("=" * 70)

    print(
        "今天：",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    print(
        "查詢區間：",
        datetime.now().date(),
        "～",
        datetime.now().date()
        + timedelta(days=LOOKAHEAD_DAYS),
    )

    session = get_session()

    # --------------------------------------------------------
    # 1. 找當月份官方法人說明會頁面
    # --------------------------------------------------------

    conference_url, conference_title = (
        find_current_month_conference_page(
            session
        )
    )

    print()
    print("=" * 70)
    print("目前月份活動")
    print("=" * 70)

    print(conference_title)
    print(conference_url)

    # --------------------------------------------------------
    # 2. 分析官方活動頁
    # --------------------------------------------------------

    result = analyze_conference_page(
        session,
        conference_url,
    )

    # --------------------------------------------------------
    # 3. 嘗試找未來 5 天
    # --------------------------------------------------------

    upcoming = extract_upcoming_from_rows(
        result["relevant_rows"],
        LOOKAHEAD_DAYS,
    )

    result["upcoming"] = upcoming

    # --------------------------------------------------------
    # 4. 儲存 JSON
    # --------------------------------------------------------

    OUTPUT_FILE.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # 5. 最終輸出
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("未來 5 天法說會")
    print("=" * 70)

    if upcoming:

        print(
            json.dumps(
                upcoming,
                ensure_ascii=False,
                indent=2,
            )
        )

    else:

        print(
            "目前尚未從官方活動頁解析到"
            "測試股票未來 5 天的法說會。"
        )

    print()
    print("=" * 70)
    print("測試完成")
    print("=" * 70)

    print(
        "結果：",
        OUTPUT_FILE.resolve(),
    )

    print(
        "原始 HTML：",
        RAW_HTML_FILE.resolve(),
    )


if __name__ == "__main__":
    main()
