import copy
import datetime
import json
import logging
import math
import os
import re

from pathlib import Path

from config import TAIPEI_TZ


SCHEMA_VERSION = 1

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
    "pending_entry",
    "holding",
    "stopped"
}

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
# 1. 基本驗證
# ============================================================

def get_taipei_now():
    return datetime.datetime.now(TAIPEI_TZ)


def get_today_string():
    return get_taipei_now().strftime("%Y-%m-%d")


def normalize_stock_id(stock_id):

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


def validate_iso_date(value, field_name, allow_none=True):

    if value is None:

        if allow_none:
            return True

        raise ValueError(
            f"{field_name} 不可為空"
        )

    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} 必須是 YYYY-MM-DD 字串"
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


def validate_finite_number(value, field_name):

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

    validate_finite_number(value, field_name)

    if value <= 0:
        raise ValueError(
            f"{field_name} 必須大於 0"
        )

    return True


def validate_non_negative_integer(value, field_name):

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

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{field_name} 必須是非空字串"
        )

    return True


def get_valid_price(value, field_name):

    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} 不可為布林值"
        )

    try:
        number = float(value)

    except (TypeError, ValueError):
        raise ValueError(
            f"{field_name} 不是有效數值"
        )

    if not math.isfinite(number) or number <= 0:
        raise ValueError(
            f"{field_name} 必須是大於 0 的有限數值"
        )

    return number


# ============================================================
# 2. 訊號資料驗證
# ============================================================

def validate_signal_object(
    signal,
    stock_id,
    field_name
):

    if signal is None:
        return True

    if not isinstance(signal, dict):
        raise ValueError(
            f"股票 {stock_id} 的 {field_name} 必須是物件或 null"
        )

    if "date" not in signal:
        raise ValueError(
            f"股票 {stock_id} 的 {field_name} 缺少 date"
        )

    if "reason" not in signal:
        raise ValueError(
            f"股票 {stock_id} 的 {field_name} 缺少 reason"
        )

    validate_iso_date(
        signal["date"],
        f"股票 {stock_id} {field_name}.date",
        allow_none=False
    )

    validate_non_empty_string(
        signal["reason"],
        f"股票 {stock_id} {field_name}.reason"
    )

    if "execution_date" in signal:
        validate_iso_date(
            signal["execution_date"],
            f"股票 {stock_id} {field_name}.execution_date",
            allow_none=False
        )

    if "exit_price" in signal:
        validate_positive_number(
            signal["exit_price"],
            f"股票 {stock_id} {field_name}.exit_price"
        )

    return True


# ============================================================
# 3. 交易資料驗證
# ============================================================

def validate_active_trade(trade, stock_id):

    if not isinstance(trade, dict):
        raise ValueError(
            f"股票 {stock_id} 的 active_trade 必須是物件"
        )

    missing = ACTIVE_TRADE_REQUIRED_FIELDS - set(trade)

    if missing:
        raise ValueError(
            f"股票 {stock_id} 的 active_trade 缺少欄位："
            f"{', '.join(sorted(missing))}"
        )

    validate_iso_date(
        trade["entry_signal_date"],
        f"股票 {stock_id} entry_signal_date",
        allow_none=False
    )

    validate_iso_date(
        trade["entry_date"],
        f"股票 {stock_id} entry_date",
        allow_none=False
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
            f"股票 {stock_id} 的進場訊號日不得晚於實際進場日"
        )

    if trade["pending_exit_date"] is not None:

        pending_date = datetime.date.fromisoformat(
            trade["pending_exit_date"]
        )

        if pending_date < entry_date:
            raise ValueError(
                f"股票 {stock_id} 的待出場日期不得早於進場日"
            )

    validate_positive_number(
        trade["entry_price"],
        f"股票 {stock_id} entry_price"
    )

    validate_non_negative_integer(
        trade["holding_days"],
        f"股票 {stock_id} holding_days"
    )

    if trade["holding_days"] < 1:
        raise ValueError(
            f"股票 {stock_id} 持有天數至少必須為 1"
        )

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

    validate_finite_number(
        trade["mfe_pct"],
        f"股票 {stock_id} mfe_pct"
    )

    validate_finite_number(
        trade["mae_pct"],
        f"股票 {stock_id} mae_pct"
    )

    pending_reason = trade["pending_exit_reason"]

    if trade["pending_exit_date"] is None:

        if pending_reason is not None:
            raise ValueError(
                f"股票 {stock_id} 待出場日期為空，"
                "但待出場原因不為空"
            )

    else:

        if pending_reason is None:
            raise ValueError(
                f"股票 {stock_id} 有待出場日期，"
                "但待出場原因為空"
            )

        validate_non_empty_string(
            pending_reason,
            f"股票 {stock_id} pending_exit_reason"
        )

    return True


