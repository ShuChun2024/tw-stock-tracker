import datetime
import json
import logging
import math

import pandas as pd

from config import CONFIG_FILE, DEFAULT_STOCKS, LOG_FILE


# ============================================================
# 1. 設定日誌記錄
# ============================================================

def setup_logging():
    """
    同時將執行訊息寫入日誌檔及主控台。
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 避免重複新增日誌處理器
    if logger.handlers:
        return

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )

    # 寫入日誌檔
    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # 顯示在主控台
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


# ============================================================
# 2. 標準化股票代碼
# ============================================================

def normalize_stock_code(stock):
    """
    將股票代碼統一轉成字串。

    支援：
    - "2330"
    - 2330
    - {"stock_id": "2330"}
    - {"stock_code": "2330"}
    - {"code": "2330"}
    """
    if stock is None:
        return None

    if isinstance(stock, dict):
        stock = (
            stock.get("stock_id")
            or stock.get("stock_code")
            or stock.get("code")
        )

    if stock is None:
        return None

    text = str(stock).strip()

    return text or None


# ============================================================
# 3. 讀取 config.json
# ============================================================

def load_config():
    """
    讀取設定檔。

    若設定檔不存在，使用預設股票清單。
    若設定檔格式錯誤，則拋出錯誤，避免靜默使用錯誤設定。
    """
    if not CONFIG_FILE.exists():
        logging.warning(
            "找不到 config.json，使用預設股票清單。"
        )

        return {
            "stocks": DEFAULT_STOCKS,
            "settings": {}
        }

    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError(
            "config.json 最外層必須是 JSON 物件。"
        )

    raw_stocks = config.get("stocks", DEFAULT_STOCKS)

    if not isinstance(raw_stocks, list):
        raise ValueError(
            "config.json 的 stocks 必須是陣列。"
        )

    stocks = []

    for item in raw_stocks:
        code = normalize_stock_code(item)

        if code and code not in stocks:
            stocks.append(code)

    if not stocks:
        raise ValueError(
            "config.json 沒有有效的股票代碼。"
        )

    config["stocks"] = stocks

    if not isinstance(config.get("settings"), dict):
        config["settings"] = {}

    return config


# ============================================================
# 4. 將資料轉換成 JSON 可處理的格式
# ============================================================

def to_json_safe(value):
    """
    遞迴處理資料，將日期、Pandas 數值及缺失值
    轉換成 JSON 可以安全輸出的格式。
    """
    # 字典
    if isinstance(value, dict):
        return {
            str(key): to_json_safe(item)
            for key, item in value.items()
        }

    # 清單或元組
    if isinstance(value, (list, tuple)):
        return [
            to_json_safe(item)
            for item in value
        ]

    # 空值
    if value is None:
        return None

    # 日期與時間
    if isinstance(
        value,
        (datetime.date, datetime.datetime)
    ):
        return value.isoformat()

    # NumPy / Pandas 標量
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass

    # 排除 NaN、正無限大、負無限大
    if isinstance(value, float):
        if not math.isfinite(value):
            return None

    # 排除 Pandas 的缺失值
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    # JSON 原生資料型別
    if isinstance(value, (str, int, float, bool)):
        return value

    # 其他無法直接序列化的物件
    return str(value)


# ============================================================
# 5. 數值安全轉換
# ============================================================

def number_or_none(value):
    """
    將輸入值轉換成有限的浮點數。

    無法轉換、缺失或非有限數值，一律回傳 None。
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None

        number = float(value)

        if math.isfinite(number):
            return number

        return None

    except (TypeError, ValueError):
        return None
