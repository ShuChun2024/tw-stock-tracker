import copy
import datetime
import json
import logging
import math
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
# 交易資料必要欄位
# ============================================================

ACTIVE_TRADE_REQUIRED_FIELDS = {
    "entry_signal_date",
    "entry_date",
    "entry_price",
    "holding_days",
    "highest_price",
    "lowest_price",
    "mfe_pct",
    "mae_pct",
    "pending_exit_date",
    "pending_exit_reason"
}

COMPLETED_TRADE_REQUIRED_FIELDS = (
    ACTIVE_TRADE_REQUIRED_FIELDS
    | {
        "exit_date",
        "exit_price",
        "return_pct",
        "exit_reason"
    }
)


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

    if parsed.isoformat() != value:
        raise ValueError(
            f"{field_name} 日期格式錯誤：{value!r}"
        )

    return True


# ============================================================
# 2. 通用資料驗證
# ============================================================

def validate_finite_number(value, field_name):
    """
    驗證有限數值。

    拒絕：
    - bool
    - 字串
    - None
    - NaN
    - 正負無限大
    """

    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} 不可為布林值"
        )

    if not isinstance(value, (int, float)):
        raise ValueError(
            f"{field_name} 必須是數值"
        )

    if not math.isfinite(value):
        raise ValueError(
            f"{field_name} 必須是有限數值"
        )

    return True


def validate_positive_number(value, field_name):
    """驗證必須大於零的數值。"""

    validate_finite_number(
        value,
        field_name
    )

    if value <= 0:
        raise ValueError(
            f"{field_name} 必須大於 0"
        )

    return True


def validate_non_negative_integer(value, field_name):
    """驗證非負整數，排除 bool。"""

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"{field_name} 必須是整數"
        )

    if value < 0:
        raise ValueError(
            f"{field_name} 不可小於 0"
        )

    return True


def validate_non_empty_string(value, field_name):
    """驗證非空字串。"""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{field_name} 必須是非空字串"
        )

    return True


# ============================================================
# 3. 交易資料驗證
# ============================================================

