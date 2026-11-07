import copy
import datetime
import json
import logging
import os

from pathlib import Path


# ============================================================
# 布林突破策略狀態管理
#
# 職責：
# 1. 讀取 breakout_state.json
# 2. 同步目前觀察清單
# 3. 保留已移除股票的歷史紀錄
# 4. 找出仍需追蹤的未完成交易
# 5. 安全寫入 JSON
#
# 不負責：
# - 布林通道計算
# - 突破訊號判斷
# - 原有技術分析評分
# ============================================================


SCHEMA_VERSION = 1


def get_today_string():
    """取得台灣日期字串。"""
    return datetime.datetime.now().strftime("%Y-%m-%d")


def normalize_stock_id(stock_id):
    """統一股票代號格式。"""
    return str(stock_id).strip().zfill(4)


def create_stock_state(stock_id, watchlist_active=True):
    """建立單一股票的初始策略狀態。"""
    return {
        "stock_id": normalize_stock_id(stock_id),

        # 是否仍在目前觀察清單
        "watchlist_active": bool(watchlist_active),

        # inactive / watching / holding / stopped
        "status": "inactive",

        # 最近一次已處理的行情日期
        "last_processed_date": None,

        # 最近一次盤整觀察訊號
        "watch_signal": None,

        # 最近一次突破買進訊號
        "entry_signal": None,

        # 最近一次停損訊號
        "exit_signal": None,

        # 尚未完成的交易
        "active_trade": None,

        # 所有策略訊號紀錄
        "signal_history": [],

        # 所有已完成交易紀錄
        "trade_history": [],

        # 最後更新時間
        "updated_at": None
    }


