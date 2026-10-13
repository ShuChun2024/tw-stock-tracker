import requests
import json
from collections import Counter


# ============================================================
# TWSE OpenAPI 測試
# API：上市公司每日重大訊息
# ============================================================

URL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"

STOCKS = {
    "1101": "台泥",
    "2330": "台積電",
    "2454": "聯發科",
    "2317": "鴻海",
}

TIMEOUT = 30


# ============================================================
# 日期格式
# ============================================================

def roc_to_date(value):
    """
    民國日期：
    1151013 -> 2026-10-13
    """

    value = str(value).strip()

    if len(value) != 7 or not value.isdigit():
        return value

    try:
        year = int(value[:3]) + 1911
        month = value[3:5]
        day = value[5:7]

        return f"{year}-{month}-{day}"

    except Exception:
        return value


# ============================================================
# 時間格式
# ============================================================

def format_time(value):
    """
    例如：
    70003 -> 07:00:03
    93015 -> 09:30:15
    """

    value = str(value).strip()

    if not value.isdigit():
        return value

    value = value.zfill(6)

    return (
        value[:2]
        + ":"
        + value[2:4]
        + ":"
        + value[4:6]
    )


# ============================================================
# 主程式
# ============================================================

def main():

    print("=" * 80)
    print("TWSE OpenAPI｜上市公司每日重大訊息")
    print("=" * 80)

    print()
    print("API：")
    print(URL)

    print()
    print("測試股票：")

    for code, name in STOCKS.items():
        print(f"  {code} {name}")

    print()
    print("開始取得資料...")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            URL,
            headers=headers,
            timeout=TIMEOUT,
        )

    except Exception as e:
        print()
        print("API 連線失敗：")
        print(repr(e))
        return

    # ========================================================
    # HTTP 基本資訊
    # ========================================================

    print()
    print("-" * 80)
    print("HTTP 測試")
    print("-" * 80)

    print("HTTP Status:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))
    print("資料長度:", len(response.text))

    if response.status_code != 200:
        print()
        print("API 回傳非 200，測試停止。")
        print(response.text[:5000])
        return

    # ========================================================
    # JSON
    # ========================================================

    try:
        data = response.json()

    except Exception as e:
        print()
        print("JSON 解析失敗：")
        print(repr(e))
        print()
        print(response.text[:5000])
        return

    print()
    print("JSON 解析成功")
    print("API 總筆數:", len(data))

    if not isinstance(data, list):
        print()
        print("錯誤：API 回傳格式不是 List。")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])
        return

    # ========================================================
    # 欄位檢查
    # ========================================================

    print()
    print("-" * 80)
    print("欄位檢查")
    print("-" * 80)

    if data:

        print("第一筆資料欄位：")

        for key in data[0].keys():
            print(f"  {repr(key)}")

    # ========================================================
    # 公司代號欄位處理
    # ========================================================

    def get_stock_code(item):
        return str(
            item.get("公司代號", "")
        ).strip()

    # ========================================================
    # 找四檔股票
    # ========================================================

    results = {}

    for stock_code in STOCKS:

        matched = [
            item
            for item in data
            if get_stock_code(item) == stock_code
        ]

        results[stock_code] = matched

    # ========================================================
    # 四檔股票摘要
    # ========================================================

    print()
    print("=" * 80)
    print("四檔股票測試結果")
    print("=" * 80)

    for stock_code, stock_name in STOCKS.items():

        matched = results[stock_code]

        print()
        print(
            f"【{stock_code} {stock_name}】"
        )

        print(
            "重大訊息筆數:",
            len(matched)
        )

        if not matched:
            print("  → 本次 API 回傳資料中沒有這檔股票。")
            continue

        dates = sorted(
            {
                str(item.get("發言日期", "")).strip()
                for item in matched
                if item.get("發言日期")
            }
        )

        print("發言日期:")

        for date in dates:
            print(
                f"  {date} "
                f"({roc_to_date(date)})"
            )

    # ========================================================
    # 全部資料的日期範圍
    # ========================================================

    all_dates = []

    for item in data:

        date = str(
            item.get("發言日期", "")
        ).strip()

        if date:
            all_dates.append(date)

    unique_dates = sorted(set(all_dates))

    print()
    print("=" * 80)
    print("整份 API 資料的日期範圍")
    print("=" * 80)

    print("不同發言日期數:", len(unique_dates))

    if unique_dates:

        print()
        print("最早發言日期:")
        print(
            unique_dates[0],
            "=>",
            roc_to_date(unique_dates[0])
        )

        print()
        print("最晚發言日期:")
        print(
            unique_dates[-1],
            "=>",
            roc_to_date(unique_dates[-1])
        )

        print()
        print("所有發言日期:")

        for date in unique_dates:
            print(
                f"  {date} => {roc_to_date(date)}"
            )

    # ========================================================
    # 四檔股票完整資料
    # ========================================================

    print()
    print("=" * 80)
    print("四檔股票完整重大訊息")
    print("=" * 80)

    for stock_code, stock_name in STOCKS.items():

        matched = results[stock_code]

        print()
        print("#" * 80)
        print(
            f"{stock_code} {stock_name} "
            f"共 {len(matched)} 筆"
        )
        print("#" * 80)

        for index, item in enumerate(
            matched,
            start=1
        ):

            date = str(
                item.get("發言日期", "")
            ).strip()

            time = str(
                item.get("發言時間", "")
            ).strip()

            title = item.get(
                "主旨",
                item.get("主旨 ", "")
            )

            print()
            print(
                f"[{index}] "
                f"{roc_to_date(date)} "
                f"{format_time(time)}"
            )

            print(
                "主旨:",
                str(title).strip()
            )

            print(
                "符合條款:",
                str(
                    item.get("符合條款", "")
                ).strip()
            )

            print(
                "事實發生日:",
                str(
                    item.get("事實發生日", "")
                ).strip(),
                "(",
                roc_to_date(
                    item.get("事實發生日", "")
                ),
                ")"
            )

    # ========================================================
    # 日期統計
    # ========================================================

    print()
    print("=" * 80)
    print("四檔股票日期統計")
    print("=" * 80)

    for stock_code, stock_name in STOCKS.items():

        matched = results[stock_code]

        counter = Counter()

        for item in matched:

            date = str(
                item.get("發言日期", "")
            ).strip()

            if date:
                counter[date] += 1

        print()
        print(
            f"{stock_code} {stock_name}"
        )

        if not counter:
            print("  無資料")
            continue

        for date in sorted(counter):
            print(
                f"  {roc_to_date(date)}："
                f"{counter[date]} 筆"
            )

    # ========================================================
    # 最後結論資料
    # ========================================================

    print()
    print("=" * 80)
    print("測試完成")
    print("=" * 80)

    print()
    print("請特別注意上面的：")

    print("1. API 總筆數")
    print("2. 四檔股票各有幾筆")
    print("3. 每檔股票的發言日期")
    print("4. 整份 API 最早／最晚發言日期")
    print("5. 是否存在多個不同發言日期")

    print()
    print("以上結果將用來判斷：")
    print("→ API 本身是否提供多日資料")
    print("→ 是否需要每天累積 events.json")
    print("→ 最近 30 天事件應如何保存")


if __name__ == "__main__":
    main()
