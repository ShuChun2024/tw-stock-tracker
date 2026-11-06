import json
import logging
from pathlib import Path

from stock_price import (
    fetch_stock_history,
    WEEKDAYS,
)


# ============================================================
# 測試設定
# ============================================================

TEST_STOCKS = [
    {
        "stock_id": "2330",
        "stock_name": "台積電",
        "market": "TWSE",
    },
    {
        "stock_id": "2454",
        "stock_name": "聯發科",
        "market": "TWSE",
    },
    {
        "stock_id": "2317",
        "stock_name": "鴻海",
        "market": "TWSE",
    },
    {
        "stock_id": "2603",
        "stock_name": "長榮",
        "market": "TWSE",
    },
]

BASE_DIR = Path(__file__).resolve().parent
TEST_OUTPUT = BASE_DIR / "stock_prices_test.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# 測試資料
# ============================================================

def validate_history(stock_id, history):
    """檢查近 5 日資料格式與正確性。"""

    assert isinstance(history, list), (
        f"{stock_id}：行情資料不是 List"
    )

    assert len(history) == 5, (
        f"{stock_id}：應有 5 筆資料，實際 {len(history)} 筆"
    )

    dates = [
        item["date"]
        for item in history
    ]

    assert len(set(dates)) == 5, (
        f"{stock_id}：交易日期有重複"
    )

    assert dates == sorted(
        dates,
        reverse=True,
    ), (
        f"{stock_id}：日期沒有由新到舊排序"
    )

    for item in history:

        assert item["close"] is not None, (
            f"{stock_id} {item['date']}：缺少收盤價"
        )

        assert item["weekday"] in WEEKDAYS, (
            f"{stock_id} {item['date']}：星期格式錯誤"
        )

        assert item["date"], (
            f"{stock_id}：缺少交易日期"
        )

        # 漲跌價差與漲跌幅允許 None，
        # 例如官方資料暫時無法提供比較值時。
        if item["change"] is not None:
            assert isinstance(
                item["change"],
                (int, float),
            )

        if item["change_percent"] is not None:
            assert isinstance(
                item["change_percent"],
                (int, float),
            )

    return True


# ============================================================
# 執行測試
# ============================================================

def main():

    logger.info("=" * 65)
    logger.info("近 5 個交易日收盤行情測試")
    logger.info("=" * 65)

    output_stocks = []
    success_count = 0
    failed_count = 0

    for stock in TEST_STOCKS:

        stock_id = stock["stock_id"]
        stock_name = stock["stock_name"]
        market = stock["market"]

        logger.info("")
        logger.info("-" * 65)
        logger.info(
            "測試股票：%s %s",
            stock_id,
            stock_name,
        )

        try:
            history = fetch_stock_history(
                stock_id,
                market,
            )

            validate_history(
                stock_id,
                history,
            )

            output_stocks.append({
                "stock_id": stock_id,
                "stock_name": stock_name,
                "market": market,
                "data": history,
            })

            success_count += 1

            logger.info("資料驗證成功")

            print("")
            print(
                f"{stock_id} {stock_name} "
                f"近 5 個交易日行情"
            )

            print(
                f"{'日期':<15}"
                f"{'收盤價':>12}"
                f"{'漲跌價':>12}"
                f"{'漲跌幅':>12}"
            )

            print("-" * 55)

            for item in history:

                date_text = (
                    f"{item['date']} "
                    f"({item['weekday']})"
                )

                close_text = str(item["close"])

                change_text = (
                    str(item["change"])
                    if item["change"] is not None
                    else "無資料"
                )

                percent_text = (
                    f"{item['change_percent']:.2f}%"
                    if item["change_percent"] is not None
                    else "無資料"
                )

                print(
                    f"{date_text:<20}"
                    f"{close_text:>10}"
                    f"{change_text:>12}"
                    f"{percent_text:>12}"
                )

        except Exception as exc:

            failed_count += 1

            logger.exception(
                "%s %s 測試失敗：%s",
                stock_id,
                stock_name,
                exc,
            )

    # ========================================================
    # 輸出測試 JSON
    # ========================================================

    result = {
        "stock_count": len(output_stocks),
        "failed_count": failed_count,
        "days": 5,
        "stocks": output_stocks,
    }

    with open(
        TEST_OUTPUT,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # ========================================================
    # 測試摘要
    # ========================================================

    print("")
    print("=" * 65)
    print("測試結果摘要")
    print("=" * 65)
    print(f"測試股票：{len(TEST_STOCKS)}")
    print(f"成功：{success_count}")
    print(f"失敗：{failed_count}")
    print(f"測試 JSON：{TEST_OUTPUT}")
    print("=" * 65)


if __name__ == "__main__":
    main()
