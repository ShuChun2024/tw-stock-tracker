import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ============================================================
# MOPS AJAX 詳細資料解析測試 V3.2
# ============================================================

BASE_URL = "https://mopsov.twse.com.tw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}


# ============================================================
# 測試案例
# ============================================================

TEST_CASES = {
    "2330": (
        "https://mopsov.twse.com.tw/mops/web/"
        "ajax_t100sb07_1?parameters="
        "0eb65210d5bdc34ea16e295ccdbad1096cc25092fb1cb844fc81ce64c36c6b8787c33f7cb1f439f0aa513445e70aaaa6f71abe605c3d23d1030108b7cc585da0d6f2b2795"
    ),

    "1101": (
        "https://mopsov.twse.com.tw/mops/web/"
        "ajax_t100sb07_1?parameters="
        "0eb65210d5bdc34ea16e295ccdbad1096cc25092fb1cb844fc81ce64c36c6b8787c33f7cb1f439f0aa513445e70aaaa6f71abe605c3d23d1030108b7cc585da0d6f2b2795"
    ),
}


# ============================================================
# HTML 文字處理
# ============================================================

def get_lines(soup):
    text = soup.get_text("\n", strip=True)

    lines = []

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()

        if line:
            lines.append(line)

    return lines


def get_value_after_label(lines, label):

    for i, line in enumerate(lines):

        if label in line:

            value = line.split(label, 1)[1].strip()

            if value:
                return value

            if i + 1 < len(lines):
                return lines[i + 1].strip()

    return ""


def get_section(lines, start_label, end_labels=None):

    end_labels = end_labels or []

    start_index = -1

    for i, line in enumerate(lines):

        if start_label in line:
            start_index = i
            break

    if start_index == -1:
        return ""

    values = []

    for line in lines[start_index + 1:]:

        if any(label in line for label in end_labels):
            break

        values.append(line)

    return " ".join(values).strip()


# ============================================================
# 日期
# ============================================================

def roc_to_ad(roc_date):

    if not roc_date:
        return ""

    match = re.search(
        r"(\d{2,3})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})",
        roc_date
    )

    if not match:
        return ""

    year = int(match.group(1)) + 1911
    month = int(match.group(2))
    day = int(match.group(3))

    return f"{year:04d}-{month:02d}-{day:02d}"


# ============================================================
# 時間
# ============================================================

def parse_time(time_text):

    if not time_text:
        return ""

    match = re.search(
        r"(\d{1,2})\s*點\s*(\d{1,2})\s*分",
        time_text
    )

    if not match:
        return ""

    hour = int(match.group(1))
    minute = int(match.group(2))

    return f"{hour:02d}:{minute:02d}"


def get_time(lines):

    for line in lines:

        if "時間" in line:

            match = re.search(
                r"(\d{1,2})\s*點\s*(\d{1,2})\s*分"
                r"(?:\s*\(24小時制\))?",
                line
            )

            if match:

                raw = match.group(0)

                return raw, parse_time(raw)

    return "", ""


# ============================================================
# PDF 連結
# ============================================================

def find_pdf_links(soup):

    links = []

    for a in soup.find_all("a", href=True):

        href = a.get("href", "").strip()

        if not href:
            continue

        absolute_url = urljoin(BASE_URL, href)

        if ".pdf" in absolute_url.lower():

            if absolute_url not in links:
                links.append(absolute_url)

    return links


# ============================================================
# HTML 外部連結
# ============================================================

def find_urls(soup):

    urls = []

    for a in soup.find_all("a", href=True):

        href = a.get("href", "").strip()

        if not href:
            continue

        absolute_url = urljoin(BASE_URL, href)

        if not absolute_url.startswith(
            ("http://", "https://")
        ):
            continue

        if ".pdf" in absolute_url.lower():
            continue

        if absolute_url not in urls:
            urls.append(absolute_url)

    return urls


# ============================================================
# 依標籤尋找連結
# ============================================================

