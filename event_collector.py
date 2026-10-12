import datetime
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlencode
import pandas as pd
import requests
from bs4 import BeautifulSoup
# ============================================================
# 台股事件／消息面資料收集器
#
# 資料來源：
#   公開資訊觀測站 MOPS
#
# 目前第一階段：
#   1. 重大訊息
#   2. 法人說明會
#   3. 增資／減資
#   4. 庫藏股
#   5. 董監／大股東
#   6. 可轉債
#   7. 重大投資／取得處分資產
#
# 注意：
#   - 不修改 analysis.json
#   - 不修改既有股票分析程式
#   - 不修改原本 100 分評分
#   - 獨立產生 events.json
# ============================================================
# ============================================================
# 1. 基本設定
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
ANALYSIS_FILE = BASE_DIR / "analysis.json"
OUTPUT_FILE = BASE_DIR / "events.json"
LOG_FILE = BASE_DIR / "event_collector.log"
# 查詢最近幾天
LOOKBACK_DAYS = 30
# 每一檔股票最多保留事件數
MAX_EVENTS_PER_STOCK = 50
# MOPS 請求間隔
REQUEST_DELAY = 0.8
# HTTP Timeout
REQUEST_TIMEOUT = 30
# ============================================================
# 2. MOPS 基本網址
# ============================================================
MOPS_BASE_URL = "https://mops.twse.com.tw"
MOPS_COMPANY_URL = (
    MOPS_BASE_URL
    + "/mops/web/ajax_t05st01"
)
MOPS_MAJOR_URL = (
    MOPS_BASE_URL
    + "/mops/web/ajax_t05st01"
)
# ============================================================
# 3. HTTP Header
# ============================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}
# ============================================================
# 4. 日誌
# ============================================================
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)
# ============================================================
# 5. 事件類型
# ============================================================
EVENT_TYPES = {
    "major": "重大訊息",
    "meeting": "法人說明會",
    "capital": "增資／減資",
    "buyback": "庫藏股",
    "insider": "董監／大股東",
    "cb": "可轉債",
    "investment": "重大投資／資產交易",
}
# ============================================================
# 6. 事件優先級
# ============================================================
EVENT_PRIORITY = {
    "major": 5,
    "meeting": 5,
    "capital": 5,
    "buyback": 5,
    "insider": 5,
    "cb": 4,
    "investment": 5,
}
# ============================================================
# 7. 事件分類關鍵字
#
# 注意：
# MOPS 本身已經是官方公告來源。
#
# 關鍵字只是用來將「重大訊息」進一步細分，
# 並不是資料來源。
# ============================================================
EVENT_KEYWORDS = {
    "meeting": [
        "法人說明會",
        "法說會",
        "法人說明",
        "投資人說明會",
    ],
    "capital": [
        "現金增資",
        "增資發行新股",
        "減資",
        "私募",
        "募集",
        "發行新股",
        "增資基準日",
    ],
    "buyback": [
        "庫藏股",
        "買回本公司股份",
        "買回股份",
        "股份買回",
        "註銷庫藏股",
    ],
    "insider": [
        "董事長",
        "總經理",
        "董事",
        "監察人",
        "獨立董事",
        "經理人",
        "大股東",
        "持股異動",
        "持股轉讓",
        "申報轉讓",
        "質押",
        "設質",
        "解除質押",
        "解質",
    ],
    "cb": [
        "可轉換公司債",
        "轉換公司債",
        "可轉債",
        "轉換價格",
        "債券換股",
    ],
    "investment": [
        "取得資產",
        "處分資產",
        "取得股權",
        "處分股權",
        "重大投資",
        "轉投資",
        "併購",
        "合併",
        "收購",
        "重大合約",
        "重大訂單",
        "策略合作",
    ],
}
# ============================================================
# 8. 初步影響方向
#
# 這個欄位只供前端參考。
# 不納入原本 100 分。
# ============================================================
POSITIVE_KEYWORDS = [
    "庫藏股",
    "買回",
    "取得",
    "合作",
    "訂單",
    "量產",
    "擴產",
    "取得許可",
    "營收創高",
    "獲利增加",
]
NEGATIVE_KEYWORDS = [
    "裁罰",
    "訴訟敗訴",
    "虧損",
    "減產",
    "停產",
    "撤單",
    "下修",
    "重大損失",
    "違約",
]
# ============================================================
# 9. 建立 Session
# ============================================================
def create_session():
    session = requests.Session()
    session.headers.update(
        HEADERS
    )
    return session
