import os
import traceback
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import tushare as ts
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pandas as pd

# --- 1. 初始化: 加载环境变量并设置Tushare Token ---
load_dotenv()
TUSHARE_TOKEN = os.getenv('TUSHARE_TOKEN')
if not TUSHARE_TOKEN:
    raise RuntimeError('错误: 请在 .env 文件中设置您的 TUSHARE_TOKEN')

ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()

# --- 2. 初始化 Flask 应用 ---
app = Flask(__name__, template_folder='templates')
CORS(app)


@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')


@app.route('/api/financial-data')
def get_financial_data():
    """处理前端的数据查询请求"""
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'error': '查询参数不能为空'}), 400

    try:
        # --- 步骤 1: 获取公司代码(ts_code) ---
        # 判断输入是代码还是公司名称
        if '.' in query or (query.isdigit() and len(query) == 6):
            ts_code = query.upper()
        else:
            # 如果是名称，则从所有A股列表中模糊查询
            # 注意: 此操作会加载所有股票列表，在首次查询时可能稍慢
            df_name = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name')
            match = df_name[df_name['name'].str.contains(query)]
            if match.empty:
                return jsonify({'error': f'未找到名称包含“{query}”的公司'}), 404
            ts_code = match.iloc[0]['ts_code']

        # --- 步骤 2: 并行获取所有需要的数据 ---
        today = datetime.now().strftime('%Y%m%d')
        start_date_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

        # a) 公司基础信息
        basic_df = pro.stock_basic(ts_code=ts_code, fields='ts_code,name,industry,area,list_date')
        
        # b) 最新财务指标 (这里我们获取最新的，Tushare会自动选择最近的报告期)
        metrics_df = pro.fina_indicator(ts_code=ts_code, limit=1, fields='end_date,roe,roa,netprofit_margin')
        
        # c) 最近4期利润表
        income_df = pro.income(ts_code=ts_code, limit=4, fields='end_date,total_revenue,n_income')
        income_df.rename(columns={'n_income': 'net_profit'}, inplace=True) # 字段重命名以方便前端使用
        
        # d) 当日最新股价
        price_df = pro.daily(ts_code=ts_code, start_date=today, end_date=today, fields='trade_date,open,high,low,close,pre_close,pct_chg')
        
        # e) 近一年历史股价
        history_df = pro.daily(ts_code=ts_code, start_date=start_date_year_ago, end_date=today, fields='trade_date,close')

        # --- 步骤 3: 将数据整理成JSON格式 ---
        # to_dict('records') 会将DataFrame转换为字典列表，非常适合JSON
        return jsonify({
            'basicInfo': basic_df.iloc[0].to_dict() if not basic_df.empty else {},
            'metrics': metrics_df.to_dict(orient='records'),
            'incomeStatements': income_df.sort_values('end_date', ascending=False).to_dict(orient='records'),
            'latestPrice': price_df.iloc[0].to_dict() if not price_df.empty else {},
            'priceHistory': history_df.sort_values('trade_date').values.tolist() if not history_df.empty else []
        })

    except Exception as e:
        traceback.print_exc() # 在服务器端打印详细错误，方便调试
        return jsonify({'error': f'查询过程中发生错误：{str(e)}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
