import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ============================================================
# MOPS AJAX 詳細資料測試 V2
# ============================================================

BASE_URL = "https://mopsov.twse.com.tw"

URL = (
    "https://mopsov.twse.com.tw/mops/web/ajax_t100sb07_1"
    "?parameters="
    "0eb65210d5bdc34ea16e295ccdbad1099abb362c3fc938a027aff9085fb47dba87c33f7cb1f439f0aa513445e70aaaa6f71abe605c3d23d1030108b7cc585da0d6f2b2795dd11812a141746f54089f075d68a73f1504246f412daf016f5a2118"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mopsov.twse.com.tw/",
}


# ============================================================
# 民國日期轉西元
# ============================================================

def roc_to_ad(date_text):
    """
    將民國日期轉成西元日期。

    例如：
        115/10/15 -> 2026-10-15
    """

    if not date_text:
        return ""

    match = re.search(
        r"(\d{2,3})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})",
        date_text
    )

    if not match:
        return date_text.strip()

    roc_year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    ad_year = roc_year + 1911

    return f"{ad_year:04d}-{month:02d}-{day:02d}"


# ============================================================
# 時間轉換
# ============================================================

def parse_time(text):
    """
    將 MOPS 顯示的：

        14 點 0 分

    轉成：

        14:00
    """

    if not text:
        return ""

    match = re.search(
        r"(\d{1,2})\s*點\s*(\d{1,2})\s*分",
        text
    )

    if not match:
        return text.strip()

    hour = int(match.group(1))
    minute = int(match.group(2))

    return f"{hour:02d}:{minute:02d}"


# ============================================================
# 清理文字
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = text.replace("\xa0", " ")

    text = re.sub(r"[ \t\r\f\v]+", " ", text)

    text = re.sub(r"\n\s*\n+", "\n", text)

    return text.strip()


# ============================================================
# 找欄位
# ============================================================

def find_label_value(soup, label):
    """
    嘗試根據欄位名稱找到下一個欄位內容。

    這是測試版解析器，不修改 MOPS 原始 HTML。
    """

    text = soup.get_text("\n", strip=True)

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for i, line in enumerate(lines):

        if line == label:

            if i + 1 < len(lines):
                return lines[i + 1]

    return ""


# ============================================================
# 解析 PDF 連結
# ============================================================

def find_pdf_links(soup):

    pdf_links = []

    for link in soup.find_all("a"):

        href = link.get("href", "").strip()
        text = link.get_text(" ", strip=True)

        if not href:
            continue

        if ".pdf" not in href.lower():
            continue

        full_url = urljoin(BASE_URL, href)

        pdf_links.append({
            "name": text,
            "href": href,
            "url": full_url,
        })

    return pdf_links


# ============================================================
# 解析完整資料
# ============================================================

