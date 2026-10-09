import datetime
import pandas as pd
from FinMind.data import DataLoader

# 填入你想追蹤的股票清單
STOCK_LIST = ["2330", "2454", "2317", "2603"] 

def analyze_stocks():
    dl = DataLoader()
    today = datetime.date.today()
    
    # 準備儲存結果的清單
    results = []
    
    for stock_id in STOCK_LIST:
        status_growth = "❌ 未符合"
        status_big_holder = "💤 渙散/調節"
        
        # 1. 基本面篩選 (近半年營收)
        try:
            start_revenue = (today - datetime.timedelta(days=180)).strftime("%Y-%m-%d")
            df_rev = dl.taiwan_stock_month_revenue(stock_id=stock_id, start_date=start_revenue)
            if not df_rev.empty and len(df_rev) >= 3:
                df_rev = df_rev.sort_values("date").reset_index(drop=True)
                m0, m1, m2 = df_rev.iloc[-1]['revenue'], df_rev.iloc[-2]['revenue'], df_rev.iloc[-3]['revenue']
                latest_yoy = df_rev.iloc[-1]['revenue_year_growth_rate']
                
                if latest_yoy > 20 and (m0 > m1 > m2):
                    status_growth = "🎯 營收爆發中"
        except Exception:
            status_growth = "⚠️ 資料錯誤"

        # 2. 籌碼面篩選 (近 4 週大戶持股)
        try:
            start_holder = (today - datetime.timedelta(days=60)).strftime("%Y-%m-%d")
            df_big = dl.taiwan_stock_holding_shares_per(stock_id=stock_id, start_date=start_holder)
            df_big = df_big[df_big['HoldingSharesLevel'] == '17'].sort_values("date").reset_index(drop=True)
            if len(df_big) >= 4:
                w0, w1, w2, w3 = df_big.iloc[-1]['percent'], df_big.iloc[-2]['percent'], df_big.iloc[-3]['percent'], df_big.iloc[-4]['percent']
                if w0 > w1 > w2 > w3:
                    status_big_holder = "🔥 大戶連三週吃貨"
                elif w0 > w1:
                    status_big_holder = "👀 本週大戶增加"
        except Exception:
            status_big_holder = "⚠️ 資料錯誤"
            
        results.append({
            "股票代號": stock_id,
            "基本面 (YoY>20%+連增)": status_growth,
            "籌碼面 (千張大戶)": status_big_holder
        })
        
    # 轉成 DataFrame 並輸出成 HTML 網頁
    df_result = pd.DataFrame(results)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>台股自動選股追蹤</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f4f6f9; }}
            h2 {{ color: #333; text-align: center; }}
            .update-time {{ text-align: center; color: #666; font-size: 14px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            th, td {{ padding: 12px; text-align: center; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #007bff; color: white; }}
            tr:hover {{ background-color: #f1f1f1; }}
        </style>
    </head>
    <body>
        <h2>📊 台股策略自動追蹤清單</h2>
        <div class="update-time">最後更新時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        {df_result.to_html(index=False, classes='table')}
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    analyze_stocks()
