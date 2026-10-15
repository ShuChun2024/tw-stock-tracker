import datetime

from conference_parser import (
    API_DETAIL_URL,
    API_LIST_URL,
    BASE_DIR,
    FILES_DIR,
    MAX_EVENTS,
    OUTPUT_JSON,
    OUTPUT_TXT,
    REQUEST_TIMEOUT,
    calculate_session_quality,
    clean_text,
    deduplicate_sessions,
    download_attachment,
    filter_conference_events,
    find_attachment_links,
    get_detail_title,
    get_event_id,
    get_event_list,
    get_event_title,
    is_listed_company_conference,
    log,
    parse_table_sessions,
    print_all_events,
    print_selected_events,
    save_json,
    session,
)
from docx_parser import (
    docx_to_tables_and_text,
    parse_docx_text_sessions,
    print_docx_tables,
)
from pdf_parser import (
    parse_pdf_schedule_sessions,
    pdf_to_tables_and_text,
)


# ============================================================
# v13 處理單一活動
# ============================================================

def process_event(event, event_index):
    title = get_event_title(event)
    event_id = get_event_id(event)

    result = {
        "event_index": event_index,
        "event_title": title,
        "event_id": event_id,
        "detail_http_status": None,
        "attachments": [],
        "attachment_formats": [],
        "downloaded_files": [],
        "page_count": None,
        "paragraph_count": 0,
        "table_count": 0,
        "session_count": 0,
        "sessions": [],
        "status": "failed",
        "errors": [],
    }

    log("")
    log("=" * 72)
    log(f"處理活動 {event_index}")
    log("=" * 72)
    log(f"活動：{title}")
    log(f"zhId：{event_id}")

    if not event_id:
        result["errors"].append("活動缺少 zhId")
        return result

    try:
        detail_response = session.get(
            API_DETAIL_URL,
            params={
                "id": event_id,
                "response": "json",
            },
            timeout=REQUEST_TIMEOUT,
        )

        result["detail_http_status"] = (
            detail_response.status_code
        )

        log(
            "詳細資料 HTTP："
            f"{detail_response.status_code}"
        )

        detail_response.raise_for_status()

        try:
            detail_payload = detail_response.json()
        except ValueError as exc:
            raise RuntimeError(
                "詳細資料不是有效 JSON"
            ) from exc

        detail_title = get_detail_title(detail_payload)

        if detail_title:
            result["detail_title"] = detail_title
            log(f"詳細資料標題：{detail_title}")

        attachments = find_attachment_links(detail_payload)

        if not attachments:
            raise RuntimeError(
                "詳細資料中找不到 DOCX 或 PDF 連結。"
            )

        result["attachments"] = attachments
        result["attachment_formats"] = [
            item["format"] for item in attachments
        ]

        log("")
        log(f"找到附件：{len(attachments)}")

        for attachment in attachments:
            log(
                f"  {attachment['format'].upper()} "
                f"{attachment['url']}"
            )

        combined_sessions = []

        for attachment_index, attachment in enumerate(
            attachments,
            start=1,
        ):
            try:
                file_path = download_attachment(
                    attachment,
                    event_index,
                    attachment_index,
                )

                result["downloaded_files"].append({
                    "path": str(
                        file_path.relative_to(BASE_DIR)
                    ),
                    "format": attachment["format"],
                    "url": attachment["url"],
                })

                file_format = attachment["format"]

                # ------------------------------------------------
                # DOCX 解析
                # ------------------------------------------------

                if file_format == "docx":
                    paragraphs, tables = (
                        docx_to_tables_and_text(file_path)
                    )

                    result["paragraph_count"] += len(paragraphs)
                    result["table_count"] += len(tables)

                    log("")
                    log(f"DOCX 段落：{len(paragraphs)}")
                    log(f"DOCX 表格：{len(tables)}")

                    print_docx_tables(tables)

                    table_sessions = parse_table_sessions(
                        tables,
                        title,
                        event_id,
                        file_format,
                    )

                    if not table_sessions:
                        table_sessions = parse_docx_text_sessions(
                            paragraphs,
                            title,
                            event_id,
                            file_format,
                        )

                    combined_sessions.extend(table_sessions)

                    log(
                        f"DOCX 辨識場次："
                        f"{len(table_sessions)}"
                    )

                # ------------------------------------------------
                # PDF 解析
                # ------------------------------------------------

                elif file_format == "pdf":
                    page_count, text_blocks, tables = (
                        pdf_to_tables_and_text(file_path)
                    )

                    result["page_count"] = (
                        result["page_count"] or 0
                    ) + page_count

                    result["table_count"] += len(tables)

                    log("")
                    log(f"PDF 頁數：{page_count}")
                    log(f"PDF 表格：{len(tables)}")

                    table_sessions = parse_table_sessions(
                        tables,
                        title,
                        event_id,
                        file_format,
                    )

                    if not table_sessions:
                        table_sessions = parse_pdf_schedule_sessions(
                            text_blocks,
                            title,
                            event_id,
                        )

                    combined_sessions.extend(table_sessions)

                    log(
                        f"PDF 辨識場次："
                        f"{len(table_sessions)}"
                    )

                    if not any(
                        block.strip()
                        for block in text_blocks
                    ):
                        result["errors"].append(
                            "PDF 未擷取到可搜尋文字；"
                            "可能是掃描影像。"
                        )

            except Exception as exc:
                error = (
                    "附件處理失敗（"
                    f"{attachment.get('format', 'unknown')}"
                    "）："
                    f"{type(exc).__name__}: {exc}"
                )

                result["errors"].append(error)
                log("ERROR：" + error)

        result["sessions"] = deduplicate_sessions(
            combined_sessions
        )
        result["session_count"] = len(result["sessions"])

        if (
            result["downloaded_files"]
            and result["session_count"] > 0
        ):
            result["status"] = "success"

        elif result["downloaded_files"]:
            result["status"] = "downloaded_but_no_sessions"
            result["errors"].append(
                "附件下載成功，但尚未辨識到公司場次。"
            )

        else:
            result["status"] = "failed"

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        result["errors"].append(error)
        log("ERROR：" + error)

    log("")
    log(f"活動狀態：{result['status']}")
    log(f"辨識公司場次：{result['session_count']}")

    return result


