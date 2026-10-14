import re

import pdfplumber
from docx import Document


# ============================================================
# 共用工具
# ============================================================

def log(message=""):
    print(message, flush=True)


def clean_text(value):
    if value is None:
        return ""

    text = str(value)

    text = (
        text.replace("\u00a0", " ")
        .replace("\u3000", " ")
        .replace("\r", "\n")
        .replace("\t", " ")
    )

    lines = []

    for line in text.splitlines():
        line = re.sub(r"[ ]+", " ", line)
        line = line.strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


def first_nonempty(*values):
    for value in values:
        value = clean_text(value)

        if value:
            return value

    return ""


def parse_date(value):
    value = clean_text(value)

    if not value:
        return ""

    match = re.search(
        r"(?:(\d{4})\s*年\s*)?"
        r"(\d{1,2})\s*月\s*"
        r"(\d{1,2})\s*日",
        value,
    )

    if not match:
        return value

    year = match.group(1)
    month = int(match.group(2))
    day = int(match.group(3))

    if year:
        return f"{year}-{month:02d}-{day:02d}"

    return f"{month:02d}-{day:02d}"


def parse_time(value):
    value = clean_text(value)

    if not value:
        return ""

    match = re.search(
        r"(\d{1,2}:\d{2})"
        r"\s*[~～〜–—-]\s*"
        r"(\d{1,2}:\d{2})",
        value,
    )

    if match:
        return f"{match.group(1)}~{match.group(2)}"

    return value


def is_cancelled(value):
    value = clean_text(value)

    if not value:
        return False

    keywords = (
        "取消",
        "延期",
        "暫停",
        "撤銷",
    )

    return any(keyword in value for keyword in keywords)


def make_session(
    stock_code="",
    sequence_no="",
    company_name="",
    session_date="",
    session_time="",
    venue="",
    notes="",
    event_title="",
    event_id="",
    file_format="",
    raw_text="",
    parse_method="",
):
    stock_code = clean_text(stock_code)
    sequence_no = clean_text(sequence_no)
    company_name = clean_text(company_name)
    session_date = clean_text(session_date)
    session_time = clean_text(session_time)
    venue = clean_text(venue)
    notes = clean_text(notes)
    event_title = clean_text(event_title)
    event_id = clean_text(event_id)
    file_format = clean_text(file_format)
    raw_text = clean_text(raw_text)
    parse_method = clean_text(parse_method)

    cancelled = is_cancelled(
        " ".join(
            [
                company_name,
                session_date,
                session_time,
                venue,
                notes,
                raw_text,
            ]
        )
    )

    return {
        "stock_code": clean_text(stock_code),
        "sequence_no": clean_text(sequence_no),
        "company_name": company_name,
        "company_name_missing": not bool(company_name),
        "date": parse_date(session_date),
        "time": parse_time(session_time),
        "venue": clean_text(venue),
        "notes": notes,
        "status": "cancelled" if cancelled else "scheduled",
        "cancelled": cancelled,
        "event_title": event_title,
        "event_id": event_id,
        "source_format": file_format,
        "raw_text": raw_text,
        "parse_method": parse_method,
    }


# ============================================================
# DOCX
# ============================================================

def docx_to_tables_and_text(content):
    document = Document(content)

    tables = []

    for table in document.tables:
        rows = []

        for row in table.rows:
            cells = []

            for cell in row.cells:
                cells.append(clean_text(cell.text))

            rows.append(cells)

        tables.append(rows)

    text_blocks = []

    paragraphs = []

    for paragraph in document.paragraphs:
        text = clean_text(paragraph.text)

        if text:
            paragraphs.append(text)

    if paragraphs:
        text_blocks.append("\n".join(paragraphs))

    return tables, text_blocks


def print_docx_tables(tables):
    log()
    log("========================================================================")
    log("===== DOCX TABLES =====")
    log("========================================================================")

    for table_index, table in enumerate(tables, start=1):
        log()
        log(f"--- TABLE {table_index} ---")

        for row in table:
            log(" | ".join(row))


# ============================================================
# PDF
# ============================================================

