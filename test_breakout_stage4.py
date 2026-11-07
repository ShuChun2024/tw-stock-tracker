import copy
import tempfile
import unittest

from pathlib import Path

from breakout import (
    create_empty_state,
    sync_watchlist,
    process_breakout_stock,
    save_breakout_state,
    load_breakout_state,
)


# ============================================================
# 1. 測試資料
# ============================================================

STOCK_ID = "2330"


def create_market_result(
    date,
    open_price=100,
    high_price=105,
    low_price=95,
    close_price=102,
    buy_signal=False,
    stop_condition=False
):
    """
    模擬 technical.py 的實際輸出結構。

    注意：
    這裡依照目前 breakout.py 的 extract_breakout_data()
    所要求的欄位建立測試資料。
    """

    return {
        "technical": {
            "breakout_strategy": {
                "data_available": True,
                "latest_date": date,

                "candle": {
                    "open": open_price,
                    "close": close_price
                },

                "latest_high": high_price,
                "latest_low": low_price,

                "conditions": {
                    "buy_signal": buy_signal
                },

                "stop_condition_met": stop_condition
            }
        }
    }


def create_test_state():
    state = create_empty_state()

    sync_watchlist(
        state,
        [STOCK_ID]
    )

    return state


def create_buy_signal(state):
    """
    建立 2026-11-02 買進訊號。
    """

    result = create_market_result(
        date="2026-11-02",
        open_price=100,
        high_price=103,
        low_price=98,
        close_price=102,
        buy_signal=True
    )

    process_breakout_stock(
        state,
        STOCK_ID,
        result
    )


def create_holding_state():
    """
    建立已於 2026-11-03 進場的持倉狀態。
    """

    state = create_test_state()

    create_buy_signal(state)

    result = create_market_result(
        date="2026-11-03",
        open_price=100,
        high_price=110,
        low_price=95,
        close_price=108
    )

    process_breakout_stock(
        state,
        STOCK_ID,
        result
    )

    return state


# ============================================================
# 2. Stage 4 交易流程測試
# ============================================================

