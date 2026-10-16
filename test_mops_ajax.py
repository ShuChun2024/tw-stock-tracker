import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

OUTPUT_JSON = BASE_DIR / "mops_ajax_v4_result.json"

REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mops.twse.com.tw/",
}

# ============================================================
# 2. 測試資料
# ============================================================

TEST_CASES = [
    {
        "stock_id": "2330",
        "stock_name": "台積電",
        "url": (
            "https://mopsov.twse.com.tw/mops/web/"
            "ajax_t100sb07_1?parameters="
            "0eb65210d5bdc34ea16e295ccdbad1099abb362c3fc938a027"
            "aff9085fb47dba87c33f7cb1f439f0aa513445e70aaaa6f71"
            "abe605c3d23d1030108b7cc585da0d6f2b2795dd11812a141"
            "746f54089f075d68a73f1504246f412daf016f5a2118"
        ),
    },
    {
        "stock_id": "1101",
        "stock_name": "台泥",
        "url": (
            "https://mopsov.twse.com.tw/mops/web/"
            "ajax_t100sb07_1?parameters="
            "0eb65210d5bdc34ea16e295ccdbad1096cc25092fb1cb844"
            "fc81ce64c36c6b8787c33f7cb1f439f0aa513445e70aaaa6"
            "f71abe605c3d23d1030108b7cc585da0d6f2b2795dd11812"
            "a141746f54089f075d68a73f1504246f412daf016f5a2118"
        ),
    },
]


# ============================================================
# 3. 共用工具
# ============================================================

def clean_text(value):
    """清理空白、換行與不必要字元。"""
    if value is None:
        return ""

    value = str(value)
    value = value.replace("\xa0", " ")
    value = value.replace("\u3000", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def get_lines(soup):
    """取得 HTML 的非空白文字行。"""
    text = soup.get_text(separator="\n")

    lines = []

    for line in text.splitlines():
        line = clean_text(line)

        if line:
            lines.append(line)

    return lines


def normalize_label(value):
    """標準化欄位名稱，方便比對。"""
    value = clean_text(value)

    value = re.sub(r"[：:]\s*$", "", value)
    value = value.replace(" ", "")

    return value


def is_pdf_url(url):
    """判斷網址是否指向 PDF。"""
    if not url:
        return False

    path = urlparse(url).path.lower()

    return path.endswith(".pdf")


def is_http_url(url):
    """只接受 HTTP 或 HTTPS 網址。"""
    if not url:
        return False

    return urlparse(url).scheme.lower() in ("http", "https")


# ============================================================
# 4. 解析表格欄位
# ============================================================

def get_table_field(soup, labels):
    """
    優先從表格列取得欄位值。

    找到包含欄位名稱的儲存格後，
    取同一列後續儲存格的文字。
    """

    if isinstance(labels, str):
        labels = [labels]

    normalized_labels = [
        normalize_label(label)
        for label in labels
    ]

    for cell in soup.find_all(["td", "th"]):
        cell_text = clean_text(cell.get_text(" ", strip=True))
        normalized_text = normalize_label(cell_text)

        matched = any(
            normalized_text == label
            or normalized_text.startswith(label + "：")
            or normalized_text.startswith(label + ":")
            for label in normalized_labels
        )

        if not matched:
            continue

        row = cell.find_parent("tr")

        if not row:
            continue

        cells = row.find_all(["td", "th"], recursive=False)

        try:
            current_index = cells.index(cell)
        except ValueError:
            continue

        # 優先取欄位右側的儲存格
        for next_cell in cells[current_index + 1:]:
            value = clean_text(
                next_cell.get_text(" ", strip=True)
            )

            if value:
                return value

    return ""


def get_text_field(soup, labels):
    """
    從整份 HTML 文字擷取欄位值。

    此方法作為表格解析失敗時的備援。
    """

    if isinstance(labels, str):
        labels = [labels]

    normalized_labels = [
        normalize_label(label)
        for label in labels
    ]

    lines = get_lines(soup)

    for index, line in enumerate(lines):
        normalized_line = normalize_label(line)

        for label in normalized_labels:

            # 欄位名稱與內容在同一行
            if normalized_line.startswith(label):
                remainder = line[len(label):].strip()

                remainder = re.sub(
                    r"^[：:＝=]\s*",
                    "",
                    remainder,
                )

                if remainder:
                    return remainder

                # 欄位名稱獨立一行，取下一個非空白行
                for next_line in lines[index + 1:]:
                    if next_line:
                        return next_line

    return ""


def get_field(soup, labels):
    """先解析表格，再使用文字解析作為備援。"""

    value = get_table_field(soup, labels)

    if value:
        return value

    return get_text_field(soup, labels)


# ============================================================
# 5. 日期與時間格式
# ============================================================

def roc_to_ad(value):
    """
    民國日期轉西元日期。

    例如：
    115/10/15 -> 2026-10-15
    """

    value = clean_text(value)

    match = re.search(
        r"(\d{2,3})\s*[/\-年]\s*"
        r"(\d{1,2})\s*[/\-月]\s*"
        r"(\d{1,2})",
        value,
    )

    if not match:
        # 若來源已經是西元日期，直接嘗試標準化
        western_match = re.search(
            r"(20\d{2})\s*[/\-年]\s*"
            r"(\d{1,2})\s*[/\-月]\s*"
            r"(\d{1,2})",
            value,
        )

        if western_match:
            year, month, day = map(
                int, western_match.groups()
            )

            try:
                return datetime(
                    year, month, day
                ).strftime("%Y-%m-%d")
            except ValueError:
                return ""

        return ""

    roc_year, month, day = map(int, match.groups())
    western_year = roc_year + 1911

    try:
        return datetime(
            western_year, month, day
        ).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def parse_time(value):
    """
    將時間轉成 HH:MM。

    支援例如：
    14 點 0 分
    下午 2:00
    14:00
    09時30分
    """

    value = clean_text(value)

    if not value:
        return ""

    is_pm = "下午" in value
    is_am = "上午" in value

    match = re.search(
        r"(\d{1,2})\s*"
        r"(?:點|時|:|：)\s*"
        r"(\d{1,2})?",
        value,
    )

    if not match:
        return ""

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)

    if hour > 23 or minute > 59:
        return ""

    if is_pm and hour < 12:
        hour += 12

    if is_am and hour == 12:
        hour = 0

    return f"{hour:02d}:{minute:02d}"