# ============================================================
# v13 TXT 報告
# ============================================================

def write_text_report(report):
    lines = [
        "證交所法人說明會測試報告（第十三版）",
        f"產生時間：{report['generated_at']}",
        "",
        f"活動列表總筆數：{report['total_event_count']}",
        f"上市公司法人說明會活動筆數：{report['conference_event_count']}",
        f"實際處理活動筆數：{report['processed_event_count']}",
        f"成功處理活動：{report['success_event_count']}",
        f"成功下載附件活動：{report['downloaded_event_count']}",
        f"成功下載 DOCX：{report['docx_event_count']}",
        f"成功下載 PDF：{report['pdf_event_count']}",
        f"辨識法人說明會表格：{report['conference_table_count']}",
        f"辨識公司場次總數：{report['total_session_count']}",
        f"處理錯誤活動：{report['error_event_count']}",
        "",
        "===== 場次資料品質 =====",
        f"完整場次：{report['session_quality']['complete_sessions']}",
        "公司名稱缺漏："
        f"{report['session_quality']['missing_company_name_sessions']}",
        f"取消場次：{report['session_quality']['cancelled_sessions']}",
        "需要檢查的場次："
        f"{report['session_quality']['sessions_needing_review']}",
        "",
        "=" * 72,
        "===== ALL EVENTS =====",
        "=" * 72,
        "",
    ]

    for index, event in enumerate(
        report["all_events"],
        start=1,
    ):
        title = get_event_title(event)
        event_id = get_event_id(event)

        if is_listed_company_conference(title):
            category = "上市公司法人說明會"
        elif "創新板" in title:
            category = "創新板公司法人說明會"
        else:
            category = "其他"

        lines.append(
            f"[{index}] {category} | "
            f"{title} | zhId={event_id}"
        )

    lines.extend([
        "",
        "=" * 72,
        "===== SELECTED EVENTS =====",
        "=" * 72,
    ])

    for item in report["events"]:
        lines.extend([
            "",
            f"活動：{item['event_title']}",
            f"zhId：{item['event_id']}",
            f"狀態：{item['status']}",
            "附件格式："
            + ", ".join(item.get("attachment_formats", [])),
            f"辨識場次：{item['session_count']}",
        ])

        for session_item in item["sessions"]:
            name = (
                session_item.get("company_name")
                or "【公司名稱缺漏】"
            )

            cancelled_mark = (
                "【取消】"
                if session_item.get("cancelled")
                else ""
            )

            reconstructed_mark = (
                "【跨行重組】"
                if session_item.get("name_reconstructed")
                else ""
            )

            lines.append(
                "  "
                f"{session_item.get('sequence_no', '')} "
                f"{session_item['stock_code']} "
                f"{name} "
                f"{session_item.get('date', '')} "
                f"{session_item.get('time', '')} "
                f"{session_item.get('venue', '')} "
                f"{cancelled_mark} "
                f"{reconstructed_mark} "
                f"[{session_item['source_format'].upper()}] "
                f"[{session_item.get('parse_method', '')}]"
            )

            if session_item.get("company_name_missing"):
                lines.append(
                    "    待確認原始資料："
                    f"{session_item.get('raw_text', '')}"
                )

            fragments = session_item.get(
                "name_source_fragments", []
            )

            if fragments:
                lines.append(
                    "    公司名稱重組來源："
                    + " + ".join(fragments)
                )

        for error in item["errors"]:
            lines.append(f"  錯誤／警告：{error}")

    lines.extend([
        "",
        "=" * 72,
        "===== ALL SESSIONS =====",
        "=" * 72,
    ])

    for item in report["sessions"]:
        name = (
            item.get("company_name")
            or "【公司名稱缺漏】"
        )

        cancelled_mark = (
            "【取消】" if item.get("cancelled") else ""
        )

        reconstructed_mark = (
            "【跨行重組】"
            if item.get("name_reconstructed")
            else ""
        )

        lines.append(
            f"{item.get('sequence_no', '')} "
            f"{item['stock_code']} "
            f"{name} | "
            f"{item.get('date', '')} | "
            f"{item.get('time', '')} | "
            f"{item.get('venue', '')} | "
            f"{item.get('notes', '')} "
            f"{cancelled_mark} "
            f"{reconstructed_mark} | "
            f"{item['event_title']} | "
            f"{item['source_format'].upper()}"
        )

    lines.extend([
        "",
        "=" * 72,
        "===== SUMMARY =====",
        "=" * 72,
        f"活動列表總筆數：{report['total_event_count']}",
        f"上市公司法人說明會活動筆數：{report['conference_event_count']}",
        f"實際處理活動筆數：{report['processed_event_count']}",
        f"成功處理活動：{report['success_event_count']}",
        f"成功下載附件活動：{report['downloaded_event_count']}",
        f"成功下載 DOCX：{report['docx_event_count']}",
        f"成功下載 PDF：{report['pdf_event_count']}",
        f"辨識法人說明會表格：{report['conference_table_count']}",
        f"辨識公司場次總數：{report['total_session_count']}",
        f"處理錯誤活動：{report['error_event_count']}",
        f"完整場次：{report['session_quality']['complete_sessions']}",
        "公司名稱缺漏："
        f"{report['session_quality']['missing_company_name_sessions']}",
        f"取消場次：{report['session_quality']['cancelled_sessions']}",
        "需要檢查的場次："
        f"{report['session_quality']['sessions_needing_review']}",
    ])

    OUTPUT_TXT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


