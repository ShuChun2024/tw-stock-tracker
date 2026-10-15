import re

import pdfplumber

from conference_parser import (
    CODE_PATTERN,
    DATE_PATTERN,
    TIME_PATTERN,
    clean_text,
    is_cancelled,
    log,
    make_session,
)


# ============================================================
# PDF 文字與表格擷取
# ============================================================

def pdf_to_tables_and_text(file_path):
    all_tables = []
    all_text = []

    with pdfplumber.open(str(file_path)) as pdf:
        page_count = len(pdf.pages)

        for page_number, page in enumerate(pdf.pages, start=1):
            log("")
            log("-" * 72)
            log(f"PDF 第 {page_number} 頁")
            log("-" * 72)

            text = page.extract_text() or ""

            if text.strip():
                text_block = (
                    f"[PDF 第 {page_number} 頁]\n"
                    f"{text.strip()}"
                )
                all_text.append(text_block)
                log("")
                log("PDF TEXT：")
                log(text.strip())

            try:
                page_tables = page.extract_tables() or []
            except Exception as exc:
                log(
                    "警告：PDF 第 "
                    f"{page_number} 頁表格擷取失敗：{exc}"
                )
                page_tables = []

            log("")
            log(
                f"PDF 第 {page_number} 頁表格數："
                f"{len(page_tables)}"
            )

            for table_index, table in enumerate(page_tables, start=1):
                rows = []

                log("")
                log("=" * 72)
                log(
                    f"===== PDF TABLE {table_index} "
                    f"(PAGE {page_number}) ====="
                )
                log("=" * 72)

                for row_index, row in enumerate(table, start=1):
                    cells = [
                        clean_text(cell)
                        for cell in (row or [])
                    ]

                    if any(cells):
                        rows.append(cells)
                        log(
                            f"[R{row_index}] "
                            + " | ".join(cells)
                        )

                if rows:
                    all_tables.append({
                        "page": page_number,
                        "table_index": table_index,
                        "rows": rows,
                    })

    return page_count, all_text, all_tables


# ============================================================
# PDF 公司名稱片段判斷
# ============================================================

PDF_NAME_IGNORE_WORDS = (
    "公司名稱",
    "公司代碼",
    "股票代碼",
    "股票代號",
    "證券代號",
    "法人說明會",
    "上市公司",
    "創新板",
    "項次",
    "序號",
    "編號",
    "日期",
    "時間",
    "時段",
    "場地",
    "地點",
    "備註",
    "說明",
    "報名",
    "取消",
    "停辦",
    "法人",
)


def is_pdf_name_fragment(line):
    """
    判斷某一行是否可能是被 PDF 拆出的公司名稱片段。
    這不是判定它一定是公司名稱，而是判斷是否值得納入候選。
    """
    line = clean_text(line)

    if not line:
        return False

    if line.startswith("[PDF 第"):
        return False

    if any(keyword in line for keyword in PDF_NAME_IGNORE_WORDS):
        return False

    if DATE_PATTERN.search(line):
        return False

    if TIME_PATTERN.search(line):
        return False

    if re.fullmatch(r"[\d\s.,，:：/\\|｜-]+", line):
        return False

    if re.fullmatch(r"\d{1,3}", line):
        return False

    if not re.search(r"[A-Za-z\u3400-\u9fff]", line):
        return False

    return True


def clean_pdf_name_fragment(line):
    """
    清理 PDF 公司名稱片段，只移除明顯不屬於名稱的空白。
    """
    line = clean_text(line)

    if not line:
        return ""

    line = re.sub(
        r"^\[PDF 第\s*\d+\s*頁\]\s*",
        "",
        line,
    )

    return clean_text(line)


# ============================================================
# PDF 核心資料列辨識
# ============================================================

def extract_core_pdf_row(line):
    """
    必須在同一行找到股票代號、日期及時間，
    才認定為一筆場次核心列。
    """
    line = clean_text(line)

    if not line:
        return None

    code_match = CODE_PATTERN.search(line)
    date_match = DATE_PATTERN.search(line)
    time_match = TIME_PATTERN.search(line)

    if not code_match or not date_match or not time_match:
        return None

    if date_match.start() < code_match.end():
        return None

    if time_match.start() < date_match.end():
        return None

    return {
        "line": line,
        "code_match": code_match,
        "date_match": date_match,
        "time_match": time_match,
    }


def parse_pdf_core_row(core):
    """
    解析核心資料行本身。

    支援：
      27 3027 盛達 12 月 24 日 ...
      1456 1 怡華 9 月 3 日 ...
      6550 9 12 月 11 日 ...
    """
    line = core["line"]
    code_match = core["code_match"]
    date_match = core["date_match"]
    time_match = core["time_match"]

    stock_code = code_match.group(1)

    before_date = line[
        code_match.end():date_match.start()
    ].strip()

    before_code = line[:code_match.start()].strip()

    sequence_no = ""
    company_name = ""

    if (
        before_code
        and re.fullmatch(r"\d{1,3}", before_code)
    ):
        sequence_no = before_code

    after_code = before_date

    if after_code:
        tokens = after_code.split()

        if tokens and re.fullmatch(r"\d{1,3}", tokens[0]):
            if not sequence_no:
                sequence_no = tokens[0]

            company_name = " ".join(tokens[1:])
        else:
            company_name = after_code

    company_name = clean_pdf_name_fragment(company_name)

    if re.fullmatch(r"\d{1,3}", company_name):
        company_name = ""

    tail = line[time_match.end():].strip()
    cancelled = is_cancelled(line)

    notes = ""
    venue = tail

    if cancelled:
        notes = "取消"
        venue = re.sub(r"取消|停辦", "", venue)
        venue = clean_text(venue)

    return {
        "stock_code": stock_code,
        "sequence_no": sequence_no,
        "company_name": company_name,
        "date": date_match.group(0),
        "time": time_match.group(0),
        "venue": venue,
        "notes": notes,
        "cancelled": cancelled,
    }