def find_labeled_link(soup, label):

    target = None

    # --------------------------------------------------------
    # 找到包含指定標籤的文字節點
    # --------------------------------------------------------

    for element in soup.find_all(string=True):

        text = element.strip()

        if not text:
            continue

        if label in text:

            target = element
            break

    if target is None:
        return ""

    # --------------------------------------------------------
    # 第一層：往上尋找附近區塊
    # --------------------------------------------------------

    current = target.parent

    for _ in range(6):

        if current is None:
            break

        for a in current.find_all("a", href=True):

            href = a.get("href", "").strip()

            if not href:
                continue

            absolute_url = urljoin(BASE_URL, href)

            if not absolute_url.startswith(
                ("http://", "https://")
            ):
                continue

            if ".pdf" in absolute_url.lower():
                continue

            return absolute_url

        current = current.parent

    # --------------------------------------------------------
    # 第二層：檢查同層後續兄弟
    # --------------------------------------------------------

    parent = target.parent

    if parent is not None:

        for sibling in parent.next_siblings:

            if not hasattr(sibling, "find_all"):
                continue

            for a in sibling.find_all("a", href=True):

                href = a.get("href", "").strip()

                if not href:
                    continue

                absolute_url = urljoin(BASE_URL, href)

                if not absolute_url.startswith(
                    ("http://", "https://")
                ):
                    continue

                if ".pdf" in absolute_url.lower():
                    continue

                return absolute_url

    return ""


# ============================================================
# V3.2
# 公司網站連結解析
# ============================================================

def find_company_website(soup):

    label = "公司網站是否有提供法人說明會相關資訊"

    # --------------------------------------------------------
    # 1. 找到公司網站欄位的文字節點
    # --------------------------------------------------------

    target = None

    for element in soup.find_all(string=True):

        text = re.sub(r"\s+", " ", element.strip())

        if label in text:

            target = element
            break

    if target is None:
        return ""

    # --------------------------------------------------------
    # 2. 從該欄位所在的 table row 尋找 URL
    #
    # 例如：
    #
    # 公司網站是否有提供法人說明會相關資訊：
    # ○無 ●有
    # https://www.taiwancement.com/...
    #
    # --------------------------------------------------------

    row = target.parent

    while row is not None and row.name != "tr":

        row = row.parent

    if row is not None:

        links = row.find_all("a", href=True)

        for a in links:

            href = a.get("href", "").strip()

            if not href:
                continue

            absolute_url = urljoin(BASE_URL, href)

            if not absolute_url.startswith(
                ("http://", "https://")
            ):
                continue

            if ".pdf" in absolute_url.lower():
                continue

            return absolute_url

    # --------------------------------------------------------
    # 3. 如果 URL 不在同一個 <tr>，
    #    往後找相鄰的 table row。
    #
    #    只尋找少量鄰近 row，避免把後面的影音 URL
    #    誤判成公司網站。
    # --------------------------------------------------------

    if row is not None:

        next_row = row.find_next("tr")

        checked = 0

        while next_row is not None and checked < 3:

            links = next_row.find_all(
                "a",
                href=True
            )

            for a in links:

                href = a.get("href", "").strip()

                if not href:
                    continue

                absolute_url = urljoin(BASE_URL, href)

                if not absolute_url.startswith(
                    ("http://", "https://")
                ):
                    continue

                if ".pdf" in absolute_url.lower():
                    continue

                return absolute_url

            next_row = next_row.find_next("tr")
            checked += 1

    # --------------------------------------------------------
    # 4. 最後才檢查標籤所在元素附近的連結
    # --------------------------------------------------------

    current = target.parent

    for _ in range(4):

        if current is None:
            break

        for a in current.find_all("a", href=True):

            href = a.get("href", "").strip()

            if not href:
                continue

            absolute_url = urljoin(BASE_URL, href)

            if not absolute_url.startswith(
                ("http://", "https://")
            ):
                continue

            if ".pdf" in absolute_url.lower():
                continue

            return absolute_url

        current = current.parent

    return ""


# ============================================================
# MOPS AJAX 解析
# ============================================================