def validate_active_trade(trade, stock_id):
    """
    驗證進行中的交易資料。

    檢查：
    1. 必要欄位
    2. 日期格式及先後順序
    3. 進場價格
    4. 持有天數
    5. 最高價及最低價
    6. MFE / MAE
    7. 待出場日期與原因
    """

    if not isinstance(trade, dict):
        raise ValueError(
            f"股票 {stock_id} 的 active_trade 必須是物件"
        )

    missing_fields = (
        ACTIVE_TRADE_REQUIRED_FIELDS - set(trade.keys())
    )

    if missing_fields:
        missing_text = ", ".join(
            sorted(missing_fields)
        )

        raise ValueError(
            f"股票 {stock_id} 的 active_trade "
            f"缺少必要欄位：{missing_text}"
        )

    # --------------------------------------------------------
    # 3.1 日期驗證
    # --------------------------------------------------------

    validate_iso_date(
        trade["entry_signal_date"],
        f"股票 {stock_id} entry_signal_date"
    )

    validate_iso_date(
        trade["entry_date"],
        f"股票 {stock_id} entry_date"
    )

    validate_iso_date(
        trade["pending_exit_date"],
        f"股票 {stock_id} pending_exit_date"
    )

    signal_date = datetime.date.fromisoformat(
        trade["entry_signal_date"]
    )

    entry_date = datetime.date.fromisoformat(
        trade["entry_date"]
    )

    if signal_date > entry_date:
        raise ValueError(
            f"股票 {stock_id} 的進場訊號日"
            "不得晚於實際進場日"
        )

    pending_exit_date = trade["pending_exit_date"]

    if pending_exit_date is not None:

        pending_date = datetime.date.fromisoformat(
            pending_exit_date
        )

        if pending_date < entry_date:
            raise ValueError(
                f"股票 {stock_id} 的待出場日期"
                "不得早於進場日期"
            )

    # --------------------------------------------------------
    # 3.2 進場價格
    # --------------------------------------------------------

    validate_positive_number(
        trade["entry_price"],
        f"股票 {stock_id} entry_price"
    )

    # --------------------------------------------------------
    # 3.3 持有天數
    # --------------------------------------------------------

    validate_non_negative_integer(
        trade["holding_days"],
        f"股票 {stock_id} holding_days"
    )

    # --------------------------------------------------------
    # 3.4 最高價及最低價
    # --------------------------------------------------------

    validate_positive_number(
        trade["highest_price"],
        f"股票 {stock_id} highest_price"
    )

    validate_positive_number(
        trade["lowest_price"],
        f"股票 {stock_id} lowest_price"
    )

    if trade["highest_price"] < trade["lowest_price"]:
        raise ValueError(
            f"股票 {stock_id} 的最高價不得低於最低價"
        )

    # --------------------------------------------------------
    # 3.5 MFE / MAE
    # --------------------------------------------------------

    validate_finite_number(
        trade["mfe_pct"],
        f"股票 {stock_id} mfe_pct"
    )

    validate_finite_number(
        trade["mae_pct"],
        f"股票 {stock_id} mae_pct"
    )

    # --------------------------------------------------------
    # 3.6 待出場日期與原因
    # --------------------------------------------------------

    pending_reason = trade["pending_exit_reason"]

    if pending_exit_date is None and pending_reason is not None:
        raise ValueError(
            f"股票 {stock_id} 的待出場日期為空，"
            "但待出場原因不為空"
        )

    if pending_exit_date is not None and pending_reason is None:
        raise ValueError(
            f"股票 {stock_id} 的待出場日期存在，"
            "但待出場原因為空"
        )

    if pending_reason is not None:
        validate_non_empty_string(
            pending_reason,
            f"股票 {stock_id} pending_exit_reason"
        )

    return True


def validate_completed_trade(trade, stock_id, index):
    """
    驗證已完成交易紀錄。

    已完成交易必須具備：
    - 完整進場資料
    - 完整出場資料
    - 有效報酬率
    """

    if not isinstance(trade, dict):
        raise ValueError(
            f"股票 {stock_id} 的 trade_history "
            f"第 {index + 1} 筆紀錄必須是物件"
        )

    missing_fields = (
        COMPLETED_TRADE_REQUIRED_FIELDS - set(trade.keys())
    )

    if missing_fields:
        missing_text = ", ".join(
            sorted(missing_fields)
        )

        raise ValueError(
            f"股票 {stock_id} 的 trade_history "
            f"第 {index + 1} 筆紀錄缺少欄位：{missing_text}"
        )

    # --------------------------------------------------------
    # 3.7 先驗證共同進場資料
    # --------------------------------------------------------

    validate_active_trade(
        trade,
        stock_id
    )

    # --------------------------------------------------------
    # 3.8 出場日期
    # --------------------------------------------------------

    validate_iso_date(
        trade["exit_date"],
        f"股票 {stock_id} exit_date"
    )

    exit_date = datetime.date.fromisoformat(
        trade["exit_date"]
    )

    entry_date = datetime.date.fromisoformat(
        trade["entry_date"]
    )

    if exit_date <= entry_date:
        raise ValueError(
            f"股票 {stock_id} 的出場日期"
            "必須晚於進場日期"
        )

    # 已完成交易必須有待出場日期及原因
    if trade["pending_exit_date"] is None:
        raise ValueError(
            f"股票 {stock_id} 的已完成交易"
            "缺少 pending_exit_date"
        )

    if trade["pending_exit_reason"] is None:
        raise ValueError(
            f"股票 {stock_id} 的已完成交易"
            "缺少 pending_exit_reason"
        )

    pending_date = datetime.date.fromisoformat(
        trade["pending_exit_date"]
    )

    if exit_date <= pending_date:
        raise ValueError(
            f"股票 {stock_id} 的實際出場日期"
            "必須晚於停損訊號日期"
        )

    # --------------------------------------------------------
    # 3.9 出場價格
    # --------------------------------------------------------

    validate_positive_number(
        trade["exit_price"],
        f"股票 {stock_id} exit_price"
    )

    # --------------------------------------------------------
    # 3.10 報酬率
    # --------------------------------------------------------

    validate_finite_number(
        trade["return_pct"],
        f"股票 {stock_id} return_pct"
    )

    # --------------------------------------------------------
    # 3.11 出場原因
    # --------------------------------------------------------

    validate_non_empty_string(
        trade["exit_reason"],
        f"股票 {stock_id} exit_reason"
    )

    return True


