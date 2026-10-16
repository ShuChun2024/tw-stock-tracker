import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime


def fetch_mops_briefing_json(company_id, western_year):

    url = "https://mops.twse.com.tw/mops/web/t05st01"

    taiwan_year = western_year - 1911

    result_data = {
        "query_info": {
            "company_id": str(company_id),
            "query_western_year": western_year,
            "query_taiwan_year": taiwan_year,
            "execution_time": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "url": url,
        },
        "briefings": [],
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": (
            "https://mops.twse.com.tw/mops/web/index"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
    }

    params = {
        "TYPEK": "all",
        "co_id": str(company_id),
        "encodeURIComponent": "1",
        "firstin": "1",
        "inpuType": "co_id",
        "off": "1",
        "step": "1",
        "year": str(taiwan_year),
    }

    try:

        session = requests.Session()
        session.headers.update(headers)

        print("正在開啟 MOPS 首頁...")

        home = session.get(
            "https://mops.twse.com.tw/mops/web/index",
            timeout=20
        )

        print("首頁 HTTP:", home.status_code)
        print("首頁 URL:", home.url)

        print()
        print("正在查詢 MOPS 法人說明會...")
        print("查詢參數：", params)

        response = session.get(
            url,
            params=params,
            timeout=20
        )

        response.encoding = "utf-8"

        print()
        print("查詢 HTTP:", response.status_code)
        print("查詢 URL:", response.url)

        if response.status_code != 200:
            return json.dumps(
                {
                    "error": (
                        "MOPS HTTP 狀態碼："
                        f"{response.status_code}"
                    )
                },
                ensure_ascii=False,
                indent=4
            )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        print("HTML 長度：", len(response.text))

        if soup.title:
            print(
                "HTML Title：",
                soup.title.get_text(strip=True)
            )

        # -------------------------------------------------
        # 判斷是否仍被導向錯誤頁
        # -------------------------------------------------

        if "/mops/error/" in response.url:

            result_data["message"] = (
                "MOPS 將查詢導向錯誤頁。"
            )

            result_data["debug"] = {
                "response_url": response.url,
                "html_length": len(response.text),
            }

            return json.dumps(
                result_data,
                ensure_ascii=False,
                indent=4
            )

        # -------------------------------------------------
        # 找所有 table
        # -------------------------------------------------

        tables = soup.find_all("table")

        print("找到 TABLE 數量：", len(tables))

        target_table = None

        for index, table in enumerate(tables):

            text = table.get_text(
                " ",
                strip=True
            )

            print(
                f"TABLE {index}:",
                text[:300]
            )

            if (
                "法人說明會" in text
                or "說明會日期" in text
                or "召開日期" in text
            ):
                target_table = table
                break

        # -------------------------------------------------
        # 沒找到表格
        # -------------------------------------------------

        if target_table is None:

            if "查無資料" in response.text:

                result_data["message"] = (
                    "MOPS 查無資料。"
                )

            else:

                result_data["message"] = (
                    "找不到法人說明會資料表。"
                )

            result_data["debug"] = {
                "response_url": response.url,
                "html_length": len(response.text),
                "table_count": len(tables),
            }

            return json.dumps(
                result_data,
                ensure_ascii=False,
                indent=4
            )

        # -------------------------------------------------
        # 解析表格
        # -------------------------------------------------

        rows = target_table.find_all("tr")

        print("法人說明會表格列數：", len(rows))

        if len(rows) <= 1:

            result_data["message"] = (
                "法人說明會表格沒有資料列。"
            )

            return json.dumps(
                result_data,
                ensure_ascii=False,
                indent=4
            )

        headers_list = [
            cell.get_text(
                " ",
                strip=True
            )
            for cell in rows[0].find_all(
                ["th", "td"]
            )
        ]

        print("欄位：", headers_list)

        for row in rows[1:]:

            cols = row.find_all("td")

            if not cols:
                continue

            row_data = {}

            for i, col in enumerate(cols):

                name = (
                    headers_list[i]
                    if i < len(headers_list)
                    else f"field_{i}"
                )

                row_data[name] = col.get_text(
                    " ",
                    strip=True
                )

            if row_data:
                result_data["briefings"].append(
                    row_data
                )

        result_data["count"] = len(
            result_data["briefings"]
        )

        return json.dumps(
            result_data,
            ensure_ascii=False,
            indent=4
        )

    except Exception as e:

        return json.dumps(
            {
                "error": str(e)
            },
            ensure_ascii=False,
            indent=4
        )


# =========================================================
# 測試
# =========================================================

if __name__ == "__main__":

    target_company = "2330"
    target_year = 2026

    print("=" * 70)
    print(
        f"正在查詢 MOPS："
        f"{target_company} / {target_year}"
    )
    print("=" * 70)

    json_output = fetch_mops_briefing_json(
        target_company,
        target_year
    )

    print()
    print("=== 查詢結果 JSON ===")
    print(json_output)

    output_filename = (
        f"mops_briefing_"
        f"{target_company}_"
        f"{target_year}.json"
    )

    with open(
        output_filename,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(json_output)

    print()
    print(
        "[完成] JSON 已儲存：",
        output_filename
    )
