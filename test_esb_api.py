import json
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

API_URL = (
    "https://www.tpex.org.tw/"
    "www/zh-tw/emerging/historical"
)

PAGE_URL = (
    "https://www.tpex.org.tw/"
    "zh-tw/esb/trading/info/stock-pricing.html"
)

# 先測試 6750，日期使用民國年月格式
PARAMS = {
    "type": "Monthly",
    "date": "115/11",
    "code": "6750",
    "id": "",
    "response": "json",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    ),
    "Referer": PAGE_URL,
    "Origin": "https://www.tpex.org.tw",
    "X-Requested-With": "XMLHttpRequest",
}

def main():
    print("=" * 65)
    print("櫃買中心興櫃行情 API POST 測試")
    print("股票：6750 泰創工程")
    print("=" * 65)

    session = requests.Session()

    # 先取得頁面，建立可能需要的 Cookie
    try:
        page = session.get(
            PAGE_URL,
            headers=HEADERS,
            timeout=30,
        )
        print("頁面 HTTP：", page.status_code)
        print("Cookie：", session.cookies.get_dict())
    except Exception as exc:
        print("頁面連線警告：", exc)

    print("\n開始 POST API...")
    print("API：", API_URL)
    print("參數：", PARAMS)

    response = session.post(
        API_URL,
        data=PARAMS,
        headers=HEADERS,
        timeout=30,
    )

    print("\nHTTP Status：", response.status_code)
    print("Content-Type：", response.headers.get("Content-Type"))
    print("Response Length：", len(response.content))

    response.raise_for_status()
    response.encoding = "utf-8"

    raw_text = response.text

    # 保存原始回應
    raw_file = BASE_DIR / "esb_6750_api_raw.txt"
    raw_file.write_text(raw_text, encoding="utf-8")

    print("\n原始回應已保存：esb_6750_api_raw.txt")
    print("\n回應前 2000 字元：")
    print(raw_text[:2000])

    try:
        data = response.json()

        json_file = BASE_DIR / "esb_6750_api_result.json"

        json_file.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print("\nJSON 解析成功")
        print("JSON 已保存：esb_6750_api_result.json")

        print("\n頂層欄位：")

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    print(
                        f"{key}: list，筆數={len(value)}"
                    )
                elif isinstance(value, dict):
                    print(
                        f"{key}: dict，欄位={list(value.keys())}"
                    )
                else:
                    print(f"{key}: {value}")

        print("\n完整 JSON：")
        print(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )[:10000]
        )

    except ValueError:
        print("\nJSON 解析失敗")
        print("實際回應不是有效 JSON")

    print("\n測試完成")


if __name__ == "__main__":
    main()
