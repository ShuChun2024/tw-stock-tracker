import requests
from collections import Counter
from datetime import datetime


# ============================================================
# TWSE OpenAPI 多事件資料源測試
# ============================================================

BASE_URL = "https://openapi.twse.com.tw/v1"

STOCKS = {
    "1101": "台泥",
    "2330": "台積電",
    "2454": "聯發科",
    "2317": "鴻海",
}


# ============================================================
# 要測試的 TWSE API
# ============================================================

APIS = {
    "t187ap04_L": "上市公司每日重大訊息",
    "t187ap22_L": "上市公司金管會證券期貨局裁罰案件",
    "t187ap23_L": "上市公司違反資訊申報、重大訊息及說明記者會規定",
    "t187ap38_L": "上市公司股東會公告",
    "t187ap41_L": "上市公司召開股東常（臨時）會日期、地點及電子投票",
    "t187ap45_L": "上市公司股利分派情形",
    "t187ap24_L": "上市公司經營權異動",
    "t187ap25_L": "上市公司營業範圍重大變更",
}


# ============================================================
# 日期格式
# ============================================================

def roc_to_date(value):
    """
    民國日期：
    1151012 -> 2026-10-12
    """

    if value is None:
        return ""

    value = str(value).strip()

    if len(value) != 7:
        return value

    try:
        year = int(value[:3]) + 1911
        month = int(value[3:5])
        day = int(value[5:7])

        return f"{year:04d}-{month:02d}-{day:02d}"

    except Exception:
        return value


# ============================================================
# 找可能的股票代號欄位
# ============================================================

def get_stock_id(item):

    possible_keys = [
        "公司代號",
        "股票代號",
        "證券代號",
        "代號",
    ]

    for key in possible_keys:
        if key in item:
            value = str(item.get(key, "")).strip()

            if value:
                return value

    return ""


# ============================================================
# 找可能的日期欄位
# ============================================================

def get_date_value(item):

    possible_keys = [
        "發言日期",
        "公告日期",
        "日期",
        "出表日期",
        "資料日期",
        "股東會日期",
        "除權息交易日",
        "事實發生日",
    ]

    for key in possible_keys:
        if key in item:

            value = str(item.get(key, "")).strip()

            if value:
                return value

    return ""


# ============================================================
# 顯示日期範圍
# ============================================================

def show_date_range(rows):

    dates = []

    for item in rows:

        value = get_date_value(item)

        if value:
            dates.append(value)

    if not dates:
        print("日期欄位：無法判斷")
        return

    dates = sorted(set(dates))

    print(f"日期筆數: {len(dates)}")

    print(f"最早日期: {dates[0]}")
    print(f"最晚日期: {dates[-1]}")

    if len(dates) <= 20:

        print("所有日期:")

        for value in dates:
            print(f"  {value}")


# ============================================================
# 測試單一 API
# ============================================================

def test_api(api_code, api_name):

    url = f"{BASE_URL}/opendata/{api_code}"

    print()
    print("=" * 80)
    print(f"{api_code}｜{api_name}")
    print("=" * 80)

    print()
    print(f"URL:")
    print(url)

    try:

        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=30
        )

        print()
        print("HTTP 測試")
        print("-" * 80)

        print(f"HTTP Status: {response.status_code}")
        print(
            "Content-Type:",
            response.headers.get("Content-Type", "")
        )
        print(
            "資料長度:",
            len(response.content)
        )

    except Exception as e:

        print()
        print("HTTP 請求失敗")
        print(e)

        return

    if response.status_code != 200:

        print()
        print("API 回傳非 200")
        print(response.text[:1000])

        return

    try:

        data = response.json()

    except Exception as e:

        print()
        print("JSON 解析失敗")
        print(e)

        print()
        print("回應前 1000 字元:")
        print(response.text[:1000])

        return

    if not isinstance(data, list):

        print()
        print("API 回傳格式不是 List")

        print(type(data))

        print(data)

        return

    print()
    print("JSON 解析成功")
    print(f"API 總筆數: {len(data)}")

    if not data:

        print()
        print("API 沒有資料")

        return

    # --------------------------------------------------------
    # 欄位
    # --------------------------------------------------------

    print()
    print("第一筆資料欄位")
    print("-" * 80)

    for key in data[0].keys():

        print(repr(key))

    # --------------------------------------------------------
    # 日期範圍
    # --------------------------------------------------------

    print()
    print("資料日期範圍")
    print("-" * 80)

    show_date_range(data)

    # --------------------------------------------------------
    # 四檔股票
    # --------------------------------------------------------

    print()
    print("四檔股票資料")
    print("-" * 80)

    for stock_id, stock_name in STOCKS.items():

        matched = []

        for item in data:

            item_stock_id = get_stock_id(item)

            if item_stock_id == stock_id:
                matched.append(item)

        print()
        print(f"【{stock_id} {stock_name}】")
        print(f"資料筆數: {len(matched)}")

        if not matched:

            print("  → 本次 API 回傳資料中沒有這檔股票。")

            continue

        # 顯示日期
        dates = []

        for item in matched:

            date_value = get_date_value(item)

            if date_value:
                dates.append(date_value)

        if dates:

            print("日期:")

            for date_value in sorted(set(dates)):

                print(
                    f"  {date_value}"
                    f" => {roc_to_date(date_value)}"
                )

        # ----------------------------------------------------
        # 顯示前 3 筆
        # ----------------------------------------------------

        print()
        print("前 3 筆資料:")

        for index, item in enumerate(matched[:3], 1):

            print()
            print(f"[{index}]")

            for key, value in item.items():

                value = str(value).replace("\r\n", " ")
                value = value.replace("\n", " ")

                if len(value) > 200:
                    value = value[:200] + "..."

                print(
                    f"{key}: {value}"
                )

    # --------------------------------------------------------
    # 資料日期統計
    # --------------------------------------------------------

    print()
    print("資料日期統計")
    print("-" * 80)

    counter = Counter()

    for item in data:

        date_value = get_date_value(item)

        if date_value:

            counter[date_value] += 1

    if counter:

        for date_value, count in sorted(counter.items()):

            print(
                f"{date_value}"
                f" ({roc_to_date(date_value)}): "
                f"{count} 筆"
            )

    print()
    print("本 API 測試完成")


# ============================================================
# 主程式
# ============================================================

def main():

    print("=" * 80)
    print("TWSE OpenAPI｜官方事件資料源測試")
    print("=" * 80)

    print()
    print("測試股票:")

    for stock_id, stock_name in STOCKS.items():

        print(
            f"  {stock_id} {stock_name}"
        )

    print()
    print(f"測試 API 數量: {len(APIS)}")

    print()
    print("開始測試...")

    for api_code, api_name in APIS.items():

        test_api(
            api_code,
            api_name
        )

    print()
    print("=" * 80)
    print("全部測試完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
