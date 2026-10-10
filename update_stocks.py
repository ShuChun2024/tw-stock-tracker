# update_stocks.py

import json
import os
import sys
import time
from datetime import datetime

import requests


# ============================================================
# 設定
# ============================================================

OUTPUT_FILE = "stocks.json"

TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

TPEX_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"

TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
}


# ============================================================
# 基本工具
# ============================================================

def clean_text(value):
    """清除前後空白與特殊空白字元"""

    if value is None:
        return ""

    value = str(value)

    value = value.replace("\u3000", " ")
    value = value.replace("\xa0", " ")

    return value.strip()


def clean_stock_id(value):
    """股票代碼統一格式"""

    value = clean_text(value)

    if not value:
        return ""

    # 有些資料可能出現 2330.0
    if value.endswith(".0"):
        value = value[:-2]

    return value


# ============================================================
# HTTP
# ============================================================

def get_json(url):
    """取得 JSON API"""

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

        stock_id = clean_stock_id(
            row.get("公司代號", "")
        )

        short_name = clean_text(
            row.get("公司簡稱", "")
        )

        company_name = clean_text(
            row.get("公司名稱", "")
        )

        if not stock_id:
            continue

        # 只保留一般股票代碼
        if not stock_id.isdigit():
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
            stock_id = clean_stock_id(
                row.get("公司代號", "")
            )

        if not short_name:
            short_name = clean_text(
                row.get("公司簡稱", "")
            )

        if not company_name:
            company_name = clean_text(
                row.get("公司名稱", "")
            )

        if not stock_id:
            continue

        if not stock_id.isdigit():
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

    # 依股票代碼排序
    all_stocks.sort(
        key=lambda x: x["stock_id"]
    )

    # 去除重複
    result = []
    seen = set()

    for stock in all_stocks:

        stock_id = stock["stock_id"]

        if stock_id in seen:
            continue

        seen.add(stock_id)

        result.append(stock)

    return result


# ============================================================
# 儲存
# ============================================================

def save_stocks(stocks):

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    output = {
        "update_time": now,
        "stock_count": len(stocks),
        "stocks": stocks
    }

    temp_file = OUTPUT_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

        f.write("\n")

    os.replace(
        temp_file,
        OUTPUT_FILE
    )

    print()
    print("=" * 60)
    print("stocks.json 更新完成")
    print("=" * 60)
    print(f"更新時間：{now}")
    print(f"股票數量：{len(stocks)}")
    print(f"檔案：{OUTPUT_FILE}")


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("==========================================")
    print(" 股票名稱資料更新程式")
    print("==========================================")

    old_exists = os.path.exists(
        OUTPUT_FILE
    )

    try:

        twse_data = fetch_twse()

        # 稍微停一下，避免兩個 API 連續請求太快
        time.sleep(1)

        tpex_data = fetch_tpex()

        # 防止 API 回傳空資料造成舊資料被清空
        if len(twse_data) < 500:
            raise ValueError(
                f"TWSE 資料異常，目前只有 {len(twse_data)} 筆"
            )

        if len(tpex_data) < 300:
            raise ValueError(
                f"TPEx 資料異常，目前只有 {len(tpex_data)} 筆"
            )

        stocks = normalize_stocks(
            twse_data,
            tpex_data
        )

        if len(stocks) < 800:
            raise ValueError(
                f"股票總數異常，目前只有 {len(stocks)} 筆"
            )

        save_stocks(stocks)

        return 0

    except Exception as e:

        print()
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("股票名稱資料更新失敗")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"錯誤：{e}")

        if old_exists:
            print(
                "stocks.json 已存在，保留原本資料，不覆蓋。"
            )
        else:
            print(
                "stocks.json 不存在，因此無法提供股票名稱資料。"
            )

        # 不讓股票名稱 API 失敗直接讓整個分析流程失敗
        return 0


if __name__ == "__main__":
    sys.exit(main())
