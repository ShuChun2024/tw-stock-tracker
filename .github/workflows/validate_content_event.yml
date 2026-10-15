name: 驗證事件內容與來源
on:
  workflow_dispatch:
  push:
    paths:
      - "events.json"
      - "test_conference.py"
      - "conference_parser.py"
      - "pdf_parser.py"
      - "docx_parser.py"
      - "validate_event_content.py"
      - ".github/workflows/validate_event_content.yml"
permissions:
  contents: read
jobs:
  validate-event-content:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then
            pip install -r requirements.txt
          else
            pip install requests python-docx pdfplumber
          fi
      - name: Check required source files
        run: |
          for file in \
            test_conference.py \
            conference_parser.py \
            pdf_parser.py \
            docx_parser.py \
            validate_event_content.py \
            events.json
          do
            if [ ! -f "$file" ]; then
              echo "錯誤：找不到 $file"
              exit 1
            fi
          done
          echo "必要檔案檢查完成"
      - name: Run conference parser v13
        run: |
          python test_conference.py
      - name: Check generated conference result
        run: |
          if [ ! -f twse_conference_v13_result.json ]; then
            echo "錯誤：v13 未產生 twse_conference_v13_result.json"
            exit 1
          fi
          echo "v13 結果檔已產生"
          ls -lh twse_conference_v13_result.json
      - name: Validate event content
        run: |
          python validate_event_content.py
