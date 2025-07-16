import os
import math
import traceback
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import tushare as ts
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pandas as pd

load_dotenv()

app = Flask(__name__)
CORS(app)

def safe_format(value, format_spec="{:.2f}", default_val='-'):
    if value is None or not isinstance(value, (int, float)) or math.isnan(value):
        return default_val
    try:
        return format(value, format_spec)
    except (ValueError, TypeError):
        return default_val

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/financial-data', methods=['GET'])
def get_financial_data():
    TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN')
    if not TUSHARE_TOKEN:
        print("CRITICAL: TUSHARE_TOKEN environment variable not set!")
        return jsonify({"error": "服务器配置错误"}), 500
    
    pro = ts.pro_api(TUSHARE_TOKEN)
    query_str = request.args.get('query')
    if not query_str:
        return jsonify({"error": "查询内容不能为空"}), 400

    ts_code = ''
    company_name = ''

    try:
        if '.' in query_str and any(char.isdigit() for char in query_str):
            ts_code = query_str
            basic_info = pro.stock_basic(ts_code=ts_code, fields='name')
            if basic_info.empty:
                return jsonify({"error": f"股票代码 '{ts_code}' 无效或不存在"}), 404
            company_name = basic_info.iloc[0]['name']
        else:
            search_results = pro.stock_basic(keyword=query_str, list_status='L', fields='ts_code,name')
            if search_results.empty:
                return jsonify({"error": f"找不到公司 '{query_str}'"}), 404
            ts_code = search_results.iloc[0]['ts_code']
            company_name = search_results.iloc[0]['name']
    except Exception as e:
        return jsonify({"error": f"查询公司代码时出错: {e}"}), 500

    if not ts_code:
        return jsonify({"error": "未能确定有效的股票代码"}), 400

    try:
        # --- 一次性抓取所有需要的数据 ---
        daily_info_df = pro.daily(ts_code=ts_code, limit=1)
        income_df = pro.income(ts_code=ts_code, end_date='20231231', fields='total_revenue,n_income_attr_p')
        indicator_df = pro.fina_indicator(ts_code=ts_code, end_date='20231231', fields='or_yoy,netprofit_yoy,grossprofit_margin')
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        history_price_df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date, fields='trade_date,close')

        # --- 安全地提取每一个值 ---
        latest_close = daily_info_df.iloc[0]['close'] if not daily_info_df.empty else None
        latest_pct_chg = daily_info_df.iloc[0]['pct_chg'] if not daily_info_df.empty else None
        
        revenue = income_df.iloc[0]['total_revenue'] if not income_df.empty else None
        net_profit = income_df.iloc[0]['n_income_attr_p'] if not income_df.empty else None
        
        revenue_yoy = indicator_df.iloc[0]['or_yoy'] if not indicator_df.empty else None
        net_profit_yoy = indicator_df.iloc[0]['netprofit_yoy'] if not indicator_df.empty else None
        gross_margin = indicator_df.iloc[0]['grossprofit_margin'] if not indicator_df.empty else None

        # --- 使用安全格式化函数整合最终数据 ---
        data = {
            "companyName": company_name,
            "stockCode": ts_code,
            "latestPrice": {
                "close": safe_format(latest_close),
                "pct_chg": safe_format(latest_pct_chg)
            },
            "annualReport2023": {
                "revenue": safe_format(revenue / 1e8 if revenue else None),
                "revenue_yoy": safe_format(revenue_yoy),
                "net_profit": safe_format(net_profit / 1e8 if net_profit else None),
                "net_profit_yoy": safe_format(net_profit_yoy),
                "gross_margin": safe_format(gross_margin)
            },
            "priceHistory": history_price_df.sort_values('trade_date').values.tolist() if not history_price_df.empty else []
        }
        return jsonify(data)
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"--- FATAL ERROR TRACEBACK ---\n{tb_str}\n--- END OF TRACEBACK ---")
        return jsonify({"error": f"获取财务数据时发生意外错误: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)