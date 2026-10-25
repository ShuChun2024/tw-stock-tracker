import datetime
import logging
import re
from functools import lru_cache
import pandas as pd
import requests
# ============================================================
# 1. 基本設定
# ============================================================
BASE_URL = (
    "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d"
)
REQUEST_TIMEOUT = 30
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.twse.com.tw/",
}
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
# ============================================================
# 2. 日期轉換
# ============================================================
def normalize_date(value):
    """
    將日期轉換為 YYYYMMDD。
    支援：
    - datetime.date
    - datetime.datetime
    - YYYY-MM-DD
    - YYYYMMDD
    """
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, datetime.date):
        return value.strftime("%Y%m%d")
    value = str(value).strip()
    if re.fullmatch(r"\d{8}", value):
        return value
    try:
        return datetime.datetime.strptime(
            value, "%Y-%m-%d"
        ).strftime("%Y%m%d")
    except ValueError as exc:
        raise ValueError(
            f"不支援的日期格式：{value}"
        ) from exc
def roc_date_to_ad(value):
    """
    將民國日期轉成西元日期。
    例如：
    115/2 -> 2026/2
    """
    if value is None:
        return None
    text = str(value).strip()
    match = re.fullmatch(
        r"(\d{2,3})\s*/\s*(\d{1,2})",
        text
    )
    if not match:
        return text or None
    roc_year = int(match.group(1))
    month = int(match.group(2))
    if not 1 <= month <= 12:
        return text
    return f"{roc_year + 1911:04d}/{month:02d}"
# ============================================================
# 3. 數值整理
# ============================================================
def to_number(value):
    """
    將 API 欄位轉為數字。
    空值、'-'、'--'、無法辨識的值回傳 None。
    不會將缺失資料轉成 0。
    """
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in ("", "-", "--", "---", "N/A", "nan"):
        return None
    try:
        number = float(text)
    except (TypeError, ValueError, OverflowError):
        return None
    if pd.isna(number):
        return None
    return number
# ============================================================
# 4. 取得指定日期的證交所估值資料
# ============================================================
@lru_cache(maxsize=20)
def fetch_twse_valuation(date_str):
    """
    取得指定交易日的上市股票估值資料。
    date_str 格式：YYYYMMDD
    回傳：
        {
            "date": "YYYY-MM-DD",
            "data": DataFrame,
            "message": "..."
        }
    注意：
    此函式不會自動改查其他日期。
    """
    date_str = normalize_date(date_str)
    params = {
        "date": date_str,
        "selectType": "ALL",
        "response": "json",
    }
    logging.info(
        "查詢 TWSE 個股估值資料：%s",
        date_str
    )
    response = requests.get(
        BASE_URL,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "TWSE 回傳內容不是有效 JSON："
            + response.text[:300]
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            "TWSE 回傳格式不是 JSON 物件。"
        )
    if payload.get("stat") != "OK":
        message = (
            payload.get("title")
            or payload.get("stat")
            or "未知錯誤"
        )
        raise RuntimeError(
            f"TWSE 查詢失敗，日期={date_str}，"
            f"訊息={message}"
        )
    if "fields" not in payload or "data" not in payload:
        raise RuntimeError(
            "TWSE 回傳資料缺少 fields 或 data。"
            f"實際欄位：{list(payload.keys())}"
        )
    df = pd.DataFrame(
        payload["data"],
        columns=payload["fields"]
    )
    if df.empty:
        raise RuntimeError(
            f"TWSE 沒有回傳資料，日期={date_str}"
        )
    logging.info(
        "TWSE 估值資料取得成功：日期=%s，筆數=%s",
        date_str,
        len(df)
    )
    logging.info(
        "API 實際欄位：%s",
        list(df.columns)
    )
    return {
        "date": (
            datetime.datetime.strptime(
                date_str, "%Y%m%d"
            ).strftime("%Y-%m-%d")
        ),
        "data": df,
        "message": payload.get("title", "查詢成功"),
    }
# ============================================================
# 5. 對應證交所欄位
# ============================================================
def find_column(df, candidates):
    """
    從實際 API 欄位中尋找符合的欄位名稱。
    """
    for name in candidates:
        if name in df.columns:
            return name
    return None
