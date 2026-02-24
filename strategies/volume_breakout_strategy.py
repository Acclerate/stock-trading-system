# -*- coding: utf-8 -*-
"""
低位放量突破策略 v1.0

策略思路：
寻找长期低位震荡的中小盘股票，在近期逐步放量时捕捉潜在机会

核心逻辑：
1. 选股池：全A股剔除ST、停牌、次新股（上市不足250天）
2. 四因子筛选：
   - 市值因子：20亿 < 总市值 < 300亿
   - 低位因子：当前价格/250日最高价 < 0.6（或过去120日振幅<40%）
   - 放量因子：5日均量 > 20日均量*1.5 且 20日均量 > 60日均量
   - 趋势因子：收盘价 > MA60
3. 综合评分：多因子打分排序
4. 回测验证：买入持有20天，止盈20%，止损-8%

适用场景：
- 小盘股风格占优市场
- 底部反转初期
- 主力建仓阶段

注意事项：
- 小盘股流动性风险较高
- 需要配合市场环境判断
- 建议每周调仓一次
"""

import pandas as pd
import numpy as np
import talib
import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.data_resilient import DataResilient
from data.cache_manager import CacheManager
from gm.api import *

# 加载.env文件
load_dotenv()

# 读取token
token = os.getenv('DIGGOLD_TOKEN')


# ========== 策略参数配置 ==========
class StrategyConfig:
    """策略参数配置"""

    # 选股参数
    MIN_MARKET_CAP = 20  # 最小市值（亿元）
    MAX_MARKET_CAP = 300  # 最大市值（亿元）
    MIN_LISTING_DAYS = 250  # 剔除上市不足N天的次新股
    PRICE_POSITION_THRESHOLD = 0.6  # 低位阈值：当前价格/250日最高价
    LOW_VOLATILITY_THRESHOLD = 0.4  # 低振幅阈值：过去120日振幅

    # 放量参数
    VOLUME_EXPANSION_RATIO = 1.5  # 5日均量 > 20日均量 * N
    VOLUME_TREND_RATIO = 1.0  # 20日均量 > 60日均量 * N

    # 趋势参数
    MA_PERIOD = 60  # 均线周期

    # 回测参数
    HOLDING_DAYS = 20  # 持有天数
    TAKE_PROFIT_PCT = 0.20  # 止盈百分比
    STOP_LOSS_PCT = -0.08  # 止损百分比

    # 筛选参数
    TOP_N_STOCKS = 30  # 选出得分最高的N只股票

    # 数据参数
    HISTORY_DAYS = 300  # 获取历史数据天数（用于计算250日最高价等）


# ========== 全市场股票获取模块 ==========
def get_all_a_stocks(trade_date=None):
    """
    获取全A股股票列表（剔除ST、停牌、次新股）

    参数:
        trade_date: 交易日期字符串 'YYYY-MM-DD'，默认为当前日期

    返回:
        股票代码列表
    """
    if trade_date is None:
        trade_date = datetime.now().strftime('%Y-%m-%d')

    trade_date_ts = pd.Timestamp(trade_date)

    print(f"获取全A股股票列表（日期: {trade_date}）...")

    # 使用掘金SDK获取A股股票
    try:
        stocks_info = get_symbols(
            sec_type1=1010,  # 股票
            sec_type2=101001,  # A股
            skip_suspended=True,  # 剔除停牌
            skip_st=True,  # 剔除ST
            trade_date=trade_date,
            df=True
        )

        if stocks_info.empty:
            print("未获取到股票列表")
            return []

        # 处理日期字段
        stocks_info['listed_date'] = stocks_info['listed_date'].apply(
            lambda x: x.replace(tzinfo=None) if hasattr(x, 'tzinfo') else x
        )
        stocks_info['delisted_date'] = stocks_info['delisted_date'].apply(
            lambda x: x.replace(tzinfo=None) if hasattr(x, 'tzinfo') else x
        )

        # 剔除次新股和退市股
        cutoff_date = trade_date_ts - pd.Timedelta(days=StrategyConfig.MIN_LISTING_DAYS)
        stocks_info = stocks_info[
            (stocks_info['listed_date'] <= cutoff_date) &
            (stocks_info['delisted_date'] > trade_date_ts)
        ]

        all_stocks = list(stocks_info['symbol'])

        print(f"可选股票池数量: {len(all_stocks)} "
              f"(剔除次新股<{StrategyConfig.MIN_LISTING_DAYS}天, 停牌, ST)")

        return all_stocks

    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return []