# ============================================================
# 6. 網址解析
# ============================================================

def get_row_links(soup, labels):
    """
    從欄位名稱所在的最近一個表格列擷取網址。

    重點：
    不再向上搜尋過大的 HTML 區塊，
    避免公司網站欄位誤抓到其他列的 PDF。
    """

    if isinstance(labels, str):
        labels = [labels]

    normalized_labels = [
        normalize_label(label)
        for label in labels
    ]

    for cell in soup.find_all(["td", "th"]):
        cell_text = clean_text(
            cell.get_text(" ", strip=True)
        )
        normalized_text = normalize_label(cell_text)

        if not any(
            label in normalized_text
            for label in normalized_labels
        ):
            continue

        row = cell.find_parent("tr")

        if not row:
            continue

        links = []

        for anchor in row.find_all("a", href=True):
            href = clean_text(anchor.get("href"))

            if not href:
                continue

            full_url = urljoin(
                "https://mopsov.twse.com.tw",
                href,
            )

            if is_http_url(full_url):
                links.append(full_url)

        # 同一列的網址去重，保留原順序
        unique_links = list(dict.fromkeys(links))

        if unique_links:
            return unique_links

    return []


def find_labeled_link(soup, labels, exclude_pdf=False):
    """
    擷取指定欄位所屬表格列中的第一個合適網址。

    不會在整個文件中任意搜尋第一個網址。
    """

    links = get_row_links(soup, labels)

    for url in links:
        if exclude_pdf and is_pdf_url(url):
            continue

        return url

    return ""


def find_pdf_links(soup):
    """
    擷取所有 PDF 連結並分類中文、英文簡報。

    本函式只解析網址，不會下載檔案。
    """

    pdf_urls = []

    for anchor in soup.find_all("a", href=True):
        href = clean_text(anchor.get("href"))

        if not href:
            continue

        full_url = urljoin(
            "https://mopsov.twse.com.tw",
            href,
        )

        if not is_http_url(full_url):
            continue

        if not is_pdf_url(full_url):
            continue

        if full_url not in pdf_urls:
            pdf_urls.append(full_url)

    chinese_pdf = ""
    english_pdf = ""
    other_pdfs = []

    for url in pdf_urls:
        filename = urlparse(url).path.rsplit("/", 1)[-1]
        upper_filename = filename.upper()

        # MOPS 檔名常見尾碼：M 為中文、E 為英文
        if re.search(r"M\d*\.PDF$", upper_filename):
            if not chinese_pdf:
                chinese_pdf = url

        elif re.search(r"E\d*\.PDF$", upper_filename):
            if not english_pdf:
                english_pdf = url

        else:
            other_pdfs.append(url)

    return {
        "chinese_pdf_url": chinese_pdf,
        "english_pdf_url": english_pdf,
        "other_pdf_urls": other_pdfs,
        "all_pdf_urls": pdf_urls,
    }


# ============================================================
# 7. 解析 MOPS AJAX 明細
# ============================================================