# ============================================================
# 4. 建立策略狀態
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
# 5. 狀態檔完整性驗證
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
    10. active_trade 完整交易資料
    11. signal_history 格式
    12. trade_history 完整交易資料

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
    # 5.1 stock_count 驗證
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
    # 5.2 逐檔股票驗證
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
        # 5.3 必要欄位驗證
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
        # 5.4 stock_id 與 key 一致性
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
        # 5.5 觀察清單狀態
        # ----------------------------------------------------

        if not isinstance(item["watchlist_active"], bool):
            raise ValueError(
                f"股票 {stock_id} 的 watchlist_active 必須是布林值"
            )

        # ----------------------------------------------------
        # 5.6 策略狀態
        # ----------------------------------------------------

        if item["status"] not in VALID_STATUSES:
            raise ValueError(
                f"股票 {stock_id} 的策略狀態不合法："
                f"{item['status']!r}"
            )

        # ----------------------------------------------------
        # 5.7 日期驗證
        # ----------------------------------------------------

        validate_iso_date(
            item["last_processed_date"],
            f"股票 {stock_id} last_processed_date"
        )

        # ----------------------------------------------------
        # 5.8 active_trade 完整驗證
        # ----------------------------------------------------

        active_trade = item["active_trade"]

        if active_trade is not None:

            validate_active_trade(
                active_trade,
                stock_id
            )

        if item["status"] == "holding" and active_trade is None:
            raise ValueError(
                f"股票 {stock_id} 狀態為 holding，"
                "但缺少 active_trade"
            )

        # ----------------------------------------------------
        # 5.9 歷史紀錄容器驗證
        # ----------------------------------------------------

        signal_history = item["signal_history"]

        if not isinstance(signal_history, list):
            raise ValueError(
                f"股票 {stock_id} 的 signal_history 必須是陣列"
            )

        for index, record in enumerate(signal_history):

            if not isinstance(record, dict):
                raise ValueError(
                    f"股票 {stock_id} 的 signal_history "
                    f"第 {index + 1} 筆紀錄必須是物件"
                )

        # ----------------------------------------------------
        # 5.10 trade_history 完整驗證
        # ----------------------------------------------------

        trade_history = item["trade_history"]

        if not isinstance(trade_history, list):
            raise ValueError(
                f"股票 {stock_id} 的 trade_history 必須是陣列"
            )

        for index, record in enumerate(trade_history):

            validate_completed_trade(
                record,
                stock_id,
                index
            )

    return True


# ============================================================
# 6. 載入策略狀態
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
# 7. 同步觀察清單
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
    # 7.1 第一階段：完整驗證觀察清單
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
    # 7.2 第二階段：驗證通過後才修改狀態
    # --------------------------------------------------------

    for item in stocks.values():

        if not isinstance(item, dict):
            raise ValueError(
                "既有股票策略資料格式錯誤"
            )

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
# 8. 取得需要分析的股票
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

        if item.get("status") == "holding":

            required.add(
                normalize_stock_id(stock_id)
            )

    return sorted(required)


# ============================================================
# 9. 安全儲存策略狀態
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
        # 9.1 寫入暫存檔
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
        # 9.2 重新讀取並驗證暫存檔
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
        # 9.3 原子替換正式檔案
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
