import csv
import io
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

OUTPUT_FILE = BASE_DIR / "market_index.json"

REQUEST_TIMEOUT = 30

# TWSE 發行量加權股價指數歷史資料
TWSE_URL = (
    "https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST"
)

# ============================================================
# 2. 工具函式
# ============================================================


def clean_number(value):
    """
    將 TWSE 回傳的數字文字轉成 float。

    例如：
    "48,382.75" -> 48382.75
    "-"         -> None
    ""          -> None
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text or text in {"-", "--", "—"}:
        return None

    text = text.replace(",", "")

    try:
        return float(text)
    except ValueError:
        return None


def convert_roc_date(value):
    """
    將民國日期轉成西元日期。

    例如：
    115/10/15 -> 2026-10-15
    """

    text = str(value or "").strip()

    match = re.match(
        r"^(\d{2,3})/(\d{1,2})/(\d{1,2})$",
        text
    )

    if not match:
        return ""

    year = int(match.group(1)) + 1911
    month = int(match.group(2))
    day = int(match.group(3))

    try:
        return datetime(
            year,
            month,
            day
        ).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def parse_date(value):
    """
    將日期文字統一成 YYYY-MM-DD。
    """

    text = str(value or "").strip()

    if not text:
        return ""

    roc_date = convert_roc_date(text)

    if roc_date:
        return roc_date

    for fmt in (
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y.%m.%d",
    ):
        try:
            return datetime.strptime(
                text,
                fmt
            ).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return ""


# ============================================================
# 3. 取得 TWSE 資料
# ============================================================


def fetch_month(year, month):
    """
    取得指定年月的 TWSE 發行量加權股價指數歷史資料。

    TWSE API 使用：
        date=YYYYMMDD
        response=html
    """

    date_value = f"{year}{month:02d}01"

    params = {
        "date": date_value,
        "response": "html",
    }

    response = requests.get(
        TWSE_URL,
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; TaiwanStockDashboard/1.0)"
            )
        },
    )

    response.raise_for_status()

    return response.text


# ============================================================
# 4. 解析 TWSE HTML
# ============================================================


def parse_twse_html(html):
    """
    從 TWSE 歷史資料頁面解析：

    日期
    開盤指數
    最高指數
    最低指數
    收盤指數
    """

    # --------------------------------------------------------
    # 優先尋找 HTML table
    # --------------------------------------------------------

    from html.parser import HTMLParser

    class TableParser(HTMLParser):

        def __init__(self):
            super().__init__()

            self.in_table = False
            self.in_row = False
            self.in_cell = False

            self.current_row = []
            self.rows = []

            self.text_buffer = []

        def handle_starttag(self, tag, attrs):

            tag = tag.lower()

            if tag == "table":
                self.in_table = True

            elif self.in_table and tag == "tr":
                self.in_row = True
                self.current_row = []

            elif (
                self.in_table
                and self.in_row
                and tag in {"td", "th"}
            ):
                self.in_cell = True
                self.text_buffer = []

        def handle_data(self, data):

            if self.in_cell:
                self.text_buffer.append(data)

        def handle_endtag(self, tag):

            tag = tag.lower()

            if (
                self.in_table
                and self.in_row
                and tag in {"td", "th"}
            ):
                text = "".join(
                    self.text_buffer
                ).strip()

                self.current_row.append(text)

                self.in_cell = False
                self.text_buffer = []

            elif self.in_table and tag == "tr":

                if self.current_row:
                    self.rows.append(
                        self.current_row
                    )

                self.in_row = False
                self.current_row = []

            elif tag == "table":

                self.in_table = False

    parser = TableParser()

    parser.feed(html)

    rows = parser.rows

    # --------------------------------------------------------
    # 找到真正的指數資料表
    # --------------------------------------------------------

    result = []

    for row in rows:

        if len(row) < 5:
            continue

        row = [
            str(item).strip()
            for item in row
        ]

        # 第一欄必須像日期
        date = parse_date(row[0])

        if not date:
            continue

        # 後面四欄必須能轉成數字
        open_value = clean_number(row[1])
        high_value = clean_number(row[2])
        low_value = clean_number(row[3])
        close_value = clean_number(row[4])

        if close_value is None:
            continue

        result.append({
            "date": date,
            "open": open_value,
            "high": high_value,
            "low": low_value,
            "close": close_value,
        })

    return result


# ============================================================
# 5. 取得最近交易日資料
# ============================================================


def get_recent_history(months=2):
    """
    取得最近數個月份的歷史資料。

    預設抓最近兩個月，
    主要用來確保可以取得：

    1. 最新交易日
    2. 前一交易日

    以計算漲跌及漲跌幅。
    """

    today = datetime.now()

    months_to_fetch = []

    year = today.year
    month = today.month

    for offset in range(months):

        target_month = month - offset
        target_year = year

        while target_month <= 0:
            target_month += 12
            target_year -= 1

        months_to_fetch.append(
            (target_year, target_month)
        )

    all_rows = []

    for target_year, target_month in reversed(
        months_to_fetch
    ):

        print(
            f"[TWSE] 取得 "
            f"{target_year}-{target_month:02d} "
            f"指數資料..."
        )

        try:

            html = fetch_month(
                target_year,
                target_month
            )

            rows = parse_twse_html(html)

            print(
                f"[TWSE] 解析 {len(rows)} 筆"
            )

            all_rows.extend(rows)

        except Exception as error:

            print(
                f"[TWSE] "
                f"{target_year}-{target_month:02d} "
                f"取得失敗：{error}"
            )

    # --------------------------------------------------------
    # 去除重複日期
    # --------------------------------------------------------

    unique = {}

    for row in all_rows:
        unique[row["date"]] = row

    history = list(unique.values())

    history.sort(
        key=lambda item: item["date"]
    )

    return history


# ============================================================
# 6. 建立大盤資料
# ============================================================


def build_market_data(history):
    """
    使用最近交易日及前一交易日，
    建立 market_index.json 的 market 區塊。
    """

    if not history:
        raise RuntimeError(
            "TWSE 沒有取得任何大盤歷史資料。"
        )

    # --------------------------------------------------------
    # 只保留有收盤價的交易日
    # --------------------------------------------------------

    valid_history = [
        row
        for row in history
        if row.get("close") is not None
    ]

    if not valid_history:
        raise RuntimeError(
            "TWSE 資料中沒有有效的收盤指數。"
        )

    latest = valid_history[-1]

    previous = (
        valid_history[-2]
        if len(valid_history) >= 2
        else None
    )

    close = latest["close"]

    change = None
    change_percent = None

    if previous and previous.get("close") is not None:

        previous_close = previous["close"]

        change = close - previous_close

        if previous_close != 0:

            change_percent = (
                change /
                previous_close *
                100
            )

    return {
        "name": "加權指數",
        "code": "TAIEX",
        "date": latest["date"],
        "open": latest["open"],
        "high": latest["high"],
        "low": latest["low"],
        "close": latest["close"],
        "change": change,
        "change_percent": change_percent,
    }


# ============================================================
# 7. 建立輸出 JSON
# ============================================================


def build_output(history):
    """
    建立完整 market_index.json。
    """

    market = build_market_data(history)

    generated_at = (
        datetime.now().astimezone().isoformat()
    )

    return {
        "version": "1.0",
        "generated_at": generated_at,
        "market": market,
    }


# ============================================================
# 8. 寫入檔案
# ============================================================


def save_output(data):
    """
    寫入 market_index.json。
    """

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

        file.write("\n")


# ============================================================
# 9. 主程式
# ============================================================


def main():

    print("=" * 70)
    print("台股大盤收盤行情更新")
    print("=" * 70)

    print(
        f"輸出檔案：{OUTPUT_FILE}"
    )

    history = get_recent_history(
        months=2
    )

    if not history:
        raise RuntimeError(
            "無法取得 TWSE 大盤資料。"
        )

    data = build_output(
        history
    )

    save_output(
        data
    )

    market = data["market"]

    print()
    print("更新完成")
    print("-" * 70)

    print(
        f"日期：{market['date']}"
    )

    print(
        f"開盤：{market['open']}"
    )

    print(
        f"最高：{market['high']}"
    )

    print(
        f"最低：{market['low']}"
    )

    print(
        f"收盤：{market['close']}"
    )

    print(
        f"漲跌：{market['change']}"
    )

    print(
        f"漲跌幅：{market['change_percent']}%"
    )

    print("-" * 70)
    print(
        f"已寫入：{OUTPUT_FILE}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
