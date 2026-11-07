import copy
import unittest

import breakout


class TestBreakoutStage2(unittest.TestCase):

    def setUp(self):
        self.state = breakout.create_empty_state()
        breakout.sync_watchlist(
            self.state,
            ["2330", "2454"]
        )
        self.state["stock_count"] = 2

    def valid_stock_state(self, stock_id="2330"):
        return breakout.create_stock_state(stock_id)

    # --------------------------------------------------------
    # 1. 股票代號驗證
    # --------------------------------------------------------

    def test_01_invalid_stock_id(self):
        invalid_ids = [
            None,
            "",
            "   ",
            "ABC",
            "23A0",
            True
        ]

        for stock_id in invalid_ids:
            with self.subTest(stock_id=stock_id):
                with self.assertRaises((ValueError, TypeError)):
                    breakout.normalize_stock_id(stock_id)

    # --------------------------------------------------------
    # 2. 股票字典 key 與 stock_id 必須一致
    # --------------------------------------------------------

    def test_02_stock_key_mismatch(self):
        state = copy.deepcopy(self.state)

        state["stocks"]["2330"]["stock_id"] = "2454"

        with self.assertRaises(ValueError):
            breakout.validate_state(state)

    # --------------------------------------------------------
    # 3. 必要欄位不可缺少
    # --------------------------------------------------------

    def test_03_missing_required_field(self):
        required_fields = [
            "stock_id",
            "watchlist_active",
            "status",
            "last_processed_date",
            "watch_signal",
            "entry_signal",
            "exit_signal",
            "active_trade",
            "signal_history",
            "trade_history",
            "updated_at"
        ]

        for field in required_fields:
            with self.subTest(field=field):
                state = copy.deepcopy(self.state)

                del state["stocks"]["2330"][field]

                with self.assertRaises(ValueError):
                    breakout.validate_state(state)

    # --------------------------------------------------------
    # 4. 日期格式驗證
    # --------------------------------------------------------

    def test_04_invalid_last_processed_date(self):
        invalid_dates = [
            "2026/11/07",
            "2026-13-01",
            "2026-02-30",
            "20261107",
            "not-a-date"
        ]

        for date_value in invalid_dates:
            with self.subTest(date=date_value):
                state = copy.deepcopy(self.state)

                state["stocks"]["2330"][
                    "last_processed_date"
                ] = date_value

                with self.assertRaises(ValueError):
                    breakout.validate_state(state)

    # --------------------------------------------------------
    # 5. stock_count 必須正確
    # --------------------------------------------------------

    def test_05_stock_count_mismatch(self):
        state = copy.deepcopy(self.state)

        state["stock_count"] = 999

        with self.assertRaises(ValueError):
            breakout.validate_state(state)

    # --------------------------------------------------------
    # 6. holding 必須有完整有效交易
    # --------------------------------------------------------

    def test_06_invalid_active_trade(self):
        invalid_trades = [
            {},
            {"entry_date": "2026-11-06"},
            {
                "entry_date": "2026-11-06",
                "entry_price": None
            },
            {
                "entry_date": "2026-11-06",
                "entry_price": 100,
                "exit_date": "2026-11-06",
                "exit_price": 101
            }
        ]

        for trade in invalid_trades:
            with self.subTest(trade=trade):
                state = copy.deepcopy(self.state)

                stock = state["stocks"]["2330"]
                stock["status"] = "holding"
                stock["active_trade"] = trade

                with self.assertRaises(ValueError):
                    breakout.validate_state(state)

    # --------------------------------------------------------
    # 7. 歷史紀錄必須是有效物件
    # --------------------------------------------------------

    def test_07_invalid_history_records(self):
        invalid_records = [
            None,
            "invalid",
            123,
            []
        ]

        for record in invalid_records:
            with self.subTest(record=record):

                state = copy.deepcopy(self.state)

                state["stocks"]["2330"][
                    "signal_history"
                ] = [record]

                with self.assertRaises(ValueError):
                    breakout.validate_state(state)

                state = copy.deepcopy(self.state)

                state["stocks"]["2330"][
                    "trade_history"
                ] = [record]

                with self.assertRaises(ValueError):
                    breakout.validate_state(state)

    # --------------------------------------------------------
    # 8. 無效觀察清單不得部分修改原狀態
    # --------------------------------------------------------

    def test_08_invalid_watchlist_no_partial_change(self):
        state = copy.deepcopy(self.state)
        original = copy.deepcopy(state)

        with self.assertRaises((ValueError, TypeError)):
            breakout.sync_watchlist(
                state,
                ["2330", None, "2454"]
            )

        self.assertEqual(state, original)


if __name__ == "__main__":

    print("=" * 60)
    print("breakout.py 第二階段資料安全測試")
    print("=" * 60)

    unittest.main(verbosity=2)
