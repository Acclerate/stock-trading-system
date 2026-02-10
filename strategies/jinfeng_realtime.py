"""
掘金SDK实时股票分析工具
支持实时行情获取和技术分析

新增功能：
- 多股票同时监控
- 信号提醒
- 配置文件支持
"""
import sys
import os
import time
from datetime import datetime, timedelta

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from data.diggold_data import DiggoldDataSource
from gm.api import (
    set_token,
    history,
    history_n,
    get_instruments,
    get_trading_dates,
    current,
    last_tick
)

# 导入实时监控模块
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from realtime_monitor.indicator_engine import IndicatorEngine
from realtime_monitor.signal_alert import SignalAlert
from realtime_monitor.monitor_config import MonitorConfig

# 技术指标库
import talib


class JinFengRealtimeAnalyzer:
    """掘金实时分析器 - 完全实时模式"""

    def __init__(self, token=None, use_cache=False):
        """
        初始化分析器

        参数:
            token: 掘金Token
            use_cache: 是否使用缓存（False=完全实时模式）
        """
        self.token = token or DiggoldDataSource.TOKEN
        self.initialized = False
        self.use_cache = use_cache  # 默认禁用缓存
        self.last_update_time = None
        self.cached_data = None

    def init(self):
        """初始化掘金SDK"""
        try:
            if not self.token:
                print("❌ 错误: 未配置DIGGOLD_TOKEN")
                return False

            set_token(self.token)
            self.initialized = True
            print("✅ 掘金SDK初始化成功 (实时模式)")
            return True
        except Exception as e:
            print(f"❌ 掘金SDK初始化失败: {e}")
            return False

    def get_realtime_data(self, symbol, frequency='60s', use_intraday=True):
        """
        获取实时行情数据（完全实时，无缓存）

        参数:
            symbol: 股票代码
            frequency: 数据频率 'tick', '60s'(1分钟), '300s'(5分钟), '1d'
            use_intraday: 是否使用日内分钟线数据
        """
        try:
            diggold_symbol = DiggoldDataSource.convert_symbol_to_diggold(symbol)
            print(f"📡 获取实时行情: {diggold_symbol} (频率: {frequency})")

            # 获取历史数据用于计算指标（使用较短周期确保数据新鲜）
            if use_intraday and frequency != '1d':
                # 分钟线模式：获取最近3天的分钟线数据
                end_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d 09:30:00')

                df = history(
                    symbol=diggold_symbol,
                    frequency=frequency,
                    start_time=start_date,
                    end_time=end_date,
                    adjust=DiggoldDataSource.ADJUST_PREV,
                    df=True
                )
            else:
                # 日线模式：获取最近60天数据
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')

                df = DiggoldDataSource.get_stock_history(
                    symbol=diggold_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    frequency='1d',
                    adjust=DiggoldDataSource.ADJUST_PREV
                )

            if df.empty:
                print(f"❌ 未获取到数据")
                return None

            # 获取最新实时tick数据并更新最后一根K线
            current_tick = self._get_latest_tick(diggold_symbol)
            if current_tick:
                df = self._update_with_tick(df, current_tick, frequency)
                print(f"✅ 已更新至最新tick数据")
            else:
                print(f"⚠️ 未能获取tick数据，使用最新K线")

            self.last_update_time = datetime.now()
            return df

        except Exception as e:
            print(f"❌ 获取数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_latest_tick(self, diggold_symbol):
        """获取最新tick数据"""
        try:
            # 使用last_tick函数获取最新tick（直接从服务器获取，无缓存）
            tick_data = last_tick(symbols=[diggold_symbol])
            if tick_data and len(tick_data) > 0:
                return tick_data[0]
            return None
        except Exception:
            # 如果tick不可用，回退到current函数
            try:
                tick_data = current(symbols=[diggold_symbol])
                if tick_data and len(tick_data) > 0:
                    return tick_data[0]
            except Exception:
                pass
            return None

    def _update_with_tick(self, df, tick_data, frequency):
        """用tick数据更新最后一根K线"""
        if df.empty or not tick_data:
            return df

        try:
            # 获取当前时间（去除时区信息以保持一致）
            now = pd.Timestamp.now()

            # 获取最后一根K线的时间
            last_idx = df.index[-1]
            # 确保时间戳格式一致
            if hasattr(last_idx, 'tz_localize'):
                last_time = pd.Timestamp(last_idx).tz_localize(None)
            else:
                last_time = pd.Timestamp(last_idx)

            # 计算K线周期（秒）
            freq_seconds = 60
            if frequency == '300s':
                freq_seconds = 300
            elif frequency == '900s':
                freq_seconds = 900
            elif frequency == '1800s':
                freq_seconds = 1800
            elif frequency == '1d':
                freq_seconds = 86400

            # 如果当前时间仍在最后一根K线的时间范围内，更新最后一根K线
            time_diff = (now - last_time).total_seconds()

            if time_diff < freq_seconds:
                # 更新最后一根K线
                latest = df.iloc[-1].copy()

                # 更新价格数据
                if 'price' in tick_data or 'last_price' in tick_data:
                    latest_price = tick_data.get('price', tick_data.get('last_price', latest['close']))
                    latest['close'] = latest_price
                    latest['high'] = max(latest['high'], latest_price)
                    latest['low'] = min(latest['low'], latest_price)

                # 更新成交量/额
                if 'volume' in tick_data:
                    latest['volume'] = tick_data['volume']
                if 'amount' in tick_data:
                    latest['amount'] = tick_data['amount']

                df.iloc[-1] = latest
                print(f"🔄 更新最后一根K线: {latest['close']:.2f}元")
            else:
                # 需要新K线，但为了保持技术指标连续性，暂不添加
                print(f"⚠️ 超出K线周期，等待下根K线形成")

        except Exception as e:
            print(f"⚠️ 更新tick数据时出错: {e}")

        return df

    def get_current_price(self, symbol):
        """获取实时行情价格"""
        try:
            diggold_symbol = DiggoldDataSource.convert_symbol_to_diggold(symbol)
            print(f"📡 获取实时价格: {diggold_symbol}")

            # 使用current函数获取实时行情（返回list）
            tick_data = current(symbols=[diggold_symbol])

            if tick_data and len(tick_data) > 0:
                # tick_data是list，取第一个元素
                latest = tick_data[0]

                # 将dict转换为Series以便访问
                if isinstance(latest, dict):
                    price = latest.get('price', latest.get('last_price', 0))
                    print(f"\n{'='*60}")
                    print(f"📊 实时行情")
                    print(f"{'='*60}")
                    print(f"股票代码: {diggold_symbol}")
                    print(f"最新价格: {price:.2f} 元")
                    if 'volume' in latest:
                        print(f"成交量: {latest['volume']:,.0f}")
                    if 'amount' in latest:
                        print(f"成交额: {latest['amount']:,.0f}")
                    print(f"更新时间: {datetime.now().strftime('%H:%M:%S')}")
                    print(f"{'='*60}\n")
                    return latest
                else:
                    print(f"⚠️ 数据格式异常: {type(latest)}")
                    return None
            else:
                print("⚠️ 未能获取到实时数据（可能休市）")
                return None

        except Exception as e:
            print(f"❌ 获取实时价格失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def calculate_indicators(self, df):
        """计算技术指标"""
        print(f"📊 获取到 {len(df)} 条数据，开始计算指标...")

        if len(df) < 20:
            print("❌ 数据太少，无法进行分析")
            return None

        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        volume = df['volume'].values.astype(float)

        # 均线系统
        df['ma5'] = talib.SMA(close, timeperiod=5)
        df['ma10'] = talib.SMA(close, timeperiod=10)
        df['ma20'] = talib.SMA(close, timeperiod=20)
        if len(df) >= 60:
            df['ma60'] = talib.SMA(close, timeperiod=60)
        else:
            df['ma60'] = np.nan

        # MACD
        macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_hist'] = macd_hist

        # RSI
        df['rsi'] = talib.RSI(close, timeperiod=14)
        df['rsi_6'] = talib.RSI(close, timeperiod=6)

        # KDJ
        slowk, slowd = talib.STOCH(high, low, close, fastk_period=9,
                                    slowk_period=3, slowd_period=3)
        df['kdj_k'] = slowk
        df['kdj_d'] = slowd
        df['kdj_j'] = 3 * slowk - 2 * slowd

        # 布林带
        boll_upper, boll_mid, boll_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
        df['boll_upper'] = boll_upper
        df['boll_mid'] = boll_mid
        df['boll_lower'] = boll_lower

        # ATR（真实波幅）
        df['atr'] = talib.ATR(high, low, close, timeperiod=14)

        # 成交量指标
        df['volume_ma5'] = talib.SMA(volume, timeperiod=5)
        df['volume_ratio'] = df['volume'] / df['volume_ma5']

        # ADX（趋势强度）
        df['adx'] = talib.ADX(high, low, close, timeperiod=14)

        return df

    def analyze_signal(self, df, stock_name, position_price=None):
        """分析买卖信号"""
        if df is None or df.empty:
            print("❌ 无数据可分析")
            return

        latest = df.iloc[-1]
        latest_date = df.index[-1].strftime('%Y-%m-%d')

        # 打印标题
        print(f"\n{'='*80}")
        print(f"📊 {stock_name} 实时技术分析报告")
        print(f"{'='*80}")
        print(f"📅 数据时间: {latest_date}")
        print(f"📈 当前价格: {latest['close']:.2f} 元")

        if position_price:
            profit_loss = (latest['close'] - position_price) / position_price * 100
            print(f"💰 成本价: {position_price:.2f} 元")
            print(f"📊 盈亏: {profit_loss:+.2f}%")

        # 检查是否有有效数据
        if pd.isna(latest.get('ma5', np.nan)):
            print("\n⚠️ 数据不足，无法进行完整的技术分析")
            return None

        print(f"\n{'='*80}")
        print(f"📈 均线系统")
        print(f"{'='*80}")
        print(f"MA5  : {latest['ma5']:>8.2f} 元  {'↑' if latest['close'] > latest['ma5'] else '↓'}  距离: {(latest['close']/latest['ma5']-1)*100:+.2f}%")
        print(f"MA10 : {latest['ma10']:>8.2f} 元  {'↑' if latest['close'] > latest['ma10'] else '↓'}  距离: {(latest['close']/latest['ma10']-1)*100:+.2f}%")
        print(f"MA20 : {latest['ma20']:>8.2f} 元  {'↑' if latest['close'] > latest['ma20'] else '↓'}  距离: {(latest['close']/latest['ma20']-1)*100:+.2f}%")
        print(f"MA60 : {latest['ma60']:>8.2f} 元  {'↑' if latest['close'] > latest['ma60'] else '↓'}  距离: {(latest['close']/latest['ma60']-1)*100:+.2f}%")

        # 均线排列判断
        if latest['ma5'] > latest['ma10'] > latest['ma20']:
            ma_trend = "🟢 多头排列（看多）"
        elif latest['ma5'] < latest['ma10'] < latest['ma20']:
            ma_trend = "🔴 空头排列（看空）"
        else:
            ma_trend = "🟡 均线纠缠（震荡）"
        print(f"\n均线趋势: {ma_trend}")

        print(f"\n{'='*80}")
        print(f"📊 MACD指标")
        print(f"{'='*80}")
        print(f"DIF   : {latest['macd']:>8.4f}")
        print(f"DEA   : {latest['macd_signal']:>8.4f}")
        print(f"MACD  : {latest['macd_hist']:>8.4f}")
        macd_status = "🟢 金叉（买入信号）" if latest['macd'] > latest['macd_signal'] else "🔴 死叉（卖出信号）"
        if latest['macd_hist'] > 0:
            macd_bar = "红柱（多头）"
        else:
            macd_bar = "绿柱（空头）"
        print(f"\nMACD信号: {macd_status} | {macd_bar}")

        print(f"\n{'='*80}")
        print(f"📉 RSI指标")
        print(f"{'='*80}")
        print(f"RSI(6)  : {latest['rsi_6']:>8.2f}")
        print(f"RSI(14) : {latest['rsi']:>8.2f}")
        if latest['rsi'] > 80:
            rsi_status = "🔴 严重超买"
        elif latest['rsi'] > 70:
            rsi_status = "🟠 超买区域"
        elif latest['rsi'] < 20:
            rsi_status = "🟢 严重超卖"
        elif latest['rsi'] < 30:
            rsi_status = "🟡 超卖区域"
        else:
            rsi_status = "○ 中性区域"
        print(f"\nRSI状态: {rsi_status}")

        print(f"\n{'='*80}")
        print(f"🎯 KDJ指标")
        print(f"{'='*80}")
        print(f"K值: {latest['kdj_k']:.2f}")
        print(f"D值: {latest['kdj_d']:.2f}")
        print(f"J值: {latest['kdj_j']:.2f}")
        if latest['kdj_k'] > latest['kdj_d']:
            kdj_signal = "🟢 金叉（买入信号）"
        else:
            kdj_signal = "🔴 死叉（卖出信号）"
        if latest['kdj_j'] > 100:
            kdj_status = "超买"
        elif latest['kdj_j'] < 0:
            kdj_status = "超卖"
        else:
            kdj_status = "中性"
        print(f"\nKDJ信号: {kdj_signal} | {kdj_status}")

        print(f"\n{'='*80}")
        print(f"📊 布林带")
        print(f"{'='*80}")
        print(f"上轨: {latest['boll_upper']:.2f} 元")
        print(f"中轨: {latest['boll_mid']:.2f} 元")
        print(f"下轨: {latest['boll_lower']:.2f} 元")
        print(f"当前: {latest['close']:.2f} 元")

        boll_width = (latest['boll_upper'] - latest['boll_lower']) / latest['boll_mid'] * 100
        boll_position = (latest['close'] - latest['boll_lower']) / (latest['boll_upper'] - latest['boll_lower']) * 100

        print(f"\n布林带宽度: {boll_width:.2f}% ({'喇叭开口' if boll_width > 10 else '收口'})")
        print(f"价格位置: {boll_position:.0f}% ({'上轨附近' if boll_position > 80 else '下轨附近' if boll_position < 20 else '中间区域'})")

        print(f"\n{'='*80}")
        print(f"📊 成交量分析")
        print(f"{'='*80}")
        print(f"今日成交: {latest['volume']:,.0f}")
        print(f"5日均量: {latest['volume_ma5']:,.0f}")
        print(f"量比: {latest['volume_ratio']:.2f}倍")

        volume_status = "放量" if latest['volume_ratio'] > 1.5 else "缩量" if latest['volume_ratio'] < 0.8 else "正常"
        print(f"成交状态: {volume_status}")

        print(f"\n{'='*80}")
        print(f"📊 ADX趋势强度")
        print(f"{'='*80}")
        print(f"ADX(14): {latest['adx']:.2f}")
        if latest['adx'] > 40:
            adx_status = "强趋势"
        elif latest['adx'] > 25:
            adx_status = "有趋势"
        else:
            adx_status = "震荡/无趋势"
        print(f"趋势强度: {adx_status}")

        print(f"\n{'='*80}")
        print(f"🎯 综合评分")
        print(f"{'='*80}")

        score = 0
        max_score = 6

        # 1. 均线趋势
        if latest['close'] > latest['ma5'] > latest['ma10']:
            score += 1
            print("✓ 短期均线多头 (+1分)")
        elif latest['close'] > latest['ma5']:
            print("○ 股价站上MA5 (0分)")
        else:
            print("✗ 股价在MA5之下 (0分)")

        # 2. MACD
        if latest['macd'] > latest['macd_signal'] and latest['macd_hist'] > 0:
            score += 1
            print("✓ MACD金叉且红柱 (+1分)")
        elif latest['macd'] > latest['macd_signal']:
            print("○ MACD金叉但绿柱 (0分)")
        else:
            print("✗ MACD死叉 (0分)")

        # 3. RSI
        if 30 < latest['rsi'] < 70:
            score += 1
            print("✓ RSI健康区间 (+1分)")
        elif latest['rsi'] < 30:
            print("○ RSI超卖 (0分)")
        else:
            print("✗ RSI超买 (0分)")

        # 4. KDJ
        if latest['kdj_k'] > latest['kdj_d'] and latest['kdj_j'] > latest['kdj_k']:
            score += 1
            print("✓ KDJ金叉且J值向上 (+1分)")
        elif latest['kdj_k'] > latest['kdj_d']:
            print("○ KDJ金叉 (0分)")
        else:
            print("✗ KDJ死叉 (0分)")

        # 5. 布林带
        if latest['boll_lower'] < latest['close'] < latest['boll_mid']:
            score += 1
            print("✓ 价格在中下轨之间 (+1分)")
        elif latest['close'] <= latest['boll_lower']:
            print("○ 价格触及下轨 (0分)")
        else:
            print("✗ 价格在中轨之上 (0分)")

        # 6. 成交量
        if latest['volume_ratio'] > 1.2:
            score += 1
            print("✓ 成交量放大 (+1分)")
        elif latest['volume_ratio'] > 0.8:
            print("○ 成交量正常 (0分)")
        else:
            print("✗ 成交量萎缩 (0分)")

        print(f"\n综合得分: {score}/{max_score} 分")

        print(f"\n{'='*80}")
        print(f"💡 操作建议")
        print(f"{'='*80}")

        if score >= 5:
            print("🟢 强烈买入信号")
            print("   建议: 可考虑分批买入")
        elif score >= 4:
            print("🟢 买入信号")
            print("   建议: 可适量买入")
        elif score >= 3:
            print("🟡 观望")
            print("   建议: 持币观望，等待更好时机")
        elif score >= 2:
            print("🟠 谨慎持有")
            print("   建议: 已持有可减仓")
        else:
            print("🔴 卖出信号")
            print("   建议: 建议止损离场")

        # 近期涨跌
        print(f"\n{'='*80}")
        print(f"📊 近期表现")
        print(f"{'='*80}")
        for days in [3, 5, 10, 20]:
            if len(df) > days:
                change = (df['close'].iloc[-1] / df['close'].iloc[-days-1] - 1) * 100
                bar = self._get_change_bar(change)
                print(f"近{days:2d}日: {change:>+6.2f}% {bar}")

        print(f"\n{'='*80}\n")

        return score

    def _get_change_bar(self, change):
        """生成涨跌图形"""
        if change > 0:
            bars = int(change / 2)
            return "📈" + "█" * min(bars, 10)
        elif change < 0:
            bars = int(abs(change) / 2)
            return "📉" + "▓" * min(bars, 10)
        else:
            return "➡️"

    def get_support_resistance(self, df):
        """计算支撑位和阻力位"""
        if len(df) < 20:
            return None, None

        latest = df.iloc[-1]
        current_price = latest['close']

        # 简单支撑阻力计算
        recent_high = df['high'].tail(20).max()
        recent_low = df['low'].tail(20).min()

        # 均线支撑
        ma_support = latest['ma20']
        ma_resistance = latest['ma5'] if latest['ma5'] > current_price else latest['ma10']

        print(f"\n{'='*80}")
        print(f"🎯 支撑位与阻力位")
        print(f"{'='*80}")
        print(f"当前价格: {current_price:.2f} 元")
        print(f"\n上方阻力:")
        print(f"  - MA5 : {latest['ma5']:.2f} 元")
        print(f"  - MA10: {latest['ma10']:.2f} 元")
        print(f"  - 近期高点: {recent_high:.2f} 元")
        print(f"\n下方支撑:")
        print(f"  - MA20: {latest['ma20']:.2f} 元")
        print(f"  - MA60: {latest['ma60']:.2f} 元")
        print(f"  - 近期低点: {recent_low:.2f} 元")
        print(f"  - 布林下轨: {latest['boll_lower']:.2f} 元")

        # 止损止盈建议
        print(f"\n{'='*80}")
        print(f"🛡️ 风险控制建议")
        print(f"{'='*80}")

        stop_loss = latest['boll_lower'] * 0.98  # 布林下轨下方2%
        take_profit = latest['boll_upper'] * 0.98  # 布林上轨附近

        print(f"建议止损价: {stop_loss:.2f} 元 ({(stop_loss/current_price-1)*100:.2f}%)")
        print(f"建议止盈价: {take_profit:.2f} 元 ({(take_profit/current_price-1)*100:.2f}%)")
        print(f"风险收益比: 1:{abs((take_profit-current_price)/(current_price-stop_loss)):.2f}")

    def continuous_monitor(self, symbol, stock_name, interval_seconds=30, max_updates=None):
        """
        持续监控股票实时行情

        参数:
            symbol: 股票代码
            stock_name: 股票名称
            interval_seconds: 更新间隔（秒）
            max_updates: 最大更新次数，None表示无限
        """
        print(f"\n{'='*80}")
        print(f"🔄 开启持续监控模式")
        print(f"{'='*80}")
        print(f"股票: {stock_name} ({symbol})")
        print(f"更新间隔: {interval_seconds}秒")
        print(f"按 Ctrl+C 停止监控\n")

        update_count = 0
        prev_score = None
        prev_price = None

        try:
            while True:
                if max_updates and update_count >= max_updates:
                    print(f"\n⏹️ 达到最大更新次数 ({max_updates})，停止监控")
                    break

                update_count += 1
                current_time = datetime.now()

                # 判断是否在交易时间
                hour, minute = current_time.hour, current_time.minute
                is_trading_time = (
                    (9 <= hour < 15) and
                    not (hour == 11 and minute > 30) and
                    not (hour == 12)
                )

                if not is_trading_time:
                    print(f"⏸️ {current_time.strftime('%H:%M:%S')} - 非交易时间，休眠中...")
                    time.sleep(interval_seconds)
                    continue

                # 清屏效果（打印分隔线）
                print(f"\n{'='*80}")
                print(f"📊 第 {update_count} 次更新 - {current_time.strftime('%H:%M:%S')}")
                print(f"{'='*80}")

                # 获取实时数据
                df = self.get_realtime_data(symbol, frequency='60s', use_intraday=True)
                if df is None or df.empty:
                    print("⚠️ 获取数据失败，等待下次更新...")
                    time.sleep(interval_seconds)
                    continue

                # 计算指标
                df = self.calculate_indicators(df)
                if df is None:
                    time.sleep(interval_seconds)
                    continue

                # 获取最新价格
                latest_price = df['close'].iloc[-1]

                # 分析信号
                score = self.analyze_signal(df, stock_name)

                # 价格变化提示
                if prev_price is not None:
                    price_change = latest_price - prev_price
                    change_pct = (price_change / prev_price) * 100
                    if abs(change_pct) > 0.5:
                        arrow = "📈" if price_change > 0 else "📉"
                        print(f"\n{arrow} 价格变化: {change_pct:+.2f}% ({prev_price:.2f} -> {latest_price:.2f})")

                # 评分变化提示
                if prev_score is not None and score != prev_score:
                    score_diff = score - prev_score
                    arrow = "📈" if score_diff > 0 else "📉"
                    print(f"{arrow} 评分变化: {prev_score} -> {score} ({score_diff:+d})")

                prev_score = score
                prev_price = latest_price

                # 等待下次更新
                print(f"\n⏳ 等待 {interval_seconds} 秒后下次更新...")
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print(f"\n\n⏹️ 用户停止监控")
            print(f"{'='*80}")
            print(f"📊 监控统计")
            print(f"{'='*80}")
            print(f"总更新次数: {update_count}")
            print(f"最后价格: {prev_price:.2f} 元" if prev_price else "无数据")
            print(f"最后评分: {prev_score}" if prev_score is not None else "无数据")
            print(f"{'='*80}\n")

    def continuous_monitor_multi(self, config: MonitorConfig):
        """
        多股票持续监控

        使用线程池并发处理多只股票

        参数:
            config: MonitorConfig 配置对象
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        enabled_stocks = config.get_enabled_stocks()

        if not enabled_stocks:
            print("❌ 没有启用的股票，请检查配置文件")
            return

        print(f"\n{'='*80}")
        print(f"🔄 开启多股票持续监控模式")
        print(f"{'='*80}")
        print(f"股票数量: {len(enabled_stocks)}")
        print(f"更新间隔: {config.interval_seconds}秒")
        print(f"并发线程: {config.max_workers}")
        print(f"按 Ctrl+C 停止监控\n")

        # 创建信号提醒器
        signal_alert = SignalAlert()

        # 记录每只股票的信号状态
        signal_states = {}

        try:
            with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
                futures = {}

                for stock in enabled_stocks:
                    future = executor.submit(
                        self._monitor_single_stock_once,
                        stock,
                        config,
                        signal_alert,
                        signal_states
                    )
                    futures[future] = stock

                # 持续监控循环
                update_count = 0
                while True:
                    if config.max_updates_per_stock and update_count >= config.max_updates_per_stock:
                        print(f"\n⏹️ 达到最大更新次数 ({config.max_updates_per_stock})，停止监控")
                        break

                    update_count += 1
                    current_time = datetime.now()

                    # 判断是否在交易时间
                    hour, minute = current_time.hour, current_time.minute
                    is_trading_time = (
                        (9 <= hour < 15) and
                        not (hour == 11 and minute > 30) and
                        not (hour == 12)
                    )

                    if not is_trading_time:
                        print(f"⏸️ {current_time.strftime('%H:%M:%S')} - 非交易时间，休眠中...")
                        time.sleep(config.interval_seconds)
                        continue

                    # 重新提交所有股票的监控任务
                    new_futures = {}
                    for stock in enabled_stocks:
                        future = executor.submit(
                            self._monitor_single_stock_once,
                            stock,
                            config,
                            signal_alert,
                            signal_states
                        )
                        new_futures[future] = stock

                    # 等待所有任务完成
                    for future in as_completed(new_futures):
                        stock = new_futures[future]
                        try:
                            future.result(timeout=10)
                        except Exception as e:
                            print(f"⚠️ 监控 {stock['symbol']} 失败: {e}")

                    print(f"\n⏳ 等待 {config.interval_seconds} 秒后下次更新...")
                    time.sleep(config.interval_seconds)

        except KeyboardInterrupt:
            print(f"\n\n⏹️ 用户停止监控")
            print(f"{'='*80}")
            print(f"📊 监控统计")
            print(f"{'='*80}")
            print(f"总更新次数: {update_count}")
            print(f"{'='*80}\n")

    def _monitor_single_stock_once(self, stock, config: MonitorConfig,
                                    signal_alert: SignalAlert, signal_states: dict):
        """
        单股票单次监控（用于多股票模式）

        参数:
            stock: StockConfig 对象
            config: MonitorConfig 配置对象
            signal_alert: SignalAlert 对象
            signal_states: 信号状态字典
        """
        try:
            # 获取实时数据
            df = self.get_realtime_data(stock.symbol, frequency='60s', use_intraday=True)
            if df is None or df.empty:
                return

            # 使用新的指标引擎计算
            df = IndicatorEngine.calculate_all(df)
            if df is None:
                return

            # 生成信号
            current_signal = IndicatorEngine.generate_signal(df)

            # 获取当前价格
            latest_price = df['close'].iloc[-1]

            # 获取之前的信号状态
            prev_signal = signal_states.get(stock.symbol)

            # 检查信号是否变化
            if prev_signal is None or current_signal['signal'] != prev_signal.get('signal'):
                # 发送提醒
                signal_alert.send_alert(
                    symbol=stock.symbol,
                    name=stock.name,
                    current_signal=current_signal,
                    prev_signal=prev_signal,
                    price=latest_price
                )

                # 更新信号状态
                signal_states[stock.symbol] = current_signal

        except Exception as e:
            print(f"⚠️ 监控 {stock.symbol} 出错: {e}")


def main():
    """主函数 - 支持命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(description='掘金SDK实时股票分析系统')
    parser.add_argument('-s', '--symbol', type=str, default='002202',
                        help='股票代码 (默认: 002202)')
    parser.add_argument('-n', '--name', type=str, default='金风科技',
                        help='股票名称 (默认: 金风科技)')
    parser.add_argument('-p', '--price', type=float, default=None,
                        help='成本价 (可选)')
    parser.add_argument('-m', '--monitor', action='store_true',
                        help='持续监控模式')
    parser.add_argument('-i', '--interval', type=int, default=30,
                        help='监控更新间隔(秒) (默认: 30)')
    parser.add_argument('--max-updates', type=int, default=None,
                        help='最大更新次数 (默认: 无限制)')
    parser.add_argument('-f', '--frequency', type=str, default='60s',
                        choices=['tick', '60s', '300s', '900s', '1d'],
                        help='数据频率 (默认: 60s)')

    # 新增：多股票监控模式
    parser.add_argument('--mode', type=str, choices=['single', 'multi'], default='single',
                        help='运行模式: single=单股票, multi=多股票 (默认: single)')
    parser.add_argument('--config', type=str, default='strategies/watchlist.yaml',
                        help='配置文件路径 (多股票模式)')

    args = parser.parse_args()

    print("="*80)
    print("掘金SDK实时股票分析系统 - 完全实时模式")
    print("="*80)
    print(f"⏰ 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 数据频率: {args.frequency}")
    print(f"🔄 缓存状态: 已禁用 (完全实时)")

    # 初始化分析器 (禁用缓存)
    analyzer = JinFengRealtimeAnalyzer(use_cache=False)

    if not analyzer.init():
        print("❌ 初始化失败，请检查DIGGOLD_TOKEN配置")
        return

    # ========== 多股票监控模式 ==========
    if args.mode == 'multi':
        print(f"📋 多股票监控模式")
        print(f"📁 配置文件: {args.config}")

        try:
            config = MonitorConfig.from_yaml(args.config)
            enabled_stocks = config.get_enabled_stocks()
            print(f"✅ 加载了 {len(enabled_stocks)} 只股票")

            for stock in enabled_stocks:
                print(f"  - {stock.name} ({stock.symbol})")

            print(f"\n🔄 开始多股票监控...")
            analyzer.continuous_monitor_multi(config)
            return
        except FileNotFoundError:
            print(f"❌ 配置文件不存在: {args.config}")
            print(f"💡 提示: 运行 'python -m realtime_monitor.monitor_config' 创建默认配置")
            return
        except Exception as e:
            print(f"❌ 加载配置失败: {e}")
            return

    # ========== 单股票模式 ==========
    # 持续监控模式
    if args.monitor:
        analyzer.continuous_monitor(
            symbol=args.symbol,
            stock_name=args.name,
            interval_seconds=args.interval,
            max_updates=args.max_updates
        )
        return

    # 单次分析模式
    print(f"\n🔍 开始分析 {args.name} ({args.symbol})...")

    # 获取实时数据
    df = analyzer.get_realtime_data(args.symbol, frequency=args.frequency, use_intraday=True)

    if df is None or df.empty:
        print("❌ 获取数据失败")
        return

    # 计算指标
    df = analyzer.calculate_indicators(df)

    if df is None:
        return

    # 分析信号
    score = analyzer.analyze_signal(df, args.name, args.price)

    # 支撑阻力
    analyzer.get_support_resistance(df)

    # 根据得分给出操作建议
    if args.price is not None:
        print(f"\n{'='*80}")
        print(f"📋 操作建议")
        print(f"{'='*80}")

        if score <= 2:
            print("⚠️ 技术面评分较低，建议:")
            print("  1. 考虑减仓或止损")
            print("  2. 设置止损价")
            print("  3. 等待更好的入场时机")
        elif score <= 3:
            print("⚠️ 技术面中性，建议:")
            print("  1. 设置止损")
            print("  2. 观察后续走势")
            print("  3. 反弹至成本价附近可考虑减仓")
        else:
            print("✅ 技术面转好，建议:")
            print("  1. 可继续持有")
            print("  2. 设置移动止损")
            print("  3. 突破关键位可考虑加仓")

    print(f"\n{'='*80}")
    print("✅ 分析完成")
    print(f"提示: 使用 -m 参数可开启持续监控模式")
    print(f"示例: python jinfeng_realtime.py -s 002202 -m -i 10")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()