def pdf_to_tables_and_text(content):
    tables = []
    text_blocks = []

    with pdfplumber.open(content) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            page_tables = []

            try:
                page_tables = page.extract_tables()
            except Exception:
                page_tables = []

            for table in page_tables or []:
                rows = []

                for row in table:
                    rows.append(
                        [
                            clean_text(cell)
                            for cell in row
                        ]
                    )

                if rows:
                    tables.append(rows)

            text = page.extract_text() or ""

            text = clean_text(text)

            if text:
                text_blocks.append(
                    f"[PDF 第{page_index}頁]\n{text}"
                )

    return tables, text_blocks


# ============================================================
# Pattern
# ============================================================

CODE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(\d{4,6})"
    r"(?!\d)"
)

DATE_PATTERN = re.compile(
    r"(?:(?:\d{4}\s*年\s*)?"
    r"\d{1,2}\s*月\s*"
    r"\d{1,2}\s*日)"
)

TIME_PATTERN = re.compile(
    r"\d{1,2}:\d{2}"
    r"\s*[~～〜–—-]\s*"
    r"\d{1,2}:\d{2}"
)


# ============================================================
# 表格解析
# ============================================================

def normalize_header(value):
    value = clean_text(value)

    value = value.replace(
        " ",
        "",
    )

    value = value.replace(
        "\n",
        "",
    )

    return value


def find_header_indices(row):
    result = {}

    for index, cell in enumerate(row):
        header = normalize_header(cell)

        if not header:
            continue

        if any(
            keyword in header
            for keyword in (
                "股票代號",
                "證券代號",
                "代號",
                "股票代碼",
                "證券碼",
            )
        ):
            result["stock_code"] = index

        elif any(
            keyword in header
            for keyword in (
                "公司名稱",
                "公司",
                "名稱",
            )
        ):
            result["company_name"] = index

        elif any(
            keyword in header
            for keyword in (
                "日期",
                "召開日期",
            )
        ):
            result["date"] = index

        elif any(
            keyword in header
            for keyword in (
                "時間",
                "召開時間",
            )
        ):
            result["time"] = index

        elif any(
            keyword in header
            for keyword in (
                "地點",
                "地點／方式",
                "地點/方式",
                "會議地點",
            )
        ):
            result["venue"] = index

        elif any(
            keyword in header
            for keyword in (
                "備註",
                "說明",
            )
        ):
            result["notes"] = index

        elif any(
            keyword in header
            for keyword in (
                "序號",
                "編號",
            )
        ):
            result["sequence_no"] = index

    return result


def find_optional_column(headers, keywords):
    for index, header in enumerate(headers):
        normalized = normalize_header(header)

        for keyword in keywords:
            if keyword in normalized:
                return index

    return None


def find_all_header_indices(row):
    result = {}

    for index, cell in enumerate(row):
        header = normalize_header(cell)

        if not header:
            continue

        if any(
            keyword in header
            for keyword in (
                "股票代號",
                "證券代號",
                "代號",
                "股票代碼",
                "證券碼",
            )
        ):
            result.setdefault(
                "stock_code",
                [],
            ).append(index)

        if any(
            keyword in header
            for keyword in (
                "公司名稱",
                "公司",
                "名稱",
            )
        ):
            result.setdefault(
                "company_name",
                [],
            ).append(index)

        if any(
            keyword in header
            for keyword in (
                "日期",
                "召開日期",
            )
        ):
            result.setdefault(
                "date",
                [],
            ).append(index)

        if any(
            keyword in header
            for keyword in (
                "時間",
                "召開時間",
            )
        ):
            result.setdefault(
                "time",
                [],
            ).append(index)

        if any(
            keyword in header
            for keyword in (
                "地點",
                "地點／方式",
                "地點/方式",
                "會議地點",
            )
        ):
            result.setdefault(
                "venue",
                [],
            ).append(index)

        if any(
            keyword in header
            for keyword in (
                "備註",
                "說明",
            )
        ):
            result.setdefault(
                "notes",
                [],
            ).append(index)

        if any(
            keyword in header
            for keyword in (
                "序號",
                "編號",
            )
        ):
            result.setdefault(
                "sequence_no",
                [],
            ).append(index)

    return result