def create_empty_state():
    """建立全新的狀態檔結構。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "update_time": None,
        "stock_count": 0,
        "stocks": {}
    }


def validate_state(data):
    """
    驗證狀態檔結構。

    發現格式錯誤時直接停止，不允許以空白資料覆蓋舊紀錄。
    """
    if not isinstance(data, dict):
        raise ValueError("breakout_state.json 根節點必須是 JSON 物件")

    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "breakout_state.json schema_version 不符合目前版本"
        )

    stocks = data.get("stocks")

    if not isinstance(stocks, dict):
        raise ValueError(
            "breakout_state.json 缺少有效的 stocks 物件"
        )

    for stock_id, item in stocks.items():

        if not isinstance(item, dict):
            raise ValueError(
                f"股票 {stock_id} 的策略資料格式錯誤"
            )

        required_list_fields = [
            "signal_history",
            "trade_history"
        ]

        for field in required_list_fields:
            if not isinstance(item.get(field), list):
                raise ValueError(
                    f"股票 {stock_id} 的 {field} 必須是陣列"
                )

        if not isinstance(item.get("watchlist_active"), bool):
            raise ValueError(
                f"股票 {stock_id} 的 watchlist_active 必須是布林值"
            )

        if item.get("status") not in {
            "inactive",
            "watching",
            "holding",
            "stopped"
        }:
            raise ValueError(
                f"股票 {stock_id} 的策略狀態不合法"
            )

        active_trade = item.get("active_trade")

        if active_trade is not None and not isinstance(
            active_trade, dict
        ):
            raise ValueError(
                f"股票 {stock_id} 的 active_trade 格式錯誤"
            )

        if item["status"] == "holding" and active_trade is None:
            raise ValueError(
                f"股票 {stock_id} 狀態為 holding，"
                "但缺少 active_trade"
            )

    return True


def load_breakout_state(state_file):
    """
    載入策略狀態。

    狀態檔不存在：
        建立新的空白結構。

    狀態檔存在但格式錯誤：
        停止執行，避免覆蓋既有歷史紀錄。
    """
    state_file = Path(state_file)

    if not state_file.exists():
        logging.info(
            "尚無 breakout_state.json，建立新的策略狀態。"
        )
        return create_empty_state()

    try:
        with state_file.open("r", encoding="utf-8") as file:
            data = json.load(file)

        validate_state(data)

        logging.info(
            "成功載入策略狀態，共 %s 檔股票。",
            len(data["stocks"])
        )

        return data

    except Exception:
        logging.exception(
            "讀取 breakout_state.json 失敗，停止更新以保護歷史紀錄。"
        )
        raise


def sync_watchlist(state, watchlist):
    """
    同步目前觀察清單。

    新增股票：
        建立初始狀態。

    移除股票：
        watchlist_active 改為 False。
        不刪除歷史紀錄。
        不改變 holding 狀態。

    重新加入：
        watchlist_active 改為 True。
        沿用原有狀態。
    """
    if not isinstance(watchlist, (list, tuple)):
        raise ValueError("watchlist 必須是股票代號清單")

    normalized_watchlist = {
        normalize_stock_id(stock_id)
        for stock_id in watchlist
    }

    stocks = state["stocks"]

    # 先將所有既有股票標記為不在觀察清單
    for stock_id, item in stocks.items():
        item["watchlist_active"] = False

    # 再同步目前觀察清單
    for stock_id in normalized_watchlist:

        if stock_id not in stocks:
            stocks[stock_id] = create_stock_state(
                stock_id,
                watchlist_active=True
            )

            logging.info(
                "新增策略追蹤股票：%s",
                stock_id
            )

        else:
            stocks[stock_id]["watchlist_active"] = True

            logging.info(
                "沿用既有策略紀錄：%s",
                stock_id
            )

    # 已移除股票只更新清單狀態，不刪除任何歷史資料
    for stock_id, item in stocks.items():

        if not item["watchlist_active"]:
            logging.info(
                "股票 %s 已移出觀察清單，保留策略歷史。",
                stock_id
            )

    return state


def get_required_stock_ids(state):
    """
    取得需要每日更新行情的股票。

    包含：
    1. 目前觀察清單中的股票
    2. 已移出觀察清單，但仍有未完成交易的股票

    不包含：
    - 已完成交易且已移出觀察清單的股票
    - 已停止追蹤且已移出觀察清單的股票
    """
    required = set()

    for stock_id, item in state["stocks"].items():

        if item.get("watchlist_active") is True:
            required.add(normalize_stock_id(stock_id))
            continue

        if item.get("status") == "holding":
            required.add(normalize_stock_id(stock_id))

    return sorted(required)


def save_breakout_state(state, state_file):
    """
    安全儲存策略狀態。

    流程：
    1. 驗證資料結構
    2. 寫入暫存檔
    3. 重新讀取暫存檔驗證
    4. 使用 os.replace 原子替換正式檔案
    """
    state_file = Path(state_file)

    state_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    state["schema_version"] = SCHEMA_VERSION
    state["update_time"] = datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    state["stock_count"] = len(state["stocks"])

    validate_state(state)

    temp_file = state_file.with_name(
        state_file.name + ".tmp"
    )

    try:
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump(
                state,
                file,
                ensure_ascii=False,
                indent=2,
                allow_nan=False
            )
            file.write("\n")

        # 重新讀取暫存檔
        with temp_file.open("r", encoding="utf-8") as file:
            verified_data = json.load(file)

        validate_state(verified_data)

        if len(verified_data["stocks"]) != len(state["stocks"]):
            raise ValueError(
                "策略狀態股票數量驗證失敗"
            )

        os.replace(temp_file, state_file)

        logging.info(
            "breakout_state.json 儲存完成，共 %s 檔股票。",
            len(state["stocks"])
        )

    except Exception:
        logging.exception(
            "儲存 breakout_state.json 失敗。"
        )

        try:
            if temp_file.exists():
                temp_file.unlink()
        except OSError:
            logging.exception(
                "清理 breakout_state.json 暫存檔失敗。"
            )

        raise
