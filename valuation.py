import datetime
import logging
import re
from functools import lru_cache
import pandas as pd
import requests
# ============================================================
# 1. 基本設定
# ============================================================
BASE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d"
REQUEST_TIMEOUT = 30
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.twse.com.tw/",
}
# ============================================================
# 2. Logging
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)
# ============================================================
# 3. 日期處理
# ============================================================
def normalize_date(value):
    """
    將日期統一轉成 YYYYMMDD 字串。
    支援：
    - datetime.date
    - datetime.datetime
    - YYYY-MM-DD
    - YYYY/MM/DD
    - YYYYMMDD
    """
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, datetime.date):
        return value.strftime("%Y%m%d")
    if value is None:
        raise ValueError("日期不可為 None")
    value = str(value).strip()
    if not value:
        raise ValueError("日期不可為空")
    # YYYYMMDD
    if re.fullmatch(r"\d{8}", value):
        return value
    # YYYY-MM-DD / YYYY/MM/DD
    match = re.fullmatch(
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
        value,
    )
    if match:
        year, month, day = match.groups()
        dt = datetime.date(
            int(year),
            int(month),
            int(day),
        )
        return dt.strftime("%Y%m%d")
    raise ValueError(f"無法辨識日期格式：{value}")
def format_display_date(date_str):
    """
    YYYYMMDD -> YYYY-MM-DD
    """
    date_str = normalize_date(date_str)
    return (
        f"{date_str[0:4]}-"
        f"{date_str[4:6]}-"
        f"{date_str[6:8]}"
    )