def parse_mops_ajax(html):

    soup = BeautifulSoup(html, "html.parser")

    result = {
        "company_id": "",
        "company_name": "",
        "date_roc": "",
        "date": "",
        "time_raw": "",
        "time": "",
        "location": "",
        "summary": "",
        "chinese_pdf": "",
        "english_pdf": "",
        "company_website": "",
        "video_url": "",
        "other": "",
    }

    # --------------------------------------------------------
    # 取得所有文字
    # --------------------------------------------------------

    text = soup.get_text("\n", strip=True)

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    # --------------------------------------------------------
    # 公司代號
    # --------------------------------------------------------

    if "公司代號：" in lines:
        index = lines.index("公司代號：")

        if index + 1 < len(lines):
            result["company_id"] = lines[index + 1]

    # --------------------------------------------------------
    # 公司名稱
    # --------------------------------------------------------

    if "公司名稱：" in lines:
        index = lines.index("公司名稱：")

        if index + 1 < len(lines):
            result["company_name"] = lines[index + 1]

    # --------------------------------------------------------
    # 法說會日期
    # --------------------------------------------------------

    if "召開法人說明會日期：" in lines:
        index = lines.index("召開法人說明會日期：")

        if index + 1 < len(lines):
            result["date_roc"] = lines[index + 1]
            result["date"] = roc_to_ad(result["date_roc"])

    # --------------------------------------------------------
    # 時間
    # --------------------------------------------------------

    if "時間：" in lines:

        index = lines.index("時間：")

        time_parts = []

        for j in range(index + 1, min(index + 8, len(lines))):

            line = lines[j]

            if line in [
                "召開法人說明會地點：",
                "法人說明會擇要訊息：",
            ]:
                break

            time_parts.append(line)

        result["time_raw"] = " ".join(time_parts)
        result["time"] = parse_time(result["time_raw"])

    # --------------------------------------------------------
    # 地點
    # --------------------------------------------------------

    if "召開法人說明會地點：" in lines:

        index = lines.index("召開法人說明會地點：")

        if index + 1 < len(lines):
            result["location"] = lines[index + 1]

    # --------------------------------------------------------
    # 法人說明會摘要
    # --------------------------------------------------------

    if "法人說明會擇要訊息：" in lines:

        index = lines.index("法人說明會擇要訊息：")

        summary_parts = []

        for j in range(index + 1, len(lines)):

            line = lines[j]

            if line == "法人說明會簡報內容":
                break

            summary_parts.append(line)

        result["summary"] = " ".join(summary_parts)

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    pdf_links = find_pdf_links(soup)

    for pdf in pdf_links:

        name = pdf["name"].lower()

        if "m001" in name:
            result["chinese_pdf"] = pdf["url"]

        elif "e001" in name:
            result["english_pdf"] = pdf["url"]

    # --------------------------------------------------------
    # 網站 / 影音
    # --------------------------------------------------------

    urls = []

    for link in soup.find_all("a"):

        href = link.get("href", "").strip()

        if href.startswith("http"):

            if href not in urls:
                urls.append(href)

    for url in urls:

        if "tsmc.com" in url:

            if not result["company_website"]:
                result["company_website"] = url

            if not result["video_url"]:
                result["video_url"] = url

    # --------------------------------------------------------
    # 其他應敘明事項
    # --------------------------------------------------------

    if "其他應敘明事項：" in lines:

        index = lines.index("其他應敘明事項：")

        if index + 1 < len(lines):
            result["other"] = lines[index + 1]

    return result


# ============================================================
# 顯示結果
# ============================================================

def print_result(data):

    print()
    print("=" * 70)
    print("結構化解析結果")
    print("=" * 70)

    print(f"公司代號       : {data['company_id']}")
    print(f"公司名稱       : {data['company_name']}")

    print()

    print(f"民國日期       : {data['date_roc']}")
    print(f"西元日期       : {data['date']}")

    print()

    print(f"原始時間       : {data['time_raw']}")
    print(f"標準時間       : {data['time']}")

    print()

    print(f"地點           : {data['location']}")

    print()

    print("法人說明會摘要")
    print("-" * 70)
    print(data["summary"])

    print()

    print(f"中文 PDF       : {data['chinese_pdf']}")
    print(f"英文 PDF       : {data['english_pdf']}")

    print()

    print(f"公司網站       : {data['company_website']}")
    print(f"影音連結       : {data['video_url']}")

    print()

    print(f"其他事項       : {data['other']}")

    print()
    print("=" * 70)


# ============================================================
# 主程式
# ============================================================

def main():

    print("=" * 70)
    print("MOPS AJAX 詳細資料測試 V2")
    print("=" * 70)

    print("\n[1] 發送 Request")

    try:

        response = requests.get(
            URL,
            headers=HEADERS,
            timeout=30,
        )

    except Exception as e:

        print("Request 失敗")
        print(type(e).__name__, e)

        return

    print("HTTP Status:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))

    if response.status_code != 200:

        print("\nHTTP Request 失敗")
        print(response.text[:2000])

        return

    print("\n[2] 開始解析 HTML")

    data = parse_mops_ajax(response.text)

    print_result(data)

    print("\n[3] 基本驗證")

    checks = {
        "公司代號": data["company_id"] == "2330",
        "公司名稱": data["company_name"] == "台積電",
        "日期": data["date"] == "2026-10-15",
        "時間": data["time"] == "14:00",
        "中文 PDF": data["chinese_pdf"].endswith(
            "233020261015M001.pdf"
        ),
        "英文 PDF": data["english_pdf"].endswith(
            "233020261015E001.pdf"
        ),
    }

    all_passed = True

    for name, passed in checks.items():

        status = "PASS" if passed else "FAIL"

        print(f"{status:>5} : {name}")

        if not passed:
            all_passed = False

    print()

    if all_passed:
        print("所有基本驗證 PASS")
    else:
        print("有驗證項目 FAIL，請檢查上面的解析結果")

    print()
    print("=" * 70)
    print("V2 測試完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
