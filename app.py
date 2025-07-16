import os
import math
import traceback
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import tushare as ts
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
CORS(app)

# 我们不再在这里初始化Tushare API
# pro = ts.pro_api(TUSHARE_TOKEN) 

def safe_format(value, format_spec="{:.2f}", default_val='-'):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default_val
    try:
        return format(float(value), format_spec)
    except (ValueError, TypeError):
        return default_val

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/financial-data', methods=['GET'])
def get_financial_data():
    # --- 步骤1：在函数内部进行Tushare API的初始化 ---
    TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN')
    if not TUSHARE_TOKEN:
        # 在生产环境中，更建议在日志中记录错误，而不是让程序崩溃
        print("CRITICAL: TUSHARE_TOKEN environment variable not set!")
        return jsonify({"error": "服务器配置错误，缺少API密钥。"}), 500
    
    # 只有在需要处理请求时，才建立API连接
    pro = ts.pro_api(TUSHARE_TOKEN)

    # --- 后续的代码逻辑完全保持不变 ---
    query_str = request.args.get('query')
    if not query_str:
        return jsonify({"error": "查询内容不能为空"}), 400

    ts_code = ''
    company_name = ''

    if '.' in query_str and any(char.isdigit() for char in query_str):
        ts_code = query_str
    else:
        try:
            search_results = pro.stock_basic(keyword=query_str, list_status='L', fields='ts_code,name')
            if search_results.empty: return jsonify({"error": f"找不到公司 '{query_str}'"}), 404
            ts_code = search_results.iloc[0]['ts_code']
        except Exception as e:
            return jsonify({"error": f"名称查询代码时出错: {e}"}), 500
    
    if not ts_code: return jsonify({"error": "未能确定有效的股票代码"}), 400

    try:
        # ... (抓取和处理数据的代码保持不变) ...
        basic_info_df = pro.stock_basic(ts_code=ts_code, fields='name')
        daily_info_df = pro.daily(ts_code=ts_code, limit=1)
        # ... etc ...
        
        # 安全地提取每一个值
        company_name = basic_info_df.iloc[0]['name'] if not basic_info_df.empty else ts_code
        # ... etc ...

        # 使用安全格式化函数整合数据
        data = {
            # ... (整合数据的代码保持不变) ...
        }
        
        return jsonify(data)
    except Exception as e:
        # ... (错误处理代码保持不变) ...
        return jsonify({"error": f"获取并处理数据时发生意外错误: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)