def prepare_valuation_data(df):
    """
    整理證交所回傳資料。
    欄位名稱以實際 API 回應為準；
    如果缺少必要欄位，會明確報錯。
    """
    if df is None or df.empty:
        return pd.DataFrame()
    stock_id_col = find_column(
        df,
        ["證券代號", "股票代號", "公司代號"]
    )
    stock_name_col = find_column(
        df,
        ["證券名稱", "股票名稱", "公司名稱"]
    )
    if stock_id_col is None:
        raise RuntimeError(
            "API 回應找不到股票代號欄位。"
            f"實際欄位：{list(df.columns)}"
        )
    if stock_name_col is None:
        raise RuntimeError(
            "API 回應找不到股票名稱欄位。"
            f"實際欄位：{list(df.columns)}"
        )
    # 不同版本的頁面可能提供不同欄位。
    close_col = find_column(
        df,
        ["收盤價", "收盤"]
    )
    yield_col = find_column(
        df,
        ["殖利率(%)", "殖利率"]
    )
    dividend_year_col = find_column(
        df,
        ["股利年度"]
    )
    pe_col = find_column(
        df,
        ["本益比"]
    )
    pb_col = find_column(
        df,
        ["股價淨值比"]
    )
    financial_period_col = find_column(
        df,
        ["財報年/季", "財報年季"]
    )
    # 本益比、股價淨值比、殖利率為核心欄位。
    missing_columns = []
    if yield_col is None:
        missing_columns.append("殖利率(%)")
    if pe_col is None:
        missing_columns.append("本益比")
    if pb_col is None:
        missing_columns.append("股價淨值比")
    if missing_columns:
        raise RuntimeError(
            f"API 缺少必要估值欄位：{missing_columns}；"
            f"實際欄位：{list(df.columns)}"
        )
    result = pd.DataFrame()
    result["stock_id"] = (
        df[stock_id_col]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(4)
    )
    result["stock_name"] = (
        df[stock_name_col]
        .astype(str)
        .str.strip()
    )
    result["close_price"] = (
        df[close_col].map(to_number)
        if close_col
        else None
    )
    result["pe_ratio"] = df[pe_col].map(to_number)
    result["pb_ratio"] = df[pb_col].map(to_number)
    result["dividend_yield"] = (
        df[yield_col].map(to_number)
    )
    result["dividend_year"] = (
        df[dividend_year_col].map(to_number)
        if dividend_year_col
        else None
    )
    result["financial_period"] = (
        df[financial_period_col].astype(str).str.strip()
        if financial_period_col
        else None
    )
    return result.reset_index(drop=True)
# ============================================================
# 6. 查詢單一股票估值
# ============================================================
def analyze_valuation(stock_id, date_value):
    """
    查詢單一股票的估值資料。
    參數：
        stock_id：股票代號，例如 2330
        date_value：日期，例如 20261023 或 2026-10-23
    回傳格式：
        {
            "stock_id": "2330",
            "stock_name": "台積電",
            "valuation_date": "2026-10-23",
            "close_price": ...,
            "pe_ratio": ...,
            "pb_ratio": ...,
            "dividend_yield": ...,
            "dividend_year": ...,
            "financial_period": ...,
            "data_available": True,
            "message": "..."
        }
    """
    stock_id = str(stock_id).strip().zfill(4)
    date_str = normalize_date(date_value)
    result = {
        "stock_id": stock_id,
        "stock_name": None,
        "valuation_date": None,
        "close_price": None,
        "pe_ratio": None,
        "pb_ratio": None,
        "dividend_yield": None,
        "dividend_year": None,
        "financial_period": None,
        "data_available": False,
        "message": "資料不足",
    }
    try:
        fetched = fetch_twse_valuation(date_str)
        valuation_df = prepare_valuation_data(
            fetched["data"]
        )
        matched = valuation_df[
            valuation_df["stock_id"] == stock_id
        ]
        if matched.empty:
            result["message"] = (
                "指定日期找不到此股票的估值資料"
            )
            return result
        row = matched.iloc[0]
        result.update({
            "stock_name": row["stock_name"],
            "valuation_date": fetched["date"],
            "close_price": row["close_price"],
            "pe_ratio": row["pe_ratio"],
            "pb_ratio": row["pb_ratio"],
            "dividend_yield": row["dividend_yield"],
            "dividend_year": row["dividend_year"],
            "financial_period": row["financial_period"],
            "data_available": True,
            "message": "取得估值資料成功",
        })
        return result
    except Exception as exc:
        logging.exception(
            "查詢股票 %s 估值資料失敗",
            stock_id
        )
        result["message"] = str(exc)
        return result
# ============================================================
# 7. 獨立測試入口
# ============================================================
if __name__ == "__main__":
    # 請設定要測試的交易日。
    # 日期必須是證交所已公布資料的日期。
    TEST_DATE = "2026-10-22"
    # 測試股票，可自行增加。
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
    try:
        # 一次取得整個交易日的資料，
        # 避免每檔股票都重新發送 HTTP 請求。
        fetched = fetch_twse_valuation(
            normalize_date(TEST_DATE)
        )
        valuation_df = prepare_valuation_data(
            fetched["data"]
        )
        print("\n資料日期：", fetched["date"])
        print("資料筆數：", len(valuation_df))
        for stock_id in TEST_STOCKS:
            matched = valuation_df[
                valuation_df["stock_id"]
                == str(stock_id).zfill(4)
            ]
            print("\n" + "-" * 50)
            print("股票代號：", stock_id)
            if matched.empty:
                print("查無資料")
                continue
            row = matched.iloc[0]
            print("股票名稱：", row["stock_name"])
            print("收盤價：", row["close_price"])
            print("本益比：", row["pe_ratio"])
            print("股價淨值比：", row["pb_ratio"])
            print("殖利率：", row["dividend_yield"])
            print("股利年度：", row["dividend_year"])
            print("財報年/季：", row["financial_period"])
        # 輸出完整估值資料，方便檢查。
        output_file = (
            f"twse_valuation_{normalize_date(TEST_DATE)}.csv"
        )
        valuation_df.to_csv(
            output_file,
            index=False,
            encoding="utf-8-sig"
        )
        print("\n完整資料已輸出：", output_file)
    except Exception as exc:
        print("\n測試失敗：", exc)
        raise SystemExit(1)
