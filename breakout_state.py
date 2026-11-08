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
    "stock_id", "watchlist_active", "status",
    "last_processed_date", "watch_signal",
    "entry_signal", "exit_signal", "active_trade",
    "signal_history", "trade_history", "updated_at"
}

VALID_STATUSES = {
    "inactive", "watching", "pending_entry",
    "holding", "stopped"
}

ACTIVE_TRADE_REQUIRED_FIELDS = {
    "entry_signal_date", "entry_date", "entry_price",
    "holding_days", "highest_price", "lowest_price",
    "mfe_pct", "mae_pct", "pending_exit_date",
    "pending_exit_reason"
}

COMPLETED_TRADE_REQUIRED_FIELDS = (
    ACTIVE_TRADE_REQUIRED_FIELDS
    | {"exit_date", "exit_price", "return_pct", "exit_reason"}
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
        raise TypeError("股票代號只能是非負整數或數字字串")

    if not stock_id:
        raise ValueError("股票代號不可為空")

    if re.fullmatch(r"[0-9]+", stock_id) is None:
        raise ValueError(f"股票代號必須是純數字：{stock_id!r}")

    return stock_id.zfill(4)


def validate_iso_date(value, field_name, allow_none=True):
    if value is None:
        if allow_none:
            return True
        raise ValueError(f"{field_name} 不可為空")

    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必須是 YYYY-MM-DD 字串")

    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} 不是有效日期：{value!r}"
        ) from exc

    if parsed.isoformat() != value:
        raise ValueError(f"{field_name} 日期格式錯誤：{value!r}")

    return True


def validate_finite_number(value, field_name):
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 不可為布林值")

    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} 必須是數值")

    if not math.isfinite(value):
        raise ValueError(f"{field_name} 必須是有限數值")

    return True


def validate_positive_number(value, field_name):
    validate_finite_number(value, field_name)

    if value <= 0:
        raise ValueError(f"{field_name} 必須大於 0")

    return True


def validate_non_negative_integer(value, field_name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} 必須是整數")

    if value < 0:
        raise ValueError(f"{field_name} 不可小於 0")

    return True


def validate_non_empty_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必須是非空字串")

    return True


def get_valid_price(value, field_name):
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 不可為布林值")

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 不是有效數值") from exc

    if not math.isfinite(number) or number <= 0:
        raise ValueError(
            f"{field_name} 必須是大於 0 的有限數值"
        )

    return number


# ============================================================
# 2. 訊號資料驗證
# ============================================================

