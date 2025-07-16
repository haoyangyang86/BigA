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

    # --- 智能判断输入类型 ---
    if '.' in query_str and any(char.isdigit() for char in query_str):
        ts_code = query_str
    else:
        try:
            search_results = pro.stock_basic(keyword=query_str, fields='ts_code,name')
            if search_results.empty: return jsonify({"error": f"找不到公司 '{query_str}'"}), 404
            ts_code = search_results.iloc[0]['ts_code']
        except Exception as e:
            return jsonify({"error": f"查询公司代码时出错: {e}"}), 500
    
    if not ts_code: return jsonify({"error": "未能确定有效的股票代码"}), 400

    try:
        # --- 抓取多维度数据 ---
        # 1. 公司基本信息 (获取公司名)
        basic_info = pro.stock_basic(ts_code=ts_code, fields='ts_code,name')
        company_name = basic_info.iloc[0]['name'] if not basic_info.empty else ts_code

        # 2. 最新日线行情
        daily_info = pro.daily(ts_code=ts_code, limit=1).iloc[0]

        # 3. 利润表数据 (获取2023年报)
        income_df = pro.income(ts_code=ts_code, end_date='20231231', fields='total_revenue,n_income_attr_p')
        annual_revenue_2023 = income_df.iloc[0]['total_revenue']
        net_profit_2023 = income_df.iloc[0]['n_income_attr_p']
        
        # 4. 财务指标 (获取同比增长率和毛利率)
        indicator_df = pro.fina_indicator(ts_code=ts_code, end_date='20231231', fields='or_yoy,netprofit_yoy,grossprofit_margin')
        revenue_yoy = indicator_df.iloc[0]['or_yoy']
        net_profit_yoy = indicator_df.iloc[0]['netprofit_yoy']
        gross_margin = indicator_df.iloc[0]['grossprofit_margin']

        # 5. 历史股价数据 (用于绘制图表，获取最近一年的数据)
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        history_price_df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date, fields='trade_date,close')
        # 转换格式以便ECharts使用
        history_price_data = history_price_df.sort_values('trade_date').values.tolist()

        # --- 整合所有数据到一个包里 ---
        data = {
            "companyName": company_name,
            "stockCode": ts_code,
            "latestPrice": {
                "close": f"{daily_info['close']:.2f}",
                "pct_chg": f"{daily_info['pct_chg']:.2f}",
            },
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
        return jsonify({"error": f"获取公司数据时发生错误，请确认该公司是否已上市并有2023年报数据。错误: {e}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)