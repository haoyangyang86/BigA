import tushare as ts
from dotenv import load_dotenv
import os

# 加载您的 .env 文件以获取密钥
load_dotenv()
TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN')

if not TUSHARE_TOKEN:
    print("错误：请确保您的 .env 文件中已设置 TUSHARE_TOKEN")
else:
    print("成功读取到Token，正在初始化Tushare API...")
    pro = ts.pro_api(TUSHARE_TOKEN)

    # 使用一个固定的股票代码进行测试
    test_code = '000001.SZ'
    print(f"\n正在为【{test_code}】测试不同的API接口...")

    print("\n--- 1. 正在测试 stock_basic (应成功) ---")
    df1 = pro.stock_basic(ts_code=test_code)
    print(df1)

    print("\n--- 2. 正在测试 daily (应成功) ---")
    df2 = pro.daily(ts_code=test_code, limit=1)
    print(df2)

    print("\n--- 3. 正在测试 income (若积分不足则为空) ---")
    df3 = pro.income(ts_code=test_code, end_date='20231231', fields='ts_code,ann_date,end_date,total_revenue,n_income_attr_p')
    print(df3)

    print("\n--- 4. 正在测试 fina_indicator (若积分不足则为空) ---")
    df4 = pro.fina_indicator(ts_code=test_code, end_date='20231231', fields='ts_code,ann_date,end_date,or_yoy,netprofit_yoy,grossprofit_margin')
    print(df4)