# ============================================================
# 10. 讀取 analysis.json
# ============================================================
def load_analysis_stocks():
    if not ANALYSIS_FILE.exists():
        raise FileNotFoundError(
            f"找不到分析資料：{ANALYSIS_FILE}"
        )
    with ANALYSIS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)
    if isinstance(data, list):
        stocks = data
    elif isinstance(data, dict):
        stocks = data.get(
            "stocks",
            []
        )
    else:
        raise ValueError(
            "analysis.json 格式不正確"
        )
    result = []
    for stock in stocks:
        if not isinstance(
            stock,
            dict
        ):
            continue
        stock_id = str(
            stock.get(
                "stock_id",
                ""
            )
        ).strip()
        if not re.fullmatch(
            r"\d{4,6}",
            stock_id
        ):
            continue
        stock_name = (
            stock.get("short_name")
            or stock.get("stock_name")
            or stock.get("name")
            or ""
        )
        result.append({
            "stock_id": stock_id,
            "stock_name": str(stock_name)
        })
    return result
# ============================================================
# 11. 民國日期轉西元日期
# ============================================================
def convert_minguo_date(value):
    text = str(
        value or ""
    ).strip()
    if not text:
        return ""
    # 115/10/12
    match = re.search(
        r"(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})",
        text
    )
    if match:
        year = int(
            match.group(1)
        )
        month = int(
            match.group(2)
        )
        day = int(
            match.group(3)
        )
        if year < 1911:
            year += 1911
        try:
            return datetime.date(
                year,
                month,
                day
            ).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            return ""
    # 西元日期
    match = re.search(
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
        text
    )
    if match:
        try:
            return datetime.date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3))
            ).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            return ""
    return ""
# ============================================================
# 12. 判斷事件類型
# ============================================================
def classify_event(title):
    text = str(
        title or ""
    ).strip()
    # 優先順序
    priority_order = [
        "capital",
        "buyback",
        "cb",
        "insider",
        "meeting",
        "investment",
    ]
    for event_type in priority_order:
        keywords = EVENT_KEYWORDS.get(
            event_type,
            []
        )
        for keyword in keywords:
            if keyword in text:
                return event_type
    return "major"
# ============================================================
# 13. 判斷事件影響
# ============================================================
def classify_impact(
    title,
    event_type
):
    text = str(
        title or ""
    )
    positive = any(
        keyword in text
        for keyword in POSITIVE_KEYWORDS
    )
    negative = any(
        keyword in text
        for keyword in NEGATIVE_KEYWORDS
    )
    if positive and not negative:
        return "positive"
    if negative and not positive:
        return "negative"
    return "neutral"
# ============================================================
# 14. 解析 MOPS 表格
# ============================================================
def parse_mops_tables(
    html
):
    try:
        tables = pd.read_html(
            html
        )
    except ValueError:
        return []
    except Exception as exc:
        logging.warning(
            "解析 MOPS HTML 失敗：%s",
            exc
        )
        return []
    return tables
# ============================================================
# 15. 找出包含指定股票代號的表格
# ============================================================
def find_stock_tables(
    tables,
    stock_id
):
    result = []
    for table in tables:
        if table is None:
            continue
        if table.empty:
            continue
        text = table.astype(
            str
        ).to_string(
            index=False
        )
        if stock_id in text:
            result.append(
                table
            )
    return result
