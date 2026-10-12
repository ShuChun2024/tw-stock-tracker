import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

ANALYSIS_FILE = BASE_DIR / "analysis.json"
OUTPUT_FILE = BASE_DIR / "events.json"

# ------------------------------------------------------------
# 第一次測試先只抓這 4 檔
# 確認成功後再改成全部股票
# ------------------------------------------------------------
TEST_STOCKS = [
    "1101",
    "2330",
    "2454",
    "2317",
]

# True = 只測試 TEST_STOCKS
# False = 從 analysis.json 讀取全部股票
TEST_MODE = True

# 抓取最近幾天
DAYS_BACK = 30

# 每次請求間隔
REQUEST_DELAY = 2.0

# MOPS 歷史重大訊息
MOPS_URL = "https://mops.twse.com.tw/mops/web/ajax_t05st01"

# 網頁查詢入口，提供使用者點擊來源
MOPS_PAGE_URL = "https://mops.twse.com.tw/mops/web/t05st01"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


# ============================================================
# 2. Session
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 3. 共用工具
# ============================================================

def clean_text(value):
    """清理 HTML / 空白 / 換行。"""

    if value is None:
        return ""

    text = str(value)

    text = text.replace("\xa0", " ")
    text = text.replace("\u3000", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_stock_id(value):
    """股票代碼標準化。"""

    if value is None:
        return ""

    text = str(value).strip()

    if re.fullmatch(r"\d{4,6}", text):
        return text

    return ""


def roc_year(year):
    """西元年轉民國年。"""

    return year - 1911


def parse_roc_date(value):
    """
    將：

    115/10/12
    115/10/12 13:50

    轉成：

    2026-10-12
    2026-10-12 13:50
    """

    text = clean_text(value)

    if not text:
        return ""

    match = re.search(
        r"(\d{2,3})/(\d{1,2})/(\d{1,2})"
        r"(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        text
    )

    if not match:
        return text

    year = int(match.group(1)) + 1911
    month = int(match.group(2))
    day = int(match.group(3))

    hour = match.group(4)
    minute = match.group(5)
    second = match.group(6)

    if hour is None:
        return f"{year:04d}-{month:02d}-{day:02d}"

    return (
        f"{year:04d}-{month:02d}-{day:02d} "
        f"{int(hour):02d}:{int(minute):02d}"
        + (f":{int(second):02d}" if second else "")
    )


def parse_date_only(value):
    text = parse_roc_date(value)

    if not text:
        return None

    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# ============================================================
# 4. 事件分類
# ============================================================

def classify_event(title):
    """
    依 MOPS 公告主旨進行分類。

    注意：
    這裡只是「事件分類」，不是利多／利空判斷。
    """

    text = clean_text(title)

    # --------------------------------------------------------
    # 法人說明會
    # --------------------------------------------------------
    if any(keyword in text for keyword in [
        "法人說明會",
        "法說會",
        "投資人說明會",
        "受邀參加",
        "召開法人說明會",
    ]):
        return "法人說明會"

    # --------------------------------------------------------
    # 庫藏股
    # --------------------------------------------------------
    if any(keyword in text for keyword in [
        "庫藏股",
        "買回本公司股份",
        "買回股份",
        "註銷買回",
    ]):
        return "庫藏股"

    # --------------------------------------------------------
    # 董監 / 大股東異動
    # --------------------------------------------------------
    if any(keyword in text for keyword in [
        "董事",
        "獨立董事",
        "監察人",
        "董事長",
        "總經理",
        "經理人",
        "大股東",
        "持股",
        "設質",
        "質押",
        "轉讓",
        "法人董事代表",
    ]):
        return "董監／大股東異動"

    # --------------------------------------------------------
    # 可轉債
    # --------------------------------------------------------
    if any(keyword in text for keyword in [
        "可轉換公司債",
        "轉換公司債",
        "公司債",
        "可轉債",
    ]):
        return "可轉債"

    # --------------------------------------------------------
    # 增資 / 減資
    # --------------------------------------------------------
    if any(keyword in text for keyword in [
        "增資",
        "減資",
        "現金增資",
        "盈餘轉增資",
        "資本公積轉增資",
        "發行新股",
        "新股",
    ]):
        return "增資／減資"

    # --------------------------------------------------------
    # 重大投資 / 併購 / 資產交易
    # --------------------------------------------------------
    if any(keyword in text for keyword in [
        "取得資產",
        "處分資產",
        "取得股份",
        "處分股份",
        "投資",
        "併購",
        "合併",
        "收購",
        "股權",
        "投資計畫",
        "重大投資",
    ]):
        return "重大投資／併購"

    # --------------------------------------------------------
    # 其他重大訊息
    # --------------------------------------------------------
    return "重大訊息"


# ============================================================
# 5. 建立 MOPS 查詢網址
# ============================================================

def build_mops_page_url(stock_id, year):
    """
    建立可讓使用者直接查看 MOPS 的查詢網址。
    """

    params = {
        "step": "1",
        "firstin": "true",
        "year": str(roc_year(year)),
        "co_id": stock_id,
    }

    return MOPS_PAGE_URL + "?" + urlencode(params)


# ============================================================
# 6. 取得單一股票重大訊息
# ============================================================

def fetch_stock_events(stock_id, year):
    """
    查詢單一股票指定年度的 MOPS 重大訊息。
    """

    params = {
        "step": "1",
        "firstin": "1",
        "co_id": stock_id,
        "year": roc_year(year),
    }

    print(
        f"    查詢 MOPS："
        f"{stock_id} / {year}"
    )

    try:
        response = session.get(
            MOPS_URL,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

    except requests.RequestException as error:
        print(
            f"    [ERROR] HTTP 請求失敗：{error}"
        )
        return []

    # --------------------------------------------------------
    # MOPS 通常為 UTF-8
    # --------------------------------------------------------
    response.encoding = response.apparent_encoding or "utf-8"

    html = response.text

    if not html:
        print("    [WARN] MOPS 回傳空白資料")
        return []

    # --------------------------------------------------------
    # 防止遇到查詢過於頻繁
    # --------------------------------------------------------
    if any(keyword in html for keyword in [
        "查詢過於頻繁",
        "請稍後再試",
        "系統忙碌",
    ]):
        print(
            "    [WARN] MOPS 可能限制查詢頻率"
        )
        return []

    soup = BeautifulSoup(html, "html.parser")

    events = []

    # ========================================================
    # 找出所有表格
    # ========================================================

    tables = soup.find_all("table")

    if not tables:
        print("    [WARN] 找不到 MOPS 表格")
        return []

    for table in tables:

        rows = table.find_all("tr")

        if not rows:
            continue

        headers = []

        # ----------------------------------------------------
        # 先找欄位名稱
        # ----------------------------------------------------
        first_row_cells = rows[0].find_all(
            ["th", "td"]
        )

        for cell in first_row_cells:
            headers.append(
                clean_text(cell.get_text(" ", strip=True))
            )

        header_text = " ".join(headers)

        # ----------------------------------------------------
        # 判斷是不是重大訊息資料表
        # ----------------------------------------------------
        if not any(keyword in header_text for keyword in [
            "發言日期",
            "發言時間",
            "主旨",
            "公告日期",
            "公告時間",
        ]):
            continue

        # ----------------------------------------------------
        # 逐列解析
        # ----------------------------------------------------
        for row in rows[1:]:

            cells = row.find_all(
                ["td", "th"]
            )

            if len(cells) < 2:
                continue

            values = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True
                    )
                )
                for cell in cells
            ]

            row_text = " ".join(values)

            # ------------------------------------------------
            # 跳過無資料訊息
            # ------------------------------------------------
            if any(keyword in row_text for keyword in [
                "查無資料",
                "資料庫中查無需求資料",
            ]):
                continue

            # ------------------------------------------------
            # 找日期
            # ------------------------------------------------
            event_date = ""

            for value in values:
                parsed = parse_roc_date(value)

                if parsed and re.match(
                    r"^\d{4}-\d{2}-\d{2}",
                    parsed
                ):
                    event_date = parsed
                    break

            if not event_date:
                continue

            # ------------------------------------------------
            # 找主旨
            # ------------------------------------------------
            title = ""

            for value in values:
                if len(value) >= 5:
                    if (
                        "公告" in value
                        or "本公司" in value
                        or "公司" in value
                        or "說明" in value
                        or "召開" in value
                        or "受邀" in value
                    ):
                        title = value
                        break

            # 如果上面找不到，嘗試使用最後一欄
            if not title and values:
                candidates = [
                    value
                    for value in values
                    if len(value) >= 5
                ]

                if candidates:
                    title = max(
                        candidates,
                        key=len
                    )

            if not title:
                continue

            # ------------------------------------------------
            # 找公告連結
            # ------------------------------------------------
            source_url = build_mops_page_url(
                stock_id,
                year
            )

            # ------------------------------------------------
            # 事件分類
            # ------------------------------------------------
            category = classify_event(title)

            event = {
                "stock_id": stock_id,
                "date": event_date,
                "category": category,
                "title": title,
                "source": "公開資訊觀測站 MOPS",
                "source_url": source_url,
            }

            events.append(event)

    return events


