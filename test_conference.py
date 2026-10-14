import json
import requests
from datetime import datetime


# ============================================================
# TWSE 法人說明會資料測試
# 第二版
# ============================================================

URL = "https://www.twse.com.tw/rwd/zh/announcement/notice"


def main():
    print("=" * 70)
    print("TWSE 法人說明會資料測試 - 第二版")
    print("=" * 70)

    params = {
        "response": "json",
        "startDate": "20261001",
        "endDate": "20261014",
        "selectType": "all",
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.twse.com.tw/",
    }

    print("\n[1] Request URL")
    print(URL)

    print("\n[2] Parameters")
    print(json.dumps(params, ensure_ascii=False, indent=2))

    try:
        response = requests.get(
            URL,
            params=params,
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as e:
        print("\n[ERROR] HTTP request failed")
        print(type(e).__name__, str(e))
        return

    print("\n[3] HTTP Status")
    print(response.status_code)

    print("\n[4] Content-Type")
    print(response.headers.get("Content-Type"))

    print("\n[5] Response Length")
    print(len(response.text))

    print("\n[6] Response Preview")
    print("-" * 70)
    print(response.text[:1000])
    print("-" * 70)

    if response.status_code != 200:
        print("\n[ERROR] HTTP status is not 200")
        return

    # --------------------------------------------------------
    # 嘗試 JSON
    # --------------------------------------------------------
    try:
        data = response.json()
    except ValueError as e:
        print("\n[ERROR] Response is not valid JSON")
        print(str(e))

        # 儲存原始回應，方便後續分析
        filename = "twse_conference_raw.html"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.text)

        print(f"\n已將原始回應儲存為：{filename}")
        return

    print("\n[7] JSON Top-Level Type")
    print(type(data).__name__)

    # --------------------------------------------------------
    # 顯示 JSON 結構
    # --------------------------------------------------------
    if isinstance(data, dict):
        print("\n[8] JSON Keys")
        print(list(data.keys()))

        print("\n[9] JSON Structure")

        for key, value in data.items():
            if isinstance(value, list):
                print(
                    f"  {key}: list "
                    f"(length={len(value)})"
                )

                if value:
                    print(
                        f"      first item type: "
                        f"{type(value[0]).__name__}"
                    )

            elif isinstance(value, dict):
                print(
                    f"  {key}: dict "
                    f"(keys={list(value.keys())[:20]})"
                )

            else:
                print(
                    f"  {key}: "
                    f"{type(value).__name__} = {value}"
                )

    elif isinstance(data, list):
        print(f"\n[8] JSON List Length")
        print(len(data))

        if data:
            print("\n[9] First Item")
            print(
                json.dumps(
                    data[0],
                    ensure_ascii=False,
                    indent=2,
                )
            )

    # --------------------------------------------------------
    # 完整儲存 JSON
    # --------------------------------------------------------
    output_file = "twse_conference_response.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n[10] JSON Saved")
    print(output_file)

    # --------------------------------------------------------
    # 如果是 dict，進一步找可能的資料欄位
    # --------------------------------------------------------
    if isinstance(data, dict):

        print("\n[11] Possible Data Fields")
        print("-" * 70)

        possible_fields = [
            "data",
            "tables",
            "fields",
            "title",
            "date",
            "status",
            "notes",
        ]

        found = False

        for field in possible_fields:
            if field in data:
                found = True

                value = data[field]

                print(f"\n{field}:")
                print(
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        indent=2,
                    )[:5000]
                )

        if not found:
            print("沒有找到預期欄位。")

    print("\n" + "=" * 70)
    print("測試完成")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)


if __name__ == "__main__":
    main()