def validate_completed_trade(trade, stock_id, index):

    if not isinstance(trade, dict):
        raise ValueError(
            f"股票 {stock_id} 的 trade_history "
            f"第 {index + 1} 筆紀錄必須是物件"
        )

    missing = COMPLETED_TRADE_REQUIRED_FIELDS - set(trade)

    if missing:
        raise ValueError(
            f"股票 {stock_id} 的 trade_history "
            f"第 {index + 1} 筆紀錄缺少欄位："
            f"{', '.join(sorted(missing))}"
        )

    validate_active_trade(trade, stock_id)

    validate_iso_date(
        trade["exit_date"],
        f"股票 {stock_id} exit_date",
        allow_none=False
    )

    validate_iso_date(
        trade["pending_exit_date"],
        f"股票 {stock_id} pending_exit_date",
        allow_none=False
    )

    exit_date = datetime.date.fromisoformat(
        trade["exit_date"]
    )

    entry_date = datetime.date.fromisoformat(
        trade["entry_date"]
    )

    pending_date = datetime.date.fromisoformat(
        trade["pending_exit_date"]
    )

    if exit_date <= entry_date:
        raise ValueError(
            "出場日期必須晚於進場日期"
        )

    if exit_date <= pending_date:
        raise ValueError(
            "實際出場日期必須晚於停損訊號日期"
        )

    validate_positive_number(
        trade["exit_price"],
        f"股票 {stock_id} exit_price"
    )

    validate_finite_number(
        trade["return_pct"],
        f"股票 {stock_id} return_pct"
    )

    validate_non_empty_string(
        trade["exit_reason"],
        f"股票 {stock_id} exit_reason"
    )

    return True


# ============================================================
# 4. 建立狀態
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
# 5. 舊版狀態相容處理
# ============================================================

def migrate_legacy_state(data):

    if not isinstance(data, dict):
        return data

    stocks = data.get("stocks")

    if not isinstance(stocks, dict):
        return data

    migrated_count = 0

    for item in stocks.values():

        if not isinstance(item, dict):
            continue

        if (
            item.get("status") == "watching"
            and isinstance(item.get("entry_signal"), dict)
        ):

            item["status"] = "pending_entry"
            item["watch_signal"] = None

            migrated_count += 1

    if migrated_count:

        logging.info(
            "舊版策略狀態相容處理完成："
            "%s 檔股票轉為 pending_entry。",
            migrated_count
        )

    return data


# ============================================================
# 6. 狀態完整性驗證
# ============================================================