# ============================================================
# 16. 從 MOPS 表格找公告資料
# ============================================================
def extract_events_from_table(
    table,
    stock
):
    stock_id = stock[
        "stock_id"
    ]
    stock_name = stock[
        "stock_name"
    ]
    events = []
    # --------------------------------------------------------
    # 將 MultiIndex 欄位轉成文字
    # --------------------------------------------------------
    columns = []
    for column in table.columns:
        if isinstance(
            column,
            tuple
        ):
            name = " ".join(
                str(x)
                for x in column
                if str(x) != "nan"
            )
        else:
            name = str(column)
        columns.append(
            name.strip()
        )
    table = table.copy()
    table.columns = columns
    # --------------------------------------------------------
    # 尋找可能的日期欄位
    # --------------------------------------------------------
    date_columns = [
        column
        for column in table.columns
        if any(
            keyword in column
            for keyword in [
                "日期",
                "時間",
                "發布"
            ]
        )
    ]
    # --------------------------------------------------------
    # 尋找可能的主旨欄位
    # --------------------------------------------------------
    title_columns = [
        column
        for column in table.columns
        if any(
            keyword in column
            for keyword in [
                "主旨",
                "標題",
                "事由",
                "說明"
            ]
        )
    ]
    # --------------------------------------------------------
    # 如果找不到標題欄位，
    # 嘗試使用文字最長的欄位
    # --------------------------------------------------------
    if not title_columns:
        for column in table.columns:
            series = table[
                column
            ].astype(str)
            if series.str.len().mean() > 15:
                title_columns.append(
                    column
                )
                break
    if not title_columns:
        return events
    # --------------------------------------------------------
    # 建立事件
    # --------------------------------------------------------
    for _, row in table.iterrows():
        title = ""
        for column in title_columns:
            value = str(
                row.get(
                    column,
                    ""
                )
            ).strip()
            if (
                value
                and value != "nan"
                and len(value) > len(title)
            ):
                title = value
        if not title:
            continue
        # 避免把純欄位標題當事件
        if title in [
            "主旨",
            "公告事項",
            "說明",
            "標題"
        ]:
            continue
        event_date = ""
        for column in date_columns:
            value = str(
                row.get(
                    column,
                    ""
                )
            )
            event_date = convert_minguo_date(
                value
            )
            if event_date:
                break
        event_type = classify_event(
            title
        )
        impact = classify_impact(
            title,
            event_type
        )
        events.append({
            "stock_id": stock_id,
            "stock_name": stock_name,
            "date": event_date,
            "event_type": event_type,
            "event_name": EVENT_TYPES.get(
                event_type,
                "重大訊息"
            ),
            "title": title,
            "impact": impact,
            "priority": EVENT_PRIORITY.get(
                event_type,
                4
            ),
            "source": "公開資訊觀測站 MOPS",
            "url": "",
            "message": title
        })
    return events
# ============================================================
# 17. 查詢單一股票重大訊息
# ============================================================
def fetch_major_events(
    session,
    stock
):
    stock_id = stock[
        "stock_id"
    ]
    today = datetime.date.today()
    events = []
    # --------------------------------------------------------
    # MOPS 查詢參數
    #
    # MOPS 歷史重大訊息查詢使用：
    # co_id = 公司代號
    # --------------------------------------------------------
    params = {
        "encodeURIComponent": 1,
        "step": 1,
        "firstin": 1,
        "off": 1,
        "TYPEK": "all",
        "co_id": stock_id,
        "year": today.year - 1911,
        "month": today.month,
        "qryType": "0",
    }
    try:
        response = session.post(
            MOPS_MAJOR_URL,
            data=params,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        response.encoding = "utf-8"
        html = response.text
    except Exception as exc:
        logging.warning(
            "%s MOPS 查詢失敗：%s",
            stock_id,
            exc
        )
        return []
    if not html:
        return []
    tables = parse_mops_tables(
        html
    )
    if not tables:
        return []
    for table in tables:
        table_events = extract_events_from_table(
            table,
            stock
        )
        events.extend(
            table_events
        )
    return events
# ============================================================
# 18. 去除重複事件
# ============================================================
def deduplicate_events(
    events
):
    result = []
    seen = set()
    for event in events:
        key = (
            event.get(
                "stock_id",
                ""
            ),
            event.get(
                "date",
                ""
            ),
            event.get(
                "title",
                ""
            )
        )
        if key in seen:
            continue
        seen.add(
            key
        )
        result.append(
            event
        )
    return result
# ============================================================
# 19. 排序事件
# ============================================================
def sort_events(
    events
):
    return sorted(
        events,
        key=lambda event: (
            event.get(
                "date",
                ""
            ),
            event.get(
                "priority",
                0
            )
        ),
        reverse=True
    )
# ============================================================
# 20. 過濾日期
# ============================================================
def filter_events_by_date(
    events,
    start_date,
    end_date
):
    result = []
    for event in events:
        event_date = event.get(
            "date",
            ""
        )
        if not event_date:
            continue
        if (
            start_date
            <= event_date
            <= end_date
        ):
            result.append(
                event
            )
    return result
# ============================================================
# 21. 分析單一股票
# ============================================================
def analyze_stock(
    session,
    stock,
    start_date,
    end_date
):
    stock_id = stock[
        "stock_id"
    ]
    logging.info(
        "%s 開始取得 MOPS 事件",
        stock_id
    )
    events = fetch_major_events(
        session,
        stock
    )
    events = filter_events_by_date(
        events,
        start_date,
        end_date
    )
    events = deduplicate_events(
        events
    )
    events = sort_events(
        events
    )
    events = events[
        :MAX_EVENTS_PER_STOCK
    ]
    logging.info(
        "%s 取得事件 %s 筆",
        stock_id,
        len(events)
    )
    return {
        "stock_id": stock_id,
        "stock_name": stock[
            "stock_name"
        ],
        "event_count": len(events),
        "events": events
    }
# ============================================================
# 22. 統計資料
# ============================================================
def build_statistics(
    stocks
):
    type_counts = {
        event_type: 0
        for event_type in EVENT_TYPES
    }
    total_events = 0
    for stock in stocks:
        events = stock.get(
            "events",
            []
        )
        total_events += len(
            events
        )
        for event in events:
            event_type = event.get(
                "event_type"
            )
            if event_type in type_counts:
                type_counts[
                    event_type
                ] += 1
    return {
        "stock_count": len(
            stocks
        ),
        "total_events": total_events,
        "event_type_counts": type_counts
    }
# ============================================================
# 23. 儲存 events.json
# ============================================================
def save_events(
    stocks,
    start_date,
    end_date
):
    statistics = build_statistics(
        stocks
    )
    output = {
        "update_time": datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "source": (
            "公開資訊觀測站 MOPS"
        ),
        "data_period": {
            "start_date": start_date,
            "end_date": end_date
        },
        "event_types": EVENT_TYPES,
        "statistics": statistics,
        "stocks": stocks
    }
    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )
    logging.info(
        "events.json 已建立：%s",
        OUTPUT_FILE
    )
