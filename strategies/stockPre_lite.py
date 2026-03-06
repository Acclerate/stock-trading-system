import pandas as pd
import talib
import akshare as ak
import numpy as np
from datetime import datetime, timedelta
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fetch_stock_data(symbol, start_date, end_date):
    """通过AKShare获取股票历史数据（日线）"""
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date)
        df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume'
            }, inplace=True)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df, True
    except Exception as e:
        return None, False


def calculate_indicators(df):
    """计算技术指标：均线、MACD、RSI、BOLL、成交量（使用TA-Lib）"""
    close = df['close'].values

    # 均线
    df['ma5'] = talib.SMA(close, timeperiod=5)
    df['ma20'] = talib.SMA(close, timeperiod=20)

    # MACD
    macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    df['macd'] = macd
    df['macd_signal'] = macd_signal
    df['macd_hist'] = macd_hist

    # RSI
    df['rsi'] = talib.RSI(close, timeperiod=14)

    # BOLL
    boll_upper, boll_mid, boll_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
    df['boll_upper'] = boll_upper
    df['boll_mid'] = boll_mid
    df['boll_lower'] = boll_lower

    # 成交量
    df['volume_ma3'] = df['volume'].rolling(window=3).mean()
    df['volume_pct_change'] = (df['volume'] / df['volume_ma3'].shift(1)) - 1

    return df


def generate_signals(df):
    """根据策略生成买卖信号"""
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0
    
    buy_conditions = [
        (df['ma5'] > df['ma20']),
        (df['macd'] > df['macd_signal']),
        (df['rsi'] < 30),
        (df['close'] < df['boll_lower']),
        (df['volume_pct_change'] > 0.2)
    ]

    satisfied_counts = sum(cond.astype(int) for cond in buy_conditions)
    buy_condition = satisfied_counts >= 2
    
    sell_condition = (
        (df['macd'] < df['macd_signal']) |
        (df['rsi'] > 70) |
        (df['close'] > df['boll_upper'])
    )
    
    signals.loc[buy_condition, 'signal'] = 1
    signals.loc[sell_condition, 'signal'] = -1
    return signals


def backtest_strategy(df, signals):
    """模拟交易回测"""
    df['position'] = signals['signal'].shift(1)
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['position'] * df['returns']
    df['cum_returns'] = (1 + df['strategy_returns']).cumprod()
    return df


