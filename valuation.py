import csv
import logging
import os
import tempfile
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

API_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d"

REQUEST_TIMEOUT = 30
MAX_LOOKBACK_DAYS = 20

LATEST_CSV = BASE_DIR / "twse_valuation_latest.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.twse.com.tw/",
}

CSV_COLUMNS = [
    "valuation_date",
    "stock_id",
    "stock_name",
    "close_price",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield",
    "dividend_year",
    "financial_period",
]


# ============================================================
# 2. 日期與數值處理
# ============================================================

def normalize_date(value):
    """將日期統一轉換成 YYYYMMDD。"""

    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")

    if isinstance(value, date):
        return value.strftime("%Y%m%d")

    text = str(value).strip()

    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m%d")
        except ValueError:
            continue

    raise ValueError(f"無法辨識日期格式：{value}")


def format_display_date(value):
    """將日期轉成 YYYY-MM-DD。"""

    return datetime.strptime(
        normalize_date(value), "%Y%m%d"
    ).strftime("%Y-%m-%d")


def to_number(value):
    """將數值欄位轉成 float；無有效數值時回傳 None。"""

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    text = str(value).strip().replace(",", "")

    if text.lower() in {
        "",
        "-",
        "--",
        "---",
        "nan",
        "none",
        "null",
        "n/a",
    }:
        return None

    try:
        number = float(text)
    except (TypeError, ValueError):
        return None

    if not pd.notna(number):
        return None

    return number


def clean_text(value):
    """清理文字欄位。"""

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip()


def normalize_stock_id(value):
    """統一股票代號格式，保留非純數字代號。"""

    stock_id = clean_text(value)

    if stock_id.isdigit():
        return stock_id.zfill(4)

    return stock_id


# ============================================================
# 3. 查詢證交所指定日期的估值資料
# ============================================================

