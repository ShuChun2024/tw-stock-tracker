import datetime
import logging
import re
from functools import lru_cache
from pathlib import Path
import pandas as pd
import requests
# ============================================================
# 1. 基本設定
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
BASE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d"
REQUEST_TIMEOUT = 30
MAX_LOOKBACK_DAYS = 20
LATEST_OUTPUT_FILE = BASE_DIR / "twse_valuation_latest.csv"
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
    if re.fullmatch(r"\d{8}", value):
        return value
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
    """YYYYMMDD -> YYYY-MM-DD"""
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
    例如：115/2 -> 2026/2
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
    無效值回傳 None。
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).strip()
    if not text:
        return None
    if text in {
        "-", "—", "－", "N/A", "NA", "null", "None"
    }:
        return None
    text = text.replace(",", "")
    try:
        number = float(text)
        if pd.isna(number):
            return None
        if number.is_integer():
            return int(number)
        return number
    except (TypeError, ValueError):
        return None
# ============================================================
# 6. 欄位名稱尋找
# ============================================================
def find_column(df, candidates):
    """從 DataFrame 中尋找第一個符合的欄位名稱。"""
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None
# ============================================================
# 7. TWSE API 查詢
# ============================================================
@lru_cache(maxsize=20)
def fetch_twse_valuation(date_str):
    """
    查詢 TWSE 個股估值資料。
    修正重點：
    TWSE JSON 的 fields 與 data 是分開回傳的，
    必須使用 pd.DataFrame(data, columns=fields)。
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
        message = f"HTTP 請求失敗：{exc}"
        logger.error("TWSE API 請求失敗：%s", exc)
        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": message,
        }
    try:
        result = response.json()
    except ValueError as exc:
        message = f"JSON 解析失敗：{exc}"
        logger.error(
            "TWSE API 回傳不是有效 JSON：%s",
            exc,
        )
        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": message,
        }
    if not isinstance(result, dict):
        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": "API 回傳格式不是 JSON 物件",
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
    if not isinstance(fields, list) or not fields:
        message = "API 沒有回傳有效欄位 fields"
        logger.warning("%s：%s", date_str, message)
        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": message,
        }
    if not isinstance(data, list) or not data:
        message = "該日期沒有估值資料"
        logger.warning(
            "TWSE API 沒有回傳資料：%s",
            date_str,
        )
        return {
            "date": date_str,
            "data": pd.DataFrame(columns=fields),
            "message": message,
        }
    # --------------------------------------------------------
    # 修正核心：正確建立 DataFrame
    # --------------------------------------------------------
    try:
        if isinstance(data[0], dict):
            # 相容 API 回傳字典陣列的格式
            df = pd.DataFrame(data)
        elif isinstance(data[0], (list, tuple)):
            # TWSE RWD 常見格式：
            # fields = ["證券代號", "證券名稱", ...]
            # data = [["2330", "台積電", ...], ...]
            for index, row in enumerate(data):
                if not isinstance(row, (list, tuple)):
                    raise ValueError(
                        f"第 {index + 1} 筆資料格式錯誤"
                    )
                if len(row) != len(fields):
                    raise ValueError(
                        f"第 {index + 1} 筆資料欄位數 "
                        f"{len(row)} 與 fields 欄位數 "
                        f"{len(fields)} 不一致"
                    )
            df = pd.DataFrame(
                data,
                columns=fields,
            )
        else:
            raise ValueError(
                f"不支援的 data 資料格式：{type(data).__name__}"
            )
    except Exception as exc:
        message = f"建立估值 DataFrame 失敗：{exc}"
        logger.error("%s", message)
        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": message,
        }
    logger.info(
        "TWSE API 實際欄位：%s",
        list(df.columns),
    )
    # --------------------------------------------------------
    # 確認股票代號欄位存在
    # --------------------------------------------------------
    stock_id_col = find_column(
        df,
        [
            "證券代號",
            "股票代號",
            "代號",
            "公司代號",
            "stock_id",
        ],
    )
    if stock_id_col is None:
        message = (
            "找不到股票代號欄位，實際欄位："
            f"{list(df.columns)}"
        )
        logger.error("%s", message)
        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": message,
        }
    if df.empty:
        return {
            "date": date_str,
            "data": df,
            "message": "該日期沒有估值資料",
        }
    logger.info(
        "TWSE 估值資料取得成功：日期=%s，筆數=%d",
        date_str,
        len(df),
    )
    return {
        "date": date_str,
        "data": df,
        "message": "",
    }
# ============================================================
# 8. 整理 TWSE 估值資料
# ============================================================
def prepare_valuation_data(df):
    """
    將 TWSE 原始資料轉成統一格式。
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
    output_columns = [
        "stock_id",
        "stock_name",
        "close_price",
        "pe_ratio",
        "pb_ratio",
        "dividend_yield",
        "dividend_year",
        "financial_period",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=output_columns)
    stock_id_col = find_column(
        df,
        [
            "證券代號",
            "股票代號",
            "代號",
            "公司代號",
            "stock_id",
        ],
    )
    stock_name_col = find_column(
        df,
        [
            "證券名稱",
            "股票名稱",
            "名稱",
            "stock_name",
        ],
    )
    close_price_col = find_column(df, ["收盤價", "close_price"])
    dividend_yield_col = find_column(
        df,
        ["殖利率(%)", "殖利率", "dividend_yield"],
    )
    dividend_year_col = find_column(
        df,
        ["股利年度", "dividend_year"],
    )
    pe_ratio_col = find_column(
        df,
        ["本益比", "pe_ratio"],
    )
    pb_ratio_col = find_column(
        df,
        ["股價淨值比", "市淨率", "pb_ratio"],
    )
    financial_period_col = find_column(
        df,
        ["財報年/季", "財報年季", "financial_period"],
    )
    if stock_id_col is None:
        raise ValueError("找不到股票代號欄位")
    result = pd.DataFrame()
    result["stock_id"] = (
        df[stock_id_col]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
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
    numeric_columns = {
        "close_price": close_price_col,
        "pe_ratio": pe_ratio_col,
        "pb_ratio": pb_ratio_col,
        "dividend_yield": dividend_yield_col,
        "dividend_year": dividend_year_col,
    }
    for output_name, source_col in numeric_columns.items():
        if source_col:
            result[output_name] = df[source_col].apply(to_number)
        else:
            result[output_name] = None
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
    return result[output_columns]
# ============================================================
# 9. 查詢單一股票估值
# ============================================================
def analyze_valuation(stock_id, date_value):
    """查詢指定股票在指定日期的估值資料。"""
    stock_id = str(stock_id).strip().zfill(4)
    date_str = normalize_date(date_value)
    fetched = fetch_twse_valuation(date_str)
    empty_result = {
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
    if fetched["data"].empty:
        return empty_result
    valuation_df = prepare_valuation_data(
        fetched["data"]
    )
    matched = valuation_df[
        valuation_df["stock_id"] == stock_id
    ]
    if matched.empty:
        empty_result["message"] = "查無該股票估值資料"
        return empty_result
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
# 10. 自動尋找最近有效估值交易日
# ============================================================
def find_latest_valuation_data(start_date=None):
    """
    從指定日期開始往前查詢，直到找到有效估值資料。
    預設從今天開始，最多往前查詢 20 個日曆日。
    回傳：
    {
        "date": "YYYYMMDD",
        "data": 標準化 DataFrame,
        "message": ""
    }
    """
    if start_date is None:
        start_date = datetime.date.today()
    current_date = datetime.datetime.strptime(
        normalize_date(start_date),
        "%Y%m%d",
    ).date()
    last_message = "尚未查詢"
    for offset in range(MAX_LOOKBACK_DAYS + 1):
        query_date = current_date - datetime.timedelta(
            days=offset
        )
        date_str = query_date.strftime("%Y%m%d")
        logger.info(
            "尋找最新估值資料：日期=%s，回溯第 %d 天",
            date_str,
            offset,
        )
        fetched = fetch_twse_valuation(date_str)
        if fetched["data"].empty:
            last_message = fetched["message"]
            continue
        try:
            valuation_df = prepare_valuation_data(
                fetched["data"]
            )
        except Exception as exc:
            last_message = str(exc)
            logger.warning(
                "整理估值資料失敗：日期=%s，原因=%s",
                date_str,
                exc,
            )
            continue
        if valuation_df.empty:
            last_message = "標準化後沒有估值資料"
            continue
        if valuation_df["stock_id"].isna().all():
            last_message = "沒有有效股票代號"
            continue
        logger.info(
            "找到最近有效估值資料：日期=%s，筆數=%d",
            date_str,
            len(valuation_df),
        )
        return {
            "date": date_str,
            "data": valuation_df,
            "message": "",
        }
    message = (
        f"往前查詢 {MAX_LOOKBACK_DAYS} 天仍找不到有效估值資料。"
        f"最後訊息：{last_message}"
    )
    logger.error("%s", message)
    return {
        "date": None,
        "data": pd.DataFrame(),
        "message": message,
    }
# ============================================================
# 11. 輸出日期 CSV 與 latest CSV
# ============================================================
def update_valuation_csv(start_date=None):
    """
    找出最近有效交易日並輸出兩份 CSV：
    1. twse_valuation_YYYYMMDD.csv
    2. twse_valuation_latest.csv
    latest 檔案只會在成功取得新資料後更新。
    """
    latest = find_latest_valuation_data(start_date)
    if latest["data"].empty:
        raise RuntimeError(latest["message"])
    date_str = latest["date"]
    valuation_df = latest["data"].copy()

    # 加入估值資料日期，供後續 analyzer.py 使用
    valuation_df.insert(
        0,
        "valuation_date",
        format_display_date(date_str),
    )

    dated_file = BASE_DIR / f"twse_valuation_{date_str}.csv"  
    # 先寫入暫存檔，避免中途失敗留下不完整 CSV
    dated_temp = dated_file.with_suffix(".csv.tmp")
    latest_temp = LATEST_OUTPUT_FILE.with_suffix(".csv.tmp")
    try:
        valuation_df.to_csv(
            dated_temp,
            index=False,
            encoding="utf-8-sig",
            na_rep="",
        )
        valuation_df.to_csv(
            latest_temp,
            index=False,
            encoding="utf-8-sig",
            na_rep="",
        )
        # 暫存檔完整寫入後再替換正式檔案
        dated_temp.replace(dated_file)
        latest_temp.replace(LATEST_OUTPUT_FILE)
    finally:
        # 若寫檔失敗，清除可能留下的暫存檔
        for temp_file in (dated_temp, latest_temp):
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
    logger.info("估值資料日期：%s", format_display_date(date_str))
    logger.info("日期檔案：%s", dated_file)
    logger.info("最新檔案：%s", LATEST_OUTPUT_FILE)
    logger.info("估值資料筆數：%d", len(valuation_df))
    return {
        "date": date_str,
        "data": valuation_df,
        "dated_file": dated_file,
        "latest_file": LATEST_OUTPUT_FILE,
        "message": "",
    }
# ============================================================
# 12. 主程式：自動更新 CSV
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("TWSE 個股估值資料更新")
    print("=" * 70)
    result = update_valuation_csv()
    valuation_df = result["data"]
    date_str = result["date"]
    print()
    print("資料日期：", format_display_date(date_str))
    print("資料筆數：", len(valuation_df))
    print("日期 CSV：", result["dated_file"])
    print("最新 CSV：", result["latest_file"])
    # --------------------------------------------------------
    # 保留原本四檔股票的測試
    # 注意：此處使用已經下載並整理好的資料，不再逐檔呼叫 API。
    # --------------------------------------------------------
    TEST_STOCKS = [
        "1101",
        "1102",
        "2330",
        "2454",
    ]
    print()
    print("=" * 70)
    print("指定股票估值測試")
    print("=" * 70)
    for stock_id in TEST_STOCKS:
        matched = valuation_df[
            valuation_df["stock_id"] == str(stock_id).zfill(4)
        ]
        print()
        print("-" * 50)
        print("股票代號：", str(stock_id).zfill(4))
        if matched.empty:
            print("資料狀態：查無該股票估值資料")
            continue
        row = matched.iloc[0]
        print("股票名稱：", row["stock_name"])
        print("收盤價：", row["close_price"])
        print("本益比：", row["pe_ratio"])
        print("股價淨值比：", row["pb_ratio"])
        print("殖利率：", row["dividend_yield"])
        print("股利年度：", row["dividend_year"])
        print("財報年/季：", row["financial_period"])
    print()
    print("=" * 70)
    print("估值 CSV 更新完成")
    print("=" * 70)