def parse_mops_ajax(stock_case, html):
    soup = BeautifulSoup(html, "html.parser")

    stock_id = stock_case["stock_id"]

    # --------------------------------------------------------
    # 基本欄位
    # --------------------------------------------------------

    company_id = get_field(
        soup,
        ["公司代號", "股票代號"],
    )

    if not company_id:
        company_id = stock_id

    company_name = get_field(
        soup,
        ["公司名稱", "公司簡稱"],
    )

    if not company_name:
        company_name = stock_case["stock_name"]

    raw_date = get_field(
        soup,
        ["法說會日期", "召開日期", "舉辦日期", "日期"],
    )

    raw_time = get_field(
        soup,
        ["法說會時間", "召開時間", "舉辦時間", "時間"],
    )

    location = get_field(
        soup,
        ["法說會地點", "召開地點", "舉辦地點", "地點"],
    )

    summary = get_field(
        soup,
        [
            "法說會內容",
            "會議內容",
            "說明內容",
            "會議摘要",
        ],
    )

    # --------------------------------------------------------
    # PDF 連結
    # --------------------------------------------------------

    pdf_data = find_pdf_links(soup)

    # --------------------------------------------------------
    # 公司網站與影音連結
    # --------------------------------------------------------

    company_website = find_labeled_link(
        soup,
        [
            "公司網站是否有提供法人說明會相關資訊",
            "公司網站",
        ],
        exclude_pdf=True,
    )

    video_url = find_labeled_link(
        soup,
        [
            "影音連結資訊",
            "影音連結",
            "影音網址",
        ],
        exclude_pdf=True,
    )

    # --------------------------------------------------------
    # 組合結果
    # --------------------------------------------------------

    result = {
        "stock_id": stock_id,
        "company_id": clean_text(company_id),
        "company_name": clean_text(company_name),

        "date_original": clean_text(raw_date),
        "date": roc_to_ad(raw_date),

        "time_original": clean_text(raw_time),
        "time": parse_time(raw_time),

        "location": clean_text(location),
        "summary": clean_text(summary),

        "chinese_pdf_url": pdf_data["chinese_pdf_url"],
        "english_pdf_url": pdf_data["english_pdf_url"],
        "other_pdf_urls": pdf_data["other_pdf_urls"],
        "all_pdf_urls": pdf_data["all_pdf_urls"],

        "company_website_url": company_website,
        "video_url": video_url,

        "source_url": stock_case["url"],
        "parsed_at": datetime.now().isoformat(
            timespec="seconds"
        ),
    }

    return result


# ============================================================
# 8. 資料驗證
# ============================================================

def validate(result):
    errors = []
    warnings = []

    stock_id = result["stock_id"]

    # --------------------------------------------------------
    # 基本欄位
    # --------------------------------------------------------

    required_fields = [
        "company_id",
        "company_name",
        "date",
        "time",
        "location",
        "summary",
    ]

    for field in required_fields:
        if not result.get(field):
            errors.append(f"缺少必要欄位：{field}")

    if result.get("company_id") and (
        result["company_id"] != stock_id
    ):
        warnings.append(
            "公司代號與測試股票代號不同："
            f"{result['company_id']} / {stock_id}"
        )

    # --------------------------------------------------------
    # 日期格式
    # --------------------------------------------------------

    if result.get("date"):
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}",
            result["date"],
        ):
            errors.append("日期格式不正確")

    # --------------------------------------------------------
    # PDF 網址
    # --------------------------------------------------------

    for field in [
        "chinese_pdf_url",
        "english_pdf_url",
    ]:
        url = result.get(field, "")

        if url and not is_pdf_url(url):
            errors.append(
                f"{field} 不是 PDF 網址：{url}"
            )

    # --------------------------------------------------------
    # 公司網站網址
    # --------------------------------------------------------

    website = result.get("company_website_url", "")

    if website:
        if is_pdf_url(website):
            errors.append(
                "公司網站網址誤抓成 PDF："
                f"{website}"
            )

        if not is_http_url(website):
            errors.append(
                "公司網站網址不是有效 HTTP/HTTPS 網址"
            )
    else:
        warnings.append(
            "未解析到公司網站網址，請檢查 HTML 欄位結構"
        )

    # --------------------------------------------------------
    # 影音網址
    # --------------------------------------------------------

    video = result.get("video_url", "")

    if video:
        if is_pdf_url(video):
            errors.append(
                "影音網址誤抓成 PDF："
                f"{video}"
            )

        if not is_http_url(video):
            errors.append(
                "影音網址不是有效 HTTP/HTTPS 網址"
            )
    else:
        warnings.append(
            "未解析到影音網址，請確認該場法說會是否提供影音"
        )

    # --------------------------------------------------------
    # PDF 欄位檢查
    # --------------------------------------------------------

    if not result.get("all_pdf_urls"):
        warnings.append("沒有解析到任何 PDF 網址")

    if not result.get("chinese_pdf_url"):
        warnings.append("沒有解析到中文 PDF 網址")

    if not result.get("english_pdf_url"):
        warnings.append("沒有解析到英文 PDF 網址")

    return errors, warnings


