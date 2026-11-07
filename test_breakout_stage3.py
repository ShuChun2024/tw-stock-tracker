import copy
import unittest

from breakout import (
    create_empty_state,
    sync_watchlist,
    validate_state,
)


# ============================================================
# 測試資料
# ============================================================

def create_test_state():
    state = create_empty_state()
    sync_watchlist(state, ["2330"])
    return state


def create_active_trade():
    return {
        "entry_signal_date": "2026-11-02",
        "entry_date": "2026-11-03",
        "entry_price": 1500.0,
        "holding_days": 3,
        "highest_price": 1560.0,
        "lowest_price": 1480.0,
        "mfe_pct": 4.0,
        "mae_pct": -1.3333,
        "pending_exit_date": None,
        "pending_exit_reason": None,
    }


def create_completed_trade():
    trade = create_active_trade()

    trade.update({
        "pending_exit_date": "2026-11-06",
        "pending_exit_reason": "跌破中軌",
        "exit_date": "2026-11-09",
        "exit_price": 1530.0,
        "return_pct": 2.0,
        "exit_reason": "跌破中軌停損",
    })

    return trade


# ============================================================
# 測試案例
# ============================================================

class TestBreakoutTradeSchema(unittest.TestCase):

    def setUp(self):
        self.state = create_test_state()

    def assert_invalid(self, state):
        with self.assertRaises((ValueError, TypeError)):
            validate_state(state)

    # --------------------------------------------------------
    # 1. 正常的空持倉狀態
    # --------------------------------------------------------

    def test_01_no_active_trade_is_valid(self):
        validate_state(self.state)

    # --------------------------------------------------------
    # 2. 正常的進行中交易
    # --------------------------------------------------------

    def test_02_valid_active_trade(self):
        self.state["stocks"]["2330"]["status"] = "holding"
        self.state["stocks"]["2330"]["active_trade"] = (
            create_active_trade()
        )

        validate_state(self.state)

    # --------------------------------------------------------
    # 3. 進行中交易缺少必要欄位
    # --------------------------------------------------------

    def test_03_active_trade_missing_required_field(self):
        self.state["stocks"]["2330"]["status"] = "holding"

        trade = create_active_trade()
        del trade["entry_price"]

        self.state["stocks"]["2330"]["active_trade"] = trade

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 4. 進場日期格式錯誤
    # --------------------------------------------------------

    def test_04_invalid_entry_date(self):
        self.state["stocks"]["2330"]["status"] = "holding"

        trade = create_active_trade()
        trade["entry_date"] = "2026-02-30"

        self.state["stocks"]["2330"]["active_trade"] = trade

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 5. 進場價格必須大於零
    # --------------------------------------------------------

    def test_05_invalid_entry_price(self):
        self.state["stocks"]["2330"]["status"] = "holding"

        trade = create_active_trade()
        trade["entry_price"] = 0

        self.state["stocks"]["2330"]["active_trade"] = trade

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 6. 持有天數必須是非負整數
    # --------------------------------------------------------

    def test_06_invalid_holding_days(self):
        self.state["stocks"]["2330"]["status"] = "holding"

        trade = create_active_trade()
        trade["holding_days"] = -1

        self.state["stocks"]["2330"]["active_trade"] = trade

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 7. 最高價不得低於最低價
    # --------------------------------------------------------

    def test_07_invalid_high_low_prices(self):
        self.state["stocks"]["2330"]["status"] = "holding"

        trade = create_active_trade()
        trade["highest_price"] = 1400.0
        trade["lowest_price"] = 1500.0

        self.state["stocks"]["2330"]["active_trade"] = trade

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 8. 待出場日期與原因不得只有其中一項
    # --------------------------------------------------------

    def test_08_pending_exit_fields_must_match(self):
        self.state["stocks"]["2330"]["status"] = "holding"

        trade = create_active_trade()
        trade["pending_exit_date"] = "2026-11-06"
        trade["pending_exit_reason"] = None

        self.state["stocks"]["2330"]["active_trade"] = trade

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 9. 正常的已完成交易
    # --------------------------------------------------------

    def test_09_valid_completed_trade(self):
        self.state["stocks"]["2330"]["trade_history"] = [
            create_completed_trade()
        ]

        validate_state(self.state)

    # --------------------------------------------------------
    # 10. 已完成交易缺少出場欄位
    # --------------------------------------------------------

    def test_10_completed_trade_missing_exit_field(self):
        trade = create_completed_trade()
        del trade["exit_price"]

        self.state["stocks"]["2330"]["trade_history"] = [
            trade
        ]

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 11. 出場價格必須大於零
    # --------------------------------------------------------

    def test_11_invalid_exit_price(self):
        trade = create_completed_trade()
        trade["exit_price"] = 0

        self.state["stocks"]["2330"]["trade_history"] = [
            trade
        ]

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 12. 出場日期格式錯誤
    # --------------------------------------------------------

    def test_12_invalid_exit_date(self):
        trade = create_completed_trade()
        trade["exit_date"] = "2026-13-40"

        self.state["stocks"]["2330"]["trade_history"] = [
            trade
        ]

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 13. 報酬率必須是有效數值
    # --------------------------------------------------------

    def test_13_invalid_return_pct(self):
        trade = create_completed_trade()
        trade["return_pct"] = float("nan")

        self.state["stocks"]["2330"]["trade_history"] = [
            trade
        ]

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 14. 交易歷史不得接受非字典資料
    # --------------------------------------------------------

    def test_14_invalid_trade_history_record(self):
        self.state["stocks"]["2330"]["trade_history"] = [
            "invalid"
        ]

        self.assert_invalid(self.state)

    # --------------------------------------------------------
    # 15. 驗證失敗不得修改原始狀態
    # --------------------------------------------------------

    def test_15_validation_does_not_mutate_state(self):
        self.state["stocks"]["2330"]["status"] = "holding"

        trade = create_active_trade()
        trade["entry_price"] = -100

        self.state["stocks"]["2330"]["active_trade"] = trade

        original = copy.deepcopy(self.state)

        try:
            validate_state(self.state)
        except (ValueError, TypeError):
            pass

        self.assertEqual(self.state, original)


if __name__ == "__main__":
    unittest.main()