def validate_state(data):

    if not isinstance(data, dict):
        raise ValueError(
            "breakout_state.json 根節點必須是 JSON 物件"
        )

    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "breakout_state.json schema_version 不符合"
        )

    stocks = data.get("stocks")

    if not isinstance(stocks, dict):
        raise ValueError(
            "breakout_state.json 缺少有效的 stocks"
        )

    stock_count = data.get("stock_count")

    if (
        isinstance(stock_count, bool)
        or not isinstance(stock_count, int)
    ):
        raise ValueError(
            "stock_count 必須是整數"
        )

    if stock_count < 0 or stock_count != len(stocks):
        raise ValueError(
            "stock_count 與實際股票數量不一致"
        )

    for stock_id, item in stocks.items():

        if not isinstance(stock_id, str):
            raise ValueError(
                "股票字典 key 必須是字串"
            )

        if normalize_stock_id(stock_id) != stock_id:
            raise ValueError(
                f"股票字典 key 未正規化：{stock_id}"
            )

        if not isinstance(item, dict):
            raise ValueError(
                f"股票 {stock_id} 的策略資料格式錯誤"
            )

        missing = REQUIRED_STOCK_FIELDS - set(item)

        if missing:
            raise ValueError(
                f"股票 {stock_id} 缺少必要欄位："
                f"{', '.join(sorted(missing))}"
            )

        if item["stock_id"] != stock_id:
            raise ValueError(
                f"股票 {stock_id} 的 key 與 stock_id 不一致"
            )

        if not isinstance(item["watchlist_active"], bool):
            raise ValueError(
                "watchlist_active 必須是布林值"
            )

        if item["status"] not in VALID_STATUSES:
            raise ValueError(
                f"股票 {stock_id} 的 status 不合法"
            )

        validate_iso_date(
            item["last_processed_date"],
            f"股票 {stock_id} last_processed_date"
        )

        validate_signal_object(
            item["watch_signal"],
            stock_id,
            "watch_signal"
        )

        validate_signal_object(
            item["entry_signal"],
            stock_id,
            "entry_signal"
        )

        validate_signal_object(
            item["exit_signal"],
            stock_id,
            "exit_signal"
        )

        active_trade = item["active_trade"]

        if active_trade is not None:
            validate_active_trade(
                active_trade,
                stock_id
            )

        if (
            item["status"] == "holding"
            and active_trade is None
        ):
            raise ValueError(
                f"股票 {stock_id} 狀態為 holding，"
                "但缺少 active_trade"
            )

        if (
            active_trade is not None
            and item["status"] != "holding"
        ):
            raise ValueError(
                f"股票 {stock_id} 有 active_trade，"
                "但 status 不是 holding"
            )

        if (
            item["status"] == "watching"
            and item["watch_signal"] is None
        ):
            raise ValueError(
                f"股票 {stock_id} 狀態為 watching，"
                "但缺少 watch_signal"
            )

        if (
            item["status"] != "watching"
            and item["watch_signal"] is not None
        ):
            raise ValueError(
                f"股票 {stock_id} 不是 watching，"
                "但仍保留 watch_signal"
            )

        if (
            item["status"] == "pending_entry"
            and item["entry_signal"] is None
        ):
            raise ValueError(
                f"股票 {stock_id} 狀態為 pending_entry，"
                "但缺少 entry_signal"
            )

        if (
            item["status"] != "pending_entry"
            and item["entry_signal"] is not None
        ):
            raise ValueError(
                f"股票 {stock_id} 不是 pending_entry，"
                "但仍保留 entry_signal"
            )

        for field in (
            "signal_history",
            "trade_history"
        ):

            if not isinstance(item[field], list):
                raise ValueError(
                    f"股票 {stock_id} 的 {field} 必須是陣列"
                )

        for index, record in enumerate(
            item["signal_history"]
        ):

            if not isinstance(record, dict):
                raise ValueError(
                    f"股票 {stock_id} 的 signal_history "
                    f"第 {index + 1} 筆不是物件"
                )

            if "date" not in record:
                raise ValueError(
                    f"股票 {stock_id} 的 signal_history "
                    f"第 {index + 1} 筆缺少日期"
                )

            validate_iso_date(
                record["date"],
                f"股票 {stock_id} signal_history date",
                allow_none=False
            )

        for index, trade in enumerate(
            item["trade_history"]
        ):

            validate_completed_trade(
                trade,
                stock_id,
                index
            )

    return True


# ============================================================
# 7. 載入狀態
# ============================================================

