import requests
from bs4 import BeautifulSoup


# ============================================================
# MOPS AJAX 測試
# ============================================================

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


def main():
    print("=" * 70)
    print("MOPS AJAX 詳細資料測試")
    print("=" * 70)

    print("\n[1] Request URL")
    print(URL)

    try:
        response = requests.get(
            URL,
            headers=HEADERS,
            timeout=30,
        )
    except Exception as e:
        print("\nRequest 失敗：")
        print(type(e).__name__, e)
        return

    print("\n[2] HTTP 狀態")
    print("Status Code:", response.status_code)
    print("Final URL:", response.url)

    print("\n[3] Response Headers")
    print("Content-Type:", response.headers.get("Content-Type"))
    print("Content-Length:", response.headers.get("Content-Length"))

    print("\n[4] Response 前 1000 字元")
    print("-" * 70)
    print(response.text[:1000])
    print("-" * 70)

    # --------------------------------------------------------
    # 嘗試解析 HTML
    # --------------------------------------------------------

    print("\n[5] HTML 解析")

    soup = BeautifulSoup(response.text, "html.parser")

    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    print("HTML Title:", title)

    text = soup.get_text("\n", strip=True)

    print("\n[6] 純文字內容")
    print("-" * 70)
    print(text[:5000])
    print("-" * 70)

    # --------------------------------------------------------
    # 列出所有連結
    # --------------------------------------------------------

    print("\n[7] 找到的連結")

    links = soup.find_all("a")

    print("連結數量:", len(links))

    for i, link in enumerate(links, 1):
        href = link.get("href")
        name = link.get_text(" ", strip=True)

        if href or name:
            print(f"[{i}]")
            print("  文字:", name)
            print("  href:", href)

    print("\n" + "=" * 70)
    print("測試完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
