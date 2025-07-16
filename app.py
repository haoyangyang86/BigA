import os
import math
import traceback  # 1. 导入traceback模块
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import tushare as ts
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
CORS(app)

TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN')
if not TUSHARE_TOKEN:
    raise ValueError("未找到环境变量 TUSHARE_TOKEN，请在 .env 文件中设置您的API密钥！")
pro = ts.pro_api(TUSHARE_TOKEN)


def format_value(value, unit='', decimal_places=2, default_val='-'):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default_val
    try:
        if unit == '亿':
            formatted_value = f"{(float(value) / 1e8):.{decimal_places}f}"
        else:
            formatted_value = f"{float(value):.{decimal_places}f}"
        return formatted_value
    except (ValueError, TypeError):
        return default_val

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/financial-data', methods=['GET'])
def get_financial_data():
    query_str = request.args.get('query')
    if not query_str:
        return jsonify({"error": "查询内容不能为空"}), 400

    ts_code = ''
    company_name = ''

    if '.' in query_str and any(char.isdigit() for char in query_str):
        ts_code = query_str
        try:
            basic_info = pro.stock_basic(ts_code=ts_code, fields='name')
            if basic_info.empty: return jsonify({"error": f"股票代码 '{ts_code}' 无效"}), 404
            company_name = basic_info.iloc[0]['name']
        except Exception as e:
            return jsonify({"error": f"查询股票基本信息时出错: {e}"}), 500
    else:
        try:
            search_results = pro.stock_basic(keyword=query_str, list_status='L', fields='ts_code,name')
            if search_results.empty: return jsonify({"error": f"找不到公司 '{query_str}'"}), 404
            ts_code = search_results.iloc[0]['ts_code']
            company_name = search_results.iloc[0]['name']
        except Exception as e:
            return jsonify({"error": f"通过名称查询公司代码时出错: {e}"}), 500
    
    if not ts_code: return jsonify({"error": "未能确定有效的股票代码"}), 400

    try:
        # ... (抓取和整合数据的代码保持不变) ...
        daily_info_df = pro.daily(ts_code=ts_code, limit=1)
        income_df = pro.income(ts_code=ts_code, end_date='20231231', fields='total_revenue,n_income_attr_p')
        indicator_df = pro.fina_indicator(ts_code=ts_code, end_date='20231231', fields='or_yoy,netprofit_yoy,grossprofit_margin')
        
        data = {
            "companyName": company_name, "stockCode": ts_code,
            "latestPrice": {
                "close": format_value(daily_info_df.iloc[0]['close'] if not daily_info_df.empty else None),
                "pct_chg": format_value(daily_info_df.iloc[0]['pct_chg'] if not daily_info_df.empty else None),
            },
            "annualReport2023": {
                "revenue": format_value(income_df.iloc[0]['total_revenue'] if not income_df.empty else None, unit='亿'),
                "revenue_yoy": format_value(indicator_df.iloc[0]['or_yoy'] if not indicator_df.empty else None),
                "net_profit": format_value(income_df.iloc[0]['n_income_attr_p'] if not income_df.empty else None, unit='亿'),
                "net_profit_yoy": format_value(indicator_df.iloc[0]['netprofit_yoy'] if not indicator_df.empty else None),
                "gross_margin": format_value(indicator_df.iloc[0]['grossprofit_margin'] if not indicator_df.empty else None),
            },
        }

        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        history_price_df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date, fields='trade_date,close')
        data["priceHistory"] = history_price_df.sort_values('trade_date').values.tolist() if not history_price_df.empty else []
        
        return jsonify(data)
    # --- 2. 修改最后的except模块，增加日志打印 ---
    except Exception as e:
        # 在日志中打印详细的错误追溯信息
        tb_str = traceback.format_exc()
        print(f"--- FATAL ERROR TRACEBACK ---")
        print(tb_str)
        print(f"--- END OF TRACEBACK ---")
        # 返回给前端一个清晰的错误信息
        return jsonify({"error": f"服务器内部发生严重错误，请联系管理员。错误详情已记录。"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)