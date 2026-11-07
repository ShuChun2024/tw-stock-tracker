import copy
import datetime
import json
import logging
import os
import re

from pathlib import Path


SCHEMA_VERSION = 1

# ============================================================
# 必要欄位
# ============================================================

REQUIRED_STOCK_FIELDS = {
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
}

VALID_STATUSES = {
    "inactive",
    "watching",
    "holding",
    "stopped"
}


# ============================================================
# 1. 日期及股票代號處理
# ============================================================

def get_today_string():
    """取得日期字串。"""
    return datetime.datetime.now().strftime("%Y-%m-%d")


def normalize_stock_id(stock_id):
    """
    統一股票代號格式。

    接受：
    - 非負整數
    - 純數字字串

    處理：
    - 去除字串前後空白
    - 不足四碼補零

    拒絕：
    - None
    - 空字串
    - 布林值
    - 小數
    - 英文字母
    - 其他非數字資料
    """

    # bool 是 int 的子類別，必須先排除
    if isinstance(stock_id, bool):
        raise ValueError("股票代號不可為布林值")

    if isinstance(stock_id, int):
        if stock_id < 0:
            raise ValueError("股票代號不可為負數")

        stock_id = str(stock_id)

    elif isinstance(stock_id, str):
        stock_id = stock_id.strip()

    else:
        raise TypeError(
            "股票代號只能是非負整數或數字字串"
        )

    if not stock_id:
        raise ValueError("股票代號不可為空")

    if re.fullmatch(r"[0-9]+", stock_id) is None:
        raise ValueError(
            f"股票代號必須是純數字：{stock_id!r}"
        )

    return stock_id.zfill(4)


def validate_iso_date(value, field_name):
    """
    驗證 YYYY-MM-DD 日期。

    None 代表尚未處理，允許存在。
    """

    if value is None:
        return True

    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} 必須是 YYYY-MM-DD 字串或 None"
        )

    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} 不是有效日期：{value!r}"
        ) from exc

    # 確保格式必須完全符合 YYYY-MM-DD
    if parsed.isoformat() != value:
        raise ValueError(
            f"{field_name} 日期格式錯誤：{value!r}"
        )

    return True


# ============================================================
# 2. 建立策略狀態
# ============================================================

def create_stock_state(stock_id, watchlist_active=True):

    stock_id = normalize_stock_id(stock_id)

    if not isinstance(watchlist_active, bool):
        raise ValueError(
            "watchlist_active 必須是布林值"
        )

    return {
        "stock_id": stock_id,
        "watchlist_active": watchlist_active,
        "status": "inactive",
        "last_processed_date": None,
        "watch_signal": None,
        "entry_signal": None,
        "exit_signal": None,
        "active_trade": None,
        "signal_history": [],
        "trade_history": [],
        "updated_at": None
    }


def create_empty_state():

    return {
        "schema_version": SCHEMA_VERSION,
        "update_time": None,
        "stock_count": 0,
        "stocks": {}
    }


# ============================================================
# 3. 狀態檔完整性驗證
# ============================================================

