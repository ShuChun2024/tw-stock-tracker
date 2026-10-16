import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime

def fetch_mops_briefing_json(company_id, western_year):
    """
    介接公開資訊觀測站(MOPS)查詢指定公司與年份的法人說明會資訊，並回傳 JSON 格式。
    
    :param company_id: 股號 (字串或數字，例如 '2330')
    :param western_year: 西元年份 (數字，例如 2025)
    :return: json_string (JSON 格式的字串資料)
    """
    url = "https://twse.com.tw"
    
    # 1. 將西元年轉換為觀測站所需的民國年
    taiwan_year = western_year - 1911
    if taiwan_year <= 0:
        return json.dumps({"error": "年份輸入錯誤，請輸入大於 1911 的西元年份。"}, ensure_ascii=False)

    # 2. 設定 Headers 偽裝瀏覽器行為，避免被伺服器直接拒絕
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://twse.com.tw",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    # 3. 準備 POST 請求的表單參數
    form_data = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "co_id": str(company_id),
        "year": str(taiwan_year)
    }
    
    result_data = {
        "query_info": {
            "company_id": str(company_id),
            "query_western_year": western_year,
            "query_taiwan_year": taiwan_year,
            "execution_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "briefings": []
    }
    
    try:
        # 發送請求
        response = requests.post(url, headers=headers, data=form_data, timeout=15)
        
        if response.status_code != 200:
            return json.dumps({"error": f"連線失敗，HTTP 狀態碼: {response.status_code}"}, ensure_ascii=False)
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尋找含有資料的關鍵表格 (MOPS 常用樣式類別為 'hasBorder')
        table = soup.find('table', {'class': 'hasBorder'})
        
        if not table:
            # 檢查網頁內是否有特定的查無資料提示
            if "查無資料" in response.text:
                return json.dumps({"query_info": result_data["query_info"], "briefings": [], "message": "該年度查無此公司之法說會申報資料。"}, ensure_ascii=False, indent=4)
            return json.dumps({"error": "無法正確解析網頁結構，可能是已被防爬蟲機制阻擋或網頁架構已調整。"}, ensure_ascii=False)
            
        # 4. 解析表格列資料
        rows = table.find_all('tr')
        if len(rows) <= 1:
            return json.dumps({"query_info": result_data["query_info"], "briefings": [], "message": "表格內無資料列。"}, ensure_ascii=False, indent=4)
            
        # 第一列通常是欄位名稱（如：公司代號、公司名稱、法人說明會日期...等）
        headers_list = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
        
        # 走訪每一行資料列
        for row in rows[1:]:
            cols = row.find_all('td')
            if not cols:
                continue
                
            row_data = {}
            for i, col in enumerate(cols):
                # 取得欄位名稱，若超出預期則用索引值代替
                col_name = headers_list[i] if i < len(headers_list) else f"field_{i}"
                
                # 處理欄位內的文字
                text_val = col.get_text(strip=True)
                
                # 特殊處理：如果欄位裡有按鈕（例如簡報檔下載按鈕），擷取按鈕上的說明文字
                button = col.find('input', {'type': 'button'})
                if button and button.has_attr('value'):
                    text_val = button['value']
                    
                row_data[col_name] = text_val
                
            if row_data:
                result_data["briefings"].append(row_data)
                
        return json.dumps(result_data, ensure_ascii=False, indent=4)
        
    except requests.exceptions.Timeout:
        return json.dumps({"error": "請求逾時，證交所伺服器反應過慢，請稍後再試。"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"程式執行發生異常: {str(e)}"}, ensure_ascii=False)

if __name__ == "__main__":
    # 範例：查詢台積電 (2330) 西元 2025 年的法說會資料
    target_company = "2330"
    target_year = 2025
    
    print(f"正在向公開資訊觀測站請求 {target_company} 公司 {target_year} 年的資料...")
    json_output = fetch_mops_briefing_json(target_company, target_year)
    
    # 輸出至終端機觀看
    print("\n=== 查詢結果 JSON 輸出 ===")
    print(json_output)
    
    # 同時將 JSON 寫入檔案儲存
    output_filename = f"mops_briefing_{target_company}_{target_year}.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(json_output)
    print(f"\n[完成] 完整 JSON 數據已成功儲存至檔案: {output_filename}")