def load_breakout_state(state_file):

    state_file = Path(state_file)

    if not state_file.exists():

        logging.info(
            "尚無 breakout_state.json，建立新狀態。"
        )

        return create_empty_state()

    try:

        with state_file.open(
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        data = migrate_legacy_state(data)

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
# 8. 同步觀察清單
# ============================================================

def sync_watchlist(state, watchlist):

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
            "策略狀態缺少有效的 stocks"
        )

    normalized_watchlist = {
        normalize_stock_id(stock_id)
        for stock_id in watchlist
    }

    for stock_id, item in stocks.items():

        if not isinstance(item, dict):
            raise ValueError(
                f"既有股票 {stock_id} 策略資料格式錯誤"
            )

        if normalize_stock_id(stock_id) != stock_id:
            raise ValueError(
                f"既有股票代號未正規化：{stock_id}"
            )

        if item.get("stock_id") != stock_id:
            raise ValueError(
                f"股票 {stock_id} 的 key 與 stock_id 不一致"
            )

    new_stock_states = {}

    for stock_id in normalized_watchlist:

        if stock_id not in stocks:

            new_stock_states[stock_id] = (
                create_stock_state(stock_id)
            )

    for stock_id, item in stocks.items():

        item["watchlist_active"] = (
            stock_id in normalized_watchlist
        )

    stocks.update(new_stock_states)

    state["stock_count"] = len(stocks)

    for stock_id in sorted(new_stock_states):

        logging.info(
            "新增策略追蹤股票：%s",
            stock_id
        )

    for stock_id, item in stocks.items():

        if not item["watchlist_active"]:

            logging.info(
                "股票 %s 已移出觀察清單，保留策略歷史。",
                stock_id
            )

    return state


# ============================================================
# 9. 取得需要分析的股票
# ============================================================

def get_required_stock_ids(state):

    validate_state(state)

    required = set()

    for stock_id, item in state["stocks"].items():

        if item["watchlist_active"] is True:
            required.add(stock_id)

        elif item["status"] in {
            "pending_entry",
            "holding"
        }:
            required.add(stock_id)

    return sorted(required)


# ============================================================
# 10. 交易紀錄工具
# ============================================================

def append_signal_history(
    item,
    signal_type,
    signal_date,
    reason=None
):

    validate_iso_date(
        signal_date,
        "signal_date",
        allow_none=False
    )

    for record in item["signal_history"]:

        if (
            record.get("type") == signal_type
            and record.get("date") == signal_date
        ):
            return

    record = {
        "type": signal_type,
        "date": signal_date
    }

    if reason is not None:
        record["reason"] = reason

    item["signal_history"].append(record)


def update_trade_extremes(
    trade,
    high_price,
    low_price
):

    high_price = get_valid_price(
        high_price,
        "high_price"
    )

    low_price = get_valid_price(
        low_price,
        "low_price"
    )

    if high_price < low_price:
        raise ValueError(
            "當日最高價不得低於最低價"
        )

    entry_price = trade["entry_price"]

    trade["highest_price"] = max(
        trade["highest_price"],
        high_price,
        entry_price
    )

    trade["lowest_price"] = min(
        trade["lowest_price"],
        low_price,
        entry_price
    )

    trade["mfe_pct"] = round(
        (
            trade["highest_price"] / entry_price - 1
        ) * 100,
        4
    )

    trade["mae_pct"] = round(
        (
            trade["lowest_price"] / entry_price - 1
        ) * 100,
        4
    )


def create_active_trade(
    signal_date,
    entry_date,
    entry_price,
    high_price,
    low_price
):

    validate_iso_date(
        signal_date,
        "entry_signal_date",
        allow_none=False
    )

    validate_iso_date(
        entry_date,
        "entry_date",
        allow_none=False
    )

    signal_day = datetime.date.fromisoformat(
        signal_date
    )

    entry_day = datetime.date.fromisoformat(
        entry_date
    )

    if signal_day > entry_day:
        raise ValueError(
            "進場訊號日期不得晚於實際進場日期"
        )

    entry_price = get_valid_price(
        entry_price,
        "entry_price"
    )

    high_price = get_valid_price(
        high_price,
        "high_price"
    )

    low_price = get_valid_price(
        low_price,
        "low_price"
    )

    if high_price < low_price:
        raise ValueError(
            "進場日最高價不得低於最低價"
        )

    if not low_price <= entry_price <= high_price:
        raise ValueError(
            "進場成交價不在當日高低價範圍內"
        )

    trade = {
        "entry_signal_date": signal_date,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "holding_days": 1,
        "highest_price": max(entry_price, high_price),
        "lowest_price": min(entry_price, low_price),
        "mfe_pct": 0.0,
        "mae_pct": 0.0,
        "pending_exit_date": None,
        "pending_exit_reason": None
    }

    update_trade_extremes(
        trade,
        high_price,
        low_price
    )

    return trade