def validate_state(data):
    """
    驗證 breakout_state.json 完整性。

    驗證內容：
    1. 根節點格式
    2. schema_version
    3. stocks 格式
    4. stock_count
    5. 股票代號及字典 key
    6. 必要欄位
    7. watchlist_active
    8. status
    9. 日期格式
    10. active_trade 基本型別
    11. 歷史紀錄格式

    任何一項錯誤都會停止處理。
    """

    if not isinstance(data, dict):
        raise ValueError(
            "breakout_state.json 根節點必須是 JSON 物件"
        )

    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "breakout_state.json schema_version 不符合目前版本"
        )

    stocks = data.get("stocks")

    if not isinstance(stocks, dict):
        raise ValueError(
            "breakout_state.json 缺少有效的 stocks 物件"
        )

    # --------------------------------------------------------
    # 3.1 stock_count 驗證
    # --------------------------------------------------------

    stock_count = data.get("stock_count")

    if isinstance(stock_count, bool) or not isinstance(
        stock_count, int
    ):
        raise ValueError(
            "stock_count 必須是整數"
        )

    if stock_count < 0:
        raise ValueError(
            "stock_count 不可小於 0"
        )

    if stock_count != len(stocks):
        raise ValueError(
            f"stock_count 不一致：記錄為 {stock_count}，"
            f"實際為 {len(stocks)}"
        )

    # --------------------------------------------------------
    # 3.2 逐檔股票驗證
    # --------------------------------------------------------

    for stock_id, item in stocks.items():

        if not isinstance(stock_id, str):
            raise ValueError(
                f"股票字典 key 必須是字串：{stock_id!r}"
            )

        normalized_id = normalize_stock_id(stock_id)

        if stock_id != normalized_id:
            raise ValueError(
                f"股票字典 key 未正規化：{stock_id}"
            )

        if not isinstance(item, dict):
            raise ValueError(
                f"股票 {stock_id} 的策略資料格式錯誤"
            )

        # ----------------------------------------------------
        # 3.3 必要欄位驗證
        # ----------------------------------------------------

        missing_fields = (
            REQUIRED_STOCK_FIELDS - set(item.keys())
        )

        if missing_fields:
            missing_text = ", ".join(
                sorted(missing_fields)
            )

            raise ValueError(
                f"股票 {stock_id} 缺少必要欄位：{missing_text}"
            )

        # ----------------------------------------------------
        # 3.4 stock_id 與 key 一致性
        # ----------------------------------------------------

        item_stock_id = item["stock_id"]

        if not isinstance(item_stock_id, str):
            raise ValueError(
                f"股票 {stock_id} 的 stock_id 必須是字串"
            )

        if item_stock_id != stock_id:
            raise ValueError(
                f"股票 key 與 stock_id 不一致："
                f"key={stock_id}, stock_id={item_stock_id}"
            )

        # ----------------------------------------------------
        # 3.5 觀察清單狀態
        # ----------------------------------------------------

        if not isinstance(item["watchlist_active"], bool):
            raise ValueError(
                f"股票 {stock_id} 的 watchlist_active 必須是布林值"
            )

        # ----------------------------------------------------
        # 3.6 策略狀態
        # ----------------------------------------------------

        if item["status"] not in VALID_STATUSES:
            raise ValueError(
                f"股票 {stock_id} 的策略狀態不合法："
                f"{item['status']!r}"
            )

        # ----------------------------------------------------
        # 3.7 日期驗證
        # ----------------------------------------------------

        validate_iso_date(
            item["last_processed_date"],
            f"股票 {stock_id} last_processed_date"
        )

        # ----------------------------------------------------
        # 3.8 active_trade 基本型別驗證
        #
        # 暫不限制交易欄位，待交易引擎規格確定後再補。
        # ----------------------------------------------------

        active_trade = item["active_trade"]

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

        # ----------------------------------------------------
        # 3.9 歷史紀錄容器驗證
        # ----------------------------------------------------

        for field in [
            "signal_history",
            "trade_history"
        ]:

            records = item[field]

            if not isinstance(records, list):
                raise ValueError(
                    f"股票 {stock_id} 的 {field} 必須是陣列"
                )

            for index, record in enumerate(records):

                if not isinstance(record, dict):
                    raise ValueError(
                        f"股票 {stock_id} 的 {field}"
                        f"第 {index + 1} 筆紀錄必須是物件"
                    )

    return True


# ============================================================
# 4. 載入策略狀態
# ============================================================