# ============================================================
# v13 主程式
# ============================================================

def main():
    log("")
    log("=" * 72)
    log("證交所法人說明會測試：第十三版")
    log("支援 DOCX / PDF")
    log("排除創新板公司法人說明會")
    log("PDF 採跨行公司名稱重組")
    log("=" * 72)

    report = {
        "version": "13.0",
        "generated_at": (
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        ),
        "list_api_url": API_LIST_URL,
        "total_event_count": 0,
        "conference_event_count": 0,
        "processed_event_count": 0,
        "success_event_count": 0,
        "downloaded_event_count": 0,
        "docx_event_count": 0,
        "pdf_event_count": 0,
        "conference_table_count": 0,
        "total_session_count": 0,
        "error_event_count": 0,
        "session_quality": {
            "total_sessions": 0,
            "complete_sessions": 0,
            "missing_company_name_sessions": 0,
            "cancelled_sessions": 0,
            "sessions_needing_review": 0,
        },
        "all_events": [],
        "events": [],
        "sessions": [],
    }

    try:
        # [1] 取得活動列表
        events = get_event_list()
        report["total_event_count"] = len(events)
        report["all_events"] = events

        log("")
        log(f"回傳活動筆數：{len(events)}")
        print_all_events(events)

        # [2] 篩選上市公司法人說明會
        conference_events = filter_conference_events(events)
        report["conference_event_count"] = len(conference_events)

        log("")
        log(
            "上市公司法人說明會活動筆數："
            f"{len(conference_events)}"
        )
        print_selected_events(conference_events)

        conference_events = conference_events[:MAX_EVENTS]

        log("")
        log(f"本次最多處理：{MAX_EVENTS} 個活動")

        # [3] 處理活動
        log("")
        log("=" * 72)
        log("[3] 查詢詳細資料、下載 DOCX/PDF 並解析")
        log("=" * 72)

        for index, event in enumerate(conference_events, start=1):
            result = process_event(event, index)
            report["events"].append(result)

        report["processed_event_count"] = len(report["events"])

        report["success_event_count"] = sum(
            1 for item in report["events"]
            if item["status"] == "success"
        )

        report["downloaded_event_count"] = sum(
            1 for item in report["events"]
            if item["downloaded_files"]
        )

        report["docx_event_count"] = sum(
            1 for item in report["events"]
            if any(
                attachment["format"] == "docx"
                for attachment in item["downloaded_files"]
            )
        )

        report["pdf_event_count"] = sum(
            1 for item in report["events"]
            if any(
                attachment["format"] == "pdf"
                for attachment in item["downloaded_files"]
            )
        )

        # 合併所有場次
        for item in report["events"]:
            report["sessions"].extend(item["sessions"])

        report["sessions"] = deduplicate_sessions(
            report["sessions"]
        )
        report["total_session_count"] = len(report["sessions"])

        # 表格活動統計
        report["conference_table_count"] = sum(
            1 for item in report["events"]
            if item["table_count"] > 0
        )

        # 錯誤活動統計
        report["error_event_count"] = sum(
            1 for item in report["events"]
            if item["status"] != "success"
        )

        # 資料品質統計
        report["session_quality"] = calculate_session_quality(
            report["sessions"]
        )

    except Exception as exc:
        report["fatal_error"] = (
            f"{type(exc).__name__}: {exc}"
        )
        log("")
        log("程式發生重大錯誤：" + report["fatal_error"])

    finally:
        # [4] 儲存 JSON 與 TXT
        log("")
        log("=" * 72)
        log("[4] 產生 JSON 與文字報告")
        log("=" * 72)

        save_json(report)
        write_text_report(report)

        # [5] Summary
        log("")
        log("=" * 72)
        log("[5] 第十三版測試摘要")
        log("=" * 72)

        for key, label in (
            ("total_event_count", "活動列表總筆數"),
            ("conference_event_count", "上市公司法人說明會活動筆數"),
            ("processed_event_count", "實際處理活動筆數"),
            ("success_event_count", "成功處理活動"),
            ("downloaded_event_count", "成功下載附件活動"),
            ("docx_event_count", "成功下載 DOCX"),
            ("pdf_event_count", "成功下載 PDF"),
            ("conference_table_count", "辨識法人說明會表格"),
            ("total_session_count", "辨識公司場次總數"),
            ("error_event_count", "處理錯誤活動"),
        ):
            log(f"{label}：{report[key]}")

        log("")
        log("場次資料品質：")

        for key, label in (
            ("complete_sessions", "完整場次"),
            ("missing_company_name_sessions", "公司名稱缺漏"),
            ("cancelled_sessions", "取消場次"),
            ("sessions_needing_review", "需要檢查的場次"),
        ):
            log(
                f"{label}："
                f"{report['session_quality'][key]}"
            )

        log("")
        log("輸出檔案：")
        log(f"- {OUTPUT_JSON.name}")
        log(f"- {OUTPUT_TXT.name}")
        log(f"- {FILES_DIR.name}/")
        log("")
        log("第十三版測試完成。")


if __name__ == "__main__":
    main()
