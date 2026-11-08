import logging


def append_signal_history(
    item,
    signal_type,
    signal_date,
    reason=None
):
    from breakout_state import validate_iso_date

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


def process_idle_signal(item, stock_id, market, today):
    """
    處理沒有持倉、沒有待進場交易時的訊號。

    買進訊號優先於觀察訊號。
    """

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
            "股票 %s 出現買進訊號：%s，預計下一交易日開盤進場。",
            stock_id,
            today
        )

    elif market["watch_signal"]:
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

        item["status"] = "watching"

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

    # inactive：沒有訊號，維持 inactive。
    # stopped：沒有新訊號時，保留 stopped。
