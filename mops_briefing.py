import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime


def fetch_mops_briefing_json(company_id, western_year):
    """
    查詢公開資訊觀測站（MOPS）
    指定公司、指定年度的法人說明會資料。
    """

    # =====================================================
    # 1. MOPS 法人說明會查詢頁
    # =====================================================

    url = "https://mops.twse.com.tw/mops/web/t05st01"

    taiwan_year = western_year - 1911

    if taiwan_year <= 0:
        return json.dumps(
            {
                "error": "年份輸入錯誤，請輸入大於 1911 的西元年份。"
            },
            ensure_ascii=False,
            indent=4
        )

    # =====================================================
    # 2. Headers
    # =====================================================

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://mops.twse.com.tw/mops/web/index",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # =====================================================
    # 3. MOPS 查詢參數
    # =====================================================

    form_data = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "co_id": str(company_id),
        "year": str(taiwan_year),
    }

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

    try:

        # =================================================
        # 4. 建立 Session
        # =================================================

        session = requests.Session()

        session.headers.update(headers)

        # 先進入 MOPS 首頁
        session.get(
            "https://mops.twse.com.tw/mops/web/index",
            timeout=15
        )

        # =================================================
        # 5. POST 查詢
        # =================================================

        response = session.post(
            url,
            data=form_data,
            timeout=15
        )

        print("HTTP Status:", response.status_code)
        print("Response URL:", response.url)

        if response.status_code != 200:
            return json.dumps(
                {
                    "error": (
                        "連線失敗，HTTP 狀態碼: "
                        f"{response.status_code}"
                    )
                },
                ensure_ascii=False,
                indent=4
            )

        response.encoding = "utf-8"

        # =================================================
        # 6. 解析 HTML
        # =================================================

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # -------------------------------------------------
        # 找法人說明會相關表格
        # -------------------------------------------------

        tables = soup.find_all("table")

        print("找到 TABLE 數量：", len(tables))

        target_table = None

        for table in tables:

            text = table.get_text(
                " ",
                strip=True
            )

            if (
                "法人說明會" in text
                or "說明會日期" in text
                or "召開日期" in text
            ):
                target_table = table
                break

        # =================================================
        # 7. 找不到表格
        # =================================================

        if target_table is None:

            if "查無資料" in response.text:

                result_data["message"] = (
                    "該年度查無此公司之法人說明會申報資料。"
                )

                return json.dumps(
                    result_data,
                    ensure_ascii=False,
                    indent=4
                )

            # 保留 HTML 關鍵資訊供除錯
            result_data["message"] = (
                "找不到法人說明會資料表。"
            )

            result_data["debug"] = {
                "html_length": len(response.text),
                "title": (
                    soup.title.get_text(strip=True)
                    if soup.title
                    else ""
                ),
            }

            return json.dumps(
                result_data,
                ensure_ascii=False,
                indent=4
            )

        # =================================================
        # 8. 解析表格
        # =================================================

        rows = target_table.find_all("tr")

        print("找到資料列：", len(rows))

        if len(rows) <= 1:

            result_data["message"] = (
                "法人說明會表格內沒有資料列。"
            )

            return json.dumps(
                result_data,
                ensure_ascii=False,
                indent=4
            )

        # -------------------------------------------------
        # 找欄位名稱
        # -------------------------------------------------

        header_row = rows[0]

        headers_list = [
            cell.get_text(
                " ",
                strip=True
            )
            for cell in header_row.find_all(
                ["th", "td"]
            )
        ]

        print("欄位：", headers_list)

        # =================================================
        # 9. 解析每一筆資料
        # =================================================

        for row in rows[1:]:

            cols = row.find_all("td")

            if not cols:
                continue

            row_data = {}

            for i, col in enumerate(cols):

                col_name = (
                    headers_list[i]
                    if i < len(headers_list)
                    else f"field_{i}"
                )

                text_val = col.get_text(
                    " ",
                    strip=True
                )

                # 如果有按鈕
                button = col.find(
                    "input",
                    {"type": "button"}
                )

                if (
                    button
                    and button.has_attr("value")
                ):
                    text_val = button["value"]

                row_data[col_name] = text_val

            if row_data:
                result_data["briefings"].append(
                    row_data
                )

        # =================================================
        # 10. 結果
        # =================================================

        result_data["count"] = len(
            result_data["briefings"]
        )

        return json.dumps(
            result_data,
            ensure_ascii=False,
            indent=4
        )

    except requests.exceptions.Timeout:

        return json.dumps(
            {
                "error": (
                    "請求逾時，MOPS 伺服器反應過慢，"
                    "請稍後再試。"
                )
            },
            ensure_ascii=False,
            indent=4
        )

    except Exception as e:

        return json.dumps(
            {
                "error": (
                    "程式執行發生異常: "
                    f"{str(e)}"
                )
            },
            ensure_ascii=False,
            indent=4
        )


# =========================================================
# 主程式
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