# ============================================================
# PDF 鄰近文字重組
# ============================================================

def build_pdf_name_from_neighbors(
    lines,
    core_index,
    parsed_core,
):
    """
    從核心列前後鄰近文字尋找公司名稱。

    例如：
        全宇生技-
        33 4148 12 月 29 日 ...
        KY

    6550 等核心列沒有公司名稱的情況，也會嘗試搜尋鄰近文字。
    """
    existing_name = clean_text(
        parsed_core.get("company_name", "")
    )

    if existing_name:
        return existing_name, []

    fragments_before = []
    fragments_after = []

    SEARCH_DISTANCE = 3

    # 向前搜尋
    for distance in range(1, SEARCH_DISTANCE + 1):
        index = core_index - distance

        if index < 0:
            break

        candidate = clean_text(lines[index])

        if not candidate:
            continue

        if candidate.startswith("[PDF 第"):
            break

        if not is_pdf_name_fragment(candidate):
            continue

        if re.fullmatch(r"\d{1,6}", candidate):
            continue

        code_matches = CODE_PATTERN.findall(candidate)

        if code_matches:
            continue

        fragments_before.append(candidate)
        break

    # 向後搜尋
    for distance in range(1, SEARCH_DISTANCE + 1):
        index = core_index + distance

        if index >= len(lines):
            break

        candidate = clean_text(lines[index])

        if not candidate:
            continue

        if candidate.startswith("[PDF 第"):
            break

        if not is_pdf_name_fragment(candidate):
            continue

        if re.fullmatch(r"\d{1,6}", candidate):
            continue

        code_matches = CODE_PATTERN.findall(candidate)

        if code_matches:
            continue

        fragments_after.append(candidate)
        break

    fragments = []

    for fragment in reversed(fragments_before):
        fragments.append(fragment)

    if existing_name:
        fragments.append(existing_name)

    for fragment in fragments_after:
        fragments.append(fragment)

    fragments = [
        clean_pdf_name_fragment(fragment)
        for fragment in fragments
        if clean_pdf_name_fragment(fragment)
    ]

    if not fragments:
        return "", []

    company_name = ""

    for fragment in fragments:
        if not company_name:
            company_name = fragment
        else:
            # 保留原 v12 行為：名稱片段直接串接，
            # 不額外插入空白。
            if (
                company_name.endswith("-")
                or fragment.startswith("-")
            ):
                company_name += fragment
            else:
                company_name += fragment

    company_name = clean_text(company_name)

    if re.fullmatch(r"\d{1,3}", company_name):
        company_name = ""

    return company_name, fragments


# ============================================================
# PDF 場次跨行重組
# ============================================================

def parse_pdf_schedule_sessions(
    text_blocks,
    event_title,
    event_id,
):
    """
    v13 PDF 解析器：
    股票代號 + 日期 + 時間 -> 核心場次 -> 鄰近文字重組名稱。
    """
    sessions = []

    for block in text_blocks:
        raw_lines = block.splitlines()

        lines = [
            clean_text(line)
            for line in raw_lines
        ]

        lines = [line for line in lines if line]

        if not lines:
            continue

        used_core_indices = set()

        for index, line in enumerate(lines):
            core = extract_core_pdf_row(line)

            if not core:
                continue

            if index in used_core_indices:
                continue

            used_core_indices.add(index)
            parsed_core = parse_pdf_core_row(core)

            company_name = clean_text(
                parsed_core.get("company_name", "")
            )
            fragments = []

            if not company_name:
                company_name, fragments = (
                    build_pdf_name_from_neighbors(
                        lines,
                        index,
                        parsed_core,
                    )
                )

            raw_parts = [line]

            for fragment in fragments:
                if fragment not in raw_parts:
                    raw_parts.append(fragment)

            raw_text = " | ".join(raw_parts)

            session_item = make_session(
                stock_code=parsed_core["stock_code"],
                company_name=company_name,
                event_title=event_title,
                event_id=event_id,
                file_format="pdf",
                parse_method="text_reconstructed",
                raw_text=raw_text,
                sequence_no=parsed_core["sequence_no"],
                session_date=parsed_core["date"],
                session_time=parsed_core["time"],
                venue=parsed_core["venue"],
                notes=parsed_core["notes"],
            )

            session_item["name_reconstructed"] = bool(fragments)
            session_item["name_source_fragments"] = fragments

            sessions.append(session_item)

    return sessions


# ============================================================
# PDF 單行解析（相容舊版）
# ============================================================

def parse_pdf_schedule_line(line, event_title, event_id):
    """
    保留單行解析函式供舊版相容使用。
    正式 PDF 備援使用 parse_pdf_schedule_sessions()。
    """
    line = clean_text(line)

    if not line:
        return None

    core = extract_core_pdf_row(line)

    if not core:
        return None

    parsed = parse_pdf_core_row(core)

    return make_session(
        stock_code=parsed["stock_code"],
        company_name=parsed["company_name"],
        event_title=event_title,
        event_id=event_id,
        file_format="pdf",
        parse_method="text_fallback",
        raw_text=line,
        sequence_no=parsed["sequence_no"],
        session_date=parsed["date"],
        session_time=parsed["time"],
        venue=parsed["venue"],
        notes=parsed["notes"],
    )
