import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


# ============================================================
# 設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "stocks.json"
TIMEOUT = 30

TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
}


# ============================================================
# 基本工具
# ============================================================

def clean_text(value):
    """清除前後空白與特殊空白字元。"""
    if value is None:
        return ""

    value = str(value)
    value = value.replace("\u3000", " ")
    value = value.replace("\xa0", " ")

    return value.strip()


def clean_stock_id(value):
    """股票代碼統一格式。"""
    value = clean_text(value)

    if not value:
        return ""

    # 有些資料可能出現 2330.0
    if value.endswith(".0"):
        value = value[:-2]

    return value


def validate_stock_data(data):
    """驗證 stocks.json 的基本結構與股票資料。"""

    if not isinstance(data, dict):
        raise ValueError("stocks.json 根節點不是 JSON 物件")

    stocks = data.get("stocks")

    if not isinstance(stocks, list):
        raise ValueError("stocks.json 缺少有效的 stocks 陣列")

    if len(stocks) < 800:
        raise ValueError(
            f"stocks.json 股票數量異常：{len(stocks)}"
        )

    valid_count = 0
    seen = set()

    for stock in stocks:
        if not isinstance(stock, dict):
            continue

        stock_id = clean_stock_id(stock.get("stock_id", ""))

        if not stock_id.isdigit():
            continue

        if not stock.get("short_name") and not stock.get("company_name"):
            continue

        if stock_id in seen:
            raise ValueError(f"stocks.json 有重複股票代碼：{stock_id}")

        seen.add(stock_id)
        valid_count += 1

    if valid_count < 800:
        raise ValueError(
            f"stocks.json 有效股票資料不足：{valid_count}"
        )

    return True


def has_valid_existing_file():
    """檢查既有 stocks.json 是否可用。"""

    if not OUTPUT_FILE.exists():
        print("找不到既有 stocks.json。")
        return False

    try:
        with OUTPUT_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        validate_stock_data(data)

        print(
            f"既有 stocks.json 可用，共 {len(data['stocks'])} 筆。"
        )
        return True

    except Exception as e:
        print(f"既有 stocks.json 無法通過驗證：{e}")
        return False


# ============================================================
# HTTP
# ============================================================

def get_json(url):
    """取得並驗證 API 回傳的 JSON 陣列。"""

    print(f"取得資料：{url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError("API 回傳格式不是 JSON 陣列")

    return data


# ============================================================
# TWSE 上市公司
# ============================================================

def fetch_twse():
    print()
    print("=" * 60)
    print("取得 TWSE 上市公司資料")
    print("=" * 60)

    data = get_json(TWSE_URL)
    result = []

    for row in data:
        if not isinstance(row, dict):
            continue

        stock_id = clean_stock_id(row.get("公司代號", ""))
        short_name = clean_text(row.get("公司簡稱", ""))
        company_name = clean_text(row.get("公司名稱", ""))

        if not stock_id or not stock_id.isdigit():
            continue

        if not short_name and not company_name:
            continue

        result.append({
            "stock_id": stock_id,
            "short_name": short_name,
            "company_name": company_name,
            "market": "TWSE"
        })

    print(f"TWSE：取得 {len(result)} 筆")

    return result


# ============================================================
# TPEx 上櫃公司
# ============================================================

def fetch_tpex():
    print()
    print("=" * 60)
    print("取得 TPEx 上櫃公司資料")
    print("=" * 60)

    data = get_json(TPEX_URL)
    result = []

    for row in data:
        if not isinstance(row, dict):
            continue

        # TPEx API 使用英文欄位
        stock_id = clean_stock_id(
            row.get("SecuritiesCompanyCode", "")
        )

        short_name = clean_text(
            row.get("CompanyAbbreviation", "")
        )

        company_name = clean_text(
            row.get("CompanyName", "")
        )

        # 某些版本可能使用中文欄位
        if not stock_id:
            stock_id = clean_stock_id(row.get("公司代號", ""))

        if not short_name:
            short_name = clean_text(row.get("公司簡稱", ""))

        if not company_name:
            company_name = clean_text(row.get("公司名稱", ""))

        if not stock_id or not stock_id.isdigit():
            continue

        if not short_name and not company_name:
            continue

        result.append({
            "stock_id": stock_id,
            "short_name": short_name,
            "company_name": company_name,
            "market": "TPEx"
        })

    print(f"TPEx：取得 {len(result)} 筆")

    return result


# ============================================================
# 整理資料
# ============================================================

def normalize_stocks(twse_data, tpex_data):
    all_stocks = []
    all_stocks.extend(twse_data)
    all_stocks.extend(tpex_data)

    all_stocks.sort(key=lambda x: x["stock_id"])

    result = []
    seen = set()

    for stock in all_stocks:
        stock_id = stock["stock_id"]

        if stock_id in seen:
            print(f"注意：發現重複股票代碼 {stock_id}，保留第一筆。")
            continue

        seen.add(stock_id)
        result.append(stock)

    return result


# ============================================================
# 儲存
# ============================================================

def save_stocks(stocks):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    output = {
        "update_time": now,
        "stock_count": len(stocks),
        "stocks": stocks
    }

    temp_file = OUTPUT_FILE.with_name(
        OUTPUT_FILE.name + ".tmp"
    )

    try:
        # 先寫入暫存檔
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(
                output,
                f,
                ensure_ascii=False,
                indent=2,
                allow_nan=False
            )
            f.write("\n")

        # 驗證暫存檔
        with temp_file.open("r", encoding="utf-8") as f:
            verified = json.load(f)

        validate_stock_data(verified)

        if verified.get("stock_count") != len(verified["stocks"]):
            raise ValueError("stock_count 與 stocks 陣列數量不一致")

        # 驗證通過後才替換正式檔案
        os.replace(temp_file, OUTPUT_FILE)

        print()
        print("=" * 60)
        print("stocks.json 更新完成")
        print("=" * 60)
        print(f"更新時間：{now}")
        print(f"股票數量：{len(stocks)}")
        print(f"檔案：{OUTPUT_FILE}")

    except Exception:
        try:
            if temp_file.exists():
                temp_file.unlink()
        except OSError:
            print("警告：無法清除暫存檔。")

        raise


# ============================================================
# 主程式
# ============================================================

def main():
    print()
    print("==========================================")
    print(" 股票名稱資料更新程式")
    print("==========================================")

    old_file_valid = has_valid_existing_file()

    try:
        twse_data = fetch_twse()

        # 避免兩個 API 連續請求太快
        time.sleep(1)

        tpex_data = fetch_tpex()

        # 防止 API 回傳異常資料
        if len(twse_data) < 500:
            raise ValueError(
                f"TWSE 資料異常，目前只有 {len(twse_data)} 筆"
            )

        if len(tpex_data) < 300:
            raise ValueError(
                f"TPEx 資料異常，目前只有 {len(tpex_data)} 筆"
            )

        stocks = normalize_stocks(twse_data, tpex_data)

        if len(stocks) < 800:
            raise ValueError(
                f"股票總數異常，目前只有 {len(stocks)} 筆"
            )

        save_stocks(stocks)

        return 0

    except Exception as e:
        print()
        print("!" * 50)
        print("股票名稱資料更新失敗")
        print("!" * 50)
        print(f"錯誤：{e}")

        if old_file_valid:
            print("既有 stocks.json 已通過驗證，保留原檔。")
        else:
            print("沒有可確認有效的既有 stocks.json。")

        # 關鍵修正：更新失敗回傳非零狀態碼
        return 1


if __name__ == "__main__":
    sys.exit(main())
