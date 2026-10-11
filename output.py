import json
import logging

from config import OUTPUT_FILE
from utils import to_json_safe


# ============================================================
# 1. 儲存分析結果
# ============================================================

def save_analysis(results, now):
    """
    儲存股票分析結果至 analysis.json。

    綜合評分：
    - 基本面（營收）：40 分
    - 籌碼面（三大法人）：20 分
    - 技術面：40 分

    外資持股趨勢分數為獨立參考指標，
    不納入綜合評分的 100 分計算。
    """

    # --------------------------------------------------------
    # 1. 統計股票數量
    # --------------------------------------------------------

    stock_count = len(results)

    complete_count = sum(
        1
        for stock in results
        if stock.get("data_quality", {}).get("complete", False)
    )

    technical_count = sum(
        1
        for stock in results
        if stock.get("technical", {}).get("data_available", False)
    )

    # --------------------------------------------------------
    # 2. 建立輸出資料
    # --------------------------------------------------------

    payload = {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "stock_count": stock_count,
        "complete_count": complete_count,
        "technical_count": technical_count,

        # 綜合評分的實際計分配置
        "score_description": {
            "revenue": 40,
            "chip": 20,
            "technical": 40,
            "total": 100
        },

        "stocks": results
    }

    # --------------------------------------------------------
    # 3. 轉換成 JSON 安全格式
    # --------------------------------------------------------

    safe_payload = to_json_safe(payload)

    # --------------------------------------------------------
    # 4. 寫入 analysis.json
    # --------------------------------------------------------

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            safe_payload,
            file,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        )

    logging.info(
        "分析結果已輸出：%s；股票數量：%s；完整資料：%s；技術資料：%s",
        OUTPUT_FILE,
        stock_count,
        complete_count,
        technical_count
    )

    return safe_payload
