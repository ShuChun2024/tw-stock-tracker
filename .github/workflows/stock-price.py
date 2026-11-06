name: Test Stock Price API

on:
  schedule:
    - cron: "0 10 * * 1-5" # 台灣時間平日 18:00
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: stock-price-test
  cancel-in-progress: false

jobs:
  test-stock-price:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          ref: main

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests

      - name: Test stock price API
        run: python test_stock_price.py

      - name: Upload test result
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: stock-price-test-result
          path: stock_prices_test.json
          if-no-files-found: ignore
          retention-days: 7
