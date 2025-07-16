import os
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

    # --- 步骤1：获取有效的股票代码和公司名 ---
    if '.' in query_str and any(char.isdigit() for char in query_str):
        ts_code = query_str
        try:
            basic_info = pro.stock_basic(ts_code=ts_code, fields='name')
            if basic_info.empty:
                return jsonify({"error": f"股票代码 '{ts_code}' 无效或不存在"}), 404
            company_name = basic_info.iloc[0]['name']
        except Exception as e:
            return jsonify({"error": f"查询股票基本信息时出错: {e}"}), 500
    else:
        try:
            # 优化查询，只查找主板、创业板、科创板的上市股票
            search_results = pro.stock_basic(keyword=query_str, list_status='L', exchange='', fields='ts_code,name')
            if search_results.empty:
                return jsonify({"error": f"找不到公司 '{query_str}'"}), 404
            ts_code = search_results.iloc[0]['ts_code']
            company_name = search_results.iloc[0]['name']
        except Exception as e:
            return jsonify({"error": f"通过名称查询公司代码时出错: {e}"}), 500
    
    if not ts_code:
        return jsonify({"error": "未能确定有效的股票代码"}), 400

    try:
        # --- 步骤2：抓取并验证各项数据 ---
        
        # 获取最新日线行情
        daily_info_df = pro.daily(ts_code=ts_code, limit=1)
        if daily_info_df.empty:
            return jsonify({"error": f"未找到 {company_name} ({ts_code}) 的日线行情数据。"}), 404
        daily_info = daily_info_df.iloc[0]

        # 获取利润表数据 (2023年报)
        income_df = pro.income(ts_code=ts_code, end_date='20231231', fields='total_revenue,n_income_attr_p')
        if income_df.empty:
            return jsonify({"error": f"未找到 {company_name} ({ts_code}) 的2023年度利润表数据。"}), 404
        annual_revenue_2023 = income_df.iloc[0]['total_revenue']
        net_profit_2023 = income_df.iloc[0]['n_income_attr_p']
        
        # 获取财务指标 (同比增长率和毛利率)
        indicator_df = pro.fina_indicator(ts_code=ts_code, end_date='20231231', fields='or_yoy,netprofit_yoy,grossprofit_margin')
        if indicator_df.empty:
            return jsonify({"error": f"未找到 {company_name} ({ts_code}) 的2023年度财务指标数据。"}), 404
        revenue_yoy = indicator_df.iloc[0]['or_yoy']
        net_profit_yoy = indicator_df.iloc[0]['netprofit_yoy']
        gross_margin = indicator_df.iloc[0]['grossprofit_margin']

        # 获取历史股价数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        history_price_df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date, fields='trade_date,close')
        if history_price_df.empty:
            return jsonify({"error": f"未找到 {company_name} ({ts_code}) 的历史股价数据。"}), 404
        history_price_data = history_price_df.sort_values('trade_date').values.tolist()

        # --- 步骤3：整合所有数据到一个包里 ---
        data = {
            "companyName": company_name,
            "stockCode": ts_code,
            "latestPrice": { "close": f"{daily_info['close']:.2f}", "pct_chg": f"{daily_info['pct_chg']:.2f}" },
            "annualReport2023": {
                "revenue": f"{(annual_revenue_2023 / 1e8):.2f}",
                "revenue_yoy": f"{revenue_yoy:.2f}",
                "net_profit": f"{(net_profit_2023 / 1e8):.2f}",
                "net_profit_yoy": f"{net_profit_yoy:.2f}",
                "gross_margin": f"{gross_margin:.2f}",
            },
            "priceHistory": history_price_data
        }
        
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"获取数据时发生意外错误: {e}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)