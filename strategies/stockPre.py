import pandas as pd
import talib
import akshare as ak
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import argparse

# 添加项目根目录到Python路径，以便导入data模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.data_resilient import DataResilient
from data.cache_manager import CacheManager


# ========== 使用统一输出工具 ==========
from utils.strategy_output import StrategyOutputManager, StrategyMetadata, StockData
from strategy_tracker.db.repository import get_repository

# ========== 股票池配置 ==========
STOCK_POOLS = {
    'hs300': {
        'name': '沪深300',
        'index_code': '000300',
        'description': '沪深300成分股'
    },
    'zz500': {
        'name': '中证500',
        'index_code': '000905',
        'description': '中证500成分股'
    },
    'zz1000': {
        'name': '中证1000',
        'index_code': '000852',
        'description': '中证1000成分股'
    },
    'zx50': {
        'name': '上证50',
        'index_code': '000016',
        'description': '上证50成分股'
    }
}

# ========== 数据获取模块 ==========
def get_stock_pool_symbols(pool_id='zz500'):
    """
    获取指定股票池的成分股代码

    参数:
        pool_id: 股票池ID (hs300/zz500/zz1000/cyb/zx50/all_a)

    返回:
        股票代码列表
    """
    if pool_id not in STOCK_POOLS:
        raise ValueError(f"不支持的股票池: {pool_id}，可选: {list(STOCK_POOLS.keys())}")

    pool_info = STOCK_POOLS[pool_id]

    # 从缓存或API获取指数成分股
    cache_key = f'{pool_id}_symbols'
    cached = CacheManager.load_macro_cache(cache_key)
    if cached is not None:
        return cached

    try:
        # 获取指数成分股
        index_df = ak.index_stock_cons(symbol=pool_info['index_code'])
        index_df = index_df.drop_duplicates(subset=['品种代码'], keep='first')

        # 标准化代码格式
        symbols = index_df['品种代码'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(6).tolist()
        symbols = [f"{s}.SZ" if s.startswith(('0', '3')) else f"{s}.SH" for s in symbols]
        symbols = list(set(symbols))  # 去重

        # 保存缓存
        CacheManager.save_macro_cache(cache_key, symbols)

        return symbols
    except Exception as e:
        print(f"获取{pool_info['name']}成分股失败: {e}")
        return []

def fetch_stock_data(symbol, start_date, end_date):
    """获取股票历史数据（日线）- 带缓存和重试"""
    return DataResilient.fetch_stock_data(symbol, start_date, end_date, use_cache=True)

# ========== 指标计算模块（使用 TA-Lib）==========
def calculate_indicators(df):
    """计算技术指标：均线、MACD、RSI、BOLL、成交量"""
    # 确保数据是 numpy 数组格式（TA-Lib 要求）
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    volume = df['volume'].values

    # 均线 (5日, 20日)
    df['ma5'] = talib.SMA(close, timeperiod=5)
    df['ma20'] = talib.SMA(close, timeperiod=20)

    # MACD (默认参数：fast=12, slow=26, signal=9)
    # 返回值：macd, signal, hist
    macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    df['macd'] = macd
    df['macd_signal'] = macd_signal
    df['macd_hist'] = macd_hist

    # RSI (14日)
    df['rsi'] = talib.RSI(close, timeperiod=14)

    # BOLL (20日, 2倍标准差)
    # 返回值：upper, middle, lower
    boll_upper, boll_mid, boll_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
    df['boll_upper'] = boll_upper
    df['boll_mid'] = boll_mid
    df['boll_lower'] = boll_lower

    # 成交量变化率（3日平均）
    df['volume_ma3'] = df['volume'].rolling(window=3).mean()
    df['volume_pct_change'] = (df['volume'] / df['volume_ma3'].shift(1)) - 1

    return df

# ========== 信号生成模块 ==========
def generate_signals(df):
    """根据策略生成买卖信号"""
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0  # 0: 无信号, 1: 买入, -1: 卖出
    
    # 单独存储每个买入条件
    buy_conditions = [
        (df['ma5'] > df['ma20']),  # 条件1: 均线金叉
        (df['macd'] > df['macd_signal']),  # 条件2: MACD金叉
        (df['rsi'] < 30),  # 条件3: RSI超卖
        (df['close'] < df['boll_lower']),  # 条件4: 股价触及BOLL下轨
        (df['volume_pct_change'] > 0.2)  # 条件5: 成交量放大20%
    ]

    # 计算满足条件数量
    satisfied_counts = sum(cond.astype(int) for cond in buy_conditions)
    
    # 新买入条件：至少满足2个条件
    buy_condition = satisfied_counts >= 2
    
    # 卖出条件（任一条件触发）
    sell_condition = (
        (df['macd'] < df['macd_signal']) |  # MACD死叉
        (df['rsi'] > 70) |  # RSI超买
        (df['close'] > df['boll_upper'])  # BOLL触及上轨
    )
    
    
    signals.loc[buy_condition, 'signal'] = 1
    signals.loc[sell_condition, 'signal'] = -1
    return signals

# ========== 回测模块 ==========
def backtest_strategy(df, signals):
    """模拟交易回测"""
    df['position'] = signals['signal'].shift(1)  # 次日开盘执行
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['position'] * df['returns']
    df['cum_returns'] = (1 + df['strategy_returns']).cumprod()
    return df

# ========== 主程序 ==========
def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description='股票池筛选系统 - 基于技术指标筛选买入信号',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
支持股票池:
  hs300   沪深300 (默认)
  zz500   中证500
  zz1000  中证1000
  zx50    上证50

示例:
  python stockPre.py -p hs300     # 默认沪深300
  python stockPre.py -p zz500     # 使用中证500
  python stockPre.py -p zz1000    # 使用中证1000
  python stockPre.py -p zx50      # 使用上证50
        '''
    )
    parser.add_argument('-p', '--pool', type=str, default='hs300',
                        choices=list(STOCK_POOLS.keys()),
                        help='股票池选择 (默认: hs300)')
    parser.add_argument('-d', '--days', type=int, default=365,
                        help='回测天数 (默认: 365)')

    args = parser.parse_args()

    # 初始化
    CacheManager.initialize()

    # 获取股票池信息
    pool_id = args.pool
    pool_info = STOCK_POOLS[pool_id]

    print("=" * 60)
    print(f"股票池筛选系统")
    print("=" * 60)
    print(f"股票池: {pool_info['name']} ({pool_info['description']})")
    print(f"回测天数: {args.days}天")
    print("=" * 60)
    print()

    # 获取股票池成分股
    symbols = get_stock_pool_symbols(pool_id)
    if not symbols:
        raise ValueError(f"无法获取{pool_info['name']}成分股数据")

    print(f"✅ 获取到 {len(symbols)} 只股票")
    print()

    # 日期设置
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")

    # 获取股票名称映射
    stock_code_name_df = DataResilient.get_stock_info(use_cache=True)
    code_name_dict = dict(zip(stock_code_name_df['code'], stock_code_name_df['name'])) if not stock_code_name_df.empty else {}

    results = []  # 存储所有股票结果
    failed_count = 0

    # 处理每只股票
    for idx, symbol in enumerate(symbols, 1):
        # 提取纯数字代码用于名称查询
        base_symbol = symbol.split('.')[0]
        stock_name = code_name_dict.get(base_symbol, "")

        # 进度显示
        if idx % 50 == 0 or idx == len(symbols):
            print(f"进度: {idx}/{len(symbols)} ({idx/len(symbols)*100:.1f}%)")

        try:
            df = fetch_stock_data(base_symbol, start_date, end_date)
            if df is None or df.empty:
                failed_count += 1
                continue

            df = calculate_indicators(df)
            signals = generate_signals(df)
            df = backtest_strategy(df, signals)

            # 只记录有买入信号的
            latest_signal = signals.iloc[-1]['signal']
            if latest_signal == 1:
                # 获取最新日期满足的买入条件
                latest_date = df.index[-1]
                satisfied_conditions = [
                    "均线金叉" if (df.loc[latest_date, 'ma5'] > df.loc[latest_date, 'ma20']) else None,
                    "MACD金叉" if (df.loc[latest_date, 'macd'] > df.loc[latest_date, 'macd_signal']) else None,
                    "RSI超卖" if (df.loc[latest_date, 'rsi'] < 30) else None,
                    "BOLL下轨" if (df.loc[latest_date, 'close'] < df.loc[latest_date, 'boll_lower']) else None,
                    "放量20%" if (df.loc[latest_date, 'volume_pct_change'] > 0.2) else None
                ]
                satisfied_conditions = [x for x in satisfied_conditions if x is not None]

                results.append({
                    'symbol': symbol,
                    'name': stock_name,
                    'return': df['cum_returns'].iloc[-1],
                    'latest_price': df['close'].iloc[-1],
                    'date': df.index[-1].strftime('%Y-%m-%d'),
                    'criteria': ' + '.join(satisfied_conditions)
                })
        except Exception as e:
            failed_count += 1
            continue

    # 按累计收益率排序
    sorted_results = sorted(results, key=lambda x: x['return'], reverse=True)


    # 创建策略元数据
    metadata = StrategyMetadata(
        strategy_name=f"{pool_info['name']}成分股筛选",
        strategy_type=f"{pool_id}_screen",
        screen_date=datetime.now(),
        generated_at=datetime.now(),
        scan_count=len(symbols),
        match_count=len(sorted_results),
        strategy_params={
            'pool_id': pool_id,
            'pool_name': pool_info['name'],
            'backtest_days': args.days,
            'min_conditions': 2,
            'start_date': start_date,
            'end_date': end_date,
            'failed_count': failed_count
        },
        filter_conditions="至少满足2个买入条件",
        scan_scope=f"{pool_info['name']}成分股"
    )

    # 创建输出管理器
    output_mgr = StrategyOutputManager(metadata)

    # 添加股票数据
    for item in sorted_results:
        # 提取6位代码（去掉.SZ/.SH后缀）
        stock_code = item['symbol'].split('.')[0] if '.' in item['symbol'] else item['symbol']

        stock = StockData(
            stock_code=stock_code,
            stock_name=item['name'],
            screen_price=item['latest_price'],
            score=item['return'] * 100,  # 转换为百分比
            reason=item['criteria'],
            extra_fields={
                'latest_date': item['date'],
                'cum_return': item['return']
            }
        )
        output_mgr.add_stock(stock)

    # 自定义表格格式化函数（保持原有格式）
    def format_stockpre_table(stocks):
        rows = []
        if stocks:
            rows.append("=== 买入信号股票推荐 (按累计收益率降序) ===")
            rows.append(f"{'名称':<20}{'代码':<15}{'最新日期':<12}{'股价':<8}{'收益率':<10}{'判定依据'}")
            rows.append("-" * 100)

            for s in stocks:
                # 从 extra_fields 获取数据
                latest_date = s.extra_fields.get('latest_date', 'N/A')
                cum_return = s.extra_fields.get('cum_return', 0)

                line = f"{s.stock_name[:18]:<20}{s.stock_code:<15}{latest_date:<12}" \
                       f"{s.screen_price:>6.2f}{cum_return:>8.2%}  {s.reason}"
                rows.append(line)
        else:
            rows.append("=== 当前无符合条件的股票 ===")
        return rows

    # 同时输出所有格式
    try:
        repo = get_repository()
        results = output_mgr.output_all(repo=repo, table_formatter=format_stockpre_table)
        print(f"\n✓ TXT: {results['txt']}")
        print(f"✓ CSV: {results['csv']}")
        print(f"✓ 数据库记录ID: {results['screening_id']}")
    except Exception as e:
        # 如果数据库操作失败，至少输出文件
        print(f"注意: 数据库写入失败 ({e})，仅输出文件")
        results = output_mgr.output_all(table_formatter=format_stockpre_table)
        print(f"\n✓ TXT: {results['txt']}")
        print(f"✓ CSV: {results['csv']}")

    # 输出到控制台（原有格式）
    print('\n')
    print('\n'.join(output_mgr._generate_txt_content(format_stockpre_table)))
    print("")
    print("=" * 80)
    print("买入条件说明:")
    print("  1. 均线金叉   - MA5 > MA20")
    print("  2. MACD金叉  - MACD > Signal")
    print("  3. RSI超卖   - RSI < 30")
    print("  4. BOLL下轨  - 收盘价 < BOLL下轨")
    print("  5. 放量20%   - 成交量较3日均量放大20%")
    print("=" * 80)


if __name__ == "__main__":
    main()