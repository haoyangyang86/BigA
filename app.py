import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import tushare as ts
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN')
if not TUSHARE_TOKEN:
    raise ValueError("未找到环境变量 TUSHARE_TOKEN，请在 .env 文件中设置您的API密钥！")
pro = ts.pro_api(TUSHARE_TOKEN)


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
    
    # --- 全新的、更清晰的判断与查询逻辑 ---
    # 假设输入的是代码
    if '.' in query_str and any(char.isdigit() for char in query_str):
        ts_code = query_str
        try:
            # 尝试用代码查名称 (需要积分)
            name_result = pro.stock_basic(ts_code=ts_code, fields='name')
            company_name = name_result.iloc[0]['name'] if not name_result.empty else ts_code
        except Exception:
            # 积分不够或查询失败，则名称也用代码代替
            company_name = ts_code
    # 假设输入的是名称
    else:
        company_name = query_str
        try:
            # 尝试用名称查代码 (需要积分)
            search_results = pro.stock_basic(keyword=query_str, fields='ts_code,name')
            if search_results.empty:
                return jsonify({"error": f"找不到公司名称为 '{query_str}' 的股票"}), 404
            
            ts_code = search_results.iloc[0]['ts_code']
            company_name = search_results.iloc[0]['name'] # 使用Tushare返回的官方名称
        except Exception as e:
            return jsonify({"error": f"查询公司代码时出错，Tushare积分可能不足。错误: {e}"}), 500
    
    if not ts_code:
        return jsonify({"error": "未能确定有效的股票代码"}), 400

    # --- 使用确定的 ts_code 查询行情数据 ---
    try:
        df = pro.daily(ts_code=ts_code, limit=1)
        if df.empty:
            return jsonify({"error": f"无法获取 {ts_code} 的日线行情数据"}), 404

        latest_trade_info = df.iloc[0]
        
        # --- 准备最终发送给前端的数据包 ---
        data = {
            "userInput": query_str,        # 用户的原始输入
            "resolvedName": company_name,  # 解析出的公司名
            "resolvedCode": ts_code,       # 解析出的股票代码
            "trade_date": latest_trade_info['trade_date'],
            "close": f"{latest_trade_info['close']:.2f}",
            "open": f"{latest_trade_info['open']:.2f}",
            "high": f"{latest_trade_info['high']:.2f}",
            "low": f"{latest_trade_info['low']:.2f}",
            "vol": f"{(latest_trade_info['vol'] / 100):.2f} 万手",
            "pct_chg": f"{latest_trade_info['pct_chg']:.2f}"
        }
        
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"获取行情数据时发生错误: {e}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)