def get_hs300_symbols():
    """获取沪深300成分股代码"""
    try:
        hs300 = ak.index_stock_cons(symbol="000300")
        hs300 = hs300.drop_duplicates(subset=['品种代码'], keep='first')
        hs300['symbol'] = hs300['品种代码'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(6)
        hs300['symbol'] = np.where(
            hs300['symbol'].str.startswith(('0', '3')),
            hs300['symbol'] + '.SZ',
            hs300['symbol'] + '.SH'
        )
        return hs300['symbol'].drop_duplicates().tolist()
    except Exception as e:
        print(f"获取沪深300成分股失败: {str(e)}")
        return []


def save_results_to_txt(results, total_symbols, success_count, failed_count,
                        failed_symbols, total_time, start_date, end_date):
    """使用统一输出工具保存结果（TXT、CSV、SQLite）"""
    if not results:
        print("没有结果需要保存")
        return None

    # ========== 使用统一输出工具 ==========
    from utils.strategy_output import StrategyOutputManager, StrategyMetadata, StockData
    from strategy_tracker.db.repository import get_repository

    sorted_results = sorted(results, key=lambda x: x['return'], reverse=True)
    success_rate = (success_count / total_symbols * 100) if total_symbols > 0 else 0

    # 创建策略元数据
    metadata = StrategyMetadata(
        strategy_name="沪深300成分股筛选 (StockPre Lite版)",
        strategy_type="hs300_lite_screen",
        screen_date=datetime.now(),
        generated_at=datetime.now(),
        scan_count=total_symbols,
        match_count=len(sorted_results),
        strategy_params={
            'backtest_days': 365,
            'min_conditions': 2,
            'success_rate': success_rate,
            'failed_count': failed_count,
            'total_time': total_time
        },
        filter_conditions="至少满足2个买入条件",
        scan_scope="沪深300成分股"
    )

    # 创建输出管理器
    output_mgr = StrategyOutputManager(metadata)

    # 添加股票数据
    for item in sorted_results:
        # 提取6位代码
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
    def format_lite_table(stocks):
        rows = []
        if stocks:
            rows.append("=== 买入信号股票推荐 (按累计收益率降序) ===")
            rows.append(f"{'名称':<20}{'代码':<15}{'最新日期':<12}{'股价':<8}{'收益率':<10}{'判定依据'}")
            rows.append("-" * 100)

            for s in stocks:
                latest_date = s.extra_fields.get('latest_date', 'N/A')
                cum_return = s.extra_fields.get('cum_return', 0)

                line = f"{s.stock_name[:18]:<20}{s.stock_code:<15}{latest_date:<12}" \
                       f"{s.screen_price:>6.2f}{cum_return:>8.2%}  {s.reason}"
                rows.append(line)
        else:
            rows.append("=== 当前无符合条件的股票 ===")

        # 添加失败股票列表
        if failed_symbols:
            rows.append("")
            rows.append(f"失败股票列表（共{len(failed_symbols)}只）:")
            for symbol in failed_symbols[:20]:
                rows.append(f"  - {symbol}")
            if len(failed_symbols) > 20:
                rows.append(f"  ... 还有 {len(failed_symbols) - 20} 只")

        return rows

    # 同时输出所有格式
    try:
        repo = get_repository()
        results = output_mgr.output_all(repo=repo, table_formatter=format_lite_table)
        print(f"\n✓ TXT: {results['txt']}")
        print(f"✓ CSV: {results['csv']}")
        print(f"✓ 数据库记录ID: {results['screening_id']}")
        return str(results['txt'])
    except Exception as e:
        # 如果数据库操作失败，至少输出文件
        print(f"注意: 数据库写入失败 ({e})，仅输出文件")
        results = output_mgr.output_all(table_formatter=format_lite_table)
        print(f"\n✓ TXT: {results['txt']}")
        print(f"✓ CSV: {results['csv']}")
        return str(results['txt'])


if __name__ == "__main__":
    print("=== StockPre 轻量级改进版 ===")
    print("特点: 进度显示 + 结果保存 + 简单统计\n")
    
    symbols = get_hs300_symbols()
    if not symbols:
        print("无法获取沪深300成分股数据")
        exit(1)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    try:
        stock_code_name_df = ak.stock_info_a_code_name()
        code_name_dict = dict(zip(stock_code_name_df['code'], stock_code_name_df['name']))
    except Exception as e:
        print(f"获取股票名称失败: {str(e)}")
        code_name_dict = {}

    results = []
    failed_symbols = []
    total_symbols = len(symbols)
    
    print(f"开始分析 {total_symbols} 只股票...\n")
    
    start_time = datetime.now()
    
    for idx, symbol in enumerate(symbols, 1):
        base_symbol = symbol.split('.')[0]
        stock_name = code_name_dict.get(base_symbol, "")
        
        if idx % 10 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            progress = idx / total_symbols * 100
            print(f"进度: {idx}/{total_symbols} ({progress:.1f}%) - 已用时: {elapsed:.1f}秒")
        
        df, success = fetch_stock_data(base_symbol, start_date, end_date)
        if not success or df is None or df.empty:
            failed_symbols.append(symbol)
            continue
                
        df = calculate_indicators(df)
        signals = generate_signals(df)
        df = backtest_strategy(df, signals)
        
        latest_signal = signals.iloc[-1]['signal']
        if latest_signal == 1:
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
    
    sorted_results = sorted(results, key=lambda x: x['return'], reverse=True)
    
    total_time = (datetime.now() - start_time).total_seconds()
    success_count = len(results)
    failed_count = len(failed_symbols)
    success_rate = (success_count / total_symbols * 100) if total_symbols > 0 else 0
    
    print("\n" + "=" * 60)
    print("=== 买入信号股票推荐 (按累计收益率降序) ===")
    print(f"{'名称':<20}{'代码':<15}{'最新日期':<12}{'股价':<8}{'收益率':<10}{'判定依据'}")
    for item in sorted_results:
        print(f"{item['name'][:18]:<20}{item['symbol']:<15}{item['date']:<12}"
              f"{item['latest_price']:>6.2f}{item['return']:>8.2%}  {item['criteria']}")
    
    print("\n" + "=" * 60)
    print("=== 统计报告 ===")
    print(f"总股票数: {total_symbols}")
    print(f"成功获取: {success_count} ({success_rate:.1f}%)")
    print(f"失败获取: {failed_count}")
    print(f"总用时: {total_time:.1f}秒")
    print(f"平均速度: {total_symbols/total_time:.2f} 只/秒")
    print("=" * 60)
    
    if failed_symbols:
        print(f"\n失败股票列表（前20只）:")
        for symbol in failed_symbols[:20]:
            print(f"  - {symbol}")
        if len(failed_symbols) > 20:
            print(f"  ... 还有 {len(failed_symbols) - 20} 只")

    # 保存结果到txt文件
    txt_filename = save_results_to_txt(
        results=sorted_results,
        total_symbols=total_symbols,
        success_count=success_count,
        failed_count=failed_count,
        failed_symbols=failed_symbols,
        total_time=total_time,
        start_date=start_date,
        end_date=end_date
    )

    if txt_filename:
        print(f"\n结果已保存至: {txt_filename}")

    print("\n=== StockPre 系统结束 ===")