@lru_cache(maxsize=30)
def fetch_twse_valuation(date_str):
    """
    查詢指定日期的 TWSE 估值資料。

    回傳：
        {
            "date": "YYYYMMDD",
            "data": DataFrame,
            "message": "說明"
        }

    注意：
    此函式只查詢指定日期，不會自行回溯。
    """

    date_str = normalize_date(date_str)

    params = {
        "date": date_str,
        "selectType": "ALL",
        "response": "json",
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            return {
                "date": date_str,
                "data": pd.DataFrame(),
                "message": "證交所回傳內容不是有效 JSON",
            }

        status = clean_text(payload.get("stat", ""))
        rows = payload.get("data", [])

        if status != "OK":
            message = clean_text(payload.get("stat", ""))
            return {
                "date": date_str,
                "data": pd.DataFrame(),
                "message": message or "證交所沒有提供該日期的資料",
            }

        if not isinstance(rows, list) or not rows:
            return {
                "date": date_str,
                "data": pd.DataFrame(),
                "message": "該日期沒有估值資料",
            }

        df = pd.DataFrame(rows)

        if df.empty:
            return {
                "date": date_str,
                "data": pd.DataFrame(),
                "message": "該日期沒有估值資料",
            }

        logging.info(
            "TWSE 估值資料取得成功：日期=%s，筆數=%s",
            date_str,
            len(df),
        )

        logging.info(
            "TWSE 欄位：%s",
            list(df.columns),
        )

        return {
            "date": date_str,
            "data": df,
            "message": "OK",
        }

    except requests.RequestException as exc:
        logging.warning(
            "查詢 TWSE 估值資料失敗，日期=%s，原因=%s",
            date_str,
            exc,
        )

        return {
            "date": date_str,
            "data": pd.DataFrame(),
            "message": f"TWSE 請求失敗：{exc}",
        }


# ============================================================
# 4. 欄位辨識與資料標準化
# ============================================================

def find_column(df, candidates):
    """依照候選名稱尋找 DataFrame 欄位。"""

    for candidate in candidates:
        if candidate in df.columns:
            return candidate

    return None


def prepare_valuation_data(df, valuation_date):
    """
    將證交所原始欄位轉成固定格式。

    不計算估值指標，只轉換原始資料。
    """

    if df is None or df.empty:
        return pd.DataFrame(columns=CSV_COLUMNS)

    stock_id_col = find_column(
        df,
        ["證券代號", "股票代號", "公司代號", "stock_id"],
    )

    if stock_id_col is None:
        raise ValueError(
            f"找不到股票代號欄位，實際欄位：{list(df.columns)}"
        )

    name_col = find_column(
        df,
        ["證券名稱", "股票名稱", "公司名稱", "stock_name"],
    )

    close_col = find_column(
        df,
        ["收盤價", "close_price"],
    )

    pe_col = find_column(
        df,
        ["本益比", "PE Ratio", "pe_ratio"],
    )

    pb_col = find_column(
        df,
        ["股價淨值比", "P/B Ratio", "pb_ratio"],
    )

    dividend_yield_col = find_column(
        df,
        ["殖利率(%)", "殖利率", "dividend_yield"],
    )

    dividend_year_col = find_column(
        df,
        ["股利年度", "dividend_year"],
    )

    financial_period_col = find_column(
        df,
        ["財報年/季", "財報年季", "financial_period"],
    )

    output_rows = []

    for _, row in df.iterrows():
        stock_id = normalize_stock_id(row.get(stock_id_col))

        if not stock_id:
            continue

        dividend_year = (
            clean_text(row.get(dividend_year_col))
            if dividend_year_col
            else ""
        )

        financial_period = (
            clean_text(row.get(financial_period_col))
            if financial_period_col
            else ""
        )

        output_rows.append({
            "valuation_date": format_display_date(valuation_date),
            "stock_id": stock_id,
            "stock_name": (
                clean_text(row.get(name_col))
                if name_col
                else ""
            ),
            "close_price": (
                to_number(row.get(close_col))
                if close_col
                else None
            ),
            "pe_ratio": (
                to_number(row.get(pe_col))
                if pe_col
                else None
            ),
            "pb_ratio": (
                to_number(row.get(pb_col))
                if pb_col
                else None
            ),
            "dividend_yield": (
                to_number(row.get(dividend_yield_col))
                if dividend_yield_col
                else None
            ),
            "dividend_year": dividend_year,
            "financial_period": financial_period,
        })

    result = pd.DataFrame(output_rows, columns=CSV_COLUMNS)

    if result.empty:
        raise ValueError("標準化後沒有任何有效股票資料")

    result = result.drop_duplicates(
        subset=["stock_id"],
        keep="last",
    )

    return result


# ============================================================
# 5. 尋找最近一個有估值資料的日期
# ============================================================

def find_latest_valuation_data(start_date=None):
    """
    從指定日期或台灣當日開始往前查詢。

    只有在 API 回傳有效資料，且資料成功標準化後，
    才會將該日期視為可用估值日期。

    注意：
    這裡依據 API 是否有資料來判斷，不使用自行推算的交易日曆。
    """

    if start_date is None:
        start_date = datetime.now(
            ZoneInfo("Asia/Taipei")
        ).date()

    if isinstance(start_date, str):
        start_date = datetime.strptime(
            normalize_date(start_date),
            "%Y%m%d",
        ).date()

    last_message = "查無有效估值資料"

    for offset in range(MAX_LOOKBACK_DAYS + 1):
        query_date = start_date - timedelta(days=offset)
        date_str = query_date.strftime("%Y%m%d")

        logging.info(
            "查詢 TWSE 個股估值資料：%s",
            date_str,
        )

        response = fetch_twse_valuation(date_str)
        raw_df = response["data"]

        if raw_df is None or raw_df.empty:
            last_message = response.get(
                "message",
                "該日期沒有估值資料",
            )
            continue

        try:
            prepared_df = prepare_valuation_data(
                raw_df,
                date_str,
            )
        except Exception as exc:
            last_message = str(exc)

            logging.warning(
                "估值資料格式驗證失敗，日期=%s，原因=%s",
                date_str,
                exc,
            )
            continue

        if prepared_df.empty:
            last_message = "標準化後沒有有效股票資料"
            continue

        logging.info(
            "找到最近有效估值資料：日期=%s，筆數=%s",
            date_str,
            len(prepared_df),
        )

        return date_str, prepared_df

    raise RuntimeError(
        f"往前查詢 {MAX_LOOKBACK_DAYS} 天仍找不到有效估值資料。"
        f"最後訊息：{last_message}"
    )


# ============================================================
# 6. 安全寫入 CSV
# ============================================================

def write_csv_atomic(df, output_path):
    """
    先寫入暫存檔，再以 os.replace 原子替換正式檔案。
    寫入失敗時，不覆蓋既有正式檔案。
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            suffix=".tmp",
            prefix=f"{output_path.stem}_",
            dir=output_path.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)

            df.to_csv(
                temp_file,
                index=False,
                quoting=csv.QUOTE_MINIMAL,
                na_rep="",
                lineterminator="\n",
            )

            temp_file.flush()
            os.fsync(temp_file.fileno())

        # 寫入後重新讀取，確認 CSV 可以正常解析。
        verified_df = pd.read_csv(
            temp_path,
            dtype={"stock_id": str},
            encoding="utf-8-sig",
        )

        if verified_df.empty:
            raise ValueError("CSV 驗證失敗：檔案沒有資料")

        for column in CSV_COLUMNS:
            if column not in verified_df.columns:
                raise ValueError(
                    f"CSV 驗證失敗：缺少欄位 {column}"
                )

        os.replace(temp_path, output_path)
        temp_path = None

        logging.info(
            "CSV 寫入完成：%s，筆數=%s",
            output_path.name,
            len(verified_df),
        )

    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                logging.warning(
                    "無法清除暫存檔：%s",
                    temp_path,
                )


# ============================================================
# 7. 每日更新 CSV
# ============================================================

def update_valuation_csv():
    """
    取得最近有資料的日期，並產生：
      1. twse_valuation_YYYYMMDD.csv
      2. twse_valuation_latest.csv

    只有取得並驗證有效資料後才更新正式檔案。
    """

    logging.info("=" * 60)
    logging.info("開始更新 TWSE 個股估值 CSV")

    valuation_date, df = find_latest_valuation_data()

    dated_csv = BASE_DIR / (
        f"twse_valuation_{valuation_date}.csv"
    )

    # 先產生日期檔，再更新固定名稱檔案。
    write_csv_atomic(df, dated_csv)
    write_csv_atomic(df, LATEST_CSV)

    logging.info(
        "估值資料日期：%s",
        format_display_date(valuation_date),
    )
    logging.info(
        "估值股票筆數：%s",
        len(df),
    )
    logging.info(
        "日期 CSV：%s",
        dated_csv.name,
    )
    logging.info(
        "最新 CSV：%s",
        LATEST_CSV.name,
    )
    logging.info("TWSE 個股估值 CSV 更新完成")
    logging.info("=" * 60)

    return {
        "valuation_date": format_display_date(valuation_date),
        "stock_count": len(df),
        "dated_csv": str(dated_csv),
        "latest_csv": str(LATEST_CSV),
    }


# ============================================================
# 8. 保留原有單檔查詢介面
# ============================================================

def analyze_valuation(stock_id, date_value):
    """
    保留原本的函式介面，供舊程式相容使用。

    注意：
    本函式仍會直接查詢指定日期的 TWSE API。
    下一階段整合 analyzer.py 時，應改為讀取 CSV，
    不再逐檔呼叫這個函式。
    """

    stock_id = normalize_stock_id(stock_id)
    date_str = normalize_date(date_value)

    response = fetch_twse_valuation(date_str)
    raw_df = response["data"]

    if raw_df is None or raw_df.empty:
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
            "message": response.get("message", "查無估值資料"),
        }

    prepared_df = prepare_valuation_data(
        raw_df,
        date_str,
    )

    matched = prepared_df[
        prepared_df["stock_id"] == stock_id
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

    def nullable(value):
        try:
            return None if pd.isna(value) else value
        except (TypeError, ValueError):
            return value

    return {
        "stock_id": stock_id,
        "valuation_date": row["valuation_date"],
        "stock_name": nullable(row["stock_name"]),
        "close_price": nullable(row["close_price"]),
        "pe_ratio": nullable(row["pe_ratio"]),
        "pb_ratio": nullable(row["pb_ratio"]),
        "dividend_yield": nullable(row["dividend_yield"]),
        "dividend_year": nullable(row["dividend_year"]),
        "financial_period": nullable(row["financial_period"]),
        "data_available": True,
        "message": "OK",
    }


# ============================================================
# 9. 程式進入點
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    update_valuation_csv()