def parse_table_sessions(
    tables,
    event_title,
    event_id,
    file_format,
):
    sessions = []

    for table_index, table in enumerate(
        tables,
        start=1,
    ):
        if not table:
            continue

        header_row_index = None
        header_indices = None

        for row_index, row in enumerate(table[:10]):
            indices = find_header_indices(row)

            if (
                "stock_code" in indices
                or "company_name" in indices
            ):
                header_row_index = row_index
                header_indices = indices
                break

        if header_row_index is None:
            continue

        for row in table[
            header_row_index + 1 :
        ]:
            if not row:
                continue

            def get_value(key):
                index = header_indices.get(key)

                if index is None:
                    return ""

                if index >= len(row):
                    return ""

                return clean_text(row[index])

            stock_code = get_value(
                "stock_code"
            )

            company_name = get_value(
                "company_name"
            )

            session_date = get_value(
                "date"
            )

            session_time = get_value(
                "time"
            )

            venue = get_value(
                "venue"
            )

            notes = get_value(
                "notes"
            )

            sequence_no = get_value(
                "sequence_no"
            )

            raw_text = " | ".join(
                clean_text(cell)
                for cell in row
                if clean_text(cell)
            )

            if not any(
                [
                    stock_code,
                    company_name,
                    session_date,
                    session_time,
                    venue,
                    notes,
                ]
            ):
                continue

            sessions.append(
                make_session(
                    stock_code=stock_code,
                    sequence_no=sequence_no,
                    company_name=company_name,
                    session_date=session_date,
                    session_time=session_time,
                    venue=venue,
                    notes=notes,
                    event_title=event_title,
                    event_id=event_id,
                    file_format=file_format,
                    raw_text=raw_text,
                    parse_method=(
                        f"table_{table_index}"
                    ),
                )
            )

    log(
        f"辨識表格場次：{len(sessions)}"
    )

    return sessions


# ============================================================
# PDF 公司名稱跨行辨識
# ============================================================

PDF_NAME_IGNORE_WORDS = {
    "公司",
    "公司名稱",
    "股票代號",
    "證券代號",
    "代號",
    "日期",
    "時間",
    "地點",
    "備註",
    "說明",
    "法人說明會",
    "上市公司",
    "創新板",
    "取消",
    "延期",
    "暫停",
    "撤銷",
}


def is_pdf_name_fragment(
    text,
    stock_code="",
):
    text = clean_text(text)

    if not text:
        return False

    if text.startswith("[PDF 第"):
        return False

    if stock_code:
        if stock_code in text:
            return False

    if CODE_PATTERN.fullmatch(text):
        return False

    if DATE_PATTERN.fullmatch(text):
        return False

    if TIME_PATTERN.fullmatch(text):
        return False

    if text in PDF_NAME_IGNORE_WORDS:
        return False

    if all(
        char.isdigit() or char in " -~～〜–—"
        for char in text
    ):
        return False

    return True


def clean_pdf_name_fragment(text):
    text = clean_text(text)

    if not text:
        return ""

    text = re.sub(
        r"\s+",
        "",
        text,
    )

    return text


def extract_core_pdf_row(line):
    line = clean_text(line)

    if not line:
        return None

    code_match = CODE_PATTERN.search(line)

    if not code_match:
        return None

    date_match = DATE_PATTERN.search(
        line,
        code_match.end(),
    )

    if not date_match:
        return None

    time_match = TIME_PATTERN.search(
        line,
        date_match.end(),
    )

    if not time_match:
        return None

    return {
        "line": line,
        "code_match": code_match,
        "date_match": date_match,
        "time_match": time_match,
    }