def load_breakout_state(state_file):

    state_file = Path(state_file)

    if not state_file.exists():

        logging.info(
            "尚無 breakout_state.json，建立新的策略狀態。"
        )

        return create_empty_state()

    try:

        with state_file.open(
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        validate_state(data)

        logging.info(
            "成功載入策略狀態，共 %s 檔股票。",
            len(data["stocks"])
        )

        return data

    except Exception:

        logging.exception(
            "讀取 breakout_state.json 失敗，"
            "停止更新以保護歷史紀錄。"
        )

        raise


# ============================================================
# 5. 同步觀察清單
# ============================================================

def sync_watchlist(state, watchlist):
    """
    同步觀察清單。

    安全原則：
    1. 先驗證整份 watchlist。
    2. 全部通過後才修改 state。
    3. 無效股票代號不得造成部分更新。
    4. 已移除股票保留歷史。
    5. 重新加入股票沿用既有狀態。
    """

    if not isinstance(watchlist, (list, tuple)):
        raise ValueError(
            "watchlist 必須是股票代號清單"
        )

    if not isinstance(state, dict):
        raise ValueError(
            "策略狀態必須是字典"
        )

    stocks = state.get("stocks")

    if not isinstance(stocks, dict):
        raise ValueError(
            "策略狀態缺少有效的 stocks 物件"
        )

    # --------------------------------------------------------
    # 5.1 第一階段：完整驗證觀察清單
    #
    # 在這個階段不得修改 state。
    # --------------------------------------------------------

    normalized_watchlist = set()

    for stock_id in watchlist:

        normalized_id = normalize_stock_id(
            stock_id
        )

        normalized_watchlist.add(
            normalized_id
        )

    # --------------------------------------------------------
    # 5.2 第二階段：驗證通過後才修改狀態
    # --------------------------------------------------------

    for item in stocks.values():

        if not isinstance(item, dict):
            raise ValueError(
                "既有股票策略資料格式錯誤"
            )

    # 先準備新股票資料，避免執行到一半才發現代號錯誤
    new_stock_states = {}

    for stock_id in normalized_watchlist:

        if stock_id not in stocks:

            new_stock_states[stock_id] = (
                create_stock_state(
                    stock_id,
                    watchlist_active=True
                )
            )

    # 更新原有股票觀察狀態
    for stock_id, item in stocks.items():

        item["watchlist_active"] = (
            normalize_stock_id(stock_id)
            in normalized_watchlist
        )

    # 新增股票
    for stock_id, item in new_stock_states.items():

        stocks[stock_id] = item

        logging.info(
            "新增策略追蹤股票：%s",
            stock_id
        )

    # 記錄重新加入及移除狀態
    for stock_id in sorted(normalized_watchlist):

        if stock_id not in new_stock_states:

            logging.info(
                "沿用既有策略紀錄：%s",
                stock_id
            )

    for stock_id, item in stocks.items():

        if not item["watchlist_active"]:

            logging.info(
                "股票 %s 已移出觀察清單，保留策略歷史。",
                stock_id
            )

    state["stock_count"] = len(stocks)

    return state


# ============================================================
# 6. 取得需要分析的股票
# ============================================================

def get_required_stock_ids(state):

    validate_state(state)

    required = set()

    for stock_id, item in state["stocks"].items():

        if item.get("watchlist_active") is True:

            required.add(
                normalize_stock_id(stock_id)
            )

            continue

        # 已移出觀察清單，但仍有持有交易
        # 必須繼續更新及檢查停損
        if item.get("status") == "holding":

            required.add(
                normalize_stock_id(stock_id)
            )

    return sorted(required)


# ============================================================
# 7. 安全儲存策略狀態
# ============================================================

def save_breakout_state(state, state_file):

    state_file = Path(state_file)

    state_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # 避免直接修改呼叫端傳入的物件
    save_data = copy.deepcopy(state)

    save_data["schema_version"] = SCHEMA_VERSION

    save_data["update_time"] = (
        datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    if not isinstance(save_data.get("stocks"), dict):

        raise ValueError(
            "策略狀態缺少有效的 stocks 物件"
        )

    save_data["stock_count"] = len(
        save_data["stocks"]
    )

    validate_state(save_data)

    temp_file = state_file.with_name(
        state_file.name + ".tmp"
    )

    try:

        # ----------------------------------------------------
        # 7.1 寫入暫存檔
        # ----------------------------------------------------

        with temp_file.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                save_data,
                file,
                ensure_ascii=False,
                indent=2,
                allow_nan=False
            )

            file.write("\n")

        # ----------------------------------------------------
        # 7.2 重新讀取並驗證暫存檔
        # ----------------------------------------------------

        with temp_file.open(
            "r",
            encoding="utf-8"
        ) as file:

            verified_data = json.load(file)

        validate_state(verified_data)

        if (
            len(verified_data["stocks"])
            != len(save_data["stocks"])
        ):

            raise ValueError(
                "策略狀態股票數量驗證失敗"
            )

        # ----------------------------------------------------
        # 7.3 原子替換正式檔案
        # ----------------------------------------------------

        os.replace(
            temp_file,
            state_file
        )

        logging.info(
            "breakout_state.json 儲存完成，共 %s 檔股票。",
            len(save_data["stocks"])
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