# ========== 因子计算模块 ==========
class FactorCalculator:
    """因子计算器"""

    @staticmethod
    def calculate_all_factors(df):
        """
        计算所有技术和量价因子

        参数:
            df: 包含 OHLCV 数据的 DataFrame

        返回:
            添加了所有因子的 DataFrame
        """
        if df.empty or len(df) < StrategyConfig.MA_PERIOD:
            return None

        # 确保数据是 numpy 数组格式（TA-Lib 要求）
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values

        # ========== 技术指标 ==========
        # 均线
        df['ma20'] = talib.SMA(close, timeperiod=20)
        df['ma60'] = talib.SMA(close, timeperiod=60)
        df['ma120'] = talib.SMA(close, timeperiod=120)

        # 成交量均线
        df['volume_ma5'] = df['volume'].rolling(window=5).mean()
        df['volume_ma20'] = df['volume'].rolling(window=20).mean()
        df['volume_ma60'] = df['volume'].rolling(window=60).mean()

        # 250日最高价（用于判断低位）
        df['high250'] = df['high'].rolling(window=250).max()

        # 120日振幅（用于判断横盘）
        df['high120'] = df['high'].rolling(window=120).max()
        df['low120'] = df['low'].rolling(window=120).min()
        df['amplitude120'] = (df['high120'] - df['low120']) / df['low120']

        # ========== 因子计算 ==========
        # 因子1：价格位置因子
        df['price_position_factor'] = df['close'] / df['high250']

        # 因子2：放量因子
        df['volume_expansion_factor'] = df['volume_ma5'] / (df['volume_ma20'] * StrategyConfig.VOLUME_EXPANSION_RATIO)
        df['volume_trend_factor'] = df['volume_ma20'] / (df['volume_ma60'] * StrategyConfig.VOLUME_TREND_RATIO)

        # 因子3：趋势因子
        df['trend_factor'] = df['close'] / df['ma60']

        return df.dropna()

    @staticmethod
    def calculate_stock_score(df, market_cap=None):
        """
        计算股票综合得分

        参数:
            df: 包含因子的 DataFrame
            market_cap: 总市值（亿元），可选

        返回:
            股票得分（0-100），如果不满足条件返回 0
        """
        if df is None or len(df) < 2:
            return 0

        latest = df.iloc[-1]

        score = 0
        reasons = []

        # ========== 条件1：市值因子（必须满足） ==========
        if market_cap is None:
            # 如果没有市值数据，跳过市值检查
            pass
        elif not (StrategyConfig.MIN_MARKET_CAP <= market_cap <= StrategyConfig.MAX_MARKET_CAP):
            return 0, "市值不符合"
        else:
            score += 20
            reasons.append(f"市值{market_cap:.1f}亿")

        # ========== 条件2：低位因子（30分） ==========
        price_position = latest['price_position_factor']

        # 2A：价格位置（最常用）
        if price_position < StrategyConfig.PRICE_POSITION_THRESHOLD:
            low_score = 30 * (1 - price_position / StrategyConfig.PRICE_POSITION_THRESHOLD)
            score += low_score
            reasons.append(f"低位{price_position:.2%}")
        # 2B：低振幅（横盘）
        elif latest['amplitude120'] < StrategyConfig.LOW_VOLATILITY_THRESHOLD:
            score += 25
            reasons.append(f"横盘振幅{latest['amplitude120']:.2%}")
        else:
            return 0, "不在低位"

        # ========== 条件3：放量因子（40分） ==========
        volume_expansion = latest['volume_expansion_factor']
        volume_trend = latest['volume_trend_factor']

        if volume_expansion >= 1.0 and volume_trend >= 1.0:
            # 逐步放量的得分计算
            expansion_score = min(40, 20 * volume_expansion + 20 * volume_trend)
            score += expansion_score
            reasons.append(f"放量{volume_expansion:.2f}倍")
        else:
            return 0, "放量不足"

        # ========== 条件4：趋势因子（10分） ==========
        trend_factor = latest['trend_factor']

        if trend_factor > 1.0:  # 收盘价 > MA60
            score += 10
            reasons.append(f"趋势启动{trend_factor:.2%}")
        elif trend_factor > 0.98:  # 接近MA60
            score += 5
            reasons.append(f"趋势接近{trend_factor:.2%}")
        else:
            score -= 5  # 趋势向下扣分

        return min(100, score), " + ".join(reasons)


