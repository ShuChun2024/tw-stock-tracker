import requests

url = "https://mops.twse.com.tw/mops/web/index"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

print("=" * 70)
print("MOPS 最小連線測試")
print("=" * 70)

try:

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
        allow_redirects=True
    )

    print("HTTP Status :", response.status_code)
    print("最終 URL    :", response.url)
    print("Content-Type:", response.headers.get("Content-Type"))
    print("HTML 長度   :", len(response.text))

    print()
    print("=== 回應前 500 字 ===")
    print(response.text[:500])

except Exception as e:

    print("發生錯誤：", repr(e))
