import json
import logging
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

import breakout


# ============================================================
# breakout.py 第一階段獨立測試
#
# 測試範圍：
# 1. 建立與儲存
# 2. 觀察清單同步
# 3. 持有股票保留
# 4. 毀損檔案保護
# 5. 重複執行與寫入異常
#
# 所有測試均使用 tempfile。
# 不會修改正式 breakout_state.json。
# ============================================================


logging.basicConfig(
    level=logging.ERROR,
    format="%(levelname)s: %(message)s"
)


class TestBreakoutState(unittest.TestCase):

    def setUp(self):
        """每個測試建立獨立暫存目錄。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        self.state_file = self.test_dir / "breakout_state.json"

    def tearDown(self):
        """測試結束後清除暫存資料。"""
        self.temp_dir.cleanup()

    # --------------------------------------------------------
    # 測試 1：建立、儲存、重新載入
    # --------------------------------------------------------

    def test_01_create_save_load(self):

        state = breakout.create_empty_state()

        self.assertEqual(
            state["schema_version"],
            breakout.SCHEMA_VERSION
        )

        self.assertEqual(state["stocks"], {})

        # 新增股票
        state["stocks"]["2330"] = (
            breakout.create_stock_state("2330")
        )

        state["stocks"]["2454"] = (
            breakout.create_stock_state("2454")
        )

        # 儲存
        breakout.save_breakout_state(
            state,
            self.state_file
        )

        self.assertTrue(self.state_file.exists())

        # 重新載入
        loaded = breakout.load_breakout_state(
            self.state_file
        )

        self.assertEqual(
            len(loaded["stocks"]),
            2
        )

        self.assertIn("2330", loaded["stocks"])
        self.assertIn("2454", loaded["stocks"])

        self.assertEqual(
            loaded["stock_count"],
            2
        )

        self.assertEqual(
            loaded["stocks"]["2330"]["status"],
            "inactive"
        )

    # --------------------------------------------------------
    # 測試 2：觀察清單同步
    # --------------------------------------------------------

    def test_02_watchlist_sync(self):

        state = breakout.create_empty_state()

        # 第一階段：觀察 2330、2454
        breakout.sync_watchlist(
            state,
            ["2330", "2454"]
        )

        self.assertTrue(
            state["stocks"]["2330"]["watchlist_active"]
        )

        self.assertTrue(
            state["stocks"]["2454"]["watchlist_active"]
        )

        # 建立歷史紀錄，模擬已經產生過訊號
        state["stocks"]["2330"]["signal_history"].append({
            "date": "2026-11-06",
            "signal": "watch",
            "message": "測試盤整訊號"
        })

        # 第二階段：移除 2454，新增 2317
        breakout.sync_watchlist(
            state,
            ["2330", "2317"]
        )

        self.assertTrue(
            state["stocks"]["2330"]["watchlist_active"]
        )

        self.assertFalse(
            state["stocks"]["2454"]["watchlist_active"]
        )

        self.assertTrue(
            state["stocks"]["2317"]["watchlist_active"]
        )

        # 確認 2454 歷史沒有被刪除
        self.assertIn("2454", state["stocks"])

        # 確認 2330 歷史仍存在
        self.assertEqual(
            len(state["stocks"]["2330"]["signal_history"]),
            1
        )

        # 第三階段：重新加入 2454
        breakout.sync_watchlist(
            state,
            ["2330", "2454"]
        )

        self.assertTrue(
            state["stocks"]["2454"]["watchlist_active"]
        )

        # 原有歷史必須保留
        self.assertEqual(
            len(state["stocks"]["2330"]["signal_history"]),
            1
        )

        self.assertIn("2317", state["stocks"])

    # --------------------------------------------------------
    # 測試 3：移出觀察清單的持有股票仍須追蹤
    # --------------------------------------------------------

    def test_03_holding_stock_retention(self):

        state = breakout.create_empty_state()

        breakout.sync_watchlist(
            state,
            ["2330", "2454", "2317"]
        )

        # 模擬 2454 已經進場持有
        stock = state["stocks"]["2454"]

        stock["status"] = "holding"

        stock["active_trade"] = {
            "entry_date": "2026-11-05",
            "entry_price": 100,
            "quantity": 1000,
            "exit_date": None,
            "exit_price": None
        }

        # 移除 2454，只留下 2330、2317
        breakout.sync_watchlist(
            state,
            ["2330", "2317"]
        )

        self.assertFalse(
            state["stocks"]["2454"]["watchlist_active"]
        )

        self.assertEqual(
            state["stocks"]["2454"]["status"],
            "holding"
        )

        self.assertIsNotNone(
            state["stocks"]["2454"]["active_trade"]
        )

        # 取得需要每日追蹤的股票
        required = breakout.get_required_stock_ids(state)

        self.assertIn("2330", required)
        self.assertIn("2317", required)
        self.assertIn("2454", required)

        # 確認排序及沒有重複
        self.assertEqual(
            required,
            sorted(set(required))
        )

        # 移除清單但已完成交易的股票不應繼續追蹤
        state["stocks"]["2317"]["watchlist_active"] = False
        state["stocks"]["2317"]["status"] = "stopped"

        required = breakout.get_required_stock_ids(state)

        self.assertNotIn("2317", required)
        self.assertIn("2454", required)

    # --------------------------------------------------------
    # 測試 4：毀損檔案保護
    # --------------------------------------------------------

    def test_04_corrupted_file_protection(self):

        corrupted_content = '{"stocks": '

        self.state_file.write_text(
            corrupted_content,
            encoding="utf-8"
        )

        original_content = self.state_file.read_bytes()

        # 錯誤 JSON 必須拒絕載入
        with self.assertRaises(Exception):
            breakout.load_breakout_state(
                self.state_file
            )

        # 原始檔案不能被改寫
        self.assertEqual(
            self.state_file.read_bytes(),
            original_content
        )

        # 測試錯誤 schema
        invalid_state = breakout.create_empty_state()

        invalid_state["schema_version"] = 999

        self.state_file.write_text(
            json.dumps(invalid_state),
            encoding="utf-8"
        )

        original_content = self.state_file.read_bytes()

        with self.assertRaises(ValueError):
            breakout.load_breakout_state(
                self.state_file
            )

        self.assertEqual(
            self.state_file.read_bytes(),
            original_content
        )

    # --------------------------------------------------------
    # 測試 5A：重複儲存
    # --------------------------------------------------------

    def test_05a_repeated_save(self):

        state = breakout.create_empty_state()

        breakout.sync_watchlist(
            state,
            ["2330", "2454"]
        )

        state["stocks"]["2330"]["signal_history"].append({
            "date": "2026-11-06",
            "signal": "watch"
        })

        # 第一次儲存
        breakout.save_breakout_state(
            state,
            self.state_file
        )

        first = breakout.load_breakout_state(
            self.state_file
        )

        # 第二次儲存
        breakout.save_breakout_state(
            first,
            self.state_file
        )

        second = breakout.load_breakout_state(
            self.state_file
        )

        # 股票不能遺失
        self.assertEqual(
            len(second["stocks"]),
            2
        )

        # 訊號歷史不能重複增加
        self.assertEqual(
            len(second["stocks"]["2330"]["signal_history"]),
            1
        )

        # 股票數量必須一致
        self.assertEqual(
            second["stock_count"],
            2
        )

    # --------------------------------------------------------
    # 測試 5B：正式檔替換失敗
    # --------------------------------------------------------

    def test_05b_replace_failure_protection(self):

        state = breakout.create_empty_state()

        breakout.sync_watchlist(
            state,
            ["2330"]
        )

        # 先建立有效正式檔
        breakout.save_breakout_state(
            state,
            self.state_file
        )

        original_content = self.state_file.read_bytes()

        # 準備另一份新狀態
        new_state = breakout.create_empty_state()

        breakout.sync_watchlist(
            new_state,
            ["2330", "2454"]
        )

        # 模擬 os.replace 失敗
        with patch(
            "breakout.os.replace",
            side_effect=OSError("模擬檔案替換失敗")
        ):

            with self.assertRaises(OSError):
                breakout.save_breakout_state(
                    new_state,
                    self.state_file
                )

        # 正式檔必須維持原始內容
        self.assertEqual(
            self.state_file.read_bytes(),
            original_content
        )

        # 暫存檔應該清理
        temp_file = self.state_file.with_name(
            self.state_file.name + ".tmp"
        )

        self.assertFalse(temp_file.exists())

        # 原始正式檔仍可正常載入
        loaded = breakout.load_breakout_state(
            self.state_file
        )

        self.assertEqual(
            len(loaded["stocks"]),
            1
        )

        self.assertIn("2330", loaded["stocks"])


# ============================================================
# 執行測試
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("breakout.py 第一階段獨立測試")
    print("=" * 60)

    unittest.main(verbosity=2)