# ========== 股票筛选模块 ==========
def screen_volume_breakout_stocks(stock_pool, end_date=None):
    """
    筛选低位放量突破股票

    参数:
        stock_pool: 股票代码列表
        end_date: 结束日期 'YYYY-MM-DD'

    返回:
        筛选结果列表
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    start_date = (pd.Timestamp(end_date) - pd.Timedelta(days=StrategyConfig.HISTORY_DAYS)).strftime('%Y-%m-%d')

    results = []
    failed_count = 0
    total = len(stock_pool)

    print(f"\n开始筛选 {total} 只股票...")

    for idx, symbol in enumerate(stock_pool, 1):
        # 进度显示
        if idx % 100 == 0 or idx == total:
            print(f"进度: {idx}/{total} ({idx/total*100:.1f}%)")

        try:
            # 获取历史数据
            df = DataResilient.fetch_stock_data(
                symbol=symbol.replace('SHSE.', '').replace('SZSE.', ''),
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                use_cache=True
            )

            if df is None or df.empty or len(df) < StrategyConfig.MA_PERIOD:
                failed_count += 1
                continue

            # 计算所有因子
            df = FactorCalculator.calculate_all_factors(df)

            if df is None or df.empty:
                failed_count += 1
                continue

            # 计算得分
            score, reason = FactorCalculator.calculate_stock_score(df)

            if score > 0:
                latest = df.iloc[-1]
                results.append({
                    'symbol': symbol,
                    'score': score,
                    'reason': reason,
                    'price': latest['close'],
                    'date': df.index[-1].strftime('%Y-%m-%d'),
                    'volume_expansion': latest['volume_expansion_factor'],
                    'price_position': latest['price_position_factor'],
                    'trend_factor': latest['trend_factor']
                })

        except Exception as e:
            failed_count += 1
            continue

    print(f"\n筛选完成: 成功 {total - failed_count}, 失败 {failed_count}")

    # 按得分排序
    results.sort(key=lambda x: x['score'], reverse=True)

    return results


# ========== 回测模块 ==========
def backtest_strategy(stock_list, end_date=None):
    """
    回测低位放量突破策略

    参数:
        stock_list: 股票列表（包含 symbol, price, date 等信息）
        end_date: 回测结束日期

    返回:
        回测结果 DataFrame
    """
    if not stock_list:
        print("没有选中股票，跳过回测")
        return None

    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    print(f"\n开始回测 {len(stock_list)} 只股票...")

    backtest_results = []

    for stock in stock_list:
        symbol = stock['symbol']
        buy_price = stock['price']
        buy_date = stock['date']

        # 获取后续数据用于回测
        start_date = (pd.Timestamp(buy_date) + pd.Timedelta(days=1)).strftime('%Y%m%d')
        forecast_end = (pd.Timestamp(buy_date) + pd.Timedelta(days=StrategyConfig.HOLDING_DAYS)).strftime('%Y%m%d')

        try:
            future_df = DataResilient.fetch_stock_data(
                symbol=symbol.replace('SHSE.', '').replace('SZSE.', ''),
                start_date=start_date,
                end_date=forecast_end,
                use_cache=True
            )

            if future_df is None or future_df.empty:
                continue

            # 模拟持有期间的收益
            max_price = buy_price
            min_price = buy_price
            final_price = buy_price
            exit_days = StrategyConfig.HOLDING_DAYS
            exit_reason = "到期"

            for i, (idx, row) in enumerate(future_df.iterrows()):
                current_price = row['close']

                # 更新最高价和最低价
                max_price = max(max_price, current_price)
                min_price = min(min_price, current_price)

                # 检查止盈
                profit_pct = (current_price - buy_price) / buy_price
                if profit_pct >= StrategyConfig.TAKE_PROFIT_PCT:
                    final_price = current_price
                    exit_days = i + 1
                    exit_reason = "止盈"
                    break

                # 检查止损
                if profit_pct <= StrategyConfig.STOP_LOSS_PCT:
                    final_price = current_price
                    exit_days = i + 1
                    exit_reason = "止损"
                    break

                final_price = current_price

            # 计算收益率
            total_return = (final_price - buy_price) / buy_price

            backtest_results.append({
                'symbol': symbol,
                'buy_price': buy_price,
                'final_price': final_price,
                'total_return': total_return,
                'exit_days': exit_days,
                'exit_reason': exit_reason,
                'max_price': max_price,
                'min_price': min_price,
                'max_drawdown': (min_price - buy_price) / buy_price
            })

        except Exception as e:
            continue

    if not backtest_results:
        print("回测失败：没有有效数据")
        return None

    # 转换为 DataFrame
    results_df = pd.DataFrame(backtest_results)

    # 计算汇总指标
    total_trades = len(results_df)
    win_trades = len(results_df[results_df['total_return'] > 0])
    loss_trades = total_trades - win_trades
    win_rate = win_trades / total_trades if total_trades > 0 else 0

    avg_return = results_df['total_return'].mean()
    avg_win = results_df[results_df['total_return'] > 0]['total_return'].mean() if win_trades > 0 else 0
    avg_loss = results_df[results_df['total_return'] <= 0]['total_return'].mean() if loss_trades > 0 else 0

    max_profit = results_df['total_return'].max()
    max_loss = results_df['total_return'].min()
    max_drawdown = results_df['max_drawdown'].min()

    print("\n" + "="*60)
    print("回测结果汇总")
    print("="*60)
    print(f"总交易次数: {total_trades}")
    print(f"盈利次数: {win_trades} | 亏损次数: {loss_trades}")
    print(f"胜率: {win_rate:.2%}")
    print(f"平均收益率: {avg_return:.2%}")
    print(f"平均盈利: {avg_win:.2%} | 平均亏损: {avg_loss:.2%}")
    print(f"最大盈利: {max_profit:.2%} | 最大亏损: {max_loss:.2%}")
    print(f"最大回撤: {max_drawdown:.2%}")
    print("="*60)

    return results_df


# ========== 报告生成模块 ==========
def generate_report(screening_results, backtest_df=None):
    """
    生成策略报告

    参数:
        screening_results: 筛选结果列表
        backtest_df: 回测结果 DataFrame
    """
    # 创建输出目录
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "outputs"
    )
    os.makedirs(output_dir, exist_ok=True)

    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    txt_filename = os.path.join(output_dir, f"volume_breakout_{timestamp}.txt")

    # 准备输出内容
    output_lines = []
    output_lines.append("="*80)
    output_lines.append("低位放量突破策略 - 筛选结果报告")
    output_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output_lines.append("="*80)
    output_lines.append("")

    # 策略说明
    output_lines.append("【策略参数】")
    output_lines.append(f"  市值范围: {StrategyConfig.MIN_MARKET_CAP}亿 ~ {StrategyConfig.MAX_MARKET_CAP}亿")
    output_lines.append(f"  低位阈值: 价格/250日高点 < {StrategyConfig.PRICE_POSITION_THRESHOLD:.0%}")
    output_lines.append(f"  放量条件: 5日均量 > 20日均量 * {StrategyConfig.VOLUME_EXPANSION_RATIO}")
    output_lines.append(f"  持有天数: {StrategyConfig.HOLDING_DAYS}天")
    output_lines.append(f"  止盈/止损: {StrategyConfig.TAKE_PROFIT_PCT:.0%} / {StrategyConfig.STOP_LOSS_PCT:.0%}")
    output_lines.append("")

    # 筛选结果
    output_lines.append("【筛选结果】")
    top_results = screening_results[:StrategyConfig.TOP_N_STOCKS]

    if top_results:
        output_lines.append(f"{'排名':<6}{'代码':<15}{'得分':<8}{'价格':<10}{'放量倍数':<10}{'价格位置':<12}{'趋势':<10}{'判定依据'}")
        output_lines.append("-"*100)

        for idx, stock in enumerate(top_results, 1):
            line = f"{idx:<6}{stock['symbol']:<15}{stock['score']:<8.1f}{stock['price']:<10.2f}"
            line += f"{stock['volume_expansion']:<10.2f}{stock['price_position']:<12.2%}{stock['trend_factor']:<10.2%}"
            line += f"{stock['reason']}"
            output_lines.append(line)
    else:
        output_lines.append("当前无符合条件的股票")

    output_lines.append("")
    output_lines.append("="*80)

    # 回测结果
    if backtest_df is not None and not backtest_df.empty:
        output_lines.append("")
        output_lines.append("【回测结果】")

        total_trades = len(backtest_df)
        win_trades = len(backtest_df[backtest_df['total_return'] > 0])
        win_rate = win_trades / total_trades if total_trades > 0 else 0

        output_lines.append(f"总交易次数: {total_trades}")
        output_lines.append(f"胜率: {win_rate:.2%}")
        output_lines.append(f"平均收益率: {backtest_df['total_return'].mean():.2%}")
        output_lines.append(f"最大回撤: {backtest_df['max_drawdown'].min():.2%}")

        # 详细回测记录（Top 10）
        output_lines.append("")
        output_lines.append("【详细回测记录（Top 10）】")
        output_lines.append(f"{'代码':<15}{'买入价':<10}{'卖出价':<10}{'收益率':<10}{'天数':<8}{'退出原因'}")
        output_lines.append("-"*80)

        for _, row in backtest_df.head(10).iterrows():
            line = f"{row['symbol']:<15}{row['buy_price']:<10.2f}{row['final_price']:<10.2f}"
            line += f"{row['total_return']:<10.2%}{row['exit_days']:<8}{row['exit_reason']}"
            output_lines.append(line)

    output_lines.append("")
    output_lines.append("="*80)

    # 写入文件
    with open(txt_filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    # 同时输出到控制台
    print('\n'.join(output_lines))
    print(f"\n报告已保存至: {txt_filename}")

    return txt_filename


# ========== 主程序 ==========
def main():
    """主程序入口"""
    print("="*70)
    print("低位放量突破策略 v1.0")
    print("="*70)
    print()

    # 初始化缓存
    CacheManager.initialize()

    # 获取当前日期
    end_date = datetime.now().strftime('%Y-%m-%d')

    # 1. 获取全市场股票池
    print(f"\n【步骤1】获取全市场股票池")
    stock_pool = get_all_a_stocks(end_date)

    if not stock_pool:
        print("未获取到股票池，退出")
        return

    # 2. 筛选低位放量突破股票
    print(f"\n【步骤2】筛选低位放量突破股票")
    screening_results = screen_volume_breakout_stocks(stock_pool, end_date)

    if not screening_results:
        print("未筛选到符合条件的股票")
        return

    print(f"\n筛选到 {len(screening_results)} 只符合条件的股票")

    # 3. 回测验证（仅对 Top N 股票进行回测）
    print(f"\n【步骤3】回测验证（Top {min(StrategyConfig.TOP_N_STOCKS, len(screening_results))} 只股票）")
    top_stocks = screening_results[:StrategyConfig.TOP_N_STOCKS]
    backtest_df = backtest_strategy(top_stocks, end_date)

    # 4. 生成报告
    print(f"\n【步骤4】生成策略报告")
    generate_report(screening_results, backtest_df)

    print("\n策略执行完成！")


if __name__ == "__main__":
    main()