def complete_active_trade(
    item,
    exit_date,
    exit_price,
    exit_reason
):

    trade = item["active_trade"]

    if trade is None:
        raise ValueError(
            "沒有 active_trade，不能完成交易"
        )

    validate_iso_date(
        exit_date,
        "exit_date",
        allow_none=False
    )

    exit_price = get_valid_price(
        exit_price,
        "exit_price"
    )

    validate_non_empty_string(
        exit_reason,
        "exit_reason"
    )

    if trade["pending_exit_date"] is None:
        raise ValueError(
            "尚無待出場訊號，不能完成交易"
        )

    exit_day = datetime.date.fromisoformat(
        exit_date
    )

    pending_day = datetime.date.fromisoformat(
        trade["pending_exit_date"]
    )

    entry_day = datetime.date.fromisoformat(
        trade["entry_date"]
    )

    if exit_day <= pending_day:
        raise ValueError(
            "實際出場日期必須晚於待出場訊號日期"
        )

    if exit_day <= entry_day:
        raise ValueError(
            "實際出場日期必須晚於進場日期"
        )

    trade = copy.deepcopy(trade)

    trade["exit_date"] = exit_date
    trade["exit_price"] = exit_price

    trade["return_pct"] = round(
        (
            exit_price / trade["entry_price"] - 1
        ) * 100,
        4
    )

    trade["exit_reason"] = exit_reason

    validate_completed_trade(
        trade,
        item["stock_id"],
        len(item["trade_history"])
    )

    item["trade_history"].append(trade)

    item["active_trade"] = None
    item["status"] = "stopped"

    item["exit_signal"] = {
        "date": trade["pending_exit_date"],
        "execution_date": exit_date,
        "reason": exit_reason,
        "exit_price": exit_price
    }

    logging.info(
        "股票 %s 完成交易：進場 %s，出場 %s，"
        "報酬 %.2f%%，持有 %s 個交易日",
        item["stock_id"],
        trade["entry_date"],
        exit_date,
        trade["return_pct"],
        trade["holding_days"]
    )


# ============================================================
# 11. 解析 technical.py 的分析結果
# ============================================================

def extract_breakout_data(stock_result):

    if not isinstance(stock_result, dict):
        return None

    technical = stock_result.get("technical")

    if not isinstance(technical, dict):
        return None

    strategy = technical.get("breakout_strategy")

    if not isinstance(strategy, dict):
        return None

    if strategy.get("data_available") is not True:
        return None

    candle = strategy.get("candle")

    if not isinstance(candle, dict):
        candle = {}

    latest_date = (
        strategy.get("latest_date")
        or technical.get("latest_date")
    )

    if latest_date is None:
        return None

    validate_iso_date(
        latest_date,
        "breakout latest_date",
        allow_none=False
    )

    latest_open = (
        candle.get("open")
        if candle.get("open") is not None
        else strategy.get("latest_open")
    )

    latest_close = (
        candle.get("close")
        if candle.get("close") is not None
        else technical.get("latest_close")
    )

    latest_high = (
        strategy.get("latest_high")
        if strategy.get("latest_high") is not None
        else technical.get("latest_high")
    )

    latest_low = (
        strategy.get("latest_low")
        if strategy.get("latest_low") is not None
        else technical.get("latest_low")
    )

    conditions = strategy.get("conditions")

    if not isinstance(conditions, dict):
        conditions = {}

    # --------------------------------------------------------
    # 買進訊號
    # --------------------------------------------------------

    buy_signal = (
        strategy.get("buy_signal") is True
        or conditions.get("buy_signal") is True
        or strategy.get("signal") == "buy"
    )

    # --------------------------------------------------------
    # 觀察訊號
    #
    # 支援不同可能的輸出位置：
    # 1. strategy.signal = "watch"
    # 2. strategy.status = "watching"
    # 3. strategy.watch_signal = True
    # 4. conditions.watch_signal = True
    # 5. conditions.watch = True
    # --------------------------------------------------------

    watch_signal = (
        strategy.get("watch_signal") is True
        or conditions.get("watch_signal") is True
        or conditions.get("watch") is True
        or strategy.get("signal") in {
            "watch",
            "watching"
        }
        or strategy.get("status") == "watching"
    )

    # --------------------------------------------------------
    # 停損訊號
    # --------------------------------------------------------

    stop_condition = (
        strategy.get("stop_condition_met") is True
        or conditions.get("stop_condition_met") is True
        or conditions.get("stop_condition") is True
    )

    return {
        "date": latest_date,
        "open": latest_open,
        "close": latest_close,
        "high": latest_high,
        "low": latest_low,
        "buy_signal": buy_signal,
        "watch_signal": watch_signal,
        "stop_condition": stop_condition
    }


