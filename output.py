import json
import logging
import math
import os

from config import OUTPUT_FILE
from utils import to_json_safe


def is_valid_score(value):
    """判斷綜合分數是否為有效數值。"""
    if isinstance(value, bool):
        return False

    try:
        score = float(value)
    except (TypeError, ValueError):
        return False

    return math.isfinite(score) and 0 <= score <= 100


def save_analysis(results, now):
    """安全輸出 analysis.json，保留舊欄位並新增統計資訊。"""

    stock_count = len(results)

    # 所有分析資料完整：維持原本 data_quality.complete 的定義
    data_complete_count = sum(
        1
        for item in results
        if isinstance(item.get("data_quality"), dict)
        and item["data_quality"].get("complete") is True
    )

    # 綜合評分完整：總分存在且為有效的 0～100 數值
    score_complete_count = sum(
        1
        for item in results
        if is_valid_score(item.get("score"))
    )

    # 技術面模組有成功取得資料
    technical_count = sum(
        1
        for item in results
        if isinstance(item.get("technical"), dict)
        and item["technical"].get("data_available") is True
    )

    payload = {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "stock_count": stock_count,

        # 保留舊欄位及原有意義
        "complete_count": data_complete_count,

        # 新增欄位，供後續監控及前端使用
        "score_complete_count": score_complete_count,
        "data_complete_count": data_complete_count,

        "technical_count": technical_count,

        "score_description": {
            "revenue": 40,
            "chip": 20,
            "technical": 40,
            "total": 100
        },

        "stocks": results
    }

    safe_payload = to_json_safe(payload)

    output_path = OUTPUT_FILE
    temp_path = output_path.with_name(
        output_path.name + ".tmp"
    )

    try:
        # 先寫入同一目錄的暫存檔
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(
                safe_payload,
                f,
                ensure_ascii=False,
                indent=2,
                allow_nan=False
            )
            f.write("\n")

        # 重新讀取，確認暫存檔是有效 JSON
        with temp_path.open("r", encoding="utf-8") as f:
            verified_payload = json.load(f)

        if not isinstance(verified_payload, dict):
            raise ValueError("analysis.json 根節點必須是 JSON 物件")

        if not isinstance(verified_payload.get("stocks"), list):
            raise ValueError("analysis.json 缺少有效的 stocks 陣列")

        if len(verified_payload["stocks"]) != stock_count:
            raise ValueError("輸出股票數量與分析結果不一致")

        # 驗證成功後才替換正式檔案
        os.replace(temp_path, output_path)

    except Exception:
        logging.exception("安全寫入 analysis.json 失敗")

        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            logging.exception("清理 analysis.json 暫存檔失敗")

        raise

    logging.info(
        "analysis.json 更新完成：股票 %s 檔，"
        "總分可用 %s 檔，資料完整 %s 檔，技術面可用 %s 檔",
        stock_count,
        score_complete_count,
        data_complete_count,
        technical_count
    )

    return safe_payload