# ============================================================
# 9. 輸出測試結果
# ============================================================

def print_result(result, errors, warnings):
    print()
    print("=" * 70)
    print(
        f"股票：{result['stock_id']} "
        f"{result['company_name']}"
    )
    print("=" * 70)

    print(f"公司代號       : {result['company_id']}")
    print(f"公司名稱       : {result['company_name']}")
    print(f"原始日期       : {result['date_original']}")
    print(f"標準日期       : {result['date']}")
    print(f"原始時間       : {result['time_original']}")
    print(f"標準時間       : {result['time']}")
    print(f"地點           : {result['location']}")
    print(f"摘要           : {result['summary']}")

    print("-" * 70)
    print("簡報網址（只保存網址，不下載檔案）")
    print(f"中文 PDF       : {result['chinese_pdf_url']}")
    print(f"英文 PDF       : {result['english_pdf_url']}")

    for index, url in enumerate(
        result["other_pdf_urls"], start=1
    ):
        print(f"其他 PDF {index}     : {url}")

    print("-" * 70)
    print("其他連結")
    print(
        f"公司網站       : "
        f"{result['company_website_url']}"
    )
    print(f"影音網址       : {result['video_url']}")

    print("-" * 70)

    if errors:
        print("驗證結果：失敗")

        for error in errors:
            print(f"[錯誤] {error}")
    else:
        print("驗證結果：基本檢查通過")

    for warning in warnings:
        print(f"[提醒] {warning}")


# ============================================================
# 10. 主程式
# ============================================================

def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    all_results = []
    total_errors = 0

    print("=" * 70)
    print("MOPS AJAX 法人說明會解析測試 V4")
    print("模式：只解析資料與網址，不下載 PDF 或影音")
    print("=" * 70)

    for stock_case in TEST_CASES:
        stock_id = stock_case["stock_id"]

        print()
        print(f"正在查詢：{stock_id} / {stock_case['stock_name']}")

        try:
            response = session.get(
                stock_case["url"],
                timeout=REQUEST_TIMEOUT,
            )

            print(f"HTTP Status：{response.status_code}")
            print(f"回應網址：{response.url}")

            response.raise_for_status()

            response.encoding = response.apparent_encoding or "utf-8"
            html = response.text

            if not html.strip():
                raise ValueError("伺服器回傳空白 HTML")

            soup = BeautifulSoup(html, "html.parser")

            page_text = clean_text(
                soup.get_text(" ", strip=True)
            )

            if not page_text:
                raise ValueError("HTML 中沒有可解析的文字")

            result = parse_mops_ajax(
                stock_case,
                html,
            )

            errors, warnings = validate(result)

            print_result(
                result,
                errors,
                warnings,
            )

            result["validation"] = {
                "passed": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
            }

            if errors:
                total_errors += len(errors)

            all_results.append(result)

        except Exception as exc:
            total_errors += 1

            print(f"[錯誤] 股票 {stock_id} 處理失敗：{exc}")

            all_results.append({
                "stock_id": stock_id,
                "company_name": stock_case["stock_name"],
                "source_url": stock_case["url"],
                "validation": {
                    "passed": False,
                    "errors": [str(exc)],
                    "warnings": [],
                },
            })

        # 避免連續請求過快
        time.sleep(1)

    # --------------------------------------------------------
    # 儲存 JSON 結果
    # --------------------------------------------------------

    output_data = {
        "version": "V4",
        "download_files": False,
        "description": (
            "只解析 MOPS 法人說明會資料及網址；"
            "不下載 PDF 或影音檔。"
        ),
        "tested_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "total_stocks": len(TEST_CASES),
        "failed_stocks": sum(
            1
            for item in all_results
            if not item.get("validation", {}).get("passed", False)
        ),
        "results": all_results,
    }

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 70)
    print("V4 測試摘要")
    print("=" * 70)
    print(f"測試股票數：{len(TEST_CASES)}")
    print(f"驗證錯誤數：{total_errors}")
    print(f"JSON 輸出：{OUTPUT_JSON}")
    print("PDF 下載：未執行")
    print("影音下載：未執行")

    failed_stocks = output_data["failed_stocks"]

    if failed_stocks == 0:
        print("整體結果：所有股票均通過錯誤檢查")
    else:
        print(
            f"整體結果：{failed_stocks} 檔股票有驗證錯誤，"
            "請檢查上方輸出"
        )


if __name__ == "__main__":
    main()