# ============================================================
# 12. 每日交易狀態更新
# ============================================================

def process_breakout_stock(
    state,
    stock_id,
    stock_result
):
    """
    每檔股票每日只處理一次。

    狀態：
        inactive：
            沒有觀察或待進場訊號。

        watching：
            盤整蓄勢觀察中。

        pending_entry：
            突破買進訊號成立，等待下一交易日開盤進場。

        holding：
            已實際進場持有。

        stopped：
            已完成出場，等待下一次訊號。

    買進：
        訊號日收盤確認，下一個可取得交易日以開盤價進場。

    停損：
        收盤跌破布林中軌，下一個可取得交易日以開盤價出場。

    注意：
        本函式目前使用 technical.py 傳入的最新一筆行情。
        若工作流程漏跑，僅憑最新一筆行情無法確認中間是否
        已經有其他交易日，因此不能保證補跑時一定是訊號後
        的第一個交易日。
    """

    stock_id = normalize_stock_id(stock_id)

    if not isinstance(state, dict):
        raise ValueError(
            "策略狀態必須是字典"
        )

    stocks = state.get("stocks")

    if not isinstance(stocks, dict):
        raise ValueError(
            "策略狀態缺少 stocks"
        )

    if stock_id not in stocks:
        raise ValueError(
            f"策略狀態中找不到股票：{stock_id}"
        )

    item = stocks[stock_id]

    if not isinstance(item, dict):
        raise ValueError(
            f"股票 {stock_id} 的策略資料格式錯誤"
        )

    market = extract_breakout_data(stock_result)

    if market is None:

        logging.warning(
            "股票 %s 缺少有效布林策略資料，"
            "本次不更新狀態。",
            stock_id
        )

        return False

    today = market["date"]

    today_date = datetime.date.fromisoformat(today)

    # --------------------------------------------------------
    # 12.1 取得開盤價
    # --------------------------------------------------------

    open_price = None

    if market["open"] is not None:

        open_price = get_valid_price(
            market["open"],
            "latest_open"
        )

    # --------------------------------------------------------
    # 12.2 同一交易日防重複及未保存訊號補救
    # --------------------------------------------------------

    last_date = item["last_processed_date"]

    if last_date is not None:

        validate_iso_date(
            last_date,
            "last_processed_date",
            allow_none=False
        )

        last_processed_day = datetime.date.fromisoformat(
            last_date
        )

        if today_date < last_processed_day:

            logging.info(
                "股票 %s 資料日期 %s 早於最後處理日期 %s，"
                "跳過較舊資料。",
                stock_id,
                today,
                last_date
            )

            return False

        if today_date == last_processed_day:

            # 同日只允許補救尚未保存訊號的 inactive 股票。
            can_recover_signal = (
                item["status"] == "inactive"
                and item["watch_signal"] is None
                and item["entry_signal"] is None
                and item["active_trade"] is None
                and (
                    market["watch_signal"]
                    or market["buy_signal"]
                )
            )

            if not can_recover_signal:

                logging.info(
                    "股票 %s 交易日 %s 已處理，"
                    "沒有符合補救條件，跳過重複資料。",
                    stock_id,
                    today
                )

                return False

            logging.warning(
                "股票 %s 交易日 %s 發現尚未保存的訊號，"
                "允許同日補救處理。",
                stock_id,
                today
            )

    # --------------------------------------------------------
    # 12.3 有待出場交易：下一交易日開盤出場
    # --------------------------------------------------------

    trade = item["active_trade"]

    if (
        trade is not None
        and trade["pending_exit_date"] is not None
        and today > trade["pending_exit_date"]
    ):

        if open_price is None:

            logging.warning(
                "股票 %s 缺少出場日開盤價，"
                "保留待出場狀態。",
                stock_id
            )

            return False

        trade["holding_days"] += 1

        # 出場在開盤執行，因此不計入出場日後續高低價。
        update_trade_extremes(
            trade,
            open_price,
            open_price
        )

        exit_reason = trade["pending_exit_reason"]

        complete_active_trade(
            item=item,
            exit_date=today,
            exit_price=open_price,
            exit_reason=exit_reason
        )

        item["last_processed_date"] = today
        item["updated_at"] = get_taipei_now().isoformat()

        return True

    # --------------------------------------------------------
    # 12.4 有待進場訊號：下一交易日開盤進場
    # --------------------------------------------------------

    entry_signal = item["entry_signal"]

    if (
        item["status"] == "pending_entry"
        and item["active_trade"] is None
        and isinstance(entry_signal, dict)
        and today > entry_signal.get("date", "")
    ):

        if open_price is None:

            logging.warning(
                "股票 %s 缺少進場日開盤價，"
                "保留待進場訊號。",
                stock_id
            )

            return False

        if market["high"] is None or market["low"] is None:

            logging.warning(
                "股票 %s 缺少進場日高低價，"
                "暫不建立持倉。",
                stock_id
            )

            return False

        high_price = get_valid_price(
            market["high"],
            "latest_high"
        )

        low_price = get_valid_price(
            market["low"],
            "latest_low"
        )

        if high_price < low_price:
            raise ValueError(
                f"股票 {stock_id} 的當日最高價低於最低價"
            )

        if not low_price <= open_price <= high_price:
            raise ValueError(
                f"股票 {stock_id} 的開盤價不在當日高低價範圍內"
            )

        signal_date = entry_signal.get("date")

        validate_iso_date(
            signal_date,
            "entry_signal.date",
            allow_none=False
        )

        new_trade = create_active_trade(
            signal_date=signal_date,
            entry_date=today,
            entry_price=open_price,
            high_price=high_price,
            low_price=low_price
        )

        item["active_trade"] = new_trade

        item["entry_signal"] = None
        item["watch_signal"] = None
        item["status"] = "holding"

        logging.info(
            "股票 %s 進場：訊號日 %s，成交日 %s，價格 %.2f",
            stock_id,
            signal_date,
            today,
            open_price
        )

        # 進場日若收盤即觸發停損，
        # 下一交易日開盤才執行出場。
        if market["stop_condition"]:

            trade = item["active_trade"]

            trade["pending_exit_date"] = today

            trade["pending_exit_reason"] = (
                "收盤跌破布林中軌"
            )

            item["exit_signal"] = {
                "date": today,
                "reason": "收盤跌破布林中軌"
            }

            append_signal_history(
                item,
                "stop",
                today,
                "收盤跌破布林中軌"
            )

        item["last_processed_date"] = today
        item["updated_at"] = get_taipei_now().isoformat()

        return True

    # --------------------------------------------------------
    # 12.5 已持倉：更新當日高低價及 MFE / MAE
    # --------------------------------------------------------

    trade = item["active_trade"]

    if trade is not None:

        if market["high"] is None or market["low"] is None:

            logging.warning(
                "股票 %s 缺少當日高低價，"
                "暫不更新持倉。",
                stock_id
            )

            return False

        high_price = get_valid_price(
            market["high"],
            "latest_high"
        )

        low_price = get_valid_price(
            market["low"],
            "latest_low"
        )

        if high_price < low_price:
            raise ValueError(
                f"股票 {stock_id} 的當日最高價低於最低價"
            )

        trade["holding_days"] += 1

        update_trade_extremes(
            trade,
            high_price,
            low_price
        )

        # ----------------------------------------------------
        # 12.6 收盤跌破布林中軌，建立待出場訊號
        # ----------------------------------------------------

        if (
            market["stop_condition"]
            and trade["pending_exit_date"] is None
        ):

            trade["pending_exit_date"] = today

            trade["pending_exit_reason"] = (
                "收盤跌破布林中軌"
            )

            item["exit_signal"] = {
                "date": today,
                "reason": "收盤跌破布林中軌"
            }

            append_signal_history(
                item,
                "stop",
                today,
                "收盤跌破布林中軌"
            )

            logging.info(
                "股票 %s 出現停損訊號：%s，"
                "預計下一交易日開盤出場。",
                stock_id,
                today
            )

        item["last_processed_date"] = today
        item["updated_at"] = get_taipei_now().isoformat()

        return True

    # --------------------------------------------------------
    # 12.7 無持倉：處理買進及觀察訊號
    # --------------------------------------------------------

    # 買進訊號優先於觀察訊號。
    if market["buy_signal"]:

        append_signal_history(
            item,
            "buy",
            today,
            "布林突破買進條件成立"
        )

        item["entry_signal"] = {
            "date": today,
            "reason": "布林突破買進條件成立"
        }

        item["watch_signal"] = None
        item["exit_signal"] = None
        item["status"] = "pending_entry"

        logging.info(
            "股票 %s 出現買進訊號：%s，"
            "預計下一交易日開盤進場。",
            stock_id,
            today
        )

    # --------------------------------------------------------
    # 有盤整觀察訊號
    # --------------------------------------------------------

    elif market["watch_signal"]:

        # 第一次進入 watching 才新增訊號歷史。
        if (
            item["status"] != "watching"
            or item["watch_signal"] is None
        ):

            append_signal_history(
                item,
                "watch",
                today,
                "布林收斂且股價呈現盤整"
            )

            item["watch_signal"] = {
                "date": today,
                "reason": "布林收斂且股價呈現盤整"
            }

            logging.info(
                "股票 %s 開始盤整觀察：%s。",
                stock_id,
                today
            )

        # 持續觀察時更新狀態，但不重複新增訊號。
        item["status"] = "watching"

    # --------------------------------------------------------
    # 原本正在觀察，但觀察條件已解除
    # --------------------------------------------------------

    elif item["status"] == "watching":

        append_signal_history(
            item,
            "watch_end",
            today,
            "盤整觀察條件已解除"
        )

        item["watch_signal"] = None
        item["status"] = "inactive"

        logging.info(
            "股票 %s 解除盤整觀察：%s。",
            stock_id,
            today
        )

    # --------------------------------------------------------
    # 其他狀態
    # --------------------------------------------------------

    # inactive：沒有訊號，維持 inactive。
    # stopped：已完成交易且目前沒有新訊號，保留 stopped。
    # 不清除歷史交易及出場紀錄。

    item["last_processed_date"] = today
    item["updated_at"] = get_taipei_now().isoformat()

    return True


# ============================================================
# 13. 安全儲存狀態
# ============================================================

def save_breakout_state(state, state_file):

    state_file = Path(state_file)

    state_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    save_data = copy.deepcopy(state)

    save_data["schema_version"] = SCHEMA_VERSION

    save_data["update_time"] = (
        get_taipei_now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    if not isinstance(save_data.get("stocks"), dict):
        raise ValueError(
            "策略狀態缺少有效的 stocks"
        )

    save_data["stock_count"] = len(
        save_data["stocks"]
    )

    validate_state(save_data)

    temp_file = state_file.with_name(
        state_file.name + ".tmp"
    )

    try:

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

        # 寫入後重新讀取驗證。
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
                "清理暫存檔失敗。"
            )

        raise
