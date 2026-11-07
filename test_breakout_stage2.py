import copy
import unittest

import breakout


# ============================================================
# breakout.py 第二階段 A 組獨立測試
#
# 測試範圍：
# 1. 股票代號格式
# 2. 股票字典 key 與 stock_id 一致性
# 3. 必要欄位完整性
# 4. 日期格式及有效性
# 5. stock_count 一致性
# 6. 歷史紀錄格式
# 7. 無效觀察清單不得部分修改狀態
#
# 不測試：
# - active_trade 完整欄位
# - 進場及出場價格
# - MFE / MAE
# - 下一交易日開盤成交
#
# 不修改正式 breakout.py。
# 所有測試均在記憶體中執行。
# ============================================================


class TestBreakoutStage2A(unittest.TestCase):

    def setUp(self):
        """建立標準有效測試狀態。"""

        self.state = breakout.create_empty_state()

        breakout.sync_watchlist(
            self.state,
            ["2330", "2454"]
        )

        self.state["stock_count"] = 2

    # --------------------------------------------------------
    # 測試 1：股票代號格式
    # --------------------------------------------------------

    def test_01_stock_id_validation(self):

        # 合法輸入及預期結果
        valid_cases = [
            ("2330", "2330"),
            ("2454", "2454"),
            ("1101", "1101"),
            (2330, "2330"),
            (" 2330 ", "2330"),
            ("675", "0675")
        ]

        for stock_id, expected in valid_cases:

            with self.subTest(stock_id=stock_id):

                result = breakout.normalize_stock_id(
                    stock_id
                )

                self.assertEqual(
                    result,
                    expected
                )

        # 不合法輸入
        invalid_cases = [
            None,
            "",
            "   ",
            "ABC",
            "23A0",
            True,
            False,
            23.5,
            [],
            {}
        ]

        for stock_id in invalid_cases:

            with self.subTest(stock_id=stock_id):

                with self.assertRaises(
                    (ValueError, TypeError)
                ):

                    breakout.normalize_stock_id(
                        stock_id
                    )

    # --------------------------------------------------------
    # 測試 2：股票字典 key 與 stock_id 必須一致
    # --------------------------------------------------------

    def test_02_stock_key_consistency(self):

        # 正常狀態必須通過
        self.assertTrue(
            breakout.validate_state(
                copy.deepcopy(self.state)
            )
        )

        # 修改 stock_id，製造 key 不一致
        invalid_state = copy.deepcopy(
            self.state
        )

        invalid_state["stocks"]["2330"][
            "stock_id"
        ] = "2454"

        with self.assertRaises(ValueError):

            breakout.validate_state(
                invalid_state
            )

        # key 本身不是合法股票代號
        invalid_state = copy.deepcopy(
            self.state
        )

        invalid_state["stocks"]["ABC"] = (
            invalid_state["stocks"].pop("2330")
        )

        with self.assertRaises(
            (ValueError, TypeError)
        ):

            breakout.validate_state(
                invalid_state
            )

    # --------------------------------------------------------
    # 測試 3：必要欄位完整性
    # --------------------------------------------------------

    def test_03_required_fields(self):

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

                invalid_state = copy.deepcopy(
                    self.state
                )

                del invalid_state["stocks"]["2330"][
                    field
                ]

                with self.assertRaises(ValueError):

                    breakout.validate_state(
                        invalid_state
                    )

    # --------------------------------------------------------
    # 測試 4：日期格式及有效性
    # --------------------------------------------------------

    def test_04_date_validation(self):

        # 合法日期
        valid_dates = [
            "2026-01-01",
            "2026-11-07",
            "2024-02-29"
        ]

        for date_value in valid_dates:

            with self.subTest(date=date_value):

                valid_state = copy.deepcopy(
                    self.state
                )

                valid_state["stocks"]["2330"][
                    "last_processed_date"
                ] = date_value

                self.assertTrue(
                    breakout.validate_state(
                        valid_state
                    )
                )

        # 不合法日期
        invalid_dates = [
            "2026/11/07",
            "2026-13-01",
            "2026-02-30",
            "20261107",
            "not-a-date",
            "",
            20261107
        ]

        for date_value in invalid_dates:

            with self.subTest(date=date_value):

                invalid_state = copy.deepcopy(
                    self.state
                )

                invalid_state["stocks"]["2330"][
                    "last_processed_date"
                ] = date_value

                with self.assertRaises(ValueError):

                    breakout.validate_state(
                        invalid_state
                    )

    # --------------------------------------------------------
    # 測試 5：stock_count 必須與實際數量一致
    # --------------------------------------------------------

    def test_05_stock_count_consistency(self):

        valid_state = copy.deepcopy(
            self.state
        )

        valid_state["stock_count"] = 2

        self.assertTrue(
            breakout.validate_state(
                valid_state
            )
        )

        invalid_counts = [
            0,
            1,
            3,
            999,
            -1,
            "2",
            None
        ]

        for count in invalid_counts:

            with self.subTest(stock_count=count):

                invalid_state = copy.deepcopy(
                    self.state
                )

                invalid_state["stock_count"] = count

                with self.assertRaises(ValueError):

                    breakout.validate_state(
                        invalid_state
                    )

    # --------------------------------------------------------
    # 測試 6：訊號及交易歷史紀錄格式
    # --------------------------------------------------------

    def test_06_history_record_validation(self):

        invalid_records = [
            None,
            "invalid",
            123,
            [],
            True
        ]

        for record in invalid_records:

            with self.subTest(record=record):

                invalid_state = copy.deepcopy(
                    self.state
                )

                invalid_state["stocks"]["2330"][
                    "signal_history"
                ] = [record]

                with self.assertRaises(ValueError):

                    breakout.validate_state(
                        invalid_state
                    )

                invalid_state = copy.deepcopy(
                    self.state
                )

                invalid_state["stocks"]["2330"][
                    "trade_history"
                ] = [record]

                with self.assertRaises(ValueError):

                    breakout.validate_state(
                        invalid_state
                    )

        # 合法的歷史紀錄必須接受
        valid_state = copy.deepcopy(
            self.state
        )

        valid_state["stocks"]["2330"][
            "signal_history"
        ] = [
            {
                "date": "2026-11-06",
                "signal": "watch"
            }
        ]

        valid_state["stocks"]["2330"][
            "trade_history"
        ] = [
            {
                "entry_date": "2026-10-01",
                "exit_date": "2026-10-10"
            }
        ]

        self.assertTrue(
            breakout.validate_state(
                valid_state
            )
        )

    # --------------------------------------------------------
    # 測試 7：無效觀察清單不得部分修改原狀態
    # --------------------------------------------------------

    def test_07_invalid_watchlist_no_partial_change(self):

        invalid_watchlists = [
            ["2330", None, "2454"],
            ["2330", "", "2454"],
            ["2330", "ABC", "2454"],
            ["2330", True, "2454"]
        ]

        for watchlist in invalid_watchlists:

            with self.subTest(watchlist=watchlist):

                state = copy.deepcopy(
                    self.state
                )

                original = copy.deepcopy(
                    state
                )

                with self.assertRaises(
                    (ValueError, TypeError)
                ):

                    breakout.sync_watchlist(
                        state,
                        watchlist
                    )

                # 失敗後原始狀態完全不能改變
                self.assertEqual(
                    state,
                    original
                )

    # --------------------------------------------------------
    # 測試 8：空白及重複觀察清單
    # --------------------------------------------------------

    def test_08_watchlist_normalization(self):

        state = breakout.create_empty_state()

        breakout.sync_watchlist(
            state,
            ["2330", " 2330 ", "2454"]
        )

        # 相同股票不能建立兩筆紀錄
        self.assertEqual(
            len(state["stocks"]),
            2
        )

        self.assertIn(
            "2330",
            state["stocks"]
        )

        self.assertIn(
            "2454",
            state["stocks"]
        )

        self.assertTrue(
            state["stocks"]["2330"]["watchlist_active"]
        )


# ============================================================
# 執行測試
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("breakout.py 第二階段 A 組資料安全測試")
    print("=" * 60)

    unittest.main(verbosity=2)