def parse_pdf_core_row(
    line,
    event_title,
    event_id,
    file_format,
):
    core = extract_core_pdf_row(line)

    if core is None:
        return None

    code_match = core["code_match"]
    date_match = core["date_match"]
    time_match = core["time_match"]

    prefix = clean_text(
        line[
            : code_match.start()
        ]
    )

    code = code_match.group(1)

    middle = clean_text(
        line[
            code_match.end() :
            date_match.start()
        ]
    )

    date_text = clean_text(
        date_match.group(0)
    )

    time_text = clean_text(
        time_match.group(0)
    )

    suffix = clean_text(
        line[
            time_match.end() :
        ]
    )

    sequence_no = ""
    company_name = ""

    prefix_parts = prefix.split()

    if prefix_parts:
        if all(
            part.isdigit()
            for part in prefix_parts
        ):
            sequence_no = prefix_parts[-1]
        else:
            sequence_no = prefix_parts[-1]

    middle_parts = middle.split()

    if middle_parts:
        if middle_parts[0].isdigit():
            if not sequence_no:
                sequence_no = middle_parts[0]

            middle_parts = (
                middle_parts[1:]
            )

        if middle_parts:
            company_name = "".join(
                middle_parts
            )

    if (
        sequence_no
        and sequence_no == code
    ):
        sequence_no = ""

    raw_text = line

    session = make_session(
        stock_code=code,
        sequence_no=sequence_no,
        company_name=company_name,
        session_date=date_text,
        session_time=time_text,
        venue=suffix,
        notes="",
        event_title=event_title,
        event_id=event_id,
        file_format=file_format,
        raw_text=raw_text,
        parse_method="pdf_core_row",
    )

    return {
        "session": session,
        "company_name": company_name,
        "stock_code": code,
        "sequence_no": sequence_no,
        "date_text": date_text,
        "time_text": time_text,
        "suffix": suffix,
        "raw_text": raw_text,
    }


def build_pdf_name_from_neighbors(
    lines,
    index,
    parsed_core,
):
    if parsed_core is None:
        return "", []

    if parsed_core.get(
        "company_name"
    ):
        return (
            parsed_core["company_name"],
            [],
        )

    stock_code = parsed_core.get(
        "stock_code",
        "",
    )

    before_fragments = []
    after_fragments = []

    search_distance = 3

    for offset in range(
        1,
        search_distance + 1,
    ):
        before_index = index - offset

        if before_index >= 0:
            candidate = clean_text(
                lines[before_index]
            )

            if is_pdf_name_fragment(
                candidate,
                stock_code,
            ):
                before_fragments.append(
                    clean_pdf_name_fragment(
                        candidate
                    )
                )

                break

    for offset in range(
        1,
        search_distance + 1,
    ):
        after_index = index + offset

        if after_index < len(lines):
            candidate = clean_text(
                lines[after_index]
            )

            if is_pdf_name_fragment(
                candidate,
                stock_code,
            ):
                after_fragments.append(
                    clean_pdf_name_fragment(
                        candidate
                    )
                )

                break

    fragments = (
        list(
            reversed(
                [
                    fragment
                    for fragment
                    in before_fragments
                    if fragment
                ]
            )
        )
        + [
            parsed_core.get(
                "company_name",
                "",
            )
        ]
        + [
            fragment
            for fragment
            in after_fragments
            if fragment
        ]
    )

    fragments = [
        clean_pdf_name_fragment(
            fragment
        )
        for fragment in fragments
        if clean_pdf_name_fragment(
            fragment
        )
    ]

    company_name = "".join(
        fragments
    )

    return (
        company_name,
        fragments,
    )


def parse_pdf_schedule_sessions(
    text_blocks,
    event_title,
    event_id,
    file_format,
):
    sessions = []

    lines = []

    for block in text_blocks:
        for line in block.splitlines():
            line = clean_text(line)

            if line:
                lines.append(line)

    for index, line in enumerate(lines):
        core = parse_pdf_core_row(
            line,
            event_title,
            event_id,
            file_format,
        )

        if core is None:
            continue

        parsed_session = core["session"]

        if not core["company_name"]:
            company_name, fragments = (
                build_pdf_name_from_neighbors(
                    lines,
                    index,
                    {
                        "company_name": core[
                            "company_name"
                        ],
                        "stock_code": core[
                            "stock_code"
                        ],
                    },
                )
            )

            if company_name:
                parsed_session[
                    "company_name"
                ] = company_name

                parsed_session[
                    "company_name_missing"
                ] = False

                parsed_session[
                    "name_reconstructed"
                ] = True

                parsed_session[
                    "name_source_fragments"
                ] = fragments

        sessions.append(
            parsed_session
        )

    return sessions


