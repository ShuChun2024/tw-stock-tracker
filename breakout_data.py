from breakout_state import (
    validate_iso_date,
)


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
        else technical.get("latest_low')
    )

    conditions = strategy.get("conditions')

    if not isinstance(conditions, dict):
        conditions = {}

    # 買進訊號
    buy_signal = (
        strategy.get("buy_signal") is True
        or conditions.get("buy_signal") is True
        or strategy.get("signal") == "buy"
    )

    # 觀察訊號
    watch_signal = (
        strategy.get("watch_signal") is True
        or conditions.get("watch_signal") is True
        or conditions.get("watch") is True
        or strategy.get("signal") in {"watch", "watching"}
        or strategy.get("status") == "watching"
    )

    # 停損訊號
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