def parse_mops_ajax(html):

    soup = BeautifulSoup(html, "html.parser")

    lines = get_lines(soup)

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

        "pdf_links": [],
        "external_urls": [],
    }

    # ========================================================
    # 公司代號
    # ========================================================

    result["company_id"] = get_value_after_label(
        lines,
        "公司代號"
    )

    # ========================================================
    # 公司名稱
    # ========================================================

    result["company_name"] = get_value_after_label(
        lines,
        "公司名稱"
    )

    # ========================================================
    # 日期
    # ========================================================

    date_roc = get_value_after_label(
        lines,
        "召開法人說明會日期"
    )

    if not date_roc:

        date_roc = get_value_after_label(
            lines,
            "法人說明會日期"
        )

    if not date_roc:

        for line in lines:

            match = re.search(
                r"\d{2,3}/\d{1,2}/\d{1,2}",
                line
            )

            if match:

                date_roc = match.group(0)
                break

    result["date_roc"] = date_roc
    result["date"] = roc_to_ad(date_roc)

    # ========================================================
    # 時間
    # ========================================================

    time_raw, time_value = get_time(lines)

    result["time_raw"] = time_raw
    result["time"] = time_value

    # ========================================================
    # 地點
    # ========================================================

    result["location"] = get_value_after_label(
        lines,
        "召開法人說明會地點"
    )

    if not result["location"]:

        result["location"] = get_value_after_label(
            lines,
            "法人說明會地點"
        )

    # ========================================================
    # 摘要
    # ========================================================

    result["summary"] = get_value_after_label(
        lines,
        "法人說明會簡報內容"
    )

    if not result["summary"]:

        result["summary"] = get_value_after_label(
            lines,
            "法人說明會內容"
        )

    if not result["summary"]:

        for i, line in enumerate(lines):

            if "說明會" in line and "內容" in line:

                if i + 1 < len(lines):

                    result["summary"] = lines[i + 1]
                    break

    # ========================================================
    # PDF
    # ========================================================

    pdf_links = find_pdf_links(soup)

    result["pdf_links"] = pdf_links

    for pdf in pdf_links:

        lower_pdf = pdf.lower()

        if "m001" in lower_pdf:

            if not result["chinese_pdf"]:
                result["chinese_pdf"] = pdf

        elif "e001" in lower_pdf:

            if not result["english_pdf"]:
                result["english_pdf"] = pdf

    # --------------------------------------------------------
    # 如果檔名不是 M001 / E001，依順序補上
    # --------------------------------------------------------

    if not result["chinese_pdf"] and len(pdf_links) >= 1:

        result["chinese_pdf"] = pdf_links[0]

    if not result["english_pdf"] and len(pdf_links) >= 2:

        result["english_pdf"] = pdf_links[1]

    # ========================================================
    # HTML 外部連結
    # ========================================================

    result["external_urls"] = find_urls(soup)

    # ========================================================
    # 公司網站
    #
    # V3.2 修正
    # ========================================================

    result["company_website"] = find_company_website(soup)

    # ========================================================
    # 影音連結
    # ========================================================

    result["video_url"] = find_labeled_link(
        soup,
        "影音連結"
    )

    if not result["video_url"]:

        result["video_url"] = find_labeled_link(
            soup,
            "影音檔"
        )

    if not result["video_url"]:

        result["video_url"] = find_labeled_link(
            soup,
            "影音"
        )

    # ========================================================
    # 其他事項
    # ========================================================

    other = get_value_after_label(
        lines,
        "其他"
    )

    if other:
        result["other"] = other
    else:
        result["other"] = "無"

    return result


# ============================================================
# 顯示結果
# ============================================================

def print_result(stock_id, result):

    print()
    print("=" * 72)
    print(f"{stock_id}：結構化解析結果")
    print("=" * 72)

    print(f"公司代號       : {result['company_id']}")
    print(f"公司名稱       : {result['company_name']}")

    print(f"民國日期       : {result['date_roc']}")
    print(f"西元日期       : {result['date']}")

    print(f"原始時間       : {result['time_raw']}")
    print(f"標準時間       : {result['time']}")

    print(f"地點           : {result['location']}")

    print()
    print("法人說明會摘要")
    print("-" * 72)
    print(result["summary"])

    print()
    print("PDF 連結（僅列出，未下載）")

    for pdf in result["pdf_links"]:

        print(f"  URL ：{pdf}")

    print()

    print(
        f"中文 PDF       : "
        f"{result['chinese_pdf']}"
    )

    print(
        f"英文 PDF       : "
        f"{result['english_pdf']}"
    )

    print(
        f"公司網站       : "
        f"{result['company_website']}"
    )

    print(
        f"影音連結       : "
        f"{result['video_url']}"
    )

    print(
        f"其他事項       : "
        f"{result['other']}"
    )

    print()
    print("HTML 外部連結")

    for url in result["external_urls"]:

        print(f"  {url}")


# ============================================================
# 基本驗證
# ============================================================

