import datetime
import logging

from breakout_state import (
    get_taipei_now,
    normalize_stock_id,
    validate_iso_date,
    get_valid_price,
    load_breakout_state,
    sync_watchlist,
    get_required_stock_ids,
    save_breakout_state,
)

from breakout_data import (
    extract_breakout_data,
)

from breakout_signals import (
    append_signal_history,
    process_idle_signal,
)

from breakout_trades import (
    update_trade_extremes,
    create_active_trade,
    complete_active_trade,
)


# ============================================================
# 1. 每日交易狀態更新
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
        raise ValueError("策略狀態必須是字典")

    stocks = state.get("stocks")

    if not isinstance(stocks, dict):
        raise ValueError("策略狀態缺少 stocks")

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
            "股票 %s 缺少有效布林策略資料，本次不更新狀態。",
            stock_id
        )
        return False

    today = market["date"]
    today_date = datetime.date.fromisoformat(today)

    # --------------------------------------------------------
    # 1.1 取得開盤價
    # --------------------------------------------------------

    open_price = None

    if market["open"] is not None:
        open_price = get_valid_price(
            market["open"],
            "latest_open"
        )

    # --------------------------------------------------------
    # 1.2 同一交易日防重複及未保存訊號補救
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
                "股票 %s 資料日期 %s 早於最後處理日期 %s，跳過較舊資料。",
                stock_id,
                today,
                last_date
            )
            return False

        if today_date == last_processed_day:
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
                "股票 %s 交易日 %s 發現尚未保存的訊號，允許同日補救處理。",
                stock_id,
                today
            )

    # --------------------------------------------------------
    # 1.3 有待出場交易：下一交易日開盤出場
    # --------------------------------------------------------

    trade = item["active_trade"]

    if (
        trade is not None
        and trade["pending_exit_date"] is not None
        and today > trade["pending_exit_date"]
    ):
        if open_price is None:
            logging.warning(
                "股票 %s 缺少出場日開盤價，保留待出場狀態。",
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
    # 1.4 有待進場訊號：下一交易日開盤進場
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
                "股票 %s 缺少進場日開盤價，保留待進場訊號。",
                stock_id
            )
            return False

        if market["high"] is None or market["low"] is None:
            logging.warning(
                "股票 %s 缺少進場日高低價，暫不建立持倉。",
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
            trade["pending_exit_reason"] = "收盤跌破布林中軌"

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
    # 1.5 已持倉：更新當日高低價及 MFE / MAE
    # --------------------------------------------------------

    trade = item["active_trade"]

    if trade is not None:
        if market["high"] is None or market["low"] is None:
            logging.warning(
                "股票 %s 缺少當日高低價，暫不更新持倉。",
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

        # 收盤跌破布林中軌，建立待出場訊號。
        if (
            market["stop_condition"]
            and trade["pending_exit_date"] is None
        ):
            trade["pending_exit_date"] = today
            trade["pending_exit_reason"] = "收盤跌破布林中軌"

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
                "股票 %s 出現停損訊號：%s，預計下一交易日開盤出場。",
                stock_id,
                today
            )

        item["last_processed_date"] = today
        item["updated_at"] = get_taipei_now().isoformat()

        return True

    # --------------------------------------------------------
    # 1.6 無持倉：處理買進及觀察訊號
    # --------------------------------------------------------

    process_idle_signal(
        item=item,
        stock_id=stock_id,
        market=market,
        today=today
    )

    item["last_processed_date"] = today
    item["updated_at"] = get_taipei_now().isoformat()

    return True
