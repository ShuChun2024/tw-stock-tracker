import re
import logging
from pathlib import Path
from urllib.parse import urljoin

import requests


BASE_DIR = Path(__file__).resolve().parent

STOCK_ID = "6750"

URL = (
    "https://www.tpex.org.tw/"
    "zh-tw/esb/trading/info/stock-pricing.html"
)

RAW_FILE = BASE_DIR / "esb_6750_response.txt"
REPORT_FILE = BASE_DIR / "esb_6750_api_diagnostic.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)


def main():

    logger.info("=" * 65)
    logger.info("櫃買中心興櫃歷史行情網頁診斷")
    logger.info("股票代號：%s", STOCK_ID)
    logger.info("=" * 65)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
    }

    response = requests.get(
        URL,
        params={
            "type": "Monthly",
            "date": "2026/11/01",
            "code": STOCK_ID,
            "id": "",
        },
        headers=headers,
        timeout=30
    )

    logger.info("HTTP Status：%s", response.status_code)
    logger.info(
        "Content-Type：%s",
        response.headers.get("Content-Type")
    )
    logger.info("實際網址：%s", response.url)

    response.raise_for_status()

    # 使用原始 bytes 解碼，避免 requests 自動判斷編碼造成亂碼
    html = response.content.decode(
        "utf-8-sig",
        errors="replace"
    )

    RAW_FILE.write_text(
        html,
        encoding="utf-8"
    )

    logger.info("已保存原始 HTML：%s", RAW_FILE.name)

    report = []

    def add(text=""):
        report.append(str(text))

    add("=" * 65)
    add("櫃買中心興櫃行情網頁診斷報告")
    add("=" * 65)

    add(f"HTTP Status：{response.status_code}")
    add(f"Content-Type：{response.headers.get('Content-Type')}")
    add(f"URL：{response.url}")
    add(f"HTML 長度：{len(html)}")
    add()

    # --------------------------------------------------------
    # 1. 搜尋 HTML 中是否已包含行情資料
    # --------------------------------------------------------

    add("[1] HTML 資料關鍵字")

    keywords = [
        STOCK_ID,
        "泰創工程",
        "成交均價",
        "成交股數",
        "電腦議價",
        "系統外議價",
        "下載 CSV",
        "stock-pricing",
    ]

    for keyword in keywords:
        add(
            f"{keyword}："
            f"{'找到' if keyword in html else '未找到'}"
        )

    add()

    # --------------------------------------------------------
    # 2. 擷取 JavaScript 檔案
    # --------------------------------------------------------

    add("[2] JavaScript 檔案")

    script_pattern = re.compile(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        re.IGNORECASE
    )

    script_urls = script_pattern.findall(html)

    for script_url in script_urls:

        full_url = urljoin(
            response.url,
            script_url
        )

        add(full_url)

    add()

    # --------------------------------------------------------
    # 3. 擷取表單
    # --------------------------------------------------------

    add("[3] HTML 表單")

    forms = re.findall(
        r'<form\b[^>]*>.*?</form>',
        html,
        flags=re.IGNORECASE | re.DOTALL
    )

    for form in forms:
        add(form[:5000])

    if not forms:
        add("沒有找到 form 標籤")

    add()

    # --------------------------------------------------------
    # 4. 搜尋可能的 API 關鍵字
    # --------------------------------------------------------

    add("[4] HTML 中的 API 線索")

    patterns = [
        r'.{0,150}ajax.{0,250}',
        r'.{0,150}fetch\s*\(.{0,250}',
        r'.{0,150}axios.{0,250}',
        r'.{0,150}response\s*:\s*["\']json["\'].{0,250}',
        r'.{0,150}download.{0,250}',
        r'.{0,150}csv.{0,250}',
        r'.{0,150}stock-pricing.{0,250}',
        r'.{0,150}成交均價.{0,250}',
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        if matches:
            add(f"\nPattern：{pattern}")

            for match in matches[:20]:
                add(
                    re.sub(r"\s+", " ", match).strip()
                )

    add()

    # --------------------------------------------------------
    # 5. 下載 JavaScript 並搜尋 API 線索
    # --------------------------------------------------------

    add("[5] JavaScript 內容檢查")

    session = requests.Session()
    session.headers.update(headers)

    for script_url in script_urls:

        full_url = urljoin(
            response.url,
            script_url
        )

        try:

            js_response = session.get(
                full_url,
                timeout=30
            )

            add()
            add(f"JavaScript：{full_url}")
            add(f"HTTP：{js_response.status_code}")

            if js_response.status_code != 200:
                continue

            js = js_response.content.decode(
                "utf-8-sig",
                errors="replace"
            )

            js_patterns = [
                r'.{0,150}ajax.{0,250}',
                r'.{0,150}fetch\s*\(.{0,250}',
                r'.{0,150}axios.{0,250}',
                r'.{0,150}response\s*:\s*["\']json["\'].{0,250}',
                r'.{0,150}stock-pricing.{0,250}',
                r'.{0,150}csv.{0,250}',
            ]

            for pattern in js_patterns:

                matches = re.findall(
                    pattern,
                    js,
                    flags=re.IGNORECASE | re.DOTALL
                )

                for match in matches[:10]:
                    add(
                        re.sub(r"\s+", " ", match).strip()
                    )

        except Exception as exc:

            add(f"下載失敗：{exc}")

    add()
    add("=" * 65)
    add("診斷結束")
    add("=" * 65)

    REPORT_FILE.write_text(
        "\n".join(report),
        encoding="utf-8"
    )

    logger.info("診斷報告：%s", REPORT_FILE.name)
    logger.info("原始 HTML：%s", RAW_FILE.name)

    logger.info("請下載 GitHub Actions Artifact 檢查結果")


if __name__ == "__main__":
    main()