# ============================================================
# 24. 主程式
# ============================================================
def main():
    today = datetime.date.today()
    start_date = (
        today
        - datetime.timedelta(
            days=LOOKBACK_DAYS
        )
    ).strftime(
        "%Y-%m-%d"
    )
    end_date = today.strftime(
        "%Y-%m-%d"
    )
    logging.info(
        "=========================================="
    )
    logging.info(
        "MOPS 事件／消息面收集開始"
    )
    logging.info(
        "資料期間：%s ~ %s",
        start_date,
        end_date
    )
    # --------------------------------------------------------
    # 讀取目前股票
    # --------------------------------------------------------
    stocks = load_analysis_stocks()
    logging.info(
        "股票數量：%s",
        len(stocks)
    )
    # --------------------------------------------------------
    # 建立 Session
    # --------------------------------------------------------
    session = create_session()
    results = []
    # --------------------------------------------------------
    # 逐檔處理
    # --------------------------------------------------------
    for index, stock in enumerate(
        stocks,
        start=1
    ):
        logging.info(
            "處理 %s/%s：%s %s",
            index,
            len(stocks),
            stock["stock_id"],
            stock["stock_name"]
        )
        try:
            result = analyze_stock(
                session,
                stock,
                start_date,
                end_date
            )
            results.append(
                result
            )
        except Exception as exc:
            logging.exception(
                "%s 處理失敗：%s",
                stock["stock_id"],
                exc
            )
            results.append({
                "stock_id": stock[
                    "stock_id"
                ],
                "stock_name": stock[
                    "stock_name"
                ],
                "event_count": 0,
                "events": [],
                "error": str(exc)
            })
        # ----------------------------------------------------
        # 避免連續大量請求
        # ----------------------------------------------------
        if index < len(stocks):
            time.sleep(
                REQUEST_DELAY
            )
    # --------------------------------------------------------
    # 儲存
    # --------------------------------------------------------
    save_events(
        results,
        start_date,
        end_date
    )
    statistics = build_statistics(
        results
    )
    logging.info(
        "事件總數：%s",
        statistics[
            "total_events"
        ]
    )
    logging.info(
        "事件分類：%s",
        statistics[
            "event_type_counts"
        ]
    )
    logging.info(
        "MOPS 事件／消息面收集完成"
    )
    logging.info(
        "=========================================="
    )
# ============================================================
# 25. 程式進入點
# ============================================================
if __name__ == "__main__":
    main()