def parse_pdf_schedule_line(
    line,
    event_title="",
    event_id="",
    file_format="pdf",
):
    core = parse_pdf_core_row(
        line,
        event_title,
        event_id,
        file_format,
    )

    if core is None:
        return None

    return core["session"]


# ============================================================
# 文字備援辨識
# ============================================================

def parse_text_sessions(
    text_blocks,
    event_title,
    event_id,
    file_format,
):
    if file_format.lower() == "pdf":
        return parse_pdf_schedule_sessions(
            text_blocks,
            event_title,
            event_id,
            file_format,
        )

    sessions = []

    for block in text_blocks:
        for line in block.splitlines():
            line = clean_text(line)

            if not line:
                continue

            match = CODE_PATTERN.search(
                line
            )

            if not match:
                continue

            stock_code = match.group(1)

            date_match = DATE_PATTERN.search(
                line,
                match.end(),
            )

            time_match = TIME_PATTERN.search(
                line,
                date_match.end()
                if date_match
                else match.end(),
            )

            if not date_match:
                continue

            if not time_match:
                continue

            prefix = clean_text(
                line[
                    : match.start()
                ]
            )

            middle = clean_text(
                line[
                    match.end() :
                    date_match.start()
                ]
            )

            suffix = clean_text(
                line[
                    time_match.end() :
                ]
            )

            company_name = middle
            sequence_no = ""

            parts = company_name.split()

            if parts and all(
                part.isdigit()
                for part in parts
            ):
                sequence_no = parts[-1]
                company_name = ""

            sessions.append(
                make_session(
                    stock_code=stock_code,
                    sequence_no=sequence_no,
                    company_name=company_name,
                    session_date=date_match.group(
                        0
                    ),
                    session_time=time_match.group(
                        0
                    ),
                    venue=suffix,
                    notes="",
                    event_title=event_title,
                    event_id=event_id,
                    file_format=file_format,
                    raw_text=line,
                    parse_method="text",
                )
            )

    return sessions


# ============================================================
# 去重
# ============================================================

def deduplicate_sessions(sessions):
    result = []
    seen = set()

    for session in sessions:
        key = (
            session.get(
                "event_id",
                "",
            ),
            session.get(
                "stock_code",
                "",
            ),
            session.get(
                "company_name",
                "",
            ),
            session.get(
                "date",
                "",
            ),
            session.get(
                "time",
                "",
            ),
            session.get(
                "sequence_no",
                "",
            ),
        )

        if (
            not session.get(
                "date",
                "",
            )
            and not session.get(
                "time",
                "",
            )
        ):
            key = key + (
                session.get(
                    "raw_text",
                    "",
                ),
            )

        if key in seen:
            continue

        seen.add(key)
        result.append(session)

    return result


# ============================================================
# 品質統計
# ============================================================

def calculate_session_quality(
    sessions
):
    total_sessions = len(
        sessions
    )

    complete_sessions = 0
    missing_company_name_sessions = 0
    cancelled_sessions = 0
    sessions_needing_review = 0

    for session in sessions:
        stock_code = clean_text(
            session.get(
                "stock_code",
                "",
            )
        )

        company_name = clean_text(
            session.get(
                "company_name",
                "",
            )
        )

        session_date = clean_text(
            session.get(
                "date",
                "",
            )
        )

        session_time = clean_text(
            session.get(
                "time",
                "",
            )
        )

        if not company_name:
            missing_company_name_sessions += 1

        if session.get(
            "cancelled",
            False,
        ):
            cancelled_sessions += 1

        if (
            stock_code
            and company_name
            and session_date
            and session_time
        ):
            complete_sessions += 1

        if not (
            stock_code
            and company_name
            and session_date
            and session_time
        ):
            sessions_needing_review += 1

    return {
        "total_sessions": total_sessions,
        "complete_sessions": complete_sessions,
        "missing_company_name_sessions": (
            missing_company_name_sessions
        ),
        "cancelled_sessions": (
            cancelled_sessions
        ),
        "sessions_needing_review": (
            sessions_needing_review
        ),
    }