# ============================================================
# 4. ROC 日期處理
# ============================================================
def roc_date_to_ad(value):
    """
    將民國日期轉成西元日期。
    例如：
    115/2 -> 2026/2
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(
        r"(\d{2,3})\s*/\s*(\d{1,2})",
        text,
    )
    if not match:
        return None
    roc_year = int(match.group(1))
    month = int(match.group(2))
    ad_year = roc_year + 1911
    return f"{ad_year}/{month}"
# ============================================================
# 5. 數值處理
# ============================================================
def to_number(value):
    """
    將 TWSE 回傳的數值轉成 Python number。
    以下狀況一律回傳 None：
    - None
    - NaN
    - 空字串
    - "-"
    - "—"
    - "－"
    """
    if value is None:
        return None
    # pandas NaN
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).strip()
    if not text:
        return None
    if text in {"-", "—", "－", "N/A", "NA", "null", "None"}:
        return None
    # 移除千分位
    text = text.replace(",", "")
    try:
        number = float(text)
        if pd.isna(number):
            return None
        # 如果是整數，轉成 int
        if number.is_integer():
            return int(number)
        return number
    except (TypeError, ValueError):
        return None
# ============================================================
# 6. TWSE API
# ============================================================
@lru_cache(maxsize=20)
def fetch_twse_valuation(date_str):
    """
    查詢 TWSE 個股日本益比、殖利率及股價淨值比。
    回傳：
    {
        "date": "20261022",
        "data": DataFrame,
        "message": ""
    }
    """
    date_str = normalize_date(date_str)
    logger.info(
        "查詢 TWSE 個股估值資料：%s",
        date_str,
    )
    params = {
        "date": date_str,
        "selectType": "ALL",
        "response": "json",
    }
    try:
        response = requests.get(
            BASE_URL,
            params=params,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error(
            "TWSE API 請求失敗：%s",
            exc,
        )
        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": f"HTTP 請求失敗：{exc}",
        }
    try:
        result = response.json()
    except ValueError as exc:
        logger.error(
            "TWSE API 回傳不是有效 JSON：%s",
            exc,
        )
        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": f"JSON 解析失敗：{exc}",
        }
    # --------------------------------------------------------
    # API 狀態
    # --------------------------------------------------------
    stat = result.get("stat")
    if stat != "OK":
        message = result.get(
            "message",
            "TWSE API 沒有回傳 OK",
        )
        logger.warning(
            "TWSE 估值資料無法取得：%s",
            message,
        )
        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": str(message),
        }
    fields = result.get("fields", [])
    data = result.get("data", [])
    if not fields:
        logger.warning(
            "TWSE API 沒有回傳欄位：%s",
            date_str,
        )
        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": "API 沒有回傳欄位",
        }
    if not data:
        logger.warning(
            "TWSE API 沒有回傳資料：%s",
            date_str,
        )
        return {
            "date": date_str,
            "data": pd.DataFrame(
                columns=fields
            ),
            "message": "該日期沒有估值資料",
        }
    df = pd.DataFrame(
        data,
        columns=fields,
    )
    logger.info(
        "TWSE 估值資料取得成功：日期=%s，筆數=%d",
        date_str,
        len(df),
    )
    logger.info(
        "API 實際欄位：%s",
        list(df.columns),
    )
    return {
        "date": date_str,
        "data": df,
        "message": "",
    }
# ============================================================
# 7. 欄位名稱尋找
# ============================================================
def find_column(df, candidates):
    """
    從 DataFrame 中尋找第一個符合的欄位名稱。
    """
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None
# ============================================================
# 8. 整理 TWSE 估值資料
# ============================================================
def prepare_valuation_data(df):
    """
    將 TWSE 原始資料轉成程式內部統一格式。
    輸出欄位：
    stock_id
    stock_name
    close_price
    pe_ratio
    pb_ratio
    dividend_yield
    dividend_year
    financial_period
    """
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "stock_id",
                "stock_name",
                "close_price",
                "pe_ratio",
                "pb_ratio",
                "dividend_yield",
                "dividend_year",
                "financial_period",
            ]
        )
    # --------------------------------------------------------
    # 找欄位
    # --------------------------------------------------------
    stock_id_col = find_column(
        df,
        [
            "證券代號",
            "股票代號",
            "代號",
        ],
    )
    stock_name_col = find_column(
        df,
        [
            "證券名稱",
            "股票名稱",
            "名稱",
        ],
    )
    close_price_col = find_column(
        df,
        [
            "收盤價",
        ],
    )
    dividend_yield_col = find_column(
        df,
        [
            "殖利率(%)",
            "殖利率",
        ],
    )
    dividend_year_col = find_column(
        df,
        [
            "股利年度",
        ],
    )
    pe_ratio_col = find_column(
        df,
        [
            "本益比",
        ],
    )
    pb_ratio_col = find_column(
        df,
        [
            "股價淨值比",
            "市淨率",
        ],
    )
    financial_period_col = find_column(
        df,
        [
            "財報年/季",
            "財報年季",
        ],
    )
    # --------------------------------------------------------
    # 必要欄位
    # --------------------------------------------------------
    if stock_id_col is None:
        raise ValueError(
            "找不到股票代號欄位"
        )
    # --------------------------------------------------------
    # 建立標準資料
    # --------------------------------------------------------
    result = pd.DataFrame()
    result["stock_id"] = (
        df[stock_id_col]
        .astype(str)
        .str.strip()
        .str.zfill(4)
    )
    if stock_name_col:
        result["stock_name"] = (
            df[stock_name_col]
            .astype(str)
            .str.strip()
        )
    else:
        result["stock_name"] = None
    # --------------------------------------------------------
    # 數值欄位
    # --------------------------------------------------------
    if close_price_col:
        result["close_price"] = (
            df[close_price_col]
            .apply(to_number)
        )
    else:
        result["close_price"] = None
    if pe_ratio_col:
        result["pe_ratio"] = (
            df[pe_ratio_col]
            .apply(to_number)
        )
    else:
        result["pe_ratio"] = None
    if pb_ratio_col:
        result["pb_ratio"] = (
            df[pb_ratio_col]
            .apply(to_number)
        )
    else:
        result["pb_ratio"] = None
    if dividend_yield_col:
        result["dividend_yield"] = (
            df[dividend_yield_col]
            .apply(to_number)
        )
    else:
        result["dividend_yield"] = None
    if dividend_year_col:
        result["dividend_year"] = (
            df[dividend_year_col]
            .apply(to_number)
        )
    else:
        result["dividend_year"] = None
    # --------------------------------------------------------
    # 財報年季
    # --------------------------------------------------------
    if financial_period_col:
        result["financial_period"] = (
            df[financial_period_col]
            .apply(
                lambda value:
                None
                if pd.isna(value)
                else str(value).strip()
            )
        )
    else:
        result["financial_period"] = None
    return result
# ============================================================
# 9. 查詢單一股票估值
# ============================================================
def analyze_valuation(stock_id, date_value):
    """
    查詢指定股票在指定日期的估值資料。
    """
    stock_id = str(stock_id).strip().zfill(4)
    date_str = normalize_date(date_value)
    fetched = fetch_twse_valuation(date_str)
    if fetched["data"].empty:
        return {
            "stock_id": stock_id,
            "valuation_date": format_display_date(date_str),
            "stock_name": None,
            "close_price": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "dividend_yield": None,
            "dividend_year": None,
            "financial_period": None,
            "data_available": False,
            "message": fetched["message"],
        }
    valuation_df = prepare_valuation_data(
        fetched["data"]
    )
    matched = valuation_df[
        valuation_df["stock_id"] == stock_id
    ]
    if matched.empty:
        return {
            "stock_id": stock_id,
            "valuation_date": format_display_date(date_str),
            "stock_name": None,
            "close_price": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "dividend_yield": None,
            "dividend_year": None,
            "financial_period": None,
            "data_available": False,
            "message": "查無該股票估值資料",
        }
    row = matched.iloc[0]
    return {
        "stock_id": stock_id,
        "valuation_date": format_display_date(date_str),
        "stock_name": row["stock_name"],
        "close_price": row["close_price"],
        "pe_ratio": row["pe_ratio"],
        "pb_ratio": row["pb_ratio"],
        "dividend_yield": row["dividend_yield"],
        "dividend_year": row["dividend_year"],
        "financial_period": row["financial_period"],
        "data_available": True,
        "message": "",
    }
# ============================================================
# 10. 主程式：測試
# ============================================================
if __name__ == "__main__":
    # --------------------------------------------------------
    # 測試日期
    # --------------------------------------------------------
    TEST_DATE = "2026-10-22"
    # --------------------------------------------------------
    # 測試股票
    # --------------------------------------------------------
    TEST_STOCKS = [
        "1101",
        "1102",
        "2330",
        "2454",
    ]
    print("=" * 70)
    print("TWSE 個股估值資料測試")
    print("查詢日期：", TEST_DATE)
    print("=" * 70)
    # --------------------------------------------------------
    # 查詢 TWSE
    # --------------------------------------------------------
    date_str = normalize_date(TEST_DATE)
    fetched = fetch_twse_valuation(date_str)
    if fetched["data"].empty:
        print()
        print("查詢失敗或該日期沒有資料。")
        print("原因：", fetched["message"])
        raise SystemExit(1)
    valuation_df = prepare_valuation_data(
        fetched["data"]
    )
    print()
    print("資料日期：", format_display_date(date_str))
    print("資料筆數：", len(valuation_df))
    # --------------------------------------------------------
    # 測試指定股票
    # --------------------------------------------------------
    for stock_id in TEST_STOCKS:
        print()
        print("-" * 50)
        result = analyze_valuation(
            stock_id,
            date_str,
        )
        print("股票代號：", result["stock_id"])
        print("股票名稱：", result["stock_name"])
        print("收盤價：", result["close_price"])
        print("本益比：", result["pe_ratio"])
        print("股價淨值比：", result["pb_ratio"])
        print("殖利率：", result["dividend_yield"])
        print("股利年度：", result["dividend_year"])
        print("財報年/季：", result["financial_period"])
        if not result["data_available"]:
            print("資料狀態：無資料")
            print("原因：", result["message"])
    # --------------------------------------------------------
    # 輸出 CSV
    # --------------------------------------------------------
    output_file = (
        f"twse_valuation_{date_str}.csv"
    )
    # CSV 缺失值保持空白，不輸出 nan
    valuation_df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig",
        na_rep="",
    )
    print()
    print("=" * 70)
    print(
        "完整資料已輸出：",
        output_file,
    )
    print("=" * 70)