def validate_signal_object(signal, stock_id, field_name):
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
        trade["entry_price"], f"股票 {stock_id} entry_price"
    )
    validate_non_negative_integer(
        trade["holding_days"], f"股票 {stock_id} holding_days"
    )

    if trade["holding_days"] < 1:
        raise ValueError(
            f"股票 {stock_id} 持有天數至少必須為 1"
        )

    validate_positive_number(
        trade["highest_price"], f"股票 {stock_id} highest_price"
    )
    validate_positive_number(
        trade["lowest_price"], f"股票 {stock_id} lowest_price"
    )

    if trade["highest_price"] < trade["lowest_price"]:
        raise ValueError(
            f"股票 {stock_id} 的最高價不得低於最低價"
        )

    validate_finite_number(
        trade["mfe_pct"], f"股票 {stock_id} mfe_pct"
    )
    validate_finite_number(
        trade["mae_pct"], f"股票 {stock_id} mae_pct"
    )

    pending_reason = trade["pending_exit_reason"]

    if trade["pending_exit_date"] is None:
        if pending_reason is not None:
            raise ValueError(
                f"股票 {stock_id} 待出場日期為空，但待出場原因不為空"
            )
    else:
        if pending_reason is None:
            raise ValueError(
                f"股票 {stock_id} 有待出場日期，但待出場原因為空"
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

    exit_date = datetime.date.fromisoformat(trade["exit_date"])
    entry_date = datetime.date.fromisoformat(trade["entry_date"])
    pending_date = datetime.date.fromisoformat(
        trade["pending_exit_date"]
    )

    if exit_date <= entry_date:
        raise ValueError("出場日期必須晚於進場日期")

    if exit_date <= pending_date:
        raise ValueError("實際出場日期必須晚於停損訊號日期")

    validate_positive_number(
        trade["exit_price"], f"股票 {stock_id} exit_price"
    )
    validate_finite_number(
        trade["return_pct"], f"股票 {stock_id} return_pct"
    )
    validate_non_empty_string(
        trade["exit_reason"], f"股票 {stock_id} exit_reason"
    )

    return True


# ============================================================
# 4. 建立狀態
# ============================================================

def create_stock_state(stock_id, watchlist_active=True):
    stock_id = normalize_stock_id(stock_id)

    if not isinstance(watchlist_active, bool):
        raise ValueError("watchlist_active 必須是布林值")

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
            "舊版策略狀態相容處理完成：%s 檔股票轉為 pending_entry。",
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

    if isinstance(stock_count, bool) or not isinstance(stock_count, int):
        raise ValueError("stock_count 必須是整數")

    if stock_count < 0 or stock_count != len(stocks):
        raise ValueError("stock_count 與實際股票數量不一致")

    for stock_id, item in stocks.items():
        if not isinstance(stock_id, str):
            raise ValueError("股票字典 key 必須是字串")

        if normalize_stock_id(stock_id) != stock_id:
            raise ValueError(f"股票字典 key 未正規化：{stock_id}")

        if not isinstance(item, dict):
            raise ValueError(f"股票 {stock_id} 的策略資料格式錯誤")

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
            raise ValueError("watchlist_active 必須是布林值")

        if item["status"] not in VALID_STATUSES:
            raise ValueError(
                f"股票 {stock_id} 的 status 不合法"
            )

        validate_iso_date(
            item["last_processed_date"],
            f"股票 {stock_id} last_processed_date"
        )

        for field in ("watch_signal", "entry_signal", "exit_signal"):
            validate_signal_object(item[field], stock_id, field)

        active_trade = item["active_trade"]

        if active_trade is not None:
            validate_active_trade(active_trade, stock_id)

        if item["status"] == "holding" and active_trade is None:
            raise ValueError(
                f"股票 {stock_id} 狀態為 holding，但缺少 active_trade"
            )

        if active_trade is not None and item["status"] != "holding":
            raise ValueError(
                f"股票 {stock_id} 有 active_trade，但 status 不是 holding"
            )

        if (
            item["status"] == "watching"
            and item["watch_signal"] is None
        ):
            raise ValueError(
                f"股票 {stock_id} 狀態為 watching，但缺少 watch_signal"
            )

        if (
            item["status"] != "watching"
            and item["watch_signal"] is not None
        ):
            raise ValueError(
                f"股票 {stock_id} 不是 watching，但仍保留 watch_signal"
            )

        if (
            item["status"] == "pending_entry"
            and item["entry_signal"] is None
        ):
            raise ValueError(
                f"股票 {stock_id} 狀態為 pending_entry，但缺少 entry_signal"
            )

        if (
            item["status"] != "pending_entry"
            and item["entry_signal"] is not None
        ):
            raise ValueError(
                f"股票 {stock_id} 不是 pending_entry，但仍保留 entry_signal"
            )

        for field in ("signal_history", "trade_history"):
            if not isinstance(item[field], list):
                raise ValueError(
                    f"股票 {stock_id} 的 {field} 必須是陣列"
                )

        for index, record in enumerate(item["signal_history"]):
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

        for index, trade in enumerate(item["trade_history"]):
            validate_completed_trade(trade, stock_id, index)

    return True


# ============================================================
# 7. 載入狀態
# ============================================================

def load_breakout_state(state_file):
    state_file = Path(state_file)

    if not state_file.exists():
        logging.info("尚無 breakout_state.json，建立新狀態。")
        return create_empty_state()

    try:
        with state_file.open("r", encoding="utf-8") as file:
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
            "讀取 breakout_state.json 失敗，停止更新以保護歷史紀錄。"
        )
        raise


# ============================================================
# 8. 同步觀察清單
# ============================================================

def sync_watchlist(state, watchlist):
    if not isinstance(watchlist, (list, tuple)):
        raise ValueError("watchlist 必須是股票代號清單")

    if not isinstance(state, dict):
        raise ValueError("策略狀態必須是字典")

    stocks = state.get("stocks")

    if not isinstance(stocks, dict):
        raise ValueError("策略狀態缺少有效的 stocks")

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
            new_stock_states[stock_id] = create_stock_state(stock_id)

    for stock_id, item in stocks.items():
        item["watchlist_active"] = (
            stock_id in normalized_watchlist
        )

    stocks.update(new_stock_states)
    state["stock_count"] = len(stocks)

    for stock_id in sorted(new_stock_states):
        logging.info("新增策略追蹤股票：%s", stock_id)

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

        elif item["status"] in {"pending_entry", "holding"}:
            required.add(stock_id)

    return sorted(required)


# ============================================================
# 10. 安全儲存狀態
# ============================================================

def save_breakout_state(state, state_file):
    state_file = Path(state_file)

    state_file.parent.mkdir(parents=True, exist_ok=True)

    save_data = copy.deepcopy(state)
    save_data["schema_version"] = SCHEMA_VERSION
    save_data["update_time"] = get_taipei_now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    if not isinstance(save_data.get("stocks"), dict):
        raise ValueError("策略狀態缺少有效的 stocks")

    save_data["stock_count"] = len(save_data["stocks"])

    validate_state(save_data)

    temp_file = state_file.with_name(state_file.name + ".tmp")

    try:
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump(
                save_data,
                file,
                ensure_ascii=False,
                indent=2,
                allow_nan=False
            )
            file.write("\n")

        with temp_file.open("r", encoding="utf-8") as file:
            verified_data = json.load(file)

        validate_state(verified_data)

        if len(verified_data["stocks"]) != len(save_data["stocks"]):
            raise ValueError("策略狀態股票數量驗證失敗")

        os.replace(temp_file, state_file)

        logging.info(
            "breakout_state.json 儲存完成，共 %s 檔股票。",
            len(save_data["stocks"])
        )

    except Exception:
        logging.exception("儲存 breakout_state.json 失敗。")

        try:
            if temp_file.exists():
                temp_file.unlink()
        except OSError:
            logging.exception("清理暫存檔失敗。")

        raise
