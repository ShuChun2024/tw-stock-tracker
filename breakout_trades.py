import copy
import datetime
import logging

from breakout_state import (
    get_valid_price,
    validate_iso_date,
    validate_non_empty_string,
    validate_completed_trade,
)


def update_trade_extremes(trade, high_price, low_price):
    high_price = get_valid_price(high_price, "high_price")
    low_price = get_valid_price(low_price, "low_price")

    if high_price < low_price:
        raise ValueError("當日最高價不得低於最低價")

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
        (trade["highest_price"] / entry_price - 1) * 100,
        4
    )

    trade["mae_pct"] = round(
        (trade["lowest_price"] / entry_price - 1) * 100,
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

    signal_day = datetime.date.fromisoformat(signal_date)
    entry_day = datetime.date.fromisoformat(entry_date)

    if signal_day > entry_day:
        raise ValueError("進場訊號日期不得晚於實際進場日期")

    entry_price = get_valid_price(entry_price, "entry_price")
    high_price = get_valid_price(high_price, "high_price")
    low_price = get_valid_price(low_price, "low_price")

    if high_price < low_price:
        raise ValueError("進場日最高價不得低於最低價")

    if not low_price <= entry_price <= high_price:
        raise ValueError("進場成交價不在當日高低價範圍內")

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

    update_trade_extremes(trade, high_price, low_price)

    return trade


def complete_active_trade(
    item,
    exit_date,
    exit_price,
    exit_reason
):
    trade = item["active_trade"]

    if trade is None:
        raise ValueError("沒有 active_trade，不能完成交易")

    validate_iso_date(
        exit_date,
        "exit_date",
        allow_none=False
    )

    exit_price = get_valid_price(exit_price, "exit_price")

    validate_non_empty_string(exit_reason, "exit_reason")

    if trade["pending_exit_date"] is None:
        raise ValueError("尚無待出場訊號，不能完成交易")

    exit_day = datetime.date.fromisoformat(exit_date)
    pending_day = datetime.date.fromisoformat(
        trade["pending_exit_date"]
    )
    entry_day = datetime.date.fromisoformat(trade["entry_date"])

    if exit_day <= pending_day:
        raise ValueError("實際出場日期必須晚於待出場訊號日期")

    if exit_day <= entry_day:
        raise ValueError("實際出場日期必須晚於進場日期")

    trade = copy.deepcopy(trade)

    trade["exit_date"] = exit_date
    trade["exit_price"] = exit_price

    trade["return_pct"] = round(
        (exit_price / trade["entry_price"] - 1) * 100,
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
        "股票 %s 完成交易：進場 %s，出場 %s，報酬 %.2f%%，"
        "持有 %s 個交易日",
        item["stock_id"],
        trade["entry_date"],
        exit_date,
        trade["return_pct"],
        trade["holding_days"]
    )
