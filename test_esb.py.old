import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


# ============================================================
# 興櫃歷史行情獨立測試
# ============================================================

STOCK_ID = "6750"

BASE_URL = (
    "https://www.tpex.org.tw/zh-tw/esb/trading/info/stock-pricing.html"
)

OUTPUT_FILE = Path(__file__).resolve().parent / "esb_6750_response.txt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,*/*",
    "Referer": "https://www.tpex.org.tw/",
}

TIMEOUT = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


def main():

    now = datetime.now(
        ZoneInfo("Asia/Taipei")
    )

    roc_year = now.year - 1911

    # 興櫃歷史行情查詢年月
    query_date = (
        f"{roc_year}/{now.month:02d}/01"
    )

    params = {
        "code": STOCK_ID,
        "date": query_date,
        "id": "",
        "response": "json",
        "type": "Daily",
    }

    print("=" * 70)
    print("櫃買中心興櫃個股歷史行情測試")
    print("=" * 70)
    print(f"股票代號：{STOCK_ID}")
    print(f"查詢年月：{query_date}")
    print(f"查詢類型：Daily")
    print(f"查詢網址：{BASE_URL}")
    print()

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        response = session.get(
            BASE_URL,
            params=params,
            timeout=TIMEOUT,
        )

        print("HTTP Status：", response.status_code)
        print("Content-Type：", response.headers.get("Content-Type"))
        print("實際請求網址：", response.url)
        print()

        response.raise_for_status()

        text = response.text

        # 儲存原始回應，方便檢查
        OUTPUT_FILE.write_text(
            text,
            encoding="utf-8",
        )

        print("原始回應已儲存：", OUTPUT_FILE)
        print()

        # ----------------------------------------------------
        # 嘗試解析 JSON
        # ----------------------------------------------------

        try:
            result = response.json()

        except ValueError:
            print("回應不是標準 JSON。")
            print("以下為 HTML / 文字回應前 5000 字：")
            print("-" * 70)
            print(text[:5000])
            print("-" * 70)
            return

        print("JSON 解析成功")
        print("回傳資料型態：", type(result).__name__)
        print()

        if isinstance(result, dict):

            print("JSON 第一層欄位：")
            for key, value in result.items():

                if isinstance(value, list):
                    print(
                        f"  {key}: list，筆數={len(value)}"
                    )

                elif isinstance(value, dict):
                    print(
                        f"  {key}: dict，"
                        f"欄位={list(value.keys())}"
                    )

                else:
                    print(f"  {key}: {value}")

            print()

            # 常見欄位結構檢查
            if "fields" in result:
                print("fields：")
                print(json.dumps(
                    result["fields"],
                    ensure_ascii=False,
                    indent=2,
                ))

            if "data" in result:
                print()
                print("data 筆數：", len(result["data"]))
                print("data 前 3 筆：")
                print(json.dumps(
                    result["data"][:3],
                    ensure_ascii=False,
                    indent=2,
                ))

            if "tables" in result:
                print()
                print("tables 結構：")
                print(json.dumps(
                    result["tables"],
                    ensure_ascii=False,
                    indent=2,
                )[:10000])

        elif isinstance(result, list):

            print("JSON 是陣列")
            print("資料筆數：", len(result))
            print("前 3 筆：")
            print(json.dumps(
                result[:3],
                ensure_ascii=False,
                indent=2,
            ))

        else:
            print("JSON 內容：")
            print(json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )[:10000])

        print()
        print("=" * 70)
        print("興櫃 API 診斷完成")
        print("=" * 70)

    except Exception as exc:

        logger.exception(
            "興櫃行情測試失敗：%s",
            exc,
        )


if __name__ == "__main__":
    main()