class TestBreakoutTradeFlow(unittest.TestCase):

    def setUp(self):
        self.state = create_test_state()

    # --------------------------------------------------------
    # 測試 01：買進訊號日只建立訊號，不立即進場
    # --------------------------------------------------------

    def test_01_buy_signal_creates_pending_entry(self):

        create_buy_signal(self.state)

        item = self.state["stocks"][STOCK_ID]

        self.assertEqual(
            item["status"],
            "watching"
        )

        self.assertIsNone(
            item["active_trade"]
        )

        self.assertEqual(
            item["entry_signal"]["date"],
            "2026-11-02"
        )

        self.assertEqual(
            len(item["signal_history"]),
            1
        )

        self.assertEqual(
            item["last_processed_date"],
            "2026-11-02"
        )

    # --------------------------------------------------------
    # 測試 02：下一交易日開盤價進場
    # --------------------------------------------------------

    def test_02_entry_on_next_trading_day_open(self):

        create_buy_signal(self.state)

        result = create_market_result(
            date="2026-11-03",
            open_price=100,
            high_price=110,
            low_price=95,
            close_price=108
        )

        changed = process_breakout_stock(
            self.state,
            STOCK_ID,
            result
        )

        item = self.state["stocks"][STOCK_ID]
        trade = item["active_trade"]

        self.assertTrue(changed)

        self.assertEqual(
            item["status"],
            "holding"
        )

        self.assertEqual(
            trade["entry_signal_date"],
            "2026-11-02"
        )

        self.assertEqual(
            trade["entry_date"],
            "2026-11-03"
        )

        self.assertEqual(
            trade["entry_price"],
            100
        )

        self.assertEqual(
            trade["holding_days"],
            1
        )

        self.assertEqual(
            trade["highest_price"],
            110
        )

        self.assertEqual(
            trade["lowest_price"],
            95
        )

        self.assertEqual(
            trade["mfe_pct"],
            10.0
        )

        self.assertEqual(
            trade["mae_pct"],
            -5.0
        )

        self.assertIsNone(
            item["entry_signal"]
        )

    # --------------------------------------------------------
    # 測試 03：持倉期間更新 MFE、MAE、holding_days
    # --------------------------------------------------------

    def test_03_update_holding_extremes_and_days(self):

        self.state = create_holding_state()

        result = create_market_result(
            date="2026-11-04",
            open_price=108,
            high_price=115,
            low_price=90,
            close_price=100
        )

        changed = process_breakout_stock(
            self.state,
            STOCK_ID,
            result
        )

        trade = self.state["stocks"][STOCK_ID]["active_trade"]

        self.assertTrue(changed)

        self.assertEqual(
            trade["holding_days"],
            2
        )

        self.assertEqual(
            trade["highest_price"],
            115
        )

        self.assertEqual(
            trade["lowest_price"],
            90
        )

        self.assertEqual(
            trade["mfe_pct"],
            15.0
        )

        self.assertEqual(
            trade["mae_pct"],
            -10.0
        )

    # --------------------------------------------------------
    # 測試 04：收盤跌破中軌，建立待出場訊號
    # --------------------------------------------------------

    def test_04_stop_signal_waits_for_next_day(self):

        self.state = create_holding_state()

        result = create_market_result(
            date="2026-11-04",
            open_price=108,
            high_price=115,
            low_price=90,
            close_price=95,
            stop_condition=True
        )

        process_breakout_stock(
            self.state,
            STOCK_ID,
            result
        )

        item = self.state["stocks"][STOCK_ID]
        trade = item["active_trade"]

        self.assertIsNotNone(trade)

        self.assertEqual(
            item["status"],
            "holding"
        )

        self.assertEqual(
            trade["pending_exit_date"],
            "2026-11-04"
        )

        self.assertEqual(
            trade["pending_exit_reason"],
            "收盤跌破布林中軌"
        )

        self.assertEqual(
            item["exit_signal"]["date"],
            "2026-11-04"
        )

        self.assertEqual(
            item["signal_history"][-1]["type"],
            "stop"
        )

        self.assertEqual(
            trade["holding_days"],
            2
        )

        self.assertEqual(
            len(item["trade_history"]),
            0
        )

    # --------------------------------------------------------
    # 測試 05：下一交易日開盤價出場
    # --------------------------------------------------------

    def test_05_exit_on_next_trading_day_open(self):

        self.state = create_holding_state()

        stop_result = create_market_result(
            date="2026-11-04",
            open_price=108,
            high_price=115,
            low_price=90,
            close_price=95,
            stop_condition=True
        )

        process_breakout_stock(
            self.state,
            STOCK_ID,
            stop_result
        )

        exit_result = create_market_result(
            date="2026-11-05",
            open_price=98,
            high_price=120,
            low_price=80,
            close_price=85
        )

        changed = process_breakout_stock(
            self.state,
            STOCK_ID,
            exit_result
        )

        item = self.state["stocks"][STOCK_ID]

        self.assertTrue(changed)

        self.assertIsNone(
            item["active_trade"]
        )

        self.assertEqual(
            item["status"],
            "stopped"
        )

        self.assertEqual(
            len(item["trade_history"]),
            1
        )

        trade = item["trade_history"][0]

        self.assertEqual(
            trade["entry_price"],
            100
        )

        self.assertEqual(
            trade["exit_date"],
            "2026-11-05"
        )

        self.assertEqual(
            trade["exit_price"],
            98
        )

        self.assertEqual(
            trade["exit_reason"],
            "收盤跌破布林中軌"
        )

        self.assertEqual(
            trade["return_pct"],
            -2.0
        )

        # 進場日、持倉日、出場日共 3 天。
        self.assertEqual(
            trade["holding_days"],
            3
        )

        # 出場日開盤後的最高價 120、最低價 80
        # 不納入持倉績效。
        self.assertEqual(
            trade["highest_price"],
            115
        )

        self.assertEqual(
            trade["lowest_price"],
            90
        )

        self.assertEqual(
            trade["mfe_pct"],
            15.0
        )

        self.assertEqual(
            trade["mae_pct"],
            -10.0
        )

        self.assertEqual(
            item["exit_signal"]["execution_date"],
            "2026-11-05"
        )

    # --------------------------------------------------------
    # 測試 06：同一交易日重複執行不得重複進場
    # --------------------------------------------------------

    def test_06_duplicate_entry_day_is_ignored(self):

        create_buy_signal(self.state)

        result = create_market_result(
            date="2026-11-03",
            open_price=100,
            high_price=110,
            low_price=95
        )

        first_result = process_breakout_stock(
            self.state,
            STOCK_ID,
            result
        )

        trade_before = copy.deepcopy(
            self.state["stocks"][STOCK_ID]["active_trade"]
        )

        second_result = process_breakout_stock(
            self.state,
            STOCK_ID,
            result
        )

        trade_after = self.state["stocks"][STOCK_ID]["active_trade"]

        self.assertTrue(first_result)
        self.assertFalse(second_result)

        self.assertEqual(
            trade_before,
            trade_after
        )

        self.assertEqual(
            trade_after["holding_days"],
            1
        )

    # --------------------------------------------------------
    # 測試 07：缺少出場日開盤價，不可提前完成交易
    # --------------------------------------------------------

    def test_07_missing_exit_open_keeps_pending_trade(self):

        self.state = create_holding_state()

        stop_result = create_market_result(
            date="2026-11-04",
            stop_condition=True
        )

        process_breakout_stock(
            self.state,
            STOCK_ID,
            stop_result
        )

        item = self.state["stocks"][STOCK_ID]

        missing_open_result = create_market_result(
            date="2026-11-05",
            open_price=None
        )

        changed = process_breakout_stock(
            self.state,
            STOCK_ID,
            missing_open_result
        )

        self.assertFalse(changed)

        self.assertIsNotNone(
            item["active_trade"]
        )

        self.assertEqual(
            item["active_trade"]["pending_exit_date"],
            "2026-11-04"
        )

        self.assertEqual(
            item["last_processed_date"],
            "2026-11-04"
        )

        self.assertEqual(
            len(item["trade_history"]),
            0
        )

        # 同一交易日資料補齊後，允許重新處理。
        corrected_result = create_market_result(
            date="2026-11-05",
            open_price=98,
            high_price=100,
            low_price=96
        )

        changed = process_breakout_stock(
            self.state,
            STOCK_ID,
            corrected_result
        )

        self.assertTrue(changed)

        self.assertIsNone(
            item["active_trade"]
        )

        self.assertEqual(
            len(item["trade_history"]),
            1
        )

    # --------------------------------------------------------
    # 測試 08：缺少進場日高低價，不可建立持倉
    # --------------------------------------------------------

    def test_08_missing_entry_high_low_keeps_signal(self):

        create_buy_signal(self.state)

        result = create_market_result(
            date="2026-11-03",
            open_price=100,
            high_price=None,
            low_price=95
        )

        changed = process_breakout_stock(
            self.state,
            STOCK_ID,
            result
        )

        item = self.state["stocks"][STOCK_ID]

        self.assertFalse(changed)

        self.assertIsNone(
            item["active_trade"]
        )

        self.assertIsNotNone(
            item["entry_signal"]
        )

        self.assertEqual(
            item["last_processed_date"],
            "2026-11-02"
        )

        # 補齊資料後，允許同一交易日重新處理。
        corrected_result = create_market_result(
            date="2026-11-03",
            open_price=100,
            high_price=110,
            low_price=95
        )

        changed = process_breakout_stock(
            self.state,
            STOCK_ID,
            corrected_result
        )

        self.assertTrue(changed)

        self.assertIsNotNone(
            item["active_trade"]
        )

    # --------------------------------------------------------
    # 測試 09：持倉日缺少高低價，不更新交易資料
    # --------------------------------------------------------

    def test_09_missing_holding_high_low_does_not_update(self):

        self.state = create_holding_state()

        item = self.state["stocks"][STOCK_ID]

        trade_before = copy.deepcopy(
            item["active_trade"]
        )

        result = create_market_result(
            date="2026-11-04",
            high_price=None,
            low_price=90
        )

        changed = process_breakout_stock(
            self.state,
            STOCK_ID,
            result
        )

        self.assertFalse(changed)

        self.assertEqual(
            item["active_trade"],
            trade_before
        )

        self.assertEqual(
            item["last_processed_date"],
            "2026-11-03"
        )

        # 補齊資料後再處理。
        corrected_result = create_market_result(
            date="2026-11-04",
            high_price=115,
            low_price=90
        )

        changed = process_breakout_stock(
            self.state,
            STOCK_ID,
            corrected_result
        )

        self.assertTrue(changed)

        self.assertEqual(
            item["active_trade"]["holding_days"],
            2
        )

    # --------------------------------------------------------
    # 測試 10：最高價低於最低價，應拒絕錯誤資料
    # --------------------------------------------------------

    def test_10_invalid_high_low_raises_error(self):

        create_buy_signal(self.state)

        result = create_market_result(
            date="2026-11-03",
            open_price=100,
            high_price=90,
            low_price=95
        )

        with self.assertRaises(ValueError):

            process_breakout_stock(
                self.state,
                STOCK_ID,
                result
            )

        item = self.state["stocks"][STOCK_ID]

        self.assertIsNone(
            item["active_trade"]
        )

        self.assertEqual(
            item["last_processed_date"],
            "2026-11-02"
        )

    # --------------------------------------------------------
    # 測試 11：儲存、重新載入後，待出場交易仍可執行
    # --------------------------------------------------------

    def test_11_save_load_pending_exit_continuity(self):

        self.state = create_holding_state()

        stop_result = create_market_result(
            date="2026-11-04",
            high_price=115,
            low_price=90,
            stop_condition=True
        )

        process_breakout_stock(
            self.state,
            STOCK_ID,
            stop_result
        )

        with tempfile.TemporaryDirectory() as temp_dir:

            state_file = Path(temp_dir) / "breakout_state.json"

            save_breakout_state(
                self.state,
                state_file
            )

            loaded_state = load_breakout_state(
                state_file
            )

            item = loaded_state["stocks"][STOCK_ID]

            self.assertIsNotNone(
                item["active_trade"]
            )

            self.assertEqual(
                item["active_trade"]["pending_exit_date"],
                "2026-11-04"
            )

            # 載入後，下一交易日仍能正常出場。
            exit_result = create_market_result(
                date="2026-11-05",
                open_price=98,
                high_price=100,
                low_price=96
            )

            changed = process_breakout_stock(
                loaded_state,
                STOCK_ID,
                exit_result
            )

            self.assertTrue(changed)

            self.assertIsNone(
                loaded_state["stocks"][STOCK_ID]["active_trade"]
            )

            self.assertEqual(
                len(loaded_state["stocks"][STOCK_ID]["trade_history"]),
                1
            )


# ============================================================
# 3. 執行測試
# ============================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
