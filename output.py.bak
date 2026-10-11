import json
import logging

from config import OUTPUT_FILE
from utils import to_json_safe


# ============================================================
# 1. 儲存分析結果至 analysis.json
# ============================================================

def save_analysis(results, now):
    """
    將所有股票分析結果輸出為 JSON。

    保留網頁儀表板需要的主要欄位：
    - update_time
    - stock_count
    - complete_count
    - technical_count
    - score_description
    - stocks
    """

    # --------------------------------------------------------
    # 1.1 統計分析結果
    # --------------------------------------------------------

    complete_count = sum(
        1
        for item in results
        if item.get(
            "data_quality", {}
        ).get("complete", False)
    )

    technical_count = sum(
        1
        for item in results
        if item.get(
            "technical", {}
        ).get("data_available", False)
    )

    # --------------------------------------------------------
    # 1.2 建立 JSON 輸出結構
    # --------------------------------------------------------

    payload = {
        "update_time": now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "stock_count": len(results),

        "complete_count": complete_count,

        "technical_count": technical_count,

        "score_description": {
            "revenue": 40,
            "foreign_holding": 20,
            "technical": 40,
            "total": 100
        },

        "stocks": results
    }

    # --------------------------------------------------------
    # 1.3 安全轉換與寫入檔案
    # --------------------------------------------------------

    safe_payload = to_json_safe(payload)

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            safe_payload,
            file,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        )

    # --------------------------------------------------------
    # 1.4 記錄輸出結果
    # --------------------------------------------------------

    logging.info(
        "分析股票數量：%s",
        len(results)
    )

    logging.info(
        "完整資料股票數量：%s",
        complete_count
    )

    logging.info(
        "技術分析成功數量：%s",
        technical_count
    )

    logging.info(
        "已輸出分析結果：%s",
        OUTPUT_FILE
    )

    return payload