def validate(stock_id, result):

    print()
    print("基本驗證")

    passed = True

    # --------------------------------------------------------
    # 公司代號
    # --------------------------------------------------------

    if result["company_id"] == stock_id:

        print("  PASS : 公司代號符合預期")

    else:

        print(
            "  FAIL : 公司代號不符合預期"
            f"（實際：{result['company_id']}）"
        )

        passed = False

    # --------------------------------------------------------
    # 公司名稱
    # --------------------------------------------------------

    if result["company_name"]:

        print("  PASS : 公司名稱非空")

    else:

        print("  FAIL : 公司名稱為空")
        passed = False

    # --------------------------------------------------------
    # 日期
    # --------------------------------------------------------

    if result["date"]:

        print("  PASS : 日期可轉換")

    else:

        print("  FAIL : 日期無法轉換")
        passed = False

    # --------------------------------------------------------
    # 時間
    # --------------------------------------------------------

    if result["time"]:

        print("  PASS : 時間可解析")

    else:

        print("  FAIL : 時間無法解析")
        passed = False

    # --------------------------------------------------------
    # 地點
    # --------------------------------------------------------

    if result["location"]:

        print("  PASS : 地點非空")

    else:

        print("  FAIL : 地點為空")
        passed = False

    # --------------------------------------------------------
    # 摘要
    # --------------------------------------------------------

    if result["summary"]:

        print("  PASS : 摘要非空")

    else:

        print("  FAIL : 摘要為空")
        passed = False

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if result["pdf_links"]:

        print("  PASS : 至少找到一個 PDF")

    else:

        print("  FAIL : 未找到 PDF")
        passed = False

    if result["chinese_pdf"]:

        print("  PASS : 中文 PDF 欄位")

    else:

        print("  FAIL : 中文 PDF 欄位為空")
        passed = False

    if result["english_pdf"]:

        print("  PASS : 英文 PDF 欄位")

    else:

        print("  FAIL : 英文 PDF 欄位為空")
        passed = False

    # --------------------------------------------------------
    # 公司網站
    # --------------------------------------------------------

    if result["company_website"]:

        if ".pdf" not in result["company_website"].lower():

            print(
                "  PASS : 公司網站"
                f" -> {result['company_website']}"
            )

        else:

            print(
                "  FAIL : 公司網站錯誤抓到 PDF"
            )

            passed = False

    else:

        print("  WARN : 公司網站未找到")

    # --------------------------------------------------------
    # 影音
    # --------------------------------------------------------

    if result["video_url"]:

        if ".pdf" not in result["video_url"].lower():

            print(
                "  PASS : 影音網址不是 PDF 網址"
            )

        else:

            print(
                "  FAIL : 影音網址錯誤抓到 PDF"
            )

            passed = False

    else:

        print("  WARN : 影音網址未找到")

    return passed


# ============================================================
# 主程式
# ============================================================

def main():

    print("=" * 72)
    print("MOPS AJAX 詳細資料解析測試 V3.2")
    print("測試股票：2330 台積電、1101 台泥")
    print("模式：只解析 HTML，不下載 PDF 或影音")
    print("=" * 72)

    session = requests.Session()
    session.headers.update(HEADERS)

    all_passed = True

    for stock_id, url in TEST_CASES.items():

        company_name = {
            "2330": "台積電",
            "1101": "台泥",
        }.get(stock_id, "")

        print()
        print("#" * 72)
        print(
            f"開始測試："
            f"{stock_id} {company_name}"
        )
        print("#" * 72)

        try:

            response = session.get(
                url,
                timeout=30
            )

            print(
                f"HTTP Status: "
                f"{response.status_code}"
            )

            print(
                f"Content-Type: "
                f"{response.headers.get('Content-Type', '')}"
            )

            if response.status_code != 200:

                print("FAIL : HTTP 請求失敗")

                all_passed = False
                continue

            result = parse_mops_ajax(
                response.text
            )

            print_result(
                stock_id,
                result
            )

            if not validate(
                stock_id,
                result
            ):

                all_passed = False

        except Exception as e:

            print(
                f"FAIL : 發生例外 "
                f"{type(e).__name__}: {e}"
            )

            all_passed = False

    # ========================================================
    # 測試總結
    # ========================================================

    print()
    print("=" * 72)

    if all_passed:

        print(
            "V3.2 測試：兩家公司核心欄位皆通過"
        )

    else:

        print(
            "V3.2 測試：仍有欄位需要確認"
        )

    print(
        "PDF 下載：未執行"
    )

    print(
        "影音下載：未執行"
    )

    print(
        "V3.2 測試完成"
    )

    print("=" * 72)


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()