# ============================================================
# 7. 去除重複事件
# ============================================================

def deduplicate_events(events):
    result = []
    seen = set()

    for event in events:

        key = (
            event.get("stock_id", ""),
            event.get("date", ""),
            event.get("title", ""),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(event)

    return result


# ============================================================
# 8. 過濾日期
# ============================================================

def filter_recent_events(events):
    today = datetime.now().date()

    start_date = today - timedelta(
        days=DAYS_BACK
    )

    result = []

    for event in events:

        event_date = parse_date_only(
            event.get("date", "")
        )

        if event_date is None:
            continue

        if start_date <= event_date <= today:
            result.append(event)

    return result


# ============================================================
# 9. 讀取 analysis.json 股票清單
# ============================================================

def load_stock_ids():
    if TEST_MODE:

        print(
            "目前為 TEST_MODE，只測試："
            + ", ".join(TEST_STOCKS)
        )

        return TEST_STOCKS

    if not ANALYSIS_FILE.exists():

        raise FileNotFoundError(
            f"找不到 {ANALYSIS_FILE}"
        )

    with ANALYSIS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if isinstance(data, dict):
        stocks = data.get(
            "stocks",
            []
        )
    elif isinstance(data, list):
        stocks = data
    else:
        stocks = []

    result = []

    for stock in stocks:

        if not isinstance(stock, dict):
            continue

        stock_id = normalize_stock_id(
            stock.get("stock_id")
        )

        if stock_id:
            result.append(stock_id)

    # 去除重複
    result = list(dict.fromkeys(result))

    return result


# ============================================================
# 10. 建立 events.json
# ============================================================

def save_events(events):

    today = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # --------------------------------------------------------
    # 按股票代碼、日期排序
    # --------------------------------------------------------
    events.sort(
        key=lambda item: (
            item.get("stock_id", ""),
            item.get("date", ""),
        ),
        reverse=True,
    )

    output = {
        "update_time": today,
        "source": "公開資訊觀測站 MOPS",
        "days_back": DAYS_BACK,
        "event_count": len(events),
        "events": events,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        f"已產生：{OUTPUT_FILE}"
    )

    print(
        f"事件數量：{len(events)}"
    )


# ============================================================
# 11. 主程式
# ============================================================

def main():

    print("=" * 60)
    print("台股事件／消息面資料收集器")
    print("資料來源：公開資訊觀測站 MOPS")
    print("=" * 60)

    stock_ids = load_stock_ids()

    print(
        f"準備處理 {len(stock_ids)} 檔股票"
    )

    all_events = []

    # --------------------------------------------------------
    # 目前只抓今年資料
    # --------------------------------------------------------
    current_year = datetime.now().year

    for index, stock_id in enumerate(
        stock_ids,
        start=1
    ):

        print()
        print(
            f"[{index}/{len(stock_ids)}] "
            f"股票代碼：{stock_id}"
        )

        events = fetch_stock_events(
            stock_id,
            current_year
        )

        print(
            f"    取得 {len(events)} 筆原始事件"
        )

        all_events.extend(events)

        # ----------------------------------------------------
        # 降低對 MOPS 的請求頻率
        # ----------------------------------------------------
        if index < len(stock_ids):
            time.sleep(
                REQUEST_DELAY
            )

    # ========================================================
    # 去除重複
    # ========================================================

    all_events = deduplicate_events(
        all_events
    )

    print()
    print(
        f"去除重複後：{len(all_events)} 筆"
    )

    # ========================================================
    # 只保留最近 DAYS_BACK 天
    # ========================================================

    recent_events = filter_recent_events(
        all_events
    )

    print(
        f"最近 {DAYS_BACK} 天："
        f"{len(recent_events)} 筆"
    )

    # ========================================================
    # 輸出
    # ========================================================

    save_events(
        recent_events
    )

    print()
    print("=" * 60)
    print("事件資料收集完成")
    print("=" * 60)


# ============================================================
# 12. 程式入口
# ============================================================

if __name__ == "__main__":
    main()
